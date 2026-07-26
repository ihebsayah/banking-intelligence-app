# Insights Agent Evaluation

**Date:** 2026-07-25
**Scope:** `services/insights_agent/` — full implementation review

---

## 1. Architecture

The Insights Agent has four layers:

| Layer | File | Technology | Dynamism |
|-------|------|-----------|----------|
| Statistical Analysis | `statistical_analyzer.py` | numpy | **Genuinely dynamic** |
| Context Gathering | `context_gatherer.py` | PostgreSQL queries | **Static** (system-wide snapshots) |
| Trend Identification | `insights_generator.py` | Hardcoded logic | **Mostly synthetic** |
| NL Summary | `mistral_integrator.py` | Ollama/tinyllama + fallback templates | **Template-driven** |

---

## 2. What Actually Analyzes Result Sets

### Statistical Analysis (Dynamic)

`StatisticalAnalyzer.analyze()` computes real numpy statistics over the primary numeric column:
- total_sum, average, median, std_dev, min_value, max_value
- Percentiles: p25, p50, p75, p90, p99
- Outlier detection: values > 2σ from mean

This is genuine, query-specific, data-driven analysis. The values change per query.

### Context Gathering (Static)

`ContextGatherer.gather_context()` executes 5 hardcoded SQL queries:

```sql
SELECT COALESCE(SUM(balance), 0) FROM accounts    -- total_deposits
SELECT COUNT(*) FROM customers                      -- total_customers
SELECT COUNT(*) FROM transactions                   -- total_transactions
SELECT state, COUNT(*) FROM branches GROUP BY state -- regional_breakdown
SELECT segment, COUNT(*) FROM customers GROUP BY segment -- segment_breakdown
```

These return the same system-wide values for every query. They are not filtered by the user's query context (tables, filters, time range).

### Trend Identification (Synthetic)

`_identify_trends()` in `insights_generator.py`:

1. **Concentration trend**: Fires when `sum / total_deposits > 30%`. Semi-dynamic — depends on real stats.
2. **YoY growth**: **Hardcoded** at `12.5%` for EVERY query. Code comment: `"# Synthetic YoY growth indicator (real impl would query historical data)"`.
3. **Risk flag volume**: Only for risk intents, pulls from static context.

### NL Summary (Template-Driven)

When Ollama/tinyllama responds: output varies per query (but quality depends on the LLM).

When LLM fails (common in practice): `_fallback_summary()` generates:

```
Analysis of '{query_text}' across {N} records: total {col} = ${sum}, average {col} = ${avg}.
Key drivers: {trend_names}.
Recommend prioritising {top_region} branch for strategic allocation.
```

The `top_region` is always the same (system-wide max from branches table). The trend names always include "yoy growth". The recommendations are always the same 3 sentences with minor number substitution.

---

## 3. Dynamic Content Ratio

| Response Field | Dynamic? | Notes |
|----------------|----------|-------|
| `summary` | Partly | LLM path: dynamic. Fallback: template with numbers |
| `key_metrics.total_count` | **Yes** | Row count |
| `key_metrics.total_sum` | **Yes** | Real sum |
| `key_metrics.average` | **Yes** | Real mean |
| `key_metrics.concentration_pct` | Semi | Computed, but denominator is always the same |
| `key_metrics.top_region` | **Static** | Same for every query in a database |
| `trends.yoy_growth` | **Static** | Hardcoded 12.5%, always present |
| `trends.concentration` | Semi | Only appears if >30% threshold |
| `anomalies` | **Yes** | Real outlier detection |
| `recommendations` | **Static** | Same 3 sentences, minor number substitution |
| `confidence` | **Static** | Always 0.85 |

**Estimated dynamic content: 30-35%**
**Estimated template/static content: 65-70%**

---

## 4. Column Usage Analysis

The agent examines only **one numeric column** per query:

```python
_KNOWN_NUMERIC = {
    "balance", "amount", "fee", "revenue", "count", "score",
    "rate", "available_balance", "risk_score", ...
}
```

Priority: `balance > total_balance > total_amount > sum > avg > average > amount > fee > revenue > count > score > risk_score > rate`

The `_detect_numeric_columns()` method checks only `results[0]` (first row) for column membership. Non-numeric columns (names, IDs, dates, categories, booleans) are completely ignored.

For the LLM prompt, only `results[:2]` (first 2 rows) and first 5 column names are passed.

---

## 5. Verdict

**The Insights Agent is a statistical calculator wrapped in a template engine.**

- It does compute real statistics over query results (genuinely dynamic)
- But the context, trends, recommendations, and summary are template-driven
- The benchmark's own assessment is accurate: "functioning as a formatter, not an analyst"
- The `confidence=0.85` hardcoded value is dishonest — it does not reflect actual insight quality

### What It Does Well
- Real statistical computation (mean, median, std, percentiles, outliers)
- Graceful degradation (works without LLM)
- Multi-format output support

### What It Does Not Do
- Query-specific trend analysis (yoy_growth is synthetic)
- Context-aware recommendations (same 3 sentences every time)
- Result-set-aware NL generation (template fallback)
- Column-type-aware analysis (only looks at one numeric column)
- Comparative analysis (no period-over-period, no benchmarking)

---

## 6. Roadmap for Genuine Analysis

### Phase 1: Fix Templates (Low effort)
1. Remove hardcoded `yoy_growth=12.5%` — only emit trends with real data
2. Make recommendations query-aware: reference actual tables, columns, and values from the result
3. Remove hardcoded `confidence=0.85` — compute from data quality signals

### Phase 2: Context-Aware Analysis (Medium effort)
1. Filter system context by query scope (tables, time range, filters)
2. Add period-over-period comparison using actual date columns
3. Detect and report data quality issues (missing values, outliers, skew)

### Phase 3: Multi-Column Analysis (Higher effort)
1. Analyze correlations between numeric columns
2. Detect categorical distributions (not just numeric)
3. Generate cross-dimensional insights (e.g., "risk is concentrated in Branch X")

### Phase 4: LLM-Powered Reasoning (Highest effort)
1. Use a larger model (mistral instead of tinyllama)
2. Provide structured data context in the prompt
3. Evaluate output quality with automated rubrics
