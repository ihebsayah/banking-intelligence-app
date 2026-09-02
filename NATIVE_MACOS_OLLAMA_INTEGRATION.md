# NATIVE macOS OLLAMA INTEGRATION

Status: IMPLEMENTED (Sept 2026)
Scope: Move Ollama out of the Docker runtime onto native macOS Apple Silicon and
connect the Dockerized Banking Intelligence services to it via
`http://host.docker.internal:11434`.

---

## 1. Why Ollama was moved outside Docker

The previous STEP 5 live benchmark (Docker) showed the local runtime was
memory-starved and unusable for LLM interpretation:

- Dockerized **Mistral 7.2B** could not load at all — the Ollama llama runner
  was OOM-killed 100% of the time because the Docker Linux VM competes with the
  ~20-container banking stack for a 16 GB Mac's unified memory.
- **TinyLlama** loaded but produced 0/14 grounded, schema-valid responses, with
  p50 latency ≈ 146 s.

That history did **not** prove the Mac M1 cannot run Mistral 7B. The real barrier
was that Ollama was running inside Docker's Linux VM (CPU-only inference,
contending with the whole stack, and unable to use native Apple Silicon). This
document describes moving Ollama to run as a **native macOS process** so it can
use Metal directly.

## 2. Previous architecture

```
Docker Desktop
├── banking stack (~20 containers)
└── ollama (banking_ollama)  ── 0.0.0.0:11434  (Linux VM, CPU inference)
        └─ mistral:latest (OOM-killed on load), tinyllama:latest (too slow)
Services talked to it as  http://ollama:11434
```

## 3. New architecture

```
                    macOS HOST
        ┌───────────────────────────────┐
        │ Native Ollama (Metal)         │
        │  mistral:latest  (100% GPU)   │
        │  localhost:11434 / 0.0.0.0    │
        └───────────────▲───────────────┘
                        │ host.docker.internal:11434
        ┌───────────────┴───────────────┐
        │ Docker Desktop                │
        │  Banking Intelligence services│
        │  Insights Agent ──────────────┘ (only when ENABLE_LLM_INSIGHTS=true)
        └───────────────────────────────┘
```

Ollama no longer runs inside Docker for the normal macOS development profile.

## 4. Apple Silicon rationale

Running Ollama as a native macOS process lets llama.cpp/llama.cpp-rust use the
Metal execution backend and the M1's unified memory pool directly, instead of
being confined to the Docker Linux VM. Verified evidence (see §10, §11):
`ollama ps` reports **PROCESSOR = 100% GPU** for `mistral:latest`, and the
Ollama runner log reports `library=Metal ... description="Apple M1"
total="11.8 GiB" available="11.8 GiB"`. Mistral **loads without OOM** natively.

## 5. Native installation

On this machine native Ollama was already installed via Homebrew, so it was
reused (no duplicate runtime installed):

```
which ollama            → /opt/homebrew/bin/ollama
ollama --version        → ollama version is 0.21.1
```

If not installed, use: `brew install ollama` (or the official macOS dmg).

## 6. Native Ollama startup

Native Ollama must bind an interface reachable from Docker Desktop. Start it
with:

```
env OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

(A development helper encapsulates this — see §18 and `scripts/ollama-native.sh`.)

Verify the server responds:

```
curl http://localhost:11434/api/tags
lsof -nP -iTCP:11434 -sTCP:LISTEN   # expects: ollama  ...  *:11434 (LISTEN)
```

This machine currently uses the background `nohup` form so it survives the
shell; the launcher can be the standard macOS `ollama serve`.

## 7. Docker-to-host networking

Docker Desktop on macOS resolves the magic hostname `host.docker.internal` to
the macOS host. Because Ollama binds `0.0.0.0:11434`, containers reach it:

```
http://host.docker.internal:11434/api/tags   → 200, lists mistral:latest
```

Verified from both `banking_orchestrator` and `banking_insights_agent`
containers (see §18).

## 8. Environment configuration

`.env` (and `.env.example`) target native host Ollama:

```
MISTRAL_API_URL=http://host.docker.internal:11434
MISTRAL_MODEL=mistral

ENABLE_LLM_INSIGHTS=false
INSIGHTS_LLM_MODEL=mistral
INSIGHTS_LLM_TIMEOUT=30
INSIGHTS_LLM_TEMPERATURE=0.1
INSIGHTS_LLM_MAX_TOKENS=512
```

Compose defaults were changed from `http://ollama:11434` to
`http://host.docker.internal:11434` for `orchestrator-agent` and
`insights-agent`, so the stack works even with an empty/minimal `.env`.

## 9. Compose profile behavior

