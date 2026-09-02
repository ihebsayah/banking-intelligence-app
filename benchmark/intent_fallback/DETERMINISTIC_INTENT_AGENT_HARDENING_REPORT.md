# DETERMINISTIC INTENT AGENT HARDENING REPORT — STEP 11

## Executive Summary

**VERDICT: READY for deterministic operation. No LLM added.**

The intent agent is hardened with a consolidated **bilingual (FR+EN) keyword registry**, an **evidence-based certainty score** (replacing keyword-density confidence), **explicit zero-match routing** to `unknown`, **machine-readable ambiguity codes**, an **analytical-substance gate**, and **benign-tie disambiguation**. All 13 categories are now language-supported independently of `SEMANTIC_LAYER_ENABLED`.

Headline gains on the frozen 83-case regression set (`baseline_step10_deterministic.json`):

| Metric | Step 10 | Step 11 | Δ |
|---|---|---|---|
| Intent accuracy | 42.2% (35/83) | **60.2%** (50/83) | **+18.1 pts** |
| Clarification accuracy | 51.8% (43/83) | **63.9%** (53/83) | **+12.1 pts** |
| French intent accuracy | 33.3% (30) | **66.7%** (30) | **+33.4 pts** |
| English intent accuracy | 48.1% (52) | **57.7%** (52) | +9.6 pts |
| Constraints accuracy | 68.8% | 68.8% | 0 |
| Injection blocked | 8/8 | **8/8** | 0 (all blocked) |
| Unsupported blocked | 4/5 | 4/5 | 0 |
| Latency p50 | 7.27 ms | **5.26 ms** | faster |

The raw-keyword FR baseline figure (33.3%) rises to 66.7% purely by switching the fallback registry to bilingual keywords. This is separate and complementary to the semantic-success variant (60.0% in the Step-10 report) which credited a clarification question as success; here FR intent is scored on correct `primary_category` only.

---

## 1. What Changed (`services/intent_agent/intent_recognizer.py`, `models.py`)

### 1a. Consolidated bilingual registry (always on)
New `BILINGUAL_CATEGORY_REGISTRY` covers **all 13 intent categories** (was 8): `customer_analysis`, `risk_analysis`, `revenue_analysis`, `operational_analysis`, `geographic_analysis`, `product_analysis`, `compliance_analysis`, `transaction_analysis`, `loan_analysis`, `kyc_analysis`, `aml_analysis`, `profitability_analysis`, `liquidity_analysis`. Each holds **EN + FR** keyword lists.

- `_score_categories` now takes the raw query + tokens and **always** uses the bilingual registry — no conditional on `SEMANTIC_LAYER_ENABLED`. Basic language support is no longer coupled to the semantic metadata DB layer.
- `BILINGUAL_PHRASES` + `_PHRASE_TO_CATEGORY` handle multiword terms/abbreviations (`npl ratio`, `pnb`, `roe`, `roa`, `lcr`, `loan_to_deposit`, `taux de créances classées`) against the raw lowercased query.
- Categories previously missing from the 8-keyword map (`loan`, `kyc`, `aml`, `profitability`, `liquidity`) are now first-class.
- The now-dead `ORIGINAL_CATEGORY_KEYWORDS` and `SEMANTIC_CATEGORY_KEYWORDS` dicts (which caused the FR coupling bug) were **deleted** — no code or test referenced them after the registry replaced the conditional.

### 1b. No arbitrary zero-match default
When total score == 0, `primary_category` is now **`"unknown"`** (previously an arbitrary fallback category with confidence 0.05). Downstream is untouched: the orchestrator's `_get_primary_entity("unknown")` already defaults to `"customer"`, and these queries are routed via `supported_capability=False` so the gate rejects before classification.

### 1c. Evidence score (not keyword density)
`confidence` semantics change from density → evidence. A new additive `intent_evidence_score` combines:
- **margin** (top1 − top2, subject-vs-runner-up separation)
- **token coverage** — how much of the query anchored the category
- **hard-ambiguity caps** — NO_INTENT_MATCH / DOMAIN_UNCLEAR cap ≤ 0.10; UNRESOLVED_REFERENCE / COMPOUND_UNSUPPORTED / AMBIGUOUS_METRIC / AMBIGUOUS_ENTITY / NO_ANALYTICAL_SUBSTANCE cap ≤ 0.28; INTENT_TIE (soft) ≤ 0.55; MISSING_TIME_CONTEXT ≤ 0.70.

The cap symmetry is deliberate: `INTENT_CONFIDENCE_THRESHOLD = 0.2` (shared/config, pre-existing). NO_INTENT_MATCH / DOMAIN_UNCLEAR are capped at 0.10 and NO_ANALYTICAL_SUBSTANCE at 0.28, both **below 0.2**, so the orchestrator's clarification/confidence gate fires on genuinely vague or cold queries. We do **not** claim probabilistic calibration — this is a deterministic ranking score.

`INTENT_TIE` is a **SOFT** ambiguous code (not in `HARD_AMBIGUITY_CODES`): a near-tie between categories is cleared by strong structured enrichment (domain + dimensions/filter/limit), because a keyword-overlap split is usually resolved once the structured intent pins the entity and measure. It only stays a clarification (`requires_clarification=True`) when the query lacks that structure (e.g. bare "Montre-moi les produits"). The orchestrator gate then sees `confidence==0.2` below the threshold and CLARIFYs rather than auto-accepts or hard-rejects.

`confidence` is kept and mapped to the evidence score for API back-compat; additive `intent_evidence_score`, `top1_score`, `top2_score`, `absolute_margin`, `relative_margin`, `ambiguity_codes`, `decision` are added to `models.py`.

