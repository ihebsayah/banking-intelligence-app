# LLM Runtime Usage & Efficiency Audit

**Date:** 2026-08-31  
**Scope:** Full repository — every service, every LLM-related code path  
**Mode:** READ-ONLY — no files modified

---

## 1. Executive Summary

**9 of 11 subsystems are fully deterministic (zero LLM). 1 uses spaCy ML (not LLM). 1 uses Ollama/Mistral LLM — and it is currently disabled by default.**

The Orchestrator instantiates a `MistralClient` at startup and stores it as `self.mistral`, but **never calls it** — zero invocations of `generate()` or `chat()` exist in any orchestrator code path. This is a dead runtime dependency.

The only actual LLM call in the entire system lives in `services/insights_agent/mistral_integrator.py`, which calls Ollama's `/api/generate` endpoint to produce natural-language summaries and recommendations. However, `ENABLE_INSIGHTS_AGENT=false` in `.env`, meaning the Insights Agent service itself is not invoked in the live pipeline.

**Bottom line:** The system currently makes **zero LLM calls** in production. The MistralClient in the orchestrator is dead code. The Insights Agent LLM is real but feature-flagged off.

---

## 2. Current Runtime Pipeline

```
User Question
    ↓
API Gateway (port 8000)
    ↓
Orchestrator (port 8001)
    ├── [INSTANTIATES MistralClient] ← NEVER CALLED
    ↓
Intent Agent (port 8002) ← spaCy + keyword rules (NO LLM)
    ↓
Schema Agent (port 8003) ← static dict + optional DB cache (NO LLM)
    ↓
Entity Resolution (port 8004) ← hardcoded maps + BFS (NO LLM)
    ↓
SQL Agent (port 8005) ← template compiler + whitelist (NO LLM)
    ↓
Validation Agent (port 8006) ← 5 regex checks + HMAC (NO LLM)
    ↓
Compliance Agent (port 8011) ← GDPR/PCI/SOX/AML rules (NO LLM)
    ↓
Execution Agent (port 8007) ← asyncpg parameterized queries (NO LLM)
    ↓
Insights Agent (port 8013) ← FEATURE FLAGGED OFF
    ├── Statistical Analyzer (numpy) — REAL
    ├── Context Gatherer (SQL) — STATIC
    ├── Trend Identification — MOSTLY SYNTHETIC
    └── MistralIntegrator → Ollama /api/generate [LLM CALL] ← DISABLED
    ↓
Audit Agent (port 8008) ← WORM INSERT (NO LLM)
    ↓
Response
```

---

## 3. Actual LLM Calls

### LLM Call #1: Orchestrator MistralClient — DEAD CODE

| Field | Value |
|-------|-------|
| **File** | `services/orchestrator/orchestrator_agent.py:17-22` |
| **Instantiation** | `self.mistral = MistralClient(...)` in `__init__` |
| **Method called** | NONE — `self.mistral.generate()` is never invoked |
| **Runtime status** | Dead / unused dependency |
| **Evidence** | Grep for `self.mistral.` in orchestrator_agent.py returns zero method calls. Only `check_health()` is called in `main.py:61` at startup. |

### LLM Call #2: Orchestrator main.py global — DEAD CODE

| Field | Value |
|-------|-------|
| **File** | `services/orchestrator/main.py:54-61` |
| **Instantiation** | `mistral_client = MistralClient(...)` at startup |
| **Method called** | `mistral_client.check_health()` only — health check at boot |
| **Runtime status** | Dead — client never used after health check. A second client is created inside `OrchestratorAgent.__init__()` (line 17 of orchestrator_agent.py). Neither is ever used for generation. |
| **Classification** | DEAD / UNUSED RUNTIME DEPENDENCY |

### LLM Call #3: Insights Agent MistralIntegrator — REAL BUT DISABLED

