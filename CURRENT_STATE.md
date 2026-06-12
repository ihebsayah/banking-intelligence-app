# CURRENT_STATE.md — Banking Intelligence Platform Audit
> Generated: 2026-06-12 | Auditor: Antigravity AI | Mode: Stabilization Pass

---

## 1. Project Overview

Multi-agent AI-powered banking intelligence platform.
Natural-language → SQL pipeline via 6 specialized microservices.
Stack: FastAPI · PostgreSQL (×3) · Redis · Ollama/Mistral · React/TypeScript/Vite · Docker Compose.

---

## 2. Docker Services Inventory

| Service | Container | Port | Health Check | Notes |
|---|---|---|---|---|
| `frontend` | banking_frontend | 3000→80 | ✅ wget /health | Nginx, Vite built |
| `api-gateway` | banking_api_gateway | 8000 | ✅ python urllib | Custom Dockerfile |
| `orchestrator-agent` | banking_orchestrator | 8001 | ❌ None | pip install at start |
| `debug-service` | banking_debug_service | 8099 | ❌ None | Dev only |
| `intent-agent` | banking_intent_agent | 8002 | ❌ None | spaCy + pip install |
| `schema-agent` | banking_schema_agent | 8003 | ❌ None | Redis dep |
| `entity-resolution-agent` | banking_entity_resolution | 8004 | ❌ None | pgvector + Redis |
| `sql-agent` | banking_sql_agent | 8005 | ❌ None | Redis dep |
| `validation-agent` | banking_validation_agent | 8006 | ❌ None | — |
| `execution-agent` | banking_execution_agent | 8007 | ✅ python urllib | DB + Redis + QUERY_SIGNING_KEY |
| `audit-agent` | banking_audit_agent | 8008 | ✅ python urllib | postgres-audit dep |
| `embedding-service` | banking_embedding_service | 8009 | ❌ None | pgvector dep |
| `secrets-manager` | banking_secrets | 8010 | ❌ None | Volume mount |
| `compliance-agent` | banking_compliance_agent | 8011 | ❌ None | Phase 2 |
| `audit-enhancement` | banking_audit_enhancement | 8012 | ❌ None | Phase 2 |
| `insights-agent` | banking_insights_agent | 8013 | ❌ None | Phase 2 · Ollama dep |
| `postgres-main` | banking_postgres_main | 5432 | ✅ pg_isready | banking_dev DB |
| `postgres-audit` | banking_postgres_audit | 5433 | ✅ pg_isready | audit_logs DB |
| `postgres-embeddings` | banking_postgres_embeddings | 5434 | ✅ pg_isready | pgvector/pg16 |
| `redis` | banking_redis | 6379 | ✅ redis-cli ping | AOF persistence |
| `ollama` | banking_ollama | 11434 | ❌ None | mistral model |

**Health check coverage: 7/21 services (33%). 14 services have no health check.**

---

## 3. NL-to-SQL Agent Pipeline

```
[User Query]
    │
    ▼
API Gateway (8000) ─── JWT auth ─── rate limit ─── audit middleware
    │
    ▼
Orchestrator (8001)
    │
    ├─► Intent Agent (8002)          — NL intent classification (spaCy + rules)
    ├─► Schema Agent (8003)          — table/column mapping (embeddings cache)
    ├─► Entity Resolution (8004)     — entity normalization (pgvector lookup)
    ├─► SQL Agent (8005)             — SQL generation (Mistral + templates)
    ├─► Validation Agent (8006)      — SQL syntax + safety check
    ├─► Compliance Agent (8011)      — GDPR/PCI/SOX/AML/KYC rule check
    └─► Execution Agent (8007)       — DB query + RBAC + masking + signing
         │
         ├─► Audit Agent (8008)      — all events logged to postgres-audit
         └─► Insights Agent (8013)   — LLM-generated narrative (Phase 2)
```

Pipeline status: **Operational** (Phase 1 complete, Phase 2 partially deployed).

---

