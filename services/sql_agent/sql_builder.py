import re
"""
services/sql_agent/sql_builder.py
Safe, parameterized SQL generation.

RULES (non-negotiable):
  - ALWAYS use ? placeholders (never f-string / string concat with user values)
  - ALWAYS add LIMIT clause
  - ALWAYS validate columns against whitelist
  - NEVER concatenate user-supplied data into SQL string

Phase 6B additions (SEMANTIC_LAYER_ENABLED=True only):
  - Inject metric_registry SQL formulas into SELECT (e.g. total_deposits formula)
  - Validate join conditions against join_registry safe-join set
  - Return structured error if a requested join has no safe registry path
  - All metadata loaded once at startup (in-memory cache, no per-request DB hits)
"""
import logging
import os
from typing import List, Tuple, Any, Optional, Dict, Set

try:
    from sql_agent.models import (
        SQLGenerationRequest,
        SQLGenerationResponse,
        Parameter,
        JoinPathInput,
    )
except ImportError:
    from models import (
        SQLGenerationRequest,
        SQLGenerationResponse,
        Parameter,
        JoinPathInput,
    )

logger = logging.getLogger(__name__)

SEMANTIC_LAYER_ENABLED = os.getenv("SEMANTIC_LAYER_ENABLED", "false").lower() == "true"

# ──────────────────────────────────────────────────────────────────────────────
# COLUMN WHITELIST — only these columns may appear in SELECT / WHERE / GROUP BY
# Expanded in Phase 6B to cover all Tunisian banking tables.
# Any column not in this set is rejected / ignored.
# ──────────────────────────────────────────────────────────────────────────────
ALLOWED_COLUMNS: Dict[str, List[str]] = {
    "customers": [
        "customer_id", "name", "email", "phone",
        "kyc_verified", "risk_score", "segment", "created_at", "updated_at",
    ],
    "accounts": [
        "account_id", "customer_id", "account_type",
        "balance", "available_balance", "currency", "status", "branch_id",
        "created_at",
    ],
    "transactions": [
        "transaction_id", "account_id", "customer_id", "amount",
        "transaction_type", "status", "description", "transaction_date",
        "created_at",
    ],
    "branches": [
        "branch_id", "name", "state", "city", "manager_id", "created_at",
        "region_id",
    ],
    "products": [
        "product_id", "name", "category", "description", "created_at",
    ],
    "risk_flags": [
        "id", "customer_id", "flag_type", "severity",
        "description", "resolved", "created_at",
        "account_id", "transaction_id", "resolved_at", "resolved_by",
        "risk_category", "source",
    ],
    "loan_contracts": [
        "loan_id", "customer_id", "account_id", "branch_id",
        "loan_product_id", "loan_type", "principal_amount", "currency",
        "interest_rate", "term_months", "installment_amount",
        "disbursement_date", "maturity_date", "status",
        "outstanding_balance", "days_past_due", "created_at", "updated_at",
    ],
    "non_performing_loans": [
        "npl_id", "loan_id", "npl_amount", "npl_date",
        "classification", "recovery_status", "created_at",
    ],
    "provisions": [
        "provision_id", "loan_id", "provision_date", "provision_amount",
        "calculation_model", "created_at",
    ],
    "employees": [
        "employee_id", "branch_id", "department_id", "first_name", "last_name",
        "title", "role", "hire_date", "is_active", "email",
        "supervisor_id", "created_at",
    ],
    "fee_income": [
        "fee_income_id", "customer_id", "account_id", "fee_type",
        "amount", "value_date", "created_at",
    ],
    "interest_income": [
        "interest_id", "loan_id", "customer_id", "amount", "period",
    ],
    "kyc_cases": [
        "kyc_case_id", "customer_id", "case_type", "status",
        "risk_level", "assigned_to", "opened_at", "closed_at",
        "due_date", "notes", "created_at",
    ],
    "aml_alerts": [
        "alert_id", "customer_id", "transaction_id", "severity", "status",
        "created_at",
    ],
    "compliance_violations": [
        "id", "query_id", "user_id", "violation_type", "severity",
        "description", "regulation", "detected_at", "status",
        "resolution_notes",
    ],
    "suspicious_activity_reports": [
        "sar_id", "alert_id", "customer_id", "report_date", "status",
        "ctaf_reference", "description", "created_at",
    ],
    "cards": [
        "card_id", "account_id", "customer_id", "card_type",
        "card_number_masked", "expiry_date", "status",
        "daily_limit", "monthly_limit", "issued_date", "created_at",
    ],
    "beneficiaries": [
        "beneficiary_id", "customer_id", "beneficiary_name",
        "bank_name", "account_number", "iban", "currency",
        "country", "is_active", "created_at",
    ],
    "audit_findings": [
        "finding_id", "title", "description", "source", "severity",
        "status", "target_resolution_date", "resolved_date", "created_at",
    ],
    "user_activity_log": [
        "id", "user_id", "action", "table_name", "record_id",
        "old_values", "new_values", "ip_address", "created_at",
    ],
    "compliance_cases": [
        "id", "user_id", "status", "description", "created_at",
    ],
    "regulatory_reports": [
        "id", "report_type", "status", "created_at",
    ],
}

