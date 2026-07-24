# FIX AUDIT REPORT

**Date:** 2026-07-24
**Scope:** 8 post-holdout fixes applied to the banking intelligence system
**Purpose:** Independent audit of each fix's architectural justification, holdout motivation, overfitting risk, and validation requirements

---

## 1. Executive Summary

This report audits 8 distinct fixes applied to the banking intelligence system after initial holdout benchmark evaluation. The fixes span four categories: implementation bug fixes (4), schema grounding fixes (1), heuristic changes (1), threshold tuning (1), and vocabulary enrichment (2, overlapping with heuristic change).

**Key finding:** Two fixes — Fix 6 (confidence threshold lowered to 0.31) and Fix 7 (vagueness query-text patterns) — were tuned after inspecting the original holdout queries. These represent potential overfitting vectors and require independent validation on unseen data before the 160/160 benchmark result can be considered a generalization estimate. The remaining fixes are architecturally justified independent of the holdout.

**Risk classification of all 8 fixes:**

| Risk Level | Fixes |
|---|---|
| LOW | Fix 1, Fix 2, Fix 3, Fix 4, Fix 8 |
| MEDIUM | Fix 5, Fix 7 |
| HIGH | Fix 6 |

---

## 2. Per-Fix Audit

---

### Fix 1: SQL JOIN Deduplication

**File/Location:** `services/sql_agent/sql_builder.py:465-480` — method `_build_joins`

**Original Behavior:** No deduplication of JOIN clauses. When multiple logical paths led to the same table join, identical JOINs were emitted multiple times in the generated SQL, causing execution errors (duplicate JOIN syntax).

**Corrected Behavior:** A `seen` set tracks `(from_table, to_table, condition)` tuples. Duplicate JOINs are skipped via a `dedup_key`.

**Classification:** IMPLEMENTATION_BUG_FIX

**Architecturally Justified:** Yes. Deduplicating identical JOINs is a standard SQL generation concern. The fix prevents SQL syntax/runtime errors on any multi-table query, regardless of benchmark content. The logic is general-purpose: it matches on full JOIN signature, not on any query-specific heuristic.

**Holdout Motivation:** Some multi-table queries in the holdout failed due to duplicate JOINs. However, the fix addresses a class of bug that would manifest on any redundant join path — not specific to the holdout queries.

**Overfitting Risk:** LOW. The deduplication operates on structural SQL properties (table names and conditions), not on query semantics or benchmark-specific patterns. No holdout-specific logic is introduced.

**Regression Tests Required:**
- Multi-table queries with circular join paths (e.g., A→B→C→A)
- Queries with redundant but non-identical join paths to the same table
- Standard multi-table joins that should produce exactly one JOIN per path

**Negative Tests Required:**
- Queries where two *different* JOINs to the same table are semantically required (e.g., joining on different foreign keys). These must NOT be deduplicated. The current implementation deduplicates on full tuple `(from_table, to_table, condition)`, so different conditions are preserved. This should be validated.

**New Data Validation Requirement:** Low priority. The fix is structurally safe. Standard SQL generation test suites suffice.

---

### Fix 2: SELECT Column `primary_table` Correction

**File/Location:** `services/sql_agent/sql_builder.py:292-318` (method `_safe_columns`) and `services/sql_agent/sql_builder.py:611-659` (method `build`)

**Original Behavior:** `_safe_columns` used a `fallback_table` defaulting to `tables[0]` (alphabetical order of table names) when resolving unqualified column references. This could differ from the actual `FROM` table, causing column reference errors.

**Corrected Behavior:** `_safe_columns` now accepts a `primary_table` parameter. The `build` method computes this from `join_paths[0].from_table`, ensuring the same table used in `FROM` is used as the SELECT fallback for unqualified columns.

**Classification:** IMPLEMENTATION_BUG_FIX

**Architecturally Justified:** Yes. Column resolution should be consistent with the FROM clause. Using alphabetical ordering as a fallback is an implementation error, not a design choice. The fix ensures structural consistency in generated SQL.

