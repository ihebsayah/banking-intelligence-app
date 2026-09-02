# LOCAL LLM MODEL SELECTION REPORT (STEP 7)

Date: 2026-09-01
Owner: AI Engineer (multi-agent / LLM pipeline optimization)
Task: Find a compact local model (~2–4B) that can outperform Mistral 7B on the
strict **grounded analytics** contract on an Apple M1 16 GB, or conclude
NO MODEL QUALIFIES.

Scope guards honored: architecture untouched, validator not weakened, no SQL/DB
access by LLM, `ENABLE_LLM_INSIGHTS=false` throughout.

---

## 1. Executive Summary

**No compact local model qualifies for the strict grounded-analytics contract.**
Two independent Qwen candidates were evaluated against the existing benchmark
and both failed on the **critical numeric-fidelity** axis — the exact disease
that disqualified Mistral 7B:

- **qwen3:4b** — non-functional as a pipeline model: Ollama (0.21.1 and, after
  upgrading, 0.33.0) never returns its output in `/api/generate` `response`;
  it always lands in the `thinking` channel, so the production pipeline receives
  an empty answer. When that output is salvaged, it still hallucinates an
  unsupported number (`700.0`).
- **qwen2.5:3b** — works correctly through `/api/generate`, but **invents
  numbers** (fabricated standard deviations, exposure totals, years). Quick
  screen: **4/5 cases rejected** by `GroundingValidator` as
  `UNSUPPORTED_NUMERIC_CLAIM`.

Across all three locally tested models (Mistral 7B, Qwen3 4B, Qwen2.5 3B) the
failure signature is identical: small local models cannot be trusted to
**reproduce exact numbers** from a verified fact payload. The deterministic
`GroundingValidator` correctly catches every violation, so nothing ungrounded
ever reaches the user — but the LLM "useful" path is dead on this hardware.

**Final verdict: KEEP_DISABLED. No STEP 8 (enablement) justified.**

---

## 2. Environment

- Apple M1, arm64, 16 GB unified memory, 8 CPUs.
- Native Ollama on macOS (Homebrew), **upgraded 0.21.1 → 0.33.0** during this
  STEP (attempted to fix Qwen3 thinking-mode handling; see §16).
- Metal backend: candidates load at **100% GPU**; resident ~2.2–3.5 GB.
- Native Ollama bound `0.0.0.0:11434`, reachable from Docker via
  `host.docker.internal:11434`.
- Deterministic Insights layer is authoritative; `ENABLE_LLM_INSIGHTS=false`.

## 3. Candidate Discovery

Discovery considered the Ollama library's compact (~2–4B) instruct families
that prioritize instruction-following and structured/JSON output:

- **Qwen instruct** — `qwen3:0.6b/1.7b/4b`, `qwen2.5:0.5b/1.5b/3b`
- **Phi instruct** — `phi3:3.8b`, `phi3.5`
- **Gemma instruct** — `gemma2:2b`
- **Llama small instruct** — `llama3.2:1b/3b`

TinyLlama excluded (historical baseline only). No new 7B+ considered.

## 4. Candidate Selection

Only one family was pursued because the user constrained downloads to **the Qwen
model** (and, after the qwen3 blocker, the Qwen fallback):

1. **qwen3:4b** (2.5 GB) — primary hope; Qwen3's strong JSON/instruction
   following and multilingual (FR) capability.
2. **qwen2.5:3b** (1.9 GB) — non-thinking Qwen chosen as the fallback when
   qwen3 proved transport-incompatible.

phi3 / gemma2 / llama3.2 / qwen3-1.7b were identified and documented but **not
downloaded** (download policy + user constraint), and were not required given
the family-wide numeric failure.

## 5. Model Sizes (verified Ollama tags)

| Tag | Params | Size (disk) | Quant | Resident (M1) | Notes |
|-----|-------:|------------:|-------|--------------:|-------|
| `qwen3:4b` | 4.02B | 2.5 GB | Q4_K_M | ~3.5 GB | "Qwen3 4B Thinking 2507", 256K ctx |
| `qwen2.5:3b` | 3.09B | 1.9 GB | Q4_K_M | ~2.2 GB | 32K ctx |
| `mistral:latest` (baseline) | 7.2B | 4.4 GB | Q4_K_M | ~5.1 GB | 100% GPU |

