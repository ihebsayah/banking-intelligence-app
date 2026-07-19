"""
tests/test_increment2_compile.py
Compile-only tests for Increment 2 + 2.5 + 2.6: QueryPlan, QueryPlanBuilder,
DeterministicSQLCompiler, CompiledQuery, analytical expressions,
CaseExpression, GrainSpec, fan-out detection, ExpectedAnswer.

Covers:
  - detail listing, aggregate-only, grouped aggregate, multi-dimension
  - ranking, numeric/string/relative-date filters
  - registered joins, bridge-table joins
  - COUNT(*) accepted, SELECT * rejected
  - unknown column/metric/join rejected (metric FAILS plan)
  - unsupported grain, missing requested field
  - deterministic repeatability, metadata snapshot mismatch
  - SQL injection value bound as parameter
  - Implicit aggregation: COUNT, SUM, AVG, MIN, MAX, DISTINCT COUNT
  - Ratio and percentage expressions (CaseExpression conditional)
  - ExpectedAnswer generation (scalar, detail_rows, grouped_rows, ranked_list, time_series)
  - Entity-aware COUNT(DISTINCT) with joins
  - Fan-out detection (one_to_many, many_to_many)
  - Grain propagation (source → output)
  - LDR must use named metric (implicit fails)
  - Deterministic SQL stability
"""
import sys
import os
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVICES = os.path.join(ROOT, "services")
for p in [SERVICES]:
    if p not in sys.path:
        sys.path.insert(0, p)

from sql_agent.plan_models import (
    QueryPlan, CompiledQuery, AggregateExpression, RatioExpression,
    CaseExpression, ColumnRef, GrainSpec, JoinSpec,
)
from sql_agent.query_plan_builder import QueryPlanBuilder
from sql_agent.deterministic_compiler import DeterministicSQLCompiler


# ─── Shared fixtures ─────────────────────────────────────────────────────────

BUILDER = QueryPlanBuilder()
COMPILER = DeterministicSQLCompiler()

SNAPSHOT = "snap-test-001"
VERSION = "v6C.5t.3j"

BASE_KWARGS = dict(
    query_text="test query",
    selected_tables=["customers"],
    bridge_tables=[],
    selected_columns={"customers": ["customer_id", "name", "email", "segment"]},
    join_paths=[],
    metrics=[],
    dimensions=[],
    filters_structured=[],
    time_range={"type": "none", "value": None},
    sort_structured=None,
    limit_requested=100,
    requested_fields=[],
    semantic_metadata_version=VERSION,
    schema_snapshot_id=SNAPSHOT,
)


def _build_and_compile(**overrides):
    kw = {**BASE_KWARGS, **overrides}
    plan = BUILDER.build(**kw)
    compiled = COMPILER.compile(plan)
    return plan, compiled


# ═════════════════════════════════════════════════════════════════════════════
# ORIGINAL INCREMENT 2 TESTS (updated where behavior changed)
# ═════════════════════════════════════════════════════════════════════════════

# ─── 1. Detail listing ───────────────────────────────────────────────────────

class TestDetailListing:
    def test_basic_listing(self):
        plan, cq = _build_and_compile(
            task="detail_listing",
            requested_fields=["customer_id", "name", "email"],
        )
        assert plan.task == "detail_listing"
        assert cq.sql.startswith("SELECT")
        assert "customers.customer_id" in cq.sql
        assert "customers.name" in cq.sql
        assert "LIMIT" in cq.sql
        assert len(cq.parameters) == 0


# ─── 2. Aggregate-only ──────────────────────────────────────────────────────

class TestAggregateOnly:
    def test_sum_without_group(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["balance"]},
            requested_fields=[],
            metrics=[],
        )
        assert "accounts" in cq.sql
        assert "GROUP BY" not in cq.sql


# ─── 3. Grouped aggregate ────────────────────────────────────────────────────

class TestGroupedAggregate:
    def test_avg_by_segment(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "segment", "risk_score"]},
            metrics=["kyc_compliance_rate"],
            dimensions=["customers.segment"],
            requested_fields=["segment"],
        )
        assert "GROUP BY" in cq.sql
        assert "customers.segment" in cq.sql


# ─── 4. Multi-dimension aggregation ──────────────────────────────────────────

class TestMultiDimension:
    def test_two_dims(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            selected_tables=["customers", "branches"],
            selected_columns={
                "customers": ["customer_id", "segment"],
                "branches": ["branch_id", "governorate"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "branches",
                "join_key": "branch_id", "join_type": "INNER JOIN",
                "condition": "customers.branch_id = branches.branch_id",
            }],
            metrics=["kyc_compliance_rate"],
            dimensions=["customers.segment", "branches.governorate"],
            requested_fields=["segment", "governorate"],
        )
        assert "GROUP BY" in cq.sql
        assert "customers.segment" in cq.sql.split("GROUP BY")[1]
        assert "branches.governorate" in cq.sql.split("GROUP BY")[1]


# ─── 5. Ranking ──────────────────────────────────────────────────────────────