The containerized `ollama` service is now **optional** behind the
`docker-llm` Compose profile. It is preserved (not deleted) for CI / non-macOS /
legacy use but is **not** part of normal development:

```
docker compose up -d                          # normal dev: NO containerized Ollama
docker compose --profile docker-llm up -d     # legacy in-Docker Ollama
```

Config check:

```
docker compose config --services   # does NOT list ollama by default
```

## 10. Insights Agent configuration

The Insights Agent reads its own settings from `services/insights_agent/config.py`:

- `MISTRAL_API_URL` default → `http://host.docker.internal:11434`
- `INSIGHTS_LLM_MODEL` is the **single source of truth** for the Insights model.

The compose `insights-agent` block passes the full `INSIGHTS_LLM_*` set
(`MODEL`, `TIMEOUT`, `TEMPERATURE`, `MAX_TOKENS`) and `ENABLE_LLM_INSIGHTS`.

### Model precedence

`MistralIntegrator` resolves the model as `INSIGHTS_LLM_MODEL or MISTRAL_MODEL`.
Because `INSIGHTS_LLM_MODEL` has a default, it always wins; the generic
`MISTRAL_MODEL` **never** silently overrides it. If you change the analytics
model, set `INSIGHTS_LLM_MODEL` (not `MISTRAL_MODEL`).

## 11. Apple Silicon / Metal evidence

```
ollama ps
NAME              ID              SIZE    PROCESSOR    CONTEXT
mistral:latest    6577803aa9a0    5.1 GB  100% GPU     4096
```

Ollama runner log:

```
inference compute ... library=Metal ... description="Apple M1"
total="11.8 GiB" available="11.8 GiB"
```

This is a definitive departure from the Docker CPU (`mmap=false`, no GPU)
path — native Mistral runs on the Metal backend.

## 12. Feature flags

- `ENABLE_LLM_INSIGHTS` — master switch for LLM interpretation in the Insights
  Agent. **Keeps default `false`.**
- When `false`, the Insights Agent makes **zero** Ollama calls: the
  NecessityGate still runs deterministically, but the
  `if decision.use_llm and ENABLE_LLM_INSIGHTS` guard short-circuits before any
  network request.
- The deterministic analytical facts, NecessityGate, deterministic formatter,
  statistical analyzer, and GroundingValidator all run regardless.

## 13. Health checks

- Insights Agent `/health` reflects the **deterministic service**, not Ollama:

```json
{ "status": "healthy", "service": "insights_agent", "port": 8013,
  "llm_enabled": false, "llm_available": "unknown" }
```

- `llm_enabled` mirrors `ENABLE_LLM_INSIGHTS`; `llm_available` is a separate
  representational field (kept `"unknown"` so health never depends on probing
  Ollama). API compatibility preserved: the original `status`/`service`/`port`
  keys are unchanged.
- The `depends_on: ollama` hard dependency on the Insights Agent was removed.
  With `ENABLE_LLM_INSIGHTS=false`, the whole stack starts with no Ollama
  container.

## 14. Failure behavior

If native Ollama is down (or a request times out / is malformed / ungrounded),
`MistralIntegrator.interpret()` returns an `llm_fallback` and the Insights
Agent uses the **deterministic summary**. The pipeline never blocks, never
errors out, and never surfaces ungrounded content. Verified: with a dead
endpoint, `interpret()` returns `LLM_UNAVAILABLE_OR_EMPTY` fallback without
raising.

## 15. Benchmark procedure

Reuse the STEP 5 runner against native Mistral with an extended timeout so
cold-start/model-load is not miscounted as a failure:

```
cd benchmark/llm_insights
OLLAMA_API_URL=http://localhost:11434 \
INSIGHTS_LLM_TIMEOUT=180 \
python3 benchmark_runner.py --only mistral --temps 0.1 --timeout 180 --label native_mistral
```

The runner reuses the production grounding components (payload builder,
`GroundingValidator`, Pydantic schema, NecessityGate, DeterministicFormatter),
so results are directly comparable to the Docker baseline.

## 16. Benchmark results

_See **Results** section near end of this file (filled from the native run)._

## 17. Development startup procedure

```
# 1. Start native Ollama (once per boot):
scripts/ollama-native.sh --start
#    or: env OLLAMA_HOST=0.0.0.0:11434 ollama serve

# 2. Start the banking stack (no containerized Ollama needed):
docker compose up -d

# 3. Sanity check:
scripts/ollama-native.sh                # binary / server / model / docker bridge
```

## 18. Development shutdown procedure

```
docker compose down          # stops banking stack (deterministic path: fine with no Ollama)
# Native Ollama: stop the background serve process you started, e.g.
kill $(pgrep -f 'ollama serve')   # optional — safe to leave running for dev
```