**Holdout Motivation:** Column references to the wrong table caused failures on holdout queries. However, the fix addresses a general class of column-resolution bugs.

**Overfitting Risk:** LOW. The fix aligns column resolution with the FROM clause — a structural invariant that should hold for any query, not just holdout queries.

**Regression Tests Required:**
- Queries with multiple tables where alphabetical order differs from FROM order
- Queries with unqualified columns that belong to the FROM table
- Queries with qualified columns (table.column) that should bypass fallback

**Negative Tests Required:**
- Queries where unqualified columns genuinely belong to a joined table, not the FROM table (edge case — SQL dialect dependent)

**New Data Validation Requirement:** Low priority. Structural fix, general-purpose.

---

### Fix 3: Compliance Table-Name Correction

**File/Location:** `services/schema_agent/schema_matcher.py:52`

**Original Behavior:** Referenced table names `["risk_flags", "kyc_status", "audit_logs"]` in the compliance schema matcher. Tables `kyc_status` and `audit_logs` do not exist in the actual schema.

**Corrected Behavior:** Changed to `["risk_flags", "kyc_cases", "compliance_violations"]`, matching actual table names in the database schema.

**Classification:** SCHEMA_GROUNDING_FIX

**Architecturally Justified:** Yes. Referencing non-existent tables guarantees SQL errors. This is a straightforward data correction — the schema matcher must reference actual schema elements.

**Holdout Motivation:** Compliance queries failed because of wrong table names. However, any compliance query against the real schema would have failed identically. This is not holdout-specific.

**Overfitting Risk:** LOW. Correcting table names to match the actual schema has zero benchmark-specific content. The fix is validated by the schema itself.

**Regression Tests Required:**
- Compliance queries that reference risk_flags, kyc_cases, compliance_violations
- Cross-domain queries that include compliance tables

**Negative Tests Required:**
- Queries for compliance-like concepts that should NOT match these tables (if any exist)

**New Data Validation Requirement:** None. Schema-grounded fix, validated by schema definition.

---

### Fix 4: Missing Phase 6C `else` Branch

**File/Location:** `services/intent_agent/intent_recognizer.py:413-414`

**Original Behavior:** Phase 6C (structured intent upgrade) only forwarded `ambiguities` and `requires_clarification` fields from structured intent. All other structured intent fields — including `domain`, `task`, `metrics`, `filters`, `time_range` — were silently dropped.

**Corrected Behavior:** Added `else: res[k] = res.get(k, False) or v` to forward remaining structured intent fields into the result, using a merge-with-OR strategy for boolean fields.

**Classification:** IMPLEMENTATION_BUG_FIX

**Architecturally Justified:** Yes. Phase 6C is an upgrade step in the intent recognition pipeline. Dropping fields that higher-fidelity analysis produced is a bug. The merge logic is a general-purpose pattern for combining keyword-based and structured intent results.

**Holdout Motivation:** This fix caused a 30-point regression during development (147→117) when temporarily removed, confirming it is load-bearing. The fix was motivated by observing this regression, but the underlying bug (dropping structured fields) would affect any query relying on structured intent.

**Overfitting Risk:** LOW. The fix is a general-purpose field merge. No holdout-specific logic is present. The `or` merge strategy for booleans is a reasonable default that preserves keyword-derived signals while allowing structured intent to upgrade them.

**Regression Tests Required:**
- Queries where structured intent provides domain, task, and metrics that keyword matching misses
- Queries where keyword matching provides signals that structured intent does not (ensure no regression)
- Queries where both sources agree (ensure no conflict)

**Negative Tests Required:**
- Queries where structured intent produces incorrect domain/task (ensure keyword fallback is preserved)

**New Data Validation Requirement:** Low priority. General-purpose pipeline fix.

---

### Fix 5: Gate Confidence Source Change

