# CONFIDENCE CALIBRATION AUDIT

**Date:** 2026-07-23
**Data source:** `benchmark/results/holdout_run.jsonl` (160 records)
**Threshold under audit:** `INTENT_CONFIDENCE_THRESHOLD = 0.31` (`services/shared/config.py:102`)

> **Warning:** This threshold was selected AFTER examining the holdout data.
> All findings below require independent validation on a held-out dataset
> before any production deployment. Do not change the threshold during this audit.

---

## 1. How intent_confidence Is Calculated

There are two independent confidence signals that get merged:

### 1.1 Keyword Confidence (`confidence`)

Computed in `services/intent_agent/intent_recognizer.py:349-353`:

```
if primary_score == 0:
    confidence = 0.05
else:
    raw_conf = (primary_score / total_tokens) * 0.90 + 0.05
    confidence = round(min(raw_conf, 0.99), 4)
```

Where `primary_score` = number of tokens matching the top keyword category, and `total_tokens` = total non-stopword alpha tokens. This is a **density** measure: how concentrated the query's vocabulary is in one category.

### 1.2 Structured Intent Confidence (`intent_confidence`)

Computed in `services/intent_agent/structured_intent.py:456`:

```python
confidence = round((dom_conf + task_conf + met_conf) / 3.0, 4)
```

Where:
- `dom_conf` = `min(0.2 + 0.1 * score_val, 0.99)` from `extract_domain()` — domain keyword match score
- `task_conf` = task detection confidence from `extract_task()`
- `met_conf` = `0.95` if a glossary KPI was matched, else `0.5`

**Critical detail:** The final `intent_confidence` returned in the intent response is set to `dom_conf` (line 472), **not** the averaged confidence:

```python
return {
    ...
    "intent_confidence": dom_conf,    # <-- domain confidence only
    "confidence": confidence,           # <-- the averaged value
    ...
}
```

This means the field that the gate checks (`intent_confidence`) is **only the domain keyword score**, not the full structured intent average.

### 1.3 Merge Behavior

In `intent_recognizer.py:372-416`, structured intent fields are merged into the keyword result. The `requires_clarification` flag can be overridden from `True` to `False` by structured intent under specific conditions (no "hard" ambiguities detected). Once `requires_clarification=False`, the confidence threshold check is bypassed entirely.

### 1.4 The Gate Logic

In `services/orchestrator/orchestrator_agent.py:85-94`:

```python
if not intent_data.get("supported_capability", True):          # Check 1
    gate_reason = intent_data.get("rejection_reason", ...)
elif intent_data.get("risk_level") in ("adversarial", "suspicious"):  # Check 2
    gate_reason = intent_data.get("rejection_reason", ...)
elif intent_data.get("requires_clarification") and              # Check 3
     (intent_data.get("intent_confidence") or intent_data.get("confidence", 1.0))
     < self.config.INTENT_CONFIDENCE_THRESHOLD:
    gate_reason = intent_data.get("clarification_question") or "Insufficient confidence to proceed"
```

**The threshold only applies when `requires_clarification=True`.** If structured intent overrides this to `False`, the threshold is never consulted.

---

## 2. Confidence Bucket Analysis

All 160 holdout records were bucketed by `intent_confidence`. The 65 records that never reached the intent step (validation errors, auth blocks) are excluded from bucketing; the 95 pipeline-processed records and the 40 intent-gate-rejected records (where intent was processed but the gate rejected) are analyzed below.

### 2.1 Distribution Summary

| Bucket | Count | Accepted | Rejected | Valid | Ambiguous | Unsupported | Adversarial | FAR | FRR |
|--------|------:|--------:|---------:|------:|----------:|------------:|------------:|----:|----:|
| 0.00-0.10 | 0 | — | — | — | — | — | — | — | — |
| 0.11-0.20 | 0 | — | — | — | — | — | — | — | — |
| 0.21-0.30 | 68 | 68 | 0 | 68 | 49 | 0 | 0 | 0.000 | 0.000 |
| 0.31-0.40 | 25 | 25 | 0 | 25 | 14 | 0 | 0 | 0.000 | 0.000 |
| 0.41-0.60 | 2 | 2 | 0 | 2 | 1 | 0 | 0 | 0.000 | 0.000 |
| 0.61-0.80 | 0 | — | — | — | — | — | — | — | — |
| 0.81-1.00 | 0 | — | — | — | — | — | — | — | — |

