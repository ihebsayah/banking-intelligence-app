# Executive Summary — Benchmark V2

**Date:** 2026-07-24 | **Verdict:** CONDITIONAL

---

## Pass/Fail Verdict

**CONDITIONAL — System needs specific improvements before production.**

The core analytical pipeline is production-grade (98.3% on supported queries). The safety and authorization layers are not. A banking system that executes SQL injection, processes mutation requests, and exposes data without authentication cannot ship.

## Key Metrics

| Metric | Result |
|---|---|
| Analytical pipeline completion | 113/115 (98.3%) |
| Safety rejection rate | 29/45 (64.4%) |
| Critical safety failures | 7 |
| HTTP success rate | 155/160 (96.9%) |
| Authorization enforcement | 0/5 (0%) |
| Adversarial detection | 6/8 (75%) |
| Mean latency | 0.52s |

## Honest Limitations

1. **16 unsafe queries executed through the pipeline** — including SQL injection (B2141), prompt injection (B2142), and all 5 no-auth requests
2. **Insight quality is template-based** — every response contains the same generic "yoy growth" and "Tunis branch" boilerplate
3. **No SQL correctness validation** — we measure completion, not correctness
4. **Single execution run** — no repeatability data
5. **The 100% V1 remediation score was on tuned data** — this is the first test on genuinely unseen questions

## What Works

- Intent classification and parameter extraction across EN/FR
- Multi-table joins, ranking, grouping, and time-series queries
- Malformed input handling (100% rejection)
- API validation (100% rejection)
- Latency well within SLA (<1s P95)

## Recommendations

**Before production:**
1. Enforce authorization (every request needs a valid token)
2. Block SQL injection patterns
3. Improve adversarial detection for conversational prompt injection
4. Block all mutation verbs (close, approve, generate, simulate)

**Before wider deployment:**
5. Fix ambiguity handling to return clarification instead of guesses
6. Replace template insights with query-specific analysis
7. Add SQL correctness scoring to benchmarks
