"""
tests/test_increment3_execution.py
Increment 3 tests: execution engine, ResultVerifier, PGRepairEngine,
PlanRefiner, MetricExecutionStrategy, orchestrator integration.

Increment 3.1: Expanded with recovery split, severity, empty-result
semantics, metric validation, independent subqueries compilation,
advisory-only refinement, and execution trace tests.

Covers:
  - MetricExecutionStrategy model construction
  - loan_to_deposit independent_subqueries strategy
  - ResultVerifier: 12 checks with severity levels
  - PGRepairEngine: three-way recovery (retry / mechanical / replan)
  - PlanRefiner: advisory-only proposals
  - DeterministicCompiler: independent subqueries materialization
  - Execution metadata: split statuses
  - Full pipeline: build → compile → execute → verify → repair → refine
"""
import sys
import os
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVICES = os.path.join(ROOT, "services")
for p in [SERVICES]:
    if p not in sys.path:
        sys.path.insert(0, p)

EXEC_DIR = os.path.join(SERVICES, "execution_agent")
for p in [EXEC_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from sql_agent.plan_models import (
    QueryPlan, CompiledQuery, MetricExecutionStrategy, MetricReference,
    GrainSpec, ColumnRef, ExpectedAnswer, MetricValidationRules,
    VerificationCheck, ResultVerification, PlanRepairRequest,
    ExecutionRetryPolicy, SQLMechanicalRepair, ExecutionTrace,
    EmptyResultSemantics,
)
from sql_agent.query_plan_builder import QueryPlanBuilder
from sql_agent.deterministic_compiler import DeterministicSQLCompiler
from result_verifier import ResultVerifier
from pg_repair_engine import PGRepairEngine, ExecutionRetryPolicy as RetryPolicy
from plan_refiner import PlanRefiner


BUILDER = QueryPlanBuilder()
COMPILER = DeterministicSQLCompiler()
VERIFIER = ResultVerifier()
REPAIR = PGRepairEngine()
REFINER = PlanRefiner()

SNAPSHOT = "snap-test-003"
VERSION = "v7.0.0"

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
# MetricExecutionStrategy Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestMetricExecutionStrategy:
    def test_strategy_model_construction(self):
        s = MetricExecutionStrategy(
            execution_strategy="independent_subqueries",
            fan_out_safe=True,
            preaggregation_required=True,
            allowed_join_patterns=["many_to_one"],
        )
        assert s.execution_strategy == "independent_subqueries"
        assert s.fan_out_safe is True
        assert s.preaggregation_required is True

    def test_strategy_default_single_query(self):
        s = MetricExecutionStrategy()
        assert s.execution_strategy == "single_query"
        assert s.fan_out_safe is True

    def test_loan_to_deposit_uses_independent_subqueries(self):
        plan, _ = _build_and_compile(
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
        assert len(plan.metrics) == 1
        m = plan.metrics[0]
        assert m.execution_strategy is not None
        assert m.execution_strategy.execution_strategy == "independent_subqueries"
        assert m.execution_strategy.fan_out_safe is True
        assert m.execution_strategy.preaggregation_required is True
        assert m.execution_strategy.allowed_join_patterns == []

    def test_kyc_compliance_rate_uses_single_query(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "kyc_verified"]},
            metrics=["kyc_compliance_rate"],
            requested_fields=[],
        )
        m = plan.metrics[0]
        assert m.execution_strategy is not None
        assert m.execution_strategy.execution_strategy == "single_query"
        assert m.execution_strategy.fan_out_safe is True

    def test_npl_ratio_uses_independent_subqueries(self):
        plan, _ = _build_and_compile(
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

    def test_metric_without_strategy(self):
        plan, _ = _build_and_compile(
            task="aggregation",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            metrics=["avg_loan_size"],
            requested_fields=[],
        )
        m = plan.metrics[0]
        assert m.execution_strategy is None


# ═════════════════════════════════════════════════════════════════════════════
# Increment 3.1: ExpectedAnswer & MetricValidationRules
# ═════════════════════════════════════════════════════════════════════════════

class TestExpectedAnswer31:
    def test_empty_result_semantics_default_invalid(self):
        ea = ExpectedAnswer(answer_type="scalar")
        assert ea.empty_result_semantics == "invalid"

    def test_empty_result_semantics_valid_no_match(self):
        ea = ExpectedAnswer(answer_type="grouped_rows", empty_result_semantics="valid_no_match")
        assert ea.empty_result_semantics == "valid_no_match"

    def test_empty_result_semantics_expect_scalar_zero(self):
        ea = ExpectedAnswer(answer_type="scalar", empty_result_semantics="expect_scalar_zero")
        assert ea.empty_result_semantics == "expect_scalar_zero"

    def test_metric_validation_rules(self):
        rules = {"npl_ratio": MetricValidationRules(minimum=0, maximum=100, nullable=False)}
        ea = ExpectedAnswer(
            answer_type="scalar",
            expected_metrics=["npl_ratio"],
            metric_validation_rules=rules,
        )
        assert "npl_ratio" in ea.metric_validation_rules
        assert ea.metric_validation_rules["npl_ratio"].minimum == 0
        assert ea.metric_validation_rules["npl_ratio"].maximum == 100
        assert ea.metric_validation_rules["npl_ratio"].nullable is False


# ═════════════════════════════════════════════════════════════════════════════
# ResultVerifier Tests (Increment 3.1: 12 checks)
# ═════════════════════════════════════════════════════════════════════════════

class TestResultVerifier:
    def test_scalar_single_row_passes(self):
        data = [{"npl_ratio": 5.23}]
        expected = {"answer_type": "scalar", "expected_metrics": ["npl_ratio"]}
        result = VERIFIER.verify(data, expected, plan_metrics=["npl_ratio"])
        assert result["verified"] is True
        assert result["row_count"] == 1

    def test_scalar_multiple_rows_fails_critical(self):
        data = [{"governorate": "Tunis", "count": 10}, {"governorate": "Sfax", "count": 5}]
        expected = {"answer_type": "scalar", "expected_metrics": ["count"]}
        result = VERIFIER.verify(data, expected, plan_metrics=["count"])
        assert result["verified"] is False
        assert "row_count_scalar" in result["critical_failures"]

    def test_grouped_rows_with_data_passes(self):
        data = [
            {"governorate": "Tunis", "count": 10},
            {"governorate": "Sfax", "count": 5},
        ]
        expected = {
            "answer_type": "grouped_rows",
            "expected_grain": ["governorate"],
            "expected_metrics": ["count"],
            "expected_columns": ["governorate", "count"],
        }
        result = VERIFIER.verify(
            data, expected,
            plan_metrics=["count"],
            plan_dimensions=["branches.governorate"],
        )
        assert result["verified"] is True

    def test_empty_result_for_grouped_invalid_fails(self):
        data = []
        expected = {"answer_type": "grouped_rows", "expected_metrics": ["count"], "empty_result_semantics": "invalid"}
        result = VERIFIER.verify(data, expected, plan_metrics=["count"])
        assert result["verified"] is False
        assert "empty_result_invalid" in result["critical_failures"]

    def test_empty_result_for_grouped_valid_no_match_passes(self):
        data = []
        expected = {"answer_type": "grouped_rows", "expected_metrics": ["count"], "empty_result_semantics": "valid_no_match"}
        result = VERIFIER.verify(data, expected, plan_metrics=["count"])
        assert result["verified"] is True

    def test_empty_result_expect_scalar_zero(self):
        data = []
        expected = {"answer_type": "scalar", "empty_result_semantics": "expect_scalar_zero"}
        result = VERIFIER.verify(data, expected)
        assert result["verified"] is True

    def test_detail_rows_empty_passes(self):
        data = []
        expected = {"answer_type": "detail_rows"}
        result = VERIFIER.verify(data, expected)
        assert result["verified"] is True

    def test_all_null_metrics_fails_warning(self):
        data = [{"npl_ratio": None}, {"npl_ratio": None}]
        expected = {"answer_type": "grouped_rows", "expected_metrics": ["npl_ratio"]}
        result = VERIFIER.verify(data, expected, plan_metrics=["npl_ratio"])
        assert result["verified"] is True  # warning, not critical
        assert "no_all_null_metrics" in result["warnings"]

    def test_non_numeric_metric_fails_critical(self):
        data = [{"npl_ratio": "not_a_number"}]
        expected = {"answer_type": "scalar", "expected_metrics": ["npl_ratio"]}
        result = VERIFIER.verify(data, expected, plan_metrics=["npl_ratio"])
        assert result["verified"] is False
        assert "metric_numeric" in result["critical_failures"]

    def test_column_presence_passes(self):
        data = [{"customer_id": "C001", "name": "Alice", "balance": 5000}]
        expected = {
            "answer_type": "detail_rows",
            "expected_columns": ["customer_id", "name", "balance"],
        }
        result = VERIFIER.verify(data, expected)
        assert result["verified"] is True

    def test_column_presence_fails_critical(self):
        data = [{"customer_id": "C001", "name": "Alice"}]
        expected = {
            "answer_type": "detail_rows",
            "expected_columns": ["customer_id", "name", "email"],
        }
        result = VERIFIER.verify(data, expected)
        assert result["verified"] is False
        assert "column_presence" in result["critical_failures"]

    def test_no_expected_answer_trivially_passes(self):
        data = [{"a": 1}, {"a": 2}]
        result = VERIFIER.verify(data, None)
        assert result["verified"] is True

    def test_grain_consistency_passes(self):
        data = [{"governorate": "Tunis", "count": 10}]
        expected = {"answer_type": "grouped_rows"}
        grain = {"output_grain": "governorate"}
        result = VERIFIER.verify(data, expected, plan_grain=grain)
        assert result["verified"] is True

    def test_grain_consistency_scalar(self):
        data = [{"npl_ratio": 5.0}]
        expected = {"answer_type": "scalar"}
        grain = {"output_grain": "scalar"}
        result = VERIFIER.verify(data, expected, plan_grain=grain)
        assert result["verified"] is True


# ═════════════════════════════════════════════════════════════════════════════
# Increment 3.1: Verifier — metric value range, ratio sanity, duplicates,
# null ratio, ordering
# ═════════════════════════════════════════════════════════════════════════════

class TestVerifier31Checks:
    def test_metric_value_range_pass(self):
        data = [{"npl_ratio": 5.0}]
        expected = {
            "answer_type": "scalar",
            "expected_metrics": ["npl_ratio"],
            "metric_validation_rules": {"npl_ratio": {"minimum": 0, "maximum": 100}},
        }
        result = VERIFIER.verify(data, expected, plan_metrics=["npl_ratio"])
        range_check = [c for c in result["checks"] if c["check_name"] == "metric_value_range"]
        assert len(range_check) == 1
        assert range_check[0]["passed"] is True

    def test_metric_value_range_fail_below_minimum(self):
        data = [{"npl_ratio": -5.0}]
        expected = {
            "answer_type": "scalar",
            "expected_metrics": ["npl_ratio"],
            "metric_validation_rules": {"npl_ratio": {"minimum": 0, "maximum": 100}},
        }
        result = VERIFIER.verify(data, expected, plan_metrics=["npl_ratio"])
        range_check = [c for c in result["checks"] if c["check_name"] == "metric_value_range"]
        assert range_check[0]["passed"] is False

    def test_ratio_sanity_pass(self):
        data = [{"loan_to_deposit": 45.5}]
        expected = {"answer_type": "scalar", "expected_metrics": ["loan_to_deposit"]}
        result = VERIFIER.verify(data, expected, plan_metrics=["loan_to_deposit"])
        ratio_check = [c for c in result["checks"] if c["check_name"] == "ratio_sanity"]
        assert ratio_check[0]["passed"] is True

    def test_ratio_sanity_fail_above_100(self):
        data = [{"loan_to_deposit": 150.0}]
        expected = {"answer_type": "scalar", "expected_metrics": ["loan_to_deposit"]}
        result = VERIFIER.verify(data, expected, plan_metrics=["loan_to_deposit"])
        ratio_check = [c for c in result["checks"] if c["check_name"] == "ratio_sanity"]
        assert ratio_check[0]["passed"] is False

    def test_duplicate_rows_detected(self):
        data = [{"a": 1, "b": 2}, {"a": 1, "b": 2}]
        expected = {"answer_type": "detail_rows"}
        result = VERIFIER.verify(data, expected)
        dupe_check = [c for c in result["checks"] if c["check_name"] == "duplicate_rows"]
        assert dupe_check[0]["passed"] is False

    def test_null_ratio_high_fails(self):
        data = [{"npl_ratio": None}, {"npl_ratio": None}, {"npl_ratio": None}, {"npl_ratio": None}, {"npl_ratio": 5.0}]
        expected = {"answer_type": "grouped_rows", "expected_metrics": ["npl_ratio"]}
        result = VERIFIER.verify(data, expected, plan_metrics=["npl_ratio"])
        null_check = [c for c in result["checks"] if c["check_name"] == "null_ratio"]
        assert null_check[0]["passed"] is False

    def test_ordering_pass(self):
        data = [{"risk_score": 1}, {"risk_score": 2}, {"risk_score": 3}]
        expected = {"answer_type": "grouped_rows", "ordering": "risk_score ASC"}
        result = VERIFIER.verify(data, expected)
        order_check = [c for c in result["checks"] if c["check_name"] == "ordering"]
        assert order_check[0]["passed"] is True

    def test_ordering_fail(self):
        data = [{"risk_score": 3}, {"risk_score": 1}, {"risk_score": 2}]
        expected = {"answer_type": "grouped_rows", "ordering": "risk_score ASC"}
        result = VERIFIER.verify(data, expected)
        order_check = [c for c in result["checks"] if c["check_name"] == "ordering"]
        assert order_check[0]["passed"] is False


# ═════════════════════════════════════════════════════════════════════════════
# PGRepairEngine Tests (Increment 3.1: three-way recovery split)
# ═════════════════════════════════════════════════════════════════════════════

class TestPGRepairEngine:
    def test_diagnose_table_missing(self):
        diag = REPAIR.diagnose('relation "nonexistent_table" does not exist')
        assert diag["error_type"] == "table_missing"
        assert diag["matched_value"] == "nonexistent_table"

    def test_diagnose_column_missing(self):
        diag = REPAIR.diagnose('column "bad_col" does not exist')
        assert diag["error_type"] == "column_missing"
        assert diag["matched_value"] == "bad_col"

    def test_diagnose_syntax_error(self):
        diag = REPAIR.diagnose('syntax error at or near "FROM"')
        assert diag["error_type"] == "syntax_error"

    def test_diagnose_timeout(self):
        diag = REPAIR.diagnose('canceling statement due to statement timeout')
        assert diag["error_type"] == "timeout"

    def test_diagnose_deadlock(self):
        diag = REPAIR.diagnose('deadlock detected')
        assert diag["error_type"] == "deadlock"

    def test_diagnose_permission_denied(self):
        diag = REPAIR.diagnose('permission denied for table customers')
        assert diag["error_type"] == "permission_denied"

    def test_diagnose_group_by_error(self):
        diag = REPAIR.diagnose('column "name" must appear in the GROUP BY clause')
        assert diag["error_type"] == "group_by_error"

    def test_diagnose_unknown_error(self):
        diag = REPAIR.diagnose("something completely unexpected happened")
        assert diag["error_type"] == "unknown"

    def test_mechanical_repair_group_by(self):
        sql = "SELECT name, COUNT(*) FROM customers GROUP BY segment"
        repaired = REPAIR.mechanical.repair(sql, "group_by_error", "name")
        assert repaired is not None
        assert "name" in repaired

    def test_mechanical_repair_syntax(self):
        sql = "SELECT * FROM customers;"
        repaired = REPAIR.mechanical.repair(sql, "syntax_error")
        assert repaired is not None
        assert not repaired.rstrip().endswith(";")

    def test_mechanical_repair_returns_none_for_structural(self):
        repaired = REPAIR.mechanical.repair("SELECT 1", "table_missing", "foo")
        assert repaired is None

    def test_recovery_deadlock_retries(self):
        recovery = REPAIR.attempt_recovery("SELECT 1", "deadlock detected", attempt=0)
        assert recovery["retry"] is True
        assert recovery["recovered"] is True

    def test_recovery_timeout_retries(self):
        recovery = REPAIR.attempt_recovery("SELECT 1", "canceling statement due to statement timeout", attempt=0)
        assert recovery["retry"] is True

    def test_recovery_timeout_no_retry_on_second_attempt(self):
        recovery = REPAIR.attempt_recovery("SELECT 1", "canceling statement due to statement timeout", attempt=1)
        assert recovery["retry"] is False
        assert recovery["recovered"] is False
        assert recovery["error_type"] == "timeout"

    def test_recovery_table_missing_produces_plan_repair(self):
        recovery = REPAIR.attempt_recovery(
            "SELECT * FROM fake_table",
            'relation "fake_table" does not exist',
        )
        assert recovery["plan_repair"] is not None
        assert recovery["plan_repair"]["error_type"] == "table_missing"
        assert recovery["recovered"] is False

    def test_recovery_column_missing_produces_plan_repair(self):
        recovery = REPAIR.attempt_recovery(
            "SELECT bad_col FROM customers",
            'column "bad_col" does not exist',
        )
        assert recovery["plan_repair"] is not None
        assert recovery["plan_repair"]["error_type"] == "column_missing"

    def test_recovery_group_by_fixes_mechanically(self):
        sql = "SELECT name, COUNT(*) FROM customers GROUP BY customer_id"
        recovery = REPAIR.attempt_recovery(
            sql,
            'column "name" must appear in the GROUP BY clause',
        )
        assert recovery["mechanical_sql"] is not None
        assert recovery["recovered"] is True
        assert "repair_id" in recovery


# ═════════════════════════════════════════════════════════════════════════════
# PlanRefiner Tests (Increment 3.1: advisory-only)
# ═════════════════════════════════════════════════════════════════════════════

class TestPlanRefiner:
    def test_refine_scalar_multi_row_proposes_dims(self):
        plan = {"task": "aggregation", "dimensions": ["governorate"], "metrics": ["count"], "filters": [], "limit": 100}
        verification = {
            "verified": False,
            "checks": [{"check_name": "row_count_scalar", "passed": False, "severity": "critical"}],
            "repair_suggestions": [],
        }
        result = REFINER.refine(plan, verification)
        assert result["refined"] is True
        assert result["retry_recommended"] is True
        # 3.1: proposals, not changes
        dim_proposals = [p for p in result["proposals"] if p["field"] == "dimensions"]
        assert len(dim_proposals) == 1
        assert result["changes"] == []  # never auto-apply

    def test_refine_scalar_multi_row_no_dims_proposes_limit(self):
        plan = {"task": "aggregation", "dimensions": [], "metrics": ["count"], "filters": [], "limit": 100}
        verification = {
            "verified": False,
            "checks": [{"check_name": "row_count_scalar", "passed": False, "severity": "critical"}],
            "repair_suggestions": [],
        }
        result = REFINER.refine(plan, verification)
        assert result["refined"] is True
        limit_proposals = [p for p in result["proposals"] if p["field"] == "limit"]
        assert len(limit_proposals) == 1

    def test_refine_empty_result_proposes_filter_review(self):
        plan = {"task": "aggregation", "dimensions": ["governorate"], "metrics": ["count"],
                "filters": [{"column": "status", "operator": "=", "value": "active"}], "limit": 100}
        verification = {
            "verified": False,
            "checks": [{"check_name": "nonempty_result", "passed": False, "severity": "critical"}],
            "repair_suggestions": [],
        }
        result = REFINER.refine(plan, verification)
        assert result["refined"] is True
        filter_proposals = [p for p in result["proposals"] if p["field"] == "filters"]
        assert len(filter_proposals) == 1

    def test_refine_timeout_proposes_limit_reduction(self):
        plan = {"task": "aggregation", "dimensions": [], "metrics": [], "filters": [], "limit": 100}
        result = REFINER.refine(plan, execution_error="canceling statement due to statement timeout")
        assert result["refined"] is True
        limit_proposals = [p for p in result["proposals"] if p["field"] == "limit"]
        assert len(limit_proposals) == 1

    def test_refine_no_failure_returns_not_refined(self):
        plan = {"task": "aggregation"}
        result = REFINER.refine(plan)
        assert result["refined"] is False
        assert result["proposals"] == []

    def test_apply_refinement_with_explicit_changes(self):
        """apply_refinement only applies changes (not proposals)."""
        plan = {"task": "aggregation", "dimensions": ["governorate"], "limit": 100}
        refinement = {
            "refined": True,
            "changes": [{"field": "dimensions", "from": ["governorate"], "to": []}],
            "proposals": [{"field": "dimensions", "action": "remove", "reason": "test"}],
        }
        new_plan = REFINER.apply_refinement(plan, refinement)
        assert new_plan["dimensions"] == []
        assert new_plan["task"] == "aggregation"


# ═════════════════════════════════════════════════════════════════════════════
# DeterministicCompiler: Independent subqueries (Increment 3.1)
# ═════════════════════════════════════════════════════════════════════════════

class TestIndependentSubqueries:
    def test_loan_to_deposit_compiles_independent_subqueries(self):
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
        m = plan.metrics[0]
        assert m.execution_strategy.execution_strategy == "independent_subqueries"
        # 3.1: SQL should contain independent subqueries, not CASE WHEN
        assert "(_num)" in cq.sql or "_num" in cq.sql
        assert "(_den)" in cq.sql or "_den" in cq.sql

    def test_npl_ratio_compiles_independent_subqueries(self):
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
        assert "_num" in cq.sql
        assert "_den" in cq.sql

    def test_single_query_metric_not_affected(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "kyc_verified"]},
            metrics=["kyc_compliance_rate"],
            requested_fields=[],
        )
        # Single-query metrics should NOT use subquery pattern
        assert "_num" not in cq.sql
        assert "FROM customers" in cq.sql

    def test_independent_subquery_deterministic(self):
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