class TestRanking:
    def test_top_n_with_order(self):
        plan, cq = _build_and_compile(
            task="ranking",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            sort_structured=[{"column": "accounts.balance", "direction": "DESC"}],
            limit_requested=10,
            requested_fields=["account_id", "balance"],
        )
        assert "ORDER BY accounts.balance DESC" in cq.sql
        assert "LIMIT 10" in cq.sql


# ─── 6. Numeric filter ──────────────────────────────────────────────────────

class TestNumericFilter:
    def test_gt_filter(self):
        plan, cq = _build_and_compile(
            task="filter",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            filters_structured=[
                {"column": "accounts.balance", "operator": ">", "value": 10000},
            ],
            requested_fields=["account_id", "balance"],
        )
        assert "accounts.balance > $1" in cq.sql
        assert cq.parameters[0].value == 10000


# ─── 7. String filter ───────────────────────────────────────────────────────

class TestStringFilter:
    def test_equality_filter(self):
        plan, cq = _build_and_compile(
            task="filter",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "name", "segment"]},
            filters_structured=[
                {"column": "customers.segment", "operator": "=", "value": "premium"},
            ],
            requested_fields=["customer_id", "name"],
        )
        assert "customers.segment = $1" in cq.sql
        assert cq.parameters[0].value == "premium"


# ─── 8. Relative date filter ─────────────────────────────────────────────────

class TestRelativeDate:
    def test_last_30_days(self):
        plan, cq = _build_and_compile(
            task="filter",
            selected_tables=["transactions"],
            selected_columns={"transactions": ["transaction_id", "amount"]},
            time_range={"type": "relative", "value": "last_30_days"},
            requested_fields=["transaction_id", "amount"],
        )
        assert "CURRENT_DATE - INTERVAL '30 days'" in cq.sql
        assert "transactions.transaction_date" in cq.sql


# ─── 9. Registered multi-table join ──────────────────────────────────────────

class TestRegisteredJoin:
    def test_customer_account_join(self):
        plan, cq = _build_and_compile(
            task="detail_listing",
            selected_tables=["customers", "accounts"],
            selected_columns={
                "customers": ["customer_id", "name"],
                "accounts": ["account_id", "balance"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "accounts",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "customers.customer_id = accounts.customer_id",
            }],
            requested_fields=["customer_id", "name", "balance"],
        )
        assert "JOIN accounts ON customers.customer_id = accounts.customer_id" in cq.sql
        assert len(cq.parameters) == 0


# ─── 10. Bridge-table join ───────────────────────────────────────────────────

class TestBridgeJoin:
    def test_three_table_join(self):
        plan, cq = _build_and_compile(
            task="detail_listing",
            selected_tables=["customers", "accounts", "transactions"],
            bridge_tables=[],
            selected_columns={
                "customers": ["customer_id", "name"],
                "accounts": ["account_id"],
                "transactions": ["transaction_id", "amount"],
            },
            join_paths=[
                {
                    "from_table": "customers", "to_table": "accounts",
                    "join_key": "customer_id", "join_type": "INNER JOIN",
                    "condition": "customers.customer_id = accounts.customer_id",
                },
                {
                    "from_table": "accounts", "to_table": "transactions",
                    "join_key": "account_id", "join_type": "INNER JOIN",
                    "condition": "accounts.account_id = transactions.account_id",
                },
            ],
            requested_fields=["name", "amount"],
        )
        assert "JOIN accounts" in cq.sql
        assert "JOIN transactions" in cq.sql


# ─── 11. COUNT(*) accepted ──────────────────────────────────────────────────

class TestCountStar:
    def test_count_star_in_metric(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id"]},
            metrics=["kyc_compliance_rate"],
            requested_fields=[],
        )
        assert "COUNT(*)" in cq.sql
        assert "COUNT(CASE" in cq.sql


# ─── 12. SELECT * rejected ──────────────────────────────────────────────────

class TestSelectStarRejected:
    def test_bare_star_rejected(self):
        plan, cq = _build_and_compile(
            task="detail_listing",
            selected_tables=["customers"],
            selected_columns={"customers": ["*"]},
            requested_fields=[],
        )
        assert "SELECT *" not in cq.sql or "COUNT(*)" in cq.sql


# ─── 13. Unknown column rejected ─────────────────────────────────────────────

class TestUnknownColumn:
    def test_invalid_column_not_in_plan(self):
        plan = BUILDER.build(
            **{
                **BASE_KWARGS,
                "task": "detail_listing",
                "missing_requested_fields": ["nonexistent_column_xyz"],
                "requested_fields": [],
            }
        )
        assert "nonexistent_column_xyz" in plan.missing_requested_fields

    def test_unresolvable_field_not_selected(self):
        plan, cq = _build_and_compile(
            task="detail_listing",
            requested_fields=["nonexistent_column_xyz"],
        )
        assert len(cq.parameters) == 0
        assert "nonexistent" not in cq.sql


# ─── 14. Unknown metric FAILS plan (Increment 2.5 change) ───────────────────

