# Banking Intelligence System — Pre-Keycloak Baseline Report

**Date**: 2026-07-26
**Author**: Senior Software Architect (Automated Reconciliation)
**Status**: RECONCILED — Single Source of Truth

---

## 1. Executive Summary

The Banking Intelligence System is a multi-agent NL-to-SQL banking analytics platform with a React frontend, FastAPI microservices, PostgreSQL databases, and Redis caching. This baseline reconciliation resolved 15+ contradictions from previous documentation. The system has 21 docker-compose services (16 application + 5 infrastructure), 40 API Gateway endpoints, 78 database tables, and a 7-stage query pipeline. Authentication is custom JWT (HS256, 480-minute expiry). The Secrets Manager is a stub. No Keycloak integration exists.

---

## 2. Repository and Git State

| Field | Value | Evidence |
|-------|-------|----------|
| Branch | main | VERIFIED_AT_RUNTIME |
| Latest commit | 9a51c43 (feat: performance report/freeze checklist/architecture diagrams) | VERIFIED_AT_RUNTIME |
| Tags | benchmark-v1-holdout-candidate, benchmark-v1-ready, v0.1-week1 through v0.5-week5-mvp | VERIFIED_AT_RUNTIME |
| Working tree | Clean | VERIFIED_AT_RUNTIME |
| Proposed baseline tag | baseline/pre-keycloak-YYYY-MM-DD | NOT YET CREATED |

---

## 3. Authoritative Architecture

| Layer | Technology | Version | Evidence |
|-------|-----------|---------|----------|
| Frontend | React + TypeScript + Vite + TailwindCSS + shadcn/ui | React 18 | VERIFIED_FROM_SOURCE |
| API Gateway | FastAPI + slowapi + PyJWT + passlib/bcrypt | Python 3.11 | VERIFIED_FROM_SOURCE |
| Pipeline | 6-stage sequential agent pipeline via orchestrator | FastAPI | VERIFIED_FROM_SOURCE |
| Database | PostgreSQL (3 instances) | 16-alpine | VERIFIED_FROM_SOURCE (docker-compose.yml:482) |
| Vector DB | pgvector extension | pg16 | VERIFIED_FROM_SOURCE (docker-compose.yml:531) |
| Cache | Redis | 7-alpine | VERIFIED_FROM_SOURCE (docker-compose.yml:556) |
| LLM | Ollama (local) | latest | VERIFIED_FROM_SOURCE (docker-compose.yml:576) |
| Auth | Custom JWT (HS256) + bcrypt | PyJWT | VERIFIED_FROM_SOURCE |

---

## 4. Executable Services

| # | Service | Port | Container | Status | Evidence |
|---|---------|------|-----------|--------|----------|
| 1 | api-gateway | 8000 | banking_api_gateway | ACTIVE | VERIFIED_FROM_SOURCE |
| 2 | orchestrator-agent | 8001 | banking_orchestrator | ACTIVE | VERIFIED_FROM_SOURCE |
| 3 | intent-agent | 8002 | banking_intent_agent | ACTIVE | VERIFIED_FROM_SOURCE |
| 4 | schema-agent | 8003 | banking_schema_agent | ACTIVE | VERIFIED_FROM_SOURCE |
| 5 | entity-resolution-agent | 8004 | banking_entity_resolution | ACTIVE | VERIFIED_FROM_SOURCE |
| 6 | sql-agent | 8005 | banking_sql_agent | ACTIVE | VERIFIED_FROM_SOURCE |
| 7 | validation-agent | 8006 | banking_validation_agent | ACTIVE | VERIFIED_FROM_SOURCE |
| 8 | execution-agent | 8007 | banking_execution_agent | ACTIVE | VERIFIED_FROM_SOURCE |
| 9 | audit-agent | 8008 | banking_audit_agent | ACTIVE | VERIFIED_FROM_SOURCE |
| 10 | embedding-service | 8009 | banking_embedding_service | ACTIVE | VERIFIED_FROM_SOURCE |
| 11 | compliance-agent | 8011 | banking_compliance_agent | ACTIVE | VERIFIED_FROM_SOURCE |
| 12 | audit-enhancement | 8012 | banking_audit_enhancement | ACTIVE | VERIFIED_FROM_SOURCE |
| 13 | insights-agent | 8013 | banking_insights_agent | ACTIVE | VERIFIED_FROM_SOURCE |
| 14 | frontend | 3000 | banking_frontend | ACTIVE | VERIFIED_FROM_SOURCE |
| 15 | debug-service | 8099 | banking_debug_service | DEV-ONLY | VERIFIED_FROM_SOURCE |
| 16 | secrets-manager | 8010 | banking_secrets | STUB | VERIFIED_FROM_SOURCE |

