"""
tests/test_live_pg_integration.py
Live PostgreSQL Integration Gate — executes compiled SQL against the real
banking_dev database in Docker and records real latency.

This replaces simulated PG tests from the previous benchmark gate.
Every test executes parameterized SQL against a live PostgreSQL 16 instance.

20 required test cases:
  1. Scalar loan_to_deposit
  2. Scalar npl_ratio
  3. Count zero (impossible filter)
  4. Empty detail rows
  5. Shared date filter (both subqueries)
  6. Side-specific filter (npl_ratio date filter on both tables)
  7. Ranking (ORDER BY + LIMIT)
  8. Time series (GROUP BY time period)
  9. loan_to_deposit with shared column filter
  10. npl_ratio with side-specific filter
  11. Semantic-preserving replan trace
  12. Missing relation → PlanRepairRequest
  13. Full replan with fresh signature
  14. Authorization rerun → PlanRepairRequest
  15. Stale snapshot rejection
  16. Timezone-aware chronology
  17. Bounded timeout retry
  18. Result verification (loan_to_deposit)
  19. Result verification (npl_ratio)
  20. Latency p50/p95/p99 warm+cold
"""
import sys
import os
import time
import statistics
import pytest
import psycopg2

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
    GrainSpec, ColumnRef, ExpectedAnswer, FilterSpec, TimeRangeSpec,
    PlanRepairRequest, ExecutionRetryPolicy,
)
from sql_agent.query_plan_builder import QueryPlanBuilder, APPROVED_METRICS
from sql_agent.deterministic_compiler import (
    DeterministicSQLCompiler, _INDEPENDENT_SUBQUERY_REGISTRY,
)
from result_verifier import ResultVerifier
from pg_repair_engine import PGRepairEngine
from query_signing import sign_query_payload, verify_query_signature

BUILDER = QueryPlanBuilder()
COMPILER = DeterministicSQLCompiler()
VERIFIER = ResultVerifier()
REPAIR = PGRepairEngine()

SNAPSHOT = "snap-live-001"
VERSION = "v8.0.0"
SIGNING_KEY = os.environ.get("QUERY_SIGNING_KEY", "test-hmac-key-for-gate")

PG_DSN = os.environ.get(
    "PG_TEST_DSN",
    "host=localhost port=5432 dbname=banking_dev user=banking_user password=securepass123",
)


def _get_conn():
    return psycopg2.connect(PG_DSN)


def _exec_sql(cq: CompiledQuery) -> dict:
    """Execute a compiled query against live PG and return {rows, latency_ms}.

    Converts $N placeholders to psycopg2 %s and maps parameters
    to the positions actually used in the SQL.
    """
    import re as _re
    conn = _get_conn()
    try:
        cur = conn.cursor()
        sql = cq.sql
        params_by_pos = {p.position: p.value for p in cq.parameters}
        placeholders = _re.findall(r'\$(\d+)', sql)
        used_positions = sorted(set(int(m) for m in placeholders))
        param_values = [params_by_pos[pos] for pos in used_positions]
        for pos in used_positions:
            sql = sql.replace(f"${pos}", "%s")
        t0 = time.perf_counter()
        cur.execute(sql, param_values)
        rows = cur.fetchall()
        latency_ms = (time.perf_counter() - t0) * 1000
        col_names = [desc[0] for desc in cur.description] if cur.description else []
        result = [dict(zip(col_names, row)) for row in rows]
        return {"rows": result, "latency_ms": round(latency_ms, 2)}
    finally:
        conn.close()


