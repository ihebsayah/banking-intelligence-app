# Grounded LLM Insights Layer (STEP 4)

**Status:** COMPLETE
**Version:** 4.0.0
**Last Updated:** 2026-08-31

---

## 1. Purpose

Turn deterministic analytics into business-readable interpretation WITHOUT
letting the LLM invent anything. The LLM (Mistral via Ollama) may only
synthesize, prioritize, and rephrase **verified facts** produced by the
deterministic fact layer (STEP 2). Everything it says is validated against
those facts by a deterministic grounding validator; any hallucination,
unsupported number, or forbidden claim rejects the entire output and falls
back to the deterministic summary. The LLM is an optional presentation
layer, never a source of truth.

## 2. Architecture

```
 AnalyticalFactPackage  (deterministic, STEP 2)
        │
        ▼
 VerifiedFactPayloadBuilder ──▶ bounded, fact-ID-tagged payload (F/A/C/D/T/R)
        │                             + allowed-numerics set
        ▼
   system prompt (fixed) + payload + user_question-as-data
        │
        ▼
      Mistral / Ollama  (JSON-only, temp 0.1, ≤512 tokens, 30s timeout)
        │
        ▼
  Pydantic (LLMInsightOutput) ──▶ GroundingValidator ──▶ YES ─▶ InterpretationResult (llm)
        │                                │
        └──────────── any failure ────────┴────────▶  llm_fallback + reason code
        (called only when NecessityGate says useful AND ENABLE_LLM_INSIGHTS=true)
```

## 3. Boundary (what the LLM may NOT do)

Enforced by construction + validation:

- NO metric calculation / recalculation
- NO new numbers, trends, anomalies, or causes
- NO fraud / illegality / AML / regulatory inference (forbidden claims)
- NO SQL generation, DB access, or raw row access
- LLM never decides whether it is invoked (the gate does)

The payload contains only sanitized verified facts (no raw rows, credentials,
schema dumps, or tokens).

## 4. Strict Input Boundary

`VerifiedFactPayload` is the ONLY thing the LLM sees besides the fixed system
prompt and the user question (which is injected as **data**, delimited and
explicitly marked "not instructions"). No customer PII rows are included.

## 5. Fact Selection & Bounding

Deterministic selection, capped to bound token usage and focus:

| Tag | Content | Cap |
|-----|---------|-----|
| F | per-column descriptive metrics (count, sum, mean, median, min, max, std, p25, p90) | 8 columns |
| D | categorical distributions (dominant, share, unique count) | 6 |
| A | anomalies (observed, severity, deviation σ, mean, std) | 10, by deviation |
| C | correlations (Pearson r, column pair, sample size) | 5, by \|r\| |
| T | period-over-period comparisons (Δ%, prev, current, period labels) | 5 |
| R | recommendation candidates (message, evidence) | all |

Each fact carries a stable ID for traceability and grounding.

## 6. Numeric Grounding (anti-hallucination)

The payload records an **allowed-numbers set** = every numeric value present
in the facts (metric values, anomaly observed/deviation, correlation
coefficients, temporal values, evidence values, embedded numbers in text).

`GroundingValidator._first_unsupported_number` extracts every numeric literal
from the LLM summary + limitations and rejects output if any is NOT in the
allowed set, except small integers ≤15 (list enumeration). Formatting is
normalized (`18250`, `18,250`, `18,250.00` → same value).

**Rejection is all-or-nothing:** one unsupported number → REJECT entire output
→ deterministic fallback + `UNSUPPORTED_NUMERIC_CLAIM`.

## 7. Fact-ID Grounding

Every `key_observation` and `recommendation` must cite ≥1 `fact_id` that
exists in the payload. Unknown IDs → fallback (`UNKNOWN_FACT_ID`). Missing
IDs → fallback (`OBSERVATION_NO_FACT` / `RECOMMENDATION_NO_FACT`).

## 8. Wording Guardrails

- **Forbidden claims** (`fraud`, `fraudulent`, `illegal`, `money laundering`,
  `AML violation`, `regulatory breach`, `sanction violation`) → `FORBIDDEN_CLAIM`.
- **Causality wording** (`causes`, `drives`, `results from`, etc.) → 
  `CAUSALITY_CLAIM`; correlations must read as association.
- Negated mentions ("no fraud", "does not cause") are legitimate and allowed.
- "Anomaly" is defined as *statistically unusual per the configured method*,
  never "suspicious" or "fraudulent".

## 9. Recommendations

The LLM may ONLY rephrase existing `RecommendationCandidate` items (R facts).
The system prompt states this; grounding enforces fact-ID citation. If no
candidates exist, recommendations resolve to `[]` on the LLM path (and the
deterministic path already returns `[]`).

