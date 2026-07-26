# Architecture Diagram — Banking Intelligence System

> **AUTHORITATIVE** — Based on VERIFIED `docker-compose.yml`.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT (Browser)                            │
│                      React 18 + TypeScript                          │
│                   Port 3000 via Nginx (80)                          │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ HTTP (via nginx reverse proxy)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    API GATEWAY (port 8000)                           │
│              banking_api_gateway container                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ JWT Validation │ Rate Limiting │ RBAC │ Audit Middleware     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│  Database: banking_dev + audit_logs │ Redis DB 0                    │
└────────┬────────────┬────────────┬────────────┬────────────────────┘
         │            │            │            │
         ▼            ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Orchestrator │ │  Compliance  │ │    Audit     │ │   Insights   │
│  (port 8001)  │ │  Agent       │ │   Agent      │ │   Agent      │
│               │ │  (port 8011) │ │  (port 8008) │ │  (port 8013) │
└──────┬───────┘ └──────────────┘ └──────────────┘ └──────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    QUERY PIPELINE (6 stages)                         │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  │ Intent   │→│ Schema   │→│ Entity   │→│ SQL      │→│Validation│→│Execution │
│  │ Agent    │ │ Agent    │ │Resolution│ │ Agent    │ │ Agent    │ │ Agent    │
│  │ :8002    │ │ :8003    │ │ Agent    │ │ :8005    │ │ :8006    │ │ :8007    │
│  │          │ │          │ │ :8004    │ │          │ │          │ │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
└─────────────────────────────────────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────────┐
│ PostgreSQL   │ │ PostgreSQL   │ │ PostgreSQL                       │
│ Main (5432)  │ │ Audit (5433) │ │ Embeddings (5434)               │
│ banking_dev  │ │ audit_logs   │ │ embeddings (pgvector)            │
│ 74 tables    │ │ 1 table      │ │ 3 tables                         │
└──────────────┘ └──────────────┘ └──────────────────────────────────┘
         │
         ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Redis (6379) │ │ Ollama       │ │ Embedding    │
│ DB 0-5       │ │ (11434)      │ │ Service      │
│              │ │ Local LLM    │ │ (8009)       │
└──────────────┘ └──────────────┘ └──────────────┘
```

---

## Service Categories (VERIFIED)

### Pipeline Agents (6 mandatory)

| Service | Port | Container | Status |
|---------|------|-----------|--------|
| intent-agent | 8002 | banking_intent_agent | ACTIVE |
| schema-agent | 8003 | banking_schema_agent | ACTIVE |
| entity-resolution-agent | 8004 | banking_entity_resolution_agent | ACTIVE |
| sql-agent | 8005 | banking_sql_agent | ACTIVE |
| validation-agent | 8006 | banking_validation_agent | ACTIVE |
| execution-agent | 8007 | banking_execution_agent | ACTIVE |

### Orchestrator (1)

| Service | Port | Container | Status |
|---------|------|-----------|--------|
| orchestrator-agent | 8001 | banking_orchestrator_agent | ACTIVE |

### API Gateway (1)

| Service | Port | Container | Status |
|---------|------|-----------|--------|
| api-gateway | 8000 | banking_api_gateway | ACTIVE |

### Post-execution Services (3)

| Service | Port | Container | Status |
|---------|------|-----------|--------|
| audit-agent | 8008 | banking_audit_agent | ACTIVE |
| compliance-agent | 8011 | banking_compliance_agent | ACTIVE |
| insights-agent | 8013 | banking_insights_agent | ACTIVE |

### Supporting Services (3)

| Service | Port | Container | Status |
|---------|------|-----------|--------|
| embedding-service | 8009 | banking_embedding_service | ACTIVE |
| audit-enhancement | 8012 | banking_audit_enhancement | ACTIVE |
| secrets-manager | 8010 | banking_secrets_manager | STUB (health endpoint only) |

### Frontend (1)

| Service | Port | Container | Status |
|---------|------|-----------|--------|
| frontend | 3000 | banking_frontend | ACTIVE |

### Dev Tools (1)

| Service | Port | Container | Status |
|---------|------|-----------|--------|
| debug-service | 8099 | banking_debug_service | DEV-ONLY |

### Infrastructure (5)

| Service | Port | Container | Status |
|---------|------|-----------|--------|
| postgres-main | 5432 | banking_postgres_main | ACTIVE |
| postgres-audit | 5433 | banking_postgres_audit | ACTIVE |
| postgres-embeddings | 5434 | banking_postgres_embeddings | ACTIVE |
| redis | 6379 | banking_redis | ACTIVE |
| ollama | 11434 | banking_ollama | ACTIVE |

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SECURITY LAYERS                             │
│                                                                     │
│  Layer 1: AUTHENTICATION                                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  JWT HS256 symmetric (auth.py)                              │   │
│  │  bcrypt password hashing                                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Layer 2: AUTHORIZATION (RBAC)                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  4 roles + database-backed permissions                      │   │
│  │  Role        │ Row Filter      │ Columns       │ PII Mask  │   │
│  │  ────────────┼─────────────────┼───────────────┼────────── │   │
│  │  compliance  │ None (all)      │ All columns   │ Disabled  │   │
│  │  analyst     │ None (all)      │ Curated       │ Enabled   │   │
│  │  manager     │ None (simplified)│ Curated+mgmt │ Enabled   │   │
│  │  customer    │ Own rows only   │ Limited       │ Enabled   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Layer 3: RATE LIMITING                                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  100 req/min per IP                                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Layer 4: QUERY SECURITY                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  5-Check SQL Validation → HMAC-SHA256 Query Signing         │   │
│  │  Tampered query = signature mismatch = REJECTED             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Layer 5: AUDIT                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Immutable audit log (RULE-protected)                       │   │
│  │  Every request logged: user, role, query, result, time, IP  │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Keycloak Migration Path

| Aspect | Current | Target |
|--------|---------|--------|
| Algorithm | HS256 symmetric | RS256 asymmetric |
| Key Management | JWT_SECRET_KEY env var | JWKS endpoint |
| Token Issuance | Internal (auth.py) | Keycloak server |
| Impacted Files | auth.py, client.ts | auth.py, client.ts, all protected routes |

---

## Port Map

```
SERVICE                    CONTAINER                    HOST PORT
─────────────────────────  ────────────────────────────  ─────────
Frontend (Nginx)           banking_frontend              3000 → 80
API Gateway                banking_api_gateway           8000 → 8000
Orchestrator               banking_orchestrator_agent    8001 → 8001
Intent Agent               banking_intent_agent          8002 → 8002
Schema Agent               banking_schema_agent          8003 → 8003
Entity Resolution          banking_entity_resolution_agent 8004 → 8004
SQL Agent                  banking_sql_agent             8005 → 8005
Validation Agent           banking_validation_agent      8006 → 8006
Execution Agent            banking_execution_agent       8007 → 8007
Audit Agent                banking_audit_agent           8008 → 8008
Embedding Service          banking_embedding_service     8009 → 8009
Secrets Manager            banking_secrets_manager       8010 → 8010
Compliance Agent           banking_compliance_agent      8011 → 8011
Audit Enhancement          banking_audit_enhancement     8012 → 8012
Insights Agent             banking_insights_agent        8013 → 8013
Debug Service              banking_debug_service         8099 → 8099
PostgreSQL Main            banking_postgres_main         5432 → 5432
PostgreSQL Audit           banking_postgres_audit        5433 → 5432
PostgreSQL Embeddings      banking_postgres_embeddings   5434 → 5432
Redis                      banking_redis                6379 → 6379
Ollama                     banking_ollama               11434 → 11434
```
