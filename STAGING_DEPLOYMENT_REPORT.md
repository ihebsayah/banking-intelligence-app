# Staging Deployment Report — Phase 2B.18a
## Banking Intelligence System — Workbench & Worker Container Closure
**Date:** 2026-08-02  
**Environment:** Local Staging (Docker Compose)  
**Status:** DEPLOYED ✓

---

## 1. Containers Deployed

| Service | Container | Port | Status | Health |
|---------|-----------|------|--------|--------|
| Frontend | banking_frontend | 3000:80 | Up | Healthy |
| API Gateway | banking_api_gateway | 8000:8000 | Up | Healthy |
| **Workbench** | **banking_workbench** | **8014:8014** | **Up** | **Healthy** |
| **Expiry Worker** | **banking_expiry_worker** | - | **Up** | Running |
| **Outbox Worker** | **banking_outbox_worker** | - | **Up** | Running |
| Audit Agent | banking_audit_agent | 8008:8008 | Up | Healthy |
| Postgres Main | banking_postgres_main | 5432:5432 | Up | Healthy |
| Postgres Audit | banking_postgres_audit | 5433:5432 | Up | Healthy |
| Postgres Integration | banking_postgres_integration | 5435:5432 | Up | Healthy |
| Postgres Embeddings | banking_postgres_embeddings | 5434:5432 | Up | Healthy |
| Postgres Keycloak | banking_postgres_keycloak | 5432:5432 | Up | Healthy |
| Redis | banking_redis | 6379:6379 | Up | Healthy |
| Keycloak | banking_keycloak | 8080:8080 | Up | Functional |
| Ollama | banking_ollama | 11434:11434 | Up | Healthy |

**All 24 core services deployed and operational.**

---

## 2. Fixes Applied (2B.18a)

### Root Cause
The workbench and worker containers failed to start due to two issues:
1. **PYTHONPATH not set correctly** — containers couldn't find `workbench` and `shared` packages
2. **Incorrect database port** — URL used host port 5435 instead of container port 5432
3. **Missing dependencies** — `pydantic-settings` not in requirements.txt
4. **Workers missing commands** — expiry-worker and outbox-worker had no CMD

### Changes Made

**`docker-compose.yml`:**
- Added `postgres-integration` service (moved from separate file)
- Added `workbench`, `expiry-worker`, `outbox-worker` services
- Set `PYTHONPATH=/app/services` for all three
- Set `command: ["python", "-m", "workbench.expiry_worker"]` etc.
- Fixed database URL port: `postgres-integration:5432` (not 5435)
- All workers use `build: context: ./services/workbench` for shared deps

**`services/workbench/main.py`:**
- Fixed sys.path to include `_services_dir` (parent of workbench/)

**`services/workbench/integration_app.py`:**
- Fixed `_assert_integration_database()` to check DB name instead of port
- Port 5432 is correct for container-to-container communication

**`services/workbench/expiry_worker.py`:**
- Use `INTEGRATION_DATABASE_URL` env var instead of `get_settings().DATABASE_URL`

**`services/workbench/outbox_worker.py`:**
- Use `INTEGRATION_DATABASE_URL` env var instead of `get_settings().DATABASE_URL`

**`services/workbench/requirements.txt`:**
- Added `pydantic-settings==2.1.0`

**`services/workbench/Dockerfile`:**
- Updated CMD to `uvicorn workbench.main:app --host 0.0.0.0 --port 8014`

---

## 3. Versions

| Component | Version |
|-----------|---------|
| PostgreSQL | 16-alpine |
| Redis | 7-alpine |
| Keycloak | 26.7.0 |
| Python | 3.11-slim |
| FastAPI | 0.104.1 |
| asyncpg | 0.29.0 |

---

## 4. Migrations Status

```
HEAD: 0010_fix_notification_type_constraint
Applied: 10 migrations total
Status: AT HEAD ✓
```

---

## 5. Health Check Results

| Check | Result |
|-------|--------|
| Workbench /health | ✓ `{"status":"ok"}` |
| API Gateway /health | ✓ OK |
| Audit Agent /health | ✓ OK |
| Frontend (port 3000) | ✓ 200 OK |
| Keycloak realm | ✓ reachable |
| PostgreSQL integration | ✓ pg_isready |
| Redis ping | ✓ PONG |

---

## 6. Worker Status

| Worker | Status | Evidence |
|--------|--------|----------|
| Expiry Worker | ✓ Running | Expired 1 approval on startup |
| Outbox Worker | ✓ Running | Polling every 5s, delivering events |
| Workbench API | ✓ Healthy | Health endpoint returning 200 |

---

## 7. Deployment Commands

```bash
# Build and start
docker compose build workbench expiry-worker outbox-worker
docker compose up -d workbench expiry-worker outbox-worker

# Check status
docker compose ps

# View logs
docker compose logs -f workbench expiry-worker outbox-worker

# Run smoke tests
./scripts/staging_smoke_test.sh
```
