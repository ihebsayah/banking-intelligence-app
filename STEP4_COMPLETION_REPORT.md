# STEP 4 — Implementation Report: Grounded Mistral Interpretation Layer

**Date:** 2026-08-31
**Program:** Multi-agent/LLM pipeline optimization (5-step)
**STEP 3 status:** COMPLETE
**Recommendation for STEP 5:** **NOT READY** — see §R.

---

## A. Objective

Introduce a grounded Mistral interpretation layer where deterministic software
(STEP 2) establishes what is true and Mistral only explains verified facts.
Enforce strict grounding validation with deterministic fallback. The LLM is a
presentation layer, never a source of truth.

## B. Non-Goals (respected)

Intent Agent, Orchestrator planner, Validation/Compliance/Execution Agents, SQL
generation, DB access, cloud LLM APIs, RAG, tool calling, Workbench, Customer
360, production enablement (`ENABLE_LLM_INSIGHTS` stays false,
`ENABLE_INSIGHTS_AGENT` stays false).

## C. Invariants Upheld

- LLM never calculates metrics, invents numbers/trends/anomalies/causes, infers
  fraud, makes compliance/regulatory decisions, generates SQL, or sees raw rows.
- Fact package is the only factual truth.
- Gated invocation (LLM never decides if it runs).
- JSON-only output (Pydantic + grounding validated).
- Summary ≤4 sentences; ≤5 observations; ≤3 recommendations; ≤3 limitations;
  temperature 0.1; tokens ≤512; timeout 30s.
- Temporal comparison stays period-grouped; evidence quality measures data
  quality, not pattern presence; no hardcoded confidence.

## D. What Was Built

Replaced the legacy `mistral_integrator.py` (365 lines of dead methods) with a
lean grounded implementation exposing a single `interpret(...)` API:

1. **`VerifiedFactPayload`** — sanitized, bounded, fact-ID-tagged payload
   (F/D/A/C/T/R) + allowed-numerics set. No raw rows, credentials, or tokens.
2. **`GroundingValidator`** — fact-ID existence, numeric grounding with
   normalization, forbidden/causality claim checks (negation-aware).
3. **`MistralIntegrator.interpret(...)`** — Ollama call (JSON-only `format`,
   temp 0.1, `num_predict≤512`, 30s timeout), JSON extraction, Pydantic schema,
   then grounding; any failure → `llm_fallback` + reason code.

## E. Files Changed

| File | Change |
|------|--------|
| `services/insights_agent/mistral_integrator.py` | replaced with grounded implementation |
| `services/insights_agent/insights_generator.py` | wired to `interpret()`; merges summary/recommendations only on `mode=="llm"` |
| `services/insights_agent/config.py` | `INSIGHTS_LLM_MODEL/TIMEOUT/TEMPERATURE/MAX_TOKENS`, `ENABLE_LLM_INSIGHTS` |
| `services/insights_agent/models.py` | `LLMInsightOutput`, `GenerationMetadata`, `InterpretationResult` (STEP 4 models) |
| `docker-compose.yml` | Insights service passes `INSIGHTS_LLM_MODEL=${INSIGHTS_LLM_MODEL:-mistral}`; kills the `tinyllama` override |
| `.env.example` | documented new flags |
| `tests/test_grounded_llm.py` | new — 22 tests |
| `tests/test_insights_agent.py` | updated mock (`generate_summary_from_facts` → `interpret`) |

## F. Test Results

| Suite | Passed |
|-------|--------|
| `test_insights_agent.py` | 36 |
| `test_necessity_gate.py` | 17 |
| `test_grounded_llm.py` (new) | 22 |
| `benchmark_necessity_gate.py` | 1 |
| **Total** | **76** |

## G. Grounding Failure Map

| Condition | Reason code | Outcome |
|-----------|-------------|---------|
| Unavailable / empty / timeout | `LLM_UNAVAILABLE_OR_EMPTY` | fallback |
| Malformed JSON / fences | `MALFORMED_JSON` | fallback |
| Schema violation | `SCHEMA_VIOLATION` | fallback |
| Unknown fact ID | `UNKNOWN_FACT_ID:<id>` | fallback |
| Missing fact IDs | `OBSERVATION_NO_FACT` / `RECOMMENDATION_NO_FACT` | fallback |
| Unsupported numeric | `UNSUPPORTED_NUMERIC_CLAIM:<tok>` | fallback (all-or-nothing) |
| Fraud/illegal wording | `FORBIDDEN_CLAIM` | fallback |
| Causality wording | `CAUSALITY_CLAIM` | fallback |

## H. Correctness Properties Verified

1. LLM failure never degrades correctness (deterministic fallback).
2. Every LLM number verifiable against the allowed set; formatting normalized.
3. Every observation/recommendation cites a real fact ID.
4. Forbidden/overreach claims rejected, not softened.
5. Invocation always gated.
6. Off by default — no behavioral change when disabled.

## I. Safety / Injection

User question wrapped and marked as data; fixed system prompt; grounding is the
backstop. Verified with a prompt-injection test.

## J. Numeric Grounding Details

Rejects any numeric literal not in the allowed set, except integers ≤15
(list enumeration). Rounding normalized to 2dp; thousands separators tolerated.

## K. Fallback Semantics

`InterpretationResult.metadata.generation_mode` = `"llm"` | `"llm_fallback"` |
`"deterministic"`. The generator adopts LLM output only on `"llm"`, else keeps
the deterministic summary/recommendations (authoritative).

## L. Configuration Surface

See `GROUNDED_LLM_INSIGHTS_LAYER.md` §13. `docker-compose` now sets
`INSIGHTS_LLM_MODEL` explicitly; the `MISTRAL_MODEL=tinyllama` override is fixed
to `mistral` (once configurable).

## M. Regression

All 76 insights tests pass. No production enablement; default path unchanged
(deterministic).

## N. Documentation

`GROUNDED_LLM_INSIGHTS_LAYER.md` (21 sections) written.

## O. Deferred / Known Constraints

- No live Ollama latency validation (local service not exercised in tests;
  mocked transport). STEP 5 benchmarks real timeout.
- `query_intent` passed but not embedded in the prompt (tracing only).
- Fallback returns empty summary/observations in the `InterpretationResult` —
  the generator's deterministic output is authoritative and unaffected.

## P. Opportunities for the Lazy Path Forward

- Single prompt/facts blob already bounded; no RAG needed for STEP 5.
- No separate tuning service — temperature/token knobs are config.

## Q. Blockers / Risks

- Real Ollama availability + latency unspecified in CI; STEP 5 must validate
  the 30s timeout and JSON mode behavior against a real runtime before enabling.

## R. Verdict

**NOT READY** to enable `ENABLE_LLM_INSIGHTS` in production. The grounded
layer is implemented, deterministic fallback is bulletproof, and the suite is
green — but STEP 5 (live benchmarking, timeout/temperature/token tuning, and a
real Ollama integration validation) must complete before flipping the flag.
Code-complete and safe-off by default.
