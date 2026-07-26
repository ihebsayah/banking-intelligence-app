# Config Inventory — Banking Intelligence System

> **Auto-generated baseline** — captures every configuration surface: Docker
> Compose, shared Python settings, `.env` files, and Keycloak migration notes.
> Edit only via code; regenerate this doc when config changes.

---

## Docker Compose Services

Source: `docker-compose.yml`

| Service | Image / Build | Ports | Volumes | Env Vars |
|---------|--------------|-------|---------|----------|
| **frontend** | build `./frontend` | 3000:80 | — | — (served by nginx) |
| **api-gateway** | build `./services/api_gateway` | 8000:8000 | `./services/api_gateway:/app`, `./services/shared:/app/shared`, `./init:/app/init` | `DATABASE_URL`, `AUDIT_DATABASE_URL`, `REDIS_URL`, `AUDIT_AGENT_URL`, `JWT_SECRET_KEY`, `LOG_LEVEL`, `SEMANTIC_LAYER_ENABLED` |
| **orchestrator-agent** | `python:3.11-slim` | 8001:8001 | `./services/orchestrator:/app`, `./services/shared:/app/shared`, `./services/debugging:/app/debugging` | `MISTRAL_API_URL`, `MISTRAL_MODEL`, `ORCHESTRATOR_LLM`, `DATABASE_URL`, `REDIS_URL`, `INTENT_AGENT_URL`, `SCHEMA_AGENT_URL`, `ENTITY_RESOLUTION_AGENT_URL`, `SQL_AGENT_URL`, `VALIDATION_AGENT_URL`, `EXECUTION_AGENT_URL`, `AUDIT_AGENT_URL`, `INSIGHTS_AGENT_URL`, `COMPLIANCE_AGENT_URL`, `QUERY_SIGNING_KEY`, `QUERY_SIGNATURE_MAX_AGE_SECONDS`, `LOG_LEVEL`, `SEMANTIC_LAYER_ENABLED` |
| **intent-agent** | `python:3.11-slim` | 8002:8002 | `./services/intent_agent:/app`, `./services/shared:/app/shared` | `DATABASE_URL`, `LOG_LEVEL`, `SEMANTIC_LAYER_ENABLED` |
| **schema-agent** | `python:3.11-slim` | 8003:8003 | `./services/schema_agent:/app`, `./services/shared:/app/shared` | `EMBEDDING_SERVICE_URL`, `REDIS_URL`, `LOG_LEVEL`, `SEMANTIC_LAYER_ENABLED` |
| **entity-resolution-agent** | `python:3.11-slim` | 8004:8004 | `./services/entity_resolution_agent:/app`, `./services/shared:/app/shared` | `EMBEDDING_SERVICE_URL`, `POSTGRES_EMBEDDINGS_URL`, `REDIS_URL`, `LOG_LEVEL`, `SEMANTIC_LAYER_ENABLED` |
| **sql-agent** | `python:3.11-slim` | 8005:8005 | `./services/sql_agent:/app`, `./services/shared:/app/shared` | `REDIS_URL`, `LOG_LEVEL`, `SEMANTIC_LAYER_ENABLED` |
| **validation-agent** | `python:3.11-slim` | 8006:8006 | `./services/validation_agent:/app`, `./services/shared:/app/shared` | `QUERY_SIGNING_KEY`, `QUERY_SIGNATURE_MAX_AGE_SECONDS`, `LOG_LEVEL`, `SEMANTIC_LAYER_ENABLED` |
| **execution-agent** | `python:3.11-slim` | 8007:8007 | `./services/execution_agent:/app`, `./services/shared:/app/shared` | `DATABASE_URL`, `REDIS_URL`, `QUERY_SIGNING_KEY`, `QUERY_SIGNATURE_MAX_AGE_SECONDS`, `AUDIT_SERVICE_URL`, `LOG_LEVEL` |
| **audit-agent** | `python:3.11-slim` | 8008:8008 | `./services/audit_agent:/app`, `./services/shared:/app/shared` | `AUDIT_DATABASE_URL`, `LOG_LEVEL` |
| **embedding-service** | `python:3.11-slim` | 8009:8009 | `./services/embedding_service:/app`, `./services/shared:/app/shared` | `POSTGRES_EMBEDDINGS_URL`, `LOG_LEVEL` |
| **secrets-manager** | `python:3.11-slim` | 8010:8010 | `./services/secrets_manager:/app`, `banking_secrets_volume:/secrets` | `LOG_LEVEL` |
| **compliance-agent** | `python:3.11-slim` | 8011:8011 | `./services/compliance_agent:/app` | `DATABASE_URL`, `LOG_LEVEL` |
| **audit-enhancement** | `python:3.11-slim` | 8012:8012 | `./services/audit_enhancement:/app` | `DATABASE_URL`, `AUDIT_DATABASE_URL`, `LOG_LEVEL` |
| **insights-agent** | `python:3.11-slim` | 8013:8013 | `./services/insights_agent:/app` | `DATABASE_URL`, `MISTRAL_API_URL`, `MISTRAL_MODEL`, `LOG_LEVEL` |
| **debug-service** | `python:3.11-slim` | 8099:8099 | `./services/debugging:/app` | `LOG_LEVEL`, `IS_DEBUG_SERVICE` |
| **postgres-main** | `postgres:16-alpine` | 5432:5432 | `postgres_main_data`, 8 init SQL scripts | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` |
| **postgres-audit** | `postgres:16-alpine` | 5433:5432 | `postgres_audit_data`, `postgres-audit-init.sql` | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` |
| **postgres-embeddings** | `pgvector/pgvector:pg16` | 5434:5432 | `postgres_embeddings_data`, `postgres-embeddings-init.sql` | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` |
| **redis** | `redis:7-alpine` | 6379:6379 | `redis_data` | — |
| **ollama** | `ollama/ollama:latest` | 11434:11434 | `ollama_data` | `OLLAMA_HOST` |

### Volumes

| Volume | Purpose |
|--------|---------|
| `postgres_main_data` | Main banking DB persistence |
| `postgres_audit_data` | Audit log DB persistence |
| `postgres_embeddings_data` | pgvector embeddings DB persistence |
| `redis_data` | Redis AOF persistence |
| `ollama_data` | LLM model cache |
| `banking_secrets_volume` | Secrets manager runtime data |

### Network

| Network | Driver |
|---------|--------|
| `banking-network` | bridge |

---

## Environment Variables — Root `.env`

Source: `.env.example` / `.env`

### Database Credentials

| Variable | Default (`.env.example`) | Current (`.env`) | Description |
|----------|--------------------------|-------------------|-------------|
| `POSTGRES_MAIN_USER` | `banking_user` | `banking_user` | Main DB user |
| `POSTGRES_MAIN_PASSWORD` | `CHANGE_ME_MAIN` | `securepass123` | Main DB password |
| `POSTGRES_MAIN_DB` | `banking_dev` | *(not set — uses default)* | Main DB name |
| `POSTGRES_AUDIT_USER` | `audit_user` | `audit_user` | Audit DB user |
| `POSTGRES_AUDIT_PASSWORD` | `CHANGE_ME_AUDIT` | `securepass123` | Audit DB password |
| `POSTGRES_AUDIT_DB` | `audit_logs` | *(not set — uses default)* | Audit DB name |
| `POSTGRES_EMBEDDINGS_USER` | `embedding_user` | `embedding_user` | Embeddings DB user |
| `POSTGRES_EMBEDDINGS_PASSWORD` | `CHANGE_ME_EMBEDDINGS` | `securepass123` | Embeddings DB password |
| `POSTGRES_EMBEDDINGS_DB` | `embeddings` | *(not set — uses default)* | Embeddings DB name |

### Derived Database URLs

| Variable | Value (resolved from env) |
|----------|---------------------------|
| `DATABASE_URL` | `postgresql://${POSTGRES_MAIN_USER}:${POSTGRES_MAIN_PASSWORD}@postgres-main:5432/${POSTGRES_MAIN_DB}` |
| `AUDIT_DATABASE_URL` | `postgresql://${POSTGRES_AUDIT_USER}:${POSTGRES_AUDIT_PASSWORD}@postgres-audit:5432/${POSTGRES_AUDIT_DB}` |
| `POSTGRES_EMBEDDINGS_URL` | `postgresql://${POSTGRES_EMBEDDINGS_USER}:${POSTGRES_EMBEDDINGS_PASSWORD}@postgres-embeddings:5432/${POSTGRES_EMBEDDINGS_DB}` |