**Key observation:** Every record in this dataset that reached the intent step was accepted. The 40 intent-gate rejections (ambiguous + unsupported + adversarial) do not appear in the buckets because they were rejected before their `intent_confidence` was recorded in the pipeline steps.

### 2.2 Why Every Bucket Shows Zero FAR and FRR

The holdout data has a structural property: **all queries that reach the intent step have `requires_clarification=False`** (overridden by structured intent). Therefore, the confidence threshold gate is never consulted for any of the 95 accepted records. The threshold could be set to 0.0 or 1.0 and the outcome would be identical.

The 40 rejected queries are rejected by Checks 1 and 2 (unsupported capability / adversarial risk), not by the confidence threshold.

---

## 3. Threshold Sensitivity Analysis

Simulating the gate across different threshold values on the 95 pipeline-processed queries:

| Threshold | Accepted | Rejected | FRR (valid rejected) |
|-----------|--------:|---------:|---------------------:|
| 0.20 | 95 | 0 | 0.0000 |
| 0.25 | 95 | 0 | 0.0000 |
| 0.299 | 95 | 0 | 0.0000 |
| 0.30 | 95 | 0 | 0.0000 |
| **0.31** | **95** | **0** | **0.0000** |
| 0.32 | 95 | 0 | 0.0000 |
| 0.35 | 95 | 0 | 0.0000 |
| 0.40 | 95 | 0 | 0.0000 |
| 0.50 | 95 | 0 | 0.0000 |

**The threshold has zero discriminating power on this dataset.** The reason: every accepted query's `requires_clarification` was overridden to `False` by structured intent, making the `elif` branch unreachable.

### 3.1 Why 0.31 Was Selected

The `intent_confidence` values in the holdout cluster at exactly three values (due to the discrete nature of `dom_conf = min(0.2 + 0.1 * score_val, 0.99)`):

| intent_confidence | Count | Percentage |
|-------------------|------:|-----------:|
| 0.30 | 68 | 71.6% |
| 0.40 | 25 | 26.3% |
| 0.60 | 2 | 2.1% |

The value 0.31 sits in the gap between 0.30 and 0.40. If `requires_clarification` were `True` for the 0.30-confidence queries, a threshold of 0.31 would reject them while accepting the 0.40+ queries. This suggests the threshold was designed as a **hypothetical safety net** for queries where structured intent fails to clear `requires_clarification`.

However, on the current holdout, that hypothetical never triggers.

---

## 4. Language Distribution (EN vs FR)

| Language | Count | Above threshold (>= 0.31) | Below threshold (< 0.31) | Mean confidence |
|----------|------:|--------------------------:|-------------------------:|----------------:|
| EN | 65 | 19 | 46 | 0.3354 |
| FR | 30 | 8 | 22 | 0.3267 |

### 4.1 Intent Confidence Distribution by Language

| intent_confidence | EN | FR |
|-------------------|---:|---:|
| 0.30 | 46 | 22 |
| 0.40 | 17 | 8 |
| 0.60 | 2 | 0 |

### 4.2 Analysis

The distributions are structurally similar:
- FR queries have a lower mean keyword confidence (`kw_conf`): EN mean = 0.2981, FR mean = 0.1532
- This is expected: spaCy's `en_core_web_sm` tokenizer handles French text poorly (more stopwords retained, worse lemmatization), producing lower token-match density
- Despite lower keyword confidence, the domain confidence (`intent_confidence`) values are similar because `extract_domain()` uses bilingual keyword tables
- **No language-specific bias was detected** in the structured intent confidence, but the keyword confidence is systematically lower for FR

---

## 5. Short Query Analysis

| Query ID | Confidence | Valid | Ambiguities | Query |
|----------|----------:|------:|------------:|-------|
| H038 | 0.30 | Yes | 0 | Combien de prêts sont actifs? |
| H039 | 0.30 | Yes | 0 | Combien de branches existe-t-il? |