# Allowed aggregate functions
ALLOWED_AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}

# Allowed ORDER BY directions
ALLOWED_ORDER_DIRS = {"ASC", "DESC"}

# Filter operators whitelist
ALLOWED_OPERATORS = {">", "<", ">=", "<=", "=", "!=", "LIKE", "IN", "BETWEEN"}

MAX_LIMIT = 10_000
DEFAULT_LIMIT = 100

# ──────────────────────────────────────────────────────────────────────────────
# Semantic layer in-memory caches
# ──────────────────────────────────────────────────────────────────────────────
_metric_cache: Dict[str, dict] = {}      # metric_name → {sql_formula, unit, description}
_safe_joins: Set[Tuple[str, str]] = set()  # {(from_table, to_table)} from join_registry
_semantic_cache_ready: bool = False

SENSITIVE_LOG_TABLES = {
    "audit_log", "user_activity_log", "compliance_events", "compliance_rules",
    "compliance_violations", "compliance_cases", "compliance_reviews", "regulatory_reports"
}


def initialize_sql_semantic_cache(db_conn) -> None:
    """
    Load metric_registry formulas + join_registry safe pairs into memory.
    Called once at startup when SEMANTIC_LAYER_ENABLED=True.
    Idempotent — safe to call multiple times.
    Cache ready=True ONLY if both metrics AND joins are non-empty.
    """
    global _metric_cache, _safe_joins, _semantic_cache_ready
    if _semantic_cache_ready:
        return
    try:
        with db_conn.cursor() as cur:
            # metric_registry — actual columns: metric_id, formula, unit, description
            # ponytail: no is_active col in schema — load all rows
            cur.execute(
                "SELECT metric_id, formula, unit, description FROM metric_registry"
            )
            metrics: Dict[str, dict] = {}
            for row in cur.fetchall():
                if row[0] and row[1]:  # skip rows with null metric_id or null formula
                    metrics[row[0].lower()] = {
                        "sql_formula": row[1],
                        "unit": row[2],
                        "description": row[3],
                    }
            _metric_cache = metrics

            # join_registry safe pairs
            cur.execute("SELECT * FROM join_registry")
            colnames = [desc[0].lower() for desc in cur.description]

            src_idx = colnames.index("source_table")
            tgt_idx = colnames.index("target_table")
            conf_idx = colnames.index("confidence") if "confidence" in colnames else -1
            bidir_idx = colnames.index("is_bidirectional") if "is_bidirectional" in colnames else -1

            safe: Set[Tuple[str, str]] = set()
            for row in cur.fetchall():
                from_t = row[src_idx].lower()
                to_t = row[tgt_idx].lower()

                # Skip low-confidence joins
                if conf_idx != -1 and row[conf_idx] is not None:
                    if float(row[conf_idx]) < 0.8:
                        continue

                is_bidirectional = True
                if bidir_idx != -1 and row[bidir_idx] is not None:
                    is_bidirectional = bool(row[bidir_idx])

                # Exclude sensitive log/compliance tables from auto-reversal
                if from_t in SENSITIVE_LOG_TABLES or to_t in SENSITIVE_LOG_TABLES:
                    is_bidirectional = False

                safe.add((from_t, to_t))
                if is_bidirectional:
                    safe.add((to_t, from_t))
            _safe_joins = safe

        # Cache ready ONLY if minimum metadata present — prevents silent empty-cache mode
        if not _metric_cache:
            logger.warning(
                "[SQLBuilder] metric_registry is empty — semantic cache NOT ready; falling back to legacy"
            )
            _semantic_cache_ready = False
            return
        if not _safe_joins:
            logger.warning(
                "[SQLBuilder] join_registry has no safe pairs — semantic cache NOT ready; falling back to legacy"
            )
            _semantic_cache_ready = False
            return

        _semantic_cache_ready = True
        logger.info(
            "[SQLBuilder] Semantic cache ready: %d metrics, %d safe join pairs",
            len(_metric_cache), len(_safe_joins)
        )
    except Exception as exc:
        logger.warning("[SQLBuilder] Semantic cache init failed — using legacy builder: %s", exc)
        _semantic_cache_ready = False


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_table_and_column(col_expr: str) -> Tuple[Optional[str], str]:
    """
    Extracts table name and raw column name from an expression.
    Examples:
      "accounts.balance" -> ("accounts", "balance")
      "AVG(accounts.balance)" -> ("accounts", "balance")
      "SUM(accounts.balance) AS balance" -> ("accounts", "balance")
      "customer_id" -> (None, "customer_id")
      "COUNT(customer_id)" -> (None, "customer_id")
    """
    expr = col_expr.strip()

    # Strip AS alias
    alias_match = re.search(r'\s+AS\s+\w+', expr, re.IGNORECASE)
    if alias_match:
        expr = expr[:alias_match.start()].strip()

    # Strip aggregate function: e.g. AVG(...)
    for agg in ALLOWED_AGGREGATES:
        if expr.upper().startswith(f"{agg}("):
            expr = expr[len(agg)+1:].rstrip(")").strip()
            break

    # Now check for table prefix
    parts = expr.split(".")
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, expr


