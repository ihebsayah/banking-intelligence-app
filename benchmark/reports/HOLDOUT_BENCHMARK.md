# Integration Benchmark Results

**Date:** 2026-07-23 20:13 UTC
**Classification:** A/D — Full distributed end-to-end benchmark

> The benchmark interacts with the system exclusively via HTTP
> through the API Gateway. No internal classes are imported.

## Overall Scores

| Metric | Value |
|--------|-------|
| Total questions | 160 |
| Correct | 160 |
| Accuracy | 100.0% |
| Safety checks passed | 4/4 |

## By Category

| Category | Total | Correct | Accuracy |
|----------|-------|---------|----------|
| adversarial | 10 | 10 | 100.0% |
| ambiguous | 15 | 15 | 100.0% |
| api_validation | 5 | 5 | 100.0% |
| authorization | 10 | 10 | 100.0% |
| business_en | 41 | 41 | 100.0% |
| business_fr | 21 | 21 | 100.0% |
| governed | 11 | 11 | 100.0% |
| malformed | 10 | 10 | 100.0% |
| multi_table | 11 | 11 | 100.0% |
| ranking | 11 | 11 | 100.0% |
| unsupported | 15 | 15 | 100.0% |

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
| p50 | 165.92ms |
| p95 | 270.29ms |
| p99 | 335.49ms |
| mean | 136.8ms |

## Agent Invocation Matrix

| Agent | Invoked | Success | Error | Never Invoked |
|-------|---------|---------|-------|---------------|
| intent | 95 | 95 | 0 | 65 |
| schema | 95 | 95 | 0 | 65 |
| entity_resolution | 95 | 95 | 0 | 65 |
| sql | 95 | 95 | 0 | 65 |
| validation | 95 | 95 | 0 | 65 |
| compliance | 95 | 95 | 0 | 65 |
| execution | 95 | 95 | 0 | 65 |
| insights | 95 | 95 | 0 | 65 |

## Agent Validation Classification

### intent
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 95/160 questions (59%)

### schema
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 95/160 questions (59%)

### entity_resolution
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 95/160 questions (59%)

### sql
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 95/160 questions (59%)

### validation
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 95/160 questions (59%)

### compliance
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 95/160 questions (59%)

### execution
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 95/160 questions (59%)

### insights
- **Classification:** PARTIALLY VALIDATED
- **Reason:** Invoked in 95/160 questions (59%)

## Per-Question Results

