# INCREMENT 1 — SEMANTIC CORRECTIONS REPORT

## Summary

All 8 semantic corrections requested by the user have been implemented. The full relevant test suite (148 tests across 12 test files) passes with **0 Phase 6C-related failures**. One pre-existing failure exists in `test_compliance_agent.py::test_role_allowed_not_in` (unrelated).

## Corrections Implemented

### 1. Business concepts separated from metrics
**File:** `services/intent_agent/structured_intent.py`

- "NPL accounts" no longer triggers `npl_ratio` — requires explicit analytical trigger (rate, ratio, total, count)
- "AML alerts" no longer triggers `aml_alert_rate` — requires explicit trigger
- Positive vs negative metric detection regression tests added

### 2. Improved task inference
**File:** `services/intent_agent/structured_intent.py`

- "par gouvernorat", "by branch", "par segment" with an explicit measure → `aggregation`
- Plain listing queries (no measure, no aggregation trigger) → `detail_listing`
- Tests verify both paths

### 3. requested_fields added to structured intent
**File:** `services/intent_agent/structured_intent.py`, `services/schema_agent/progressive_schema.py`

- `extract_requested_fields()` preserves every output field explicitly requested
- Schema selection reports `missing_requested_fields` instead of silently omitting
- Test: `nonexistent_field` reported as missing, `name` found when present in metadata

### 4. Metric grain compatibility
**File:** `services/schema_agent/progressive_schema.py`

- PNB by account type → `unsupported` (metric doesn't support that grain)
- ROE/ROA by branch/governorate → `unsupported` (only supports time dimension)
- Test: `test_metric_grain_compatibility`

### 5. Temporal source capability validation
**File:** `services/schema_agent/progressive_schema.py`

- Historical questions select sources with valid date/period fields
- KYC compliance rate historically → replaces `customers` with `kyc_cases`
- Test: `test_temporal_source_capability`

### 6. Authoritative source priority
**File:** `services/schema_agent/progressive_schema.py`

- Authoritative analytical views (weight ≥3.0) ranked higher than operational tables (weight 2.0) for same metric
- Metric source tables selected before primary operational tables
- Selection order preserves candidate ranking (not set-unordered)
- Test: `test_authoritative_source_priority`

### 7. Review and corrected examples
All 7 examples from user request corrected:

| Example | Corrected Behavior |
|---|---|
| List NPL accounts with DPD > 90 | `domain: credit_risk`, `metrics: []`, `requested_fields: [npl, loan_id, days_past_due]` |
| Créances douteuses par gouvernorat | `domain: credit_risk`, `task: aggregation`, `dimensions: [governorate]` |
| Compliance audits count by branch | `metrics: []`, `task: aggregation`, not `compliance_audit_rate` |
| KYC compliance rate by branch last year | `metrics: [kyc_compliance_rate]`, `task: aggregation` |
| AML alerts and suspicious activity report history | `requested_fields: [aml_alerts, sar]`, no metric trigger |
| PNB by account type | `unsupported_reason: PNB metric does not support account_type grain` |
| Risk score and active status for customers | `requested_fields: [risk_score, status]`, no metric trigger |

### 8. Semantic regression tests
**File:** `tests/test_intent_agent.py`

- `test_metric_separation_positive_vs_negative` — 8 assertions covering NPL, AML, PNB detection vs non-detection
- `test_task_inference_grouping_vs_listing` — 4 assertions for aggregation vs listing
- `test_requested_fields_extraction` — 3 assertions for field extraction

**File:** `tests/test_schema_agent.py`

- `test_metric_grain_compatibility` — PNB and ROE grain incompatibility
- `test_temporal_source_capability` — Historical source replacement
- `test_authoritative_source_priority` — Analytical view priority
- `test_requested_fields_reporting` — Missing field detection

## Files Modified

| File | Change |
|---|---|
| `services/intent_agent/structured_intent.py` | Separated concepts from metrics, improved task inference, added requested_fields extraction |
| `services/schema_agent/progressive_schema.py` | Metric grain validation, temporal source checks, authoritative source priority, requested_fields column matching, fixed selection ordering |
| `services/schema_agent/schema_matcher.py` | Added `requested_fields` and `intent` params to `progressive_map`, fixed cross-service import |
| `services/intent_agent/intent_recognizer.py` | Fixed cross-service import path |
| `tests/test_intent_agent.py` | Added 3 semantic regression tests (16+ assertions) |
| `tests/test_schema_agent.py` | Added 4 schema selection regression tests, fixed test setup for mock metadata |

## Test Results

```
149 tests collected
148 passed, 1 failed (pre-existing, unrelated)

Phase 6C tests: 34/34 pass
  - test_intent_agent.py: 17/17 pass
  - test_schema_agent.py: 17/17 pass
Integration tests: 15/15 pass
Phase 6B tests: 12/12 pass
Phase 6B.1 tests: 12/12 pass
Compliance tests: 14/15 pass (1 pre-existing failure)
Entity resolution: 10/10 pass
SQL agent: 12/12 pass
Validation agent: 10/10 pass
Execution agent: 10/10 pass
```

## Key Design Decisions

1. **Metric detection requires analytical triggers** — "npl accounts" ≠ "npl ratio". Only rate/ratio/total/average/count/exposure/balance trigger metric detection.
2. **Selection order preserved** — `selected_tables` now respects candidate ranking order instead of set-unordered behavior, ensuring authoritative tables appear first.
3. **Grain validation blocks early** — Incompatible metric+dimension combos return `unsupported_reason` before schema selection, avoiding wasted work.
4. **Cross-service imports hardened** — Both `intent_recognizer.py` and `schema_matcher.py` now use `__file__`-relative path injection, surviving full-suite test runs with `sys.path` pollution.

## Status

- [x] All semantic corrections implemented
- [x] All relevant tests passing
- [x] Ready for review
- [ ] Not yet implementing QueryPlanBuilder or DeterministicSQLCompiler (per user constraint)