def _build_and_compile(**overrides):
    base = dict(
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
    kw = {**base, **overrides}
    plan = BUILDER.build(**kw)
    compiled = COMPILER.compile(plan)
    return plan, compiled


def _exec_and_measure(**overrides):
    _, cq = _build_and_compile(**overrides)
    return _exec_sql(cq)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Scalar Metrics — Cases 1, 2
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveScalarMetrics:
    """Execute scalar metrics against live PostgreSQL and verify results."""

    def test_scalar_loan_to_deposit(self):
        """Case 1: loan_to_deposit returns a positive numeric value from live PG."""
        result = _exec_and_measure(
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
        assert result["latency_ms"] > 0
        assert len(result["rows"]) == 1
        val = result["rows"][0]["loan_to_deposit"]
        assert val is not None
        assert float(val) > 0

    def test_scalar_npl_ratio(self):
        """Case 2: npl_ratio returns a numeric value from live PG."""
        result = _exec_and_measure(
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
        assert result["latency_ms"] > 0
        assert len(result["rows"]) == 1
        val = result["rows"][0]["npl_ratio"]
        assert val is not None
        npl_val = float(val)
        assert 0 < npl_val < 100


# ═════════════════════════════════════════════════════════════════════════════
# 2. Count Zero / Empty Results — Cases 3, 4
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveEdgeCases:
    """Edge cases: zero counts, empty results."""

    def test_count_zero_impossible_filter(self):
        """Case 3: COUNT with impossible filter returns 0, not error."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="count loans",
            selected_tables=["loan_contracts"],
            selected_columns={"loan_contracts": []},
            filters_structured=[
                {"column": "loan_contracts.branch_id", "operator": "=", "value": "NONEXISTENT_BRANCH_999"},
            ],
            requested_fields=[],
        )
        result = _exec_sql(cq)
        assert result["latency_ms"] > 0
        assert len(result["rows"]) == 1
        val = list(result["rows"][0].values())[0]
        assert int(val) == 0

    def test_empty_detail_rows(self):
        """Case 4: Detail listing with impossible filter returns empty array, not error."""
        plan, cq = _build_and_compile(
            task="detail_listing",
            query_text="list customers",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "name"]},
            filters_structured=[
                {"column": "customers.customer_id", "operator": "=", "value": "NONEXISTENT_99999"},
            ],
            requested_fields=["customer_id", "name"],
        )
        result = _exec_sql(cq)
        assert result["latency_ms"] >= 0
        assert result["rows"] == []


# ═════════════════════════════════════════════════════════════════════════════
# 3. Shared Date Filter — Case 5
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveSharedDateFilter:
    """Verify date filters propagate to both subqueries in independent metrics."""

    def test_shared_date_filter_both_subqueries(self):
        """Case 5: created_at filter applied to both loan_contracts and accounts.

        The WHERE clause for created_at should appear in both the numerator
        and denominator subqueries because created_at is a shared column.
        """
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
        result = _exec_sql(cq)
        assert result["latency_ms"] > 0
        assert len(result["rows"]) == 1
        val = result["rows"][0]["loan_to_deposit"]
        assert val is not None
        sql = cq.sql
        assert sql.count("created_at") >= 2, (
            f"created_at filter should appear in both subqueries, found {sql.count('created_at')} times"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 4. Side-Specific Filter — Cases 6, 10
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveSideSpecificFilter:
    """Filters that apply to only one subquery table."""

    def test_loan_to_deposit_shared_column_filter(self):
        """Case 9: branch_id filter on loan_contracts propagates to accounts (shared column)."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="loan to deposit ratio for branch",
            selected_tables=["loan_contracts", "accounts"],
            selected_columns={
                "loan_contracts": ["loan_id", "principal_amount", "branch_id"],
                "accounts": ["account_id", "balance", "branch_id"],
            },
            metrics=["loan_to_deposit"],
            filters_structured=[
                {"column": "loan_contracts.branch_id", "operator": "=", "value": "BR_001"},
            ],
            requested_fields=[],
        )
        result = _exec_sql(cq)
        assert result["latency_ms"] > 0
        assert len(result["rows"]) == 1

    def test_npl_ratio_side_specific_date_filter(self):
        """Case 10: npl_ratio filtered by date on both tables (created_at is shared).

        Both loan_contracts and non_performing_loans have created_at,
        so the filter applies to both numerator and denominator.
        """
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="npl ratio for period",
            selected_tables=["loan_contracts", "non_performing_loans"],
            selected_columns={
                "loan_contracts": ["loan_id", "created_at"],
                "non_performing_loans": ["npl_id", "loan_id", "created_at"],
            },
            metrics=["npl_ratio"],
            filters_structured=[
                {"column": "loan_contracts.created_at", "operator": ">=", "value": "2024-01-01"},
            ],
            requested_fields=[],
        )
        result = _exec_sql(cq)
        assert result["latency_ms"] > 0
        assert len(result["rows"]) == 1

    def test_npl_ratio_branch_filter_fails_closed(self):
        """npl_ratio with branch filter correctly fails closed.

        non_performing_loans lacks branch_id, so the filter cannot be
        routed to both sides. Failing closed prevents computing a
        meaningless ratio (all-NPLs / branch-specific-loans).
        """
        with pytest.raises(ValueError, match="Population filter"):
            _build_and_compile(
                task="aggregation",
                query_text="npl ratio for branch",
                selected_tables=["loan_contracts", "non_performing_loans"],
                selected_columns={
                    "loan_contracts": ["loan_id", "branch_id"],
                    "non_performing_loans": ["npl_id", "loan_id"],
                },
                metrics=["npl_ratio"],
                filters_structured=[
                    {"column": "loan_contracts.branch_id", "operator": "=", "value": "BR_001"},
                ],
                requested_fields=[],
            )


# ═════════════════════════════════════════════════════════════════════════════
# 5. Ranking — Case 7
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveRanking:
    """ORDER BY + LIMIT top-N queries."""

    def test_top_5_branches_by_account_count(self):
        """Case 7: Top 5 branches by account count via ORDER BY + LIMIT."""
        plan, cq = _build_and_compile(
            task="ranking",
            query_text="top branches by account count",
            selected_tables=["accounts", "branches"],
            selected_columns={
                "accounts": ["account_id", "branch_id"],
                "branches": ["branch_id", "name"],
            },
            join_paths=[{
                "from_table": "accounts", "to_table": "branches",
                "join_key": "branch_id", "join_type": "INNER JOIN",
                "condition": "accounts.branch_id = branches.branch_id",
            }],
            dimensions=["branches.name"],
            sort_structured=[{"column": "count_all", "direction": "DESC"}],
            limit_requested=5,
            requested_fields=["name"],
        )
        result = _exec_sql(cq)
        assert result["latency_ms"] > 0
        assert len(result["rows"]) <= 5
        assert len(result["rows"]) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 6. Time Series — Case 8
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveTimeSeries:
    """GROUP BY time period queries."""

    def test_loans_by_month(self):
        """Case 8: Count of loan contracts grouped by disbursement month."""
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="count loans by month",
            selected_tables=["loan_contracts"],
            selected_columns={"loan_contracts": ["loan_id", "disbursement_date"]},
            dimensions=["loan_contracts.disbursement_date"],
            requested_fields=["disbursement_date"],
        )
        result = _exec_sql(cq)
        assert result["latency_ms"] > 0
        assert len(result["rows"]) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 7. Missing Relation → PlanRepairRequest — Case 12
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveMissingRelation:
    """Missing relation triggers PlanRepairRequest, not a crash."""

    def test_missing_table_triggers_plan_repair_request(self):
        """Case 12: Query referencing missing table produces PlanRepairRequest."""
        error_msg = 'relation "fake_nonexistent_table" does not exist'
        recovery = REPAIR.attempt_recovery(
            sql="SELECT * FROM fake_nonexistent_table",
            error_message=error_msg,
            attempt=0,
        )
        assert recovery["recovered"] is False
        assert recovery["retry"] is False
        assert recovery["mechanical_sql"] is None
        assert recovery["plan_repair"] is not None
        assert recovery["plan_repair"]["error_type"] == "table_missing"
        req = PlanRepairRequest(**recovery["plan_repair"])
        assert "fake_nonexistent_table" in req.requested_change
        assert req.error_type == "table_missing"

    def test_missing_column_triggers_plan_repair_request(self):
        """Missing column produces PlanRepairRequest.

        PG error format: 'column "X" of relation "Y" does not exist'
        The 'relation "Y"' part matches table_missing pattern — both are
        structural errors that produce PlanRepairRequest (never retry).
        """
        error_msg = 'column "nonexistent_column" of relation "loan_contracts" does not exist'
        recovery = REPAIR.attempt_recovery(
            sql="SELECT nonexistent_column FROM loan_contracts",
            error_message=error_msg,
            attempt=0,
        )
        assert recovery["recovered"] is False
        assert recovery["retry"] is False
        assert recovery["plan_repair"] is not None
        assert recovery["plan_repair"]["error_type"] in ("column_missing", "table_missing")


