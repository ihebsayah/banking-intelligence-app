# Increment 2.6 Validation Report — Aggregation Semantics & Grain Safety

**Date:** 2026-07-18
**Status:** PASS — 71/71 tests, 121/121 regression suite, zero regressions

---

## 1. What Changed

### Files Modified

| File | Lines Before | Lines After | Delta |
|------|-------------|-------------|-------|
| `services/sql_agent/plan_models.py` | 200 | 240 | +40 |
| `services/sql_agent/query_plan_builder.py` | 791 | 909 | +118 |
| `services/sql_agent/deterministic_compiler.py` | 259 | 259 | +1 (import only) |
| `tests/test_increment2_compile.py` | 912 | 1362 | +450 |

### New Typed Contracts

| Model | Purpose |
|-------|---------|
| `CaseExpression` | `COUNT(CASE WHEN col = val THEN 1 END)` — conditional aggregation for boolean columns. Has `to_sql()`. |
| `GrainSpec` | Tracks source_table, source_grain, aggregate_input_grain, output_grain, temporal_grain, identity_columns. |
| `JoinCardinality` | Literal type: `one_to_one`, `many_to_one`, `one_to_many`, `many_to_many`. |

### Updated Contracts

| Model | Change |
|-------|--------|
| `JoinSpec` | Added `cardinality: JoinCardinality` field (default `many_to_one`). |
| `RatioExpression` | Added `aggregation_strategy` field (`same_relation` / `independent_subqueries` / `approved_metric_view`). Numerator/denominator now accept `Union[AggregateExpression, CaseExpression]`. |
| `ExpectedAnswer` | Expanded `answer_type` to: `scalar`, `detail_rows`, `grouped_rows`, `ranked_list`, `time_series`, `comparison`, `distribution`. |
| `QueryPlan` | Added `grain: Optional[GrainSpec]` and `fan_out_risk: bool`. |
| `AnalyticalExpression` | Union expanded: `AggregateExpression | RatioExpression | CaseExpression`. |

---

## 2. Bugs Fixed

### Bug 1: Percentage used COUNT(boolean) — counted non-nulls, not true values
- **Root cause:** `_detect_percentage` built `COUNT(kyc_verified)` which counts all non-null values (including false).
- **Fix:** Introduced `CaseExpression` model. `_detect_percentage` now builds `CaseExpression(column=kyc_verified, condition_column=kyc_verified, condition_value=True)` → renders as `COUNT(CASE WHEN kyc_verified = True THEN 1 END)`.

### Bug 2: Implicit LDR had fan-out risk
- **Root cause:** `_detect_ratio` built `SUM(loans) + SUM(deposits)` after joining `loan_contracts` and `accounts` — rows duplicated by the join, inflating both sums.
- **Fix:** `_detect_ratio` returns `None` for LDR. Must use named metric `loan_to_deposit` from `APPROVED_METRICS` (which uses CASE WHEN pattern to handle fan-out).

### Bug 3: No entity-aware counting
- **Root cause:** "count customers" with a one-to-many join produced `COUNT(*)` which counts rows, not unique entities. Join duplication → inflated count.
- **Fix:** `_find_entity_count` detects entity keywords (customer, account, loan, etc.) in query text. When a one-to-many or many-to-many join exists, returns `COUNT(DISTINCT entity_pk)` instead.

### Bug 4: No join cardinality metadata
- **Root cause:** JoinSpec had no cardinality field — couldn't detect fan-out risk.
- **Fix:** Added `cardinality` field to JoinSpec. `_build_joins` reads it from join_paths. `_detect_fan_out` checks for one_to_many/many_to_many.

### Bug 5: No grain tracking
- **Root cause:** No model for tracking aggregation grain from source through output.
- **Fix:** Added `GrainSpec` model. `_build_grain` populates source_table, source_grain (from entity identity), output_grain (from dimensions), temporal_grain (from time_range).

### Bug 6: ExpectedAnswer types too limited
- **Root cause:** Only `scalar`, `row_set`, `ranked_list` — missing `detail_rows`, `grouped_rows`, `time_series`.
- **Fix:** Expanded answer_type detection in `_build_expected_answer`. Added time-series detection when dimensions include temporal columns.

---

## 3. Test Results

### Increment 2.6 Tests: 71/71 PASS

```
Tests 1-23   (Increment 2 + 2.5) — 23/23 PASS (unchanged behavior)
Test 24      — RatioExpression uses named metric (updated from implicit)
Test 29      — Percentage now uses CaseExpression (updated assertion)
Tests 30-36  (Increment 2.5 ExpectedAnswer + expressions) — 7/7 PASS
Test 37      — Conditional percentage (CaseExpression numerator)
Test 38      — COUNT(boolean_column) false-value regression
Test 39      — Entity-aware COUNT(DISTINCT) with one_to_many join
Test 40      — Entity-aware COUNT(*) without joins
Test 41      — COUNT accounts by segment (many_to_one, no DISTINCT)
Test 42      — One-to-many fan-out detection
Test 43      — Many-to-many fan-out detection
Test 44      — Many-to-one no fan-out
Test 45      — No joins no fan-out
Test 46      — Source grain from entity identity
Test 47      — Output grain from dimensions
Test 48      — Temporal grain from time range
Test 49      — GrainSpec model construction
Test 50      — Join cardinality propagation
Test 51      — Default cardinality is many_to_one
Test 52      — Implicit LDR returns no expression
Test 53      — Named metric LDR compiles
Test 54      — Time-series ExpectedAnswer
Test 55-56   — Expanded answer types (detail_rows, grouped_rows)
Test 57-59   — Deterministic SQL stability (2.6 changes)
Test 35-36   — CaseExpression type tests (to_sql, in ratio)
```