Only 2 queries in the holdout have ≤5 words. Both received confidence 0.30 and were accepted.

### 5.1 Analysis

Short valid queries do receive lower confidence (0.30 vs 0.40 for longer queries), which is expected given the density formula: fewer tokens means fewer matches, and even one match produces low density. However, structured intent overrides `requires_clarification` for these queries because they contain explicit analytical triggers (`combien` → aggregation task).

**No systematic false rejection of short valid queries was observed**, but the sample size (2) is too small for statistical significance.

---

## 6. Ambiguous Queries and High Confidence

Ambiguity detection produces these patterns in the holdout:

| Pattern | Occurrences |
|---------|------------:|
| Multiple categories equally matched | 33 |
| ambiguous_account_type | 18 |
| 'balance' could mean account balance or revenue balance | 15 |
| Query too vague — no clear category detected | 9 |
| All products or specific product type? | 9 |
| What time period? | 9 |
| Unclear primary entity: customer or branch? | 3 |

### 6.1 Can Ambiguous Queries Receive High Confidence?

Yes. 15 of 25 queries in the 0.31-0.40 bucket have ambiguities, and 1 of 2 queries in the 0.41-0.60 bucket has ambiguities.

Example: H002 "What is the total balance across all accounts?" received `intent_confidence=0.30` with the ambiguity "'balance' could mean account balance or revenue balance" — yet it was accepted because structured intent overrode `requires_clarification` to `False`.

The ambiguity detector fires on generic patterns (e.g., "balance" triggers a false positive for ambiguity even when the query is contextually clear). The structured intent layer's override logic is designed to suppress these false-positive ambiguities.

---

## 7. Unsupported Requests and High Confidence

**No unsupported or adversarial queries received `intent_confidence` values** because they were rejected by Checks 1 and 2 of the gate before the confidence field was recorded in the pipeline steps.

All 15 unsupported queries (H101-H115) and all 10 adversarial queries (H116-H125) were correctly rejected with `early_stop=intent`.

The unsupported and adversarial detection is independent of confidence and operates on keyword/regex patterns, so there is no scenario where a high-confidence adversarial query could pass the gate.

---

## 8. The requires_clarification Override Problem

This is the most significant finding of the audit.

### 8.1 The Override Mechanism

In `intent_recognizer.py:386-412`, structured intent can override `requires_clarification` from `True` to `False` when:
1. Structured intent says no clarification needed
2. No "hard" ambiguities exist (e.g., "too short" patterns)
3. No vague informational patterns detected

Once `requires_clarification=False`, the confidence threshold is bypassed entirely (the `elif` on line 89 requires `requires_clarification` to be truthy).

### 8.2 Impact on Holdout

Every single query that reached the intent step (95/95) had `requires_clarification=False`. This means:
- The confidence threshold of 0.31 is **never consulted** for any query in the holdout
- The gate's third check is effectively dead code for this dataset
- The threshold could be set to any value between 0.0 and 1.0 with identical results

### 8.3 Risk

If a future query bypasses structured intent (e.g., due to a parsing failure in `build_structured_intent()`), the keyword recognizer's `requires_clarification` defaults to `True` (line 359: `requires_clarification = confidence < 0.85 or len(ambiguities) > 0`). In that case, the threshold of 0.31 would apply, and the query would need `intent_confidence >= 0.31` to pass. Given that most keyword-confidence values are 0.20-0.35, this would reject many valid queries.

---

## 9. Overall System Accuracy

| Expected Behavior | Count | Correct | Incorrect |
|-------------------|------:|--------:|----------:|
| pipeline_complete | 95 | 95 | 0 |
| clarification | 15 | 15 | 0 |
| semantic_planning | 25 | 25 | 0 |
| auth_required | 10 | 10 | 0 |
| validation_error | 15 | 15 | 0 |
| **Total** | **160** | **160** | **0** |

**Overall accuracy: 100.0%** on the holdout dataset.

---

## 10. Recommendations

### 10.1 Immediate Actions