## 4. Authentication & Authorization

| Layer | Status | Detail |
|---|---|---|
| JWT auth | ✅ Implemented | HS256, 8h expiry, `jti` field for future revocation |
| Mock user store | ✅ Present | 4 users (analyst_001/002, compliance_001, manager_001) |
| Password hashing | ❌ Missing | Plaintext compare — bcrypt not yet integrated |
| RBAC permissions | ✅ Defined | Per-user permission arrays in mock store |
| Token revocation | ❌ Missing | `jti` exists in JWT but no revocation list |
| Real user DB | ❌ Missing | All users hardcoded — no DB lookup |
| Refresh tokens | ❌ Missing | Single token, no refresh flow |

**Roles defined:** `analyst`, `compliance`, `manager`, `admin`, `maker_checker` (SOX)

---

## 5. Compliance Implementation

| Regulation | Status | Location |
|---|---|---|
| GDPR — PII masking | ✅ Implemented | `compliance_checker.py` |
| PCI-DSS — card data | ✅ Implemented | `compliance_checker.py` |
| SOX — audit trail | ✅ Partial | Audit logs exist, segregation check partial |
| AML — transaction monitor | ✅ Implemented | `compliance_checker.py` |
| KYC — due diligence | ✅ Implemented | `compliance_checker.py` |
| DB-driven rules | ✅ Implemented | `compliance_rules` table query |
| Data lineage tracking | ✅ Partial | `data_lineage_tracker.py` exists |
| Compliance reports | ✅ Partial | `compliance_reporter.py` exists |

---

## 6. API Gateway Routes

| Method | Path | Auth Required | Description |
|---|---|---|---|
| GET | `/health` | ❌ | Liveness probe |
| POST | `/auth/login` | ❌ | Form login → JWT |
| POST | `/query` | ✅ Bearer JWT | NL query → full pipeline |
| GET | `/docs` | ❌ | Swagger UI |
| GET | `/redoc` | ❌ | ReDoc UI |

**Missing routes:** `/auth/logout`, `/auth/refresh`, `/users/me`, `/audit/logs`, `/compliance/report`

---

## 7. Frontend Routing

| Path | Layout | Auth Guard | Page |
|---|---|---|---|
| `/login` | None | ❌ | LoginPage |
| `/` | BankingSidebar | ✅ ProtectedRoute | BankingDashboard |
| `/dashboard` | BankingSidebar | ✅ ProtectedRoute | BankingDashboard |
| `/branches` | BankingSidebar | ✅ ProtectedRoute | Branches |
| `/assistant` | BankingSidebar | ✅ ProtectedRoute | Assistant (NL query UI) |
| `/settings` | BankingSidebar | ✅ ProtectedRoute | Settings |
| `/dev` | DevSidebar | ❌ No guard | Dashboard (dev) |
| `/dev/query` | DevSidebar | ❌ No guard | QueryTester |
| `/dev/agents` | DevSidebar | ❌ No guard | AgentMonitorPage |
| `/dev/performance` | DevSidebar | ❌ No guard | PerformanceMonitor |
| `/dev/debug` | DevSidebar | ❌ No guard | DebugPage |

**Issue:** `/dev/*` routes have no auth guard — dev tools exposed without authentication.

---

## 8. Frontend Tech Stack

- **Framework:** React 18 + TypeScript + Vite
- **Styling:** Tailwind CSS (tailwind.config.js present)
- **Routing:** React Router DOM
- **State:** Zustand (stores/ dir present)
- **API layer:** `src/api/` directory (dashboard.ts confirmed)
- **WebSocket:** `useWebSocket` hook initialized at app root
- **Build:** Nginx serves `/dist` in Docker

---

## 9. Database Schema Summary

**postgres-main (banking_dev):**
- `customers`, `accounts`, `transactions`, `risk_flags`, `branches`, `compliance_rules`
- Seed data present in `postgres-main-init.sql` (19KB)

