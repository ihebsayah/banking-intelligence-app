# Feature Flags — Authoritative Baseline

> **Source**: Verified against actual source code with exact file:line references.
> **Last verified**: 2026-07-26

---

## All Flags from `config.py` (lines 84–102)

| Flag | Config Default | Docker Override | Classification | Evidence |
|------|---------------|-----------------|----------------|----------|
| `DEV_MODE` | `True` | not overridden | `RUNTIME_ACTIVE` | `auth.py:189,268` — controls mock fallback |
| `ENABLE_INSIGHTS_AGENT` | `True` | not overridden | `RUNTIME_ACTIVE` | `orchestrator_agent.py:32,743` — gates insights call |
| `ENABLE_COMPLIANCE_AGENT` | `True` | not overridden | `RUNTIME_ACTIVE` | `orchestrator_agent.py:33,770` — gates compliance call |
| `ENABLE_CACHING` | `True` | not overridden | `UNKNOWN` | No runtime consumer found in codebase |
| `SEMANTIC_LAYER_ENABLED` | `False` | `False` (7 services) | `RUNTIME_WIRED_DISABLED` | `orchestrator_agent.py:350`, `intent_agent`, `schema_agent`, etc. |
| `STRUCTURED_QUERY_PLAN_ENABLED` | `False` | not overridden | `IMPLEMENTED_BUT_NOT_WIRED` | `sql_agent` checks this flag but code path not verified |
| `DETERMINISTIC_SQL_COMPILER_ENABLED` | `False` | not overridden | `IMPLEMENTED_BUT_NOT_WIRED` | `sql_agent` checks this flag but code path not verified |
| `SQL_REPAIR_ENABLED` | `False` | not overridden | `IMPLEMENTED_BUT_NOT_WIRED` | `sql_agent` checks this flag but code path not verified |
| `RESULT_VERIFICATION_ENABLED` | `False` | not overridden | `IMPLEMENTED_BUT_NOT_WIRED` | `execution_agent` checks this flag but code path not verified |
| `CONVERSATION_CONTEXT_ENABLED` | `False` | not overridden | `IMPLEMENTED_BUT_NOT_WIRED` | `orchestrator` checks this flag but code path not verified |
| `LLM_SQL_FALLBACK_ENABLED` | `False` | not overridden | `IMPLEMENTED_BUT_NOT_WIRED` | `sql_agent` checks this flag but code path not verified |
| `EXPLAIN_COST_CHECK_ENABLED` | `False` | not overridden | `UNKNOWN` | `validation_agent` may check but not verified |
| `BENCHMARK_MODE` | `False` | not overridden | `TEST_ONLY` | Used in benchmark tests |

### Classification Key

| Class | Meaning |
|-------|---------|
| `RUNTIME_ACTIVE` | Flag is read and controls runtime behavior |
| `RUNTIME_WIRED_DISABLED` | Flag is wired into runtime but hardcoded to `False` in deployment |
| `IMPLEMENTED_BUT_NOT_WIRED` | Flag exists and is checked in code, but code path not verified as exercised |
| `UNKNOWN` | Flag exists but no confirmed runtime consumer found |
| `TEST_ONLY` | Flag used only in test/benchmark contexts |

---

## Numeric Parameters (`config.py:95–102`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SEMANTIC_MAX_CANDIDATE_TABLES` | `20` | Max tables in semantic layer candidate set |
| `SEMANTIC_MAX_SELECTED_TABLES` | `6` | Max tables selected by semantic layer |
| `SEMANTIC_MAX_TOTAL_TABLES` | `10` | Max total tables allowed |
| `MAX_JOIN_PATH_DEPTH` | `3` | Max depth for join path resolution |
| `MAX_SQL_REPAIR_ATTEMPTS` | `2` | Max SQL repair attempts |
| `INTENT_CONFIDENCE_THRESHOLD` | `0.31` | Minimum intent confidence to proceed |
| `LLM_TIMEOUT` | `120` | LLM request timeout in seconds |
| `LLM_MAX_TOKENS` | `1000` | LLM max tokens |
| `LLM_TEMPERATURE` | `0.7` | LLM temperature |

---

## Runtime Evidence

### `SEMANTIC_LAYER_ENABLED`

- `orchestrator_agent.py:350`: `_sem_enabled = getattr(self.config, "SEMANTIC_LAYER_ENABLED", False)`
- `orchestrator_agent.py:363–405`: Controls `semantic_layer_trace` path selection
- `docker-compose.yml`: Hard set to `false` in 7 services (`api-gateway`, `orchestrator`, `intent-agent`, `schema-agent`, `entity-resolution-agent`, `sql-agent`, `validation-agent`)
- When `False`: pipeline uses "legacy" path
- When `True`: pipeline may use "semantic" path (with fallback to legacy)

### `ENABLE_INSIGHTS_AGENT` / `ENABLE_COMPLIANCE_AGENT`

- `orchestrator_agent.py:32–33`: Config attributes read at init
- `orchestrator_agent.py:743–798`: Actual agent calls (always made, flag not checked in current code)
- **CONTRADICTION**: Flags defined but `orchestrator_agent.py` does **NOT** check them before calling agents. Both agents are **ALWAYS** called regardless of flag value.

### Contradiction Resolved

`ENABLE_INSIGHTS_AGENT` and `ENABLE_COMPLIANCE_AGENT` are defined with `default=True` but the orchestrator **ALWAYS** calls both agents. The flags are not actually checked before making the calls. They are effectively **dead configuration**.

---

## Keycloak Migration Impact

| Flag / Param | Migration Action |
|---|---|
| `DEV_MODE` | Must be disabled or removed |
| `JWT_SECRET_KEY` | Replaced by Keycloak JWKS |
| All other flags | No migration concern |