| Field | Value |
|-------|-------|
| **File** | `services/insights_agent/mistral_integrator.py:184-203` |
| **Method** | `_call_ollama()` → `POST {base_url}/api/generate` |
| **Model** | Configurable: `MISTRAL_MODEL` (default: `mistral`, insights override: `tinyllama`) |
| **Endpoint** | `MISTRAL_API_URL` → `http://host.docker.internal:11434/api/generate` |
| **Invocation path** | `InsightsGenerator.generate()` → `self.mistral.generate_summary_and_recommendations()` → `self._call_ollama()` |
| **Runtime status** | `ENABLE_INSIGHTS_AGENT=false` in `.env` → orchestrator still calls the HTTP endpoint but service is down/unavailable → fallback to template |
| **Classification** | LLM_CURRENTLY_LOW_VALUE + DISABLED |

---

## 4. Orchestrator Findings

**File:** `services/orchestrator/orchestrator_agent.py` (1022 lines)

### MistralClient Usage
- **Line 1:** `from mistral_client import MistralClient`
- **Lines 17-22:** `self.mistral = MistralClient(base_url=..., model=..., timeout=..., max_tokens=...)`
- **Zero method calls on `self.mistral`** anywhere in the 1022-line file

### Pipeline Orchestration
The `process_query()` method (lines 39-438) follows a **fixed, deterministic sequence**:

1. Intent Agent → HTTP POST `/process_intent`
2. Schema Agent → HTTP POST `/map_schema`
3. Entity Resolution → HTTP POST `/resolve_entities`
4. SQL Agent → HTTP POST `/generate_sql`
5. Validation Agent → HTTP POST `/validate_query`
6. Compliance Agent → HTTP POST `/check_compliance`
7. Execution Agent → HTTP POST `/execute_query`
8. Insights Agent → HTTP POST `/generate_insights` (non-fatal on failure)
9. Audit Agent → HTTP POST `/log_access`

**No dynamic planning. No LLM-driven routing. No conditional LLM calls. Pure fixed pipeline.**

### Classification
| Component | Classification |
|-----------|---------------|
| `self.mistral` in orchestrator_agent.py | DEAD / UNUSED RUNTIME DEPENDENCY |
| `mistral_client` in main.py | DEAD / UNUSED RUNTIME DEPENDENCY (health check only) |
| Orchestration logic | DETERMINISTIC (fixed sequence) |

---

## 5. Intent Findings

**File:** `services/intent_agent/intent_recognizer.py` (543 lines)

### Implementation
- **spaCy** (`en_core_web_sm`) for tokenization and lemmatization
- **Keyword scoring** against 8 intent categories (12 with semantic layer)
- **Bilingual** (English + French) keyword tables
- **Redis caching** (TTL 24h)
- **Constraint extraction** via regex (top-N, time periods, geography, segments)
- **Adversarial pattern detection** via regex (SQL injection, prompt injection, social engineering)
- **Ambiguity detection** (near-tie scoring, word ambiguity, risk thresholds)

### LLM Usage
**None.** Explicitly documented: `"Pattern-matching intent recogniser (no LLM)."` (line 4)

### Classification
**DETERMINISTIC_PREFERRED** — spaCy tokenization + keyword scoring is adequate for the banking domain. LLM could add value for genuinely novel or ambiguous queries, but the current regex-based constraint extraction and adversarial detection are more reliable.

---

## 6. Schema Findings

**File:** `services/schema_agent/schema_matcher.py` (366 lines)

### Implementation
- **Static dict mappings:** `INTENT_TO_DOMAINS`, `DOMAIN_TO_TABLES`, `JOIN_GRAPH`
- **Optional DB cache:** `table_metadata`, `column_metadata`, `join_registry` (when `SEMANTIC_LAYER_ENABLED=True`)
- **BFS join path discovery** via `_bfs_join_path()` over join_registry
- **Progressive schema retrieval** (Phase 6C)

### LLM Usage
**None.** Grep for `mistral|LLM|llm|openai|generate\(` in schema_agent returns zero matches.

### Classification
**DETERMINISTIC_PREFERRED** — Schema retrieval is a pure mapping operation. LLM has no role here.

---

## 7. Entity Resolution Findings

**File:** `services/entity_resolution_agent/entity_resolver.py` (330 lines)

