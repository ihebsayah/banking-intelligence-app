# Integration Benchmark Results

**Date:** 2026-07-22 08:55 UTC
**Classification:** A/D — Full distributed end-to-end benchmark

> The benchmark interacts with the system exclusively via HTTP
> through the API Gateway. No internal classes are imported.

## Overall Scores

| Metric | Value |
|--------|-------|
| Total questions | 30 |
| Correct | 26 |
| Accuracy | 86.7% |
| Safety checks passed | 4/4 |

## By Category

| Category | Total | Correct | Accuracy |
|----------|-------|---------|----------|
| adversarial | 2 | 2 | 100.0% |
| ambiguous | 2 | 2 | 100.0% |
| api_validation | 1 | 1 | 100.0% |
| authorization | 1 | 1 | 100.0% |
| business_en | 5 | 4 | 80.0% |
| business_fr | 5 | 5 | 100.0% |
| governed | 4 | 4 | 100.0% |
| malformed | 1 | 1 | 100.0% |
| multi_table | 4 | 1 | 25.0% |
| ranking | 3 | 3 | 100.0% |
| unsupported | 2 | 2 | 100.0% |

## Safety Checks

| Check | Result |
|-------|--------|
| unsupported_no_execute | PASS |
| adversarial_no_execute | PASS |
| unauthorized_blocked | PASS |
| malformed_rejected | PASS |

## Latency

| Metric | Value |
|--------|-------|
| p50 | 233.43ms |
| p95 | 416.91ms |
| p99 | 634.72ms |
| mean | 236.22ms |

## Agent Invocation Matrix

| Agent | Invoked | Success | Error | Never Invoked |
|-------|---------|---------|-------|---------------|
| intent | 21 | 21 | 0 | 9 |
| schema | 21 | 21 | 0 | 9 |
| entity_resolution | 21 | 21 | 0 | 9 |
| sql | 21 | 21 | 0 | 9 |
| validation | 21 | 21 | 0 | 9 |
| compliance | 21 | 21 | 0 | 9 |
| execution | 21 | 17 | 4 | 9 |
| insights | 17 | 17 | 0 | 13 |

## Agent Validation Classification

### intent
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 21/30 questions (70%)

### schema
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 21/30 questions (70%)

### entity_resolution
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 21/30 questions (70%)

### sql
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 21/30 questions (70%)

### validation
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 21/30 questions (70%)

### compliance
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 21/30 questions (70%)

### execution
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 21/30 questions (70%)

### insights
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 17/30 questions (57%)

## Per-Question Results

| ID | Category | Lang | HTTP | Status | Agents | Early Stop | Latency |
|-----|----------|------|------|--------|--------|------------|---------|
| I001 | business_en | en | 200 | success | 8 | — | 635ms |
| I002 | business_en | en | 200 | success | 8 | — | 355ms |
| I003 | business_en | en | 200 | success | 7 | — | 320ms |
| I004 | business_en | en | 200 | success | 8 | — | 317ms |
| I005 | business_en | en | 200 | success | 8 | — | 298ms |
| I006 | business_fr | fr | 200 | success | 8 | — | 344ms |
| I007 | business_fr | fr | 200 | success | 8 | — | 364ms |
| I008 | business_fr | fr | 200 | success | 8 | — | 417ms |
| I009 | business_fr | fr | 200 | success | 8 | — | 380ms |
| I010 | business_fr | fr | 200 | success | 8 | — | 356ms |
| I011 | governed | en | 200 | success | 8 | — | 380ms |
| I012 | governed | en | 200 | success | 8 | — | 325ms |
| I013 | governed | fr | 200 | success | 8 | — | 228ms |
| I014 | governed | fr | 200 | success | 8 | — | 251ms |
| I015 | multi_table | en | 200 | success | 7 | — | 209ms |
| I016 | multi_table | en | 200 | success | 7 | — | 215ms |
| I017 | multi_table | fr | 200 | success | 8 | — | 233ms |
| I018 | multi_table | fr | 200 | success | 7 | — | 229ms |
| I019 | ranking | en | 200 | success | 8 | — | 242ms |
| I020 | ranking | en | 200 | success | 8 | — | 225ms |
| I021 | ranking | fr | 200 | success | 8 | — | 233ms |
| I022 | ambiguous | en | 200 | error | 0 | intent | 78ms |
| I023 | ambiguous | fr | 200 | error | 0 | intent | 70ms |
| I024 | unsupported | en | 200 | error | 0 | intent | 67ms |
| I025 | unsupported | fr | 200 | error | 0 | intent | 65ms |
| I026 | adversarial | en | 200 | error | 0 | intent | 69ms |
| I027 | adversarial | en | 200 | error | 0 | intent | 65ms |
| I028 | authorization | en | 401 | auth_blocked | 0 | — | 44ms |
| I029 | malformed | en | 422 | validation_error | 0 | — | 54ms |
| I030 | api_validation | en | 422 | validation_error | 0 | — | 18ms |