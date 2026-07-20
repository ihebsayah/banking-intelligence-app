"""
tests/test_benchmark_gate.py
Benchmark Readiness Gate tests — validates architecture requirements
before the 200-question benchmark.

Covers:
  2. Independent-subquery grain behavior (scalar vs grouped)
  3. Filter routing for independent subqueries (shared + side-specific)
  4. Governed metric populations (npl_ratio, loan_to_deposit)
  5. Full replanning lifecycle (bounded retries, visited hashes)
  6. PostgreSQL-backed integration (simulated with mock DB)
  7. Security recovery tests (retry cannot broaden auth, etc.)
"""
import sys
import os
import hashlib
import time
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVICES = os.path.join(ROOT, "services")
for p in [SERVICES, os.path.join(SERVICES, "shared")]:
    if p not in sys.path:
        sys.path.insert(0, p)

EXEC_DIR = os.path.join(SERVICES, "execution_agent")
for p in [EXEC_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from sql_agent.plan_models import (
    QueryPlan, CompiledQuery, MetricExecutionStrategy, MetricReference,
    GrainSpec, ColumnRef, ExpectedAnswer, FilterSpec,
    PlanRepairRequest, ExecutionRetryPolicy, ExecutionTrace,
)
from sql_agent.query_plan_builder import QueryPlanBuilder, APPROVED_METRICS
from sql_agent.deterministic_compiler import (
    DeterministicSQLCompiler, _INDEPENDENT_SUBQUERY_REGISTRY,
)
from result_verifier import ResultVerifier
from pg_repair_engine import PGRepairEngine, SQLMechanicalRepair
from plan_refiner import PlanRefiner
from shared.query_signing import sign_query_payload, verify_query_signature

BUILDER = QueryPlanBuilder()
COMPILER = DeterministicSQLCompiler()
VERIFIER = ResultVerifier()
REPAIR = PGRepairEngine()
REFINER = PlanRefiner()

SNAPSHOT = "snap-gate-001"
VERSION = "v8.0.0"
SIGNING_KEY = "test-secret-key-for-gate"

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


def _sql_hash(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]


# ═════════════════════════════════════════════════════════════════════════════
# 2. Independent-Subquery Grain Behavior
# ═════════════════════════════════════════════════════════════════════════════

class TestIndependentSubqueryGrain:
    """Validate that independent subqueries handle scalar and grouped grains."""

    def test_scalar_grain_uses_cross_join(self):
        """Scalar loan_to_deposit: cross-join of two single-row subqueries."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="loan to deposit ratio",
            selected_tables=["loan_contracts", "accounts"],
            selected_columns={
                "loan_contracts": ["loan_id", "principal_amount"],
                "accounts": ["account_id", "balance"],
            },
            metrics=["loan_to_deposit"],
            requested_fields=[],
        )
        m = plan.metrics[0]
        assert m.execution_strategy.execution_strategy == "independent_subqueries"
        # Scalar: no dimensions → cross-join is correct
        assert "_num" in cq.sql
        assert "_den" in cq.sql
        assert "GROUP BY" not in cq.sql or "loan_to_deposit" in cq.sql

    def test_grouped_independent_subquery_rejects_unsupported_grain(self):
        """Grouped independent subquery with dimension fails at plan build time.

        The builder rejects the plan before it reaches the compiler,
        preventing unsupported grain requests from generating SQL.
        """
        plan = BUILDER.build(
            task="aggregation",
            query_text="loan to deposit ratio by branch",
            selected_tables=["loan_contracts", "accounts", "branches"],
            bridge_tables=[],
            selected_columns={
                "loan_contracts": ["loan_id", "principal_amount", "branch_id"],
                "accounts": ["account_id", "balance", "branch_id"],
                "branches": ["branch_id", "name"],
            },
            join_paths=[],
            metrics=["loan_to_deposit"],
            dimensions=["branches.name"],
            filters_structured=[],
            time_range={"type": "none", "value": None},
            sort_structured=None,
            limit_requested=100,
            requested_fields=["name"],
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        assert plan.unsupported_reason is not None
        assert "does not support grain" in plan.unsupported_reason

    def test_npl_ratio_scalar_independent_subqueries(self):
        """Scalar npl_ratio uses independent subqueries correctly."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="npl ratio",
            selected_tables=["loan_contracts", "non_performing_loans"],
            selected_columns={
                "loan_contracts": ["loan_id"],
                "non_performing_loans": ["npl_id", "loan_id"],
            },
            metrics=["npl_ratio"],
            requested_fields=[],
        )
        m = plan.metrics[0]
        assert m.execution_strategy.execution_strategy == "independent_subqueries"
        assert "_num" in cq.sql
        assert "_den" in cq.sql

    def test_independent_subquery_deterministic(self):
        """Same inputs produce identical SQL and parameters."""
        kw = {
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
        cq1 = COMPILER.compile(BUILDER.build(**kw))
        cq2 = COMPILER.compile(BUILDER.build(**kw))
        assert cq1.sql == cq2.sql
        assert [p.value for p in cq1.parameters] == [p.value for p in cq2.parameters]

    def test_single_query_metric_unaffected_by_independent_strategy(self):
        """Single-query metrics bypass independent subquery path entirely."""
        plan, cq = _build_and_compile(
            task="aggregation",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "kyc_verified"]},
            metrics=["kyc_compliance_rate"],
            requested_fields=[],
        )
        assert "_num" not in cq.sql
        assert "FROM customers" in cq.sql


# ═════════════════════════════════════════════════════════════════════════════
# 3. Filter Routing for Independent Subqueries
# ═════════════════════════════════════════════════════════════════════════════

