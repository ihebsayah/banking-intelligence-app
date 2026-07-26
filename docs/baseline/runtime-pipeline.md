# Runtime Query Pipeline

This document traces the exact runtime query pipeline based on verified source code.

**Evidence sources:**
- `services/api_gateway/routes.py` lines 568-652: `submit_query` handler
- `services/orchestrator/main.py` lines 71-83: `process_query` endpoint
- `services/orchestrator/orchestrator_agent.py`: full pipeline logic

---

## Pipeline Overview

```
POST /query
    │
    ▼
┌─────────────┐
│ API Gateway  │ (routes.py:568-652)
│ Port 8000    │
└──────┬──────┘
       │ http://orchestrator-agent:8001/process_query
       ▼
┌─────────────────┐
│  Orchestrator    │ (orchestrator_agent.py)
│  Port 8001       │
└──────┬──────────┘
       │
       │ sequential stage calls
       ▼
```

---

## Exact Pipeline (7 mandatory stages + 2 post-execution stages)

### 1. API Gateway (`routes.py:568-652`)

- `POST /query` receives `QueryRequest(query: str, format: str = "json")`
- Validates input (non-empty, no markup, no template syntax)
- Forwards to `http://orchestrator-agent:8001/process_query` with `{query, user_role, user_id, format}`
- Timeout: **300s**
- On timeout: returns `504 PIPELINE_TIMEOUT`
- On error: returns `503 PIPELINE_UNAVAILABLE`

### 2. Orchestrator (`orchestrator_agent.py`)

- Receives `process_query` POST at `/process_query`
- Calls: Intent Agent → Schema Agent → Entity Resolution Agent → SQL Agent → Validation Agent → Compliance Agent → Execution Agent → Insights Agent → Audit Agent

### Stage 1: Intent Agent

| Field | Value |
|-------|-------|
| Caller | Orchestrator |
| Callee | `http://intent-agent:8002/process_intent` |
| Request | `{"query": user_query}` |
| Timeout | 10s |
| Feature flag | `SEMANTIC_LAYER_ENABLED` (affects intent depth) |

**Intent gate:** rejects if `supported_capability=false`, `risk_level=adversarial/suspicious`, or `confidence < INTENT_CONFIDENCE_THRESHOLD` (0.31).

### Stage 2: Schema Agent

| Field | Value |
|-------|-------|
| Caller | Orchestrator |
| Callee | `http://schema-agent:8003/map_schema` |
| Request | `{"intent_categories": [primary + secondary categories]}` |
| Timeout | 10s |
| Feature flag | `SEMANTIC_LAYER_ENABLED` |
| Dependency | `embedding-service:8009` (`EMBEDDING_SERVICE_URL`) |

### Stage 3: Entity Resolution Agent

| Field | Value |
|-------|-------|
| Caller | Orchestrator |
| Callee | `http://entity-resolution-agent:8004/resolve_entities` |
| Request | `{"primary_entity": mapped_entity, "tables": schema_data.tables}` |
| Timeout | 10s |
| Dependency | `embedding-service:8009`, `postgres-embeddings` |

### Stage 4: SQL Generation Agent

| Field | Value |
|-------|-------|
| Caller | Orchestrator |
| Callee | `http://sql-agent:8005/generate_sql` |
| Request | `{intent, primary_entity, limit, tables, join_paths, filters, group_by, order_by, columns, detected_kpis}` |
| Timeout | 10s |

- Contains hardcoded preset queries (17 presets)
- Feature flags: `STRUCTURED_QUERY_PLAN_ENABLED`, `DETERMINISTIC_SQL_COMPILER_ENABLED`, `SQL_REPAIR_ENABLED`, `SEMANTIC_LAYER_ENABLED`

### Stage 5: Validation Agent

| Field | Value |
|-------|-------|
| Caller | Orchestrator |
| Callee | `http://validation-agent:8006/validate_query` |
| Request | `{sql, parameters, user_role, upstream_semantic_warnings, request_id, nonce}` |
| Timeout | 10s |

- Signs the query (query signing)
- Blocks if `safe=false`

### Stage 5.5: Compliance Agent (Phase 2)

| Field | Value |
|-------|-------|
| Caller | Orchestrator |
| Callee | `http://compliance-agent:8011/check_compliance` |
| Request | `{user_id, user_role, query_intent, tables, columns}` |
| Timeout | 10s |
| Feature flag | `ENABLE_COMPLIANCE_AGENT` (default: `True`) |

- Blocks if critical/high severity violations found
- Failure behavior: defaults to `COMPLIANT` (non-fatal)

### Stage 6: Execution Agent

| Field | Value |
|-------|-------|
| Caller | Orchestrator |
| Callee | `http://execution-agent:8007/execute_query` |
| Request | `{sql, parameters, signature, user_role, user_id}` |
| Timeout | 30s |

- Executes against `banking_dev` database
- Sends audit log to `audit-agent:8008`

### Stage 6.5: Insights Agent (Phase 2, post-execution)

