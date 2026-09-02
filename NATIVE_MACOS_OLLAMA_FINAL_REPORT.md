# NATIVE MACOS OLLAMA — FINAL A–Z REPORT

Date: 2026-09-01
Owner: AI Engineer (multi-agent / LLM pipeline optimization)
Scope: Move Ollama from Docker to native macOS Apple Silicon; verify whether
native Metal inference changes the usability of Mistral 7B; deliver a decision.

---

## 1. Task

Move Ollama from the Docker runtime to native macOS and connect the Dockerized
Banking Intelligence services to it via `host.docker.internal:11434`. Verify
whether native Apple Silicon (Metal) inference makes Mistral 7B usable, and
produce:

- a documented final recommendation (Decision A/B/C/D), and
- a full A–Z report.

**Hard safety constraint:** `ENABLE_LLM_INSIGHTS=false` throughout. The
deterministic-LLM pipeline must keep working. At no point may Mistral generate
or execute SQL, touch databases, or weaken deterministic / grounding /
necessity-gate components.

---

## 2. Exec Summary

Moving Ollama to native macOS was a **runtime success** but a **usability
failure on this model/hardware**.

- Native Apple Silicon **Metal** works: `mistral:latest` (7.2B, Q4_K_M) loads
  and runs at **100% GPU** — a definitive fix for the prior Docker OOM (the
  whole reason STEP 5 was abandoned).
- Docker→host bridge works: containers reach `host.docker.internal:11434`.
- **But** on the full 46-case grounded benchmark, native Mistral produced
  **0/14 grounded responses (0% pass)** — rejected every time by the
  deterministic `GroundingValidator`, dominated by numeric hallucination
  (78.6%) and causal claims (14.3%). Latency p50 ≈86s, p95 ≈119s, and behavior
  is non-deterministic (a clean grounded pass one run, rejection the next).
- The deterministic path is untouched and remains the production default.

**Recommendation: Decision C** (keep the LLM integration wired + documented,
but keep it **disabled**). Optionally pursue **Decision D** later with a
smaller/higher-quality model. Do not enable Mistral 7B on M1.

---

## 3. Environment (confirmed)

- macOS 26.0.1, arm64 (Apple M1), 8 CPUs, 16 GB unified memory.
- Native Ollama: `/opt/homebrew/bin/ollama`, brew **0.21.1**
  (Docker image client was 0.17.7).
- Native models: `mistral:latest` (7.2B, Q4_K_M, 4.4 GB), `tinyllama:latest`.
- Prior Docker installed Ollama store is separate from the native store.

---

## 4. Previous state (why this existed)

STEP 5 (Docker) baseline concluded the local LLM was unusable:
- Dockerized Mistral 7B OOM-killed on load under the running cluster.
- TinyLlama: **0/14 grounded**, malformed JSON mostly, p50 146s / max 275s.

That conclusion conflated "model unusable" with "runtime starved inside the
Docker Linux VM" — which this native experiment disproved on the runtime side.

---

## 5. What was done (A–Z)

| Step | Action | Result |
|------|--------|--------|
| 1 | Inspect env, record baseline | Facts in §3; old metrics in §4 |
| 2 | Stop dockerized `banking_ollama` (preserved) | port 11434 freed |
| 3 | Start native Ollama `OLLAMA_HOST=0.0.0.0:11434` | listening `*:11434`, PID recorded, log `/tmp/native_ollama.log` |
| 4 | Verify Docker→host | `host.docker.internal:11434/api/tags`→`mistral` from orchestrator & insights |
| 5 | Direct native Mistral probe | cold ≈8.9s, warm ≈3.4s latency |
| 6 | Confirm Metal | `ollama ps`=100% GPU; runner `library=Metal ... Apple M1 11.8GiB` |
| 7 | Config: host endpoint + single model source | `services/insights_agent/config.py`, `services/shared/config.py`, compose, `.env*` |
| 8 | Docker Ollama optional | `profiles:["docker-llm"]`, `depends_on: ollama` removed |
| 9 | Health + lazy init | `/health` LLM-aware; `insights_generator` short-circuits when flag off |
| 10 | Fix pre-existing pydantic bug | `Trend` moved above `InsightsResponse` (container was broken on pydantic 2.5) |
| 11 | Rebuild/restart | insights-agent recreated, now **healthy** |
| 12 | Deterministic verification | `generation_mode:deterministic`, 2 anomalies, no LLM call |
| 13 | Isolated grounded tests | single case passed (≈53s) but non-repeating |
| 14 | Small validation set (5 cases) | 2 gated → fallback (numeric/fact-id) |
| 15 | Full benchmark (46 cases) | **0/14 grounded**, see §8 |
| 16 | Security review | native Ollama LAN-exposed (dev tradeoff) |
| 17 | Tests | 88 relevant pass (see §9) |
| 18 | Docs + helper | this report, `NATIVE_MACOS_OLLAMA_INTEGRATION.md`, `scripts/ollama-native.sh` |

---

## 6. Grounding contract (why LLM output was rejected)