Both Qwen models fit comfortably (largest resident 3.5 GB < 16 GB).

## 6. Quick-Screen Results

Harness: `benchmark/llm_insights/quick_screen.py` — runs the production payload
builder, NecessityGate, prompt and `GroundingValidator` on 5 high-signal,
gate=True cases (`stress_n02` FR-anomaly, `anom_b02` EN-anomaly, `multi_f04`
FR-synthesis, `multi_f01` EN-multi-dim, `multi_f02` FR-empty-rec), temp 0.0.

**qwen2.5:3b (t=0.0):**

| Case | Lang | Result | Latency |
|------|------|--------|--------:|
| stress_n02 | fr | UNSUPPORTED_NUMERIC_CLAIM:16.67 | 29.1 s |
| **anom_b02** | en | **OK (grounded)** | 30.8 s |
| multi_f04 | fr | UNSUPPORTED_NUMERIC_CLAIM:2026 | 44.0 s |
| multi_f01 | en | UNSUPPORTED_NUMERIC_CLAIM:5,000,000 | 56.1 s |
| multi_f02 | fr | UNSUPPORTED_NUMERIC_CLAIM:14,000 | 47.3 s |

**Structural failure on the critical numeric-fidelity axis (4/5 = 80%
unsupported-numeric rate).** Only the simplest single-anomaly case passed.
Per STEP 7 §5 ("STOP evaluating early if it clearly fails structurally") and
§11 (numeric fidelity is critical), no full 46-case run was justified.

**qwen3:4b:** quick screen returned `LLM_UNAVAILABLE_OR_EMPTY` on every case —
the transport blocker (see §16) means the harness could never receive a
response. Raw probe showed grounding-correct prose in the `thinking` channel,
but that channel is not consumed by the pipeline, and the salvaged content
still contained an invented number (`700.0`).

## 7. Full Benchmark Results

**Not run.** Both Qwen candidates were disqualified at the quick-screen /
structural stage (qwen3: transport-incompatible; qwen2.5: critical numeric
failures). Running the full 46-set would only confirm the same failure mode and
is not justified. The existing baselines stand:
- Docker TinyLlama: 0/14 grounded.
- Native Mistral 7B: 0/14 grounded, unsupported-numeric 78.6%, p50 ≈ 86 s.

## 8. Grounding Metrics (per candidate, where measurable)

| Metric | qwen3:4b | qwen2.5:3b | Mistral 7B (base) |
|--------|----------|-----------|-------------------|
| VALID_JSON_RATE | n/a (never in `response`) | 100% (in `thinking`? no — in `response` yes) | 100% |
| GROUNDING_PASS_RATE | n/a | 20% (1/5) | 0% |
| UNSUPPORTED_NUMERIC_RATE | n/a* | **80%** | 78.6% |
| UNKNOWN_FACT_ID_RATE | n/a* | 0% | 0% |
| FORBIDDEN/CAUSAL_RATE | n/a* | 0% | 14.3% |
| RECOMMENDATION_GROUNDING_RATE | n/a | 20% (1/5) | 0% |

\* qwen3:4b could not be measured through the standard path (empty response);
the single salvaged case also failed numeric grounding.

## 9. Numeric Fidelity (critical)

**Both Qwen models fail.** Even at **temperature 0.0**, they invent numbers
absent from the verified `allowed_numbers` payload:

- qwen2.5:3b invented `16.67` (%), `2026` (a year), `5,000,000` / `14,000`
  (values), and a fabricated **standard deviation of 900,000** — none present in
  the facts (`allowed` for multi_f01 = `{0.55, 0.71, 1.0, 7.5, 200000, 500000,
  1500000}`).
- qwen3:4b introduced `700.0` on the same class of task.
- Mistral 7B: `5400`, `60000`, `500`, `1.57`, `27`, etc.

