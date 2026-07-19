# Increment 2.5 Validation Report — Analytical Expression Resolution

**Date:** 2026-07-18
**Status:** PASS — 46/46 tests, 96/96 regression suite, zero regressions

---

## 1. What Changed

### Files Modified

| File | Lines Before | Lines After | Delta |
|------|-------------|-------------|-------|
| `services/sql_agent/plan_models.py` | 200 | 200 | 0 |
| `services/sql_agent/query_plan_builder.py` | 765 | 809 | +44 |
| `services/sql_agent/deterministic_compiler.py` | 259 | 259 | 0 |
| `tests/test_increment2_compile.py` | 911 | 911 | 0 |

### Contracts Introduced

| Model | Purpose |
|-------|---------|
| `AggregateExpression` | Typed COUNT/SUM/AVG/MIN/MAX with optional `ColumnRef`, `distinct`, `alias`. Has `to_sql()`. |
| `RatioExpression` | numerator/denominator as `AggregateExpression`, optional `multiply_100`, `alias`. Has `to_sql()`. |
| `AnalyticalExpression` | `Union[AggregateExpression, RatioExpression]` |
| `ExpectedAnswer` | answer_type (scalar/row_set/ranked_list), expected_grain, expected_metrics, expected_dimensions, ordering, aggregation_required, expected_columns |

`QueryPlan` field added: `analytical_expressions: List[AnalyticalExpression]` and `expected_answer: Optional[ExpectedAnswer]`

---

## 2. What We Fixed This Session

Three bugs discovered when running the 46-test suite:

### Bug 1: Substring matching false positive (`query_plan_builder.py:500-515`)
- **Root cause:** `_detect_aggregate_function` used `"count" in q` (substring match). The word `"account"` contains `"count"`, so `"total account balance"` matched `has_count = True` → returned COUNT instead of SUM.
- **Fix:** Replaced all `any(w in q for w in [...])` with word-boundary regex: `re.search(r'\b' + re.escape(w) + r'\b', q)`.

### Bug 2: COUNT picks wrong target column (`query_plan_builder.py:435-476`)
- **Root cause:** `_detect_plain_aggregation` called `_find_target_column` which picked up any column (including dimension columns like `governorate` or numeric fallbacks like `balance`), then applied COUNT to it. "count customers by governorate" → `COUNT(governorate)` instead of `COUNT(*)`.
- **Fix:** Split into `_find_count_target` (skips agg keywords, entity names, and dimension columns — returns `None` for `COUNT(*)`) and a cleaner flow where COUNT always defaults to `COUNT(*)` unless an explicit non-dimension, non-entity column is found.

### Bug 3: SUM picks dimension column (`query_plan_builder.py:578-598`)
- **Root cause:** `_find_target_column` didn't skip dimension columns. "total balance by segment" with `requested_fields=["segment"]` → `SUM(customers.segment)` instead of `SUM(accounts.balance)`.
- **Fix:** Added `dim_set` parameter to `_find_target_column` to skip dimension columns.

### Bug 4: Missing import in tests (`tests/test_increment2_compile.py:31-33`)
- `ColumnRef` was used in 3 test classes but not imported. Added to import block.

---

## 3. Test Results

### Increment 2.5 Tests: 46/46 PASS