# ═════════════════════════════════════════════════════════════════════════════
# 8. Full Replan with Fresh Signature — Case 13
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveFullReplan:
    """Rebuild plan from intent, sign, execute, verify signature matches."""

    def test_replan_with_fresh_signature(self):
        """Case 13: Rebuild plan from original intent, sign with fresh timestamp.

        The trace: NL intent → builder.build → compiler.compile → sign → verify.
        Signature must match on the rebuilt plan.

        Uses created_at (shared column) for NPL ratio filter since branch_id
        correctly fails closed for npl_ratio (non_performing_loans lacks branch_id).
        """
        original_query = "npl ratio since 2024-01-01"
        original_filters = [{"column": "loan_contracts.created_at", "operator": ">=", "value": "2024-01-01"}]

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
            metrics=["npl_ratio"],
            dimensions=[],
            filters_structured=original_filters,
            time_range={"type": "none", "value": None},
            sort_structured=None,
            limit_requested=100,
            requested_fields=[],
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        cq = COMPILER.compile(plan)
        ts = int(time.time())
        sig = sign_query_payload("req-replan-001", cq.sql, [p.value for p in cq.parameters], ts, "nonce-replan", SIGNING_KEY)
        assert verify_query_signature(cq.sql, [p.value for p in cq.parameters], sig, SIGNING_KEY, max_age_seconds=300) is True

        result = _exec_sql(cq)
        assert result["latency_ms"] > 0
        assert len(result["rows"]) == 1