def _validate_column(table: str, column: str) -> bool:
    """Return True if column is whitelisted for table."""
    return column in ALLOWED_COLUMNS.get(table, []) or column == "*"


def _safe_columns(tables: List[str], requested: Optional[List[str]], primary_table: Optional[str] = None) -> str:
    """
    Build SELECT column list — validated against whitelist.
    Falls back to <primary_table>.* if nothing valid.
    """
    fallback_table = primary_table or (tables[0] if tables else None)
    if not requested:
        if fallback_table:
            return f"{fallback_table}.*"
        return "*"

    valid_cols = []
    for col in requested:
        tbl, colname = _extract_table_and_column(col)
        if tbl:
            if tbl in tables and _validate_column(tbl, colname):
                valid_cols.append(col)
            else:
                logger.warning("Column not whitelisted: %s (table %s, col %s) — skipped", col, tbl, colname)
        else:
            found = any(_validate_column(t, colname) for t in tables)
            if found or colname.upper() in ("*", "1"):
                valid_cols.append(col)
            else:
                logger.warning("Column not whitelisted: %s (col %s) — skipped", col, colname)

    return ", ".join(valid_cols) if valid_cols else f"{fallback_table}.*"


def _validate_joins_against_registry(join_paths: List[JoinPathInput]) -> Tuple[List[JoinPathInput], List[str]]:
    """
    Phase 6B: Validate each join against the safe join pairs from join_registry.
    Returns (safe_joins, warning_messages).
    NEVER invents a join — if not in registry and SEMANTIC_LAYER_ENABLED, it is skipped with a warning.
    """
    if not SEMANTIC_LAYER_ENABLED or not _semantic_cache_ready:
        return join_paths, []  # pass-through in legacy mode

    safe: List[JoinPathInput] = []
    warnings: List[str] = []
    for jp in join_paths:
        pair = (jp.from_table.lower(), jp.to_table.lower())
        if pair in _safe_joins:
            safe.append(jp)
        else:
            msg = (
                f"Join '{jp.from_table}' → '{jp.to_table}' not found in join_registry "
                f"(is_safe=TRUE) — skipped to prevent unsafe join"
            )
            warnings.append(msg)
            logger.warning("[SQLBuilder] %s", msg)

    return safe, warnings


