"""
services/sql_agent/deterministic_compiler.py
Renders a QueryPlan into parameterized PostgreSQL SQL.

Increment 2.5: Pure SQL renderer. All analytical decisions (aggregation,
GROUP BY, ordering) are made by the QueryPlanBuilder. This compiler reads
already-resolved expressions and emits SQL.

Increment 3.1: Materializes independent_subqueries strategy — metrics with
execution_strategy="independent_subqueries" are compiled as separate
aggregated subqueries joined at the end, eliminating fan-out risk.

Rules:
  - Renderer ONLY: does not infer metrics, select tables, or alter intent.
  - Only uses: selected tables, bridge tables, registered joins, approved
    metric formulas, analytical expressions, validated columns.
  - SELECT * is forbidden (COUNT(*) is allowed).
  - Every user filter value is bound via $N placeholders.
  - Same QueryPlan always produces identical SQL, parameters, and aliases.
  - asyncpg convention: $1, $2, ... (verified in query_executor.py)
"""
import re
import logging
from typing import List

from sql_agent.plan_models import (
    QueryPlan, CompiledQuery, BoundParameter, ColumnRef,
    MetricReference, FilterSpec, TimeRangeSpec,
    AggregateExpression, RatioExpression, CaseExpression,
)

logger = logging.getLogger(__name__)

# ─── Time range → PostgreSQL interval mapping ────────────────────────────────

_TIME_INTERVALS = {
    "last_30_days": "30 days",
    "last_90_days": "90 days",
    "last_year": "1 year",
    "last_quarter": "3 months",
    "last_month": "1 month",
    "ytd": "365 days",
}

# Date column candidates per table
_DATE_COLUMNS = {
    "customers": "created_at",
    "accounts": "created_at",
    "transactions": "transaction_date",
    "branches": "created_at",
    "loan_contracts": "created_at",
    "non_performing_loans": "created_at",
    "kyc_cases": "created_at",
    "aml_alerts": "created_at",
    "risk_flags": "created_at",
    "income_statement_snapshots": "period",
    "balance_sheet_snapshots": "period",
}

# ─── Increment 3.1: Independent subquery registry ───────────────────────────
# Maps metric_id → (numerator_sql, denominator_sql) templates.
# Used when execution_strategy="independent_subqueries" to eliminate fan-out.
_INDEPENDENT_SUBQUERY_REGISTRY = {
    "loan_to_deposit": {
        "numerator": "SELECT COALESCE(SUM(lc.principal_amount), 0) AS num FROM loan_contracts lc WHERE lc.currency = 'TND'",
        "denominator": "SELECT COALESCE(SUM(a.balance), 0) AS den FROM accounts a WHERE a.currency = 'TND'",
        "ratio_expr": "ROUND(100.0 * _num.num::numeric / NULLIF(_den.den::numeric, 0), 2)",
    },
    "npl_ratio": {
        "numerator": "SELECT COUNT(DISTINCT n.loan_id) AS num FROM non_performing_loans n",
        "denominator": "SELECT COUNT(DISTINCT lc.loan_id) AS den FROM loan_contracts lc",
        "ratio_expr": "ROUND(100.0 * _num.num::numeric / NULLIF(_den.den::numeric, 0), 2)",
    },
}