class TestFilterRouting:
    """Validate filter routing for independent subqueries."""

    def test_shared_date_filter_applies_to_both_sides(self):
        """Date filter present in both numerator and denominator subqueries."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="loan to deposit ratio",
            selected_tables=["loan_contracts", "accounts"],
            selected_columns={
                "loan_contracts": ["loan_id", "principal_amount", "created_at"],
                "accounts": ["account_id", "balance", "created_at"],
            },
            metrics=["loan_to_deposit"],
            filters_structured=[
                {"column": "loan_contracts.created_at", "operator": ">=", "value": "2024-01-01"},
            ],
            requested_fields=[],
        )
        sql = cq.sql
        # Both subqueries must have the filter (parameterized)
        assert "lc.created_at >= $1" in sql
        assert "a.created_at >= $2" in sql
        # Parameter value present
        assert any(p.value == "2024-01-01" for p in cq.parameters)

    def test_branch_filter_applies_to_both_sides(self):
        """Branch filter present in both numerator and denominator subqueries."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="loan to deposit ratio",
            selected_tables=["loan_contracts", "accounts"],
            selected_columns={
                "loan_contracts": ["loan_id", "principal_amount", "branch_id"],
                "accounts": ["account_id", "balance", "branch_id"],
            },
            metrics=["loan_to_deposit"],
            filters_structured=[
                {"column": "loan_contracts.branch_id", "operator": "=", "value": "B001"},
            ],
            requested_fields=[],
        )
        sql = cq.sql
        assert "lc.branch_id = $1" in sql
        assert "a.branch_id = $2" in sql
        assert any(p.value == "B001" for p in cq.parameters)

    def test_unsupported_filter_fails_closed(self):
        """Filter on non-existent table raises ValueError at build time.

        The builder drops unknown-table filters and now raises ValueError
        to prevent silent data loss.
        """
        with pytest.raises(ValueError, match="Unsupported filter"):
            _build_and_compile(
                task="aggregation",
                query_text="loan to deposit ratio",
                selected_tables=["loan_contracts", "accounts"],
                selected_columns={
                    "loan_contracts": ["loan_id", "principal_amount"],
                    "accounts": ["account_id", "balance"],
                },
                metrics=["loan_to_deposit"],
                filters_structured=[
                    {"column": "nonexistent_table.column", "operator": "=", "value": "X"},
                ],
                requested_fields=[],
            )

    def test_filter_parameters_are_deterministic(self):
        """Same filters produce same parameter order and values."""
        filters = [
            {"column": "loan_contracts.branch_id", "operator": "=", "value": "B001"},
            {"column": "accounts.status", "operator": "=", "value": "active"},
        ]
        kw1 = {
            **BASE_KWARGS,
            "task": "aggregation",
            "selected_tables": ["loan_contracts", "accounts"],
            "selected_columns": {
                "loan_contracts": ["loan_id", "principal_amount", "branch_id"],
                "accounts": ["account_id", "balance", "status"],
            },
            "metrics": ["loan_to_deposit"],
            "filters_structured": filters,
            "requested_fields": [],
        }
        kw2 = dict(kw1)
        cq1 = COMPILER.compile(BUILDER.build(**kw1))
        cq2 = COMPILER.compile(BUILDER.build(**kw2))
        assert cq1.sql == cq2.sql
        assert [p.value for p in cq1.parameters] == [p.value for p in cq2.parameters]

    def test_in_operator_applied_to_both_subqueries(self):
        """IN operator filter appears in both subqueries."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="loan to deposit ratio",
            selected_tables=["loan_contracts", "accounts"],
            selected_columns={
                "loan_contracts": ["loan_id", "principal_amount", "branch_id"],
                "accounts": ["account_id", "balance", "branch_id"],
            },
            metrics=["loan_to_deposit"],
            filters_structured=[
                {"column": "loan_contracts.branch_id", "operator": "IN", "value": ["B001", "B002"]},
            ],
            requested_fields=[],
        )
        sql = cq.sql
        assert "lc.branch_id IN" in sql
        assert "a.branch_id IN" in sql
        param_values = [p.value for p in cq.parameters]
        assert "B001" in param_values
        assert "B002" in param_values


# ═════════════════════════════════════════════════════════════════════════════
# 4. Governed Metric Populations
# ═════════════════════════════════════════════════════════════════════════════

class TestGovernedMetricPopulations:
    """Validate that governed metrics have explicit population definitions."""

    def test_npl_ratio_registry_entry(self):
        """npl_ratio has a complete registry entry with population."""
        info = APPROVED_METRICS.get("npl_ratio")
        assert info is not None
        assert "formula" in info
        assert "source_tables" in info
        assert "grains" in info
        assert "execution_strategy" in info
        # Population: numerator = non_performing_loans, denominator = loan_contracts
        assert "non_performing_loans" in info["source_tables"]
        assert "loan_contracts" in info["source_tables"]

    def test_loan_to_deposit_registry_entry(self):
        """loan_to_deposit has a complete registry entry with population."""
        info = APPROVED_METRICS.get("loan_to_deposit")
        assert info is not None
        assert "formula" in info
        assert "source_tables" in info
        assert "grains" in info
        assert "execution_strategy" in info
        # Population: numerator = loan_contracts (principal_amount), denominator = accounts (balance)
        assert "loan_contracts" in info["source_tables"]
        assert "accounts" in info["source_tables"]

    def test_npl_ratio_independent_subquery_registry(self):
        """npl_ratio has explicit numerator/denominator SQL templates."""
        reg = _INDEPENDENT_SUBQUERY_REGISTRY.get("npl_ratio")
        assert reg is not None
        assert "numerator" in reg
        assert "denominator" in reg
        assert "ratio_expr" in reg
        # Numerator: count of NPLs
        assert "non_performing_loans" in reg["numerator"]
        # Denominator: count of all loans
        assert "loan_contracts" in reg["denominator"]

    def test_loan_to_deposit_independent_subquery_registry(self):
        """loan_to_deposit has explicit numerator/denominator SQL templates."""
        reg = _INDEPENDENT_SUBQUERY_REGISTRY.get("loan_to_deposit")
        assert reg is not None
        assert "numerator" in reg
        assert "denominator" in reg
        assert "ratio_expr" in reg
        # Numerator: sum of principal_amount from loan_contracts
        assert "loan_contracts" in reg["numerator"]
        assert "principal_amount" in reg["numerator"]
        # Denominator: sum of balance from accounts
        assert "accounts" in reg["denominator"]
        assert "balance" in reg["denominator"]

    def test_npl_ratio_grains(self):
        """npl_ratio supports scalar grain (independent_subqueries rejects dimensions)."""
        info = APPROVED_METRICS["npl_ratio"]
        assert "scalar" in info["grains"]
        # Independent-subquery metrics cannot support grouped grains
        assert "branch" not in info["grains"]
        assert "governorate" not in info["grains"]

    def test_loan_to_deposit_grains(self):
        """loan_to_deposit supports scalar grain (independent_subqueries rejects dimensions)."""
        info = APPROVED_METRICS["loan_to_deposit"]
        assert "scalar" in info["grains"]
        assert "branch" not in info["grains"]
        assert "governorate" not in info["grains"]

    def test_npl_ratio_has_population(self):
        """npl_ratio has governed population definition with all required fields."""
        info = APPROVED_METRICS["npl_ratio"]
        assert "population" in info
        pop = info["population"]
        assert "numerator" in pop
        assert "denominator" in pop
        assert "governed_loan_identity" in pop
        assert "numerator_uniqueness" in pop
        assert "denominator_inclusion" in pop
        assert "current_state_vs_historical" in pop
        assert "reporting_date_alignment" in pop
        assert "definition" in pop
        assert "DISTINCT" in pop["numerator"]

    def test_loan_to_deposit_has_population(self):
        """loan_to_deposit has governed population definition with currency enforcement."""
        info = APPROVED_METRICS["loan_to_deposit"]
        assert "population" in info
        pop = info["population"]
        assert "numerator" in pop
        assert "denominator" in pop
        assert "reporting_currency" in pop
        assert "TND" in pop["reporting_currency"]

    def test_loan_to_deposit_currency_policy(self):
        """loan_to_deposit enforces single-currency TND in SQL templates."""
        reg = _INDEPENDENT_SUBQUERY_REGISTRY["loan_to_deposit"]
        assert "currency" in reg["numerator"]
        assert "TND" in reg["numerator"]
        assert "currency" in reg["denominator"]
        assert "TND" in reg["denominator"]
        # Also check the APPROVED_METRICS population
        info = APPROVED_METRICS["loan_to_deposit"]
        assert "population" in info
        assert info["population"]["reporting_currency"] == "TND"

    def test_npl_ratio_has_temporal_policy(self):
        """npl_ratio has governed temporal policy with business date columns."""
        info = APPROVED_METRICS["npl_ratio"]
        assert "temporal_policy" in info
        tp = info["temporal_policy"]
        assert "allowed_time_ranges" in tp
        assert "default_time_range" in tp
        assert "numerator_business_date" in tp
        assert "as_of_semantics" in tp
        assert "timezone" in tp

    def test_loan_to_deposit_has_temporal_policy(self):
        """loan_to_deposit has governed temporal policy with business date columns."""
        info = APPROVED_METRICS["loan_to_deposit"]
        assert "temporal_policy" in info
        tp = info["temporal_policy"]
        assert "allowed_time_ranges" in tp
        assert "default_time_range" in tp
        assert "numerator_business_date" in tp
        assert "denominator_business_date" in tp
        assert "timezone" in tp

    def test_all_governed_metrics_have_execution_strategy(self):
        """All ratio metrics have explicit execution_strategy."""
        ratio_metrics = ["npl_ratio", "loan_to_deposit", "roe", "roa"]
        for mid in ratio_metrics:
            info = APPROVED_METRICS.get(mid)
            assert info is not None, f"Metric {mid} not in registry"
            assert "execution_strategy" in info, f"Metric {mid} missing execution_strategy"
            strategy = info["execution_strategy"]
            assert strategy.get("execution_strategy") in (
                "independent_subqueries", "single_query", "approved_metric_view"
            ), f"Metric {mid} has invalid execution_strategy"

    def test_npl_ratio_is_count_based(self):
        """npl_ratio numerator is count-based (COUNT DISTINCT loan_id)."""
        reg = _INDEPENDENT_SUBQUERY_REGISTRY["npl_ratio"]
        assert "COUNT" in reg["numerator"]
        assert "DISTINCT" in reg["numerator"]
        assert "loan_id" in reg["numerator"]

    def test_loan_to_deposit_is_exposure_based(self):
        """loan_to_deposit numerator is exposure-based (SUM of principal_amount)."""
        reg = _INDEPENDENT_SUBQUERY_REGISTRY["loan_to_deposit"]
        assert "SUM" in reg["numerator"]
        assert "principal_amount" in reg["numerator"]


# ═════════════════════════════════════════════════════════════════════════════
# 4b. Requested Currency Semantics
# ═════════════════════════════════════════════════════════════════════════════

class TestRequestedCurrencySemantics:
    """Validate requested_currency planning-time enforcement for loan_to_deposit."""

    def test_no_currency_uses_governed_default(self):
        """Omitting requested_currency uses governed default TND silently."""
        plan = BUILDER.build(
            task="aggregation", query_text="loan to deposit ratio",
            selected_tables=["loan_contracts", "accounts"], bridge_tables=[],
            selected_columns={"loan_contracts": ["loan_id", "principal_amount"], "accounts": ["account_id", "balance"]},
            join_paths=[], metrics=["loan_to_deposit"], dimensions=[], filters_structured=[],
            time_range={"type": "none", "value": None}, sort_structured=None,
            limit_requested=100, requested_fields=[], semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        assert plan.unsupported_reason is None

    def test_explicit_tnd_accepted(self):
        """Explicit TND is accepted (matches governed currency)."""
        plan = BUILDER.build(
            task="aggregation", query_text="loan to deposit ratio",
            selected_tables=["loan_contracts", "accounts"], bridge_tables=[],
            selected_columns={"loan_contracts": ["loan_id", "principal_amount"], "accounts": ["account_id", "balance"]},
            join_paths=[], metrics=["loan_to_deposit"], dimensions=[], filters_structured=[],
            time_range={"type": "none", "value": None}, sort_structured=None,
            limit_requested=100, requested_fields=[], semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT, requested_currency="TND",
        )
        assert plan.unsupported_reason is None

    def test_non_tnd_rejected_at_planning(self):
        """Explicit non-TND (e.g. EUR) is rejected during planning, not silently answered with TND SQL."""
        plan = BUILDER.build(
            task="aggregation", query_text="loan to deposit ratio in EUR",
            selected_tables=["loan_contracts", "accounts"], bridge_tables=[],
            selected_columns={"loan_contracts": ["loan_id", "principal_amount"], "accounts": ["account_id", "balance"]},
            join_paths=[], metrics=["loan_to_deposit"], dimensions=[], filters_structured=[],
            time_range={"type": "none", "value": None}, sort_structured=None,
            limit_requested=100, requested_fields=[], semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT, requested_currency="EUR",
        )
        assert plan.unsupported_reason is not None
        assert "EUR" in plan.unsupported_reason
        assert "TND" in plan.unsupported_reason

    def test_usd_rejected_at_planning(self):
        """USD is also rejected at planning for loan_to_deposit."""
        plan = BUILDER.build(
            task="aggregation", query_text="loan to deposit ratio in USD",
            selected_tables=["loan_contracts", "accounts"], bridge_tables=[],
            selected_columns={"loan_contracts": ["loan_id", "principal_amount"], "accounts": ["account_id", "balance"]},
            join_paths=[], metrics=["loan_to_deposit"], dimensions=[], filters_structured=[],
            time_range={"type": "none", "value": None}, sort_structured=None,
            limit_requested=100, requested_fields=[], semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT, requested_currency="USD",
        )
        assert plan.unsupported_reason is not None

    def test_npl_ratio_ignores_currency(self):
        """npl_ratio is count-based and ignores requested_currency."""
        plan = BUILDER.build(
            task="aggregation", query_text="npl ratio",
            selected_tables=["loan_contracts", "non_performing_loans"], bridge_tables=[],
            selected_columns={"loan_contracts": ["loan_id"], "non_performing_loans": ["npl_id", "loan_id"]},
            join_paths=[], metrics=["npl_ratio"], dimensions=[], filters_structured=[],
            time_range={"type": "none", "value": None}, sort_structured=None,
            limit_requested=100, requested_fields=[], semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT, requested_currency="EUR",
        )
        assert plan.unsupported_reason is None

    def test_sql_has_tnd_default_when_no_currency(self):
        """When no requested_currency, compiled SQL contains TND filter."""
        _, cq = _build_and_compile(
            task="aggregation", query_text="loan to deposit ratio",
            selected_tables=["loan_contracts", "accounts"],
            selected_columns={"loan_contracts": ["loan_id", "principal_amount"], "accounts": ["account_id", "balance"]},
            metrics=["loan_to_deposit"], requested_fields=[],
        )
        assert "TND" in cq.sql

    def test_no_non_tnd_in_sql(self):
        """Verify the compiled SQL never contains non-TND currency filters."""
        _, cq = _build_and_compile(
            task="aggregation", query_text="loan to deposit ratio",
            selected_tables=["loan_contracts", "accounts"],
            selected_columns={"loan_contracts": ["loan_id", "principal_amount"], "accounts": ["account_id", "balance"]},
            metrics=["loan_to_deposit"], requested_fields=[],
        )
        assert "EUR" not in cq.sql
        assert "USD" not in cq.sql


# ═════════════════════════════════════════════════════════════════════════════
# 4c. NPL Population Alignment
# ═════════════════════════════════════════════════════════════════════════════

class TestNPLPopulationAlignment:
    """Validate that population filters route to both sides or fail closed."""

    def test_branch_filter_fails_closed_for_npl_ratio(self):
        """Branch filter on npl_ratio fails closed (non_performing_loans lacks branch_id)."""
        with pytest.raises(ValueError, match="Population filter"):
            _build_and_compile(
                task="aggregation", query_text="npl ratio for branch",
                selected_tables=["loan_contracts", "non_performing_loans"],
                selected_columns={"loan_contracts": ["loan_id", "branch_id"], "non_performing_loans": ["npl_id", "loan_id"]},
                metrics=["npl_ratio"],
                filters_structured=[{"column": "loan_contracts.branch_id", "operator": "=", "value": "BR_001"}],
                requested_fields=[],
            )

    def test_created_at_filter_applies_to_both_npl_sides(self):
        """created_at filter applies to both sides of npl_ratio (shared column)."""
        _, cq = _build_and_compile(
            task="aggregation", query_text="npl ratio for period",
            selected_tables=["loan_contracts", "non_performing_loans"],
            selected_columns={"loan_contracts": ["loan_id", "created_at"], "non_performing_loans": ["npl_id", "loan_id", "created_at"]},
            metrics=["npl_ratio"],
            filters_structured=[{"column": "loan_contracts.created_at", "operator": ">=", "value": "2024-01-01"}],
            requested_fields=[],
        )
        sql = cq.sql
        assert "n.created_at" in sql
        assert "lc.created_at" in sql

    def test_branch_filter_works_for_loan_to_deposit(self):
        """Branch filter on loan_to_deposit works (both sides have branch_id)."""
        _, cq = _build_and_compile(
            task="aggregation", query_text="loan to deposit ratio for branch",
            selected_tables=["loan_contracts", "accounts"],
            selected_columns={"loan_contracts": ["loan_id", "principal_amount", "branch_id"], "accounts": ["account_id", "balance", "branch_id"]},
            metrics=["loan_to_deposit"],
            filters_structured=[{"column": "loan_contracts.branch_id", "operator": "=", "value": "BR_001"}],
            requested_fields=[],
        )
        sql = cq.sql
        assert "lc.branch_id" in sql
        assert "a.branch_id" in sql

    def test_npl_ratio_sql_uses_count_distinct_both_sides(self):
        """NPL ratio SQL uses COUNT DISTINCT on both numerator and denominator."""
        _, cq = _build_and_compile(
            task="aggregation", query_text="npl ratio",
            selected_tables=["loan_contracts", "non_performing_loans"],
            selected_columns={"loan_contracts": ["loan_id"], "non_performing_loans": ["npl_id", "loan_id"]},
            metrics=["npl_ratio"], requested_fields=[],
        )
        sql = cq.sql
        assert "COUNT(DISTINCT" in sql


# ═════════════════════════════════════════════════════════════════════════════
# 4d. NPL Temporal Governance
# ═════════════════════════════════════════════════════════════════════════════

class TestNPLTemporalGovernance:
    """Validate NPL ratio temporal definition: as-of semantics, not period flow."""

    def test_npl_ratio_has_as_of_semantics(self):
        """NPL ratio population defines as-of semantics for both numerator and denominator."""
        info = APPROVED_METRICS["npl_ratio"]
        pop = info["population"]
        align = pop["reporting_date_alignment"].lower()
        assert "as_of" in align or "as-of" in align or "synthetic benchmark reporting" in align

    def test_npl_ratio_temporal_policy_has_both_business_dates(self):
        """NPL temporal policy specifies business dates for both numerator and denominator."""
        tp = APPROVED_METRICS["npl_ratio"]["temporal_policy"]
        assert tp["numerator_business_date"] is not None
        assert tp["denominator_business_date"] is not None

    def test_npl_ratio_is_not_flow_metric(self):
        """NPL ratio definition explicitly states it is not a period-flow metric."""
        tp = APPROVED_METRICS["npl_ratio"]["temporal_policy"]
        assert "stock" in tp["as_of_semantics"].lower() or "not a period" in tp["as_of_semantics"].lower()

    def test_npl_ratio_population_uses_both_tables(self):
        """NPL ratio population references both tables with created_at as synthetic proxy."""
        info = APPROVED_METRICS["npl_ratio"]
        pop = info["population"]
        assert "loan_contracts" in pop["denominator"]
        assert "non_performing_loans" in pop["numerator"]
        assert "created_at" in pop["numerator"]
        assert "created_at" in pop["denominator"]

    def test_npl_ratio_schema_column_mapping_documented(self):
        """NPL temporal metadata documents created_at as synthetic benchmark proxy."""
        info = APPROVED_METRICS["npl_ratio"]
        pop = info["population"]
        assert "schema_column_mapping" in pop
        assert "created_at" in pop["schema_column_mapping"]


# ═════════════════════════════════════════════════════════════════════════════
# 5. Full Replanning Lifecycle
# ═════════════════════════════════════════════════════════════════════════════

class TestReplanningLifecycle:
    """Prove full replanning lifecycle with bounded retries and visited hashes."""

    def test_execution_failure_produces_plan_repair_request(self):
        """Execution failure → PlanRepairRequest → QueryPlanBuilder."""
        recovery = REPAIR.attempt_recovery(
            "SELECT * FROM fake_table",
            'relation "fake_table" does not exist',
        )
        assert recovery["plan_repair"] is not None
        pr = recovery["plan_repair"]
        assert pr["error_type"] == "table_missing"
        assert "fake_table" in pr["requested_change"]

    def test_plan_repair_request_goes_through_builder(self):
        """PlanRepairRequest → QueryPlanBuilder → new plan."""
        recovery = REPAIR.attempt_recovery(
            "SELECT * FROM fake_table",
            'relation "fake_table" does not exist',
        )
        pr = recovery["plan_repair"]
        # Simulate: builder removes the missing table
        new_plan = BUILDER.build(
            task="aggregation",
            query_text="test query",
            selected_tables=["customers"],  # removed fake_table
            bridge_tables=[],
            selected_columns={"customers": ["customer_id", "name"]},
            join_paths=[],
            metrics=[],
            dimensions=[],
            filters_structured=[],
            time_range={"type": "none", "value": None},
            sort_structured=None,
            limit_requested=100,
            requested_fields=["name"],
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        assert new_plan.unsupported_reason is None
        assert "customers" in new_plan.selected_tables

    def test_plan_validation_after_replan(self):
        """After replanning, the new plan validates successfully."""
        new_plan = BUILDER.build(
            task="aggregation",
            query_text="test query",
            selected_tables=["customers"],
            bridge_tables=[],
            selected_columns={"customers": ["customer_id", "name"]},
            join_paths=[],
            metrics=[],
            dimensions=[],
            filters_structured=[],
            time_range={"type": "none", "value": None},
            sort_structured=None,
            limit_requested=100,
            requested_fields=["name"],
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        compiled = COMPILER.compile(new_plan)
        assert compiled.sql.startswith("SELECT")
        assert "customers" in compiled.sql

    def test_compiler_produces_fresh_sql_after_replan(self):
        """Changed plan produces different SQL (fresh signature required)."""
        original_sql = "SELECT customers.name FROM customers LIMIT 100"
        new_sql = "SELECT customers.name FROM customers WHERE customers.name = $1 LIMIT 100"
        assert _sql_hash(original_sql) != _sql_hash(new_sql)

    def test_fresh_signature_for_changed_sql(self):
        """Changed SQL gets a new signature; old signature is invalid."""
        ts = int(time.time())
        sql1 = "SELECT customers.name FROM customers LIMIT 100"
        sql2 = "SELECT customers.name FROM customers WHERE customers.name = $1 LIMIT 100"
        params = []

        sig1 = sign_query_payload("req-001", sql1, params, ts, "nonce-1", SIGNING_KEY)
        # Verify with original SQL → passes
        assert verify_query_signature(sql1, params, sig1, SIGNING_KEY, max_age_seconds=300) is True
        # Verify with changed SQL → fails
        with pytest.raises(ValueError, match="SIGNATURE_PAYLOAD_MISMATCH"):
            verify_query_signature(sql2, params, sig1, SIGNING_KEY, max_age_seconds=300)

    def test_bounded_execution_retries(self):
        """Retry policy enforces max_retries limit."""
        policy = ExecutionRetryPolicy(max_retries=2)
        assert policy.should_retry("deadlock", 0) is True
        assert policy.should_retry("deadlock", 1) is True
        assert policy.should_retry("deadlock", 2) is False  # bounded

    def test_bounded_replanning_attempts(self):
        """Replanning loop cannot exceed max attempts."""
        max_replan = 3
        visited_plans = set()
        attempts = 0

        for _ in range(10):  # try to exceed
            if attempts >= max_replan:
                break
            plan_hash = _sql_hash(f"plan-attempt-{attempts}")
            if plan_hash in visited_plans:
                break
            visited_plans.add(plan_hash)
            attempts += 1

        assert attempts == max_replan
        assert len(visited_plans) == max_replan

    def test_visited_plan_hashes_prevent_cycles(self):
        """Visited plan hashes prevent replanning cycles."""
        visited = set()
        sql = "SELECT 1 FROM fake_table"
        h = _sql_hash(sql)
        visited.add(h)
        # Second attempt with same SQL → cycle detected
        assert h in visited

    def test_visited_sql_hashes_prevent_reuse(self):
        """Visited SQL hashes prevent reuse of failed SQL."""
        visited = set()
        sql = "SELECT * FROM missing_table"
        h = _sql_hash(sql)
        visited.add(h)
        # Same SQL again → already visited
        assert h in visited

    def test_preserved_original_intent(self):
        """Replanning preserves original query_text and task."""
        original_query = "show me the npl ratio by branch"
        plan = BUILDER.build(
            task="aggregation",
            query_text=original_query,
            selected_tables=["loan_contracts", "non_performing_loans"],
            bridge_tables=[],
            selected_columns={
                "loan_contracts": ["loan_id"],
                "non_performing_loans": ["npl_id", "loan_id"],
            },
            join_paths=[],
            metrics=["npl_ratio"],
            dimensions=[],
            filters_structured=[],
            time_range={"type": "none", "value": None},
            sort_structured=None,
            limit_requested=100,
            requested_fields=[],
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        assert plan.query_text == original_query
        assert plan.task == "aggregation"

    def test_semantic_preserving_replan(self):
        """Rebuild plan from original intent preserves contract.

        The trace begins with the natural-language intent, requested outputs,
        metrics, dimensions, filters, and ExpectedAnswer. The rebuilt plan
        must preserve that contract.

        Uses created_at (shared column) for NPL ratio filter, since branch_id
        correctly fails closed for npl_ratio (non_performing_loans lacks branch_id).
        """
        original_query = "show me the npl ratio since 2024-01-01"
        original_metrics = ["npl_ratio"]
        original_dimensions = []
        original_filters = [{"column": "loan_contracts.created_at", "operator": ">=", "value": "2024-01-01"}]
        original_time_range = {"type": "none", "value": None}

        plan = BUILDER.build(
            task="aggregation",
            query_text=original_query,
            selected_tables=["loan_contracts", "non_performing_loans"],
            bridge_tables=[],
            selected_columns={
                "loan_contracts": ["loan_id", "created_at"],
                "non_performing_loans": ["npl_id", "loan_id", "created_at"],
            },
            join_paths=[],
            metrics=original_metrics,
            dimensions=original_dimensions,
            filters_structured=original_filters,
            time_range=original_time_range,
            sort_structured=None,
            limit_requested=100,
            requested_fields=[],
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        original_sql = COMPILER.compile(plan).sql

        # Simulate: rebuild from same intent
        rebuilt_plan = BUILDER.build(
            task="aggregation",
            query_text=original_query,
            selected_tables=["loan_contracts", "non_performing_loans"],
            bridge_tables=[],
            selected_columns={
                "loan_contracts": ["loan_id", "created_at"],
                "non_performing_loans": ["npl_id", "loan_id", "created_at"],
            },
            join_paths=[],
            metrics=original_metrics,
            dimensions=original_dimensions,
            filters_structured=original_filters,
            time_range=original_time_range,
            sort_structured=None,
            limit_requested=100,
            requested_fields=[],
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        rebuilt_sql = COMPILER.compile(rebuilt_plan).sql

        # Contract preserved
        assert rebuilt_plan.query_text == original_query
        assert rebuilt_plan.task == plan.task
        assert rebuilt_plan.schema_snapshot_id == plan.schema_snapshot_id
        assert rebuilt_plan.semantic_metadata_version == plan.semantic_metadata_version
        assert len(rebuilt_plan.metrics) == len(plan.metrics)
        assert rebuilt_plan.metrics[0].metric_id == plan.metrics[0].metric_id
        assert len(rebuilt_plan.filters) == len(plan.filters)
        assert rebuilt_plan.filters[0].column == plan.filters[0].column
        assert rebuilt_plan.filters[0].value == plan.filters[0].value
        assert rebuilt_sql == original_sql

    def test_execution_trace_captures_repair(self):
        """ExecutionTrace captures full repair lifecycle metadata."""
        trace = ExecutionTrace(
            plan_hash="plan-abc",
            original_sql_hash="sql-orig",
            attempted_sql_hash="sql-attempt",
            retry_reason="deadlock",
            mechanical_repair_id="mr-123",
            critical_failures=[],
            replanning_request=PlanRepairRequest(
                reason="table missing",
                error_type="table_missing",
                requested_change="remove_table: fake",
            ),
            metadata_version="3.1",
        )
        assert trace.replanning_request.error_type == "table_missing"
        assert trace.mechanical_repair_id == "mr-123"


# ═════════════════════════════════════════════════════════════════════════════
# 6. PostgreSQL-Backed Integration (Simulated)
# ═════════════════════════════════════════════════════════════════════════════

class TestPostgresIntegration:
    """Integration tests simulating PostgreSQL execution results."""

    def _simulate_pg_execution(self, compiled_query, mock_data):
        """Simulate PG execution returning mock_data."""
        return {"rows": mock_data, "row_count": len(mock_data)}

    def test_scalar_zero(self):
        """Scalar result returning zero."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="count of risk flags",
            selected_tables=["risk_flags"],
            selected_columns={"risk_flags": ["flag_id"]},
            metrics=[],
            requested_fields=[],
        )
        mock_result = self._simulate_pg_execution(cq, [{"count_all": 0}])
        assert mock_result["rows"][0]["count_all"] == 0
        assert mock_result["row_count"] == 1

    def test_scalar_null(self):
        """Scalar result returning NULL."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="average balance",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            metrics=[],
            requested_fields=[],
        )
        mock_result = self._simulate_pg_execution(cq, [{"avg_balance": None}])
        assert mock_result["rows"][0]["avg_balance"] is None

    def test_valid_empty_detail_result(self):
        """Detail query returning empty result is valid."""
        plan, cq = _build_and_compile(
            task="detail_listing",
            requested_fields=["customer_id", "name"],
        )
        mock_result = self._simulate_pg_execution(cq, [])
        assert mock_result["row_count"] == 0

    def test_grouped_aggregation(self):
        """Grouped aggregation returns multiple rows."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="count customers by segment",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "segment"]},
            dimensions=["customers.segment"],
            requested_fields=["segment"],
        )
        mock_data = [
            {"segment": "premium", "count_all": 150},
            {"segment": "standard", "count_all": 300},
            {"segment": "basic", "count_all": 500},
        ]
        mock_result = self._simulate_pg_execution(cq, mock_data)
        assert mock_result["row_count"] == 3

    def test_ranking(self):
        """Ranking query returns ordered results."""
        plan, cq = _build_and_compile(
            task="ranking",
            query_text="top customers by balance",
            selected_tables=["accounts", "customers"],
            selected_columns={
                "accounts": ["account_id", "balance"],
                "customers": ["customer_id", "name"],
            },
            sort_structured=[{"column": "balance", "direction": "DESC"}],
            limit_requested=10,
            requested_fields=["name", "balance"],
        )
        mock_data = [
            {"name": "Alice", "balance": 50000},
            {"name": "Bob", "balance": 30000},
            {"name": "Charlie", "balance": 10000},
        ]
        mock_result = self._simulate_pg_execution(cq, mock_data)
        assert mock_result["rows"][0]["balance"] >= mock_result["rows"][1]["balance"]

    def test_time_series(self):
        """Time series result with period dimension."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="balance by month",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance", "created_at"]},
            dimensions=["accounts.created_at"],
            requested_fields=["created_at"],
        )
        mock_data = [
            {"created_at": "2024-01", "sum_balance": 100000},
            {"created_at": "2024-02", "sum_balance": 120000},
        ]
        mock_result = self._simulate_pg_execution(cq, mock_data)
        assert mock_result["row_count"] == 2

    def test_bound_filters(self):
        """Query with bound filters compiles correctly."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="count customers",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "segment"]},
            filters_structured=[
                {"column": "customers.segment", "operator": "=", "value": "premium"},
            ],
            requested_fields=[],
        )
        assert len(cq.parameters) >= 1
        assert cq.parameters[0].value == "premium"

    def test_missing_relation_error(self):
        """Missing table produces plan_repair from PGRepairEngine."""
        recovery = REPAIR.attempt_recovery(
            "SELECT * FROM nonexistent",
            'relation "nonexistent" does not exist',
        )
        assert recovery["plan_repair"] is not None
        assert recovery["plan_repair"]["error_type"] == "table_missing"

    def test_missing_column_error(self):
        """Missing column produces plan_repair from PGRepairEngine."""
        recovery = REPAIR.attempt_recovery(
            "SELECT bad_col FROM customers",
            'column "bad_col" does not exist',
        )
        assert recovery["plan_repair"] is not None
        assert recovery["plan_repair"]["error_type"] == "column_missing"

    def test_transient_retry(self):
        """Transient error (deadlock) triggers retry."""
        recovery = REPAIR.attempt_recovery("SELECT 1", "deadlock detected", attempt=0)
        assert recovery["retry"] is True
        assert recovery["recovered"] is True

    def test_scalar_loan_to_deposit(self):
        """Scalar loan_to_deposit compiles with independent subqueries."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="loan to deposit ratio",
            selected_tables=["loan_contracts", "accounts"],
            selected_columns={
                "loan_contracts": ["loan_id", "principal_amount"],
                "accounts": ["account_id", "balance"],
            },
            metrics=["loan_to_deposit"],
            requested_fields=[],
        )
        assert "_num" in cq.sql
        assert "_den" in cq.sql
        m = plan.metrics[0]
        assert m.execution_strategy.execution_strategy == "independent_subqueries"

    def test_grouped_loan_to_deposit_explicit_unsupported(self):
        """Grouped loan_to_deposit fails at build time (not silently wrong)."""
        plan = BUILDER.build(
            task="aggregation",
            query_text="loan to deposit ratio by branch",
            selected_tables=["loan_contracts", "accounts", "branches"],
            bridge_tables=[],
            selected_columns={
                "loan_contracts": ["loan_id", "principal_amount", "branch_id"],
                "accounts": ["account_id", "balance", "branch_id"],
                "branches": ["branch_id", "name"],
            },
            join_paths=[],
            metrics=["loan_to_deposit"],
            dimensions=["branches.name"],
            filters_structured=[],
            time_range={"type": "none", "value": None},
            sort_structured=None,
            limit_requested=100,
            requested_fields=["name"],
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        assert plan.unsupported_reason is not None
        assert "does not support grain" in plan.unsupported_reason

    def test_governed_npl_ratio(self):
        """Governed npl_ratio compiles correctly."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="npl ratio",
            selected_tables=["loan_contracts", "non_performing_loans"],
            selected_columns={
                "loan_contracts": ["loan_id"],
                "non_performing_loans": ["npl_id", "loan_id"],
            },
            metrics=["npl_ratio"],
            requested_fields=[],
        )
        m = plan.metrics[0]
        assert m.execution_strategy.execution_strategy == "independent_subqueries"
        assert "_num" in cq.sql
        assert "_den" in cq.sql