def _sanitize_metric_formula(formula: str) -> Tuple[bool, str]:
    """
    Validates a metric_registry SQL formula.
    Allows only whitelisted aggregate/logical functions, table.column identifiers,
    basic arithmetic, numbers, and basic comparison operators.
    Rejects dangerous SQL commands, semicolons, comments, etc.
    """
    if not formula:
        return False, "Formula is empty"
        
    # 1. Quick blocklist checks
    formula_lower = formula.lower()
    for block in [";", "--", "/*", "*/"]:
        if block in formula:
            return False, f"Contains forbidden sequence '{block}'"
            
    # Standalone blocklist keywords
    blocked_words = {"drop", "delete", "insert", "update", "union", "create", "alter", "truncate", "grant", "revoke"}
    # Tokenize by word boundaries to find exact keyword matches
    words = re.findall(r'\b[a-z_]+\b', formula_lower)
    for w in words:
        if w in blocked_words:
            return False, f"Contains forbidden keyword '{w}'"

    # 2. Tokenizer check: check every token against a strict whitelist
    # Token regex extracts:
    # - float/int numbers: \d+(?:\.\d+)?
    # - single-quoted strings: '[^']*'
    # - word tokens: [a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?
    # - operators and punctuation: <=|>=|!=|<>|[-+*/().,=<>]
    token_pattern = re.compile(
        r"(\d+(?:\.\d+)?|'[^']*'|[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?|<=|>=|!=|<>|[-+*/().,=<>]|\s+)"
    )
    
    tokens = token_pattern.findall(formula)
    reconstructed = "".join(tokens)
    if reconstructed.strip() != formula.strip():
        return False, "Contains invalid/unparsed characters"

    allowed_funcs = {"sum", "avg", "count", "min", "max", "round", "coalesce", "case", "when", "then", "else", "end", "abs", "now", "in"}
    safe_keywords = {"as", "and", "or", "not", "is", "null", "true", "false", "like", "distinct", "where", "filter", "interval"}
    
    non_empty_tokens = [t.strip() for t in tokens if t.strip()]
    for i, token_strip in enumerate(non_empty_tokens):
        # Is it a number?
        if re.match(r'^\d+(?:\.\d+)?$', token_strip):
            continue
        # Is it a string literal?
        if token_strip.startswith("'") and token_strip.endswith("'"):
            continue
        # Is it an operator or punctuation?
        if token_strip in {"+", "-", "*", "/", "(", ")", ".", ",", "=", "<", ">", "<=", ">=", "!=", "<>"}:
            continue
        # Is it a word token?
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?$', token_strip):
            parts = token_strip.lower().split('.')
            if len(parts) == 1:
                word = parts[0]
                if word in allowed_funcs or word in safe_keywords:
                    continue
                # If this word is followed by an opening parenthesis, it is a function call
                if i + 1 < len(non_empty_tokens) and non_empty_tokens[i+1] == "(":
                    return False, f"Disallowed function call '{token_strip}'"
                # Otherwise assume it's a column name (e.g. risk_score)
                continue
            elif len(parts) == 2:
                # table.column
                continue
            else:
                return False, f"Malformed identifier '{token_strip}'"
        
        return False, f"Disallowed token/operator '{token_strip}'"

    return True, ""


def _inject_metric_formulas(
    columns: Optional[List[str]],
    detected_kpis: Optional[List[str]],
    tables: List[str],
) -> Tuple[Optional[List[str]], List[str]]:
    """
    Phase 6B: Replace KPI references in columns with metric_registry SQL formulas.
    Returns (updated_columns, trace_notes).
    """
    if not SEMANTIC_LAYER_ENABLED or not _semantic_cache_ready or not detected_kpis:
        return columns, []

    updated = list(columns) if columns else []
    notes: List[str] = []

    for kpi in detected_kpis:
        kpi_lower = kpi.lower()
        if kpi_lower in _metric_cache:
            formula_info = _metric_cache[kpi_lower]
            formula = formula_info["sql_formula"]  # key set in initialize_sql_semantic_cache

            # Sanitize formula before injection
            is_safe, reason = _sanitize_metric_formula(formula)
            if not is_safe:
                msg = f"KPI '{kpi}' formula is unsafe and was rejected: {reason}"
                logger.warning("[SQLBuilder] %s", msg)
                notes.append(msg)
                continue

            alias = kpi_lower.replace(" ", "_")
            col_entry = f"{formula} AS {alias}"
            # Avoid duplicates
            if col_entry not in updated:
                updated.append(col_entry)
                notes.append(f"KPI '{kpi}' resolved via metric_registry: {formula}")
                logger.info("[SQLBuilder] Injected metric formula for '%s': %s", kpi, formula)
        else:
            notes.append(f"KPI '{kpi}' not found in metric_registry — ignored")

    return updated if updated else columns, notes