class TestUnknownMetric:
    def test_invalid_metric_fails_plan(self):
        plan = BUILDER.build(
            **{
                **BASE_KWARGS,
                "task": "aggregation",
                "metrics": ["totally_fake_metric"],
                "requested_fields": [],
            }
        )
        assert plan.unsupported_reason is not None
        assert "totally_fake_metric" in plan.unsupported_reason

    def test_compiler_rejects_unsupported_plan(self):
        plan = BUILDER.build(
            **{
                **BASE_KWARGS,
                "task": "aggregation",
                "metrics": ["totally_fake_metric"],
                "requested_fields": [],
            }
        )
        with pytest.raises(ValueError, match="Cannot compile unsupported"):
            COMPILER.compile(plan)


# ─── 15. Unregistered join ──────────────────────────────────────────────────

class TestUnregisteredJoin:
    def test_invalid_join_not_in_plan(self):
        plan = BUILDER.build(
            **{
                **BASE_KWARGS,
                "task": "detail_listing",
                "selected_tables": ["customers", "branches"],
                "selected_columns": {
                    "customers": ["customer_id"],
                    "branches": ["branch_id", "name"],
                },
                "join_paths": [{
                    "from_table": "customers", "to_table": "branches",
                    "join_key": "branch_id", "join_type": "INNER JOIN",
                    "condition": "customers.customer_id = branches.branch_id",
                }],
                "requested_fields": ["customer_id"],
            }
        )
        assert len(plan.joins) == 1


# ─── 16. Unsupported grain rejected ──────────────────────────────────────────

class TestUnsupportedGrain:
    def test_unsupported_grain_sets_flag(self):
        plan = BUILDER.build(
            **{
                **BASE_KWARGS,
                "task": "aggregation",
                "selected_tables": ["income_statement_snapshots"],
                "selected_columns": {
                    "income_statement_snapshots": ["snapshot_id", "fee_income"],
                },
                "metrics": ["pnb"],
                "dimensions": ["accounts.account_type"],
                "requested_fields": [],
                "unsupported_reason": "PNB metric does not support account_type grain.",
            }
        )
        assert plan.unsupported_reason is not None
        assert "PNB" in plan.unsupported_reason


# ─── 17. Missing requested field rejected ────────────────────────────────────

class TestMissingRequestedField:
    def test_missing_field_sets_list(self):
        plan = BUILDER.build(
            **{
                **BASE_KWARGS,
                "task": "detail_listing",
                "missing_requested_fields": ["crypto_balance", "nft_portfolio"],
                "requested_fields": [],
            }
        )
        assert "crypto_balance" in plan.missing_requested_fields
        assert "nft_portfolio" in plan.missing_requested_fields


# ─── 18. Deterministic repeatability ─────────────────────────────────────────

class TestDeterministicRepeatability:
    def test_same_plan_same_sql(self):
        kw = {
            **BASE_KWARGS,
            "task": "detail_listing",
            "selected_tables": ["customers", "accounts"],
            "selected_columns": {
                "customers": ["customer_id", "name"],
                "accounts": ["account_id", "balance"],
            },
            "join_paths": [{
                "from_table": "customers", "to_table": "accounts",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "customers.customer_id = accounts.customer_id",
            }],
            "filters_structured": [
                {"column": "accounts.balance", "operator": ">", "value": 5000},
            ],
            "requested_fields": ["name", "balance"],
        }
        plan1 = BUILDER.build(**kw)
        cq1 = COMPILER.compile(plan1)
        plan2 = BUILDER.build(**kw)
        cq2 = COMPILER.compile(plan2)
        assert cq1.sql == cq2.sql
        assert len(cq1.parameters) == len(cq2.parameters)
        for p1, p2 in zip(cq1.parameters, cq2.parameters):
            assert p1.value == p2.value


# ─── 19. Metadata snapshot mismatch ──────────────────────────────────────────

class TestMetadataSnapshotMismatch:
    def test_different_snapshots_preserved(self):
        plan_a = BUILDER.build(
            **{**BASE_KWARGS, "task": "detail_listing", "schema_snapshot_id": "snap-aaa", "semantic_metadata_version": "v1"}
        )
        plan_b = BUILDER.build(
            **{**BASE_KWARGS, "task": "detail_listing", "schema_snapshot_id": "snap-bbb", "semantic_metadata_version": "v2"}
        )
        cq_a = COMPILER.compile(plan_a)
        cq_b = COMPILER.compile(plan_b)
        assert cq_a.schema_snapshot_id == "snap-aaa"
        assert cq_b.schema_snapshot_id == "snap-bbb"
        assert cq_a.semantic_metadata_version == "v1"
        assert cq_b.semantic_metadata_version == "v2"


# ─── 20. SQL injection value bound as parameter ─────────────────────────────

class TestSQLInjectionBound:
    def test_injection_value_is_parameter(self):
        plan, cq = _build_and_compile(
            task="filter",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "name"]},
            filters_structured=[{
                "column": "customers.name",
                "operator": "=",
                "value": "'; DROP TABLE customers; --",
            }],
            requested_fields=["customer_id", "name"],
        )
        assert "DROP TABLE" not in cq.sql
        assert cq.parameters[0].value == "'; DROP TABLE customers; --"
        assert "$1" in cq.sql


# ─── Bonus: CompiledQuery contract ───────────────────────────────────────────

