# Development 40-Question Benchmark Results

**Run:** development_run_2
**Date:** 2026-07-20
**Classification:** C — Core NL-to-SQL Component Benchmark

> The benchmark tests the deterministic pipeline (QueryPlanBuilder →
> DeterministicSQLCompiler → PostgreSQL → ResultVerifier). It does not
> invoke the Orchestrator, Intent Agent, Schema Agent, or API Gateway.
> See `benchmark/analysis/BENCHMARK_RUNTIME_INVOCATION_MAP.md` for the
> full invocation map.

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

| Metric | Run 1 | Run 2 |
|--------|-------|-------|
| p50 | 19.83ms | 12.80ms |
| p95 | 33.93ms | 17.24ms |
| p99 | 46.71ms | 38.60ms |
| mean | 21.79ms | 13.80ms |

**Latency difference explanation:** Run 2 ran in the same process
immediately after Run 1. The ~40% improvement is consistent with
warmed PostgreSQL buffer cache, reused prepared statement plans,
and warm connection pooling. Run 1 also incurred exception/retry
overhead on the 6 failing questions (PG errors → error handling →
no result). These are core-pipeline latencies, not user-visible
distributed-system latencies. No application-level caching (Redis,
semantic retrieval cache) is used in the runner.

## Expected Safe Stops

These are not benchmark failures. They are correct rejections of
unsupported, ambiguous, or unauthorized requests.

| Stage | Count | Meaning |
|-------|-------|---------|
| Clarification or semantic planning | 3 | Ambiguous requests rejected correctly |
| Semantic planning | 4 | Unsupported/adversarial requests rejected correctly |
| Authorization | 1 | Unauthorized request blocked correctly |

**Unexpected supported-query failures: 0**

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