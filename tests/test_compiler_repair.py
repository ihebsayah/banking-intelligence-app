"""
tests/test_compiler_repair.py
Step 14: Deterministic SQL compiler correctness repair — focused unit matrix.

Covers the compiler invariants from STEP 14:
  - correct FROM root (join-graph head, never alphabetical accounts-first)
  - join state machine (ordering, duplicates, unreachable → error, no self-join)
  - SELECT / GROUP BY built from plan dimensions only
  - filter parameterization (order, IN, BETWEEN, IS NULL without binding)
  - limits and ordering
  - ratio metric path (independent subqueries)
  - validator accepts generated join SQL

Runs without a database. Only test 30 loads QueryValidator (pure rules).
"""
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVICES = os.path.join(ROOT, "services")
for _p in (SERVICES, os.path.join(SERVICES, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sql_agent.plan_models import (
    QueryPlan, ColumnRef, JoinSpec, FilterSpec, MetricReference,
    AggregateExpression, TimeRangeSpec, SortSpec,
)
from sql_agent.deterministic_compiler import DeterministicSQLCompiler, SQLCompileError

COMPILER = DeterministicSQLCompiler()


def plan(
    *,
    selected_tables=None,
    joins=None,
    requested_columns=None,
    metrics=None,
    dims=None,
    filters=None,
    time_range=None,
    sort=None,
    limit=100,
    analytical=None,
) -> QueryPlan:
    return QueryPlan(
        schema_snapshot_id="snap-repair",
        semantic_metadata_version="v14",
        task="aggregation",
        query_text="test",
        selected_tables=selected_tables or [],
        selected_columns={},
        joins=joins or [],
        requested_columns=requested_columns or [],
        metrics=metrics or [],
        analytical_expressions=analytical if analytical is not None else [],
        dimensions=dims or [],
        filters=filters or [],
        time_range=time_range or TimeRangeSpec(),
        sort=sort,
        limit=limit,
    )


def col(table, name):
    return ColumnRef(table=table, name=name)


def J(from_table, to_table, condition=None, join_type="INNER JOIN"):
    return JoinSpec(
        from_table=from_table,
        to_table=to_table,
        join_type=join_type,
        join_key=from_table + "_id",
        condition=condition or f"{from_table}.{from_table.rstrip('s')}_id = "
                               f"{to_table}.{to_table.rstrip('s')}_id",
    )


# ─── 1. Single-table customer count ─────────────────────────────────────────
def test_single_table_customer_count():
    p = plan(selected_tables=["customers"])
    cq = COMPILER.compile(p)
    assert "FROM customers" in cq.sql
    assert "JOIN" not in cq.sql


# ─── 2. Single-table account aggregation ────────────────────────────────────
def test_single_table_account_sum():
    p = plan(
        selected_tables=["accounts"],
        analytical=[AggregateExpression(function="SUM", column=col("accounts", "balance"), alias="sum_balance")],
    )
    cq = COMPILER.compile(p)
    assert "FROM accounts" in cq.sql
    assert "SUM(accounts.balance)" in cq.sql


# ─── 3. Customers by segment ────────────────────────────────────────────────
def test_customers_by_segment():
    p = plan(
        selected_tables=["customers"],
        dims=[col("customers", "segment")],
        requested_columns=[col("customers", "segment")],
        analytical=[AggregateExpression(function="COUNT", column=None, alias="count_all")],
    )
    cq = COMPILER.compile(p)
    assert "FROM customers" in cq.sql
    assert "GROUP BY customers.segment" in cq.sql


# ─── 4. Customer → account join ─────────────────────────────────────────────
def test_customer_account_join():
    p = plan(
        selected_tables=["accounts", "customers"],
        joins=[J("customers", "accounts", "customers.customer_id = accounts.customer_id", "LEFT JOIN")],
        dims=[col("customers", "segment")],
    )
    cq = COMPILER.compile(p)
    # FROM root must be the join head (customers), NOT alphabetical accounts.
    assert "FROM customers" in cq.sql
    assert "JOIN accounts ON customers.customer_id = accounts.customer_id" in cq.sql
    assert "JOIN customers" not in cq.sql


# ─── 5. Account → branch join ───────────────────────────────────────────────
def test_account_branch_join():
    p = plan(
        selected_tables=["accounts", "branches"],
        joins=[J("accounts", "branches", "accounts.branch_id = branches.branch_id")],
    )
    cq = COMPILER.compile(p)
    assert cq.sql.startswith("SELECT") or "FROM accounts" in cq.sql
    assert "FROM accounts" in cq.sql
    assert "JOIN branches" in cq.sql


# ─── 6. Customer → account → branch two-hop ────────────────────────────────
def test_two_hop_join():
    p = plan(
        selected_tables=["customers", "accounts", "branches"],
        joins=[
            J("customers", "accounts", "customers.customer_id = accounts.customer_id"),
            J("accounts", "branches", "accounts.branch_id = branches.branch_id"),
        ],
        dims=[col("branches", "name")],
    )
    cq = COMPILER.compile(p)
    assert "FROM customers" in cq.sql
    ci = cq.sql.index("JOIN")
    assert cq.sql.index("accounts") < cq.sql.index("branches", ci)


# ─── 7. No accidental self-join ─────────────────────────────────────────────
def test_no_accidental_self_join():
    """The classic Step-13 defect: FROM accounts LEFT JOIN accounts."""
    p = plan(
        selected_tables=["accounts", "customers"],
        joins=[J("customers", "accounts", "customers.customer_id = accounts.customer_id", "LEFT JOIN")],
    )
    cq = COMPILER.compile(p)
    assert "FROM customers" in cq.sql
    assert "JOIN accounts ON customers.customer_id = accounts.customer_id" in cq.sql
    # no self-join: accounts must never be both FROM root and join target, and
    # a JOIN must never reuse the base table as its introduced side.
    assert "FROM accounts" not in cq.sql
    assert "JOIN customers" not in cq.sql
    assert cq.sql.index("FROM customers") < cq.sql.index("JOIN accounts")


# ─── 8. Duplicate edge ignored ──────────────────────────────────────────────
def test_duplicate_edge_ignored():
    p = plan(
        selected_tables=["accounts", "branches"],
        joins=[
            J("accounts", "branches", "accounts.branch_id = branches.branch_id"),
            J("accounts", "branches", "accounts.branch_id = branches.branch_id"),
        ],
    )
    cq = COMPILER.compile(p)
    assert cq.sql.count("JOIN branches") == 1


# ─── 9. Disconnected graph rejected ─────────────────────────────────────────
def test_disconnected_graph_rejected():
    p = plan(
        selected_tables=["customers", "risk_flags"],
        joins=[J("customers", "risk_flags", "customers.customer_id = risk_flags.customer_id")],
        dims=[col("branches", "name")],
    )
    with pytest.raises(SQLCompileError) as ei:
        COMPILER.compile(p)
    assert ei.value.code == "UNRESOLVABLE_JOIN_GRAPH"


# ─── 10–12. Aggregation functions ──────────────────────────────────────────
def test_count():
    p = plan(selected_tables=["customers"],
             analytical=[AggregateExpression(function="COUNT", column=None, alias="count_all")])
    assert "COUNT(*)" in COMPILER.compile(p).sql


def test_sum():
    p = plan(selected_tables=["accounts"],
             analytical=[AggregateExpression(function="SUM", column=col("accounts", "balance"), alias="s")])
    assert "SUM(accounts.balance)" in COMPILER.compile(p).sql


def test_avg():
    p = plan(selected_tables=["accounts"],
             analytical=[AggregateExpression(function="AVG", column=col("accounts", "balance"), alias="a")])
    assert "AVG(accounts.balance)" in COMPILER.compile(p).sql


# ─── 13–14. Grouped / multi-dimension aggregate ─────────────────────────────
def test_grouped_aggregate():
    p = plan(
        selected_tables=["accounts"],
        dims=[col("accounts", "status")],
        analytical=[AggregateExpression(function="COUNT", column=None, alias="count_all")],
    )
    cq = COMPILER.compile(p)
    assert "GROUP BY accounts.status" in cq.sql
    assert "accounts.status" in cq.sql.split("GROUP BY")[0]  # selected too


def test_multi_dimension_group():
    p = plan(
        selected_tables=["accounts"],
        dims=[col("accounts", "account_type"), col("accounts", "status")],
        analytical=[AggregateExpression(function="COUNT", column=None, alias="count_all")],
    )
    cq = COMPILER.compile(p)
    gb = cq.sql.split("GROUP BY")[1]
    assert "accounts.account_type" in gb
    assert "accounts.status" in gb


# ─── 15. Filter parameterization ────────────────────────────────────────────
def test_filter_parameterization():
    p = plan(
        selected_tables=["customers"],
        filters=[FilterSpec(column="customers.segment", operator="=", value="CORP_LARGE")],
    )
    cq = COMPILER.compile(p)
    assert "customers.segment = $1" in cq.sql
    assert cq.parameters[0].value == "CORP_LARGE"
    assert "$1" in cq.sql and "[object]" not in cq.sql


# ─── 16. Multiple filter parameter order ────────────────────────────────────
def test_filter_parameter_order():
    p = plan(
        selected_tables=["customers", "branches"],
        joins=[J("customers", "accounts", "customers.customer_id = accounts.customer_id", "LEFT JOIN"),
               J("accounts", "branches", "accounts.branch_id = branches.branch_id", "LEFT JOIN")],
        filters=[
            FilterSpec(column="customers.segment", operator="=", value="corporate"),
            FilterSpec(column="branches.region_id", operator="=", value="Tunis"),
        ],
    )
    cq = COMPILER.compile(p)
    assert cq.sql.index("customers.segment = $1") < cq.sql.index("branches.region_id = $2")
    assert [x.value for x in cq.parameters] == ["corporate", "Tunis"]


# ─── 17. French string value parameterized ──────────────────────────────────
def test_french_value_parameterized():
    p = plan(
        selected_tables=["customers"],
        filters=[FilterSpec(column="customers.segment", operator="=", value="CORP_LARGE")],
    )
    cq = COMPILER.compile(p)
    assert "CORP_LARGE" not in cq.sql.replace("$1", "")
    assert cq.parameters[0].value == "CORP_LARGE"


# ─── 18. Date range parameterization (BETWEEN) ──────────────────────────────
def test_date_range_parameters():
    p = plan(
        selected_tables=["accounts"],
        filters=[FilterSpec(
            column="accounts.created_at", operator="BETWEEN",
            value=["2025-01-01", "2025-12-31"],
        )],
    )
    cq = COMPILER.compile(p)
    assert "accounts.created_at BETWEEN $1 AND $2" in cq.sql
    assert [x.value for x in cq.parameters] == ["2025-01-01", "2025-12-31"]


# ─── 19. Status filter ──────────────────────────────────────────────────────
def test_status_filter():
    p = plan(
        selected_tables=["accounts"],
        filters=[FilterSpec(column="accounts.status", operator="=", value="dormant")],
    )
    cq = COMPILER.compile(p)
    assert "accounts.status = $1" in cq.sql
    assert cq.parameters[0].value == "dormant"


# ─── 20. Numeric threshold filter ───────────────────────────────────────────
def test_numeric_threshold_filter():
    p = plan(
        selected_tables=["customers"],
        filters=[FilterSpec(column="customers.risk_score", operator=">", value=0.7)],
    )
    cq = COMPILER.compile(p)
    assert "customers.risk_score > $1" in cq.sql
    assert cq.parameters[0].value == 0.7


# ─── 21. NULL filter ────────────────────────────────────────────────────────
def test_null_filter_never_binds():
    p = plan(
        selected_tables=["risk_flags"],
        filters=[FilterSpec(column="risk_flags.resolved_at", operator="IS NULL", value=None)],
    )
    cq = COMPILER.compile(p)
    assert "risk_flags.resolved_at IS NULL" in cq.sql
    assert len(cq.parameters) == 0


def test_not_null_filter_never_binds():
    p = plan(
        selected_tables=["risk_flags"],
        filters=[FilterSpec(column="risk_flags.resolved_at", operator="IS NOT NULL", value=None)],
    )
    cq = COMPILER.compile(p)
    assert "risk_flags.resolved_at IS NOT NULL" in cq.sql
    assert len(cq.parameters) == 0


# ─── 22. IN filter ──────────────────────────────────────────────────────────
def test_in_filter_parameterized():
    p = plan(
        selected_tables=["accounts"],
        filters=[FilterSpec(column="accounts.status", operator="IN", value=["active", "dormant"])],
    )
    cq = COMPILER.compile(p)
    assert "accounts.status IN ($1, $2)" in cq.sql
    assert [x.value for x in cq.parameters] == ["active", "dormant"]
    assert "[object Object]" not in cq.sql


# ─── 23–24. Ordering ────────────────────────────────────────────────────────
def test_top_n_ordering():
    p = plan(
        selected_tables=["branches", "accounts"],
        joins=[J("accounts", "branches", "accounts.branch_id = branches.branch_id", "LEFT JOIN")],
        dims=[col("branches", "name")],
        analytical=[AggregateExpression(function="COUNT", column=None, alias="count_all")],
        sort=SortSpec(column="count_all", direction="DESC"),
        limit=5,
    )
    cq = COMPILER.compile(p)
    assert "ORDER BY count_all DESC" in cq.sql
    assert "LIMIT 5" in cq.sql


def test_bottom_n_ordering():
    p = plan(
        selected_tables=["accounts"],
        analytical=[AggregateExpression(function="SUM", column=col("accounts", "balance"), alias="total")],
        sort=SortSpec(column="total", direction="ASC"),
        limit=3,
    )
    cq = COMPILER.compile(p)
    assert "ORDER BY total ASC" in cq.sql
    assert "LIMIT 3" in cq.sql


# ─── 25–26. Limits ──────────────────────────────────────────────────────────
def test_default_limit():
    cq = COMPILER.compile(plan(selected_tables=["customers"]))
    assert "LIMIT 100" in cq.sql


def test_requested_limit():
    cq = COMPILER.compile(plan(selected_tables=["customers"], limit=42))
    assert "LIMIT 42" in cq.sql


# ─── 27. Ambiguous column qualification ─────────────────────────────────────
def test_column_qualification():
    p = plan(
        selected_tables=["customers", "accounts"],
        joins=[J("customers", "accounts", "customers.customer_id = accounts.customer_id", "LEFT JOIN")],
        dims=[col("customers", "segment")],
        requested_columns=[col("customers", "segment")],
        analytical=[AggregateExpression(function="COUNT", column=None, alias="count_all")],
    )
    cq = COMPILER.compile(p)
    assert "customers.segment" in cq.sql
    assert "GROUP BY customers.segment" in cq.sql  # fully qualified, never bare


# ─── 28. Invalid group-by rejected ──────────────────────────────────────────
def test_invalid_group_by_rejected():
    p = plan(
        selected_tables=["customers"],
        dims=[col("branches", "name")],
        analytical=[AggregateExpression(function="COUNT", column=None, alias="count_all")],
    )
    with pytest.raises(SQLCompileError) as ei:
        COMPILER.compile(p)
    assert ei.value.code == "UNRESOLVABLE_JOIN_GRAPH"


# ─── 29. Ratio metric (independent subqueries) ──────────────────────────────
def test_ratio_metric_subqueries():
    from sql_agent.plan_models import MetricExecutionStrategy
    p = QueryPlan(
        schema_snapshot_id="snap", semantic_metadata_version="v14",
        task="aggregation", query_text="npl",
        selected_tables=["loan_contracts", "non_performing_loans"],
        metrics=[MetricReference(
            metric_id="npl_ratio", alias="npl_ratio",
            formula="ROUND(100.0 * x / NULLIF(y,0), 2)",
            source_tables=["loan_contracts", "non_performing_loans"],
            execution_strategy=MetricExecutionStrategy(
                execution_strategy="independent_subqueries"),
        )],
    )
    cq = COMPILER.compile(p)
    assert "_num" in cq.sql and "_den" in cq.sql
    assert "npl_ratio" in cq.sql


def test_ratio_metric_disconnected_edges_rejected():
    """A registered-formula metric referencing tables the join graph cannot
    reach must fail closed instead of emitting SQL referencing tables absent
    from the FROM clause (would be a DB error at runtime)."""
    p = QueryPlan(
        schema_snapshot_id="snap", semantic_metadata_version="v14",
        task="aggregation", query_text="npl",
        selected_tables=["loan_contracts"],  # non_performing_loans unreachable
        metrics=[MetricReference(
            metric_id="npl_ratio", alias="npl_ratio",
            formula="COUNT(DISTINCT n.loan_id)::numeric / NULLIF(COUNT(DISTINCT lc.loan_id), 0)",
            source_tables=["loan_contracts", "non_performing_loans"],
        )],
    )
    with pytest.raises(SQLCompileError) as ei:
        COMPILER.compile(p)
    assert ei.value.code == "UNRESOLVABLE_JOIN_GRAPH"


# ─── 30. Validator accepts generated join SQL ───────────────────────────────
def test_validator_accepts_join_sql():
    """Generated multi-table join SQL passes the QueryValidator."""
    import importlib
    prev = sys.modules.get("models")
    sys.modules.pop("models", None)
    vd = os.path.join(SERVICES, "validation_agent")
    sys.path.insert(0, vd)
    sys.modules["models"] = importlib.import_module("models")
    sys.path.remove(vd)
    try:
        QueryValidator = importlib.import_module("validation_agent.query_validator").QueryValidator
        QueryValidationRequest = importlib.import_module("validation_agent.models").QueryValidationRequest
    finally:
        if prev is None:
            sys.modules.pop("models", None)
        else:
            sys.modules["models"] = prev

    p = plan(
        selected_tables=["customers", "accounts", "branches"],
        joins=[
            J("customers", "accounts", "customers.customer_id = accounts.customer_id", "INNER JOIN"),
            J("accounts", "branches", "accounts.branch_id = branches.branch_id", "INNER JOIN"),
        ],
        dims=[col("branches", "name")],
        analytical=[AggregateExpression(function="COUNT", column=None, alias="count_all")],
    )
    cq = COMPILER.compile(p)
    request = QueryValidationRequest(sql=cq.sql, parameters=[], user_role="analyst")
    resp = QueryValidator().validate(request)
    assert resp.safe is True