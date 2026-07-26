# Configuration Audit

**Date:** 2026-07-25
**Scope:** DEV_MODE and SEMANTIC_LAYER_ENABLED runtime behavior

---

## 1. DEV_MODE

### Current Value
`True` (Python default in `services/shared/config.py:87`). No environment variable override in docker-compose.yml, .env, or .env.example.

### Runtime Effect

**Affects exactly one thing: authentication fallback.**

| Location | Behavior when True | Behavior when False |
|----------|-------------------|---------------------|
| `auth.py:188-194` | If DB connection is `None`, falls back to in-memory mock user store | Returns `None` (login fails) |
| `auth.py:268-270` | If DB query throws exception, falls back to mock store | Login fails |
| `auth.py:276-278` | `_authenticate_mock()` is allowed to run | `_authenticate_mock()` refuses to authenticate anyone |
| `routes.py:409-414` | If DB unavailable during permission lookup, uses mock store permissions | Empty permissions list |

### What DEV_MODE Does NOT Control
- SQL generation
- Validation
- Safety checks
- Schema matching
- Entity resolution
- Intent classification
- Benchmark execution
- Logging levels
- Semantic layer features

### Verdict

**Classification: B — Flag exists but has limited runtime effect.**

DEV_MODE is NOT obsolete. It controls authentication fallback behavior. However, it is misleadingly named — it suggests broad development-mode behavior when it only affects auth.

**Recommendation:** Rename to `AUTH_MOCK_FALLBACK_ENABLED` or add a note to the config description. The default of `True` means the benchmark ran with mock auth available, which contributed to the 0% authorization enforcement rate (B2154-B2158 executed because mock auth succeeded).

**Impact on benchmark:** The V2 benchmark ran with `DEV_MODE=true`. Authorization tests (B2154-B2158) expected `auth_required` but received `pipeline_complete` because the benchmark harness did not send auth tokens, and the system fell back to mock authentication. To test real authorization, `DEV_MODE` must be `False`.

---

## 2. SEMANTIC_LAYER_ENABLED

### Current Values (docker-compose.yml)

| Service | Value | Actual Effect |
|---------|-------|---------------|
| api-gateway | `false` | N/A (auth-only service) |
| orchestrator-agent | `false` | Trace block always shows `"enabled": False` |
| **intent-agent** | **`true`** | French+English keywords, dynamic KPI detection, `detected_kpis` in response |
| schema-agent | `false` | Static hardcoded domain-to-table mappings only |
| entity-resolution-agent | `false` | Hardcoded join map only; BFS graph never built |
| sql-agent | `false` | No metric formula injection, no join validation |
| validation-agent | `false` | No semantic warnings on unknown tables |

### Inconsistency

The orchestrator reads `SEMANTIC_LAYER_ENABLED` from the shared Pydantic Settings (`config.py:88`, default `false`). The individual microservices each read it via `os.getenv()` at module import time. These are **independent loading mechanisms** — the orchestrator's value does not propagate to the agents.

The intent-agent is the only service with `true`. All other agents use `false`. The orchestrator's trace block reports `"enabled": False` because its own value is `false`, even though the intent-agent has it enabled.

### What SEMANTIC_LAYER_ENABLED Controls Per Service

| Service | Enabled Effect | Disabled Effect |
|---------|---------------|-----------------|
| **intent-agent** | Broader FR+EN keyword tables, KPI detection from metric_registry, `detected_kpis` in response | Original 8 English-only categories, no KPI detection |
| **schema-agent** | Live table/column/join metadata from DB, BFS join discovery, business descriptions | Hardcoded domain-to-table mappings, static join paths |
| **entity-resolution-agent** | Glossary-based entity normalization, BFS join path discovery, safe join validation | Hardcoded join key lookup, fixed transitive joins |
| **sql-agent** | Metric formula injection (KPI→SQL), join validation against registry, semantic warnings | All joins accepted without validation, no formula injection |
| **validation-agent** | Warnings on unknown tables, warnings on raw arithmetic | No semantic warnings |

### What SEMANTIC_LAYER_ENABLED Does NOT Control
- Vector search (embedding service is separate)
- Core security (5-check validation, HMAC signing, RBAC)
- Intent classification logic
- Query execution

### Verdict

**Classification: C — Flag changes runtime, but current configuration is inconsistent and misleading.**

The flag is architecturally significant — it gates 5 major pipeline features. However:

1. **Intent-agent is enabled while all downstream agents are disabled.** The intent-agent detects KPIs and passes `detected_kpis` downstream, but the sql-agent ignores them because it has `SEMANTIC_LAYER_ENABLED=false`. This is wasted work.

2. **The orchestrator's trace block is misleading.** It reports `"enabled": False` because its own config is `false`, but the intent-agent actually has it enabled. The trace does not reflect per-service reality.

3. **The frozen manifest reports `SEMANTIC_LAYER_ENABLED: false`** which is accurate for most services but not for intent-agent.

**Recommendation:** Either enable `SEMANTIC_LAYER_ENABLED=true` across all services (to activate the full semantic layer) or set it `false` across all services (including intent-agent) for consistency. The current split configuration provides no benefit.

**Impact on benchmark:** The benchmark was run with `SEMANTIC_LAYER_ENABLED=false` on all services except intent-agent. The semantic layer features (BFS joins, metric formulas, glossary normalization, join validation) were not active. The 98.3% supported query completion was achieved WITHOUT the semantic layer. Re-running with the full semantic layer enabled could improve or change results — the benchmark should be rerun if the configuration changes.

---

## 3. Configuration Consistency Matrix

| Setting | config.py Default | docker-compose Override | .env Override | Benchmark State |
|---------|-------------------|------------------------|---------------|-----------------|
| DEV_MODE | True | None | None | True |
| SEMANTIC_LAYER_ENABLED | False | Per-service (mixed) | None | False (most services) |
| INTENT_CONFIDENCE_THRESHOLD | 0.31 | None | None | 0.31 |
| BENCHMARK_MODE | False | None | None | False |
| ENABLE_INSIGHTS_AGENT | True | None | None | True |
| ENABLE_COMPLIANCE_AGENT | True | None | None | True |

---

## 4. Code Changes Required

### Priority 1: Fix authorization test configuration
The benchmark authorization tests (B2154-B2158) cannot work with `DEV_MODE=True`. Either:
- Set `DEV_MODE=False` in docker-compose for api-gateway, OR
- Document that authorization benchmarks require `DEV_MODE=False`

### Priority 2: Reconcile SEMANTIC_LAYER_ENABLED
Set a consistent value across all services. Recommended: `false` everywhere until the semantic layer is validated, then enable everywhere.

### Priority 3: Add flags to .env.example
Both `DEV_MODE` and `SEMANTIC_LAYER_ENABLED` should appear in `.env.example` with documentation.
