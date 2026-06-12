# PLATFORM_ROADMAP.md — Banking Intelligence System
> Version: 1.0 | Updated: 2026-06-12

---

## Phase Status Overview

| Phase | Name | Status |
|---|---|---|
| Phase 1 | Core NL-to-SQL Pipeline | ✅ Complete |
| Phase 2 | Insights, Compliance & Audit Enhancement | 🔄 Partial (services deployed, not fully integrated) |
| Phase 3 | Stabilization & Security Hardening | 🔜 Next |
| Phase 4 | Multi-tenancy & RBAC v2 | 🔜 Planned |
| Phase 5 | Observability & CI/CD | 🔜 Planned |
| Phase 6 | Advanced ML & Dashboards | 🔜 Future |

---

## Phase 3 — Stabilization & Security Hardening (IMMEDIATE)

> Do these first. No new features until stable.

### 3.1 Docker Hardening
- [ ] Add health checks to all 14 services missing them
- [ ] Replace hardcoded DB passwords in `docker-compose.yml` with `${VAR}` references
- [ ] Add `restart: unless-stopped` to all production services
- [ ] Add `depends_on` + condition `service_healthy` where missing
- [ ] Pin all `python:3.11-slim` images with digest or use custom Dockerfiles

### 3.2 Security
- [ ] Replace plaintext password compare with `bcrypt.checkpw()` in `auth.py`
- [ ] Restrict CORS `allow_origins` from `["*"]` to known frontend origins
- [ ] Implement token revocation using Redis blacklist keyed on `jti`
- [ ] Add `POST /auth/logout` endpoint that invalidates JWT
- [ ] Add `POST /auth/refresh` endpoint with short-lived access + long-lived refresh tokens
- [ ] Rotate `JWT_SECRET_KEY` — use a 256-bit random value
- [ ] Rotate `QUERY_SIGNING_KEY`

### 3.3 Environment Variables
- [ ] Create `.env.example` from current `.env` with all secrets blanked
- [ ] Add missing vars: `COMPLIANCE_AGENT_URL`, `INSIGHTS_AGENT_URL`, `QUERY_SIGNING_KEY`, `DEBUG_SERVICE_URL`
- [ ] Ensure all vars in compose use `${VAR}` not hardcoded strings

### 3.4 Root Cleanup
- [ ] Create `scripts/` directory
- [ ] Move all `fix_*.py`, `debug.py`, `db_test.py`, `print_payload.py` → `scripts/`
- [ ] Move `test_local.py`, `test_mistral*.py`, `test_orch.py` → `scripts/` or `tests/`
- [ ] Create root `README.md`

### 3.5 Testing
- [ ] Add `pytest-cov` and minimum coverage gate (70%)
- [ ] Add health-check test that verifies all running services respond to `/health`
- [ ] Fix any tests broken by conftest stub limitations
- [ ] Add `make test` and `make test-integration` targets to Makefile

---

## Phase 4 — RBAC v2 & User Management (SHORT-TERM)

### 4.1 Real User Store
- [ ] Create `users` table in `postgres-main`
- [ ] Add bcrypt password hashes to `users` table seed
- [ ] Replace `MOCK_USERS` dict in `auth.py` with async DB lookup
- [ ] Add `GET /users/me` endpoint (returns current user profile)
- [ ] Add `GET /audit/logs` endpoint (compliance role only)

### 4.2 Permission Granularity
- [ ] Store permissions in `user_permissions` join table
- [ ] Load permissions into JWT claims at login
- [ ] Add `check_permission(user, "read:pii")` helper to shared lib
- [ ] Apply permission checks to execution_agent masking logic

### 4.3 Role Expansion
- [ ] Add `admin` role with full access
- [ ] Add `kyc_officer` role (compliance_checker.py already references it)
- [ ] Add `readonly` role for report-only access
- [ ] Add `auditor` role for audit-log-only access

---

## Phase 5 — Observability & CI/CD (MEDIUM-TERM)

### 5.1 Monitoring
- [ ] Configure `monitoring/prometheus.yml` — scrape all /metrics endpoints
- [ ] Configure `monitoring/grafana/` — datasource + dashboard JSON
- [ ] Add `prometheus-fastapi-instrumentator` to each service
- [ ] Add `monitoring` service block to `docker-compose.yml`
- [ ] Add Grafana service to `docker-compose.yml` on port 3001

### 5.2 Logging
- [ ] Centralize log format: all services use `shared/logger.py` (already exists)
- [ ] Add request correlation ID propagated through all agent hops
- [ ] Add structured log shipping (Loki or ELK optional)

### 5.3 CI/CD
- [ ] Create `.github/workflows/test.yml` — run pytest on PR
- [ ] Create `.github/workflows/build.yml` — Docker build check
- [ ] Add pre-commit hooks: black, ruff, mypy
- [ ] Add `Makefile` with: `make up`, `make down`, `make test`, `make build`, `make logs`

---

## Phase 6 — Multi-Tenancy (LONG-TERM)

> Only after Phase 4 RBAC is solid.

- [ ] Add `tenant_id` to user model and JWT claims
- [ ] Add row-level security (RLS) in PostgreSQL per tenant
- [ ] Add `X-Tenant-ID` header propagation through agent pipeline
- [ ] Add tenant-isolated Redis key namespacing
- [ ] Keep Keycloak as optional future IdP (not yet)

---

## Phase 7 — Advanced ML & Dashboards (FUTURE)

- [ ] Enable `ENABLE_INSIGHTS_AGENT=true` when stable
- [ ] Enable `ENABLE_ADVANCED_ML=true` when model fine-tuning complete
- [ ] Build compliance report dashboard (frontend `/reports` route)
- [ ] Build audit log viewer (frontend `/audit` route)
- [ ] Build risk flag heatmap (frontend `/risk` route)
- [ ] Add chart library (Recharts already in frontend via `src/components/dashboard/`)
- [ ] Integrate real-time alerts via WebSocket (useWebSocket hook already initialized)

---

## Immediate Next Steps (Do Now)

1. **Create `.env.example`** — unblock new developer onboarding
2. **Write root `README.md`** — architecture, quickstart, port map
3. **Add health checks to 14 services** — Docker restart safety
4. **Fix docker-compose `${VAR}` for all DB creds** — security hygiene
5. **Move 19 root fix/debug scripts to `scripts/`** — repo cleanliness
6. **Add `POST /auth/logout`** — session management baseline
7. **Add `bcrypt` to auth.py** — password security minimum
8. **Set up Prometheus scraping** — `monitoring/` dir exists but empty

---

## API Surface Target State (Phase 4 Complete)

```
POST   /auth/login          ← exists
POST   /auth/logout         ← MISSING
POST   /auth/refresh        ← MISSING
GET    /users/me            ← MISSING
POST   /query               ← exists
GET    /health              ← exists
GET    /audit/logs          ← MISSING (compliance role only)
GET    /compliance/report   ← MISSING
GET    /metrics             ← MISSING (Prometheus)
```