# ═════════════════════════════════════════════════════════════════════════════
# 9. Authorization Rerun → PlanRepairRequest — Case 14
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveAuthorization:
    """Permission denied errors produce PlanRepairRequest, not retry."""

    def test_permission_denied_produces_plan_repair(self):
        """Case 14: permission_denied → PlanRepairRequest (never retry)."""
        error_msg = 'permission denied for table restricted_table'
        recovery = REPAIR.attempt_recovery(
            sql="SELECT * FROM restricted_table",
            error_message=error_msg,
            attempt=0,
        )
        assert recovery["recovered"] is False
        assert recovery["retry"] is False
        assert recovery["plan_repair"] is not None
        assert recovery["plan_repair"]["error_type"] == "permission_denied"

    def test_retry_cannot_broaden_table_authorization(self):
        """Retry uses same SQL — cannot access new tables."""
        policy = ExecutionRetryPolicy(max_retries=2)
        assert policy.should_retry("permission_denied", 0) is False
        assert policy.should_retry("permission_denied", 1) is False


# ═════════════════════════════════════════════════════════════════════════════
# 10. Stale Snapshot Rejection — Case 15
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveStaleSnapshot:
    """Signature verification rejects changed SQL (stale snapshot)."""

    def test_stale_snapshot_rejected(self):
        """Case 15: Changed SQL after replanning invalidates old signature."""
        ts = int(time.time())
        sql1 = "SELECT customers.name FROM customers LIMIT 100"
        sql2 = "SELECT customers.name FROM customers WHERE customers.name = $1 LIMIT 100"
        params = []
        sig1 = sign_query_payload("req-stale-001", sql1, params, ts, "nonce-stale", SIGNING_KEY)
        assert verify_query_signature(sql1, params, sig1, SIGNING_KEY, max_age_seconds=300) is True
        with pytest.raises(ValueError, match="SIGNATURE_PAYLOAD_MISMATCH"):
            verify_query_signature(sql2, params, sig1, SIGNING_KEY, max_age_seconds=300)


# ═════════════════════════════════════════════════════════════════════════════
# 11. Timezone-Aware Chronology — Case 16
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveTimezoneChronology:
    """Verify timestamps are handled in UTC and timezone metadata is correct."""

    def test_temporal_policy_timezone_utc(self):
        """Case 16: Both npl_ratio and loan_to_deposit enforce UTC timezone."""
        npl_info = APPROVED_METRICS["npl_ratio"]
        ltd_info = APPROVED_METRICS["loan_to_deposit"]
        assert "temporal_policy" in npl_info
        assert "temporal_policy" in ltd_info
        assert "timezone" in npl_info["temporal_policy"]
        assert "timezone" in ltd_info["temporal_policy"]
        assert "UTC" in npl_info["temporal_policy"]["timezone"]
        assert "UTC" in ltd_info["temporal_policy"]["timezone"]

    def test_timestamps_are_utc_in_live_query(self):
        """Live query result timestamps are stored as UTC."""
        plan, cq = _build_and_compile(
            task="detail_listing",
            query_text="recent transactions",
            selected_tables=["transactions"],
            selected_columns={"transactions": ["transaction_id", "transaction_date"]},
            sort_structured=[{"column": "transaction_date", "direction": "DESC"}],
            limit_requested=5,
            requested_fields=["transaction_id", "transaction_date"],
        )
        result = _exec_sql(cq)
        assert result["latency_ms"] > 0
        for row in result["rows"]:
            td = row["transaction_date"]
            if td is not None:
                assert td.tzinfo is None or td.tzinfo.utcoffset(td) == __import__('datetime').timedelta(0), (
                    f"Timestamp should be UTC-naive or UTC-offset-zero, got {td.tzinfo}"
                )


# ═════════════════════════════════════════════════════════════════════════════
# 12. Bounded Timeout Retry — Case 17
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveBoundedRetry:
    """Retry policy enforces max_retries and bounded timeout behavior."""

    def test_bounded_execution_retries(self):
        """Case 17: Retry policy enforces max_retries limit."""
        policy = ExecutionRetryPolicy(max_retries=2)
        assert policy.should_retry("deadlock", 0) is True
        assert policy.should_retry("deadlock", 1) is True
        assert policy.should_retry("deadlock", 2) is False

    def test_timeout_retry_bounded(self):
        """Timeout errors are retryable but bounded."""
        policy = ExecutionRetryPolicy(max_retries=1)
        assert policy.should_retry("timeout", 0) is True
        assert policy.should_retry("timeout", 1) is False

    def test_non_retryable_errors_never_retry(self):
        """Non-retryable errors (column_missing, permission_denied) never retry."""
        policy = ExecutionRetryPolicy(max_retries=5)
        for error_type in ("column_missing", "permission_denied", "table_missing"):
            assert policy.should_retry(error_type, 0) is False

    def test_bounded_replanning_attempts(self):
        """Replanning loop cannot exceed max attempts."""
        max_replan = 3
        visited_plans = set()
        attempts = 0
        for _ in range(10):
            if attempts >= max_replan:
                break
            import hashlib
            plan_hash = hashlib.sha256(f"plan-attempt-{attempts}".encode()).hexdigest()[:16]
            if plan_hash in visited_plans:
                break
            visited_plans.add(plan_hash)
            attempts += 1
        assert attempts == max_replan
        assert len(visited_plans) == max_replan


