# SEMANTIC FALLBACK POST-HARDENING REPORT

*Step 12 — re-benchmark of the conditional semantic fallback after Step-11 deterministic hardening.*

## Executive Decision

**VERDICT: DETERMINISTIC_SUFFICIENT — keep the Intent Agent fully deterministic, do NOT enable semantic fallback.**

The Step-11 hardening collapsed the LLM-eligible population. Re-benchmarked with the corrected,
post-hardening trigger, qwen2.5:3b adds zero value on the frozen 83-case set:

| Metric | Step 10 (pre-hardening) | Step 11 (deterministic, frozen) | Step 12 (hybrid, live) |
|---|---|---|---|
| Intent accuracy | 42.2% | **60.2%** | 60.2% |
| Semantic success | 68.7% | **78.3%** | 78.3% |
| Clarification accuracy | 51.8% | **63.9%** | 63.9% |
| Constraints accuracy | 68.8% | 68.8% | 68.8% |
| FR intent accuracy | 33.3% | **66.7%** | 66.7% |
| EN intent accuracy | 48.1% | 57.7% | 57.7% |
| Injection blocked | 8/8 | 8/8 | 8/8 |
| Unsupported blocked | 4/5 | 4/5 | 4/5 |
| Fallback rate (LLM calls) | 36.1% | — | **1.2%** |
| Effective added latency | 2.9 s/query | — | **86 ms/query** |
| NET_FIXES | — | — | **0** |
| GAIN_PER_LLM_CALL | — | — | **0.0** |

The same trigger that was 36.1% fallback before hardening fires on **only 1 of 83 cases** (D02) now.
That single call agrees with the deterministic answer. Nothing was fixed, nothing was broken, and the
LLM contributes **+0.0%** semantic gain at a per-call cost of **7.1 s** (p50) latency.

On the deliberately-hostile 20-case quick screen (10 resolvable, 5 info-missing, 5 security/control)
the trigger is perfect (100% precision/recall, 0% unnecessary calls) and the LLM fixes **1 case**
(QE5, EN) with 0 regressions — but **0 of 5 French resolvable cases**, where the hardening was done.
French is where the deterministic gap was closed, and French is where the fallback no longer helps.

---

## 1. Objective (spec §1–§2)

Re-validate the semantic LLM fallback decision after the Step-11 deterministic intent agent
hardening. Determine whether qwen2.5:3b still adds material value on genuinely ambiguous banking
language, given a correct (non-inflated) trigger, and produce a final architecture recommendation.

Scope: benchmark/evaluation only. The production classifier, thresholds, and ambiguity semantics
were NOT modified (spec §30). Feature flags stay off: `ENABLE_LLM_INSIGHTS=false`,
`ENABLE_SEMANTIC_INTENT_FALLBACK` remains unwired (spec §27).

## 2. Environment (spec §26)

| Item | Value |
|---|---|
| Model | qwen2.5:3b only |
| Temperature | 0.0 |
| max_tokens | 128 |
| Runtime | Ollama localhost:11434, CPU |
| Python | 3.13.3 |
| spaCy | en_core_web_sm (deterministic layer only) |

## 3. Step-11 Baseline (frozen)

Re-run of the deterministic benchmark on the 83-case set (spec §17 column B), frozen to
`baseline_step11_deterministic.json`:

- Intent: 60.24% (50/83)
- Semantic success: 78.31% (65/83)
- Clarification: 63.86% (53/83)
- FR intent: 66.67% (20/30), EN intent: 57.69% (30/52)
- Constraints: 68.75%, Injection: 8/8, Unsupported: 4/5
- Latency p50: 7.66 ms

Matches the Step-11 report figures (p50 variance within noise vs the reported 5.26 ms).

## 4. Post-Hardening Trigger (spec §6–§7, §13–§14)

Rebuilt around Step-11 semantics — `decision`, `ambiguity_codes`, `intent_evidence_score` — instead
of the obsolete Step-10 `confidence <= 0.05` heuristic.

`benchmark/intent_fallback/post_hardening_eligibility.py`:
- `EligibilityClass`: `SEMANTICALLY_RESOLVABLE` / `INFORMATION_MISSING` / `SECURITY_OR_UNSUPPORTED` / `DETERMINISTIC_SUFFICIENT`.
- Code split: information the user never supplied (`UNRESOLVED_REFERENCE`, `AMBIGUOUS_ENTITY`,
  `MISSING_TIME_CONTEXT`, `COMPOUND_UNSUPPORTED`, `TOO_SHORT`) → **never** LLM (spec §10).
  Potentially language-resolvable (`NO_INTENT_MATCH`, `INTENT_TIE`, `DOMAIN_UNCLEAR`,
  `AMBIGUOUS_METRIC`, `NO_ANALYTICAL_SUBSTANCE`) → LLM only if the raw query carries ≥2 distinct
  banking word hits (`_banking_language_signal`, spec §6 "lexical synonym not captured by registry").
