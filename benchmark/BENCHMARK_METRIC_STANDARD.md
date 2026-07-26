# Benchmark Metric Standard

**Purpose:** Define every metric used across all benchmark reports. No report may use "Overall Accuracy" without specifying which metric it represents.

---

## 1. HTTP Success Rate

**Definition:** Percentage of requests that received an HTTP 2xx response (regardless of content correctness).

**Formula:** `(HTTP 2xx responses) / (total requests sent)`

**V2 Value:** 155/160 = **96.9%**

**What it measures:** Network-level reliability. A request that returns HTTP 200 with an error body still counts as HTTP success.

**What it does NOT measure:** Whether the response was correct, safe, or meaningful.

---

## 2. Pipeline Completion Rate (Total)

**Definition:** Percentage of all questions (including unsupported, adversarial, etc.) that reached `pipeline_complete` status — meaning the full intent→schema→SQL→validation→execution→insights pipeline ran and returned data.

**Formula:** `(questions with pipeline_complete status) / (total questions)`

**V2 Value:** 129/160 = **80.6%**

**What it measures:** How often the pipeline runs end-to-end. High values on safety categories indicate guardrail failures.

**Critical note:** A high pipeline completion rate across ALL categories is NOT desirable. For unsupported/adversarial/authorization categories, pipeline completion is a failure.

---

## 3. Supported Query Pipeline Completion Rate

**Definition:** Percentage of questions expected to produce analytical results (business_en, business_fr, governed_metrics, multi_table, ranking, time_series) that successfully completed the pipeline.

**Formula:** `(pipeline_complete in supported categories) / (total questions in supported categories)`

**V2 Value:** 113/115 = **98.3%**

**What it measures:** Core analytical capability — the system's ability to understand and execute valid banking queries.

**This is the primary measure of analytical quality.**

---

## 4. Safety Rejection Rate

**Definition:** Percentage of questions that SHOULD be rejected (ambiguity, unsupported, adversarial, malformed, authorization, api_validation) that were correctly NOT processed through the full pipeline.

**Formula:** `(correctly rejected) / (total questions in safety categories)`

**V2 Value:** 29/45 = **64.4%**

**What it measures:** Guardrail effectiveness. Low values indicate the system processes dangerous or invalid requests.

---

## 5. Routing Accuracy (End-to-End Correctness)

**Definition:** Percentage of all questions where the system's actual output stage matched the expected output stage (pipeline_complete, clarification, unsupported, auth_required, validation_error).

**Formula:** `(questions where actual stage == expected stage) / (total questions)`

**V2 Value:** 142/160 = **88.8%**

**What it measures:** Overall system correctness — combining analytical capability and safety in a single number. This is the broadest accuracy measure.

**Note:** This is the only metric that combines analytical and safety performance. It should not be confused with pipeline completion rate.

---

## 6. Authorization Enforcement Rate

**Definition:** Percentage of no-auth requests that were correctly rejected with auth_required.

**Formula:** `(no-auth requests rejected) / (total no-auth requests)`

**V2 Value:** 0/5 = **0%**

---

## 7. Adversarial Detection Rate

**Definition:** Percentage of adversarial queries correctly rejected or blocked.

**Formula:** `(adversarial queries correctly handled) / (total adversarial queries)`

**V2 Value:** 6/8 = **75%**

---

## 8. SQL Correctness

**Definition:** Whether the generated SQL accurately answers the user's question.

**Status:** NOT MEASURED in V2 benchmark. Pipeline completion does not imply SQL correctness.

---

## 9. Insight Quality

**Definition:** Whether the insights agent produces query-specific analysis vs. generic template output.

**Status:** NOT QUANTIFIED. V2 benchmark notes template-based output qualitatively but assigns no score.

---

## Metric Cross-Reference

| Metric | V1 Holdout (Tuned) | V2 Blind | Notes |
|--------|-------------------|----------|-------|
| HTTP Success Rate | N/A | 96.9% | |
| Pipeline Completion (total) | 100% (160/160) | 80.6% (129/160) | V1 100% was on tuned data |
| Supported Query Completion | N/A | 98.3% (113/115) | |
| Safety Rejection Rate | N/A | 64.4% (29/45) | |
| Routing Accuracy | 100% (160/160) | 88.8% (142/160) | V1 was on tuned data |
| Authorization Enforcement | N/A | 0% (0/5) | Critical gap |
| Adversarial Detection | N/A | 75% (6/8) | |

---

## Report Usage Rules

1. Every report MUST specify which metric is being discussed.
2. Never use "Overall Accuracy" without clarifying: routing accuracy? pipeline completion? supported query completion?
3. Pipeline completion rates for safety categories are failure indicators, not success indicators.
4. Routing accuracy is the only single-number summary that combines both analytical and safety performance.
5. Supported query completion rate should be reported alongside safety rejection rate — never in isolation.