### Implementation
- **Primary key lookup** via `semantic_id_mapper.py` (hardcoded maps)
- **Join key discovery** via `find_join_key()`
- **BFS graph traversal** over join_registry (when semantic layer enabled)
- **Business glossary** synonym normalization (when semantic layer enabled)
- **Fallback:** hardcoded `SEMANTIC_JOIN_MAP`

### LLM Usage
**None.** Grep returns zero matches.

### Classification
**DETERMINISTIC_PREFERRED** — Entity resolution uses exact matching and graph traversal. LLM could help with truly ambiguous entity references (e.g., "revenue" meaning different things), but the current system handles this via structured intent extraction.

---

## 8. SQL Agent Findings

**File:** `services/sql_agent/sql_builder.py` (887 lines), `deterministic_compiler.py` (535 lines)

### SQL Generation Strategy
**100% deterministic.** Two paths:

1. **Template path** (`sql_builder.py`): Rule-based builder with column whitelist, parameterized `?` placeholders, and LIMIT enforcement
2. **Compiler path** (`deterministic_compiler.py`): `QueryPlan → CompiledQuery` pure renderer when `DETERMINISTIC_SQL_COMPILER_ENABLED=True`

### Security Guarantees (CONFIRMED)
- **Parameterized queries:** All user values bound via `$N` placeholders (asyncpg convention)
- **Column whitelist:** `ALLOWED_COLUMNS` dict — only whitelisted columns in SELECT/WHERE/GROUP BY
- **LIMIT enforcement:** `_assert_parameterized()` rejects SQL without LIMIT
- **No string concatenation of user data:** Belt-and-suspenders check in `main.py:165-171`
- **HMAC signing:** `sign_query_payload()` in validation, verified in execution

### LLM SQL Fallback
- `LLM_SQL_FALLBACK_ENABLED = False` (default) in `config.py:150`
- **No LLM SQL generation code exists** — grep for `mistral|LLM|llm` in sql_agent returns zero matches
- The flag exists but has no implementation behind it

### Security Assessment
**User text CANNOT be concatenated into SQL.** The orchestrator passes structured data (`intent`, `tables`, `filters`, `join_paths`) to the SQL agent. The SQL builder constructs queries from these structured fields using parameterized placeholders. Even the user query text (`user_query`) is only passed for logging, never injected into SQL.

### Classification
**DETERMINISTIC_PREFERRED** — SQL generation from structured intent is a compiler task. LLM-generated SQL carries hallucination risk with no security benefit.

---

## 9. Validation Findings

**File:** `services/validation_agent/query_validator.py` (352 lines)

### Checks (ALL DETERMINISTIC)
1. **syntax_check** — `sqlparse.parse()` validates syntax
2. **select_only** — First statement must be SELECT (no DML/DDL)
3. **keyword_check** — 40+ dangerous keywords rejected (DELETE, DROP, GRANT, etc.)
4. **limit_check** — LIMIT clause required
5. **pattern_check** — 18 injection patterns detected (OR 1=1, UNION SELECT, stacked queries, etc.)

### Additional
- **HMAC-SHA256 signing** of safe queries with nonce and timestamp
- **Signature verification** with max age (60s default)
- **Semantic warnings** (non-blocking): unknown table refs, raw arithmetic in SELECT

### LLM Usage
**None.** Grep returns zero matches.

### Classification
**DETERMINISTIC_PREFERRED** — Security validation must be deterministic and auditable. LLM has no role.

---

## 10. Compliance Findings

**File:** `services/compliance_agent/compliance_checker.py` (266 lines)

### Rules Implemented
- **GDPR:** PII column masking (ssn, email, phone, national_id, date_of_birth)
- **PCI-DSS:** Card data access restriction (credit_card, card_number, pan, cvv) — role-gated
- **SOX:** Segregation of duties enforcement (maker_checker role violation)
- **AML:** Transaction data access monitoring — role-gated
- **KYC:** Intent-based role gating (compliance, admin, kyc_officer only)
- **DB-driven rules:** `compliance_rules` table for dynamic access_control and data_masking rules

### LLM Usage
**None.** Grep returns zero matches.

### Classification
**DETERMINISTIC_PREFERRED** — Compliance/regulatory decisions must be rule-based, auditable, and deterministic. LLM has no role in security/compliance.

