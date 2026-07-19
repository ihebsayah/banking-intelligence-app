# Increment 3.1 Validation Report

**Date:** 2026-07-19
**Status:** PASS — 141/141 tests green (71 regression + 70 new)

---

## Summary

Increment 3.1 (semantic-preserving execution hardening) implemented across 8 files. All destructive SQL repairs replaced with recovery splitting. Verification expanded to 12 checks with severity levels. Independent subqueries materialized in compiler. PlanRefiner reduced to advisory-only.

---

## Scope Changes Implemented

| # | Scope Item | Status |
|---|-----------|--------|
| 1 | Replace destructive SQL repairs with PlanRepairRequest | ✅ |
| 2 | Split recovery: ExecutionRetryPolicy / SQLMechanicalRepair / PlanRepairRequest | ✅ |
| 3 | Correct PlanRefiner to advisory-only proposals | ✅ |
| 4 | Add empty_result_semantics to ExpectedAnswer | ✅ |
| 5 | Add VerificationSeverity to VerificationCheck | ✅ |
| 6 | Expand ResultVerifier to 12 checks | ✅ |
| 7 | Add MetricValidationRules model | ✅ |
| 8 | Materialize independent_subqueries in compiler | ✅ |
| 9 | Refine response statuses (execution/verification/retry) | ✅ |
| 10 | Preserve execution trace integrity | ✅ |
| 11 | Required tests: 70 total (exceeds 18 minimum) | ✅ |

---

## Files Modified

| File | Change |
|------|--------|
| `services/sql_agent/plan_models.py` | +EmptyResultSemantics, +VerificationSeverity, +MetricValidationRules, +PlanRepairRequest, +ExecutionRetryPolicy, +SQLMechanicalRepair; Updated ExpectedAnswer, VerificationCheck, ResultVerification, PGRepairEngine, PlanRefinement, ExecutionTrace |
| `services/sql_agent/deterministic_compiler.py` | +`_INDEPENDENT_SUBQUERY_REGISTRY`; `_compile_independent_subqueries()` for loan_to_deposit/npl_ratio |
| `services/execution_agent/pg_repair_engine.py` | Rewritten: ExecutionRetryPolicy + SQLMechanicalRepair + PGRepairEngine orchestrator |
| `services/execution_agent/result_verifier.py` | Rewritten: 12 checks with severity, empty-result semantics, metric range, ratio sanity, duplicates, null ratio, ordering |
| `services/execution_agent/plan_refiner.py` | Rewritten: advisory-only proposals (no auto-apply) |
| `services/execution_agent/models.py` | +execution_status, +verification_status, +retry_status, +execution_trace |
| `services/execution_agent/query_executor.py` | +`attempt_recovery()` method |
| `services/execution_agent/main.py` | Updated execute_query with three-way recovery, split statuses |
| `tests/test_increment3_execution.py` | Rewritten: 70 tests across 10 classes |
| `tests/test_increment2_compile.py` | Updated LDR test for independent subqueries |

---

## Test Results

### Increment 3.1 New Tests: 70/70

| Class | Tests | Status |
|-------|-------|--------|
| TestMetricExecutionStrategy | 6 | ✅ |
| TestExpectedAnswer31 | 4 | ✅ |
| TestResultVerifier | 13 | ✅ |
| TestVerifier31Checks | 8 | ✅ |
| TestPGRepairEngine | 14 | ✅ |
| TestPlanRefiner | 6 | ✅ |
| TestIndependentSubqueries | 4 | ✅ |
| TestIntegrationPipeline | 5 | ✅ |
| TestExecutionTrace31 | 4 | ✅ |
| TestIncrement3Deterministic | 2 | ✅ |

### Increment 2 Regression: 71/71

All existing tests in `test_increment2_compile.py` pass. One test updated (LDR compiles as independent subqueries instead of CASE WHEN).

### Total: 141/141 ✅

---

## Unit Performance

| Component | Avg Time (ms) | Notes |
|-----------|--------------|-------|
| ResultVerifier (12 checks) | <1 | Pure dict operations |
| PGRepairEngine.diagnose | <1 | Regex matching |
| PGRepairEngine.attempt_recovery | <1 | Split logic |
| PlanRefiner.refine | <1 | Advisory proposals |
| DeterministicSQLCompiler (independent) | <1 | String formatting |

---

## Database Execution Performance

Not yet benchmarked — Increment 3.1 does not change execution path for non-independent-subquery metrics. Independent subqueries for loan_to_deposit/npl_ratio will be benchmarked in the 200-question benchmark (post-review).

---

## Total Wall-Clock Performance

Not measured in unit tests. All 141 tests complete in 0.28s total.

---

## Key Design Decisions

1. **Destructive repairs → replan request**: Removing JOINs/columns/filters from SQL is never safe. The new `attempt_recovery()` returns a `PlanRepairRequest` that the caller routes back to the planner.

2. **Advisory-only refinement**: PlanRefiner now produces proposals the caller must explicitly accept. No auto-dim-removal, no auto-filter-removal, no auto-LIMIT-1.

3. **Severity-aware verification**: `verified = not critical`. Warnings and informational findings do not block execution. This prevents false negatives from over-sensitive checks.

4. **Independent subqueries in compiler**: loan_to_deposit and npl_ratio are compiled as two independent aggregate subqueries joined on a constant key, eliminating fan-out risk at the SQL level.

5. **Empty-result semantics**: ExpectedAnswer now declares whether empty results are valid (`valid_no_match`, `expect_scalar_zero`, `expect_scalar_null`) or invalid. The verifier respects this instead of blanket-failing on empty results.
