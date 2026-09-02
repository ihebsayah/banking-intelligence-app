# SYMBOLIC_LLM_GROUNDING_REPORT (STEP 8)

**Status: STOP & REPORT — quick screen failed (1/5 then 0/5; threshold ≥4/5)**

Experiment: replace the local-LLM grounding contract (STEP 4–7) with **symbolic grounding and deterministic value rendering**. The LLM writes NO numeric literals and only symbolic tokens (`{{F1}}`, `{{A1}}`, `{{C1}}`, `{{T1}}`, `{{R1}}`); a deterministic `FactRenderer` injects verified values after generation. Model under test: `qwen2.5:3b` via Ollama `http://localhost:11434`, `temperature=0.0`, `num_predict=384`.

---

## A. Numeric-literal eradication — Implemented (new symbolic layer)

- `services/insights_agent/symbolic_renderer.py` (new): `build_symbolic_facts`, `FactRegistry`, `SymbolicPayloadBuilder`, `SymbolicValidator`, `FactRenderer`, `render_result`.
- LLM-facing payload exposes **only** tokens plus qualitative metadata (`relationship`, `direction`, `magnitude_class`, `severity`). Verified across **all 46 offline cases**: 0 numeric literals remain after token-strip in any payload field.
- `_sanitize_label()` strips bare and parenthetical numbers (`(62%)`, `20.0%`) from recommendation labels while preserving natural language.
- Anomaly meanings no longer expose sigma values; temporal meanings no longer expose period literals (`2026-05`).

## B. Zero numeric literal rate — 100% (both attempts)

`ZERO_NUMERIC_VIOLATION_RATE = 0.0` in attempt 1 and attempt 2. The model never wrote a numeric literal under the symbolic contract.

## C. Raw zero-numeric-violation measurement — cleaner than STEP 7

STEP 7 raw contract failures: 4/5 `UNSUPPORTED_NUMERIC_CLAIM`. STEP 8 attempts: **0/5 numeric violations in both attempts**. All failures moved out of the numeric-literal dimension into schema/token-consistency dimensions (E below), proving the token-obfuscation itself works.

## D. Deterministic value rendering — Implemented + unit-tested

`FactRenderer.render` replaces allowlisted `{{ID}}` tokens with verified values post-generation; any unresolved token → `RENDER_FAILURE` and fallback.
- `{{F1}}` → `"18 250"`; `{{A1}}` → rendered currency; `{{C1}}` → `"+0.85"`; `{{R1}}` → the full deterministic candidate message.
- `RENDER_SUCCESS_RATE`: 20% attempt 1, 0% attempt 2 (all render-attempts gated behind successful validation).

## E. Renderer unit tests — 29 tests, all passing

`tests/test_symbolic_grounding.py`: 29 tests across `TestSymbolicRawValidator`, `TestSymbolicGrounding`, `TestRenderer` (spec asked for ≥20). Full regression: `tests/test_grounded_llm.py` + `tests/test_necessity_gate.py` + `tests/test_insights_agent.py` → **111 passed, 0 failed**. Legacy `_SYSTEM_PROMPT`, `_build_facts`, `GroundingValidator`, `_extract_json`, `DeterministicFormatter` untouched and intact.

## F. Registry invariant — Enforced (strict, unweakened)

`SymbolicValidator` enforces, with **set equality**, that for every item:
- `tokens_in_text == fact_ids` (no extra, no missing);
- recommendations reference only `R#`;
- zero numeric literals after token-strip;
- metadata bounds (severity, direction, magnitude classes); no `FORBIDDEN_CLAIM` / `CAUSALITY_CLAIM`.

Failing any check → deterministic fallback with the recorded reason. The validator was **not weakened** to accommodate the model.

## G. Obfuscation kept existing verifier — Yes

The old `_build_facts` / `_collect_allowed_numbers` / `VerifiedFactPayload` / `GroundingValidator` contract remains in `mistral_integrator.py` (`interpret_grounded`); the symbolic path is additive (`interpret_symbolic`). Both registered under the same `InterpretationResult` schema.

## H. No RAG — Confirmed

Single verified-facts payload per query; no retrieval step added. Prompt-injection guard from STEP 4 preserved (user question wrapped as data).

## I. GPU attention — N/A