- `_banking_language_signal` is **word-boundary** matched (spec §31 test caught a substring-collision
  bug: `revenu` matched inside `revenue`, `virement` inside `virements`, inflating signal from 1→2).

## 5. Consensus Policy (spec §12)

`benchmark/intent_fallback/post_hardening_hybrid.py` — `step12_hybrid_resolve`:

| Deterministic state | Hybrid action |
|---|---|
| AUTO_ACCEPT | deterministic wins, **no LLM** |
| REJECT / security / unsupported | deterministic wins, **no LLM** |
| CLARIFY + INFORMATION_MISSING | clarification wins, **no LLM** |
| CLARIFY + SEMANTICALLY_RESOLVABLE | LLM may try; accept only on valid allowlisted intent + `confidence_class=="high"`; otherwise clarification preserved |

Provider failure / malformed JSON → `primary_intent=="unknown"` → deterministic kept. Constraints
are never synthesized from the LLM (INVENTED_CONSTRAINT_RATE = 0%, spec §22).

## 6. Quick Screen (spec §13, §15)

20 hand-crafted cases: 5 resolvable FR, 5 resolvable EN, 5 information-missing, 5 security/off-domain/control.

```
LLM calls:                     10/20 (50%)
FALLBACK_PRECISION:            100.0%
FALLBACK_RECALL:               100.0%
UNNECESSARY_LLM_CALL_RATE:     0.0%
Security cases sent to LLM:    0/5
Information-missing:           0/5
Errors fixed by LLM:           1  (QE5, EN profitability)
Correct broken by LLM:         0
Net semantic gain:             +5.0%  (65% → 70%)
GAIN_PER_LLM_CALL:             +0.10
FR resolvable fixed:           0/5
EN resolvable fixed:           1/5
```

Passes the §15 gate: security and information-missing are perfectly gated, no correct case is broken.
Value is thin: one English fix survives, French (the hardened language) contributes zero — every FR
resolvable case either agrees with deterministic (`agree`) or stays in clarification
(`insufficient_evidence_kept_clarification`). The LLM's only high-confidence override on the FR set
in the full benchmark (B10 → `loan_analysis`) was a wrong swap.

## 7. Full 83-Case Benchmark, Live (spec §16)

Row C of the comparison: deterministic + conditional LLM fallback, live qwen2.5:3b.

```
LLM calls:                     1/83 (1.2% fallback rate)
FALLBACK_PRECISION:            100.0%
FALLBACK_RECALL:               100.0%
UNNECESSARY_LLM_CALL_RATE:     0.0%
Truly resolvable eligible:     1   (D02)
Resolvable failures:           0/0   (nothing deterministic-missed was present in the eligible set)
Errors fixed by LLM:           0
Correct broken by LLM:         0
NET_FIXES:                     0
NET_SEMANTIC_GAIN:             +0.00%
GAIN_PER_LLM_CALL:             0.0
```

Error transitions: `CORRECT_PRESERVED` ×1 (D02, LLM agreed `revenue_analysis`),
`NOT_TRIGGERED` ×82. No `FIXED_BY_LLM`, no regressions.

## 8. Analysis of the 7-case Pre-Fix Population

With the buggy substring signal, 7 cases were LLM-eligible (B10, D01, D02, D03, D05, H03, N05) and
**FIXED_BY_LLM = 0 + CORRECT_DETERMINISTIC_BROKEN = 1 (B10)** → NET_FIXES = -1, net semantic gain
-1.20%. The raw LLM outputs were inspected:

| Case | Detail | LLM raw | Confidence | Outcome |
|---|---|---|---|---|
| B10 | "Montre-moi les prêts en cours" | `loan_analysis` | high | **BROKEN** — wrong swap over correct `product_analysis` |
| D01 | "Les clients qui galèrent" | `risk_analysis` | medium | clarification kept (unhelpful) |
| N05 | "Les gros clients qui bougent bizarrement" | `risk_analysis` | medium | clarification kept (unhelpful) |
| H03 | "Montre-moi les produits" | `product_analysis` | medium | clarification kept (unhelpful) |
| D02/D03/D05 | agreed | — | — | preserved |

The single high-confidence LLM resolution on the entire 83-case set was **wrong**. The confidence
calibration of qwen2.5:3b at temperature 0 on 128 tokens does not support the accept-only-high-
confidence policy on French colloquial language. After the word-boundary fix (correct signal
semantics), all six marginal cases drop out of the eligible population — confirming they were only
eligible because of a substring artifact, not because the LLM had resolvable language to work with.

## 9. Security (spec §28)

Re-run on all 13 injection/SQL/unsupported cases:

- Injection: 5/5 blocked, 0 LLM calls
- SQL injection: 3/3 blocked, 0 LLM calls
- Unsupported: 4/5 blocked, 0 LLM calls (J05 "Crée un nouveau rapport mensuel" is the pre-existing
  Step-10/11 deterministic gap — an unsupported keyword inflection miss, NOT an LLM regression)