---

## 11. Execution Findings

**File:** `services/execution_agent/query_executor.py` (428 lines)

### Security Controls
- **HMAC signature verification** before execution (blocks tampered queries)
- **asyncpg parameterized queries** ($1, $2 placeholders)
- **30-second execution timeout** via `asyncio.wait_for()`
- **Redis caching** (cache-aside, 1h TTL)
- **PGRepairEngine** for error recovery (deadlocks, timeouts, syntax)
- **PlanRefiner** for structural plan adjustments
- **Retry policy** with bounded attempts

### LLM Usage
**None.** Grep returns zero matches. PGRepairEngine and PlanRefiner are deterministic.

### Classification
**DETERMINISTIC_PREFERRED** — Query execution must be deterministic. LLM has no role.

---

## 12. Insights Agent Deep Audit

**Files:** `services/insights_agent/` (7 files)

### Output Field Analysis

| Output Field | Source | Classification | Risk |
|-------------|--------|---------------|------|
| `key_metrics.total_count` | `len(request.results)` | COMPUTED from real data | None |
| `key_metrics.total_sum` | `numpy.sum()` | COMPUTED from real data | None |
| `key_metrics.average` | `numpy.mean()` | COMPUTED from real data | None |
| `key_metrics.concentration_pct` | `(total_sum / total_deposits) * 100` | COMPUTED, but denominator is static system total | Low |
| `key_metrics.top_region` | `max(context.regional_breakdown)` | STATIC — same for every query in the DB | Medium |
| `trends[].concentration` | Fires when `>30%` threshold | SEMI-DYNAMIC — real threshold check | Low |
| `trends[].yoy_growth` | **HARDCODED 12.5%** (was in prior version; currently removed in code) | ~~DATA-INTEGRITY RISK~~ — code comment says "Synthetic YoY growth indicator" | Previously HIGH |
| `trends[].risk_flag_volume` | `context.segment_breakdown["high_risk"]` | STATIC system-wide count | Low |
| `anomalies` | `numpy` outlier detection (>2σ) | COMPUTED from real data | None |
| `summary` (LLM path) | Mistral/tinyllama via Ollama | LLM-generated — dynamic but low quality | Medium |
| `summary` (fallback) | Template: `"Analysis of '{query}' across {N} records..."` | TEMPLATE — dynamic numbers, static prose | Low |
| `recommendations` (LLM path) | Mistral/tinyllama via Ollama | LLM-generated — low quality | Medium |
| `recommendations` (fallback) | 3 hardcoded sentences with minor number substitution | STATIC — same recommendations for every query | High |
| `confidence` | **HARDCODED 0.85** | STATIC — does not reflect actual insight quality | HIGH |

### LLM Call Path (When Enabled)

```
InsightsGenerator.generate()
  ↓
self.mistral.generate_summary_and_recommendations()
  ↓
MistralIntegrator._call_ollama()
  ↓
POST {base_url}/api/generate
  body: { model: "tinyllama", prompt: <combined_prompt>, stream: false, temperature: 0.6, num_predict: 300 }
  timeout: 180s
```

### Data Sent to LLM

| Input | Content | PII Risk |
|-------|---------|----------|
| `query_text` | Original user question | LOW — may contain branch names, entity names |
| `query_intent` | Category string (e.g., "customer_analysis") | NONE |
| `results[:2]` | First 2 rows of query results | **MEDIUM — may contain customer names, balances** |
| `results[:5] column names` | Column headers | LOW |
| Statistics | total, avg, outlier count | LOW |
| Context | total_deposits, top_region | LOW |
| Trends | metric names only | NONE |

**Sensitivity Assessment:** Because Ollama runs locally, PII in LLM prompts does not leave the machine. Acceptable for local deployment. Would be a **CRITICAL** issue if pointed at a cloud API.

### Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| Ollama HTTP 200 | LLM summary + recommendations returned |
| Ollama HTTP error | Empty string → fallback to template summary + static recommendations |
| Ollama timeout (180s) | Empty string → same fallback |
| Ollama connection refused | Empty string → same fallback |
| Insights Agent unreachable | Orchestrator logs "Insights unavailable (non-fatal)", continues |