### LLM / Ollama

| Variable | Default (`.env.example`) | Current (`.env`) | Description |
|----------|--------------------------|-------------------|-------------|
| `MISTRAL_API_URL` | `http://ollama:11434` | `http://host.docker.internal:11434` | Ollama API endpoint |
| `MISTRAL_MODEL` | `mistral` | `mistral` | Model name |
| `ORCHESTRATOR_LLM` | `mistral` | `mistral` | LLM used by orchestrator |
| `LLM_TIMEOUT` | `120` | `120` | Request timeout (seconds) |
| `LLM_MAX_TOKENS` | `1000` | `1000` | Max completion tokens |
| `LLM_TEMPERATURE` | `0.7` | `0.7` | Sampling temperature |

### JWT / Auth

| Variable | Default (`.env.example`) | Current (`.env`) | Description |
|----------|--------------------------|-------------------|-------------|
| `JWT_SECRET_KEY` | `CHANGE_ME_USE_256BIT_RANDOM_VALUE` | `change-this-in-production-do-not-use-in-prod` | HMAC signing secret |
| `JWT_ALGORITHM` | `HS256` | *(not set — uses default)* | JWT algorithm |
| `JWT_EXPIRE_MINUTES` | `480` | *(not set — uses default)* | Token TTL (8 hours) |