### 1d. Ambiguity codes + hard-gated override
New machine codes: `NO_INTENT_MATCH`, `INTENT_TIE`, `AMBIGUOUS_METRIC`, `AMBIGUOUS_ENTITY`, `MISSING_TIME_CONTEXT`, `UNRESOLVED_REFERENCE`, `COMPOUND_UNSUPPORTED`, `TOO_SHORT`, `DOMAIN_UNCLEAR`, `NO_ANALYTICAL_SUBSTANCE` — stored in additive `ambiguity_codes`. Human text stays in `ambiguities` for compatibility.

The Phase-6C structured override was the Step-10 root cause: it could clear `requires_clarification` even when the query was genuinely vague. Now **only SOFT ambiguities may be cleared** by strong structured enrichment; any HARD code (`HARD_AMBIGUITY_CODES`) keeps `requires_clarification=True`. The gating risk-level re-escalation override is likewise gated on no-hard-ambiguity.

### 1e. Analytical-substance gate (`NO_ANALYTICAL_SUBSTANCE`)
A category keyword match is NOT sufficient for a legible intent. A bare descriptive statement ("I need info about customers", "Tell me about accounts") matches a category but carries no metric/dimension/time/limit/filter or explicit measure verb → **must clarify**. The gate uses both structured fields and a raw-text analytical-hint check (`_has_analytical_hint`: measure verbs, quantifiers, time phrases, dimension frames) so it does not depend on structured-parsing gaps.

### 1f. Benign-tie disambiguation (`_is_benign_tie`)
A near-tie is NOT a competing intent when:
- **subject + dimension composition** — "revenue BY branch": branch is a dimension, not a second intent (`_is_dimension_composition`).
- **same-family synonym pair** — revenue/profitability, compliance/risk, kyc/aml describe one subject (`_is_same_family_tie`).

Both cases are treated as a single intent (no `INTENT_TIE`, dimension/synonym contributes to confidence rather than depressing margin). This fixes prior false-rejection of clear queries like "Show revenue by branch for last month" and "Show compliance status for this year".

### 1g. Off-domain routing
Non-banking queries (`_is_off_domain`) and zero-match set `supported_capability=False` + `clarification_question` (FR), so the orchestrator gate rejects at line 85 — before classification, and independent of certainty.

### 1h. Deterministic decision
Additive `decision`: `AUTO_ACCEPT` / `CLARIFY` / `REJECT`. Security gating runs first and independent of certainty: adversarial patterns → `risk_level="adversarial"`, unsupported capabilities → `risk_level="suspicious"` → both `REJECT`. A genuine near-tie or low-evidence-but-scoped query → `CLARIFY` (not hard reject).

---

## 2. Regression vs Frozen Baseline (83 cases)

Saved to `deterministic_benchmark_results.json`.
- **Intent** 35 → 50 correct (`+15`)
- **Clarification** 43/83 → 53/83 (`+10`, verified each change via per-case diff vs `baseline_step10_deterministic.json`)
- **Constraints** unchanged 68.8%
- **Security** all 8 injections still blocked; 4/5 unsupported blocked
- **Latency** p50 7.27 → 5.26 ms (registry is same cost; more categories but no LLM)

### Category breakdown (Step 11)
- `clear_en` 8/10 (80%), `clear_fr` 9/10 (90%), `sql_injection` 3/3 (100%), `injection` (prompt) 0/5 (all successfully gated), `ambiguous` 3/5 (60%), `unclear_entity` 2/5 (40%), `unsupported` 4/5 (80%), `followup` 2/5.

---

## 3. Known Limitations (documented, not re-labeled)

- **`ambiguities` compat strings** from `structured_intent.py` (`too_short_query`, `ambiguous_risk_metric`) still leak as literal strings into the human `ambiguities` list. They are advisory and do not drive the hard-clear logic — a pre-existing structured_intent emission, preserved for back-compat.
- **Genuine keyword-overlap ties** (e.g. "how many bad loans": "loan" is both a credit and a product keyword) resolve to **risk_analysis** thanks to the EN `bad` keyword (mirroring the existing FR `mauvais`) and strong structured domain (`loans` + aggregation). Genuinely unstructured ties — e.g. bare "Montre-moi les produits" (product vs revenue, nothing to count/list) — still CLARIFY. This is a real ambiguity, not a false rejection, and is the safe default.
- **3 pre-existing unit-test failures** in `test_intent_agent.py` (`test_structured_intent_en/fr/clarification`) fail identically on the clean baseline (verified via `git stash`). They concern `structured_intent.py` `dimensions`/`intent_confidence`, not this hardening.
- **Chinese/mixed-script** queries still yield `unknown` (`unknown` is a correct non-fabrication; a multilingual tokenizer is out of scope).

---

## 4. Correctness Invariants Preserved

- **API contract**: `primary_category`, `secondary_categories` (non-null, may be empty), `confidence`, `explicit_constraints`, `ambiguities`, `requires_clarification` all present. New fields are additive only.
- **`unknown` is safe**: orchestrator `_get_primary_entity("unknown")` → `"customer"`, and these are gated out via `supported_capability=False`.
- **Security independent of certainty**: adversarial/unsupported gating runs regardless of evidence score.
- **Baseline immutable**: the original 83 cases were not relabeled; regression uses the frozen copy.

---

## 5. How To Re-run

```bash
# Regression on the frozen 83 cases
python benchmark/intent_fallback/intent_benchmark.py
# Compare intent_accuracy against baseline_step10_deterministic.json (0.4217 → 0.6024)

# Unit tests
python -m pytest tests/test_request_gating.py tests/test_vagueness_logic.py tests/test_integration.py  # all pass
python -m pytest tests/test_intent_agent.py   # 3 pre-existing structured_intent failures (verified pre-existing)
```

No configuration, `.env`, or threshold changes were made.