```
TestDetailListing              (1)  — detail listing unchanged
TestAggregateOnly              (1)  — SUM without GROUP BY
TestGroupedAggregate           (1)  — AVG by segment
TestMultiDimension             (1)  — two dims
TestRanking                    (1)  — TOP N with ORDER BY
TestNumericFilter              (1)  — GT filter
TestStringFilter               (1)  — equality filter
TestRelativeDate               (1)  — last 30 days
TestRegisteredJoin             (1)  — customer-account join
TestBridgeJoin                 (1)  — three-table join
TestCountStar                  (1)  — COUNT(*) in metric
TestSelectStarRejected         (1)  — SELECT * forbidden
TestUnknownColumn              (2)  — invalid/unresolvable column
TestUnknownMetric              (2)  — invalid metric FAILS plan + compiler rejects
TestUnregisteredJoin           (1)  — invalid join not in plan
TestUnsupportedGrain           (1)  — unsupported grain sets flag
TestMissingRequestedField      (1)  — missing field sets list
TestDeterministicRepeatability (1)  — same plan → same SQL
TestMetadataSnapshotMismatch   (1)  — different snapshots preserved
TestSQLInjectionBound          (1)  — injection value bound as $N
TestCompiledQueryContract      (1)  — required fields present
TestImplicitCount              (2)  — COUNT(*) for "count X" + "count X by Y"
TestImplicitSum                (2)  — SUM for "total X" (EN + FR)
TestImplicitAvg                (1)  — AVG for "average X"
TestImplicitMin                (1)  — MIN for "minimum X"
TestImplicitMax                (1)  — MAX for "highest X"
TestImplicitDistinctCount      (1)  — COUNT(DISTINCT) for "unique X"
TestRankingWithImplicitCount    (1)  — ranking + COUNT(*)
TestRatioExpression            (1)  — loan-to-deposit ratio
TestPercentageExpression       (1)  — percentage with NULLIF/ROUND
TestExpectedAnswerScalar       (2)  — scalar answer type (with/without named metric)
TestExpectedAnswerRowSet       (1)  — grouped answer type
TestExpectedAnswerRankedList   (1)  — ranking answer type
TestExpectedAnswerDetail       (1)  — detail listing (no aggregation)
TestImplicitExpressionSQL      (2)  — SUM+GROUP BY SQL, AVG no dim SQL
TestExpressionTypes            (4)  — AggregateExpression.to_sql(), RatioExpression.to_sql()
TestMultipleMetricsFailFast    (1)  — known+unknown metric fails
```

### Regression Suite: 96/96 PASS

```
test_increment2_compile.py     46/46
test_schema_agent.py           12/12
test_sql_agent.py              15/15
test_validation_agent.py       10/10
test_query_signing.py          13/13
```

---

## 4. Examples

### English (10 examples)

| # | Query | Task | Expression | SQL |
|---|-------|------|------------|-----|
| 1 | "count customers by governorate" | aggregation | COUNT(*) | `SELECT COUNT(*) AS count_all, branches.governorate FROM ... GROUP BY branches.governorate` |
| 2 | "how many accounts" | aggregation | COUNT(*) | `SELECT COUNT(*) AS count_all FROM accounts` |
| 3 | "total account balance" | aggregation | SUM(balance) | `SELECT SUM(accounts.balance) AS sum_balance FROM accounts` |
| 4 | "average balance" | aggregation | AVG(balance) | `SELECT AVG(accounts.balance) AS avg_balance FROM accounts` |
| 5 | "minimum balance" | aggregation | MIN(balance) | `SELECT MIN(accounts.balance) AS min_balance FROM accounts` |
| 6 | "highest balance" | aggregation | MAX(balance) | `SELECT MAX(accounts.balance) AS max_balance FROM accounts` |
| 7 | "unique customer count" | aggregation | COUNT(DISTINCT customer_id) | `SELECT COUNT(DISTINCT customers.customer_id) AS distinct_count_customer_id FROM customers` |
| 8 | "top branches by customer count" | ranking | COUNT(*) | `SELECT COUNT(*) AS count_all, branches.name FROM ... GROUP BY branches.name ORDER BY count_all DESC` |
| 9 | "total balance by segment" | aggregation | SUM(balance) | `SELECT SUM(accounts.balance) AS sum_balance, customers.segment FROM ... GROUP BY customers.segment` |
| 10 | "loan to deposit ratio" | aggregation | RatioExpression | `SELECT ROUND(SUM(lc.principal_amount) / NULLIF(SUM(a.balance), 0), 4) AS loan_to_deposit FROM ...` |

### French (10 examples)

