# Insights Agent — Deterministic Analytical Fact Layer

**Version:** 2.0.0
**Last Updated:** 2026-08-31
**Status:** Production-ready, all 31 tests passing

---

## Architecture Overview

```
Query Results (raw rows)
        │
        ▼
┌─────────────────────────┐
│  StatisticalAnalyzer    │  ← Column classification, per-column stats,
│  (deterministic, no LLM)│    anomalies, correlations, temporal
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  AnalyticalFactPackage  │  ← Single source of truth for all facts
│  (internal model)       │    Every field has Provenance
└────────────┬────────────┘
             │
     ┌───────┴───────┐
     │               │
     ▼               ▼
┌──────────┐  ┌──────────────┐
│ Response  │  │ Mistral LLM  │  ← LLM may EXPLAIN facts, not CREATE facts
│ (API)    │  │ (optional)   │
└──────────┘  └──────────────┘
```

## Key Design Principles

1. **Zero synthetic values** — every number comes from actual execution results
2. **No hardcoded confidence** — `EvidenceQuality.score` replaces the old `0.85`
3. **Provenance on every fact** — `Provenance(source, column, method)` tracks origin
4. **Evidence-backed recommendations only** — no static "optimal capacity" sentences
5. **LLM optional** — deterministic summary always available as fallback
6. **Backward-compatible API** — `InsightsRequest`/`InsightsResponse` unchanged

## Files Modified

| File | Change |
|------|--------|
| `models.py` | Added `AnalyticalFactPackage`, `DatasetProfile`, `DescriptiveStats`, `CategoricalDistribution`, `AnomalyFact`, `CorrelationFact`, `TemporalComparison`, `RecommendationCandidate`, `EvidenceQuality`, `Provenance` |
| `statistical_analyzer.py` | Full rewrite: column classification, per-column stats, categorical distributions, z-score anomalies, Pearson correlations, temporal half-split comparison |
| `context_gatherer.py` | Simplified to metadata-only (no DB queries). System-wide totals were misleading alongside query-specific results |
| `insights_generator.py` | Rewritten to orchestrate `AnalyticalFactPackage` → response. No more `_KNOWN_NUMERIC` sets or synthetic `_identify_trends` |
| `mistral_integrator.py` | Added `generate_summary_from_facts()` using only fact package. Deterministic fallback summary. Removed hardcoded recommendation templates |
| `main.py` | Removed DB pool teardown (no longer needed) |
| `tests/test_insights_agent.py` | 31 tests across 9 categories |

## AnalyticalFactPackage Structure

```python
class AnalyticalFactPackage(BaseModel):
    query_intent: str
    query_text: str
    dataset_profile: DatasetProfile       # column types, row count, null counts
    descriptive_stats: List[DescriptiveStats]  # per-numeric-column
    categorical_distributions: List[CategoricalDistribution]
    anomalies: List[AnomalyFact]          # z-score > 2σ
    correlations: List[CorrelationFact]   # Pearson r, |r| ≥ 0.7 reported
    temporal_comparisons: List[TemporalComparison]  # half-split
    recommendation_candidates: List[RecommendationCandidate]  # evidence-backed
    evidence_quality: EvidenceQuality     # replaces hardcoded confidence
```

## Column Classification Rules

| Type | Rule |
|------|------|
| **Numeric** | ≥80% of values parseable as `float` |
| **Temporal** | ≥60% match ISO date/timestamp patterns |
| **Identifier** | ≥60% match ID patterns + ≥80% unique |
| **Categorical** | Everything else |

## Evidence Quality Scoring

| Signal | Weight |
|--------|--------|
| Row count ≥ 5 | +0.15 |
| Has numeric columns | +0.15 |
| Completeness ratio (non-null / total cells) | ×0.20 |
| Has categorical columns | +0.10 |
| Correlation pairs computed ≥ 1 | +0.10 |
| Temporal comparison available | +0.10 |
| Anomalies detected ≥ 1 | +0.10 |
| Numeric columns ≥ 2 | +0.10 |

Score ranges 0.0–1.0, computed deterministically.

## Recommendation Rules

| Rule | Trigger | Severity |
|------|---------|----------|
| `anomaly_concentration` | ≥1 extreme anomaly (3σ) | warning |
| `moderate_anomalies` | ≥1 moderate anomaly (2σ) | info |
| `strong_correlation` | |r| ≥ 0.7 | info |
| `large_temporal_change` | |Δ%| > 20% | info/warning |
| `skewed_distribution` | |mean - median| / std > 0.5 | info |

**No generic recommendations are emitted.** Every recommendation has `evidence_column` and `evidence_value`.

## API Contract (unchanged)

```
POST /generate_insights
{
  "query_intent": "customer_analysis",
  "query_text": "Top 10 customers by balance",
  "results": [...],
  "metadata": {"tables": [...], "rows_returned": 10}
}
→ InsightsResponse { status, summary, key_metrics, trends, anomalies, recommendations, confidence }
```

`confidence` now reflects `EvidenceQuality.score` (data completeness) instead of hardcoded `0.85`.

## Future: LLM Integration (STEP 3)

When LLM is enabled:
1. Fact package is built deterministically first
2. LLM receives `build_verified_fact_payload()` output (never raw rows)
3. LLM explains facts in natural language
4. LLM cannot add new numbers — only the fact package is authoritative