## 10. Output Contract

`LLMInsightOutput` (Pydantic): `summary` (str), `key_observations`
(≤5, each with fact_ids), `recommendations` (≤3), `limitations` (≤3).
Returned as `InterpretationResult` with `GenerationMetadata`:

- `generation_mode`: `"llm"` | `"llm_fallback"` | `"deterministic"`
- `model_name`, `latency_ms`, `fallback_reason`, `gate_reason_codes`

## 11. Deterministic Fallback

Any fault (unavailable, timeout, HTTP error, malformed JSON, schema
violation, grounding violation, forbidden claim, unsupported number) returns
an `InterpretationResult` with `generation_mode="llm_fallback"` and a reason
code. The generator only adopts LLM output when mode == `"llm"`; otherwise it
keeps the deterministic summary/recommendations (authoritative fallback).

## 12. Language Support

FR + EN surfaced by the LLM following the user question's language. No
separate translation LLM. The deterministic fallback remains the fast path.

## 13. Runtime Configuration

| Setting | Default | Notes |
|---------|---------|-------|
| `ENABLE_LLM_INSIGHTS` | false | kill switch; off by default |
| `INSIGHTS_LLM_MODEL` | mistral | explicit (was overridden to tinyllama) |
| `INSIGHTS_LLM_TIMEOUT` | 30s | conservative; STEP 5 benchmarks/tunes |
| `INSIGHTS_LLM_TEMPERATURE` | 0.1 | low for reproducibility |
| `INSIGHTS_LLM_MAX_TOKENS` | 512 | bounded |

## 14. Prompt Safety (injection)

The user question is wrapped in `<user_question>…</user_question>` and stated
to be data, not instructions. The system prompt is fixed and never receives
user text. The grounding validator is the final backstop (injected numbers
fail numeric grounding).

## 15. Integration Point

`InsightsGenerator.generate()`: after the gate sets `decision.use_llm` and
`ENABLE_LLM_INSIGHTS` is true, call
`MistralIntegrator.interpret(fact_package, query_intent, query_text, reason_codes)`.
On `mode=="llm"`, adopt summary + rephrased recommendations; the deterministic
components (metrics, trends, anomalies, confidence) are always the generative
product and never LLM-produced.

## 16. Files Changed

- `services/insights_agent/mistral_integrator.py` — replaced with grounded
  implementation (was 365 lines of legacy dead methods).
- `services/insights_agent/insights_generator.py` — wired to `interpret()`.
- `services/insights_agent/config.py` — added STEP 4 runtime settings.
- `services/insights_agent/models.py` — `LLMInsightOutput`, `GenerationMetadata`,
  `InterpretationResult` (added earlier this step).
- `docker-compose.yml` — Insights service passes `INSIGHTS_LLM_MODEL` explicitly.
- `.env.example` — documented new flags.
- `tests/test_grounded_llm.py` (new), `tests/test_insights_agent.py` (updated mock).

## 17. Correctness Properties

1. LLM failure never degrades correctness (deterministic fallback).
2. Every LLM number is verifiable against the allowed set.
3. Every observation/recommendation cites a real fact ID.
4. Forbidden/overreach claims are rejected, not softened.
5. LLM invocation is always gated (no self-selection).
6. Off-by-default: no behavior change unless explicitly enabled.

## 18. Test Coverage

- `tests/test_grounded_llm.py` (22): structured output, numeric grounding,
  wording constraints (fraud/causation + negation), transport failures,
  prompt safety/injection, fact bounding, no-raw-rows, metadata, E2E
  (direct→no LLM; analytical+flag off→deterministic; flag on+mock→grounded;
  hallucination→fallback; unavailable→fallback).
- Full insights suite: **76 passing**.

## 19. Gated Invocation Summary

| Gate + flag | Route |
|-------------|-------|
| `use_llm=false` | deterministic (no LLM call) |
| `use_llm=true`, flag off | deterministic (no LLM call) |
| `use_llm=true`, flag on | grounded LLM; any failure → deterministic fallback |

## 20. Operational Monitoring

The generator records `generation_mode` in `key_metrics` so consumers can
distinguish deterministic vs LLM output. The integrator logs per-call
model/latency/fact-count/observation-count.

## 21. STEP 5 Handoff

- Benchmark `INSIGHTS_LLM_TIMEOUT` (30s default) against real Ollama latency.
- Tune temperature/tokens; validate against the benchmark harness.
- Consider surfacing `InterpretationResult.metadata` in the API response.