**Fallback output is functionally near-identical to LLM output** — the template substitutes the same numbers that the LLM would describe. The LLM call adds natural-language variation but not analytical value.

### Key Findings

1. **`confidence=0.85` is hardcoded** — does not vary with LLM success/failure or data quality. This is misleading.
2. **`recommendations` fallback is the same 3 sentences for every query** — only the outlier count and average number change.
3. **`top_region` is static** — same system-wide maximum for every query.
4. **Only 1 numeric column is analyzed** — multi-column correlation is not performed.
5. **Context is not query-scoped** — `total_deposits` and `regional_breakdown` are system-wide, not filtered by the user's query tables/filters/time range.

---

## 13. Feature Flags

| Flag | Default | `.env` Value | `.env.example` Value | Impact |
|------|---------|-------------|---------------------|--------|
| `ENABLE_INSIGHTS_AGENT` | `True` (config.py:136) | **`false`** (.env:62) | `false` (.env.example:115) | Insights Agent service not invoked. Orchestrator still calls HTTP endpoint → fails → non-fatal fallback. |
| `LLM_SQL_FALLBACK_ENABLED` | `False` (config.py:150) | Not set | Not set | No LLM SQL fallback code exists — flag is dead |
| `SEMANTIC_LAYER_ENABLED` | `False` (config.py:144) | Not set | Not set | Disables DB-driven schema/entity/SQL semantic features |
| `DEV_MODE` | `True` (config.py:139) | Not set | Not set | Enables development fallbacks/mocks |

### What Happens When Insights Agent is Disabled
1. Orchestrator calls `POST /generate_insights` on port 8013
2. If Insights Agent service is down → exception caught, logged as "Insights unavailable (non-fatal)"
3. Response includes `"insights": null`
4. Pipeline continues to Audit Agent normally

### Does Mistral Run Elsewhere When Insights is Disabled?
**No.** The only actual LLM call path is `mistral_integrator.py` inside the Insights Agent. When `ENABLE_INSIGHTS_AGENT=false` and the service is down, no LLM calls occur anywhere in the system.

---

## 14. Model Configuration

### Global Config (`services/shared/config.py`)

| Parameter | Value | Source |
|-----------|-------|--------|
| `MISTRAL_API_URL` | `http://host.docker.internal:11434` | `.env` |
| `MISTRAL_MODEL` | `mistral` | `.env` |
| `ORCHESTRATOR_LLM` | `mistral` | `.env` |
| `LLM_TIMEOUT` | 120s | `.env` |
| `LLM_MAX_TOKENS` | 1000 | `.env` |
| `LLM_TEMPERATURE` | 0.7 | `.env` |

### Insights Agent Config (`services/insights_agent/config.py`)

| Parameter | Value | Source |
|-----------|-------|--------|
| `MISTRAL_API_URL` | `http://localhost:11434` | config.py default (overridden by env) |
| `MISTRAL_MODEL` | `mistral` | config.py default |

### Docker Compose Override (`docker-compose.yml:459`)
```yaml
MISTRAL_MODEL=${INSIGHTS_LLM_MODEL:-tinyllama}
```
**Insights Agent uses `tinyllama` (1B params), not `mistral` (7B params).** This is the model that would actually be called for insights.

### Ollama API Parameters (from `mistral_integrator.py:184-203`)

| Parameter | Value |
|-----------|-------|
| `stream` | `False` |
| `temperature` | 0.6 |
| `num_predict` | 300 (insights) / 400 (summary) |
| `timeout` | 180s |

### Ollama API Parameters (from `shared/mistral_client.py:65-76`)

| Parameter | Value |
|-----------|-------|
| `stream` | `False` |
| `temperature` | 0.7 |
| `num_predict` | 1000 |
| `timeout` | 130s (config + 10s buffer) |

### Prompt Structure (Insights Combined Prompt)
```
Banking analysis. Query: {query_text}
Intent: {query_intent}. Records: {len(results)}. Columns: {cols}
Stats: total={total_sum}, avg={average}, outliers={len(outliers)}
Context: deposits={total_deposits}, region={top_region}
Trends: {[t.metric for t in trends]}

Write summary then 3 recommendations.
Summary:
Recommendations:
1.
2.
3.
```

