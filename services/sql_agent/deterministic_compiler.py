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


class SQLCompileError(Exception):
    """Raised when a QueryPlan cannot be compiled to valid SQL.

    Carries a stable error code so callers can attribute failures without
    parsing the message (Step 14: deterministic compiler correctness repair).
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

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
    "fee_income": "value_date",
    "provisions": "provision_date",
    "income_statement_snapshots": "period",
    "balance_sheet_snapshots": "period",
    "compliance_violations": "detected_at",
    "suspicious_activity_reports": "report_date",
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
    "roe": {
        "numerator": "SELECT COALESCE(SUM(ins.net_income), 0) AS num FROM income_statement_snapshots ins",
        "denominator": "SELECT COALESCE(SUM(bss.total_equity), 0) AS den FROM balance_sheet_snapshots bss",
        "ratio_expr": "ROUND(100.0 * _num.num::numeric / NULLIF(_den.den::numeric, 0), 2)",
    },
    "roa": {
        "numerator": "SELECT COALESCE(SUM(ins.net_income), 0) AS num FROM income_statement_snapshots ins",
        "denominator": "SELECT COALESCE(SUM(bss.total_assets), 0) AS den FROM balance_sheet_snapshots bss",
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

        # ── Step 14 REPAIR: base-table selection + join state machine ──
        # The SQL relation set is built once and threaded through every
        # clause so joins, SELECT, GROUP BY, and WHERE share one graph.
        base, relation, join_clause = self._compile_base_and_joins(plan)

        # ── SELECT ────────────────────────────────────────────────────────
        select_parts = self._compile_select(plan, relation)
        select_clause = f"SELECT {', '.join(select_parts)}"

        # ── FROM ──────────────────────────────────────────────────────────
        from_clause = f"FROM {base}"

        # ── WHERE ─────────────────────────────────────────────────────────
        where_parts = self._compile_where(plan, relation, next_param)
        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        # ── GROUP BY (dimensions present = group by them) ─────────────────
        group_clause = self._compile_group_by(plan, relation)

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

    def _compile_select(
        self, plan: QueryPlan, relation: set,
    ) -> List[str]:
        parts: List[str] = []

        # Registered metric formulas
        for m in plan.metrics:
            missing = [t for t in m.source_tables if t not in relation]
            if missing:
                raise SQLCompileError(
                    "UNRESOLVABLE_JOIN_GRAPH",
                    f"Metric '{m.metric_id}' references table(s) {missing} "
                    f"not present in the SQL relation set {sorted(relation)}.",
                )
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
                if col.table in relation:
                    parts.append(f"{col.table}.{col.name}")
        elif plan.dimensions:
            dim_set = {(d.table, d.name) for d in plan.dimensions}
            for col in plan.requested_columns:
                if (col.table, col.name) in dim_set and col.table in relation:
                    parts.append(f"{col.table}.{col.name}")
            for d in plan.dimensions:
                if (d.table, d.name) not in {(c.table, c.name) for c in plan.requested_columns}:
                    if d.table not in relation:
                        raise SQLCompileError(
                            "UNRESOLVABLE_JOIN_GRAPH",
                            f"Dimension '{d.qualified}' references table '{d.table}' "
                            f"not present in the SQL relation set {sorted(relation)}.",
                        )
                    parts.append(f"{d.table}.{d.name}")

        # Fallback: if nothing selected, add primary key
        if not parts and plan.selected_tables:
            base = next((t for t in plan.selected_tables if t in relation), None)
            if base:
                pk = f"{base.rstrip('s')}_id"
                parts.append(f"{base}.{pk}")

        return parts

    # ── FROM root & join state machine (Step 14 repair) ───────────────────

    def _compile_base_and_joins(self, plan: QueryPlan) -> tuple:
        """Choose the true primary FROM table and build the ordered JOIN list.

        Base-table selection:
          - No joins → the single selected table.
          - Joins → the join-graph head: a table that appears as some edge's
            from_table and never as any edge's to_table (the root of the ER
            tree). Deterministic fallbacks handle ambiguous graphs.

        Join state machine (Step 14 §6):
          joined = {base}
          for every edge (s → t):
            * s in joined and t not        → JOIN t,  joined += {t}
            * t in joined and s not        → JOIN s (reversed), joined += {s}
            * both already joined          → skip duplicate edge
            * neither joined               → UNRESOLVABLE_JOIN_GRAPH

        Self-join protection (Step 14 §7): s == t is rejected unless the edge
        is explicitly marked self_join_allowed=true.

        Table presence (Step 14 §8): every table referenced in an ON predicate
        of an emitted join is either already joined or the table being
        introduced — guaranteed by the state machine.

        Returns (base, relation, join_clause). relation = {base} ∪ joined.
        """
        joins = plan.joins or []
        if not joins:
            if not plan.selected_tables:
                raise SQLCompileError("EMPTY_PLAN", "QueryPlan selects no tables")
            base = plan.selected_tables[0]
            return base, {base}, ""

        froms = {j.from_table for j in joins}
        tos = {j.to_table for j in joins}

        # Source-only nodes (never a join target) present in selected tables.
        source_only = sorted(froms - tos)
        candidates = [t for t in source_only if t in plan.selected_tables]
        if candidates:
            base = candidates[0]
        elif froms:
            base = next((t for t in plan.selected_tables if t in froms), sorted(froms)[0])
        else:
            base = plan.selected_tables[0]

        joined = {base}
        lines = []
        for j in joins:
            s, t = j.from_table, j.to_table
            if s == t:
                self_allowed = bool(getattr(j, "self_join_allowed", False))
                if not self_allowed:
                    raise SQLCompileError(
                        "SELF_JOIN_FORBIDDEN",
                        f"Self-join on '{s}' is not allowed unless explicitly marked "
                        f"self_join_allowed=true.",
                    )
                continue
            if s in joined and t not in joined:
                lines.append(f"{j.join_type} {t} ON {j.condition}")
                joined.add(t)
            elif t in joined and s not in joined:
                # Reverse: introduce the source side onto the already-present
                # target. The ON predicate stays the same because both tables
                # are in the relation set (t present, s being introduced).
                lines.append(f"{j.join_type} {s} ON {j.condition}")
                joined.add(s)
            elif s in joined and t in joined:
                # Duplicate edge: both endpoints already present, skip.
                continue
            else:
                # Neither endpoint present → disconnected from the current
                # graph. Do not emit a fabricated path.
                raise SQLCompileError(
                    "UNRESOLVABLE_JOIN_GRAPH",
                    f"Join '{s} → {t}' has no endpoint in the relation set "
                    f"{sorted(joined)}; plan join graph is disconnected.",
                )

        return base, joined, "\n    ".join(lines)

    # ── WHERE compilation ─────────────────────────────────────────────────

    def _compile_where(
        self, plan: QueryPlan, relation: set, next_param,
    ) -> List[str]:
        parts: List[str] = []

        for f in plan.filters:
            # Null semantics (Step 14 §16): IS NULL / IS NOT NULL are never
            # bound to = NULL parameters.
            op = f.operator.upper()
            if op in ("IS NULL", "IS NOT NULL"):
                parts.append(f"{f.column} {op}")
                continue

            col_table = f.column.split(".")[0] if "." in f.column else ""
            if col_table and col_table not in relation:
                raise SQLCompileError(
                    "UNRESOLVABLE_JOIN_GRAPH",
                    f"Filter '{f.column}' references table '{col_table}' outside "
                    f"the SQL relation set {sorted(relation)}.",
                )

            if op == "IN" and isinstance(f.value, (list, tuple)):
                placeholders = ", ".join(next_param(v) for v in f.value)
                parts.append(f"{f.column} IN ({placeholders})")
            elif op == "BETWEEN" and isinstance(f.value, (list, tuple)) and len(f.value) == 2:
                ph_lo = next_param(f.value[0])
                ph_hi = next_param(f.value[1])
                parts.append(f"{f.column} BETWEEN {ph_lo} AND {ph_hi}")
            else:
                ph = next_param(f.value)
                parts.append(f"{f.column} {op} {ph}")

        if plan.time_range.type == "relative" and plan.time_range.value:
            interval = _TIME_INTERVALS.get(plan.time_range.value)
            if interval:
                date_col = self._resolve_date_column(plan, relation)
                if date_col:
                    parts.append(f"{date_col} >= CURRENT_DATE - INTERVAL '{interval}'")

        return parts

    def _resolve_date_column(self, plan: QueryPlan, relation: set = None) -> str:
        relation = relation or set(plan.selected_tables)
        for t in plan.selected_tables:
            if t not in relation:
                continue
            dc = _DATE_COLUMNS.get(t)
            if dc:
                return f"{t}.{dc}"
        return ""

    # ── GROUP BY compilation ──────────────────────────────────────────────

    def _compile_group_by(self, plan: QueryPlan, relation: set = None) -> str:
        """Pure renderer: GROUP BY when dimensions are present."""
        if not plan.dimensions:
            return ""
        relation = relation or {d.table for d in plan.dimensions}
        for d in plan.dimensions:
            if d.table not in relation:
                raise SQLCompileError(
                    "UNRESOLVABLE_JOIN_GRAPH",
                    f"Dimension '{d.qualified}' references table '{d.table}' outside "
                    f"the SQL relation set {sorted(relation)}.",
                )
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
            "fee_income": {"created_at", "value_date", "account_id"},
            "provisions": {"created_at", "provision_date", "loan_id"},
            "income_statement_snapshots": {"period"},
            "balance_sheet_snapshots": {"period"},
            "compliance_violations": {"detected_at"},
            "suspicious_activity_reports": {"report_date"},
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
                op = f.operator.upper()
                if op in ("IS NULL", "IS NOT NULL"):
                    result[num_table].append(f"{alias_col} {op}")
                else:
                    ph = next_param(f.value)
                    if op == "IN" and isinstance(f.value, (list, tuple)):
                        placeholders = ", ".join(next_param(v) for v in f.value)
                        result[num_table].append(f"{alias_col} IN ({placeholders})")
                    elif op == "BETWEEN" and isinstance(f.value, (list, tuple)) and len(f.value) == 2:
                        ph_lo = next_param(f.value[0])
                        ph_hi = next_param(f.value[1])
                        result[num_table].append(f"{alias_col} BETWEEN {ph_lo} AND {ph_hi}")
                    else:
                        result[num_table].append(f"{alias_col} {op} {ph}")

            if applies_to_den:
                alias_col = f"{den_alias}.{filter_col}"
                op = f.operator.upper()
                if op in ("IS NULL", "IS NOT NULL"):
                    result[den_table].append(f"{alias_col} {op}")
                else:
                    ph = next_param(f.value)
                    if op == "IN" and isinstance(f.value, (list, tuple)):
                        placeholders = ", ".join(next_param(v) for v in f.value)
                        result[den_table].append(f"{alias_col} IN ({placeholders})")
                    elif op == "BETWEEN" and isinstance(f.value, (list, tuple)) and len(f.value) == 2:
                        ph_lo = next_param(f.value[0])
                        ph_hi = next_param(f.value[1])
                        result[den_table].append(f"{alias_col} BETWEEN {ph_lo} AND {ph_hi}")
                    else:
                        result[den_table].append(f"{alias_col} {op} {ph}")

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
