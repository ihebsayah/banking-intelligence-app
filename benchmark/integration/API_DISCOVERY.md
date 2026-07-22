# API Discovery — Integration Benchmark

## Production Query Endpoint

```
POST http://localhost:8000/query
```

Requires JWT Bearer token.

## Authentication

### Step 1: Login

```
POST http://localhost:8000/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin_001&password=<password>
```

Response:
```json
{
  "access_token": "<jwt>",
  "user_id": "admin_001",
  "user_role": "admin",
  "expires_in": 3600
}
```

### Step 2: Use token

```
POST http://localhost:8000/query
Authorization: Bearer <access_token>
Content-Type: application/json

{"query": "...", "format": "json"}
```

## Request Payload

| Field | Type | Required | Default |
|-------|------|----------|---------|
| query | string | yes | — |
| format | string | no | "json" |

## Response Payload

```json
{
  "status": "success|error",
  "results": [...],
  "metadata": {"row_count": N, ...},
  "pipeline_steps": [
    {"agent": "intent", "status": "success", "response": {...}},
    {"agent": "schema", "status": "success", "response": {...}},
    {"agent": "entity_resolution", "status": "success", "response": {...}},
    {"agent": "sql", "status": "success", "response": {...}},
    {"agent": "validation", "status": "success", "response": {...}},
    {"agent": "compliance", "status": "success", "response": {...}},
    {"agent": "execution", "status": "success", "response": {"rows_returned": N}},
    {"agent": "insights", "status": "success", "response": {...}}
  ],
  "insights": {...},
  "message": null,
  "error": null,
  "request_id": "uuid",
  "debug_url": null
}
```

## Pipeline Steps (in order)

| # | Agent | Internal Endpoint | Port | Can Block? |
|---|-------|-------------------|------|------------|
| 1 | intent | POST /process_intent | 8002 | Yes (semantic_planning) |
| 2 | schema | POST /map_schema | 8003 | Yes (no schema match) |
| 3 | entity_resolution | POST /resolve_entities | 8004 | No (best-effort) |
| 4 | sql | POST /generate_sql | 8005 | Yes (generation failure) |
| 5 | validation | POST /validate_query | 8006 | Yes (unsafe SQL) |
| 5.5 | compliance | POST /check_compliance | 8011 | Yes (critical violations) |
| 6 | execution | POST /execute_query | 8007 | Yes (SQL errors) |
| 6.5 | insights | POST /generate_insights | 8013 | No (non-fatal) |
| 7 | audit | POST /log_access | 8008 | No (fire-and-forget) |

## Services Required

All 21 Docker Compose services must be running:
- api-gateway (8000), orchestrator (8001), intent (8002), schema (8003)
- entity-resolution (8004), sql (8005), validation (8006), execution (8007)
- audit (8008), embedding (8009), compliance (8011), insights (8013)
- postgres-main (5432), postgres-audit (5433), postgres-embeddings (5434)
- redis (6379), ollama (11434), frontend (3000), debug (8099)
- secrets-manager (8010), audit-enhancement (8012)

## Known Users

| User ID | Role | Password |
|---------|------|----------|
| admin_001 | admin | (same bcrypt hash as all users) |
| analyst_001 | analyst | (same bcrypt hash) |
| compliance_001 | compliance | (same bcrypt hash) |

## Architecture

```
Client → POST /query → API Gateway (8000, JWT auth)
  → Orchestrator (8001, httpx)
    → Intent Agent (8002)
    → Schema Agent (8003)
    → Entity Resolution (8004)
    → SQL Agent (8005)
    → Validation Agent (8006)
    → Compliance Agent (8011)
    → Execution Agent (8007)
    → Insights Agent (8013)
    → Audit Agent (8008)
  ← HTTP Response
```

All inter-agent communication is HTTP (httpx). No direct Python imports between services.