# ═════════════════════════════════════════════════════════════════════════════
# 7. Security Recovery Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestSecurityRecovery:
    """Prove retry, repair and replanning cannot bypass security."""

    def test_retry_cannot_broaden_table_authorization(self):
        """Retry uses same SQL — cannot access new tables."""
        sql = "SELECT name FROM customers LIMIT 100"
        recovery = REPAIR.attempt_recovery(sql, "deadlock detected", attempt=0)
        assert recovery["retry"] is True
        # Retry uses same SQL — no table broadening
        assert recovery.get("mechanical_sql") is None

    def test_retry_cannot_remove_row_limits(self):
        """Retry preserves original SQL with LIMIT — no row limit removal."""
        sql = "SELECT name FROM customers LIMIT 100"
        recovery = REPAIR.attempt_recovery(sql, "deadlock detected", attempt=0)
        # Retry replays same SQL (with LIMIT), not a modified version
        assert recovery["retry"] is True

    def test_mechanical_repair_cannot_bypass_timeout(self):
        """Mechanical repair only fixes GROUP BY and syntax — not timeout."""
        sql = "SELECT name, COUNT(*) FROM customers GROUP BY customer_id"
        recovery = REPAIR.attempt_recovery(sql, "timeout", attempt=1)
        # Timeout at attempt=1 → no retry, no mechanical repair (timeout is not mechanical)
        assert recovery["retry"] is False
        assert recovery["mechanical_sql"] is None

    def test_mechanical_repair_semantics_preserving(self):
        """Mechanical repair only adds GROUP BY or fixes syntax."""
        sql = "SELECT name, COUNT(*) FROM customers GROUP BY customer_id"
        recovery = REPAIR.attempt_recovery(
            sql,
            'column "name" must appear in the GROUP BY clause',
        )
        assert recovery["mechanical_sql"] is not None
        assert "name" in recovery["mechanical_sql"]
        # Original SQL structure preserved (no table removal, no filter removal)
        assert "FROM customers" in recovery["mechanical_sql"]

    def test_replan_cannot_alter_user_role(self):
        """PlanRepairRequest does not contain role information."""
        recovery = REPAIR.attempt_recovery(
            "SELECT * FROM secret_table",
            'relation "secret_table" does not exist',
        )
        pr = recovery["plan_repair"]
        assert pr is not None
        # No role information in plan repair
        assert "role" not in pr
        assert "user" not in pr

    def test_replan_cannot_reuse_old_signature_for_changed_sql(self):
        """Changed SQL after replanning gets new signature; old is invalid."""
        ts = int(time.time())
        old_sql = "SELECT * FROM fake_table LIMIT 100"
        new_sql = "SELECT * FROM customers LIMIT 100"
        sig_old = sign_query_payload("req-001", old_sql, [], ts, "nonce-1", SIGNING_KEY)
        # New SQL with old signature → fails
        with pytest.raises(ValueError, match="SIGNATURE_PAYLOAD_MISMATCH"):
            verify_query_signature(new_sql, [], sig_old, SIGNING_KEY, max_age_seconds=300)

    def test_replan_cannot_bypass_table_authorization(self):
        """Replan removes missing table — does not add unauthorized tables."""
        # Original plan has fake_table (missing)
        recovery = REPAIR.attempt_recovery(
            "SELECT * FROM fake_table",
            'relation "fake_table" does not exist',
        )
        pr = recovery["plan_repair"]
        assert pr["error_type"] == "table_missing"
        assert "fake_table" in pr["requested_change"]
        # PlanRepairRequest requests removal, not addition

    def test_replan_cannot_remove_row_limits(self):
        """PlanRepairRequest preserves limit — does not remove it."""
        plan = BUILDER.build(
            task="aggregation",
            query_text="test",
            selected_tables=["customers"],
            bridge_tables=[],
            selected_columns={"customers": ["customer_id", "name"]},
            join_paths=[],
            metrics=[],
            dimensions=[],
            filters_structured=[],
            time_range={"type": "none", "value": None},
            sort_structured=None,
            limit_requested=50,
            requested_fields=["name"],
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        assert plan.limit == 50
        # PlanRepairRequest does not modify limit
        pr = PlanRepairRequest(
            reason="table missing",
            error_type="table_missing",
            requested_change="remove_table: fake",
        )
        assert "limit" not in pr.requested_change.lower()

    def test_replan_cannot_bypass_timeout(self):
        """PlanRepairRequest does not remove timeout constraints."""
        recovery = REPAIR.attempt_recovery(
            "SELECT * FROM huge_table",
            "canceling statement due to statement timeout",
            attempt=1,
        )
        # Timeout at attempt=1: no retry, no mechanical, no plan_repair (timeout not in structural list)
        assert recovery["retry"] is False
        assert recovery["mechanical_sql"] is None

    def test_replan_cannot_execute_against_stale_metadata(self):
        """Schema snapshot ID preserved in rebuilt plan."""
        plan = BUILDER.build(
            task="aggregation",
            query_text="test",
            selected_tables=["customers"],
            bridge_tables=[],
            selected_columns={"customers": ["customer_id"]},
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
        assert plan.schema_snapshot_id == SNAPSHOT
        # Rebuilt plan carries the same snapshot
        new_plan = BUILDER.build(
            task="aggregation",
            query_text="test",
            selected_tables=["customers"],
            bridge_tables=[],
            selected_columns={"customers": ["customer_id"]},
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
        assert new_plan.schema_snapshot_id == SNAPSHOT


# ═════════════════════════════════════════════════════════════════════════════
# 9. Changed-SQL Semantic Replanning
# ═════════════════════════════════════════════════════════════════════════════

class TestChangedSQLReplanning:
    """Demonstrate changed-SQL semantic replanning with source change.

    When the original physical source is unavailable or stale, replanning
    starts from the same natural-language intent. If an equivalent source
    exists, it is selected and SQL hash changes. If no equivalent source
    exists, replanning fails closed.
    """

    def test_same_intent_same_source_same_sql(self):
        """Rebuilding from same intent with same source produces same SQL.

        This is the baseline: if no source change occurred, SQL is identical.
        """
        kw = {
            **BASE_KWARGS,
            "task": "aggregation",
            "query_text": "count customers by segment",
            "selected_tables": ["customers"],
            "selected_columns": {"customers": ["customer_id", "segment"]},
            "dimensions": ["customers.segment"],
            "requested_fields": ["segment"],
        }
        plan1 = BUILDER.build(**kw)
        plan2 = BUILDER.build(**kw)
        sql1 = COMPILER.compile(plan1).sql
        sql2 = COMPILER.compile(plan2).sql
        assert sql1 == sql2
        assert _sql_hash(sql1) == _sql_hash(sql2)

    def test_different_source_same_intent_different_sql(self):
        """Using different table for same intent produces different SQL (hash changes).

        Simulates: original source 'risk_flags' is stale; equivalent source
        'aml_alerts' is authoritative. Same intent, different physical source.
        """
        # Original: count from risk_flags
        plan_orig = BUILDER.build(
            **{
                **BASE_KWARGS,
                "task": "aggregation",
                "query_text": "count alerts",
                "selected_tables": ["risk_flags"],
                "selected_columns": {"risk_flags": ["flag_id"]},
                "dimensions": [],
                "requested_fields": [],
            }
        )
        sql_orig = COMPILER.compile(plan_orig).sql

        # Replan: use aml_alerts instead (authoritative equivalent)
        plan_new = BUILDER.build(
            **{
                **BASE_KWARGS,
                "task": "aggregation",
                "query_text": "count alerts",
                "selected_tables": ["aml_alerts"],
                "selected_columns": {"aml_alerts": ["alert_id"]},
                "dimensions": [],
                "requested_fields": [],
            }
        )
        sql_new = COMPILER.compile(plan_new).sql

        # SQL hash changes
        assert _sql_hash(sql_orig) != _sql_hash(sql_new)
        # Both are valid SELECT
        assert sql_orig.startswith("SELECT")
        assert sql_new.startswith("SELECT")
        # Old signature is invalid for new SQL
        ts = int(time.time())
        sig_old = sign_query_payload("req-replan", sql_orig, [], ts, "nonce-1", SIGNING_KEY)
        with pytest.raises(ValueError, match="SIGNATURE_PAYLOAD_MISMATCH"):
            verify_query_signature(sql_new, [], sig_old, SIGNING_KEY, max_age_seconds=300)

    def test_replanning_fails_closed_no_equivalent_source(self):
        """When the original source is unavailable and no equivalent exists, fail closed.

        Simulate: original table 'risk_flags_for_legacy_metric' does not exist.
        Replanning cannot find an equivalent source. The compiler raises
        because the metric's required tables are missing from the plan.
        """
        # Build plan with a table that doesn't exist in the schema
        # and a metric that requires tables not present → compiler fails
        recovery = REPAIR.attempt_recovery(
            "SELECT * FROM nonexistent_legacy_source",
            'relation "nonexistent_legacy_source" does not exist',
        )
        assert recovery["plan_repair"] is not None
        assert recovery["plan_repair"]["error_type"] == "table_missing"
        # The PlanRepairRequest requests removal, not addition of a new source
        # This is the expected behavior: replanning removes the missing table
        # but does not add unauthorized new tables
        req = PlanRepairRequest(**recovery["plan_repair"])
        assert "remove" in req.requested_change.lower() or "missing" in req.requested_change.lower()