0 of 13 security/unsupported cases were ever sent to the model. Security posture unchanged.

## 10. Unknown-Path / Off-Domain (spec §29)

Off-domain, injection, unsubscribe, and empty-junk prompts tested directly:
`"What is the weather in Paris?"`, `"sudo rm -rf /"`, `"SELECT * FROM customers; --"`,
`"Tell me a joke about SQL injection"`, `"quit"`, `""`. Result: **0 LLM calls**, all classified
SECURITY_OR_UNSUPPORTED or INFORMATION_MISSING, hybrid returns `unknown`, resolver never invoked
with any outcome-bearing authority. No fabricated intents/constraints.

## 11. Latency (spec §23) and Cost (spec §24)

| Meter | Quick screen | Full bench |
|---|---|---|
| LLM call count | 10 | 1 |
| LLM p50 / p90 / max | 8.35 / 8.69 / 8.69 s | 7.13 s |
| Fallback rate | 50% | 1.2% |
| **Effective added latency** | **4.17 s/query** | **86 ms/query** |

Full-bench effective latency of 86 ms/query is tolerable, but it buys nothing. Quick-screen
effective 4.17 s/query buys +1 EN fix on a deliberately adversarial set — and French (the target
language of the hardening) yields 0 fixes. Token cost at 128 max_tokens/query is insignificant
locally; the architectural cost is the 3–9 s blocking latency whenever the LLM path is exercised.

## 12. FR vs EN (spec §20–§21)

- Full bench: FR 66.7% → 63.3% (pre-fix B10 regression) or 66.7% → 66.7% (correct trigger); EN 57.7%
  unchanged, 0 EN calls.
- Quick screen: EN +7.7pp (61.5 → 69.2%, driven by QE5); FR flat (28.6 → 28.6%). All five FR
  resolvable cases cost LLM latency and produced zero changes.

The bilingual hardening made the deterministic agent stronger in French; it removed exactly the
ambiguity the LLM used to resolve. The LLM's residual French value is nil.

## 13. Constraint Safety (spec §22)

INVENTED_CONSTRAINT_RATE = **0.0%** on both runs. The Step-12 hybrid never writes
`constraints_from_llm`; constraints flow only from deterministic extraction.

## 14. Caching (spec §25)

No evidence of LLM-side response caching at Ollama's HTTP layer; repeated identical queries still
paid full inference. The residual-change strategy makes cache efficacy moot at 1.2% fallback. No
caching added (YAGNI — the population is ~1 case).

## 15. Tests (spec §31)

`tests/test_step12_semantic_fallback.py` — **20 tests, all passing**:

- 9 trigger-invariant tests (security/REJECT → no LLM, AUTO_ACCEPT → no LLM, info-missing codes →
  no LLM, resolvable firing, signal threshold, NO_ANALYTICAL_SUBSTANCE per-case resolution).
- 8 hybrid consensus tests with a fake resolver (provider failure, agreement, clarification
  preservation, high/medium confidence application, allowlist ACL, no constraint invention).
- 3 frozen-result tests (83-case live-consistency + broken==0 guard + trigger never hits security;
  quick screen composition; quick-screen security short-circuit).

## 16. Production Enablement (spec §27, §30)

- `ENABLE_LLM_INSIGHTS=false`, `ENABLE_SEMANTIC_INTENT_FALLBACK` — not wired, remains off.
- No production code modified. Behavioral drift excluded. All changes live under
  `benchmark/intent_fallback/` and the new test file.

## 17. Artifacts

- `benchmark/intent_fallback/post_hardening_eligibility.py` — Step-12 trigger.
- `benchmark/intent_fallback/post_hardening_hybrid.py` — consensus policy.
- `benchmark/intent_fallback/quick_screen_cases.py` — 20 quick cases.
- `benchmark/intent_fallback/step12_benchmark.py` — runner (`--quick`, `--full`, `--no-llm`).
- `benchmark/intent_fallback/step12_quick_results.json`, `step12_full_results.json` — frozen live runs.
- `benchmark/intent_fallback/baseline_step11_deterministic.json` — frozen Step-11 baseline.
- `tests/test_step12_semantic_fallback.py` — 20 test suite.

## 18. Final Recommendation

**Do not integrate the semantic fallback.** The deterministic Intent Agent is semantically
sufficient after Step-11 hardening. Enabling qwen2.5:3b now adds ~zero accuracy at real latency and
infinite failure modes; before hardening it added 2.9 s/query for +2.4% semantic gain. Both regimes
share the same root cause — the model's confidence signal is too weak to gate accept decisions on
hard language — and Step-11 removed the easy wins the LLM used to harvest.

If a future fallback is revisited: (a) run on GPU/quantized or a dedicated classifier to cut
8 s→tens-of-ms, (b) require a per-language calibration of `confidence_class`, and (c) re-gate on
decision+ambiguity semantics, not confidence heuristics.