| # | Query | Task | Expression | SQL |
|---|-------|------|------------|-----|
| 11 | "combien de clients par gouvernorat" | aggregation | COUNT(*) | Same pattern as #1 with French text |
| 12 | "somme des dépots" | aggregation | SUM(balance) | `SELECT SUM(accounts.balance) AS sum_balance FROM accounts` |
| 13 | "montant total des prêts" | aggregation | SUM(principal) | `SELECT SUM(loan_contracts.principal_amount) AS sum_principal_amount FROM loan_contracts` |
| 14 | "nombre de comptes" | aggregation | COUNT(*) | `SELECT COUNT(*) AS count_all FROM accounts` |
| 15 | "moyenne des soldes" | aggregation | AVG(balance) | `SELECT AVG(accounts.balance) AS avg_balance FROM accounts` |
| 16 | "solde minimum" | aggregation | MIN(balance) | `SELECT MIN(accounts.balance) AS min_balance FROM accounts` |
| 17 | "solde maximum" | aggregation | MAX(balance) | `SELECT MAX(accounts.balance) AS max_balance FROM accounts` |
| 18 | "clients uniques par branche" | aggregation | COUNT(DISTINCT) | `SELECT COUNT(DISTINCT customers.customer_id) ...` |
| 19 | "pourcentage de clients vérifiés" | aggregation | RatioExpression | `SELECT ROUND(100.0 * COUNT(c.kyc_verified) / NULLIF(COUNT(*), 0), 2) AS percentage FROM customers` |
| 20 | "nombre total par type de compte" | ranking | COUNT(*) | `SELECT COUNT(*) AS count_all, accounts.account_type FROM accounts GROUP BY accounts.account_type` |

---

## 5. Unsupported / Fail-Fast Cases

| Query | Behavior | Reason |
|-------|----------|--------|
| `"fake_metric"` as metric | Plan FAILS with `unsupported_reason` | Not in `APPROVED_METRICS` registry |
| Unknown column in `requested_fields` | Plan FAILS with `missing_requested_fields` | Not in `_VALID_COLUMNS` |
| Unknown join path | Plan FAILS — no JoinSpec added | Not in `join_registry` |
| SELECT * (bare) | Compiler raises `ValueError` | Forbidden rule |
| `npl_ratio` at `segment` grain | `grain_supported=False` on MetricReference | Segment not in allowed grains |

---

## 6. Known Pre-existing Failures (not caused by this work)

| Test | Root Cause |
|------|------------|
| `test_intent_agent.py` (2 tests) | `spacy` not installed |
| `test_portal.py` (3 tests) | `fastapi` not installed |
| `test_insights.py` (1 test) | `numpy` not installed |
| Compliance agent logic bug | Pre-existing in `compliance_agent.py` — unrelated to Increment 2.5 |

---

## 7. Architecture Notes

**Builder owns all decisions, compiler is a pure renderer:**
- `QueryPlanBuilder._resolve_implicit_aggregation()` → detects ratio/percentage first (highest priority), then plain aggregation (COUNT/SUM/AVG/MIN/MAX/DISTINCT_COUNT)
- `_detect_aggregate_function()` uses word-boundary regex to avoid false positives (e.g., "account" ≠ "count")
- `_find_count_target()` only returns a column if explicitly requested and not a dimension/entity; otherwise returns `None` → `COUNT(*)`
- `_build_expected_answer()` generates `ExpectedAnswer` with answer_type, grain, metrics, dims, ordering, aggregation_required
- `DeterministicSQLCompiler._compile_select()` reads `plan.analytical_expressions` and calls `expr.to_sql()` — no inference

**Unknown metrics → FAIL (not silent drop):**
- `_validate_metrics()` returns error string on unknown metric ID
- Plan created with `unsupported_reason` set
- Compiler raises `ValueError` on compile attempt

---

## 8. Technical Debt Logged

- Cross-service `sys.path` injection pattern in test files (should use package installs)
- `_VALID_COLUMNS` whitelist is static; no runtime DB introspection
- `_NUMERIC_HINTS` fallback for non-COUNT aggregates could be replaced with column type metadata