### Query Signing

| Variable | Default (`.env.example`) | Current (`.env`) | Description |
|----------|--------------------------|-------------------|-------------|
| `QUERY_SIGNING_KEY` | `replace-with-a-long-random-secret` | `replace-with-a-long-random-secret` | Inter-agent query HMAC key |
| `QUERY_SIGNATURE_MAX_AGE_SECONDS` | `60` | `60` | Signature freshness window |

### Redis

| Variable | Default (`.env.example`) | Current (`.env`) | Description |
|----------|--------------------------|-------------------|-------------|
| `REDIS_HOST` | `redis` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | `6379` | Redis port |
| `REDIS_URL` | `redis://redis:6379/0` | *(not set — uses default)* | Full Redis URL |

### Internal Service URLs

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `API_GATEWAY_URL` | `http://api-gateway:8000` | API Gateway |
| `ORCHESTRATOR_URL` | `http://orchestrator-agent:8001` | Orchestrator Agent |
| `INTENT_AGENT_URL` | `http://intent-agent:8002` | Intent Agent |
| `SCHEMA_AGENT_URL` | `http://schema-agent:8003` | Schema Agent |
| `ENTITY_RESOLUTION_AGENT_URL` | `http://entity-resolution-agent:8004` | Entity Resolution Agent |
| `SQL_AGENT_URL` | `http://sql-agent:8005` | SQL Agent |
| `VALIDATION_AGENT_URL` | `http://validation-agent:8006` | Validation Agent |
| `EXECUTION_AGENT_URL` | `http://execution-agent:8007` | Execution Agent |
| `AUDIT_AGENT_URL` | `http://audit-agent:8008` | Audit Agent |
| `EMBEDDING_SERVICE_URL` | `http://embedding-service:8009` | Embedding Service |
| `SECRETS_MANAGER_URL` | `http://secrets-manager:8010` | Secrets Manager |
| `COMPLIANCE_AGENT_URL` | `http://compliance-agent:8011` | Compliance Agent |
| `AUDIT_ENHANCEMENT_URL` | `http://audit-enhancement:8012` | Audit Enhancement |
| `INSIGHTS_AGENT_URL` | `http://insights-agent:8013` | Insights Agent |
| `DEBUG_SERVICE_URL` | `http://debug-service:8099` | Debug Service |

### Logging & Feature Flags

| Variable | Default (`.env.example`) | Current (`.env`) | Description |
|----------|--------------------------|-------------------|-------------|
| `LOG_LEVEL` | `INFO` | `INFO` | Global log level |
| `ENABLE_INSIGHTS_AGENT` | `false` | `false` | Insights agent feature flag |
| `ENABLE_ADVANCED_ML` | `false` | `false` | Advanced ML feature flag |
| `ENABLE_CACHING` | `true` | `true` | Redis caching toggle |

---

## Python Config — `services/shared/config.py`

Source: `services/shared/config.py` (pydantic-settings `BaseSettings`)