Local CPU laptop (darwin, no CUDA). Ollama serves `qwen2.5:3b` at ~8.2 tok/s.

## J. Offline-first evaluation — Confirmed

All fixtures in `benchmark/llm_insights/cases.json` (46 cases) are offline `AnalyticalFactPackage`. `ENABLE_LLM_INSIGHTS=false` in production `Settings`; the suite touches no flags and no live data.

## K. OLLAMA mode / engine — Running

`ollama list` → `qwen2.5:3b`, `qwen3:4b`, `mistral:latest`. Tested with `qwen2.5:3b`. Engine works; the contract, not the engine, is the blocker.

## L. Local-LLM contract — Prior 4/5 fail → now 1/5 (attempt 1) / 0/5 (attempt 2)

| Metric (aggregate, n=5 LLM attempts) | STEP 7 (numeric contract) | STEP 8 attempt 1 | STEP 8 attempt 2 |
|---|---|---|---|
| SYMBOLIC_GROUNDING_PASS_RATE | (4/5 fail) 20% | **20%** | **0%** |
| ZERO_NUMERIC_VIOLATION_RATE | n/a | **0.0%** | **0.0%** |
| TOKEN_VALIDITY_RATE | n/a | **100%** | **100%** |
| FACT_ID_TOKEN_CONSISTENCY_RATE | n/a | 20% | 20% |
| UNRESOLVED_TOKEN_RATE | n/a | 0% | 0% |
| RENDER_SUCCESS_RATE | n/a | 20% | 0% |
| FORBIDDEN_CLAIM_RATE | n/a | 0% | 0% |
| CAUSALITY_CLAIM_RATE | n/a | 0% | 0% |

Improvement over STEP 7 on the numeric dimension is total (100% zero-numeric). But the model cannot reliably maintain the strict `fact_ids`↔token set-equality invariant narrative.

## M. Hard cap 1,200 tokens — Respected (measured)

`prompt_eval_count` per case: attempt 1 = 546–884; attempt 2 = 685–1,023. Under the 1,200 hard cap but **close** for the 8-fact case (`multi_f01`, 1,023 with the tightened prompt), which squeezes headroom for languages/examples.

## N. 20-test minimum — 29 tests written, all green

See E. Tests include: valid summary accepted; unknown token rejected; fact/token mismatch rejected; zero-numeric invariant; renderer substitution; deterministic fallback unchanged; non-causal correlation; statistical-only anomaly language; French/English rendering; recommendation-requires-R#.

## O. Quick screen — 5 high-signal cases, t=0.0 (results files in repo)

Attempt 1 (`symbolic_qwen25_symbolic_quick_t0.0.json`):

| Case | Result | Reason |
|---|---|---|
| stress_n02 (fr) | fallback | TOKEN_FACT_MISMATCH OBS0 missing F1 |
| anom_b02 (en) | fallback | TOKEN_FACT_MISMATCH OBS0 missing F1 |
| multi_f04 (fr) | fallback | TOKEN_FACT_MISMATCH OBS0 missing D1 |
| multi_f01 (en) | **PASS** | OK |
| multi_f02 (fr) | fallback | TOKEN_FACT_MISMATCH OBS0 extra A1 / missing D1,T1 |

Attempt 2 — tightened prompt, one allowed attempt (`symbolic_v2_qwen25_symbolic_quick_t0.0.json`):

| Case | Result | Reason |
|---|---|---|
| stress_n02 (fr) | fallback | SCHEMA_VIOLATION (limitations as string) |
| anom_b02 (en) | fallback | TOKEN_FACT_MISMATCH REC0 missing R1 |
| multi_f04 (fr) | fallback | TOKEN_FACT_MISMATCH OBS0 missing C1,D1 |
| multi_f01 (en) | fallback | TOKEN_FACT_MISMATCH REC0 missing R1 |
| multi_f02 (fr) | fallback | TOKEN_FACT_MISMATCH REC0 missing A1 → R1 |

Gate: **2 required attempts both < 4/5 → STOP; do NOT run the full 46-case benchmark.**

## P. Attempt 2 report — Prompt tightening, then sign reversal