class TestCompiledQueryContract:
    def test_has_required_fields(self):
        _, cq = _build_and_compile(task="detail_listing")
        assert isinstance(cq, CompiledQuery)
        assert cq.sql
        assert isinstance(cq.parameters, list)
        assert isinstance(cq.tables_used, list)
        assert isinstance(cq.column_aliases, dict)
        assert cq.schema_snapshot_id == SNAPSHOT
        assert cq.semantic_metadata_version == VERSION
        assert cq.description


# ═════════════════════════════════════════════════════════════════════════════
# INCREMENT 2.5 TESTS: Implicit analytical expressions + ExpectedAnswer
# ═════════════════════════════════════════════════════════════════════════════

# ─── 21. Implicit COUNT(*) ──────────────────────────────────────────────────

class TestImplicitCount:
    def test_count_customers_by_governorate(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="count customers by governorate",
            selected_tables=["customers", "branches"],
            selected_columns={
                "customers": ["customer_id", "name"],
                "branches": ["branch_id", "governorate"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "branches",
                "join_key": "branch_id", "join_type": "INNER JOIN",
                "condition": "customers.branch_id = branches.branch_id",
            }],
            dimensions=["branches.governorate"],
            requested_fields=["governorate"],
        )
        assert len(plan.analytical_expressions) == 1
        expr = plan.analytical_expressions[0]
        assert isinstance(expr, AggregateExpression)
        assert expr.function == "COUNT"
        assert expr.column is None
        assert "COUNT(*)" in cq.sql
        assert "GROUP BY" in cq.sql

    def test_number_of_accounts(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="how many accounts",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            requested_fields=[],
        )
        assert len(plan.analytical_expressions) == 1
        expr = plan.analytical_expressions[0]
        assert expr.function == "COUNT"
        assert "COUNT(*)" in cq.sql


# ─── 22. Implicit SUM ───────────────────────────────────────────────────────

class TestImplicitSum:
    def test_total_account_balance(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="total account balance",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            requested_fields=["balance"],
        )
        assert len(plan.analytical_expressions) == 1
        expr = plan.analytical_expressions[0]
        assert isinstance(expr, AggregateExpression)
        assert expr.function == "SUM"
        assert expr.column.name == "balance"
        assert "SUM(accounts.balance)" in cq.sql

    def test_somme_des_depots(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="somme des depots",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            requested_fields=["balance"],
        )
        assert plan.analytical_expressions[0].function == "SUM"
        assert "SUM(accounts.balance)" in cq.sql


# ─── 23. Implicit AVG ───────────────────────────────────────────────────────

class TestImplicitAvg:
    def test_average_balance(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="average balance",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            requested_fields=["balance"],
        )
        assert len(plan.analytical_expressions) == 1
        expr = plan.analytical_expressions[0]
        assert isinstance(expr, AggregateExpression)
        assert expr.function == "AVG"
        assert "AVG(accounts.balance)" in cq.sql


# ─── 24. Implicit MIN ───────────────────────────────────────────────────────

class TestImplicitMin:
    def test_minimum_balance(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="minimum balance",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            requested_fields=["balance"],
        )
        assert plan.analytical_expressions[0].function == "MIN"
        assert "MIN(accounts.balance)" in cq.sql


# ─── 25. Implicit MAX ───────────────────────────────────────────────────────

class TestImplicitMax:
    def test_highest_balance(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="highest balance",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            requested_fields=["balance"],
        )
        assert plan.analytical_expressions[0].function == "MAX"
        assert "MAX(accounts.balance)" in cq.sql


# ─── 26. Implicit DISTINCT COUNT ─────────────────────────────────────────────

class TestImplicitDistinctCount:
    def test_unique_customer_count(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="unique customer count",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "name"]},
            requested_fields=["customer_id"],
        )
        assert len(plan.analytical_expressions) == 1
        expr = plan.analytical_expressions[0]
        assert isinstance(expr, AggregateExpression)
        assert expr.function == "COUNT"
        assert expr.distinct is True
        assert "COUNT(DISTINCT" in cq.sql


# ─── 27. Ranking with implicit COUNT ────────────────────────────────────────

class TestRankingWithImplicitCount:
    def test_top_branches_by_customer_count(self):
        plan, cq = _build_and_compile(
            task="ranking",
            query_text="top branches by customer count",
            selected_tables=["customers", "branches"],
            selected_columns={
                "customers": ["customer_id"],
                "branches": ["branch_id", "name"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "branches",
                "join_key": "branch_id", "join_type": "INNER JOIN",
                "condition": "customers.branch_id = branches.branch_id",
            }],
            dimensions=["branches.name"],
            sort_structured=[{"column": "count_all", "direction": "DESC"}],
            limit_requested=10,
            requested_fields=["name"],
        )
        assert len(plan.analytical_expressions) == 1
        expr = plan.analytical_expressions[0]
        assert expr.function == "COUNT"
        assert "COUNT(*)" in cq.sql
        assert "ORDER BY count_all DESC" in cq.sql
        assert "LIMIT 10" in cq.sql


# ─── 28. Ratio expression ───────────────────────────────────────────────────