| Field | Value |
|-------|-------|
| Caller | Orchestrator |
| Callee | `http://insights-agent:8013/generate_insights` |
| Request | `{query_intent, query_text, results, metadata}` |
| Timeout | 300s |
| Feature flag | `ENABLE_INSIGHTS_AGENT` (default: `True`) |

- Failure behavior: non-fatal (log warning, continue)
- Uses Ollama LLM (`tinyllama`)

### Stage 7: Audit Agent (Phase 2, post-execution)

| Field | Value |
|-------|-------|
| Caller | Orchestrator |
| Callee | `http://audit-agent:8008/log_access` |
| Request | `{user_role, action: "nl_query", status, endpoint, http_method, execution_time_ms, metadata}` |
| Timeout | 10s |

- Writes to `audit_logs.audit_log` table

---

## Service Dependency Diagram

```
                          ┌──────────────────┐
                          │    Frontend /     │
                          │    Client App     │
                          └────────┬─────────┘
                                   │ POST /query
                                   ▼
                          ┌──────────────────┐
                          │   API Gateway     │
                          │   :8000           │
                          └────────┬─────────┘
                                   │ :8001
                                   ▼
                          ┌──────────────────┐
                          │   Orchestrator    │
                          │   :8001           │
                          └────────┬─────────┘
                                   │
               ┌───────────────────┼───────────────────┐
               │                   │                   │
               ▼                   ▼                   ▼
     ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
     │ Intent Agent  │   │ Schema Agent │   │ Entity Resolution│
     │ :8002         │   │ :8003        │   │ Agent :8004      │
     └──────────────┘   └──────┬───────┘   └────────┬─────────┘
                               │                    │
                               ▼                    ▼
                     ┌──────────────────┐  ┌──────────────────┐
                     │ Embedding Service │  │ postgres-        │
                     │ :8009            │  │ embeddings       │
                     └──────────────────┘  └──────────────────┘
               │
               ▼
     ┌──────────────────┐
     │ SQL Agent :8005   │
     └────────┬─────────┘
              ▼
     ┌──────────────────┐
     │ Validation Agent  │
     │ :8006            │
     └────────┬─────────┘
              ▼
     ┌──────────────────┐
     │ Compliance Agent  │  (if ENABLE_COMPLIANCE_AGENT=True)
     │ :8011            │
     └────────┬─────────┘
              ▼
     ┌──────────────────┐
     │ Execution Agent   │
     │ :8007            │──────────────┐
     └────────┬─────────┘              │
              │                        ▼
              │              ┌──────────────────┐
              │              │  banking_dev DB   │
              │              └──────────────────┘
              │
    ┌─────────┴──────────┐
    │                    │
    ▼                    ▼
┌──────────────┐  ┌──────────────────┐
│ Insights Agent│  │  Audit Agent     │
│ :8013         │  │  :8008           │
│ (post-exec)   │  │  (post-exec)     │
└──────────────┘  └────────┬─────────┘
                           ▼
                 ┌──────────────────┐
                 │ audit_logs.       │
                 │ audit_log table   │
                 └──────────────────┘
```

---

## Classification

| Category | Stages |
|----------|--------|
| **Pipeline stages (always called)** | Intent, Schema, Entity Resolution, SQL, Validation, Execution |
| **Pipeline stages (conditionally called)** | Compliance (if `ENABLE_COMPLIANCE_AGENT=True`, default `True`) |
| **Post-execution (non-fatal)** | Insights (if `ENABLE_INSIGHTS_AGENT=True`, default `True`), Audit (always) |

> **No feature flag disables any of the 7 core pipeline stages.**

---

## Summary of External Dependencies

| Service | Port | Used By | Purpose |
|---------|------|---------|---------|
| `orchestrator-agent` | 8001 | API Gateway | Pipeline coordination |
| `intent-agent` | 8002 | Orchestrator | Query intent classification |
| `schema-agent` | 8003 | Orchestrator | Schema mapping |
| `entity-resolution-agent` | 8004 | Orchestrator | Entity/table resolution |
| `sql-agent` | 8005 | Orchestrator | SQL generation |
| `validation-agent` | 8006 | Orchestrator | SQL validation + signing |
| `execution-agent` | 8007 | Orchestrator | SQL execution against DB |
| `audit-agent` | 8008 | Orchestrator, Execution Agent | Audit logging |
| `embedding-service` | 8009 | Schema Agent, Entity Resolution | Vector embeddings |
| `compliance-agent` | 8011 | Orchestrator | Data access compliance |
| `insights-agent` | 8013 | Orchestrator | Post-query insights (LLM) |

---

## Timeout Budget (worst case)

```
API Gateway (300s total budget)
  └─ Orchestrator serial chain:
       Intent:           10s
       Schema:           10s
       Entity Resolution: 10s
       SQL Generation:    10s
       Validation:        10s
       Compliance:        10s
       Execution:         30s
       ─────────────────────
       Core total:        90s
       Insights:         300s (post-execution, non-fatal)
       Audit:             10s (post-execution)
       ─────────────────────
       Worst case total: 400s (but Insights is non-fatal)
```

The 300s API Gateway timeout covers the core pipeline (90s worst case) with headroom. Insights at 300s runs post-execution and is non-fatal, so it does not block the user response.