Tightened `_SYMBOLIC_SYSTEM_PROMPT` in `mistral_integrator.py` (explicit bidirectional rule: tokens in text == fact_ids; added a valid/invalid example; banned spelling out categorical values; recommendations must be R# only).

Observed behavior change:
- **Improvement**: observations now embed tokens far more often (anom_b02, multi_f01 cases).
- **Regression**: recommendations broke — the model wrote prose that cites the anomaly token (`{{A1}}`) inside the recommendation text while declaring `fact_ids=["R1"]`, and one case lapsed into `SCHEMA_VIOLATION` (limitations as a string).
- Net: **0/5**, sign reversed vs attempt 1. This is the tri-modal STOP trigger: neither passing nor improving; the second attempt flipped negative.

## Q. No-weakening statement — Explicit promise kept

The symbolic validator's strict set-equality invariant, zero-numeric check, R#-only recommendations, and provenance-bound metadata checks were **not relaxed** at any point to improve a pass rate. The benchmark was run against the same production validator the renderer uses. Test expectations encode the strict contract.

## R. Latency (t=0.0, qwen2.5:3b, CPU) — Over budget

| | min | p50 | p90 | max | tok/s |
|---|---|---|---|---|---|
| Attempt 1 | 19.4s | 29.5s | 45.4s | 53.3s | 8.2 |
| Attempt 2 | 21.7s | 25.1s | 34.2s | 34.6s | 8.1 |

p50 ≈ 25–30 s vs the 30 s production timeout target. Even a passing contract would sit at the edge of the time budget on this hardware.

## S. Prompt size / observation counts — Bounded

`max 3 summary sentences, max 4 observations, max 3 recommendations, max 3 limitations` per the symbolic system prompt; renderer and validator enforce the same caps. Payload facts per quick-screen case: 2–8.

## T. Report path

This file: `SYMBOLIC_LLM_GROUNDING_REPORT.md` (repo root). Results:
`benchmark/llm_insights/results/symbolic_qwen25_symbolic_quick_t0.0.json`,
`benchmark/llm_insights/results/symbolic_v2_qwen25_symbolic_quick_t0.0.json`.

## U. Final verdict — STOP

The STEP 8 symbolic layer (code, tests, validator, renderer) is complete and green in isolation (29/29 unit tests, 111/111 regression). The **live quick screen fails**: 1/5 then 0/5, threshold ≥4/5, with the second attempt sign-reversed. Per the experiment's decision rule: **STOP; do not deploy; do not run the full benchmark; report the measured gap.**

## V. What would be required to continue (unblocked next iteration)

1. A model that reliably maintains bidirectional token↔fact_id set-equality over multi-fact narratives (attempt with `qwen3:4b` or a larger local model; 8.2 tok/s CPU is the binding constraint).
2. Recommendation candidates that resolve **deterministically** — the model should emit text exactly `{{R1}}` for candidates; teach this explicitly, or relax R-text to require the R token only when the candidate exists (without weakening A/O observation invariants).
3. Latency: a smaller/quantized model or GPU to bring p50 under ~10 s end-to-end.
4. Re-run the quick screen; only if ≥4/5 do we proceed to the full 46-case benchmark.

## W. Sign-flip / tri-modal evaluation

| Modal criterion | Outcome |
|---|---|
| Attempt 1 passes ≥4/5 | ❌ 1/5 |
| Attempt 2 (tighten) passes ≥4/5 | ❌ 0/5 |
| Attempt 2 improves over attempt 1 | ❌ sign reversed |
| Would weakening the contract be acceptable | ❌ never (Q) |

## X. Recommendations & next steps

- **Adopt the symbolic layer as infrastructure**: zero-numeric obfuscation works; keep `ENABLE_LLM_INSIGHTS=false`; the deterministic `FactRenderer` is a strict, testable value-injection seam worth keeping for any future LLM tier.
- **Do not weaken STEP 8 strictness** to hit a number; the invariant is the point.
- **Try `qwen3:4b`** on the same harness: one quick-screen run (~2.5 min) is cheap and decides the model question empirically.
- **Optional**: a structured decoder path where the model emits only ordered fact_ids (no free-text tokens), letting a template renderer assemble the narration — stricter and likely more CPU-robust than free-text token weaving.

— STEP 8 symbolic grounding experiment, `qwen2.5:3b`, CPU laptop, t=0.0.