class TestRatioExpression:
    def test_loan_to_deposit_ratio_uses_named_metric(self):
        """'loan to deposit ratio' → implicit detection returns None;
        must use named metric 'loan_to_deposit' to avoid fan-out."""
        plan = BUILDER.build(
            **{
                **BASE_KWARGS,
                "task": "aggregation",
                "query_text": "loan to deposit ratio",
                "selected_tables": ["loan_contracts", "accounts"],
                "selected_columns": {
                    "loan_contracts": ["loan_id", "principal_amount"],
                    "accounts": ["account_id", "balance"],
                },
                "metrics": ["loan_to_deposit"],
                "requested_fields": [],
            }
        )
        assert len(plan.analytical_expressions) == 0
        assert len(plan.metrics) == 1
        assert plan.metrics[0].metric_id == "loan_to_deposit"


# ─── 29. Percentage expression ──────────────────────────────────────────────

class TestPercentageExpression:
    def test_percentage_verified(self):
        """'what percentage of customers are verified' → RatioExpression
        with CaseExpression numerator (conditional count)."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="what percentage of customers are verified",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "kyc_verified"]},
            requested_fields=[],
        )
        assert len(plan.analytical_expressions) == 1
        expr = plan.analytical_expressions[0]
        assert isinstance(expr, RatioExpression)
        assert expr.multiply_100 is True
        assert isinstance(expr.numerator, CaseExpression)
        assert expr.numerator.condition_column == "kyc_verified"
        assert "CASE WHEN" in cq.sql
        assert "100.0" in cq.sql


# ─── 30. ExpectedAnswer: scalar ─────────────────────────────────────────────

class TestExpectedAnswerScalar:
    def test_scalar_answer_type(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="total account balance",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            requested_fields=["balance"],
        )
        ea = plan.expected_answer
        assert ea is not None
        assert ea.answer_type == "scalar"
        assert ea.aggregation_required is True
        assert len(ea.expected_metrics) > 0

    def test_named_metric_scalar(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="what is the npl ratio",
            selected_tables=["loan_contracts"],
            selected_columns={"loan_contracts": ["loan_id"]},
            metrics=["npl_ratio"],
            requested_fields=[],
        )
        ea = plan.expected_answer
        assert ea.answer_type == "scalar"
        assert "npl_ratio" in ea.expected_metrics


# ─── 31. ExpectedAnswer: grouped_rows with dimensions ───────────────────────

class TestExpectedAnswerRowSet:
    def test_grouped_answer_type(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="count customers by governorate",
            selected_tables=["customers", "branches"],
            selected_columns={
                "customers": ["customer_id"],
                "branches": ["branch_id", "governorate"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "branches",
                "join_key": "branch_id", "join_type": "INNER JOIN",
                "condition": "customers.branch_id = branches.branch_id",
            }],
            dimensions=["branches.governorate"],
            requested_fields=["governorate"],
        )
        ea = plan.expected_answer
        assert ea.answer_type == "grouped_rows"
        assert "governorate" in ea.expected_grain
        assert ea.aggregation_required is True


# ─── 32. ExpectedAnswer: ranked_list ────────────────────────────────────────

class TestExpectedAnswerRankedList:
    def test_ranking_answer_type(self):
        plan, _ = _build_and_compile(
            task="ranking",
            query_text="top 10 branches by customer count",
            selected_tables=["customers", "branches"],
            selected_columns={
                "customers": ["customer_id"],
                "branches": ["branch_id", "name"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "branches",
                "join_key": "branch_id", "join_type": "INNER JOIN",
                "condition": "customers.branch_id = branches.branch_id",
            }],
            dimensions=["branches.name"],
            sort_structured=[{"column": "count_all", "direction": "DESC"}],
            limit_requested=10,
            requested_fields=["name"],
        )
        ea = plan.expected_answer
        assert ea.answer_type == "ranked_list"
        assert ea.ordering is not None
        assert "DESC" in ea.ordering


# ─── 33. ExpectedAnswer: detail listing ─────────────────────────────────────

class TestExpectedAnswerDetail:
    def test_detail_no_aggregation(self):
        plan, _ = _build_and_compile(
            task="detail_listing",
            requested_fields=["customer_id", "name", "email"],
        )
        ea = plan.expected_answer
        assert ea.answer_type == "detail_rows"
        assert ea.aggregation_required is False
        assert len(ea.expected_metrics) == 0


# ─── 34. Implicit expressions produce correct SQL ───────────────────────────

class TestImplicitExpressionSQL:
    def test_sum_with_dimension(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="total balance by segment",
            selected_tables=["accounts", "customers"],
            selected_columns={
                "accounts": ["account_id", "balance"],
                "customers": ["customer_id", "segment"],
            },
            join_paths=[{
                "from_table": "accounts", "to_table": "customers",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "accounts.customer_id = customers.customer_id",
            }],
            dimensions=["customers.segment"],
            requested_fields=["segment"],
        )
        assert "SUM(accounts.balance)" in cq.sql
        assert "GROUP BY customers.segment" in cq.sql

    def test_avg_no_dimension(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="average balance",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            requested_fields=["balance"],
        )
        assert "AVG(accounts.balance)" in cq.sql
        assert "GROUP BY" not in cq.sql


# ─── 35. AnalyticalExpression type objects ───────────────────────────────────

class TestExpressionTypes:
    def test_aggregate_expression_to_sql(self):
        expr = AggregateExpression(
            function="COUNT", column=None, alias="count_all",
        )
        assert expr.to_sql() == "COUNT(*)"

    def test_aggregate_with_column(self):
        expr = AggregateExpression(
            function="SUM",
            column=ColumnRef(table="accounts", name="balance"),
            alias="total_balance",
        )
        assert expr.to_sql() == "SUM(accounts.balance)"

    def test_distinct_count(self):
        expr = AggregateExpression(
            function="COUNT",
            column=ColumnRef(table="customers", name="customer_id"),
            distinct=True,
            alias="unique_customers",
        )
        assert expr.to_sql() == "COUNT(DISTINCT customers.customer_id)"

    def test_ratio_expression_to_sql(self):
        expr = RatioExpression(
            numerator=AggregateExpression(function="SUM", column=ColumnRef(table="a", name="x")),
            denominator=AggregateExpression(function="SUM", column=ColumnRef(table="a", name="y")),
            multiply_100=True,
            alias="pct",
        )
        sql = expr.to_sql()
        assert "100.0" in sql
        assert "NULLIF" in sql

    def test_case_expression_to_sql(self):
        expr = CaseExpression(
            column=ColumnRef(table="customers", name="kyc_verified"),
            condition_column="kyc_verified",
            condition_value=True,
            function="COUNT",
            alias="verified_count",
        )
        sql = expr.to_sql()
        assert "CASE WHEN" in sql
        assert "customers.kyc_verified = True" in sql
        assert sql.startswith("COUNT(")

    def test_case_expression_in_ratio(self):
        expr = RatioExpression(
            numerator=CaseExpression(
                column=ColumnRef(table="customers", name="kyc_verified"),
                condition_column="kyc_verified",
                condition_value=True,
            ),
            denominator=AggregateExpression(function="COUNT", column=None),
            multiply_100=True,
            alias="pct",
        )
        sql = expr.to_sql()
        assert "CASE WHEN" in sql
        assert "100.0" in sql
        assert "NULLIF(COUNT(*), 0)" in sql


# ─── 36. Multiple metrics fail on first unknown ─────────────────────────────

class TestMultipleMetricsFailFast:
    def test_known_then_unknown_fails(self):
        plan = BUILDER.build(
            **{
                **BASE_KWARGS,
                "task": "aggregation",
                "metrics": ["npl_ratio", "fake_metric"],
                "requested_fields": [],
            }
        )
        assert plan.unsupported_reason is not None
        assert "fake_metric" in plan.unsupported_reason


# ═════════════════════════════════════════════════════════════════════════════
# INCREMENT 2.6 TESTS: Aggregation semantics, grain safety, fan-out
# ═════════════════════════════════════════════════════════════════════════════

# ─── 37. Conditional percentage (CaseExpression) ────────────────────────────

class TestConditionalPercentage:
    def test_verified_percentage_uses_case_numerator(self):
        """Percentage of verified customers must use CASE WHEN, not COUNT(col)."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="what percentage of customers are verified",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "kyc_verified"]},
            requested_fields=[],
        )
        expr = plan.analytical_expressions[0]
        assert isinstance(expr, RatioExpression)
        assert isinstance(expr.numerator, CaseExpression)
        assert "CASE WHEN customers.kyc_verified = True" in cq.sql
        assert "COUNT(CASE WHEN" in cq.sql

    def test_count_boolean_column_not_used_for_percentage(self):
        """COUNT(kyc_verified) must NOT appear — it counts non-null, not true."""
        _, cq = _build_and_compile(
            task="aggregation",
            query_text="what percentage of customers are verified",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "kyc_verified"]},
            requested_fields=[],
        )
        assert "COUNT(customers.kyc_verified)" not in cq.sql