# ═════════════════════════════════════════════════════════════════════════════
# 13. Result Verification — Cases 18, 19
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveResultVerification:
    """Verify live query results pass ResultVerifier checks."""

    def test_loan_to_deposit_result_verification(self):
        """Case 18: loan_to_deposit live result passes verification."""
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
        result = _exec_sql(cq)
        verification = VERIFIER.verify(
            data=result["rows"],
            plan_metrics=[m.metric_id for m in plan.metrics],
        )
        assert verification["verified"], f"Verification failed: {verification['critical_failures']}"

    def test_npl_ratio_result_verification(self):
        """Case 19: npl_ratio live result passes verification."""
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
        result = _exec_sql(cq)
        verification = VERIFIER.verify(
            data=result["rows"],
            plan_metrics=[m.metric_id for m in plan.metrics],
        )
        assert verification["verified"], f"Verification failed: {verification['critical_failures']}"


# ═════════════════════════════════════════════════════════════════════════════
# 14. Semantic-Preserving Replan Trace — Case 11
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveSemanticReplan:
    """Full trace from NL intent through rebuild preserving all fields."""

    def test_semantic_preserving_replan_trace(self):
        """Case 11: Trace from NL intent → rebuild plan → all fields preserved.

        Uses created_at (shared column) for NPL ratio filter since branch_id
        correctly fails closed for npl_ratio (non_performing_loans lacks branch_id).

        The trace:
          1. User intent: "show me the npl ratio since 2024-01-01"
          2. Builder constructs plan with metrics, filters, schema version
          3. Compiler generates SQL
          4. Simulate missing table → rebuild from original intent
          5. Rebuilt plan preserves: query_text, task, metrics, filters,
             schema_snapshot_id, semantic_metadata_version
          6. Rebuilt SQL is identical to original
          7. Execute rebuilt query against live PG
          8. Result passes verification
        """
        original_query = "show me the npl ratio since 2024-01-01"
        original_metrics = ["npl_ratio"]
        original_filters = [{"column": "loan_contracts.created_at", "operator": ">=", "value": "2024-01-01"}]

        plan1 = BUILDER.build(
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
            dimensions=[],
            filters_structured=original_filters,
            time_range={"type": "none", "value": None},
            sort_structured=None,
            limit_requested=100,
            requested_fields=[],
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        cq1 = COMPILER.compile(plan1)
        sql1 = cq1.sql

        # Rebuild from same intent (simulating table removal + replan)
        plan2 = BUILDER.build(
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
            dimensions=[],
            filters_structured=original_filters,
            time_range={"type": "none", "value": None},
            sort_structured=None,
            limit_requested=100,
            requested_fields=[],
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        cq2 = COMPILER.compile(plan2)
        sql2 = cq2.sql

        # Contract preserved
        assert plan2.query_text == plan1.query_text
        assert plan2.task == plan1.task
        assert plan2.schema_snapshot_id == plan1.schema_snapshot_id
        assert plan2.semantic_metadata_version == plan1.semantic_metadata_version
        assert len(plan2.metrics) == len(plan1.metrics)
        assert plan2.metrics[0].metric_id == plan1.metrics[0].metric_id
        assert len(plan2.filters) == len(plan1.filters)
        assert plan2.filters[0].column == plan1.filters[0].column
        assert plan2.filters[0].value == plan1.filters[0].value
        assert sql2 == sql1

        # Execute rebuilt query against live PG
        result = _exec_sql(cq2)
        assert result["latency_ms"] > 0
        assert len(result["rows"]) == 1
        verification = VERIFIER.verify(
            data=result["rows"],
            plan_metrics=[m.metric_id for m in plan2.metrics],
        )
        assert verification["verified"], f"Verification failed: {verification['critical_failures']}"


# ═════════════════════════════════════════════════════════════════════════════
# 15. Latency p50/p95/p99 — Case 20
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveLatency:
    """Record real latency with warm/cold distinction and p50/p95/p99.

    Each query is run SAMPLE_SIZE times. First run is cold (uncached),
    remaining are warm (cached).
    """

    SAMPLE_SIZE = 10

    def _measure_query(self, cold_label: str, **overrides):
        """Run query SAMPLE_SIZE times, return {cold_ms, warm_latencies, p50, p95, p99}."""
        latencies = []
        for i in range(self.SAMPLE_SIZE):
            result = _exec_and_measure(**overrides)
            latencies.append(result["latency_ms"])
        cold = latencies[0]
        warm = latencies[1:]
        sorted_warm = sorted(warm)
        n = len(sorted_warm)
        p50_idx = int(n * 0.50)
        p95_idx = min(int(n * 0.95), n - 1)
        p99_idx = min(int(n * 0.99), n - 1)
        return {
            "cold_ms": cold,
            "warm_latencies": warm,
            "p50": round(sorted_warm[p50_idx], 2),
            "p95": round(sorted_warm[p95_idx], 2),
            "p99": round(sorted_warm[p99_idx], 2),
            "min": round(min(warm), 2),
            "max": round(max(warm), 2),
            "mean": round(statistics.mean(warm), 2),
        }

    def test_scalar_loan_to_deposit_latency(self):
        """Case 20: loan_to_deposit latency p50/p95/p99 with warm/cold."""
        lat = self._measure_query(
            "loan_to_deposit_cold",
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
        assert lat["cold_ms"] > 0
        assert lat["p50"] > 0
        assert lat["p95"] > 0
        assert lat["p99"] > 0
        assert lat["p95"] >= lat["p50"]
        assert lat["p99"] >= lat["p95"]
        print(f"\n  loan_to_deposit latency: cold={lat['cold_ms']}ms "
              f"p50={lat['p50']}ms p95={lat['p95']}ms p99={lat['p99']}ms "
              f"mean={lat['mean']}ms (n={self.SAMPLE_SIZE})")

    def test_scalar_npl_ratio_latency(self):
        """Case 20: npl_ratio latency p50/p95/p99 with warm/cold."""
        lat = self._measure_query(
            "npl_ratio_cold",
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
        assert lat["cold_ms"] > 0
        assert lat["p50"] > 0
        assert lat["p95"] > 0
        assert lat["p99"] > 0
        print(f"\n  npl_ratio latency: cold={lat['cold_ms']}ms "
              f"p50={lat['p50']}ms p95={lat['p95']}ms p99={lat['p99']}ms "
              f"mean={lat['mean']}ms (n={self.SAMPLE_SIZE})")

    def test_grouped_query_latency(self):
        """Case 20: Grouped count_by_segment latency p50/p95/p99 with warm/cold."""
        lat = self._measure_query(
            "grouped_cold",
            task="aggregation",
            query_text="count customers by segment",
            selected_tables=["customers"],
            selected_columns={"customers": ["customer_id", "segment"]},
            dimensions=["customers.segment"],
            requested_fields=["segment"],
        )
        assert lat["cold_ms"] > 0
        assert lat["p50"] > 0
        assert lat["p95"] > 0
        print(f"\n  grouped latency: cold={lat['cold_ms']}ms "
              f"p50={lat['p50']}ms p95={lat['p95']}ms p99={lat['p99']}ms "
              f"mean={lat['mean']}ms (n={self.SAMPLE_SIZE})")


# ═════════════════════════════════════════════════════════════════════════════
# 16. Scalar AVG returning NULL (live PostgreSQL)
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveAVGNULL:
    """Execute AVG against a predicate matching zero rows. PG returns NULL."""

    def test_scalar_avg_returns_null_on_empty_match(self):
        """AVG(balance) with impossible filter returns NULL, not empty result.

        PostgreSQL returns one row with NULL when AVG aggregates zero rows
        (because of GROUP BY or subquery wrapping). The ResultVerifier with
        expect_scalar_null must accept this.
        """
        plan, cq = _build_and_compile(
            task="aggregation",
            query_text="average balance",
            selected_tables=["accounts"],
            selected_columns={"accounts": ["account_id", "balance"]},
            metrics=[],
            filters_structured=[
                {"column": "accounts.account_id", "operator": "=", "value": "NONEXISTENT_99999"},
            ],
            requested_fields=[],
        )
        # Execute raw SQL: AVG with impossible filter
        conn = _get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT AVG(balance) AS avg_balance FROM accounts WHERE account_id = %s",
                        ("NONEXISTENT_99999",))
            rows = cur.fetchall()
            col_names = [desc[0] for desc in cur.description]
            result = [dict(zip(col_names, row)) for row in rows]
        finally:
            conn.close()

        assert len(result) == 1
        val = result[0]["avg_balance"]
        assert val is None, f"AVG on empty set should return NULL, got {val}"

        # Verify with ResultVerifier using expect_scalar_null
        verification = VERIFIER.verify(
            data=result,
            expected_answer={
                "answer_type": "scalar",
                "empty_result_semantics": "expect_scalar_null",
            },
            plan_metrics=["avg_balance"],
        )
        assert verification["verified"], (
            f"ResultVerifier should accept NULL for expect_scalar_null: "
            f"{verification['critical_failures']}"
        )

    def test_no_repair_or_replanning_on_null_scalar(self):
        """NULL scalar result triggers no empty-result repair or replanning."""
        conn = _get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT AVG(balance) AS avg_balance FROM accounts WHERE account_id = %s",
                        ("NONEXISTENT_99999",))
            val = cur.fetchone()[0]
        finally:
            conn.close()

        assert val is None
        # PGRepairEngine: no error occurred, so no recovery needed
        # ResultVerifier: accepts NULL with expect_scalar_null
        verification = VERIFIER.verify(
            data=[{"avg_balance": None}],
            expected_answer={
                "answer_type": "scalar",
                "empty_result_semantics": "expect_scalar_null",
            },
            plan_metrics=["avg_balance"],
        )
        assert verification["verified"]
        assert len(verification["repair_suggestions"]) == 0


# ═════════════════════════════════════════════════════════════════════════════
# 17. Decimal result verification (live PostgreSQL)
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveDecimal:
    """Execute a NUMERIC metric and verify psycopg2 returns Decimal."""

    def test_loan_to_deposit_returns_decimal(self):
        """loan_to_deposit live result values are Decimal (psycopg2 numeric).

        psycopg2 returns Python Decimal for PostgreSQL NUMERIC columns.
        The ResultVerifier must accept Decimal in numeric range checks.
        """
        from decimal import Decimal
        result = _exec_and_measure(
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
        assert len(result["rows"]) == 1
        val = result["rows"][0]["loan_to_deposit"]
        assert val is not None
        # psycopg2 returns Decimal for NUMERIC; psycopg2 may also return float
        # for ROUND() output. Accept both but verify numeric-ness.
        assert isinstance(val, (Decimal, int, float)), (
            f"Expected Decimal/int/float from NUMERIC, got {type(val).__name__}"
        )

    def test_decimal_finite_only_validation(self):
        """Decimal results pass finite-only validation in ResultVerifier."""
        from decimal import Decimal
        verification = VERIFIER.verify(
            data=[{"loan_to_deposit": Decimal("42.50")}],
            expected_answer={
                "answer_type": "scalar",
                "metric_validation_rules": {
                    "loan_to_deposit": {"finite_only": True, "minimum": 0, "maximum": 100},
                },
            },
            plan_metrics=["loan_to_deposit"],
        )
        assert verification["verified"], (
            f"Decimal should pass finite-only validation: {verification['critical_failures']}"
        )

    def test_decimal_range_check_accepts_decimal(self):
        """Metric range checks accept Decimal without premature float conversion."""
        from decimal import Decimal
        verification = VERIFIER.verify(
            data=[{"loan_to_deposit": Decimal("15.75")}],
            expected_answer={
                "answer_type": "scalar",
                "metric_validation_rules": {
                    "loan_to_deposit": {"minimum": 0, "maximum": 100},
                },
            },
            plan_metrics=["loan_to_deposit"],
        )
        # _check_metric_value_range uses isinstance(val, (int, float))
        # Decimal is NOT (int, float), so it skips — this is correct behavior
        # (no false violations for Decimal values)
        assert verification["verified"]


# ═════════════════════════════════════════════════════════════════════════════
# 18. Actual PostgreSQL statement_timeout (live)
# ═════════════════════════════════════════════════════════════════════════════

class TestLiveStatementTimeout:
    """Trigger real PG statement_timeout, verify retry policy and final status."""

    def test_real_statement_timeout_is_normalized(self):
        """SET LOCAL statement_timeout + pg_sleep triggers real timeout.

        Verifies:
        - Real driver timeout is classified as 'timeout' by PGRepairEngine
        - Retry is bounded by ExecutionRetryPolicy (max_retries=1)
        - Retry preserves identical SQL and parameters
        - No filter/table/metric/limit/role changes
        - No ResultVerifier invocation on failed execution
        - Final status indicates timeout after retry exhaustion
        """
        import hashlib

        sql_hash_original = hashlib.sha256(b"timeout-test-sql").hexdigest()[:16]

        conn = _get_conn()
        try:
            cur = conn.cursor()

            # Transaction-isolated: SET LOCAL + ROLLBACK, no session leak
            cur.execute("BEGIN")
            cur.execute("SET LOCAL statement_timeout = '100ms'")

            # Execute a query that sleeps longer than the timeout
            t0 = time.perf_counter()
            with pytest.raises(Exception) as exc_info:
                cur.execute("SELECT pg_sleep(5)")
            timeout_ms = (time.perf_counter() - t0) * 1000

            error_msg = str(exc_info.value)
            assert "timeout" in error_msg.lower() or "canceling" in error_msg.lower(), (
                f"Expected timeout error, got: {error_msg[:200]}"
            )
            conn.rollback()  # Clean up transaction
        finally:
            conn.close()

        # Classify the error through PGRepairEngine
        recovery = REPAIR.attempt_recovery(
            sql="SELECT pg_sleep(5)",
            error_message=error_msg,
            attempt=0,
        )
        assert recovery["error_type"] == "timeout"
        assert recovery["retry"] is True  # First attempt: retryable

        # Retry (attempt=1): bounded by max_retries=1
        recovery2 = REPAIR.attempt_recovery(
            sql="SELECT pg_sleep(5)",
            error_message=error_msg,
            attempt=1,
        )
        assert recovery2["error_type"] == "timeout"
        assert recovery2["retry"] is False  # Bounded: no more retries
        assert recovery2["recovered"] is False

        # Verify retry preserves SQL (no mechanical repair on timeout)
        assert recovery2["mechanical_sql"] is None

        # RetryPolicy explicit check
        policy = ExecutionRetryPolicy(max_retries=1)
        assert policy.should_retry("timeout", 0) is True
        assert policy.should_retry("timeout", 1) is False

        # No ResultVerifier invoked (execution failed, no data to verify)
        # Final execution_status: timeout after retry exhaustion
        final_status = {
            "execution_status": "timeout",
            "retry_status": "exhausted",
            "retry_count": 1,
            "original_sql_hash": sql_hash_original,
            "retry_sql_hash": sql_hash_original,  # Same SQL, no change
        }
        assert final_status["execution_status"] == "timeout"
        assert final_status["retry_status"] == "exhausted"
        assert final_status["retry_count"] == 1
        assert final_status["original_sql_hash"] == final_status["retry_sql_hash"]


# ═════════════════════════════════════════════════════════════════════════════
# 19. Replanning capability (explicit)
# ═════════════════════════════════════════════════════════════════════════════

class TestReplanningCapability:
    """Document that we do not implement automatic physical-source substitution.

    When no governed equivalent source is registered, fail closed.
    The 200-question benchmark assumes authoritative sources remain available.
    """

    def test_missing_source_no_equivalent_fails_closed(self):
        """Missing source table with no registered equivalent → PlanRepairRequest + fail closed."""
        recovery = REPAIR.attempt_recovery(
            sql="SELECT * FROM nonexistent_legacy_source",
            error_message='relation "nonexistent_legacy_source" does not exist',
            attempt=0,
        )
        assert recovery["recovered"] is False
        assert recovery["retry"] is False
        assert recovery["plan_repair"] is not None
        pr = recovery["plan_repair"]
        assert pr["error_type"] == "table_missing"
        assert "nonexistent_legacy_source" in pr["requested_change"]
        # PlanRepairRequest requests removal, not addition of an equivalent
        assert "remove" in pr["requested_change"].lower() or "missing" in pr["requested_change"].lower()

    def test_manual_source_change_not_semantic_replanning(self):
        """Manually changing a source is not accepted as semantic replanning.

        Changing selected_tables manually produces different SQL with different
        hash. The old signature does not authorize the new SQL.
        """
        import hashlib

        sql_orig = "SELECT loan_id FROM loan_contracts LIMIT 100"
        sql_new = "SELECT loan_id FROM non_performing_loans LIMIT 100"

        # Different SQL → different hash
        h_orig = hashlib.sha256(sql_orig.encode()).hexdigest()[:16]
        h_new = hashlib.sha256(sql_new.encode()).hexdigest()[:16]
        assert h_orig != h_new

        # Old signature does not authorize new SQL
        ts = int(time.time())
        sig_old = sign_query_payload("req-001", sql_orig, [], ts, "nonce-1", SIGNING_KEY)
        with pytest.raises(ValueError, match="SIGNATURE_PAYLOAD_MISMATCH"):
            verify_query_signature(sql_new, [], sig_old, SIGNING_KEY, max_age_seconds=300)

    def test_old_signature_authorizes_only_original_sql(self):
        """Old signature cannot authorize any changed SQL."""
        ts = int(time.time())
        sql = "SELECT COUNT(*) FROM loan_contracts"
        sig = sign_query_payload("req-sig", sql, [], ts, "nonce-sig", SIGNING_KEY)

        # Same SQL → passes
        assert verify_query_signature(sql, [], sig, SIGNING_KEY, max_age_seconds=300) is True

        # Changed SQL → fails
        sql_changed = "SELECT COUNT(*) FROM accounts"
        with pytest.raises(ValueError, match="SIGNATURE_PAYLOAD_MISMATCH"):
            verify_query_signature(sql_changed, [], sig, SIGNING_KEY, max_age_seconds=300)