**postgres-audit (audit_logs):**
- `audit_log` table — all access events
- `compliance_events` (likely)
- Init via `postgres-audit-init.sql`

**postgres-embeddings (embeddings):**
- `schema_embeddings` (pgvector for schema-agent)
- `entity_embeddings` (pgvector for entity-resolution)
- pgvector/pg16 image

---

## 10. Test Structure

```
tests/
├── conftest.py                    — Stubs: redis, asyncpg, spacy (no Docker needed)
├── test_audit_enhancement.py
├── test_caching.py
├── test_compliance_agent.py       (11.9KB — comprehensive)
├── test_entity_resolution_agent.py
├── test_execution_agent.py
├── test_insights_agent.py
├── test_integration.py            (9.4KB)
├── test_intent_agent.py
├── test_performance.py
├── test_preset_queries.py
├── test_preset_queries_unit.py
├── test_schema_agent.py
├── test_security.py               (15.6KB — comprehensive)
├── test_sql_agent.py
├── test_validation_agent.py
├── week3_local_test.py
└── week4_local_test.py
```

**Coverage:** Unit tests per agent ✅ | Integration tests ✅ | Security tests ✅ | No E2E tests | No CI/CD config found.

---

## 11. Root-Level Clutter

Files in root that should be cleaned up:
```
fix_cors.py, fix_date_type.py, fix_executor_date.py, fix_fallback.py,
fix_init_vars.py, fix_join_key.py, fix_orch2.py, fix_orchestrator.py,
fix_products.py, fix_re.py, fix_risk_flags.py, fix_unit_test_risk_flags.py,
debug.py, db_test.py, test_local.py, test_mistral.py, test_mistral_output.py,
test_orch.py, print_payload.py
```
19 one-off debug/fix scripts in root — should move to `scripts/` or delete.

---

## 12. Missing Folders / Files

| Missing | Priority | Reason |
|---|---|---|
| `README.md` (root) | 🔴 High | No root readme — onboarding impossible |
| `.env.example` | 🔴 High | .env committed, no template for newcomers |
| `scripts/` dir | 🟡 Medium | Root cluttered with 19 fix/debug scripts |
| `monitoring/` config | 🟡 Medium | Dir exists but empty — Prometheus/Grafana planned |
| `CI/` or `.github/workflows/` | 🟡 Medium | No CI pipeline |
| `CHANGELOG.md` | 🟢 Low | Phase tracking unclear |
| Health checks for 14 services | 🔴 High | Docker orchestration blind without them |

---

## 13. Environment Variable Gaps

Variables in `docker-compose.yml` but missing from `.env`:
- `COMPLIANCE_AGENT_URL` (used by orchestrator)
- `INSIGHTS_AGENT_URL` (used by orchestrator)
- `SECRETS_MANAGER_URL`
- `DEBUG_SERVICE_URL`
- `QUERY_SIGNING_KEY`

Variables in `.env` but hardcoded in compose (not referenced via `${VAR}`):
- All DB passwords (`securepass123`) hardcoded in compose — not using `.env` vars

---

## 14. Known Issues / Risks

| Issue | Severity | Notes |
|---|---|---|
| Passwords hardcoded in docker-compose | 🔴 Critical | Must use `${VAR}` references |
| JWT_SECRET_KEY weak default | 🔴 Critical | In .env and compose — dev default exposed |
| Mock auth — plaintext passwords | 🟡 Medium | MVP only, no bcrypt |
| CORS `allow_origins=["*"]` | 🟡 Medium | Must restrict in prod |
| No token revocation | 🟡 Medium | jti unused |
| 14 services without health checks | 🟡 Medium | Docker can't restart them safely |
| `pip install` at container start | 🟡 Medium | Slow start, no version lock per image |
| `/dev/*` routes unguarded | 🟢 Low | Dev layout, not prod concern yet |
| `monitoring/` dir empty | 🟢 Low | Prometheus/Grafana not configured |
| 19 debug scripts in root | 🟢 Low | Visual noise, confusing |