class DeterministicSQLCompiler:
    """
    Compiles a QueryPlan into a CompiledQuery containing parameterized SQL
    ready for asyncpg execution.

    Pure renderer: all analytical decisions are in the QueryPlanBuilder.
    """

    def compile(self, plan: QueryPlan) -> CompiledQuery:
        if plan.unsupported_reason:
            raise ValueError(f"Cannot compile unsupported plan: {plan.unsupported_reason}")

        params: List[BoundParameter] = []
        param_counter = [0]

        def next_param(value: object) -> str:
            param_counter[0] += 1
            pos = param_counter[0]
            ptype = _infer_type(value)
            params.append(BoundParameter(position=pos, value=value, type=ptype))
            return f"${pos}"

        # ── Increment 3.1: Check for independent subqueries ────────────
        independent_metric = self._find_independent_metric(plan)
        if independent_metric:
            return self._compile_independent_subqueries(plan, independent_metric, params, next_param)

        # ── Standard single-query compilation ──────────────────────────
        # ── SELECT ────────────────────────────────────────────────────────
        select_parts = self._compile_select(plan)
        select_clause = f"SELECT {', '.join(select_parts)}"

        # ── FROM ──────────────────────────────────────────────────────────
        primary = plan.selected_tables[0] if plan.selected_tables else ""
        from_clause = f"FROM {primary}"

        # ── JOIN ──────────────────────────────────────────────────────────
        join_clause = self._compile_joins(plan.joins)

        # ── WHERE ─────────────────────────────────────────────────────────
        where_parts = self._compile_where(plan, next_param)
        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        # ── GROUP BY (dimensions present = group by them) ─────────────────
        group_clause = self._compile_group_by(plan)

        # ── ORDER BY ──────────────────────────────────────────────────────
        order_clause = self._compile_order_by(plan)

        # ── LIMIT ─────────────────────────────────────────────────────────
        limit_clause = f"LIMIT {plan.limit}"

        # ── Assemble ──────────────────────────────────────────────────────
        parts = [select_clause, from_clause]
        if join_clause:
            parts.append(join_clause)
        if where_clause:
            parts.append(where_clause)
        if group_clause:
            parts.append(group_clause)
        if order_clause:
            parts.append(order_clause)
        parts.append(limit_clause)

        sql = "\n".join(parts)

        # ── Column aliases ────────────────────────────────────────────────
        aliases = {}
        for col in plan.requested_columns:
            aliases[col.name] = col.qualified
        for m in plan.metrics:
            aliases[m.alias] = m.formula
        for expr in plan.analytical_expressions:
            if hasattr(expr, "alias"):
                aliases[expr.alias] = expr.to_sql()

        # ── Description ───────────────────────────────────────────────────
        description = self._describe(plan)

        return CompiledQuery(
            sql=sql,
            parameters=params,
            tables_used=plan.selected_tables + plan.bridge_tables,
            column_aliases=aliases,
            schema_snapshot_id=plan.schema_snapshot_id,
            semantic_metadata_version=plan.semantic_metadata_version,
            description=description,
        )

    # ── SELECT compilation ────────────────────────────────────────────────

    def _compile_select(self, plan: QueryPlan) -> List[str]:
        parts: List[str] = []

        # Registered metric formulas
        for m in plan.metrics:
            parts.append(f"{m.formula} AS {m.alias}")

        # Implicit analytical expressions (typed)
        for expr in plan.analytical_expressions:
            sql_expr = expr.to_sql()
            alias = expr.alias if hasattr(expr, "alias") else ""
            if alias:
                parts.append(f"{sql_expr} AS {alias}")
            else:
                parts.append(sql_expr)

        # Plain requested columns — skip when aggregate present
        # ponytail: one guard prevents GROUP BY errors for all aggregate queries
        has_aggregates = bool(plan.metrics or plan.analytical_expressions)
        if not has_aggregates:
            for col in plan.requested_columns:
                parts.append(f"{col.table}.{col.name}")
        elif plan.dimensions:
            dim_set = {(d.table, d.name) for d in plan.dimensions}
            for col in plan.requested_columns:
                if (col.table, col.name) in dim_set:
                    parts.append(f"{col.table}.{col.name}")
            for d in plan.dimensions:
                if (d.table, d.name) not in {(c.table, c.name) for c in plan.requested_columns}:
                    parts.append(f"{d.table}.{d.name}")

        # Fallback: if nothing selected, add primary key
        if not parts and plan.selected_tables:
            pk = f"{plan.selected_tables[0].rstrip('s')}_id"
            parts.append(f"{plan.selected_tables[0]}.{pk}")

        return parts

    # ── JOIN compilation ──────────────────────────────────────────────────

    def _compile_joins(self, joins) -> str:
        if not joins:
            return ""
        lines = []
        for j in joins:
            lines.append(f"{j.join_type} {j.to_table} ON {j.condition}")
        return "\n    ".join(lines)

    # ── WHERE compilation ─────────────────────────────────────────────────

    def _compile_where(
        self, plan: QueryPlan, next_param,
    ) -> List[str]:
        parts: List[str] = []

        for f in plan.filters:
            ph = next_param(f.value)
            if f.operator.upper() == "IN" and isinstance(f.value, (list, tuple)):
                placeholders = ", ".join(next_param(v) for v in f.value)
                parts.append(f"{f.column} IN ({placeholders})")
            elif f.operator.upper() == "BETWEEN" and isinstance(f.value, (list, tuple)) and len(f.value) == 2:
                ph_lo = next_param(f.value[0])
                ph_hi = next_param(f.value[1])
                parts.append(f"{f.column} BETWEEN {ph_lo} AND {ph_hi}")
            else:
                parts.append(f"{f.column} {f.operator} {ph}")

        if plan.time_range.type == "relative" and plan.time_range.value:
            interval = _TIME_INTERVALS.get(plan.time_range.value)
            if interval:
                date_col = self._resolve_date_column(plan)
                if date_col:
                    parts.append(f"{date_col} >= CURRENT_DATE - INTERVAL '{interval}'")

        return parts

    def _resolve_date_column(self, plan: QueryPlan) -> str:
        for t in plan.selected_tables:
            dc = _DATE_COLUMNS.get(t)
            if dc:
                return f"{t}.{dc}"
        return ""

    # ── GROUP BY compilation ──────────────────────────────────────────────

    def _compile_group_by(self, plan: QueryPlan) -> str:
        """Pure renderer: GROUP BY when dimensions are present."""
        if not plan.dimensions:
            return ""
        dim_exprs = [f"{d.table}.{d.name}" for d in plan.dimensions]
        return f"GROUP BY {', '.join(dim_exprs)}"

    # ── ORDER BY compilation ──────────────────────────────────────────────

    def _compile_order_by(self, plan: QueryPlan) -> str:
        if not plan.sort:
            return ""
        return f"ORDER BY {plan.sort.column} {plan.sort.direction}"

    # ── Increment 3.1: Independent subqueries ────────────────────────────

    def _find_independent_metric(self, plan: QueryPlan) -> str:
        """Find the first metric with independent_subqueries strategy."""
        for m in plan.metrics:
            if m.execution_strategy and m.execution_strategy.execution_strategy == "independent_subqueries":
                if m.metric_id in _INDEPENDENT_SUBQUERY_REGISTRY:
                    return m.metric_id
        return ""

    def _compile_independent_subqueries(
        self, plan: QueryPlan, metric_id: str, params: list, next_param,
    ) -> CompiledQuery:
        """Compile metric as two independent subqueries.

        Grouped independent subqueries (dimensions present) are NOT supported
        because scalar subqueries joined on a constant key cannot produce
        per-group results. Fail closed by raising ValueError.
        """
        reg = _INDEPENDENT_SUBQUERY_REGISTRY[metric_id]

        # ── Fail closed: grouped independent subqueries unsupported ────
        if plan.dimensions:
            raise ValueError(
                f"Grouped independent subqueries for '{metric_id}' are not "
                f"supported: scalar subqueries joined on a constant key cannot "
                f"produce per-group results. Use 'single_query' strategy or "
                f"approved_metric_view for grouped execution."
            )

        # ── Filter routing: resolve column aliases per subquery ────────
        num_alias = self._extract_subquery_alias(reg["numerator"])
        den_alias = self._extract_subquery_alias(reg["denominator"])
        num_table = self._extract_subquery_table(reg["numerator"])
        den_table = self._extract_subquery_table(reg["denominator"])

        where_parts = self._compile_where_routed(
            plan, next_param, num_table, num_alias, den_table, den_alias,
        )
        num_where = f"WHERE {where_parts[num_table]}" if where_parts.get(num_table) else ""
        den_where = f"WHERE {where_parts[den_table]}" if where_parts.get(den_table) else ""

        num_sql = reg["numerator"]
        den_sql = reg["denominator"]

        if num_where:
            kw = "AND" if " WHERE " in num_sql.upper() else "WHERE"
            num_sql = num_sql.rstrip() + f"\n  {kw} {where_parts[num_table].lstrip('WHERE ')}"
        if den_where:
            kw = "AND" if " WHERE " in den_sql.upper() else "WHERE"
            den_sql = den_sql.rstrip() + f"\n  {kw} {where_parts[den_table].lstrip('WHERE ')}"

        # Build the combined SQL
        sql = f"""SELECT
    {reg['ratio_expr']} AS {metric_id}
FROM
    ({num_sql}) AS _num,
    ({den_sql}) AS _den"""

        # Add ORDER BY and LIMIT if present
        order_clause = self._compile_order_by(plan)
        if order_clause:
            sql += f"\n{order_clause}"
        sql += f"\nLIMIT {plan.limit}"

        # Column aliases
        aliases = {metric_id: reg["ratio_expr"]}

        description = f"Independent subqueries for {metric_id} (Increment 3.1)"

        return CompiledQuery(
            sql=sql,
            parameters=params,
            tables_used=plan.selected_tables + plan.bridge_tables,
            column_aliases=aliases,
            schema_snapshot_id=plan.schema_snapshot_id,
            semantic_metadata_version=plan.semantic_metadata_version,
            description=description,
        )

    # ── Independent subquery helpers ────────────────────────────────────

    @staticmethod
    def _extract_subquery_alias(sql_template: str) -> str:
        """Extract the table alias from a subquery template.

        e.g. 'SELECT ... FROM loan_contracts lc' → 'lc'
        """
        match = re.search(r'FROM\s+\w+\s+(\w+)', sql_template)
        return match.group(1) if match else ""

    @staticmethod
    def _extract_subquery_table(sql_template: str) -> str:
        """Extract the table name from a subquery template.

        e.g. 'SELECT ... FROM loan_contracts lc' → 'loan_contracts'
        """
        match = re.search(r'FROM\s+(\w+)', sql_template)
        return match.group(1) if match else ""

    def _compile_where_routed(
        self, plan: QueryPlan, next_param,
        num_table: str, num_alias: str,
        den_table: str, den_alias: str,
    ) -> dict:
        """Route WHERE filters to the correct subquery with alias rewriting.

        Returns {table_name: where_clause_string} for each subquery.
        Shared filters (date, branch, region) are applied to both sides.
        Side-specific filters are applied only to the matching side.
        Unsupported filter columns (not in any subquery table) are skipped.
        """
        # Shared columns that apply to both subqueries when the column exists
        # in both tables. branch_id/region/governorate only propagate if the
        # target table actually has the column (non_performing_loans lacks branch_id).
        _SHARED_COLUMNS = {
            "created_at",
            "branch_id",
            "region",
            "governorate",
        }

        # Columns that exist per subquery table (validated against live schema)
        _TABLE_HAS_COLUMN = {
            "loan_contracts": {"created_at", "branch_id", "currency"},
            "accounts": {"created_at", "branch_id", "currency"},
            "non_performing_loans": {"created_at"},
            "income_statement_snapshots": {"period"},
            "balance_sheet_snapshots": {"period"},
        }

        def _col_exists_in_table(table: str, col: str) -> bool:
            """Check if a column exists in the given table for shared-column propagation."""
            if table in _TABLE_HAS_COLUMN:
                return col in _TABLE_HAS_COLUMN[table]
            return False

        result = {num_table: [], den_table: []}

        for f in plan.filters:
            parts = f.column.split(".")
            if len(parts) == 2:
                filter_table, filter_col = parts
            else:
                filter_table, filter_col = "", parts[0]

            # Determine if this filter applies to num, den, or both
            applies_to_num = False
            applies_to_den = False

            if filter_table == num_table:
                applies_to_num = True
                # Shared column in matched table → also apply to other side
                # only if the other table actually has the column
                if filter_col in _SHARED_COLUMNS:
                    if _col_exists_in_table(den_table, filter_col):
                        applies_to_den = True
                    else:
                        # ponytail: population filter cannot reach denominator → fail closed
                        raise ValueError(
                            f"Population filter '{f.column}' cannot be routed to denominator "
                            f"table '{den_table}' (column '{filter_col}' not present). "
                            f"Failing closed: cannot compute meaningful ratio with "
                            f"unequal population filters."
                        )
            elif filter_table == den_table:
                applies_to_den = True
                if filter_col in _SHARED_COLUMNS:
                    if _col_exists_in_table(num_table, filter_col):
                        applies_to_num = True
                    else:
                        raise ValueError(
                            f"Population filter '{f.column}' cannot be routed to numerator "
                            f"table '{num_table}' (column '{filter_col}' not present). "
                            f"Failing closed: cannot compute meaningful ratio with "
                            f"unequal population filters."
                        )
            elif not filter_table:
                # Unqualified column: apply to both if present
                applies_to_num = True
                applies_to_den = True
            else:
                # Table specified but doesn't match either subquery → fail closed
                raise ValueError(
                    f"Unsupported filter column '{f.column}': table '{filter_table}' "
                    f"is not in the subquery tables ({num_table}, {den_table}). "
                    f"Filters must reference columns from the metric's source tables."
                )

            if applies_to_num:
                alias_col = f"{num_alias}.{filter_col}"
                ph = next_param(f.value)
                if f.operator.upper() == "IN" and isinstance(f.value, (list, tuple)):
                    placeholders = ", ".join(next_param(v) for v in f.value)
                    result[num_table].append(f"{alias_col} IN ({placeholders})")
                elif f.operator.upper() == "BETWEEN" and isinstance(f.value, (list, tuple)) and len(f.value) == 2:
                    ph_lo = next_param(f.value[0])
                    ph_hi = next_param(f.value[1])
                    result[num_table].append(f"{alias_col} BETWEEN {ph_lo} AND {ph_hi}")
                else:
                    result[num_table].append(f"{alias_col} {f.operator} {ph}")

            if applies_to_den:
                alias_col = f"{den_alias}.{filter_col}"
                ph = next_param(f.value)
                if f.operator.upper() == "IN" and isinstance(f.value, (list, tuple)):
                    placeholders = ", ".join(next_param(v) for v in f.value)
                    result[den_table].append(f"{alias_col} IN ({placeholders})")
                elif f.operator.upper() == "BETWEEN" and isinstance(f.value, (list, tuple)) and len(f.value) == 2:
                    ph_lo = next_param(f.value[0])
                    ph_hi = next_param(f.value[1])
                    result[den_table].append(f"{alias_col} BETWEEN {ph_lo} AND {ph_hi}")
                else:
                    result[den_table].append(f"{alias_col} {f.operator} {ph}")

        if plan.time_range.type == "relative" and plan.time_range.value:
            interval = _TIME_INTERVALS.get(plan.time_range.value)
            if interval:
                for table, alias, where_list in [
                    (num_table, num_alias, result[num_table]),
                    (den_table, den_alias, result[den_table]),
                ]:
                    date_col_name = _DATE_COLUMNS.get(table)
                    if date_col_name:
                        where_list.append(
                            f"{alias}.{date_col_name} >= CURRENT_DATE - INTERVAL '{interval}'"
                        )

        return {
            num_table: " AND ".join(result[num_table]),
            den_table: " AND ".join(result[den_table]),
        }

    def _describe(self, plan: QueryPlan) -> str:
        action = plan.task.replace("_", " ").title()
        tables = ", ".join(plan.selected_tables[:3])
        n_metrics = len(plan.metrics) + len(plan.analytical_expressions)
        n_filters = len(plan.filters)
        desc = f"{action} from {tables}"
        if n_metrics:
            desc += f" ({n_metrics} metric{'s' if n_metrics > 1 else ''})"
        if n_filters:
            desc += f" with {n_filters} filter{'s' if n_filters > 1 else ''}"
        if plan.dimensions:
            dims = ", ".join(d.name for d in plan.dimensions)
            desc += f" grouped by {dims}"
        return desc


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _infer_type(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return "date"
    return "string"