**File/Location:** `services/orchestrator/orchestrator_agent.py:89`

**Original Behavior:** The confidence gate used the keyword matcher's `confidence` score. This score gave very low values (~0.05) for valid queries that were well-captured by structured intent but poorly by keyword matching, causing valid queries to be incorrectly blocked.

**Corrected Behavior:** The gate now prefers `intent_confidence` (from structured intent) with fallback to the keyword matcher's `confidence`.

**Classification:** HEURISTIC_CHANGE

**Architecturally Justified:** Yes. The structured intent system was introduced to provide higher-fidelity intent classification than keyword matching. Using its confidence score in the gate is the architecturally correct integration point. The keyword matcher's confidence was always a rough heuristic.

**Holdout Motivation:** 17+ valid queries were incorrectly blocked by the old gate. These were queries where structured intent correctly identified the intent but keyword confidence was too low to pass the threshold. However, the architectural argument stands independently: if structured intent exists, its confidence should drive the gate.

**Overfitting Risk:** MEDIUM. While architecturally justified, the change affects gate behavior globally. Any query near the confidence boundary could be affected. The 17+ blocked queries were observed on the holdout, so the change was validated against that specific set. Independent validation on new data is needed.

**Regression Tests Required:**
- Queries that should pass the gate (valid, well-formed)
- Queries that should fail the gate (vague, ambiguous)
- Queries near the confidence boundary

**Negative Tests Required:**
- Queries where keyword confidence is high but structured intent confidence is low (edge case — should these pass or fail?)

**New Data Validation Required:** Yes. Must validate that the gate does not over-admit (allowing vague queries through) or under-admit (blocking valid queries) on unseen data.

---

### Fix 6: Confidence Threshold Change to 0.31

**File/Location:** `services/shared/config.py:102`

**Original Behavior:** `INTENT_CONFIDENCE_THRESHOLD` was set to `0.50`.

**Corrected Behavior:** Threshold lowered to `0.31`.

**Classification:** THRESHOLD_TUNING

**Architecturally Justified:** Partially. The original 0.50 threshold was designed for keyword matcher confidence distributions, not structured intent confidence distributions. When the gate source changed (Fix 5), the threshold needed recalibration. However, the specific value of 0.31 was chosen empirically against the holdout set.

**Holdout Motivation:** Directly motivated by holdout failures. The value 0.31 was selected after examining the original holdout queries and their confidence scores.

**Overfitting Risk:** HIGH. This threshold was tuned against the holdout. The value 0.31 may be optimal for the 160 holdout queries but may not generalize to arbitrary new queries. This is the highest-risk fix in the set.

**CRITICAL NOTE:** This threshold was selected after examining the original holdout. The 160/160 benchmark result is NOT an independent generalization estimate when this threshold is included. Independent validation on a truly held-out dataset (not used for any tuning) is mandatory.

**Regression Tests Required:**
- Full holdout set re-evaluation (already done — 160/160)
- Sensitivity analysis: test at thresholds 0.25, 0.31, 0.35, 0.40, 0.50

**Negative Tests Required:**
- Queries with confidence scores between 0.31 and 0.50 — these were previously blocked, now admitted. Must verify they are all valid.

**New Data Validation Required:** MANDATORY. This threshold must be validated on a dataset not used for any tuning decisions. Ideally, run the full benchmark on a new set of 100+ queries with threshold sensitivity reporting.

---

### Fix 7: Vagueness Query-Text Patterns

**File/Location:** `services/intent_agent/intent_recognizer.py:290-294` and `services/intent_agent/intent_recognizer.py:399-408`

**Original Behavior:** No direct query-text vagueness checks existed. Structured intent could override keyword ambiguity signals, causing genuinely vague informational requests to be treated as specific analytical queries.

**Corrected Behavior:** Added text patterns: "need info", "info about", "informations sur", "besoin d'informations". Queries matching these patterns are marked as vague, preventing structured intent override.