---

## 15. Data Sent to LLM

### LLM Call #3 (Insights Agent — only actual call)

**INPUT:**
- `query_text` — raw user question (may contain entity names like branch names)
- `query_intent` — category string
- `results[:2]` — first 2 rows of SQL results (**may contain customer names, balances, account numbers**)
- `results[:5] column names` — first 5 column headers
- Aggregate statistics (total, avg, outlier count)
- System context (total deposits, top region)
- Trend metric names

**OUTPUT:**
- Free text: 2-3 sentence summary
- Structured: 3 numbered recommendations
- Parsed by `_parse_combined_response()` → splits on `\nRecommendations:` or `\n1.`

**PII Assessment:**
- Customer names, balances, and account details in `results[:2]` ARE sent to the LLM
- Because Ollama is local, PII does not leave the machine — acceptable for local deployment
- **Would be CRITICAL if Ollama were replaced with a cloud API**

---

## 16. Fallback Behavior

### Insights Agent LLM Fallback

| Call | Success Output | Failure Output | Difference |
|------|---------------|---------------|------------|
| Summary | LLM-generated 2-3 sentences (varies per query) | Template: `"Analysis of '{query}' across {N} records: total {col} = ${sum}..."` | LLM adds natural-language variation; template has same information |
| Recommendations | LLM-generated 3 items (varies) | `"1. Optimize operational capacity... 2. Schedule a portfolio risk review... 3. Tailor personalized high-value..."` | **LTM is almost identical** — same 3 generic sentences with minor number changes |

**Verdict:** The LLM call adds **minimal analytical value**. The fallback template contains the same statistical information in a more predictable format. The LLM output is lower quality (tinyllama, 1B params, 2KB context window) than the deterministic template.

---

## 17. Latency Evidence

### From Existing Documentation

| Source | Data Point |
|--------|-----------|
| `END_TO_END_PIPELINE_EVALUATION.md:140` | "Each LLM call (SQL generation + insights) takes 30-60s. A full pipeline with insights takes 60-130s." |
| `PERFORMANCE_AND_SCALABILITY_REPORT.md:112` | "Ollama LLM: 30s → TimeoutError caught, template fallback" |
| `FINAL_PROJECT_READINESS.md:160` | "LLM limited to 2KB context. yoy_growth hardcoded 12.5%." |

### Latency Breakdown (Estimated from Documentation)

| Stage | Latency | Source |
|-------|---------|--------|
| Intent (spaCy) | <100ms | Deterministic |
| Schema (dict lookup) | <50ms | Deterministic |
| Entity Resolution (BFS) | <50ms | Deterministic |
| SQL Generation (template) | <100ms | Deterministic |
| Validation (regex) | <50ms | Deterministic |
| Compliance (rules) | <100ms | Deterministic |
| Execution (asyncpg) | 10-500ms | Database dependent |
| **Insights LLM (Ollama/tinyllama)** | **30-60s** | CPU-only Ollama |
| **Insights fallback (template)** | **<100ms** | Deterministic |

**Insights LLM adds 30-60 seconds to pipeline latency for a summary that is functionally equivalent to the template fallback.**

---

## 18. Data-Integrity Risks

| Risk | Severity | Location | Description |
|------|----------|----------|-------------|
| Hardcoded confidence 0.85 | **HIGH** | `insights_generator.py:104` | Confidence score is always 0.85 regardless of LLM success, data quality, or insight completeness. Misleading to downstream consumers. |
| Static recommendations | **HIGH** | `mistral_integrator.py:140-144` | Same 3 generic recommendations for every query. Only the outlier count and average number change. |
| Static top_region | **MEDIUM** | `mistral_integrator.py:160-164` | Always shows the system-wide largest branch region, regardless of query context. |
| Static system context | **MEDIUM** | `context_gatherer.py:36-70` | `total_deposits`, `total_customers`, etc. are system-wide totals, not scoped to the user's query tables/filters/time range. |
| Template fallback indistinguishable from LLM | **MEDIUM** | `mistral_integrator.py:97-100` | When LLM fails, the fallback template produces output that is structurally identical to LLM output. Consumers cannot distinguish. |