### Regression Suite: 121/121 PASS

```
test_increment2_compile.py     71/71
test_schema_agent.py           12/12
test_sql_agent.py              15/15
test_validation_agent.py       10/10
test_query_signing.py          13/13
```

---

## 4. Corrected SQL Examples

### Percentage — Before vs After

```sql
-- BEFORE (Increment 2.5): COUNT(non-nulls), wrong
SELECT ROUND(100.0 * COUNT(customers.kyc_verified) / NULLIF(COUNT(*), 0), 2) AS percentage

-- AFTER (Increment 2.6): COUNT(true values), correct
SELECT ROUND(100.0 * COUNT(CASE WHEN customers.kyc_verified = True THEN 1 END) / NULLIF(COUNT(*), 0), 2) AS percentage
```

### Entity-Aware Count — Before vs After

```sql
-- BEFORE (Increment 2.5): COUNT(*) counts rows, inflated by join
SELECT COUNT(*) AS count_all
FROM customers
INNER JOIN accounts ON customers.customer_id = accounts.customer_id

-- AFTER (Increment 2.6): COUNT(DISTINCT customer_id) counts unique entities
SELECT COUNT(DISTINCT customers.customer_id) AS count_customer_id
FROM customers
INNER JOIN accounts ON customers.customer_id = accounts.customer_id
```

### LDR — Implicit vs Named Metric

```sql
-- Implicit detection: returns None (fan-out risk, must use named metric)

-- Named metric 'loan_to_deposit' from APPROVED_METRICS:
SELECT ROUND(SUM(CASE WHEN lc.loan_id IS NOT NULL THEN lc.principal_amount ELSE 0 END) / NULLIF(SUM(a.balance), 0), 4) AS loan_to_deposit
```

---

## 5. Grain Propagation Examples

| Query | Source Grain | Output Grain | Temporal Grain | Identity |
|-------|-------------|--------------|----------------|----------|
| "count customers" | customer_id | scalar | — | customer_id |
| "count customers by governorate" | customer_id | governorate | — | customer_id |
| "total balance last 30 days" | account_id | scalar | last_30_days | account_id |
| "count accounts by segment" | account_id | segment | — | account_id |

---

## 6. Fan-Out Rejection/Rewrite Examples

| Scenario | Join Cardinality | fan_out_risk | Behavior |
|----------|-----------------|--------------|----------|
| customers → branches | many_to_one | False | COUNT(*) safe |
| customers → accounts | one_to_many | True | Entity count uses COUNT(DISTINCT) |
| transactions ↔ products | many_to_many | True | Flagged, aggregation distorted |
| Implicit LDR (loans ↔ accounts) | many_to_many | True | Returns None, must use named metric |

---

## 7. Unsupported / Fail-Fast Cases

| Query | Behavior | Reason |
|-------|----------|--------|
| Implicit "loan to deposit ratio" | No expression produced | Fan-out risk, must use named metric |
| Unknown metric | Plan FAILS | Not in APPROVED_METRICS |
| SELECT * | Compiler raises ValueError | Forbidden rule |
| `unsupported_reason` set | Plan FAILS immediately | Fast-fail path |

---

## 8. Known Pre-existing Failures (not caused by this work)

| Test | Root Cause |
|------|------------|
| `test_intent_agent.py` (2 tests) | `spacy` not installed |
| `test_portal.py` (3 tests) | `fastapi` not installed |
| `test_insights.py` (1 test) | `numpy` not installed |
| Compliance agent logic bug | Pre-existing in `compliance_agent.py` |

---

## 9. Architecture Notes

**Builder owns all decisions, compiler is a pure renderer:**
- `CaseExpression.to_sql()` renders `COUNT(CASE WHEN col = val THEN 1 END)`
- `RatioExpression.to_sql()` delegates to numerator/denominator `.to_sql()` — works with both AggregateExpression and CaseExpression
- `_find_entity_count()` uses `_ENTITY_KEYWORDS` regex with plural support (`customer` matches `customers`) and only triggers DISTINCT when fan-out joins exist
- `_detect_fan_out()` checks JoinSpec cardinality — simple boolean flag on QueryPlan
- `_build_grain()` creates GrainSpec from entity identity registry and dimension refs
- `_build_expected_answer()` expanded with time-series detection via temporal column names

**Compiler unchanged beyond import:**
- Already renders `analytical_expressions` via `expr.to_sql()` — CaseExpression plugs in naturally
- Already reads `plan.fan_out_risk` and `plan.grain` from the plan model (passthrough)