Small local models consistently **round/reformat/invent** numerics beyond the
verified normalization. This is disqualifying under the strict contract.

## 10. Fact-ID Fidelity

- **qwen2.5:3b:** 0% bad fact-IDs on the 5-case screen — when it produced
  output it cited only existing fact IDs (F1/C1/D1/A1/R1/R2 correctly). So
  fact-ID discipline alone is good.
- **qwen3:4b:** cited F1/A1 correctly in its salvaged output.
- **Mistral 7B:** ∈~0% unknown IDs but 14.3% causal overclaims.

Fact-ID fidelity is not the blocker; numeric fidelity is.

## 11. Structured Output

All candidates produced valid JSON (`VALID_JSON_RATE=100%` when a response was
present) that passed the strict Pydantic `LLMInsightOutput` schema. Schema
adherence is not the blocker for qwen2.5:3b. qwen3:4b's output was never
deliverable to the schema layer via the standard endpoint.

## 12. French Quality (manual — from grounded output only)

Only qwen2.5:3b produced any grounded (single) French-relevant output; its
French synthesis was grammatically reasonable but the model could not complete
a grounded multilingual case. Because the grounding gate rejects most FR
output, French quality is effectively unreachable.

Scale 0(poor)–3(business-grade):
- **qwen3:4b**: n/a (no deliverable through pipeline).
- **qwen2.5:3b**: FR acceptable in isolation (1) but unusable because gated out.

## 13. English Quality

- **qwen2.5:3b** passed the single EN anomaly case with business-readable,
  concise prose (grammar good, banking terms fine, no hallucinated business
  conclusion). English quality ≈ **2 (good)**, but this is one case and it
  cannot be trusted to stay numeric-accurate.

## 14. Latency

Measured (wall, /api/generate, Metal):

| Model | Quick-screen per-case (wall) | tok/s |
|-------|------------------------------|------:|
| qwen2.5:3b | 29–56 s (p50 ≈ 44 s) | ~6–8 |
| qwen3:4b | ~43 s full-budget (thinking) | ~6 |
| Mistral 7B (base) | p50 86 s, p95 119 s | ~4–6 |

Even the fastest candidate (qwen2.5:3b, ~6–8 tok/s) is **far above** the
p50 ≤ 10–15 s acceptance target. Config: temperature 0.0, max_tokens 512,
timeout 180.

## 15. Resource Usage

| Model | Resident | Metal | Notes |
|-------|---------:|-------|-------|
| qwen3:4b | 3.5 GB | 100% GPU | loads instantly after warm, no OOM |
| qwen2.5:3b | 2.2 GB | 100% GPU | very comfortable on 16 GB |
| Mistral 7B | 5.1 GB | 100% GPU | baseline |

No candidate created memory pressure or destabilized the Docker stack. Resource
fit is fine; correctness is the blocker.

## 16. Prompt/Token/Transport Behavior

- Temperature 0.0 used throughout (spec §14). Raising to 0.1 would only
  increase non-determinism and is not justified for a factual task.
- max_tokens 512 was reached only by qwen3 (thinking preamble). qwen2.5:3b
  completed within budget.
- **Transport blocker (qwen3):** on Ollama 0.21.1 and, after upgrading, 0.33.0,
  qwen3:4b ("Qwen3 4B Thinking 2507") returns its output only in the `thinking`
  channel; `response`/`content` stay empty on `/api/generate` and `/api/chat`,
  with and without `thinking:false` / `format:json`. The production pipeline
  reads `response`, so it receives an empty answer and always falls back to
  `LLM_UNAVAILABLE_OR_EMPTY`. The request-level `thinking:false` toggle is not
  honored by Ollama for this model. When the `thinking` content is salvaged and
  validated, it still fails numeric grounding (invents `700.0`). qwen3:4b is
  therefore **not pipeline-compatible** on this toolchain.

## 17. Model Decision Matrix