## 19. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| Container cannot reach `host.docker.internal:11434` | Native Ollama bound only to loopback. Restart with `OLLAMA_HOST=0.0.0.0:11434`. |
| `llama runner ... signal: killed` | Running Dockerized (old OOM) — switch to native (§6). |
| Grounded output rejected (`UNSUPPORTED_NUMERIC_CLAIM`, `UNKNOWN_FACT_ID`) | Mistral added a number not in the verified payload or mangled a fact ID. Deterministic GroundingValidator correctly rejects it; expect occasional `llm_fallback`. |
| `Ollama timed out` at 30s | `INSIGHTS_LLM_TIMEOUT` too tight for cold-start. Native grounded generation measured ≈55–100s. Bump per §15 if you intentionally test/permit LLM. |
| Health shows `llm_enabled:false` | Expected. Deterministic path is the safe default. |
| `docker compose up -d` starts `banking_ollama` unexpectedly | Old image/container lingering — `docker compose --profile docker-llm down`, then plain `docker compose up -d`. |

## 20. How to revert to Docker Ollama

1. Stop native Ollama: `kill $(pgrep -f 'ollama serve')` (frees port 11434).
2. Start the legacy containerized runtime:
   `docker compose --profile docker-llm up -d ollama`
3. Point services back to the containerized endpoint. Either:
   - set `MISTRAL_API_URL=http://ollama:11434` in `.env`, or
   - revert the compose defaults (orchestrator-agent / insights-agent) to
     `http://ollama:11434`.
4. Recreate the services to pick up the new env:
   `docker compose up -d orchestrator-agent insights-agent`
5. Re-enable the hard dependency if you want the old startup ordering back
   (`depends_on: ollama` on `insights-agent`) — not recommended.
   The Docker Ollama image, container definition, and `ollama_data` volume are
   all preserved.

---

## Results (native benchmark)

Run source: `benchmark/llm_insights/results/native_mistral_mistral_t0.1.json`
and `native_mistral_summary.json`. Native Mistral (`mistral:latest`, Q4_K_M,
temp 0.1, timeout 180s), 46 cases (14 LLM-useful, 32 negative controls).

| Metric | Native Mistral (M1) | Docker TinyLlama (STEP5 baseline) |
|--------|--------------------:|----------------------------------:|
| LLM attempts (gated useful) | 14 | 14 |
| **Grounded LLM responses** | **0** | 0 |
| **Grounding pass rate** | **0.0%** | 0% |
| Unsupported-numeric rate | 78.6% | high |
| Forbidden-causal claim rate | 14.3% | high |
| Valid JSON rate | 100% | n/a |
| Latency p50 | ≈86 s | ≈146 s |
| Latency p95 | ≈119 s | ≈246 s |
| Timeouts / transport failures | 0 | n/a |

### Interpretation

Native allows Mistral to **load and run on Metal** (a real win over Docker,
which OOM-killed the model) and to emit **fluent, valid-JSON prose**. But the
grounded-analytics contract is not met: on the full suite the deterministic
`GroundingValidator` rejected **all 14** LLM-useful responses.

Failure is dominated by **numeric hallucination** — Mistral repeatedly emits
values that are not in the verified `allowed_numbers` payload (e.g. `60`,
`500`, `5400`, `"60,000."`, `"14,000."`, `27`, `1.57`, `2.0`), plus occasional
causal claims and (on some probes) mangled fact-IDs. Small quantized 7B models
cannot be relied upon to reproduce exact figures under the strict grounding
gate. Two probe runs on the same package also produced **non-deterministic**
results — a clean grounded pass one run, a rejection the next — so compliance
is not repeatable.

The safety net works exactly as designed: nothing ungrounded ever surfaces; the
pipeline falls back to the deterministic summary. But the "useful" LLM path is
effectively dead on this hardware/model.

## Decision

**Decision B/C (keep LLM layer, but disabled).** The native runtime migration
is a success (no OOM, Metal GPU, Docker bridge working, health/flags correct),
so the code path is kept and fully documented. Mistral 7B Q4 on M1 is however
**not usable** for strict grounded analytics (0% pass, ~86 s p50, non-repeating).
Action taken:

- **`ENABLE_LLM_INSIGHTS` stays `false`** — deterministic analytical facts,
  NecessityGate, deterministic formatter, and GroundingValidator remain the
  production path and are unaffected.
- The native Ollama wiring is retained so the LLM layer can be re-enabled
  later, e.g. via **Decision D** (a smaller or higher-quality grounded model).
- **Caveat:** native Ollama binds `0.0.0.0:11434` (no auth) and is reachable on
  the LAN — acceptable only as a dev tradeoff for `host.docker.internal` access;
  block external exposure with the macOS application firewall or a host-only
  bind in non-dev environments.