---

## 19. Agent-by-Agent LLM Classification

| Component | Current Implementation | Current LLM Usage | Classification | Rationale |
|-----------|----------------------|-------------------|----------------|-----------|
| **Intent Agent** | spaCy + keyword scoring | None | **DETERMINISTIC_PREFERRED** | Pattern matching is reliable for banking domain. LLM could add marginal value for novel phrasings. |
| **Schema Agent** | Static dict + optional DB cache | None | **DETERMINISTIC_PREFERRED** | Pure mapping operation. LLM has no role. |
| **Entity Resolution** | Hardcoded maps + BFS graph | None | **DETERMINISTIC_PREFERRED** | Graph traversal is correct by construction. |
| **SQL Agent** | Template compiler + whitelist | None (LLM_SQL_FALLBACK_ENABLED=False, no implementation) | **DETERMINISTIC_PREFERRED** | SQL from structured intent is a compiler task. LLM carries hallucination risk. |
| **Validation Agent** | 5 regex checks + HMAC | None | **DETERMINISTIC_PREFERRED** | Security must be auditable and deterministic. |
| **Compliance Agent** | GDPR/PCI/SOX/AML/KYC rules | None | **DETERMINISTIC_PREFERRED** | Regulatory compliance must be rule-based. |
| **Execution Agent** | asyncpg + Redis cache | None | **DETERMINISTIC_PREFERRED** | Query execution is deterministic. |
| **Insights Agent** | numpy stats + templates + Ollama | **Yes — tinyllama via Ollama** (disabled) | **LLM_CURRENTLY_LOW_VALUE** | LLM adds minimal value over template fallback. tinyllama quality is insufficient for banking analysis. |
| **Audit Agent** | WORM INSERT | None | **DETERMINISTIC_PREFERRED** | Audit must be immutable and deterministic. |
| **Orchestrator** | Fixed HTTP pipeline | **MistralClient instantiated but NEVER called** | **DETERMINISTIC** (actual) / **DEAD_CODE** (MistralClient) | Pipeline is fixed sequence. MistralClient is dead code. |
| **Embedding Service** | sentence-transformers (MiniLM-L6) | None (not an LLM) | **DETERMINISTIC_PREFERRED** | Embedding model is ML, not generative LLM. |

---

## 20. Current Call Graph

```
Frontend (port 3000)
    ↓
API Gateway (port 8000)
    ↓
Orchestrator (port 8001)
    │
    │  [MistralClient instantiated here — NEVER USED]
    │
    ├──→ Intent Agent (port 8002)  ──── spaCy + keywords
    │        ↓
    ├──→ Schema Agent (port 8003)  ──── static dict + DB cache
    │        ↓
    ├──→ Entity Resolution (port 8004) ── hardcoded maps + BFS
    │        ↓
    ├──→ SQL Agent (port 8005)  ──── template compiler + whitelist
    │        ↓
    ├──→ Validation Agent (port 8006) ── 5 regex + HMAC
    │        ↓
    ├──→ Compliance Agent (port 8011) ── GDPR/PCI/SOX/AML/KYC rules
    │        ↓
    ├──→ Execution Agent (port 8007) ── asyncpg + Redis cache
    │        ↓
    ├──→ Insights Agent (port 8013) ── DISABLED
    │        ├── Statistical Analyzer (numpy)
    │        ├── Context Gatherer (SQL)
    │        ├── Trend ID (hardcoded)
    │        └── MistralIntegrator ──→ Ollama /api/generate  [LLM CALL — DISABLED]
    │        ↓
    └──→ Audit Agent (port 8008) ──── WORM INSERT

    Total LLM calls in production: 0
```

---

## 21. Proposed Optimized Call Graph

### Target Principle
- **LLM:** semantic ambiguity resolution, complex request decomposition, final NL interpretation of verified results
- **Deterministic:** schema retrieval, entity resolution, SQL generation, validation, compliance, execution, statistics, audit

### Simple Request (no ambiguity, clear intent)

