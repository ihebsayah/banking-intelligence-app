# Insights Necessity Gate (STEP 3)

**Status:** COMPLETE
**Version:** 3.0.0
**Last Updated:** 2026-08-31

---

## 1. Purpose

Decide deterministically whether a query result benefits from generative
natural-language (LLM) interpretation. The gate exists to eliminate
unnecessary LLM latency/cost: a simple factual query should never pay the
30–60s cost of an Ollama call when a deterministic one-line answer is correct.

- SIMPLE / DIRECT → deterministic formatter (NO LLM)
- COMPLEX / ANALYTICAL / explicitly requested → LLM useful

NO LLM decides whether the LLM is called. The gate is pure, deterministic
Python over structured signals.

## 2. Gate Architecture

```
                      ┌──────────────────────────────┐
Execution results ──▶ │ deterministic fact generation │  (STEP 2)
                      └──────────────┬───────────────┘
                                     ▼
                      ┌──────────────────────────────┐
                      │      NecessityGate.evaluate  │  (new, deterministic)
                      │   intent + text + facts      │
                      └──────────────┬───────────────┘
                                     │
                   ┌─────────────────┴─────────────────┐
                   ▼                                    ▼
        ┌───────────────────┐                ┌───────────────────────┐
        │ deterministic     │                │ LLM useful            │
        │ formatter         │                │ (only if              │
        │ (fast, factual)   │                │  ENABLE_LLM_INSIGHTS)  │
        └───────────────────┘                └───────────────────────┘
            ALL numeric facts come from the deterministic fact package.
```

## 3. Input Signals

- `query_intent` (existing orchestrator `primary_category`)
- `query_text` (original user question)
- `AnalyticalFactPackage` (verified facts from STEP 2)
  - `dataset_profile` (numeric/categorical/temporal column counts)
  - `anomalies`, `correlations`, `temporal_comparisons`, `recommendation_candidates`
  - `evidence_quality.score`

## 4. Query Classifications

Reuses the orchestrator's intent categories; no competing taxonomy.

| Classification | Intent / text signal | Default route |
|----------------|----------------------|---------------|
| DIRECT_LOOKUP | `retrieve`/`lookup` | deterministic |
| SIMPLE_AGGREGATION | numeric fact, no analysis verbs | deterministic |
| RANKING_TOP_N | "top N" wording | deterministic |
| COMPARATIVE_ANALYSIS | comparison wording | LLM if warranted |
| TREND_ANALYSIS | trend wording | LLM only if valid temporal facts exist |
| ANOMALY_ANALYSIS | anomaly wording | LLM only if anomaly facts exist |
| ANALYTICAL | `*_analysis` intents | LLM if multi-dim facts exist |

## 5. Complexity Logic

Evidence-weighted score (0.0–1.0), fully documented:

| Signal | Weight |
|--------|--------|
| Explicit explanation language (EN/FR) | +0.6 |
| ≥ 2 numeric columns (multi-dimension) | +0.2 |
| Anomalies present | +0.2 |
| Correlations present | +0.2 |
| Valid temporal comparison present | +0.2 |
| ≥ 2 recommendation candidates | +0.1 |
| Trend requested but no temporal facts | −0.4 |
| Anomaly requested but none found | −0.4 |
| Low evidence quality (< 0.4) | −0.3 |

Rule: `use_llm = score >= 0.5 AND evidence_quality.score >= 0.3`

The numeric score is interpretable; reason codes matter more.

## 6. Reason Codes

- `DIRECT_LOOKUP`, `SIMPLE_AGGREGATION`, `RANKING_TOP_N`
- `USER_REQUESTED_EXPLANATION`
- `MULTI_DIMENSION_ANALYSIS`
- `ANOMALIES_REQUIRE_SYNTHESIS`
- `CORRELATIONS_REQUIRE_INTERPRETATION`
- `TEMPORAL_ANALYSIS`
- `MULTIPLE_RECOMMENDATION_CANDIDATES`
- `TREND_UNAVAILABLE`, `NO_ANOMALIES`, `LOW_EVIDENCE_QUALITY`

## 7. Deterministic Formatter

Concise, factual, traceable output from verified facts only.

Examples:
```
"Balance of CUST_00141"                      → "Balance: 27,450."
"Average loan amount"                        → "Total amount: 1,825,000 across 100 records (mean 18,250)."
"Top 5 branches by deposits"                 → "Top balance: Tunis Centre (24% share)."
"Identify unusual activity" (no anomalies)   → "No anomalies were detected."  (via no-data wording)
```