**Classification:** VOCABULARY_ENRICHMENT + HEURISTIC_CHANGE

**Architecturally Justified:** Partially. Direct text pattern matching for vagueness is a reasonable layer in the intent pipeline — some queries are structurally vague regardless of domain vocabulary. However, the specific patterns were chosen to match holdout queries.

**Holdout Motivation:** Yes. The patterns were specifically added to fix H090 ("I need info about customers") and H094 ("J'ai besoin d'informations sur les comptes"). The pattern list is small and targeted at these failures.

**Overfitting Risk:** MEDIUM. The patterns are general enough to catch a class of vague informational requests, but they were derived from two specific holdout failures. New vague queries using different phrasing (e.g., "tell me about", "what can you tell me about", "give me details on") would not be caught by these patterns. The fix addresses a symptom (specific phrasings) rather than the root cause (a general vagueness detector).

**Regression Tests Required:**
- H090 and H094 equivalents (already passing)
- Other vague informational queries with different phrasings
- Non-vague queries that coincidentally contain "info" (e.g., "information security policy violations")

**Negative Tests Required:**
- Queries containing "info" that are NOT vague (must not be incorrectly marked as vague)
- Vague queries in other languages (French, Arabic) with different phrasings

**New Data Validation Required:** Yes. Must verify that the pattern list does not cause false positives on new data and that new vague queries (not using these exact phrasings) are still caught by other vagueness signals.

---

### Fix 8: Sanctions and Screening Vocabulary

**File/Location:** `services/intent_agent/structured_intent.py:67-72`

**Original Behavior:** The compliance domain vocabulary did not include sanctions/screening terms. Queries about sanctions screening were misclassified (likely to a different domain or as ambiguous).

**Corrected Behavior:** Added "sanctions", "screening", "sanctions screening", "ofac", "lists" to the compliance domain vocabulary.

**Classification:** VOCABULARY_ENRICHMENT

**Architecturally Justified:** Yes. Sanctions screening is a standard compliance function in banking. Omitting these terms from the compliance vocabulary is an oversight in domain modeling, not a benchmark-specific fix.

**Holdout Motivation:** Fixed H065 ("How many sanctions screening checks were completed last month?"). However, any sanctions-related query would have failed identically before the fix.

**Overfitting Risk:** LOW. Standard compliance vocabulary. "Sanctions", "screening", and "OFAC" are universal banking compliance terms. Their absence was a gap in domain coverage.

**Regression Tests Required:**
- Sanctions screening queries (various phrasings)
- Compliance queries that should NOT be classified as sanctions (e.g., KYC, AML without sanctions)

**Negative Tests Required:**
- Non-compliance queries that coincidentally mention "screening" (e.g., "employee screening process")

**New Data Validation Requirement:** None. Vocabulary enrichment with universally recognized domain terms.

---

## 3. Overfitting Risk Summary Table

| Fix | Description | Classification | Holdout-Motivated | Overfitting Risk | New Data Required |
|---|---|---|---|---|---|
| 1 | SQL JOIN Deduplication | IMPLEMENTATION_BUG_FIX | Yes (trigger) | LOW | No |
| 2 | SELECT Column primary_table | IMPLEMENTATION_BUG_FIX | Yes (trigger) | LOW | No |
| 3 | Compliance Table Names | SCHEMA_GROUNDING_FIX | Yes (trigger) | LOW | No |
| 4 | Phase 6C else Branch | IMPLEMENTATION_BUG_FIX | Yes (trigger) | LOW | No |
| 5 | Gate Confidence Source | HEURISTIC_CHANGE | Yes (17+ blocked) | MEDIUM | Yes |
| 6 | Threshold → 0.31 | THRESHOLD_TUNING | Yes (tuned) | **HIGH** | **MANDATORY** |
| 7 | Vagueness Text Patterns | VOCABULARY_ENRICHMENT + HEURISTIC_CHANGE | Yes (tuned) | MEDIUM | Yes |
| 8 | Sanctions Vocabulary | VOCABULARY_ENRICHMENT | Yes (trigger) | LOW | No |