`GroundingValidator` accepts a response only if every claim/recommendation
references an **existing fact ID** and every number is in the **verified
allowed set** built from the deterministic analytical facts. This is the
deterministic safety gate — it never lets ungrounded content through.

---

## 7. Files changed (this task)

- `docker-compose.yml` — host endpoint defaults; `INSIGHTS_LLM_*` env;
  `depends_on: ollama` removed; `ollama` service → `profiles:["docker-llm"]`.
- `services/insights_agent/config.py` — `MISTRAL_API_URL` host default;
  `INSIGHTS_LLM_MODEL` precedence.
- `services/insights_agent/main.py` — LLM-aware `/health`.
- `services/insights_agent/models.py` — `Trend` ordering fix (pydantic 2.5).
- `services/shared/config.py` — host default endpoint.
- `.env` / `.env.example` — flags + host URL.
- `scripts/ollama-native.sh` (new) — dev verification helper.
- `NATIVE_MACOS_OLLAMA_INTEGRATION.md` (new) — full integration doc.
- This report.

_(Note: the working tree also contains unrelated pre-existing changes to
frontend/workbench/schema modules from other in-progress work; none are part of
this task and none were relied upon.)_

---

## 8. Benchmark results (native Mistral, temp 0.1, timeout 180s)

46 cases (14 LLM-useful, 32 negative controls). Source:
`benchmark/llm_insights/results/native_mistral_mistral_t0.1.json`.

| Metric | Native Mistral M1 | Docker TinyLlama (STEP5) |
|--------|------------------:|--------------------------:|
| Grounded LLM responses | **0** / 14 | 0 / 14 |
| Grounding pass rate | **0.0%** | 0% |
| Unsupported-numeric rate | 78.6% | high |
| Forbidden-causal rate | 14.3% | high |
| Valid JSON rate | 100% | poor |
| Latency p50 | ≈86 s | ≈146 s |
| Latency p95 | ≈119 s | ≈246 s |
| Timeouts / transport failures | 0 | n/a |

Failure samples: `UNSUPPORTED_NUMERIC_CLAIM:5400`, `:500`, `:60,000.`,
`:14,000.`, `:27`, `:1.57`, `OBSERVATION_NO_FACT`, `CAUSALITY_CLAIM` ×2.

## 9. Test results

- `tests/test_grounded_llm.py`, `test_necessity_gate.py`,
  `test_insights_agent.py`, `test_llm_runtime_config.py` → **88 passed**.
- Full suite shows pre-existing failures/errors in unrelated modules
  (schema_agent, user_management, etc.) that also **contaminate shared
  interpreter state** — they are not regressions here; my scope files pass
  88/88 both isolated and together.

## 10. Security notes

- Native Ollama bound to `0.0.0.0:11434` is reachable on the LAN and has **no
  auth**. This is a dev-only tradeoff required for `host.docker.internal`
  access. Restrict external exposure (macOS firewall / host-only bind) outside
  dev. Documented in `NATIVE_MACOS_OLLAMA_INTEGRATION.md` §3 / Results-Decision.

## 11. Decisions considered

- **A — Just keep Docker Ollama:** rejected — Docker Mistral OOMs; TinyLlama
  ungrounded and too slow. Already proven insufficient.
- **B — Enable native Mistral as production LLM:** rejected — 0% grounding
  pass, ~86s p50, non-repeating. Unsafe/useless under the strict Gate.
- **C — Keep native Ollama integration wired + documented, flag OFF
  (deterministic default):** **SELECTED.**
- **D — Later, find a smaller/higher-quality grounded model** (e.g. a
  fine-tuned 3B/instruction model, or raise quant/context, or improve prompt to
  force allowed-numbers adherence): recommended follow-up, gated on a real
  grounding pass rate. Not attempted now — every available model already failed
  and this hardware is capacity-limited.

## 12. Final recommendation

**Adopt Decision C:** keep the native macOS Ollama wiring and the full LLM
integration layer (health, flags, lazy init, single-model source, grounding
gate, fallback) — all documented and test-covered — but **leave
`ENABLE_LLM_INSIGHTS=false`. The deterministic analytical facts + NecessityGate
+ deterministic formatter + GroundingValidator remain the production path** and
are fully verified.

Native Ollama on M1 is a net improvement **infrastructure-wise** (no OOM, real
Metal, Docker bridge) and should be kept as the dev runtime, replacing the
containerized Ollama for normal development. Mistral 7B Q4_K_M itself should
**not** be enabled for grounded analytics on this hardware. The ground is
prepared for a later **Decision D** model swap without further architecture
change.

## 13. Deliverables

- `NATIVE_MACOS_OLLAMA_INTEGRATION.md` — 20-section integration/operations doc.
- `scripts/ollama-native.sh` — dev helper (binary/server/model/Docker bridge).
- `benchmark/llm_insights/results/native_mistral_mistral_t0.1.json` +
  `native_mistral_summary.json` — reproducible native benchmark artifacts.
- This A–Z report.