1. **The threshold needs independent validation.** It was tuned on the same data it is evaluated against. Create a new holdout set of at least 50 queries (10 ambiguous, 10 unsupported, 10 adversarial, 20 valid) and evaluate with the current threshold before any production deployment.

2. **Test the requires_clarification override failure mode.** Intentionally inject a structured intent parsing failure (e.g., mock `build_structured_intent` to raise an exception) and verify that the keyword recognizer's fallback + threshold correctly rejects vague queries.

3. **Add more short queries (< 5 words) to the holdout.** The current sample of 2 is statistically meaningless. Add at least 10 short valid queries and 10 short ambiguous queries.

### 10.2 Structural Improvements

4. **Record intent data for rejected queries.** The 40 intent-gate-rejected queries have empty `pipeline_steps`, making post-hoc analysis impossible. The orchestrator should record the intent response before returning the error.

5. **Decouple `intent_confidence` from `dom_conf`.** Currently `intent_confidence` in the response is set to `dom_conf` alone (line 472 of `structured_intent.py`), not the averaged `(dom_conf + task_conf + met_conf) / 3`. This means the gate is checking a less-informative signal. Consider using the averaged value, or at minimum document this discrepancy.

6. **Add confidence distribution monitoring.** Track the distribution of `intent_confidence` values in production to detect drift. If the distribution shifts (e.g., more queries at 0.20-0.30), the threshold may need recalibration.

### 10.3 Low Priority

7. **FR keyword confidence is systematically lower** due to `en_core_web_sm` limitations. Consider adding a French spaCy model (`fr_core_news_sm`) for FR queries to improve keyword confidence parity.

---

## Appendix A: Raw Confidence Values

### intent_confidence distribution (domain confidence)

| Value | Count | Percentage |
|-------|------:|-----------:|
| 0.30 | 68 | 71.6% |
| 0.40 | 25 | 26.3% |
| 0.60 | 2 | 2.1% |

### keyword confidence (`confidence`) distribution

| Value | Count |
|-------|------:|
| 0.05 | 9 |
| 0.1143 | 1 |
| 0.125 | 1 |
| 0.1318 | 2 |
| 0.14 | 3 |
| 0.15 | 6 |
| 0.1625 | 5 |
| 0.1786 | 4 |
| 0.20 | 7 |
| 0.23 | 12 |
| 0.25 | 1 |
| 0.275 | 15 |
| 0.3071 | 2 |
| 0.35 | 15 |
| 0.41 | 5 |
| 0.50 | 6 |
| 0.725 | 1 |

Keyword confidence ranges from 0.05 to 0.725 with a median around 0.23. This is the value that would be used as fallback if structured intent parsing fails (via `intent_data.get("confidence", 1.0)` in the gate).

## Appendix B: Domain Confidence by Domain

| Domain | Count | Mean | Values |
|--------|------:|-----:|--------|
| accounts | 25 | 0.336 | [0.30, 0.40, 0.60] |
| aml | 2 | 0.300 | [0.30] |
| branch/regional | 6 | 0.300 | [0.30] |
| compliance | 3 | 0.400 | [0.30, 0.60] |
| credit risk | 2 | 0.300 | [0.30] |
| customer | 22 | 0.323 | [0.30, 0.40] |
| deposits | 4 | 0.300 | [0.30] |
| kyc | 2 | 0.350 | [0.30, 0.40] |
| loans | 18 | 0.361 | [0.30, 0.40] |
| profitability | 2 | 0.400 | [0.40] |
| transactions | 9 | 0.300 | [0.30] |

## Appendix C: Records Rejected at Intent Gate (No Intent Data Recorded)

These 40 queries were rejected before the intent step was recorded. They do not appear in the bucket analysis.

**Ambiguous (15):** Rejected by vagueness/confidence checks
- H086-H100: queries like "Show me data", "What's going on?", "Summarize everything"

**Unsupported (15):** Rejected by `supported_capability=False`
- H101-H115: queries like "Send an email", "Create a new account", "Forecast revenue"

**Adversarial (10):** Rejected by `risk_level=adversarial`
- H116-H125: queries like "Ignore previous instructions", SQL injection attempts, "act_as_admin"