No verbose templates. No fabricated summary.

## 8. LLM-Route Behavior

When `decision.use_llm == true` AND `ENABLE_LLM_INSIGHTS == true`, the existing
Mistral integration produces a summary from `generate_summary_from_facts(fact_package)`.
The LLM receives ONLY verified facts — never raw rows.

STEP 3 does not improve the Mistral prompt/model; that is STEP 4. LLM default
remains disabled.

## 9. Feature Flags

`ENABLE_LLM_INSIGHTS` (bool, default `false`) in `config.py`.

- Deterministic analytical facts always run (independent of Mistral).
- LLM interpretation only runs when both the gate says useful AND the flag is on.
- `ENABLE_INSIGHTS_AGENT` is unchanged and stays `false` globally.

## 10. Fallback Behavior

Previewed but complete at the agent layer: if the gate chooses LLM but Ollama
fails, `generate_summary_from_facts` returns a deterministic summary built from
verified facts (not generic static recommendations, not fabricated numbers).

## 11. Data Minimization

Preserved from STEP 2. The LLM prompt contains only:
verified metrics, categorical facts, anomalies, temporal comparisons,
correlations, recommendation candidates, and query context. No `results[:2]`,
no raw rows, no broader PII exposure.

## 12. Temporal-Analysis Correction (STEP 2 → 3)

`compute_temporal_comparisons` no longer treats a row-half split as
period-over-period. It now:

1. parses dates reliably (invalid dates dropped);
2. infers granularity (yearly / monthly / daily) from actual distribution;
3. buckets chronologically;
4. compares the latest complete period vs the immediately preceding one;
5. requires ≥ 1 observation per compared period.

If granularity or evidence is insufficient → `temporal comparison unavailable`.

Tests cover: unsorted timestamps, only-one-period, uneven ranges, invalid
dates, monthly granularity detection.

## 13. Evidence-Quality Correction (STEP 2 → 3)

`EvidenceQuality` now measures analytical evidence QUALITY only. It does NOT
reward anomaly presence, correlation presence, or temporal change presence
(absence of a pattern is not poor data quality).

Formula (documented weights):
- non-empty result set +0.15
- adequate sample size (≥ 5 rows) +0.15
- completeness ratio (non-null / total cells) ×0.30
- usable data (numeric or categorical) +0.10
- parseability (typed / non-null cells) ×0.15
- consistency (single-type columns) ×0.15

Removed model fields: `correlation_pairs_computed`, `anomaly_count`,
`has_temporal_comparison`. Public `confidence` field is preserved and now
reflects `evidence_quality.score`. Documented as "analytical evidence
quality", NOT "AI confidence".

## 14. Tests

- `tests/test_necessity_gate.py` — 17 scenarios covering §15 matrix
  (direct, count, aggregation, top-N, concentration, trend-valid,
  anomaly-valid, compare+explain, user override, trend-no-evidence,
  anomaly-none, empty, low-quality, French analytical, French direct,
  formatter, no-anomalies message).
- `tests/test_insights_agent.py` — updated temporal + evidence-quality +
  integration (39 tests).
- Total: 54 passing.

## 15. Benchmark Routing Results

`python3 -m tests.benchmark_necessity_gate` (13 representative query types,
offline, no DB/LLM).

```
Cases: 13
  UNNECESSARY LLM CALL RATE : 0%  (0 false positives / 6 LLM-route)
  LLM routing precision      : 100%
  LLM routing recall         : 100%
  False negatives            : 0
  Deterministic%             : 54% of benchmark routed away
```

Direct lookups, counts, simple aggregations, and basic rankings all route
deterministic (no LLM). Analytical requests (concentration, valid trend,
anomalies, compare+explain, French analytical) route to LLM.

## 16. Known Limitations

- Text-signal matching is keyword-based; unusual paraphrase may misclassify.
- Granularity heuristic assumes clean date values; weird formats → no comparison.
- Decision weights are hand-tuned; re-validate if production intent mix shifts.
- Benchmark is offline/representative; not a full production query set.

## 17. Readiness for STEP 4

READY. The gate cleanly separates "LLM useful" from "deterministic", keeps the
LLM path disabled behind `ENABLE_LLM_INSIGHTS`, feeds verified facts only, and
degrades to deterministic on failure. STEP 4 can now rebuild the LLM
interpretation/prompt without touching the gate, temporal, or evidence-quality
logic.