| Model | Size | JSON | Schema | Grounding | Numeric failures | FR | EN | p50 | Memory | Useful rate | Verdict |
|-------|-----:|:----:|:------:|:---------:|------------------|:--:|:--:|-----:|-------:|------------:|---------|
| qwen2.5:3b | 3B | ✓ | ✓ | 20% | **high (invents)** | 1 | 2 | ~44s | 2.2GB | 20% | NOT_SUITABLE |
| qwen3:4b | 4B | n/a | n/a | 0%* | high* | n/a | n/a | n/a | 3.5GB | 0% | NOT_SUITABLE |
| Mistral 7B (base) | 7B | ✓ | ✓ | 0% | high | 1 | 1 | 86s | 5.1GB | 0% | NOT_SUITABLE |
| TinyLlama (base) | 637M | ✗ | ✗ | 0% | high | 0 | 0 | 146s | small | 0% | NOT_SUITABLE |

\* qwen3 could not be benchmarked through the standard path (empty response);
its salvaged output failed numeric grounding.

## 18. Baseline Comparison

| Metric | Docker TinyLlama | Native Mistral 7B | qwen3:4b | qwen2.5:3b |
|--------|:----------------:|:-----------------:|:--------:|:----------:|
| Grounded / attempts | 0/14 | 0/14 | 0* | 1/5 |
| Grounding pass % | 0% | 0% | 0%* | 20% |
| Unsupported-numeric % | high | 78.6% | high* | 80% |
| Valid JSON % | poor | 100% | n/a | 100% |
| p50 latency | 146 s | 86 s | n/a | ~44 s |

qwen2.5:3b is the **fastest and most instruction-clean** of the four, but it
still fails the grounding gate on 80% of cases because of numeric invention —
i.e. it is strictly faster than Mistral but **not** groundedly better.

## 19. Recommended Model

**None.** No candidate satisfies the strict contract. If a Qwen model were ever
to be reconsidered, qwen2.5:3b is the only one that is pipeline-functionally
correct (works on `/api/generate`), but it is disqualified on numeric fidelity.

## 20. Recommended Settings

If (hypothetically) one accepted the numeric risk, sensible settings would be:
temperature **0.0**, token budget **512**, timeout **180 s**, model
`qwen2.5:3b`. These are **not** recommended for enablement.

## 21. Recommended Query Classes

qwen2.5:3b's only grounded pass was the **English single-anomaly interpretation**
(`anom_b02`). There is **no** reliable query class for any local model tested;
LLM grounding is not trustworthy for multi-dimensional synthesis, comparison,
or empty-recommendation cases.

## 22. Enablement Recommendation

**DO NOT enable.** `ENABLE_LLM_INSIGHTS` remains `false`. No STEP 8 enablement
is justified. The deterministic analytical facts + NecessityGate +
deterministic formatter + GroundingValidator remain the production path.

## 23. Remaining Risks

- Any future model must clear the numeric-fidelity gate on the full 46-set
  (≥90% grounding, ≤2% unsupported-numeric) before enablement.
- The qwen3/Ollama transport bug confirms that "model family" alone is not a
  proxy for pipeline compatibility — always validate `/api/generate` response
  routing before benchmarking.
- Numeric hallucination persists at temperature 0.0, so temperature tuning does
  not rescue grounding.
- GroundingValidator continues to defend the pipeline (rejects 100% of bad
  numeric claims), so the risk of ungrounded output surfacing is nil.

## 24. Final Verdict

**NO MODEL QUALIFIES.** Local compact LLMs (Qwen3 4B, Qwen2.5 3B, and the
Mistral 7B / TinyLlama baselines) do not meet the strict grounded-analytics
contract on this Apple M1 16 GB: they consistently invent numbers the
deterministic validator (correctly) rejects. The deterministic Insights layer
is the correct production answer. Keep `ENABLE_LLM_INSIGHTS=false`.

---

### Artifacts
- `benchmark/llm_insights/quick_screen.py` — 5-case quick-screen harness.
- `benchmark/llm_insights/raw_probe.py` — raw-response diagnostic.
- `benchmark/llm_insights/results/native_qwen25_3b_t0.0.json` — qwen2.5:3b screen.
- `benchmark/llm_insights/results/native_mistral_mistral_t0.1.json` — baseline.