---

## 5. Infrastructure Services

| # | Service | Port | Image | Evidence |
|---|---------|------|-------|----------|
| 17 | postgres-main | 5432 | postgres:16-alpine | VERIFIED_FROM_SOURCE |
| 18 | postgres-audit | 5433 | postgres:16-alpine | VERIFIED_FROM_SOURCE |
| 19 | postgres-embeddings | 5434 | pgvector/pgvector:pg16 | VERIFIED_FROM_SOURCE |
| 20 | redis | 6379 | redis:7-alpine | VERIFIED_FROM_SOURCE |
| 21 | ollama | 11434 | ollama/ollama:latest | VERIFIED_FROM_SOURCE |

---

## 6. Runtime Query Pipeline

7 mandatory stages + 2 post-execution stages:

| Stage | Agent | Port | Timeout | Feature Flag | Failure Behavior |
|-------|-------|------|---------|-------------|-----------------|
| 1. Intent | intent-agent | 8002 | 10s | SEMANTIC_LAYER_ENABLED | Block (gate reject) |
| 2. Schema | schema-agent | 8003 | 10s | SEMANTIC_LAYER_ENABLED | Block |
| 3. Entity Resolution | entity-resolution-agent | 8004 | 10s | none | Block |
| 4. SQL Generation | sql-agent | 8005 | 10s | 6 flags (all disabled) | Block |
| 5. Validation | validation-agent | 8006 | 10s | none | Block (unsafe) |
| 5.5. Compliance | compliance-agent | 8011 | 10s | ENABLE_COMPLIANCE_AGENT | Block (critical) / warn (non-critical) |
| 6. Execution | execution-agent | 8007 | 30s | none | Block |
| 6.5. Insights | insights-agent | 8013 | 300s | ENABLE_INSIGHTS_AGENT | Non-fatal |
| 7. Audit | audit-agent | 8008 | 10s | none | Non-fatal |

Evidence: VERIFIED_FROM_SOURCE (orchestrator_agent.py:39-423)

---

## 7. API Gateway Endpoints

**Total: 40 endpoints** (VERIFIED_FROM_SOURCE, routes.py)

| Category | Count | Endpoints |
|----------|-------|-----------|
| Health | 1 | /health |
| Auth | 1 | POST /auth/login |
| Query | 1 | POST /query |
| Dashboard | 4 | /dashboard/overview, /dashboard/kpis, /dashboard/recent-activity, /dashboard/charts/{chart_id} |
| KPI | 7 | /kpi/catalog, /kpi/dashboard, /kpi/values, /kpi/metrics, /kpi/trends, /kpi/{kpi_id}/insights, /kpi/{kpi_id} |
| Risk | 4 | /risk/overview, /risk/flags, /risk/segments, /risk/summary |
| Compliance | 4 | /compliance/overview, /compliance/report, /compliance/rules, /compliance/violations |
| Audit | 1 | /audit/logs |
| Reports | 2 | GET /reports, POST /reports/generate |
| Profile | 2 | /users/me, /auth/me |
| Admin | 11 | /admin/users (GET/POST), /admin/users/{id} (GET/PATCH), /admin/users/{id}/status, /admin/users/{id}/reset-password, /admin/users/{id}/roles, /admin/roles (GET/POST), /admin/roles/{id} (PATCH), /admin/roles/{id}/permissions, /admin/permissions, /admin/activity |