# ═════════════════════════════════════════════════════════════════════════════
# Integration: Builder → Compiler → Verifier
# ═════════════════════════════════════════════════════════════════════════════

class TestIntegrationPipeline:
    def test_scalar_metric_verifies_correctly(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="what is the npl ratio",
            selected_tables=["loan_contracts"],
            selected_columns={"loan_contracts": ["loan_id"]},
            metrics=["npl_ratio"],
            requested_fields=[],
        )
        ea = plan.expected_answer
        mock_data = [{"loan_id": "L001", "npl_ratio": 5.23}]
        result = VERIFIER.verify(
            mock_data,
            ea.model_dump() if ea else None,
            plan_metrics=[m.alias for m in plan.metrics],
        )
        assert result["verified"] is True

    def test_grouped_metric_verifies_correctly(self):
        plan, cq = _build_and_compile(
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
        mock_data = [
            {"governorate": "Tunis", "count_all": 150},
            {"governorate": "Sfax", "count_all": 89},
        ]
        result = VERIFIER.verify(
            mock_data,
            ea.model_dump() if ea else None,
            plan_metrics=["count_all"],
            plan_dimensions=["branches.governorate"],
            plan_grain=plan.grain.model_dump() if plan.grain else None,
        )
        assert result["verified"] is True

    def test_ldr_compiles_with_independent_subqueries(self):
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
        m = plan.metrics[0]
        assert m.execution_strategy.execution_strategy == "independent_subqueries"
        # 3.1: independent subqueries, not CASE WHEN
        assert "_num" in cq.sql

    def test_full_pipeline_trace(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="total account balance by segment",
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
        mock_data = [
            {"segment": "premium", "sum_balance": 50000},
            {"segment": "standard", "sum_balance": 30000},
        ]
        ea = plan.expected_answer
        verification = VERIFIER.verify(
            mock_data,
            ea.model_dump() if ea else None,
            plan_metrics=[m.alias for m in plan.analytical_expressions] if hasattr(plan, 'analytical_expressions') else ["sum_balance"],
            plan_dimensions=["customers.segment"],
            plan_grain=plan.grain.model_dump() if plan.grain else None,
        )
        assert verification["verified"] is True
        assert len(verification["repair_suggestions"]) == 0

    def test_verification_failure_triggers_advisory_refinement(self):
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="what is the npl ratio",
            selected_tables=["loan_contracts"],
            selected_columns={"loan_contracts": ["loan_id"]},
            metrics=["npl_ratio"],
            requested_fields=[],
        )
        mock_data = [{"npl_ratio": 5.0}, {"npl_ratio": 3.0}]
        ea = plan.expected_answer
        verification = VERIFIER.verify(
            mock_data,
            ea.model_dump() if ea else None,
            plan_metrics=["npl_ratio"],
        )
        assert verification["verified"] is False

        plan_summary = {
            "task": "aggregation",
            "dimensions": [],
            "metrics": ["npl_ratio"],
            "filters": [],
            "limit": 100,
        }
        refinement = REFINER.refine(plan_summary, verification)
        assert refinement["refined"] is True
        assert refinement["retry_recommended"] is True
        # 3.1: advisory-only, no auto-changes
        assert refinement["changes"] == []
        assert len(refinement["proposals"]) > 0


# ═════════════════════════════════════════════════════════════════════════════
# ExecutionTrace & Metadata (Increment 3.1)
# ═════════════════════════════════════════════════════════════════════════════

class TestExecutionTrace31:
    def test_execution_trace_model(self):
        trace = ExecutionTrace(
            plan_hash="abc123",
            original_sql_hash="def456",
            attempted_sql_hash="ghi789",
            retry_reason="deadlock",
            mechanical_repair_id="mr-12345678",
            critical_failures=["row_count_scalar"],
            metadata_version="3.1",
        )
        assert trace.original_sql_hash == "def456"
        assert trace.retry_reason == "deadlock"
        assert trace.mechanical_repair_id == "mr-12345678"
        assert trace.metadata_version == "3.1"

    def test_verification_severity_levels(self):
        check = VerificationCheck(
            check_name="test",
            passed=False,
            severity="critical",
            message="fail",
        )
        assert check.severity == "critical"

    def test_plan_repair_request_model(self):
        req = PlanRepairRequest(
            reason="table missing",
            error_type="table_missing",
            requested_change="remove_table: fake_table",
            original_sql="SELECT * FROM fake_table",
            original_error='relation "fake_table" does not exist',
        )
        assert req.error_type == "table_missing"
        assert req.original_sql == "SELECT * FROM fake_table"

    def test_execution_retry_policy(self):
        policy = ExecutionRetryPolicy(max_retries=2)
        assert policy.should_retry("deadlock", 0) is True
        assert policy.should_retry("deadlock", 1) is True
        assert policy.should_retry("deadlock", 2) is False
        assert policy.should_retry("table_missing", 0) is False


# ═════════════════════════════════════════════════════════════════════════════
# Deterministic stability (existing tests still pass)
# ═════════════════════════════════════════════════════════════════════════════

class TestIncrement3Deterministic:
    def test_same_plan_same_sql_with_strategy(self):
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

    def test_strategy_preserved_after_roundtrip(self):
        plan, _ = _build_and_compile(
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
        plan_dict = plan.model_dump()
        plan2 = QueryPlan(**plan_dict)
        assert plan2.metrics[0].execution_strategy.execution_strategy == "independent_subqueries"