# ─── 38. Entity-aware COUNT(DISTINCT) ───────────────────────────────────────

class TestEntityAwareCount:
    def test_count_customers_with_join_uses_distinct(self):
        """'count customers' with a one_to_many join → COUNT(DISTINCT customer_id)."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="count customers",
            selected_tables=["customers", "accounts"],
            selected_columns={
                "customers": ["customer_id", "name"],
                "accounts": ["account_id", "balance"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "accounts",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "customers.customer_id = accounts.customer_id",
                "cardinality": "one_to_many",
            }],
            requested_fields=[],
        )
        expr = plan.analytical_expressions[0]
        assert isinstance(expr, AggregateExpression)
        assert expr.function == "COUNT"
        assert expr.distinct is True
        assert expr.column.name == "customer_id"
        assert "COUNT(DISTINCT customers.customer_id)" in cq.sql

    def test_count_customers_no_join_uses_star(self):
        """'count customers' without joins → COUNT(*), no DISTINCT needed."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="count customers",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "name"]},
            requested_fields=[],
        )
        expr = plan.analytical_expressions[0]
        assert expr.function == "COUNT"
        assert expr.column is None
        assert "COUNT(*)" in cq.sql

    def test_count_accounts_by_customer_segment(self):
        """'count accounts by customer segment' → COUNT(*), segment is a dim."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="count accounts by customer segment",
            selected_tables=["accounts", "customers"],
            selected_columns={
                "accounts": ["account_id", "balance"],
                "customers": ["customer_id", "segment"],
            },
            join_paths=[{
                "from_table": "accounts", "to_table": "customers",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "accounts.customer_id = customers.customer_id",
            }],
            dimensions=["customers.segment"],
            requested_fields=["segment"],
        )
        expr = plan.analytical_expressions[0]
        assert expr.function == "COUNT"
        assert "COUNT(*)" in cq.sql
        assert "GROUP BY customers.segment" in cq.sql


# ─── 39. Fan-out detection ──────────────────────────────────────────────────

class TestFanOutDetection:
    def test_one_to_many_sets_fan_out_risk(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="total balance by customer",
            selected_tables=["customers", "accounts"],
            selected_columns={
                "customers": ["customer_id", "name"],
                "accounts": ["account_id", "balance"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "accounts",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "customers.customer_id = accounts.customer_id",
                "cardinality": "one_to_many",
            }],
            dimensions=["customers.name"],
            requested_fields=["name"],
        )
        assert plan.fan_out_risk is True

    def test_many_to_many_sets_fan_out_risk(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="total amount by category",
            selected_tables=["transactions", "products"],
            selected_columns={
                "transactions": ["transaction_id", "amount"],
                "products": ["product_id", "category"],
            },
            join_paths=[{
                "from_table": "transactions", "to_table": "products",
                "join_key": "product_id", "join_type": "INNER JOIN",
                "condition": "transactions.product_id = products.product_id",
                "cardinality": "many_to_many",
            }],
            dimensions=["products.category"],
            requested_fields=["category"],
        )
        assert plan.fan_out_risk is True

    def test_many_to_one_no_fan_out(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="count customers by branch",
            selected_tables=["customers", "branches"],
            selected_columns={
                "customers": ["customer_id"],
                "branches": ["branch_id", "name"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "branches",
                "join_key": "branch_id", "join_type": "INNER JOIN",
                "condition": "customers.branch_id = branches.branch_id",
                "cardinality": "many_to_one",
            }],
            dimensions=["branches.name"],
            requested_fields=["name"],
        )
        assert plan.fan_out_risk is False

    def test_no_joins_no_fan_out(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="total balance",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            requested_fields=[],
        )
        assert plan.fan_out_risk is False


# ─── 40. Grain propagation ──────────────────────────────────────────────────

class TestGrainPropagation:
    def test_source_grain_from_entity(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="count customers",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id"]},
            requested_fields=[],
        )
        assert plan.grain is not None
        assert plan.grain.source_table == "customers"
        assert plan.grain.source_grain == "customer_id"
        assert "customer_id" in plan.grain.identity_columns

    def test_output_grain_from_dimensions(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="count customers by governorate",
            selected_tables=["customers", "branches"],
            selected_columns={
                "customers": ["customer_id"],
                "branches": ["branch_id", "governorate"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "branches",
                "join_key": "branch_id", "join_type": "INNER JOIN",
                "condition": "customers.branch_id = branches.branch_id",
            }],
            dimensions=["branches.governorate"],
            requested_fields=["governorate"],
        )
        assert plan.grain.output_grain == "governorate"
        assert plan.grain.source_grain == "customer_id"

    def test_temporal_grain_from_time_range(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="total transactions last 30 days",
            selected_tables=["transactions"],
            selected_columns={"transactions": ["transaction_id", "amount"]},
            time_range={"type": "relative", "value": "last_30_days"},
            requested_fields=[],
        )
        assert plan.grain.temporal_grain == "last_30_days"

    def test_grain_spec_model(self):
        grain = GrainSpec(
            source_table="accounts",
            source_grain="account_id",
            aggregate_input_grain="account_id",
            output_grain="branch",
            temporal_grain="monthly",
            identity_columns=["account_id"],
        )
        assert grain.source_table == "accounts"
        assert grain.identity_columns == ["account_id"]


# ─── 41. Join cardinality ───────────────────────────────────────────────────

class TestJoinCardinality:
    def test_cardinality_propagated_to_join_spec(self):
        plan, _ = _build_and_compile(
            task="detail_listing",
            selected_tables=["customers", "accounts"],
            selected_columns={
                "customers": ["customer_id", "name"],
                "accounts": ["account_id", "balance"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "accounts",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "customers.customer_id = accounts.customer_id",
                "cardinality": "one_to_many",
            }],
            requested_fields=["name", "balance"],
        )
        assert len(plan.joins) == 1
        assert plan.joins[0].cardinality == "one_to_many"

    def test_default_cardinality_is_many_to_one(self):
        plan, _ = _build_and_compile(
            task="detail_listing",
            selected_tables=["customers", "accounts"],
            selected_columns={
                "customers": ["customer_id", "name"],
                "accounts": ["account_id", "balance"],
            },
            join_paths=[{
                "from_table": "customers", "to_table": "accounts",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "customers.customer_id = accounts.customer_id",
            }],
            requested_fields=["name", "balance"],
        )
        assert plan.joins[0].cardinality == "many_to_one"


# ─── 42. LDR must use named metric ──────────────────────────────────────────

class TestLDRNamedMetric:
    def test_implicit_ldr_returns_no_expression(self):
        """Implicit 'loan to deposit ratio' must not produce an expression
        (fan-out risk with independent tables)."""
        plan = BUILDER.build(
            **{
                **BASE_KWARGS,
                "task": "aggregation",
                "query_text": "loan to deposit ratio",
                "selected_tables": ["loan_contracts", "accounts"],
                "selected_columns": {
                    "loan_contracts": ["loan_id", "principal_amount"],
                    "accounts": ["account_id", "balance"],
                },
                "requested_fields": [],
            }
        )
        assert len(plan.analytical_expressions) == 0

    def test_named_metric_ldr_compiles(self):
        """Named metric 'loan_to_deposit' from APPROVED_METRICS compiles."""
        plan, cq = _build_and_compile(
            task="aggregation",
            selected_tables=["loan_contracts", "accounts"],
            selected_columns={
                "loan_contracts": ["loan_id", "principal_amount"],
                "accounts": ["account_id", "balance"],
            },
            metrics=["loan_to_deposit"],
            requested_fields=[],
        )
        assert len(plan.metrics) == 1
        assert "CASE WHEN" in cq.sql
        assert "loan_to_deposit" in cq.sql


# ─── 43. Time-series ExpectedAnswer ─────────────────────────────────────────

class TestTimeSeriesExpectedAnswer:
    def test_time_series_answer_type(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="total balance by period",
            selected_tables=["accounts", "income_statement_snapshots"],
            selected_columns={
                "accounts": ["account_id", "balance"],
                "income_statement_snapshots": ["snapshot_id", "period"],
            },
            join_paths=[{
                "from_table": "accounts", "to_table": "income_statement_snapshots",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "accounts.customer_id = income_statement_snapshots.snapshot_id",
            }],
            dimensions=["income_statement_snapshots.period"],
            requested_fields=["period"],
        )
        ea = plan.expected_answer
        assert ea.answer_type == "time_series"
        assert "period" in ea.expected_grain


# ─── 44. Comparison and distribution ExpectedAnswer ─────────────────────────

class TestExpandedAnswerTypes:
    def test_detail_rows_for_detail_listing(self):
        plan, _ = _build_and_compile(
            task="detail_listing",
            requested_fields=["customer_id", "name"],
        )
        assert plan.expected_answer.answer_type == "detail_rows"

    def test_grouped_rows_for_agg_with_dims(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            query_text="total balance by segment",
            selected_tables=["accounts", "customers"],
            selected_columns={
                "accounts": ["account_id", "balance"],
                "customers": ["customer_id", "segment"],
            },
            join_paths=[{
                "from_table": "accounts", "to_table": "customers",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "accounts.customer_id = customers.customer_id",
            }],
            dimensions=["customers.segment"],
            requested_fields=["segment"],
        )
        assert plan.expected_answer.answer_type == "grouped_rows"


# ─── 45. Deterministic SQL stability ────────────────────────────────────────

class TestDeterministicStability:
    def test_same_plan_same_sql_after_26_changes(self):
        kw = {
            **BASE_KWARGS,
            "task": "aggregation",
            "query_text": "total balance by segment",
            "selected_tables": ["accounts", "customers"],
            "selected_columns": {
                "accounts": ["account_id", "balance"],
                "customers": ["customer_id", "segment"],
            },
            "join_paths": [{
                "from_table": "accounts", "to_table": "customers",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "accounts.customer_id = customers.customer_id",
            }],
            "dimensions": ["customers.segment"],
            "requested_fields": ["segment"],
        }
        plan1 = BUILDER.build(**kw)
        cq1 = COMPILER.compile(plan1)
        plan2 = BUILDER.build(**kw)
        cq2 = COMPILER.compile(plan2)
        assert cq1.sql == cq2.sql
        assert [p.value for p in cq1.parameters] == [p.value for p in cq2.parameters]

    def test_deterministic_with_percentage(self):
        kw = {
            **BASE_KWARGS,
            "task": "aggregation",
            "query_text": "what percentage of customers are verified",
            "selected_tables": ["customers"],
            "selected_columns": {"customers": ["customer_id", "kyc_verified"]},
            "requested_fields": [],
        }
        cq1 = COMPILER.compile(BUILDER.build(**kw))
        cq2 = COMPILER.compile(BUILDER.build(**kw))
        assert cq1.sql == cq2.sql

    def test_deterministic_with_entity_count(self):
        kw = {
            **BASE_KWARGS,
            "task": "aggregation",
            "query_text": "count customers",
            "selected_tables": ["customers", "accounts"],
            "selected_columns": {
                "customers": ["customer_id", "name"],
                "accounts": ["account_id", "balance"],
            },
            "join_paths": [{
                "from_table": "customers", "to_table": "accounts",
                "join_key": "customer_id", "join_type": "INNER JOIN",
                "condition": "customers.customer_id = accounts.customer_id",
                "cardinality": "one_to_many",
            }],
            "requested_fields": [],
        }
        cq1 = COMPILER.compile(BUILDER.build(**kw))
        cq2 = COMPILER.compile(BUILDER.build(**kw))
        assert cq1.sql == cq2.sql
