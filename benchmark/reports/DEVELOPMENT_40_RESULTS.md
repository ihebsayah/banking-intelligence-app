# Development 40-Question Benchmark Results

**Run:** development_run_2
**Date:** 2026-07-20

## Overall Scores

| Metric | Value |
|--------|-------|
| End-to-end score | 100.0% |
| Supported-question accuracy | 100.0% |
| Correct unsupported rate | 100.0% |
| Unsafe executions | 0 |
| Adversarial SQL executions | 0 |

## By Category

| Category | Total | Correct | Accuracy |
|----------|-------|---------|----------|
| adversarial | 2 | 2 | 100.0% |
| ambiguous | 3 | 3 | 100.0% |
| filters | 5 | 5 | 100.0% |
| governed | 5 | 5 | 100.0% |
| grouped | 5 | 5 | 100.0% |
| multi_table | 4 | 4 | 100.0% |
| ranking | 4 | 4 | 100.0% |
| scalar | 5 | 5 | 100.0% |
| time_series | 4 | 4 | 100.0% |
| unsupported | 3 | 3 | 100.0% |

## By Language

| Language | Total | Correct | Accuracy |
|----------|-------|---------|----------|
| en | 25 | 25 | 100.0% |
| fr | 15 | 15 | 100.0% |

## By Difficulty

| Difficulty | Total | Correct | Accuracy |
|------------|-------|---------|----------|
| easy | 9 | 9 | 100.0% |
| hard | 14 | 14 | 100.0% |
| medium | 17 | 17 | 100.0% |

## Latency

| Metric | Value |
|--------|-------|
| p50 total | 12.8ms |
| p95 total | 17.24ms |
| p99 total | 38.6ms |
| mean total | 13.8ms |

## Failure Stages

- **authorization**: 1
- **clarification_or_semantic_planning**: 3
- **semantic_planning**: 4

## Per-Question Results

| ID | Category | Lang | Diff | Supported | Answer | Failure | Latency |
|-----|----------|------|------|-----------|--------|---------|---------|
| D001 | scalar | en | easy | Y | PASS | — | 15.33ms |
| D002 | scalar | fr | easy | Y | PASS | — | 14.87ms |
| D003 | scalar | en | easy | Y | PASS | — | 12.27ms |
| D004 | scalar | fr | easy | Y | PASS | — | 11.45ms |
| D005 | scalar | en | easy | Y | PASS | — | 12.34ms |
| D006 | grouped | en | easy | Y | PASS | — | 12.76ms |
| D007 | grouped | fr | easy | Y | PASS | — | 12.64ms |
| D008 | grouped | en | medium | Y | PASS | — | 12.56ms |
| D009 | grouped | fr | easy | Y | PASS | — | 13.79ms |
| D010 | grouped | en | medium | Y | PASS | — | 17.24ms |
| D011 | filters | en | medium | Y | PASS | — | 12.15ms |
| D012 | filters | fr | medium | Y | PASS | — | 12.75ms |
| D013 | filters | en | medium | Y | PASS | — | 38.6ms |
| D014 | filters | fr | hard | Y | PASS | — | 15.67ms |
| D015 | filters | en | hard | Y | PASS | — | 12.79ms |
| D016 | ranking | en | medium | Y | PASS | — | 11.81ms |
| D017 | ranking | fr | easy | Y | PASS | — | 15.2ms |
| D018 | ranking | en | medium | Y | PASS | — | 14.64ms |
| D019 | ranking | en | hard | Y | PASS | — | 14.78ms |
| D020 | time_series | en | medium | Y | PASS | — | 14.56ms |
| D021 | time_series | fr | medium | Y | PASS | — | 13.42ms |
| D022 | time_series | en | medium | Y | PASS | — | 11.74ms |
| D023 | time_series | fr | medium | Y | PASS | — | 12.8ms |
| D024 | governed | en | hard | Y | PASS | — | 16.17ms |
| D025 | governed | fr | hard | Y | PASS | — | 13.87ms |
| D026 | governed | en | medium | Y | PASS | — | 13.33ms |
| D027 | governed | fr | medium | Y | PASS | — | 13.43ms |
| D028 | governed | en | hard | Y | PASS | — | 12.12ms |
| D029 | multi_table | en | hard | Y | PASS | — | 16.77ms |
| D030 | multi_table | fr | hard | Y | PASS | — | 14.94ms |
| D031 | multi_table | en | hard | Y | PASS | — | 16.97ms |
| D032 | multi_table | fr | hard | Y | PASS | — | 14.87ms |
| D033 | ambiguous | en | medium | N | PASS | clarification_or_semantic_planning | 10.1ms |
| D034 | ambiguous | fr | medium | N | PASS | clarification_or_semantic_planning | 10.71ms |
| D035 | ambiguous | en | hard | N | PASS | clarification_or_semantic_planning | 10.13ms |
| D036 | unsupported | en | medium | N | PASS | semantic_planning | 10.49ms |
| D037 | unsupported | fr | medium | N | PASS | semantic_planning | 10.21ms |
| D038 | unsupported | en | hard | N | PASS | semantic_planning | 12.03ms |
| D039 | adversarial | en | hard | N | PASS | semantic_planning | 10.08ms |
| D040 | adversarial | en | hard | N | PASS | authorization | 9.66ms |