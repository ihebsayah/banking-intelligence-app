"""
services/validation_agent/query_validator.py

CRITICAL SECURITY MODULE — Validates SQL queries to prevent injection attacks.

Five checks (all must pass):
  1. syntax_check    — sqlparse can parse it
  2. select_only     — first statement is SELECT (no DML/DDL)
  3. keyword_check   — no dangerous keywords
  4. limit_check     — LIMIT clause present
  5. pattern_check   — no suspicious injection patterns

Also signs safe queries with HMAC to detect tampering.
"""
import hashlib
import hmac
import logging
import os
import re
import time
from typing import List, Tuple

try:
    import sqlparse
    HAS_SQLPARSE = True
except ImportError:
    HAS_SQLPARSE = False

from models import QueryValidationRequest, QueryValidationResponse

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# WARNING: Demo signing key — replace with secrets manager in production!
# ──────────────────────────────────────────────────────────────────────────────
SIGNING_KEY = os.getenv(
    "QUERY_SIGNING_KEY",
    "DEMO_KEY_CHANGE_IN_PRODUCTION_DO_NOT_USE_IN_PROD"
)

# ──────────────────────────────────────────────────────────────────────────────
# DANGEROUS KEYWORDS — any occurrence = instant reject
# ──────────────────────────────────────────────────────────────────────────────
DANGEROUS_KEYWORDS = {
    # DML mutations
    "DELETE", "INSERT", "UPDATE", "REPLACE", "MERGE", "UPSERT",
    # DDL
    "DROP", "CREATE", "ALTER", "TRUNCATE", "RENAME",
    # Privilege / system
    "GRANT", "REVOKE", "EXEC", "EXECUTE", "CALL",
    # Dangerous functions
    "SLEEP", "BENCHMARK", "LOAD_FILE", "OUTFILE", "DUMPFILE",
    "LOAD", "INTO OUTFILE", "INTO DUMPFILE",
    # Stored procs / scripting
    "PROCEDURE", "FUNCTION", "TRIGGER", "EVENT",
    # Info schema / system tables
    "INFORMATION_SCHEMA", "SYS", "MYSQL", "PG_CATALOG",
    "PG_SLEEP", "PG_READ_FILE",
    # Transaction abuse
    "COMMIT", "ROLLBACK", "SAVEPOINT",
    # Replication / backup
    "FLUSH", "RESET", "PURGE",
}

# ──────────────────────────────────────────────────────────────────────────────
# SUSPICIOUS PATTERNS — regex patterns indicating injection attempts
# ──────────────────────────────────────────────────────────────────────────────
SUSPICIOUS_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # Classic OR/AND bypass
    ("or_1_equals_1",       re.compile(r"\bOR\s+['\"]?1['\"]?\s*=\s*['\"]?1['\"]?", re.I)),
    ("and_1_equals_1",      re.compile(r"\bAND\s+['\"]?1['\"]?\s*=\s*['\"]?1['\"]?", re.I)),
    ("or_true",             re.compile(r"\bOR\s+TRUE\b", re.I)),
    ("and_false",           re.compile(r"\bAND\s+FALSE\b", re.I)),
    # UNION injection
    ("union_select",        re.compile(r"\bUNION\s+(ALL\s+)?SELECT\b", re.I)),
    # Stacked queries
    ("stacked_queries",     re.compile(r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC)\b", re.I)),
    # Comment stripping
    ("inline_comment",      re.compile(r"--\s*\S", re.I)),   # -- comment with content
    ("block_comment",       re.compile(r"/\*.*?\*/", re.I | re.S)),
    ("hash_comment",        re.compile(r"#.*$", re.I | re.M)),
    # Time-based blind injection
    ("sleep_call",          re.compile(r"\bSLEEP\s*\(", re.I)),
    ("benchmark_call",      re.compile(r"\bBENCHMARK\s*\(", re.I)),
    ("pg_sleep_call",       re.compile(r"\bPG_SLEEP\s*\(", re.I)),
    ("waitfor_delay",       re.compile(r"\bWAITFOR\s+DELAY\b", re.I)),
    # Boolean blind
    ("always_true_num",     re.compile(r"\b\d+\s*=\s*\d+\b")),   # 1=1, 2=2
    # Hex encoding bypass
    ("hex_bypass",          re.compile(r"\b0x[0-9a-fA-F]{2,}\b")),
    # Scientific notation bypass
    ("scientific_notation", re.compile(r"\b\d+e\d+\b", re.I)),
    # CHAR / encoding functions
    ("char_function",       re.compile(r"\bCHAR\s*\(", re.I)),
    ("ascii_function",      re.compile(r"\bASCII\s*\(", re.I)),
    ("concat_ws",           re.compile(r"\bCONCAT_WS\s*\(", re.I)),
    # Subquery abuse — any nested SELECT
    ("subselect_where",     re.compile(r"\bWHERE\s+\(?\s*SELECT\b", re.I)),
    ("nested_select",       re.compile(r"\(\s*SELECT\b", re.I)),  # catches = (SELECT ..)
    # System variable access
    ("sys_variable",        re.compile(r"@@\w+", re.I)),
    # LOAD / file read
    ("load_data",           re.compile(r"\bLOAD\s+DATA\b", re.I)),
    ("into_outfile",        re.compile(r"\bINTO\s+(OUT|DUMP)FILE\b", re.I)),
    # Information schema
    ("info_schema",         re.compile(r"\bINFORMATION_SCHEMA\b", re.I)),
    ("pg_catalog",          re.compile(r"\bPG_CATALOG\b", re.I)),
    # xp_cmdshell (MSSQL)
    ("xp_cmdshell",         re.compile(r"\bXP_CMDSHELL\b", re.I)),
    # Null byte
    ("null_byte",           re.compile(r"\x00")),
]