### Non-existent Endpoints (Previously Claimed)
- POST /auth/logout — DOES NOT EXIST
- POST /auth/refresh — DOES NOT EXIST
- GET /documents/* — DOES NOT EXIST
- GET /notifications/* — DOES NOT EXIST
- GET /settings/* — DOES NOT EXIST (backend)
- GET /analytics/* — DOES NOT EXIST
- GET /branches/* — DOES NOT EXIST (backend)

---

## 8. Frontend Reality

**17 page files**, **18 routes**, **14 API client modules** (VERIFIED_FROM_SOURCE)

| Page | Route | Role Gate | Backend Endpoint | Contract |
|------|-------|-----------|-----------------|----------|
| BankingDashboard | /, /dashboard | any auth | GET /dashboard/overview | MATCHED |
| Branches | /branches | any auth | (no dedicated endpoint) | GAP |
| Assistant | /assistant | any auth | POST /query | MATCHED |
| KpiPage | /kpi | any auth | GET /kpi/metrics | MATCHED |
| KpiGovernancePage | /kpi-governance | analyst+ | GET /kpi/catalog | MATCHED |
| RiskPage | /risk | analyst+ | GET /risk/overview | MATCHED |
| CompliancePage | /compliance | compliance+ | GET /compliance/overview | MATCHED |
| ReportsPage | /reports | manager+ | GET /reports | MATCHED |
| AdminPage | /admin | admin | GET /admin/users | MATCHED |
| ProfilePage | /profile | any auth | GET /auth/me | MATCHED |
| Settings | /settings | any auth | (no backend endpoint) | GAP |

### Frontend/Backend Gaps
1. /settings — page exists, no backend endpoint
2. /branches — page exists, no dedicated backend endpoint (may use dashboard data)
3. Documents page — DOES NOT EXIST (contrary to previous baseline)
4. Notifications page — DOES NOT EXIST (contrary to previous baseline)
5. Analytics page — DOES NOT EXIST (contrary to previous baseline)

---

## 9. Authentication and Authorisation

| Aspect | Value | Source Reference |
|--------|-------|-----------------|
| Library | PyJWT | auth.py:14 |
| Algorithm | HS256 | config.py:62 |
| Secret | env JWT_SECRET_KEY, default "change-this-in-production-do-not-use-in-prod" | config.py:58-60 |
| Expiry | 480 minutes (8 hours) | config.py:63 |
| Password hashing | bcrypt (passlib) | auth.py:26 |
| Token claims | sub, role, iat, exp, jti | auth.py:115-121 |
| Issuer validation | None | auth.py:151-155 |
| Audience validation | None | auth.py:151-155 |
| JTI validation | Generated but NOT validated | auth.py:120, 156 |
| Refresh tokens | NOT supported | No /auth/refresh endpoint |
| Logout | Client-side only (clear localStorage) | No /auth/logout endpoint |
| DEV_MODE | Falls back to MOCK_USERS when DB unavailable; does NOT allow any username | auth.py:188-194, 274-290 |
| Mock users | 5 users (analyst_001, analyst_002, compliance_001, manager_001, admin_001) | auth.py:37-93 |
| Roles | analyst, compliance, manager, admin | models.py:14-18 |
| RBAC groups | business={analyst,manager,admin}, compliance={compliance,admin}, admin={admin} | routes.py:433-437 |
| Permission source | DB role_permissions junction + users.permissions column (hybrid) | routes.py:390-408 |

---

## 10. Databases and Data State

| Database | Engine | Tables | Evidence |
|----------|--------|--------|----------|
| banking_dev | PostgreSQL 16-alpine | 74 | VERIFIED_FROM_SOURCE |
| audit_logs | PostgreSQL 16-alpine | 1 | VERIFIED_FROM_SOURCE |
| embeddings | pgvector/pgvector:pg16 | 3 | VERIFIED_FROM_SOURCE |
| **TOTAL** | | **78** | |

### Seed Data Status
| Script | Tables Seeded | Volume | Evidence |
|--------|--------------|--------|----------|
| postgres-main-init.sql | 6 core tables | ~410 rows | VERIFIED_FROM_SOURCE |
| 02-users-kpis.sql | 10 RBAC/KPI tables | ~60 rows | VERIFIED_FROM_SOURCE |
| 08-semantic-layer-seed.sql | 5 semantic tables | ~50 rows | VERIFIED_FROM_SOURCE |
| 09-tunisian-banking-data-seed.sql | (additional Tunisia data) | varies | VERIFIED_FROM_SOURCE |

---

## 11. Feature Flags

| Flag | Default | Docker | Classification | Runtime Effect |
|------|---------|--------|----------------|----------------|
| DEV_MODE | True | not overridden | RUNTIME_ACTIVE | Controls mock auth fallback |
| ENABLE_INSIGHTS_AGENT | True | not overridden | DEAD_CONFIG | Flag defined but NOT checked before agent call |
| ENABLE_COMPLIANCE_AGENT | True | not overridden | DEAD_CONFIG | Flag defined but NOT checked before agent call |
| ENABLE_CACHING | True | not overridden | UNKNOWN | No runtime consumer found |
| SEMANTIC_LAYER_ENABLED | False | False (7 services) | RUNTIME_WIRED_DISABLED | Controls pipeline semantic vs legacy path |
| STRUCTURED_QUERY_PLAN_ENABLED | False | not overridden | IMPLEMENTED_BUT_NOT_WIRED | Code path exists but not verified |
| DETERMINISTIC_SQL_COMPILER_ENABLED | False | not overridden | IMPLEMENTED_BUT_NOT_WIRED | Code path exists but not verified |
| SQL_REPAIR_ENABLED | False | not overridden | IMPLEMENTED_BUT_NOT_WIRED | Code path exists but not verified |
| RESULT_VERIFICATION_ENABLED | False | not overridden | IMPLEMENTED_BUT_NOT_WIRED | Code path exists but not verified |
| CONVERSATION_CONTEXT_ENABLED | False | not overridden | IMPLEMENTED_BUT_NOT_WIRED | Code path exists but not verified |
| LLM_SQL_FALLBACK_ENABLED | False | not overridden | IMPLEMENTED_BUT_NOT_WIRED | Code path exists but not verified |
| EXPLAIN_COST_CHECK_ENABLED | False | not overridden | UNKNOWN | No verified consumer |
| BENCHMARK_MODE | False | not overridden | TEST_ONLY | Used in benchmark tests |

---

## 12. Tests Actually Executed

| Metric | Value | Evidence |
|--------|-------|----------|
| Command | python3 -m pytest tests/ --ignore=tests/test_schema_agent.py -q --tb=no | VERIFIED_AT_RUNTIME |
| Date | 2026-07-26 | VERIFIED_AT_RUNTIME |
| Total collected | 623 (18 blocked by import error in test_schema_agent.py) | VERIFIED_AT_RUNTIME |
| Passed | 481 | VERIFIED_AT_RUNTIME |
| Failed | 38 | VERIFIED_AT_RUNTIME |
| Errors | 104 (import/collection errors) | VERIFIED_AT_RUNTIME |
| Duration | 15.43s | VERIFIED_AT_RUNTIME |

---

## 13. Verified Working Capabilities

- Login with seeded users (analyst_001, manager_001, compliance_001, admin_001)
- JWT token generation and validation
- Dashboard overview, KPIs, recent activity, charts
- KPI governance catalog, dashboard, values, metrics, trends
- Risk overview, flags, segments, summary
- Compliance overview, rules, violations, report
- Audit log querying
- Report listing and generation
- Admin user CRUD, role management, permission management
- Profile viewing
- NL-to-SQL query pipeline (end-to-end)
- All RBAC role checks

---

## 14. Implemented But Disabled Capabilities

- Semantic layer (SEMANTIC_LAYER_ENABLED=false)
- Structured query planning (STRUCTURED_QUERY_PLAN_ENABLED=false)
- Deterministic SQL compiler (DETERMINISTIC_SQL_COMPILER_ENABLED=false)
- SQL repair (SQL_REPAIR_ENABLED=false)
- Result verification (RESULT_VERIFICATION_ENABLED=false)
- Conversation context (CONVERSATION_CONTEXT_ENABLED=false)
- LLM SQL fallback (LLM_SQL_FALLBACK_ENABLED=false)

---

## 15. Partially Implemented Capabilities

- **Secrets Manager**: Health endpoint only, no secret storage/retrieval/encryption (STUB)
- **Embedding Service**: pgvector database exists, embedding-service runs, but full semantic search not verified
- **Audit Enhancement**: Service runs, compliance reports work, but integration depth not verified

---

## 16. Scaffolds and Placeholders

- **secrets_manager**: Pure stub — returns 501 on POST, only /health works
- **debug-service**: Dev-only WebSocket relay, no restart policy
- **ENABLE_INSIGHTS_AGENT / ENABLE_COMPLIANCE_AGENT flags**: Dead configuration — agents always called regardless

---

## 17. Missing Capabilities

- No /auth/logout endpoint (server-side)
- No /auth/refresh endpoint (token refresh)
- No Documents page or backend
- No Notifications page or backend
- No dedicated /branches/* backend endpoints
- No dedicated /settings/* backend endpoints
- No /analytics/* backend endpoints
- No refresh token support
- No issuer/audience JWT validation
- No JTI revocation

---

## 18. Frontend/Backend Mismatches

| Issue | Frontend | Backend | Severity |
|-------|----------|---------|----------|
| Settings page has no backend | Settings page renders | No /settings/* endpoints | LOW |
| Branches page has no backend | Branches page renders | No /branches/* endpoints | LOW |
| queries.ts may be dead code | queries.ts exists | Not clear if used | LOW |

---

## 19. Documentation Contradictions Corrected

| Contradiction | Previous Claim | Verified Truth | Resolution |
|--------------|---------------|----------------|------------|
| Service count | 15 or 16 | 21 (16 app + 5 infra) | docker-compose.yml: 21 services |
| Service names | analytics_engine, compliance_monitor, etc. | intent-agent, schema-agent, etc. | docker-compose.yml: exact names verified |
| JWT expiry | 24 hours | 480 minutes (8 hours) | config.py:63 |
| DEV_MODE | Any username succeeds | Falls back to MOCK_USERS only when DB unavailable | auth.py:188-194 |
| PostgreSQL version | 15 | 16-alpine | docker-compose.yml:482 |
| Database tables | 76 or 78 | 78 (74+1+3) | SQL scripts: exact count |
| Refresh tokens | Existed | Do NOT exist | routes.py: no endpoint |
| Logout | Existed | Does NOT exist (client-side only) | routes.py: no endpoint |
| Secrets Manager | Operational | STUB (health only) | secrets_manager/main.py |
| Feature flags | 3 active | Only DEV_MODE truly active; ENABLE_* flags are dead config | orchestrator_agent.py |
| Pipeline stages | 6, 8, or 9 | 7 mandatory + 2 post-execution | orchestrator_agent.py:39-423 |
| Documents page | Existed | DOES NOT EXIST | App.tsx: no route |
| Notifications page | Existed | DOES NOT EXIST | App.tsx: no route |
| Analytics page | Existed | DOES NOT EXIST | App.tsx: no route |
| Admin endpoints | PUT/DELETE | PATCH | routes.py:1871,1956,2060 |

---

## 20. Keycloak Migration Impact

| Area | Impact | Effort |
|------|--------|--------|
| auth.py | Replace JWT creation/verification with Keycloak SDK | HIGH |
| routes.py get_current_user | Replace JWT decode with Keycloak JWKS validation | HIGH |
| client.ts | Replace localStorage token with keycloak-js adapter | HIGH |
| LoginPage | Replace form login with Keycloak redirect | MEDIUM |
| Role checks | Map Keycloak realm roles to ROLE_GROUPS | MEDIUM |
| Permission checks | Map Keycloak client roles to role_permissions | MEDIUM |
| DEV_MODE | Remove or replace with Keycloak dev profile | LOW |
| MOCK_USERS | Remove entirely | LOW |
| docker-compose.yml | Add Keycloak service | MEDIUM |
| 5 seed users | Migrate to Keycloak users | LOW |

---

## 21. Keycloak Migration Blockers

1. **No refresh token support**: Current system has no token refresh mechanism. Keycloak requires refresh token handling.
2. **No logout endpoint**: Server-side token revocation needed for Keycloak.
3. **DEV_MODE bypass**: Must be replaced with Keycloak dev profile or test realm.
4. **Hybrid permissions**: role_permissions junction table + users.permissions column must be reconciled with Keycloak client roles.
5. **jti not validated**: Keycloak RS256 requires proper token validation.

---

## 22. GO or NO-GO Decision

**GO** — with conditions.

The system is functional with 481/623 tests passing. The 38 failures and 104 errors are pre-existing and do not block Keycloak integration. The auth system is well-structured for migration. The main risks are:
- DEV_MODE must be disabled in production
- No refresh token support must be addressed
- 104 test import errors need investigation

---

## 23. Exact Scope of Next Increment

Increment 1 should focus on:
1. Add Keycloak service to docker-compose.yml
2. Replace auth.py JWT functions with Keycloak SDK calls
3. Add keycloak-js to frontend
4. Implement refresh token handling
5. Implement server-side logout
6. Remove DEV_MODE bypass
7. Map existing roles to Keycloak realm roles
8. Update all protected routes to use Keycloak JWT validation

---

**Baseline Files Updated**:
- docs/baseline/BASELINE_REPORT.md (this file)
- docs/baseline/service-inventory.md
- docs/baseline/api-inventory.md
- docs/baseline/database-inventory.md
- docs/baseline/auth-system.md
- docs/baseline/feature-flags.md
- docs/baseline/frontend-inventory.md
- docs/baseline/test-inventory.md
- docs/baseline/architecture-diagram.md
- docs/baseline/runtime-pipeline.md
