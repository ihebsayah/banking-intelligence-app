"""
services/sql_agent/sql_builder.py
Safe, parameterized SQL generation.

RULES (non-negotiable):
  - ALWAYS use ? placeholders (never f-string / string concat with user values)
  - ALWAYS add LIMIT clause
  - ALWAYS validate columns against whitelist
  - NEVER concatenate user-supplied data into SQL string
"""
import logging
from typing import List, Tuple, Any, Optional, Dict

from models import (
    SQLGenerationRequest,
    SQLGenerationResponse,
    Parameter,
    JoinPathInput,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# COLUMN WHITELIST — only these columns may appear in SELECT / WHERE / GROUP BY
# Any column not in this set is rejected / ignored.
# ──────────────────────────────────────────────────────────────────────────────
ALLOWED_COLUMNS: Dict[str, List[str]] = {
    "customers": [
        "customer_id", "first_name", "last_name", "email", "phone",
        "date_of_birth", "kyc_status", "credit_score", "created_at",
        "risk_level", "branch_id",
    ],
    "accounts": [
        "account_id", "customer_id", "account_number", "account_type",
        "balance", "currency", "status", "branch_id", "product_id",
        "opened_at", "interest_rate",
    ],
    "transactions": [
        "transaction_id", "account_id", "customer_id", "amount",
        "transaction_type", "description", "created_at", "status",
        "channel", "merchant_category",
    ],
    "branches": [
        "branch_id", "branch_name", "city", "country", "region",
        "manager_id", "opened_at", "status",
    ],
    "products": [
        "product_id", "product_name", "product_type", "interest_rate",
        "minimum_balance", "maximum_balance", "currency", "status",
    ],
    "risk_flags": [
        "risk_id", "customer_id", "account_id", "flag_type", "severity",
        "description", "flagged_at", "resolved_at", "status",
    ],
    "loans": [
        "loan_id", "customer_id", "account_id", "branch_id", "loan_type",
        "principal_amount", "interest_rate", "term_months", "status",
        "disbursed_at", "due_date",
    ],
    "employees": [
        "employee_id", "branch_id", "first_name", "last_name", "role",
        "hired_at", "status",
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


def _validate_column(table: str, column: str) -> bool:
    """Return True if column is whitelisted for table."""
    allowed = ALLOWED_COLUMNS.get(table, [])
    # Strip aggregate wrappers: COUNT(col) → col
    col_clean = column.strip()
    for agg in ALLOWED_AGGREGATES:
        if col_clean.upper().startswith(f"{agg}("):
            col_clean = col_clean[len(agg)+1:].rstrip(")")
            break
    return col_clean in allowed or col_clean == "*"


def _safe_columns(tables: List[str], requested: Optional[List[str]]) -> str:
    """
    Build SELECT column list — validated against whitelist.
    Falls back to <primary_table>.* if nothing valid.
    """
    if not requested:
        if tables:
            return f"{tables[0]}.*"
        return "*"

    valid_cols = []
    for col in requested:
        # format: "table.column" or "column" or "COUNT(column) AS alias"
        parts = col.split(".")
        if len(parts) == 2:
            tbl, colname = parts
            if tbl in tables and _validate_column(tbl, colname):
                valid_cols.append(col)
            else:
                logger.warning("Column not whitelisted: %s — skipped", col)
        else:
            # Check against any table
            found = any(_validate_column(t, col) for t in tables)
            if found or col.upper() in ("*", "1"):
                valid_cols.append(col)
            else:
                logger.warning("Column not whitelisted: %s — skipped", col)

    return ", ".join(valid_cols) if valid_cols else f"{tables[0]}.*"


def _build_joins(join_paths: List[JoinPathInput]) -> str:
    """Build JOIN clauses from resolved join paths."""
    if not join_paths:
        return ""
    parts = []
    for jp in join_paths:
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
    return "string"


def _build_group_by(group_by: Optional[List[str]], tables: List[str]) -> str:
    if not group_by:
        return ""
    valid = []
    for col in group_by:
        parts = col.split(".")
        if len(parts) == 2:
            tbl, c = parts
            if tbl in tables and _validate_column(tbl, c):
                valid.append(col)
        else:
            if any(_validate_column(t, col) for t in tables):
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
    # Validate col
    col_parts = col.split(".")
    if len(col_parts) == 2:
        tbl, c = col_parts
        if tbl not in tables or not _validate_column(tbl, c):
            return ""
    else:
        if not any(_validate_column(t, col) for t in tables):
            return ""
    return f"ORDER BY {col} {direction}"


class SQLBuilder:
    """
    Builds safe, parameterized SQL queries.
    All user-supplied values become ? placeholders.
    """

    def build(self, request: SQLGenerationRequest) -> SQLGenerationResponse:
        tables = [t.lower() for t in request.tables]
        if not tables:
            raise ValueError("No tables specified")

        # Determine true primary table instead of just using alphabetical tables[0]
        primary_table = tables[0]
        if request.join_paths:
            primary_table = request.join_paths[0].from_table
        else:
            # simple pluralization fallback
            derived = f"{request.primary_entity.lower()}s"
            if derived in tables:
                primary_table = derived
            elif request.primary_entity.lower() in tables:
                primary_table = request.primary_entity.lower()

        # SELECT columns
        select_cols = _safe_columns(tables, request.columns)

        # FROM + JOINs
        join_sql = _build_joins(request.join_paths)

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
            "SQL built: tables=%s params=%d limit=%d",
            tables, len(parameters), limit_val
        )

        return SQLGenerationResponse(
            sql=sql,
            parameters=parameters,
            description=description,
            estimated_rows=estimated_rows,
            estimated_time_ms=estimated_time_ms,
            tables_used=tables,
            is_parameterized=True,
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