class QueryValidator:
    """
    Validates SQL queries for safety. All 5 checks must pass.
    Signs safe queries with HMAC.
    """

    def validate(self, request: QueryValidationRequest) -> QueryValidationResponse:
        sql = request.sql.strip()
        checks_passed: List[str] = []
        checks_failed: List[str] = []
        issues: List[str] = []

        # ── CHECK 1: SYNTAX ────────────────────────────────────────────────────
        try:
            if HAS_SQLPARSE:
                parsed = sqlparse.parse(sql)
                if not parsed or not parsed[0].tokens:
                    checks_failed.append("syntax_check")
                    issues.append("SQL could not be parsed — invalid syntax")
                    return self._unsafe(issues, checks_passed, checks_failed)
            else:
                # Pure-Python fallback: basic non-empty check
                if not sql.strip():
                    checks_failed.append("syntax_check")
                    issues.append("SQL is empty")
                    return self._unsafe(issues, checks_passed, checks_failed)
            checks_passed.append("syntax_check")
        except Exception as exc:
            checks_failed.append("syntax_check")
            issues.append(f"SQL parse error: {exc}")
            return self._unsafe(issues, checks_passed, checks_failed)

        # Normalised uppercase for keyword checks
        sql_upper = sql.upper()

        # ── CHECK 2: SELECT-ONLY ───────────────────────────────────────────────
        if HAS_SQLPARSE:
            stmt_type = sqlparse.parse(sql)[0].get_type()
        else:
            # Pure-Python fallback: first non-whitespace word
            first_word = sql_upper.split()[0] if sql_upper.split() else ""
            stmt_type = first_word if first_word in (
                "SELECT", "INSERT", "UPDATE", "DELETE", "DROP",
                "CREATE", "ALTER", "TRUNCATE", "EXEC", "LOAD"
            ) else "UNKNOWN"

        if stmt_type != "SELECT":
            checks_failed.append("select_only")
            issues.append(f"Non-SELECT statement detected: type='{stmt_type}'")
        else:
            checks_passed.append("select_only")

        # ── CHECK 3: DANGEROUS KEYWORDS ────────────────────────────────────────
        found_dangerous = []
        for kw in DANGEROUS_KEYWORDS:
            # word-boundary match
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, sql_upper):
                found_dangerous.append(kw)
        if found_dangerous:
            checks_failed.append("keyword_check")
            issues.append(f"Dangerous keyword(s) detected: {', '.join(found_dangerous)}")
        else:
            checks_passed.append("keyword_check")

        # ── CHECK 4: LIMIT CLAUSE ─────────────────────────────────────────────
        if "LIMIT" not in sql_upper:
            checks_failed.append("limit_check")
            issues.append("No LIMIT clause — query could return unbounded rows")
        else:
            checks_passed.append("limit_check")

        # ── CHECK 5: SUSPICIOUS PATTERNS ─────────────────────────────────────
        found_patterns = []
        for name, pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(sql):
                found_patterns.append(name)
        if found_patterns:
            checks_failed.append("pattern_check")
            issues.append(f"Suspicious injection pattern(s): {', '.join(found_patterns)}")
        else:
            checks_passed.append("pattern_check")

        # ── VERDICT ────────────────────────────────────────────────────────────
        safe = len(checks_failed) == 0
        confidence = len(checks_passed) / (len(checks_passed) + len(checks_failed))

        signature = None
        if safe:
            signature = self._sign_query(sql, request.parameters)

        # Sanitized SQL for safe logging
        if HAS_SQLPARSE:
            sanitized = sqlparse.format(sql, strip_comments=True, reindent=True)
        else:
            # Simple fallback: strip leading/trailing whitespace
            sanitized = " ".join(sql.split())

        logger.info(
            "Validation: safe=%s confidence=%.2f checks_failed=%s",
            safe, confidence, checks_failed
        )

        return QueryValidationResponse(
            safe=safe,
            confidence=round(confidence, 3),
            issues=issues,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            signature=signature,
            sanitized_sql=sanitized if safe else None,
        )

    def _sign_query(self, sql: str, parameters: list) -> str:
        """HMAC-SHA256 signature over (sql + parameters) for tamper detection."""
        message = sql + "|" + str(sorted(str(p) for p in parameters))
        sig = hmac.new(
            SIGNING_KEY.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        timestamp = int(time.time())
        return f"sha256:{sig}:{timestamp}"

    def verify_signature(self, sql: str, parameters: list, signature: str) -> bool:
        """Verify a previously signed query has not been tampered with."""
        try:
            parts = signature.split(":")
            if len(parts) != 3 or parts[0] != "sha256":
                return False
            expected_sig = parts[1]
            message = sql + "|" + str(sorted(str(p) for p in parameters))
            actual_sig = hmac.new(
                SIGNING_KEY.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected_sig, actual_sig)
        except Exception:
            return False

    def _unsafe(
        self,
        issues: List[str],
        checks_passed: List[str],
        checks_failed: List[str],
    ) -> QueryValidationResponse:
        total = len(checks_passed) + len(checks_failed)
        confidence = len(checks_passed) / total if total else 0.0
        return QueryValidationResponse(
            safe=False,
            confidence=round(confidence, 3),
            issues=issues,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            signature=None,
        )