**Legend:**
- **LOW**: Architecturally justified independent of holdout; no benchmark-specific logic
- **MEDIUM**: Architecturally justified but validated primarily against holdout; global behavior change
- **HIGH**: Tuned against holdout; specific numeric value chosen empirically; not independently validated

---

## 4. Mandatory New Dataset Validation Requirements

### Critical: Fix 6 (Threshold = 0.31)

The confidence threshold of 0.31 was selected by examining holdout query confidence scores. This creates a direct data-leakage vector: the threshold is optimized for the same data it is evaluated on.

**Required actions:**
1. Generate a new dataset of 100+ queries NOT used in any prior benchmark or tuning
2. Evaluate at threshold 0.31 and report pass rate
3. Run threshold sensitivity analysis (0.25, 0.31, 0.35, 0.40, 0.50) on new data
4. Report false positive rate (vague queries admitted) and false negative rate (valid queries blocked)

### Important: Fix 7 (Vagueness Patterns)

The vagueness patterns were derived from two specific holdout queries (H090, H094). While architecturally reasonable, the pattern list may not generalize.

**Required actions:**
1. Test against new vague queries with different phrasings
2. Test for false positives (non-vague queries matching patterns)
3. Consider a more general vagueness detection mechanism as follow-up

### Important: Fix 5 (Gate Confidence Source)

The gate now uses structured intent confidence. This is architecturally correct but changes global gate behavior.

**Required actions:**
1. Validate on new data that the gate does not over-admit or under-admit
2. Report queries near the decision boundary

### Statement on 160/160 Result

**The 160/160 benchmark result is NOT an independent generalization estimate.** Fixes 5, 6, and 7 were tuned or validated against the holdout set. The perfect score reflects the system's performance on data that informed its configuration, not on truly unseen data. This is standard practice in iterative development, but the result should be reported with this caveat until independent validation is complete.

---

## 5. Methodology Statement

This audit was conducted by:

1. **Reading each fix's source code** to verify the described behavior matches actual implementation
2. **Classifying each fix** into one of: IMPLEMENTATION_BUG_FIX, SCHEMA_GROUNDING_FIX, HEURISTIC_CHANGE, THRESHOLD_TUNING, VOCABULARY_ENRICHMENT
3. **Evaluating architectural justification** independent of holdout context — would this fix be correct if the holdout never existed?
4. **Assessing holdout motivation** — was this fix triggered by, tuned against, or validated primarily on the holdout?
5. **Estimating overfitting risk** using a three-tier scale (LOW/MEDIUM/HIGH) based on:
   - Whether the fix introduces benchmark-specific logic
   - Whether the fix's numeric parameters were tuned on the evaluation data
   - Whether the fix affects global system behavior vs. local structural correctness
6. **Defining regression and negative test requirements** to ensure fixes do not introduce new failures
7. **Identifying new data validation requirements** to establish independent generalization estimates

**Classification criteria:**
- **IMPLEMENTATION_BUG_FIX**: Corrects a defect in implementation logic that would fail on general inputs
- **SCHEMA_GROUNDING_FIX**: Corrects a mismatch between code and actual schema/data
- **HEURISTIC_CHANGE**: Modifies a heuristic or decision logic; behavior changes for some inputs
- **THRESHOLD_TUNING**: Adjusts a numeric threshold; directly affects decision boundaries
- **VOCABULARY_ENRICHMENT**: Adds domain terms or patterns; expands coverage for specific concepts

**Risk escalation criteria:**
- **LOW**: Fix is structurally correct, operates on general properties, no benchmark-specific parameters
- **MEDIUM**: Fix is architecturally justified but was validated primarily on holdout; affects global behavior
- **HIGH**: Fix's parameters were tuned against evaluation data; requires independent validation

---

*End of FIX AUDIT REPORT*