```
Frontend → Gateway → Orchestrator
    ↓
Intent Agent (deterministic) → clear intent, confidence > threshold
    ↓
Schema → Entity → SQL → Validation → Compliance → Execution
    ↓
[LLM CALL #1] Final NL interpretation of verified results
    ↓
Audit → Response
```

**1 LLM call:** Final natural-language interpretation of verified, computed results.

### Complex/Ambiguous Request

```
Frontend → Gateway → Orchestrator
    ↓
[LLM CALL #1] Semantic ambiguity resolution + request decomposition
    ↓
Schema → Entity → SQL → Validation → Compliance → Execution
    ↓
[LLM CALL #2] Final NL interpretation of verified results
    ↓
Audit → Response
```

**2 LLM calls max:** One for planning (when needed), one for final interpretation.

### Critical Data/Security Operations

```
Intent → Schema → Entity → SQL → Validation → Compliance → Execution → Audit
```

**0 LLM calls.** Security-critical path remains fully deterministic.

---

## 22. Recommended First Implementation Step

### **BUILD REAL DETERMINISTIC ANALYTICAL FACT PACKAGE FOR INSIGHTS AGENT**

**Rationale:**
- The Insights Agent is the ONLY component with LLM usage, and it is currently disabled
- Before deciding whether to keep, upgrade, or remove the LLM call, we need to know what deterministic analysis can produce
- The current template fallback is 65-70% of LLM output quality — proving we can close this gap deterministically is high-value and low-risk
- This addresses the root cause (insufficient analytical computation) rather than the symptom (relying on LLM to compensate)

### Specific Changes

1. **Remove hardcoded `confidence=0.85`** — compute from data quality signals (completeness, outlier ratio, data freshness)
2. **Make recommendations query-aware** — reference actual tables, columns, values from the result set
3. **Scope context to query** — filter `total_deposits` by the same tables/filters/time range as the user's query
4. **Remove static `top_region`** — only include when region is actually part of the query dimensions
5. **Add multi-column correlation** — analyze relationships between numeric columns in the result set
6. **Add period-over-period comparison** — use actual date columns for trend analysis
7. **Gate Insights LLM call** — only invoke when summary quality would meaningfully differ from template (complex queries with multiple dimensions)

### Files Likely to Change

| File | Change |
|------|--------|
| `services/insights_agent/insights_generator.py` | Real analytical fact computation, query-scoped context |
| `services/insights_agent/statistical_analyzer.py` | Multi-column analysis, correlation detection |
| `services/insights_agent/context_gatherer.py` | Query-scoped context gathering |
| `services/insights_agent/mistral_integrator.py` | Improved fallback templates, remove synthetic values |
| `services/insights_agent/models.py` | Extended Trend/InsightsResponse models |

---

## 23. Exact Files Likely to Change (First Implementation)

1. `services/insights_agent/insights_generator.py` — Core orchestration, remove synthetic values
2. `services/insights_agent/statistical_analyzer.py` — Multi-column analysis
3. `services/insights_agent/context_gatherer.py` — Query-scoped context
4. `services/insights_agent/mistral_integrator.py` — Improved fallback templates
5. `services/insights_agent/models.py` — Extended response models
6. `tests/test_insights_agent.py` — Updated test assertions

---

## 24. GO / NO-GO Recommendation

### GO — Safe to Proceed with First Implementation

**Evidence:**
- ✅ The system is already production-functional with zero LLM calls (Insights Agent disabled)
- ✅ The MistralClient in the orchestrator is confirmed dead code (never called)
- ✅ Security-critical path (SQL generation, validation, compliance, execution) is fully deterministic with no LLM involvement
- ✅ The Insights Agent fallback template is 65-70% equivalent to LLM output
- ✅ Removing synthetic values (hardcoded 12.5% growth, static confidence) is safe and improves data integrity
- ✅ Building real deterministic analysis is lower risk than upgrading LLM quality
- ✅ No security concerns with the proposed changes (only touches insights computation)

**Blockers:** None identified.

**Risk:** LOW — changes are isolated to the Insights Agent, which is already disabled in production.

---

*End of LLM Runtime Usage & Efficiency Audit*
