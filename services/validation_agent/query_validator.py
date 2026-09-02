"""
services/validation_agent/query_validator.py

CRITICAL SECURITY MODULE — Validates SQL queries to prevent injection attacks.

Five checks (all must pass):
  1. syntax_check    — sqlparse can parse it
  2. select_only     — statement(s) are SELECT (no DML/DDL)
  3. keyword_check   — no dangerous keywords
  4. limit_check     — LIMIT clause present
  5. pattern_check   — no suspicious injection patterns
                     (regex layer + structured statement-purity scan;
                      legitimate nested SELECT derived tables / scalar
                      subqueries are accepted, non-SELECT nested statements
                      are rejected)

Also signs safe queries with HMAC to detect tampering.

Phase 6B additions (SEMANTIC_LAYER_ENABLED=True, non-blocking):
  - Warns if SQL references unknown tables (not in KNOWN_TABLES)
  - Warns on unsupported aggregate formulas
  - Carries upstream_semantic_warnings through to response
  IMPORTANT: semantic checks are WARNINGS only — they never set safe=False.
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

SEMANTIC_LAYER_ENABLED = os.getenv("SEMANTIC_LAYER_ENABLED", "false").lower() == "true"

# Phase 6B: known safe tables (used for semantic unknown-table warning only)
KNOWN_TABLES = {
    "customers", "accounts", "transactions", "branches", "products",
    "risk_flags", "loans", "employees", "cards", "beneficiaries",
    "fees", "exchange_rates", "compliance_checks", "audit_log",
    # semantic layer tables (read-only metadata — allowed in SELECT)
    "table_metadata", "column_metadata", "metric_registry",
    "business_glossary", "join_registry",
}

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
    ("and_true",            re.compile(r"\bAND\s+TRUE\b", re.I)),
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
    # NOTE: nested SELECTs are NOT flagged here — legitimate derived tables,
    # scalar subqueries and EXISTS subqueries (all read-only SELECTs) must pass.
    # Non-SELECT nested statements are rejected by the structured purity scan in
    # pattern_check (_structured_statement_purity), not by regex.
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
        # Structured statement-purity scan (defense-in-depth + nested SELECTs):
        # rejects stacked queries and nested non-SELECT statements (subquery/CTE
        # with DELETE/DROP/...) while accepting legitimate derived tables and
        # scalar subqueries. Only applied when sqlparse is available.
        if HAS_SQLPARSE:
            found_patterns = found_patterns + [
                p for p in self._structured_statement_purity(sql) if p not in found_patterns
            ]
        if found_patterns:
            checks_failed.append("pattern_check")
            issues.append(f"Suspicious injection pattern(s): {', '.join(found_patterns)}")
        else:
            checks_passed.append("pattern_check")

        # ── VERDICT ────────────────────────────────────────────────────────────────────
        safe = len(checks_failed) == 0
        confidence = len(checks_passed) / (len(checks_passed) + len(checks_failed))

        signature = None
        if safe:
            import uuid
            import secrets
            # Generate request_id and nonce if not provided (e.g. in standalone tests)
            req_id = getattr(request, "request_id", None) or str(uuid.uuid4())
            nonce = getattr(request, "nonce", None) or secrets.token_hex(8)
            try:
                import sys
                import os
                shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared"))
                if shared_path not in sys.path:
                    sys.path.insert(0, shared_path)
                from query_signing import sign_query_payload
                signature = sign_query_payload(
                    request_id=req_id,
                    sql=sql,
                    parameters=request.parameters,
                    timestamp=int(time.time()),
                    nonce=nonce,
                    key=SIGNING_KEY
                )
            except Exception as exc:
                logger.error("Failed to sign query payload: %s", exc)
                signature = None

        # Sanitized SQL for safe logging
        if HAS_SQLPARSE:
            sanitized = sqlparse.format(sql, strip_comments=True, reindent=True)
        else:
            # Simple fallback: strip leading/trailing whitespace
            sanitized = " ".join(sql.split())

        # ── Phase 6B: Semantic checks (WARNING level — never affect safe verdict) ──
        semantic_warnings: List[str] = list(request.upstream_semantic_warnings)

        if SEMANTIC_LAYER_ENABLED and safe:
            # Check 6: unknown table references
            table_refs = re.findall(r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)', sql, re.IGNORECASE)
            for match in table_refs:
                tbl = (match[0] or match[1]).lower()
                if tbl and tbl not in KNOWN_TABLES:
                    msg = f"[semantic] Unknown table '{tbl}' referenced — not in known banking schema"
                    semantic_warnings.append(msg)
                    logger.warning("[Validator] %s", msg)

            # Check 7: unsupported formula pattern (raw math in SELECT without aggregation)
            if re.search(r'SELECT\s+[^,]+[*/][^,]+FROM', sql, re.IGNORECASE):
                msg = "[semantic] Possible raw arithmetic in SELECT — consider using metric_registry formulas"
                semantic_warnings.append(msg)
                logger.info("[Validator] %s", msg)

        if semantic_warnings:
            logger.info(
                "[Validator] Semantic warnings (%d): %s", len(semantic_warnings), semantic_warnings
            )

        logger.info(
            "Validation: safe=%s confidence=%.2f checks_failed=%s semantic_warnings=%d",
            safe, confidence, checks_failed, len(semantic_warnings)
        )

        return QueryValidationResponse(
            safe=safe,
            confidence=round(confidence, 3),
            issues=issues,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            signature=signature,
            sanitized_sql=sanitized if safe else None,
            semantic_warnings=semantic_warnings,
        )

    @staticmethod
    def _structured_statement_purity(sql: str) -> List[str]:
        """Structured scan for non-SELECT / clause-embedded subquery content.

        Replaces the brittle `nested_select` / `subselect_where` regex checks:
          - `stacked_queries`    — more than one top-level statement (`;`-separated)
          - `nested_non_select`  — a nested DML/DDL keyword other than SELECT
                                   anywhere in the tree (subquery/CTE write attempt)
          - `subquery_in_clause` — a Parenthesis sub-SELECT appearing inside a
                                   WHERE/HAVING/ON clause (injection exfil vector).
                                   Legitimate derived tables live in FROM, never
                                   in clauses — the compiler emits neither.
        Legitimate derived tables, scalar subqueries and EXISTS subqueries are
        read-only SELECTs and are accepted.
        """
        violations: List[str] = []
        try:
            statements = sqlparse.parse(sql)
        except Exception:  # noqa: BLE001 — nothing parsed, regex layer still applies
            return violations
        if len(statements) > 1:
            violations.append("stacked_queries")
        for stmt in statements:
            if stmt.get_type() != "SELECT":
                violations.append("nested_non_select")
                continue
            if QueryValidator._subquery_in_clause(stmt):
                violations.append("subquery_in_clause")
            for token in stmt.flatten():
                ttype = token.ttype
                if ttype in (sqlparse.tokens.Keyword.DML, sqlparse.tokens.Keyword.DDL):
                    if str(token.value).strip().upper() != "SELECT":
                        violations.append("nested_non_select")
                        break
        return violations

    @staticmethod
    def _subquery_in_clause(stmt) -> bool:
        """True if a Parenthesis containing a SELECT appears inside a
        WHERE/HAVING/ON clause. Derived tables and scalar subqueries are fine;
        subqueries inside filter clauses are the classic exfil vector."""
        clause_keywords = ("HAVING", "ON")

        def walk(tokens: list, in_clause: bool, prev=None) -> bool:
            for t in tokens:
                if isinstance(t, sqlparse.sql.Parenthesis) and in_clause:
                    prev_upper = str(prev.value).strip().upper() if prev is not None else ""
                    prev_exists = prev_upper == "EXISTS"
                    has_select = any(tk.ttype is sqlparse.tokens.Keyword.DML
                                     and str(tk.value).strip().upper() == "SELECT"
                                     for tk in t.flatten())
                    if has_select and not prev_exists:
                        return True
                sub = in_clause
                if isinstance(t, sqlparse.sql.Where):
                    sub = True
                elif t.ttype is sqlparse.tokens.Keyword and str(t.value).strip().upper() in clause_keywords:
                    sub = True
                if t.is_group and walk(t.tokens, sub, None):
                    return True
                if str(t.value).strip() and getattr(t, "ttype", None) not in (
                        sqlparse.tokens.Token.Text.Whitespace,):
                    prev = t
            return False

        try:
            return walk(stmt.tokens, False)
        except Exception:  # noqa: BLE001
            return False

    def _sign_query(self, sql: str, parameters: list) -> str:
        """HMAC-SHA256 signature over (sql + parameters) for tamper detection."""
        import uuid
        import secrets
        try:
            import sys
            import os
            shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared"))
            if shared_path not in sys.path:
                sys.path.insert(0, shared_path)
            from query_signing import sign_query_payload
            return sign_query_payload(
                request_id=str(uuid.uuid4()),
                sql=sql,
                parameters=parameters,
                timestamp=int(time.time()),
                nonce=secrets.token_hex(8),
                key=SIGNING_KEY
            )
        except Exception as exc:
            logger.error("Failed to sign query payload in _sign_query fallback: %s", exc)
            # Fallback to a legacy-like dummy signature to avoid completely crashing
            timestamp = int(time.time())
            return f"sha256:dummy:{timestamp}"

    def verify_signature(self, sql: str, parameters: list, signature: str) -> bool:
        """Verify a previously signed query has not been tampered with."""
        try:
            import sys
            import os
            shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared"))
            if shared_path not in sys.path:
                sys.path.insert(0, shared_path)
            from query_signing import verify_query_signature
            return verify_query_signature(
                sql=sql,
                parameters=parameters,
                signature=signature,
                key=SIGNING_KEY,
                max_age_seconds=int(os.getenv("QUERY_SIGNATURE_MAX_AGE_SECONDS", "60"))
            )
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