All services import `get_settings()` → singleton `Settings` instance.
Settings are loaded from env vars with the defaults below.

### Database URLs

| Setting | Default | Description |
|---------|---------|-------------|
| `DATABASE_URL` | `postgresql://banking_user:securepass123@localhost:5432/banking_dev` | Main banking PostgreSQL |
| `AUDIT_DATABASE_URL` | `postgresql://audit_user:securepass123@localhost:5433/audit_logs` | Audit PostgreSQL |
| `EMBEDDINGS_DATABASE_URL` | `postgresql://embedding_user:securepass123@localhost:5434/embeddings` | pgvector PostgreSQL |

### Redis

| Setting | Default | Description |
|---------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |

### LLM Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `MISTRAL_API_URL` | `http://localhost:11434` | Ollama API endpoint |
| `MISTRAL_MODEL` | `mistral` | Model name |
| `ORCHESTRATOR_LLM` | `mistral` | Orchestrator LLM model |
| `LLM_TIMEOUT` | `120` | Request timeout (seconds) |
| `LLM_MAX_TOKENS` | `1000` | Max completion tokens |
| `LLM_TEMPERATURE` | `0.7` | Sampling temperature |

### JWT Auth

| Setting | Default | Description |
|---------|---------|-------------|
| `JWT_SECRET_KEY` | `change-this-in-production-do-not-use-in-prod` | HMAC signing secret |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRE_MINUTES` | `480` | Token TTL in minutes (8 hours) |

### Service URLs

| Setting | Default | Description |
|---------|---------|-------------|
| `AUDIT_AGENT_URL` | `http://localhost:8008` | Audit Agent |
| `ORCHESTRATOR_URL` | `http://localhost:8001` | Orchestrator Agent |
| `INTENT_AGENT_URL` | `http://localhost:8002` | Intent Agent |
| `SCHEMA_AGENT_URL` | `http://localhost:8003` | Schema Agent |
| `ENTITY_RESOLUTION_AGENT_URL` | `http://localhost:8004` | Entity Resolution Agent |
| `SQL_AGENT_URL` | `http://localhost:8005` | SQL Agent |
| `VALIDATION_AGENT_URL` | `http://localhost:8006` | Validation Agent |
| `EXECUTION_AGENT_URL` | `http://localhost:8007` | Execution Agent |
| `EMBEDDING_SERVICE_URL` | `http://localhost:8009` | Embedding Service |
| `INSIGHTS_AGENT_URL` | `http://localhost:8013` | Insights Agent (Phase 2) |
| `COMPLIANCE_AGENT_URL` | `http://localhost:8011` | Compliance Agent (Phase 2) |
| `AUDIT_ENHANCEMENT_URL` | `http://localhost:8012` | Audit Enhancement (Phase 2) |

### Logging

| Setting | Default | Description |
|---------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Global log level |

### Feature Flags & Tuning

| Setting | Default | Description |
|---------|---------|-------------|
| `ENABLE_INSIGHTS_AGENT` | `true` | Enable insights agent |
| `ENABLE_COMPLIANCE_AGENT` | `true` | Enable compliance agent |
| `ENABLE_CACHING` | `true` | Enable Redis caching |
| `DEV_MODE` | `true` | Enable dev fallback/mocks |
| `SEMANTIC_LAYER_ENABLED` | `false` | Semantic layer routing |
| `STRUCTURED_QUERY_PLAN_ENABLED` | `false` | Structured query planning |
| `DETERMINISTIC_SQL_COMPILER_ENABLED` | `false` | Deterministic SQL compilation |
| `SQL_REPAIR_ENABLED` | `false` | Auto-repair broken SQL |
| `RESULT_VERIFICATION_ENABLED` | `false` | Verify query results |
| `CONVERSATION_CONTEXT_ENABLED` | `false` | Multi-turn conversation context |
| `LLM_SQL_FALLBACK_ENABLED` | `false` | Fallback to LLM for SQL generation |
| `EXPLAIN_COST_CHECK_ENABLED` | `false` | Post-execution EXPLAIN cost check |
| `BENCHMARK_MODE` | `false` | Benchmark mode toggle |
| `INTENT_CONFIDENCE_THRESHOLD` | `0.31` | Below this, intent gate rejects query |
| `SEMANTIC_MAX_CANDIDATE_TABLES` | `20` | Max candidate tables for semantic matching |
| `SEMANTIC_MAX_SELECTED_TABLES` | `6` | Max tables selected by semantic layer |
| `SEMANTIC_MAX_TOTAL_TABLES` | `10` | Max total tables in query |
| `MAX_JOIN_PATH_DEPTH` | `3` | Max join path depth |
| `MAX_SQL_REPAIR_ATTEMPTS` | `2` | Max SQL repair retries |