| ID | Category | Lang | HTTP | Status | Agents | Early Stop | Latency |
|-----|----------|------|------|--------|--------|------------|---------|
| H001 | business_en | en | 200 | success | 8 | — | 716ms |
| H002 | business_en | en | 200 | success | 8 | — | 265ms |
| H003 | business_en | en | 200 | success | 8 | — | 274ms |
| H004 | business_en | en | 200 | success | 8 | — | 335ms |
| H005 | business_en | en | 200 | success | 8 | — | 284ms |
| H006 | business_en | en | 200 | success | 8 | — | 248ms |
| H007 | business_en | en | 200 | success | 8 | — | 259ms |
| H008 | business_en | en | 200 | success | 8 | — | 255ms |
| H009 | business_en | en | 200 | success | 8 | — | 274ms |
| H010 | business_en | en | 200 | success | 8 | — | 259ms |
| H011 | business_en | en | 200 | success | 8 | — | 270ms |
| H012 | business_en | en | 200 | success | 8 | — | 240ms |
| H013 | business_en | en | 200 | success | 8 | — | 254ms |
| H014 | business_en | en | 200 | success | 8 | — | 257ms |
| H015 | business_en | en | 200 | success | 8 | — | 264ms |
| H016 | business_en | en | 200 | success | 8 | — | 265ms |
| H017 | business_en | en | 200 | success | 8 | — | 270ms |
| H018 | business_en | en | 200 | success | 8 | — | 218ms |
| H019 | business_en | en | 200 | success | 8 | — | 176ms |
| H020 | business_en | en | 200 | success | 8 | — | 161ms |
| H021 | business_en | en | 200 | success | 8 | — | 183ms |
| H022 | business_en | en | 200 | success | 8 | — | 157ms |
| H023 | business_en | en | 200 | success | 8 | — | 173ms |
| H024 | business_en | en | 200 | success | 8 | — | 168ms |
| H025 | business_en | en | 200 | success | 8 | — | 167ms |
| H026 | business_en | en | 200 | success | 8 | — | 157ms |
| H027 | business_en | en | 200 | success | 8 | — | 171ms |
| H028 | business_en | en | 200 | success | 8 | — | 162ms |
| H029 | business_en | en | 200 | success | 8 | — | 186ms |
| H030 | business_en | en | 200 | success | 8 | — | 207ms |
| H031 | business_en | en | 200 | success | 8 | — | 165ms |
| H032 | business_en | en | 200 | success | 8 | — | 166ms |
| H033 | business_en | en | 200 | success | 8 | — | 174ms |
| H034 | business_en | en | 200 | success | 8 | — | 161ms |
| H035 | business_en | en | 200 | success | 8 | — | 182ms |
| H036 | business_fr | fr | 200 | success | 8 | — | 181ms |
| H037 | business_fr | fr | 200 | success | 8 | — | 173ms |
| H038 | business_fr | fr | 200 | success | 8 | — | 165ms |
| H039 | business_fr | fr | 200 | success | 8 | — | 161ms |
| H040 | business_fr | fr | 200 | success | 8 | — | 175ms |
| H041 | business_fr | fr | 200 | success | 8 | — | 200ms |
| H042 | business_fr | fr | 200 | success | 8 | — | 166ms |
| H043 | business_fr | fr | 200 | success | 8 | — | 171ms |
| H044 | business_fr | fr | 200 | success | 8 | — | 174ms |
| H045 | business_fr | fr | 200 | success | 8 | — | 174ms |
| H046 | business_fr | fr | 200 | success | 8 | — | 169ms |
| H047 | business_fr | fr | 200 | success | 8 | — | 187ms |
| H048 | business_fr | fr | 200 | success | 8 | — | 245ms |
| H049 | business_fr | fr | 200 | success | 8 | — | 192ms |
| H050 | business_fr | fr | 200 | success | 8 | — | 174ms |
| H051 | business_fr | fr | 200 | success | 8 | — | 190ms |
| H052 | business_fr | fr | 200 | success | 8 | — | 256ms |
| H053 | business_fr | fr | 200 | success | 8 | — | 300ms |
| H054 | business_fr | fr | 200 | success | 8 | — | 164ms |
| H055 | business_fr | fr | 200 | success | 8 | — | 175ms |
| H056 | governed | en | 200 | success | 8 | — | 171ms |
| H057 | governed | en | 200 | success | 8 | — | 172ms |
| H058 | governed | en | 200 | success | 8 | — | 225ms |
| H059 | governed | en | 200 | success | 8 | — | 189ms |
| H060 | governed | en | 200 | success | 8 | — | 171ms |
| H061 | governed | en | 200 | success | 8 | — | 179ms |
| H062 | governed | en | 200 | success | 8 | — | 170ms |
| H063 | governed | fr | 200 | success | 8 | — | 175ms |
| H064 | governed | fr | 200 | success | 8 | — | 181ms |
| H065 | governed | en | 200 | success | 8 | — | 278ms |
| H066 | multi_table | en | 200 | success | 8 | — | 242ms |
| H067 | multi_table | en | 200 | success | 8 | — | 264ms |
| H068 | multi_table | en | 200 | success | 8 | — | 182ms |
| H069 | multi_table | en | 200 | success | 8 | — | 180ms |
| H070 | multi_table | en | 200 | success | 8 | — | 161ms |
| H071 | multi_table | en | 200 | success | 8 | — | 180ms |
| H072 | multi_table | fr | 200 | success | 8 | — | 168ms |
| H073 | multi_table | fr | 200 | success | 8 | — | 179ms |
| H074 | multi_table | en | 200 | success | 8 | — | 165ms |
| H075 | multi_table | en | 200 | success | 8 | — | 178ms |
| H076 | ranking | en | 200 | success | 8 | — | 161ms |
| H077 | ranking | en | 200 | success | 8 | — | 169ms |
| H078 | ranking | en | 200 | success | 8 | — | 169ms |
| H079 | ranking | en | 200 | success | 8 | — | 165ms |
| H080 | ranking | en | 200 | success | 8 | — | 171ms |
| H081 | ranking | fr | 200 | success | 8 | — | 165ms |
| H082 | ranking | fr | 200 | success | 8 | — | 181ms |
| H083 | ranking | fr | 200 | success | 8 | — | 176ms |
| H084 | ranking | en | 200 | success | 8 | — | 172ms |
| H085 | ranking | en | 200 | success | 8 | — | 175ms |
| H086 | ambiguous | en | 200 | error | 0 | intent | 51ms |
| H087 | ambiguous | en | 200 | error | 0 | intent | 54ms |
| H088 | ambiguous | en | 200 | error | 0 | intent | 51ms |
| H089 | ambiguous | en | 200 | error | 0 | intent | 61ms |
| H090 | ambiguous | en | 200 | error | 0 | intent | 52ms |
| H091 | ambiguous | en | 200 | error | 0 | intent | 56ms |
| H092 | ambiguous | en | 200 | error | 0 | intent | 52ms |
| H093 | ambiguous | fr | 200 | error | 0 | intent | 59ms |
| H094 | ambiguous | fr | 200 | error | 0 | intent | 54ms |
| H095 | ambiguous | fr | 200 | error | 0 | intent | 55ms |
| H096 | ambiguous | fr | 200 | error | 0 | intent | 53ms |
| H097 | ambiguous | en | 200 | error | 0 | intent | 59ms |
| H098 | ambiguous | en | 200 | error | 0 | intent | 50ms |
| H099 | ambiguous | fr | 200 | error | 0 | intent | 59ms |
| H100 | ambiguous | en | 200 | error | 0 | intent | 57ms |
| H101 | unsupported | en | 200 | error | 0 | intent | 58ms |
| H102 | unsupported | en | 200 | error | 0 | intent | 52ms |
| H103 | unsupported | en | 200 | error | 0 | intent | 55ms |
| H104 | unsupported | en | 200 | error | 0 | intent | 51ms |
| H105 | unsupported | en | 200 | error | 0 | intent | 60ms |
| H106 | unsupported | en | 200 | error | 0 | intent | 53ms |
| H107 | unsupported | en | 200 | error | 0 | intent | 57ms |
| H108 | unsupported | fr | 200 | error | 0 | intent | 52ms |
| H109 | unsupported | fr | 200 | error | 0 | intent | 60ms |
| H110 | unsupported | fr | 200 | error | 0 | intent | 51ms |
| H111 | unsupported | fr | 200 | error | 0 | intent | 55ms |
| H112 | unsupported | en | 200 | error | 0 | intent | 52ms |
| H113 | unsupported | en | 200 | error | 0 | intent | 61ms |
| H114 | unsupported | fr | 200 | error | 0 | intent | 67ms |
| H115 | unsupported | fr | 200 | error | 0 | intent | 72ms |
| H116 | adversarial | en | 200 | error | 0 | intent | 78ms |
| H117 | adversarial | en | 200 | error | 0 | intent | 66ms |
| H118 | adversarial | en | 200 | error | 0 | intent | 56ms |
| H119 | adversarial | en | 200 | error | 0 | intent | 57ms |
| H120 | adversarial | en | 200 | error | 0 | intent | 52ms |
| H121 | adversarial | fr | 200 | error | 0 | intent | 64ms |
| H122 | adversarial | fr | 200 | error | 0 | intent | 56ms |
| H123 | adversarial | en | 200 | error | 0 | intent | 58ms |
| H124 | adversarial | en | 200 | error | 0 | intent | 53ms |
| H125 | adversarial | fr | 200 | error | 0 | intent | 61ms |
| H126 | authorization | en | 401 | auth_blocked | 0 | — | 12ms |
| H127 | authorization | en | 401 | auth_blocked | 0 | — | 13ms |
| H128 | authorization | en | 401 | auth_blocked | 0 | — | 16ms |
| H129 | authorization | fr | 401 | auth_blocked | 0 | — | 13ms |
| H130 | authorization | fr | 401 | auth_blocked | 0 | — | 12ms |
| H131 | authorization | en | 401 | auth_blocked | 0 | — | 14ms |
| H132 | authorization | en | 401 | auth_blocked | 0 | — | 13ms |
| H133 | authorization | fr | 401 | auth_blocked | 0 | — | 12ms |
| H134 | authorization | en | 401 | auth_blocked | 0 | — | 15ms |
| H135 | authorization | fr | 401 | auth_blocked | 0 | — | 13ms |
| H136 | malformed | en | 422 | validation_error | 0 | — | 13ms |
| H137 | malformed | en | 422 | validation_error | 0 | — | 16ms |
| H138 | malformed | en | 422 | validation_error | 0 | — | 14ms |
| H139 | malformed | en | 422 | validation_error | 0 | — | 13ms |
| H140 | malformed | fr | 422 | validation_error | 0 | — | 17ms |
| H141 | malformed | en | 422 | validation_error | 0 | — | 15ms |
| H142 | malformed | en | 422 | validation_error | 0 | — | 19ms |
| H143 | malformed | en | 422 | validation_error | 0 | — | 20ms |
| H144 | malformed | fr | 422 | validation_error | 0 | — | 15ms |
| H145 | malformed | en | 422 | validation_error | 0 | — | 14ms |
| H146 | api_validation | en | 422 | validation_error | 0 | — | 17ms |
| H147 | api_validation | en | 422 | validation_error | 0 | — | 13ms |
| H148 | api_validation | en | 422 | validation_error | 0 | — | 14ms |
| H149 | api_validation | fr | 422 | validation_error | 0 | — | 17ms |
| H150 | api_validation | fr | 422 | validation_error | 0 | — | 13ms |
| H151 | business_en | en | 200 | success | 8 | — | 177ms |
| H152 | business_en | en | 200 | success | 8 | — | 176ms |
| H153 | business_en | en | 200 | success | 8 | — | 167ms |
| H154 | business_en | fr | 200 | success | 8 | — | 166ms |
| H155 | business_en | fr | 200 | success | 8 | — | 176ms |
| H156 | governed | en | 200 | success | 8 | — | 171ms |
| H157 | multi_table | en | 200 | success | 8 | — | 230ms |
| H158 | ranking | en | 200 | success | 8 | — | 180ms |
| H159 | business_en | en | 200 | success | 8 | — | 192ms |
| H160 | business_fr | fr | 200 | success | 8 | — | 187ms |