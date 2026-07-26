# Service Inventory — Banking Intelligence System

> **AUTHORITATIVE** baseline from verified `docker-compose.yml` and source code.
> Last verified: 2026-07-26

---

## EXECUTABLE SERVICES (16 total, including frontend and debug)

From docker-compose.yml:

| # | Docker Compose Name | Container Name | Source Folder | Port | Image | Restart | Status |
|---|---------------------|----------------|---------------|------|-------|---------|--------|
| 1 | frontend | banking_frontend | ./frontend | 3000:80 | custom build | unless-stopped | ACTIVE |
| 2 | api-gateway | banking_api_gateway | ./services/api_gateway | 8000:8000 | custom build | unless-stopped | ACTIVE |
| 3 | orchestrator-agent | banking_orchestrator | ./services/orchestrator | 8001:8001 | python:3.11-slim | unless-stopped | ACTIVE |
| 4 | intent-agent | banking_intent_agent | ./services/intent_agent | 8002:8002 | python:3.11-slim | unless-stopped | ACTIVE |
| 5 | schema-agent | banking_schema_agent | ./services/schema_agent | 8003:8003 | python:3.11-slim | unless-stopped | ACTIVE |
| 6 | entity-resolution-agent | banking_entity_resolution | ./services/entity_resolution_agent | 8004:8004 | python:3.11-slim | unless-stopped | ACTIVE |
| 7 | sql-agent | banking_sql_agent | ./services/sql_agent | 8005:8005 | python:3.11-slim | unless-stopped | ACTIVE |
| 8 | validation-agent | banking_validation_agent | ./services/validation_agent | 8006:8006 | python:3.11-slim | unless-stopped | ACTIVE |
| 9 | execution-agent | banking_execution_agent | ./services/execution_agent | 8007:8007 | python:3.11-slim | unless-stopped | ACTIVE |
| 10 | audit-agent | banking_audit_agent | ./services/audit_agent | 8008:8008 | python:3.11-slim | unless-stopped | ACTIVE |
| 11 | embedding-service | banking_embedding_service | ./services/embedding_service | 8009:8009 | python:3.11-slim | unless-stopped | ACTIVE |
| 12 | secrets-manager | banking_secrets | ./services/secrets_manager | 8010:8010 | python:3.11-slim | unless-stopped | STUB |
| 13 | compliance-agent | banking_compliance_agent | ./services/compliance_agent | 8011:8011 | python:3.11-slim | unless-stopped | ACTIVE |
| 14 | audit-enhancement | banking_audit_enhancement | ./services/audit_enhancement | 8012:8012 | python:3.11-slim | unless-stopped | ACTIVE |
| 15 | insights-agent | banking_insights_agent | ./services/insights_agent | 8013:8013 | python:3.11-slim | unless-stopped | ACTIVE |
| 16 | debug-service | banking_debug_service | ./services/debugging | 8099:8099 | python:3.11-slim | (none) | DEV-ONLY |

## INFRASTRUCTURE SERVICES (4)

| # | Docker Compose Name | Container Name | Image | Port |
|---|---------------------|----------------|-------|------|
| 17 | postgres-main | banking_postgres_main | postgres:16-alpine | 5432:5432 |
| 18 | postgres-audit | banking_postgres_audit | postgres:16-alpine | 5433:5432 |
| 19 | postgres-embeddings | banking_postgres_embeddings | pgvector/pgvector:pg16 | 5434:5432 |
| 20 | redis | banking_redis | redis:7-alpine | 6379:6379 |
| 21 | ollama | banking_ollama | ollama/ollama:latest | 11434:11434 |

**TOTAL: 21 docker-compose services**

## Service Classification

**Pipeline Agents (6 mandatory stages)**:
1. intent-agent (8002) - Intent classification
2. schema-agent (8003) - Schema/table mapping
3. entity-resolution-agent (8004) - Join path resolution
4. sql-agent (8005) - SQL generation
5. validation-agent (8006) - Query validation + signing
6. execution-agent (8007) - Query execution against database

**Orchestrator (1)**:
7. orchestrator-agent (8001) - Coordinates all pipeline agents

**API Gateway (1)**:
8. api-gateway (8000) - Central router, auth, rate limiting

**Post-execution Services (3)**:
9. audit-agent (8008) - Audit log writing
10. compliance-agent (8011) - Compliance rule checking
11. insights-agent (8013) - NL insights generation

**Supporting Services (3)**:
12. embedding-service (8009) - Vector embeddings for semantic search
13. audit-enhancement (8012) - Audit log enrichment
14. secrets-manager (8010) - STUB only, health endpoint only

**Frontend (1)**:
15. frontend (3000) - React SPA

**Dev Tools (1)**:
16. debug-service (8099) - Debug WebSocket relay

## Shared Library (NOT a service)
- services/shared/ - Python modules imported by all services
  - config.py, database.py, errors.py, logger.py, mistral_client.py, models.py, provenance.py, query_signing.py, redis_client.py

## Previously Claimed Non-existent Services

| Claimed Name | Status | Explanation |
|-------------|--------|-------------|
| analytics_engine | DOES NOT EXIST | Port 8002 is intent-agent |
| compliance_monitor | DOES NOT EXIST | Port 8003 is schema-agent |
| document_store | DOES NOT EXIST | No such service |
| notification_service | DOES NOT EXIST | No such service |
| risk_engine | DOES NOT EXIST | No such service |
| semantic_layer | DOES NOT EXIST | Port 8007 is execution-agent |
| report_service | DOES NOT EXIST | No such service |
| branch_network | DOES NOT EXIST | No such service |
| query_engine | DOES NOT EXIST | Port 8010 is secrets-manager (stub) |
| agent_api | DOES NOT EXIST | No such service |

## Database Dependencies

| Service | Database Dependencies | Redis DB |
|---------|----------------------|----------|
| api-gateway | banking_dev, audit_logs | DB 0 |
| orchestrator-agent | banking_dev | DB 1 |
| intent-agent | banking_dev | (none) |
| schema-agent | (none directly) | DB 2 |
| entity-resolution-agent | embeddings | DB 3 |
| sql-agent | (none directly) | DB 4 |
| validation-agent | (none directly) | (none) |
| execution-agent | banking_dev | DB 5 |
| audit-agent | audit_logs | (none) |
| embedding-service | embeddings | (none) |
| compliance-agent | banking_dev | (none) |
| insights-agent | banking_dev | (none) |
| audit-enhancement | banking_dev, audit_logs | (none) |