def _build_joins(join_paths: List[JoinPathInput]) -> str:
    """Build JOIN clauses from resolved join paths. Deduplicates identical joins."""
    if not join_paths:
        return ""
    parts = []
    seen: Set[str] = set()
    for jp in join_paths:
        dedup_key = f"{jp.from_table.lower()}|{jp.to_table.lower()}|{jp.condition.lower()}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        join_type = jp.join_type if jp.join_type in (
            "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "LEFT OUTER JOIN"
        ) else "INNER JOIN"
        parts.append(f"{join_type} {jp.to_table} ON {jp.condition}")
    return "\n    ".join(parts)


def _build_where(
    filters: Optional[Dict[str, Any]],
    tables: List[str],
) -> Tuple[str, List[Tuple[str, Any, str]]]:
    """
    Build parameterized WHERE clause.
    Returns (where_clause_str, [(param_name, value, type), ...])
    NEVER concatenates user values into SQL string — always uses ?
    """
    if not filters:
        return "", []

    clauses = []
    params: List[Tuple[str, Any, str]] = []

    for column, condition in filters.items():
        # Validate column
        col_parts = column.split(".")
        if len(col_parts) == 2:
            tbl, col = col_parts
            if tbl not in tables or not _validate_column(tbl, col):
                logger.warning("Filter column not whitelisted: %s — skipped", column)
                continue
        else:
            allowed_for_col = any(_validate_column(t, column) for t in tables)
            if not allowed_for_col:
                logger.warning("Filter column not whitelisted: %s — skipped", column)
                continue

        if isinstance(condition, dict):
            for op, val in condition.items():
                op_upper = op.upper().strip()
                if op_upper not in ALLOWED_OPERATORS:
                    logger.warning("Operator not allowed: %s — skipped", op)
                    continue

                if op_upper == "BETWEEN" and isinstance(val, (list, tuple)) and len(val) == 2:
                    # BETWEEN uses TWO placeholders
                    param_name_lo = f"{column.replace('.','_')}_lo"
                    param_name_hi = f"{column.replace('.','_')}_hi"
                    clauses.append(f"{column} BETWEEN ? AND ?")
                    params.append((param_name_lo, val[0], _infer_type(val[0])))
                    params.append((param_name_hi, val[1], _infer_type(val[1])))
                elif op_upper == "IN" and isinstance(val, (list, tuple)):
                    placeholders = ", ".join(["?" for _ in val])
                    clauses.append(f"{column} IN ({placeholders})")
                    for idx, v in enumerate(val):
                        params.append((f"{column.replace('.','_')}_{idx}", v, _infer_type(v)))
                else:
                    param_name = column.replace(".", "_")
                    clauses.append(f"{column} {op_upper} ?")
                    params.append((param_name, val, _infer_type(val)))
        else:
            # Simple equality
            param_name = column.replace(".", "_")
            clauses.append(f"{column} = ?")
            params.append((param_name, condition, _infer_type(condition)))

    if not clauses:
        return "", []

    return "WHERE " + " AND ".join(clauses), params


def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return "date"
    return "string"


def _build_group_by(group_by: Optional[List[str]], tables: List[str]) -> str:
    if not group_by:
        return ""
    valid = []
    for col in group_by:
        tbl, colname = _extract_table_and_column(col)
        if tbl:
            if tbl in tables and _validate_column(tbl, colname):
                valid.append(col)
        else:
            if any(_validate_column(t, colname) for t in tables):
                valid.append(col)
    return f"GROUP BY {', '.join(valid)}" if valid else ""


def _build_order_by(order_by: Optional[str], tables: List[str]) -> str:
    if not order_by:
        return ""
    parts = order_by.strip().split()
    col = parts[0]
    direction = parts[1].upper() if len(parts) > 1 else "ASC"
    if direction not in ALLOWED_ORDER_DIRS:
        direction = "ASC"

    tbl, colname = _extract_table_and_column(col)
    if tbl:
        if tbl not in tables or not _validate_column(tbl, colname):
            return ""
    else:
        if not any(_validate_column(t, colname) for t in tables):
            return ""
    return f"ORDER BY {col} {direction}"


