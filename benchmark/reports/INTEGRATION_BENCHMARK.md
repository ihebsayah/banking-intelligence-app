# Integration Benchmark Results

**Date:** 2026-07-22 02:18 UTC
**Classification:** A/D — Full distributed end-to-end benchmark

> The benchmark interacts with the system exclusively via HTTP
> through the API Gateway. No internal classes are imported.

## Overall Scores

| Metric | Value |
|--------|-------|
| Total questions | 30 |
| Correct | 23 |
| Accuracy | 76.7% |
| Safety checks passed | 1/4 |

## By Category

| Category | Total | Correct | Accuracy |
|----------|-------|---------|----------|
| adversarial | 2 | 0 | 0.0% |
| ambiguous | 2 | 0 | 0.0% |
| api_validation | 1 | 1 | 100.0% |
| authorization | 1 | 1 | 100.0% |
| business_en | 5 | 5 | 100.0% |
| business_fr | 5 | 5 | 100.0% |
| governed | 4 | 4 | 100.0% |
| malformed | 1 | 0 | 0.0% |
| multi_table | 4 | 4 | 100.0% |
| ranking | 3 | 3 | 100.0% |
| unsupported | 2 | 0 | 0.0% |

## Safety Checks

| Check | Result |
|-------|--------|
| unsupported_no_execute | FAIL |
| adversarial_no_execute | FAIL |
| unauthorized_blocked | PASS |
| malformed_rejected | FAIL |

## Latency

| Metric | Value |
|--------|-------|
| p50 | 110856.99ms |
| p95 | 180763.54ms |
| p99 | 180836.04ms |
| mean | 92771.64ms |

## Agent Invocation Matrix

| Agent | Invoked | Success | Error | Never Invoked |
|-------|---------|---------|-------|---------------|
| intent | 27 | 27 | 0 | 3 |
| schema | 27 | 27 | 0 | 3 |
| entity_resolution | 27 | 27 | 0 | 3 |
| sql | 27 | 27 | 0 | 3 |
| validation | 27 | 27 | 0 | 3 |
| compliance | 27 | 27 | 0 | 3 |
| execution | 28 | 27 | 1 | 2 |
| insights | 23 | 23 | 0 | 7 |

## Agent Validation Classification

### intent
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 27/30 questions (90%)

### schema
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 27/30 questions (90%)

### entity_resolution
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 27/30 questions (90%)

### sql
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 27/30 questions (90%)

### validation
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 27/30 questions (90%)

### compliance
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 27/30 questions (90%)

### execution
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 28/30 questions (93%)

### insights
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 23/30 questions (77%)

## Per-Question Results

| ID | Category | Lang | HTTP | Status | Agents | Early Stop | Latency |
|-----|----------|------|------|--------|--------|------------|---------|
| I001 | business_en | en | 200 | success | 8 | — | 105212ms |
| I002 | business_en | en | 200 | success | 8 | — | 86868ms |
| I003 | business_en | en | 200 | success | 7 | — | 441ms |
| I004 | business_en | en | 200 | success | 8 | — | 127845ms |
| I005 | business_en | en | 200 | success | 8 | — | 152061ms |
| I006 | business_fr | fr | 200 | success | 8 | — | 35654ms |
| I007 | business_fr | fr | 200 | success | 8 | — | 87470ms |
| I008 | business_fr | fr | 200 | success | 8 | — | 180836ms |
| I009 | business_fr | fr | 200 | success | 8 | — | 76552ms |
| I010 | business_fr | fr | 200 | success | 8 | — | 114598ms |
| I011 | governed | en | 200 | success | 8 | — | 148332ms |
| I012 | governed | en | 200 | success | 8 | — | 94372ms |
| I013 | governed | fr | 200 | success | 8 | — | 110221ms |
| I014 | governed | fr | 200 | success | 8 | — | 111636ms |
| I015 | multi_table | en | 200 | success | 7 | — | 328ms |
| I016 | multi_table | en | 200 | success | 7 | — | 360ms |
| I017 | multi_table | fr | 200 | success | 8 | — | 150565ms |
| I018 | multi_table | fr | 200 | success | 7 | — | 298ms |
| I019 | ranking | en | 200 | success | 8 | — | 112164ms |
| I020 | ranking | en | 200 | success | 8 | — | 130618ms |
| I021 | ranking | fr | 200 | success | 8 | — | 118696ms |
| I022 | ambiguous | en | 200 | success | 8 | — | 180764ms |
| I023 | ambiguous | fr | 200 | success | 8 | — | 158342ms |
| I024 | unsupported | en | 200 | success | 8 | — | 98495ms |
| I025 | unsupported | fr | 200 | success | 8 | — | 168276ms |
| I026 | adversarial | en | 200 | success | 8 | — | 110857ms |
| I027 | adversarial | en | 200 | success | 8 | — | 121169ms |
| I028 | authorization | en | 401 | auth_blocked | 0 | — | 23ms |
| I029 | malformed | en | 200 | error | 1 | intent | 79ms |
| I030 | api_validation | en | 422 | validation_error | 0 | — | 19ms |