---

## Frontend Configuration

Source: `frontend/Dockerfile`, `frontend/vite.config.ts`, `frontend/nginx.conf`

| File | Key Config | Description |
|------|-----------|-------------|
| `Dockerfile` | `node:24-alpine` (build), `nginx:alpine` (serve) | Two-stage build |
| `vite.config.ts` | `server.port: 3000` | Dev server port |
| `vite.config.ts` | `server.proxy['/api']` → `http://localhost:8000` | API proxy |
| `vite.config.ts` | `server.proxy['/ws']` → `ws://localhost:8001` | WebSocket proxy |
| `nginx.conf` | `location /api/` → `proxy_pass http://api-gateway:8000/` | Production API proxy |
| `nginx.conf` | `location /ws/` → `proxy_pass http://orchestrator-agent:8001/ws/` | Production WS proxy |
| `nginx.conf` | `location /debug/` → `proxy_pass http://debug-service:8099` | Debug proxy |
| `nginx.conf` | `location /debug/stream` → WebSocket upgrade | Debug stream |
| `nginx.conf` | Security headers | X-Frame-Options, CSP, X-XSS-Protection |
| `nginx.conf` | Static asset caching | `1 year, immutable` for JS/CSS/fonts/images |

> **Note**: Frontend has no `.env` file. API URL is resolved via nginx reverse proxy at runtime.
> During dev, Vite dev server proxies `/api` → `localhost:8000`.

---

## Keycloak Migration Concerns

Planned migration from local JWT auth → Keycloak identity provider.

### Breaking Changes

| Current | Keycloak Equivalent | Impact |
|---------|---------------------|--------|
| `JWT_SECRET_KEY` (HMAC secret) | JWKS endpoint (asymmetric keys) | All JWT validation code must switch to JWKS |
| `JWT_ALGORITHM: HS256` | `RS256` (Keycloak default) | Algorithm validation must change |
| `JWT_EXPIRE_MINUTES: 480` | Managed by Keycloak realm | Token refresh flow required |
| `DEV_MODE: true` (auth bypass) | Must be `false` | No more dev auth bypass |
| `users` table in `banking_dev` | Managed by Keycloak | User CRUD moves to Keycloak Admin API |

### New Environment Variables Required

| Variable | Description | Example |
|----------|-------------|---------|
| `KEYCLOAK_URL` | Keycloak server base URL | `https://keycloak.example.com` |
| `KEYCLOAK_REALM` | Realm name | `banking` |
| `KEYCLOAK_CLIENT_ID` | OIDC client ID | `banking-api` |
| `KEYCLOAK_CLIENT_SECRET` | OIDC client secret | *(from Keycloak admin)* |
| `KEYCLOAK_ADMIN_USERNAME` | Admin console user | *(optional — admin operations)* |
| `KEYCLOAK_ADMIN_PASSWORD` | Admin console password | *(optional — admin operations)* |

### Services Affected by Migration

1. **api-gateway** — Primary JWT validation entry point; must fetch JWKS
2. **orchestrator-agent** — Validates tokens for WebSocket connections
3. **All microservice agents** — If any perform independent JWT validation
4. **frontend** — Must use OIDC authorization code flow instead of local login
5. **services/shared/config.py** — `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `DEV_MODE` defaults change

### Migration Checklist

- [ ] Deploy Keycloak instance (Docker or managed)
- [ ] Create `banking` realm and `banking-api` client
- [ ] Migrate user data from `banking_dev.users` → Keycloak
- [ ] Update `api-gateway` to validate via JWKS
- [ ] Update frontend to use OIDC flow
- [ ] Disable `DEV_MODE` in all environments
- [ ] Remove `JWT_SECRET_KEY` from production configs
- [ ] Update `services/shared/config.py` to support JWKS validation
- [ ] Test token refresh flow end-to-end
- [ ] Update all service Docker Compose files with Keycloak env vars