class SQLBuilder:
    """
    Builds safe, parameterized SQL queries.
    All user-supplied values become ? placeholders.

    Phase 6B additions (when SEMANTIC_LAYER_ENABLED=True):
      - Injects metric_registry SQL formulas for detected KPIs
      - Validates join paths against join_registry safe pairs
      - Attaches semantic_warnings and semantic_trace to response metadata
    """

    def build(self, request: SQLGenerationRequest) -> SQLGenerationResponse:
        tables = [t.lower() for t in request.tables]
        if not tables:
            raise ValueError("No tables specified")

        semantic_warnings: List[str] = []
        semantic_trace: List[str] = []

        # Determine true primary table instead of just using alphabetical tables[0]
        primary_table = tables[0]
        if request.join_paths:
            primary_table = request.join_paths[0].from_table
        else:
            derived = f"{request.primary_entity.lower()}s"
            if derived in tables:
                primary_table = derived
            elif request.primary_entity.lower() in tables:
                primary_table = request.primary_entity.lower()

        # Phase 6B: Validate join paths against join_registry (non-blocking)
        validated_joins = request.join_paths
        if SEMANTIC_LAYER_ENABLED and _semantic_cache_ready and request.join_paths:
            validated_joins, join_warnings = _validate_joins_against_registry(request.join_paths)
            semantic_warnings.extend(join_warnings)
            if join_warnings:
                semantic_trace.append(f"join_validation: {len(join_warnings)} join(s) skipped (not in registry)")

        # Phase 6B: Inject metric_registry formulas for detected KPIs
        columns = request.columns
        detected_kpis = getattr(request, "detected_kpis", None)
        if SEMANTIC_LAYER_ENABLED and _semantic_cache_ready and detected_kpis:
            columns, metric_notes = _inject_metric_formulas(columns, detected_kpis, tables)
            semantic_trace.extend(metric_notes)

        # SELECT columns
        select_cols = _safe_columns(tables, columns, primary_table)

        # FROM + JOINs
        join_sql = _build_joins(validated_joins)

        # WHERE (parameterized)
        where_sql, raw_params = _build_where(request.filters, tables)

        # GROUP BY
        group_sql = _build_group_by(request.group_by, tables)

        # ORDER BY
        order_sql = _build_order_by(request.order_by, tables)

        # LIMIT (always enforced)
        limit_val = min(int(request.limit or DEFAULT_LIMIT), MAX_LIMIT)
        # LIMIT is a constant in SQL — safe to inline (not user-controlled value)
        limit_sql = f"LIMIT {limit_val}"

        # Assemble SQL
        parts = [f"SELECT {select_cols}", f"FROM {primary_table}"]
        if join_sql:
            parts.append(f"    {join_sql}")
        if where_sql:
            parts.append(where_sql)
        if group_sql:
            parts.append(group_sql)
        if order_sql:
            parts.append(order_sql)
        parts.append(limit_sql)

        sql = "\n".join(parts)

        # Build Parameter objects
        parameters = [
            Parameter(name=name, value=val, type=ptype)
            for name, val, ptype in raw_params
        ]

        # Build description
        description = self._describe(request, tables, len(parameters))

        # Rough estimates
        estimated_rows = limit_val
        estimated_time_ms = 50 + len(tables) * 20 + len(parameters) * 5

        logger.info(
            "SQL built: tables=%s params=%d limit=%d semantic=%s",
            tables, len(parameters), limit_val, SEMANTIC_LAYER_ENABLED
        )

        if semantic_warnings:
            logger.warning("[SQLBuilder] Semantic warnings: %s", semantic_warnings)
        if semantic_trace:
            logger.info("[SQLBuilder] Semantic trace: %s", semantic_trace)

        return SQLGenerationResponse(
            sql=sql,
            parameters=parameters,
            description=description,
            estimated_rows=estimated_rows,
            estimated_time_ms=estimated_time_ms,
            tables_used=tables,
            is_parameterized=True,
            semantic_warnings=semantic_warnings,
            semantic_trace=semantic_trace,
        )

    def _describe(self, req: SQLGenerationRequest, tables: List[str], param_count: int) -> str:
        action = {
            "retrieve": "Retrieve",
            "aggregate": "Aggregate",
            "filter": "Filter",
            "count": "Count",
            "sum": "Sum",
            "average": "Average",
        }.get(req.intent.lower(), "Query")
        entity = req.primary_entity
        tbl_str = " + ".join(tables)
        desc = f"{action} {entity} data from {tbl_str}"
        if param_count:
            desc += f" with {param_count} filter(s)"
        if req.group_by:
            desc += f" grouped by {', '.join(req.group_by)}"
        return desc
