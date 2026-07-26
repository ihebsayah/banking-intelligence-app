# API Inventory — Banking Intelligence System

> Authoritative inventory based on VERIFIED `routes.py` source code (2434 lines).
> Last verified: 2026-07-26

---

## Table of Contents

1. [Overview](#overview)
2. [API Gateway Endpoints (VERIFIED_FROM_SOURCE)](#api-gateway-endpoints-verified_from_source)
   - [Central Router Endpoints](#central-router-endpoints)
   - [Internal Service Endpoints](#internal-service-endpoints)
3. [Non-existent Endpoints (Previously Claimed)](#non-existent-endpoints-previously-claimed)
4. [Frontend/Backend Contract Gaps](#frontendbackend-contract-gaps)
5. [RBAC Reference](#rbac-reference)
6. [Service-to-Port Mapping](#service-to-port-mapping)

---

## Overview

```
                    ┌─────────────────────────────────────────────┐
                    │              Frontend (port 3000)            │
                    │         React SPA — nginx reverse proxy      │
                    └──────────────────┬──────────────────────────┘
                                       │ HTTP
                    ┌──────────────────▼──────────────────────────┐
                    │         api-gateway (port 8000)              │
                    │  Auth · RBAC · Rate Limiting · Audit Log     │
                    │  Central REST API for all portal features    │
                    └──┬───────────────────────────┬──────────────┘
                       │ Internal HTTP              │ Internal HTTP
        ┌──────────────▼───────┐       ┌────────────▼────────────┐
        │  orchestrator (8001) │       │   All agent services    │
        │  LLM query pipeline  │──────▶│   (8002–8013, 8099)     │
        └──────────────────────┘       └─────────────────────────┘
```

**Architecture pattern:** The central `api-gateway` serves **all user-facing (portal) endpoints** through a single FastAPI `APIRouter`. Internal agent-to-agent communication happens on private Docker-network ports that are never exposed to the browser.

**Total central router endpoints: 40**
**Total internal service endpoints: 29**

---

## API Gateway Endpoints (VERIFIED_FROM_SOURCE)

The API Gateway runs on port 8000. All routes are defined in `services/api_gateway/routes.py`.

### Central Router Endpoints

Every endpoint below exists as a `@router` decorator in `routes.py`:

| # | Method | Path | Auth | Role/Permission | Handler Function | Line | Source |
|---|--------|------|------|-----------------|------------------|------|--------|
| 1 | GET | `/health` | No | None | `health()` | 522 | routes.py |
| 2 | POST | `/auth/login` | No | None | `login()` | 527 | routes.py |
| 3 | POST | `/query` | Yes | `get_current_user` | `submit_query()` | 568 | routes.py |
| 4 | GET | `/dashboard/overview` | Yes | `require_roles("business")` | `dashboard_overview()` | 659 | routes.py |
| 5 | GET | `/dashboard/kpis` | Yes | `require_roles("business")` | `dashboard_kpis()` | 695 | routes.py |
| 6 | GET | `/dashboard/recent-activity` | Yes | `require_roles("business")` | `dashboard_recent_activity()` | 776 | routes.py |
| 7 | GET | `/dashboard/charts/{chart_id}` | Yes | `require_roles("business")` | `dashboard_chart()` | 810 | routes.py |
| 8 | GET | `/kpi/catalog` | Yes | `require_roles("business")` | `kpi_catalog()` | 889 | routes.py |
| 9 | GET | `/kpi/dashboard` | Yes | `require_roles("business")` | `kpi_dashboard()` | 921 | routes.py |
| 10 | GET | `/kpi/values` | Yes | `require_roles("business")` | `kpi_values()` | 950 | routes.py |
| 11 | GET | `/kpi/metrics` | Yes | `require_roles("business")` | `kpi_metrics()` | 1003 | routes.py |
| 12 | GET | `/kpi/trends` | Yes | `require_roles("business")` | `kpi_trends()` | 1013 | routes.py |
| 13 | GET | `/kpi/{kpi_id}/insights` | Yes | `require_roles("business")` | `kpi_insights()` | 1039 | routes.py |
| 14 | GET | `/kpi/{kpi_id}` | Yes | `require_roles("business")` | `kpi_detail()` | 1056 | routes.py |
| 15 | GET | `/risk/overview` | Yes | `require_roles("business")` | `risk_overview()` | 1098 | routes.py |
| 16 | GET | `/risk/flags` | Yes | `require_roles("business")` | `risk_flags()` | 1140 | routes.py |
| 17 | GET | `/risk/segments` | Yes | `require_roles("business")` | `risk_segments()` | 1193 | routes.py |
| 18 | GET | `/risk/summary` | Yes | `require_roles("business")` | `risk_summary()` | 1222 | routes.py |
| 19 | GET | `/compliance/overview` | Yes | `require_roles("compliance")` | `compliance_overview()` | 1260 | routes.py |
| 20 | GET | `/compliance/report` | Yes | `require_roles("compliance")` | `compliance_report()` | 1304 | routes.py |
| 21 | GET | `/compliance/rules` | Yes | `require_roles("compliance")` | `compliance_rules()` | 1317 | routes.py |
| 22 | GET | `/compliance/violations` | Yes | `require_permission("read:pii")` | `compliance_violations()` | 1352 | routes.py |
| 23 | GET | `/audit/logs` | Yes | `require_permission("read:audit_logs")` | `audit_logs()` | 1406 | routes.py |
| 24 | GET | `/reports` | Yes | `require_roles("business")` | `list_reports()` | 1465 | routes.py |
| 25 | POST | `/reports/generate` | Yes | `require_permission("write:reports")` | `generate_report()` | 1515 | routes.py |
| 26 | GET | `/users/me` | Yes | `get_current_user` | `get_user_me()` | 1638 | routes.py |
| 27 | GET | `/auth/me` | Yes | `get_current_user` | `get_auth_me()` | 1647 | routes.py |
| 28 | GET | `/admin/users` | Yes | `require_roles("admin")` | `admin_users()` | 1704 | routes.py |
| 29 | GET | `/admin/users/{user_id}` | Yes | `require_roles("admin")` | `get_admin_user_detail()` | 1771 | routes.py |
| 30 | POST | `/admin/users` | Yes | `require_roles("admin")` | `create_admin_user()` | 1804 | routes.py |
| 31 | PATCH | `/admin/users/{user_id}` | Yes | `require_roles("admin")` | `update_admin_user()` | 1871 | routes.py |
| 32 | PATCH | `/admin/users/{user_id}/status` | Yes | `require_roles("admin")` | `update_admin_user_status()` | 1956 | routes.py |
| 33 | POST | `/admin/users/{user_id}/reset-password` | Yes | `require_roles("admin")` | `reset_admin_user_password()` | 2017 | routes.py |
| 34 | PATCH | `/admin/users/{user_id}/roles` | Yes | `require_roles("admin")` | `update_admin_user_role()` | 2060 | routes.py |
| 35 | POST | `/admin/roles` | Yes | `require_roles("admin")` | `create_admin_role()` | 2129 | routes.py |
| 36 | PATCH | `/admin/roles/{role_id}` | Yes | `require_roles("admin")` | `update_admin_role()` | 2173 | routes.py |
| 37 | PATCH | `/admin/roles/{role_id}/permissions` | Yes | `require_roles("admin")` | `update_role_permissions()` | 2234 | routes.py |
| 38 | GET | `/admin/roles` | Yes | `require_roles("admin")` | `admin_roles()` | 2299 | routes.py |
| 39 | GET | `/admin/permissions` | Yes | `require_roles("admin")` | `admin_permissions()` | 2338 | routes.py |
| 40 | GET | `/admin/activity` | Yes | `require_roles("admin")` | `admin_activity_log()` | 2375 | routes.py |

**Total: 40 endpoints**

### Internal Service Endpoints

| Service | Port | Endpoint | Method | Purpose |
|---------|------|----------|--------|---------|
| orchestrator-agent | 8001 | `/process_query` | POST | Query pipeline entry |
| orchestrator-agent | 8001 | `/health` | GET | Health check |
| orchestrator-agent | 8001 | `/ws/monitoring` | WS | Agent monitoring WebSocket |
| intent-agent | 8002 | `/process_intent` | POST | Intent classification |
| intent-agent | 8002 | `/health` | GET | Health check |
| schema-agent | 8003 | `/map_schema` | POST | Schema mapping |
| schema-agent | 8003 | `/health` | GET | Health check |
| entity-resolution-agent | 8004 | `/resolve_entities` | POST | Entity resolution |
| entity-resolution-agent | 8004 | `/health` | GET | Health check |
| sql-agent | 8005 | `/generate_sql` | POST | SQL generation |
| sql-agent | 8005 | `/health` | GET | Health check |
| validation-agent | 8006 | `/validate_query` | POST | Query validation |
| validation-agent | 8006 | `/health` | GET | Health check |
| execution-agent | 8007 | `/execute_query` | POST | Query execution |
| execution-agent | 8007 | `/health` | GET | Health check |
| audit-agent | 8008 | `/log_access` | POST | Audit logging |
| audit-agent | 8008 | `/health` | GET | Health check |
| embedding-service | 8009 | `/health` | GET | Health check |
| secrets-manager | 8010 | `/health` | GET | Health check (stub only) |
| compliance-agent | 8011 | `/check_compliance` | POST | Compliance check |
| compliance-agent | 8011 | `/health` | GET | Health check |
| audit-enhancement | 8012 | `/health` | GET | Health check |
| insights-agent | 8013 | `/generate_insights` | POST | Insights generation |
| insights-agent | 8013 | `/health` | GET | Health check |
| debug-service | 8099 | `/health` | GET | Health check |

---

## Non-existent Endpoints (Previously Claimed)

| Claimed Endpoint | Status | Evidence |
|-----------------|--------|----------|
| POST `/auth/logout` | DOES NOT EXIST | Not in routes.py |
| POST `/auth/refresh` | DOES NOT EXIST | Not in routes.py |
| GET `/documents/*` | DOES NOT EXIST | No document_store service |
| GET `/notifications/*` | DOES NOT EXIST | No notification_service service |
| GET `/settings/*` | DOES NOT EXIST (backend) | Settings page exists in frontend but no backend endpoint |
| GET `/analytics/*` | DOES NOT EXIST | No analytics_engine service |
| GET `/branches/*` | DOES NOT EXIST (backend) | Branches page exists in frontend but no dedicated backend endpoint |

---

## Frontend/Backend Contract Gaps

For each frontend API module, verify contract alignment:

| Frontend Module | API Calls | Backend Endpoint | Contract |
|----------------|-----------|-----------------|----------|
| auth.ts | `login` -> POST `/auth/login` | POST `/auth/login` | MATCHED |
| dashboard.ts | `getOverview` -> GET `/dashboard/overview` | GET `/dashboard/overview` | MATCHED |
| dashboard.ts | `getKPIs` -> GET `/dashboard/kpis` | GET `/dashboard/kpis` | MATCHED |
| dashboard.ts | `getRecentActivity` -> GET `/dashboard/recent-activity` | GET `/dashboard/recent-activity` | MATCHED |
| dashboard.ts | `getChart` -> GET `/dashboard/charts/{id}` | GET `/dashboard/charts/{chart_id}` | MATCHED |
| kpiApi.ts | `getCatalog` -> GET `/kpi/catalog` | GET `/kpi/catalog` | MATCHED |
| kpiApi.ts | `getDashboard` -> GET `/kpi/dashboard` | GET `/kpi/dashboard` | MATCHED |
| kpiApi.ts | `getValues` -> GET `/kpi/values` | GET `/kpi/values` | MATCHED |
| kpiApi.ts | `getMetrics` -> GET `/kpi/metrics` | GET `/kpi/metrics` | MATCHED |
| kpiApi.ts | `getTrends` -> GET `/kpi/trends` | GET `/kpi/trends` | MATCHED |
| riskApi.ts | `getOverview` -> GET `/risk/overview` | GET `/risk/overview` | MATCHED |
| riskApi.ts | `getFlags` -> GET `/risk/flags` | GET `/risk/flags` | MATCHED |
| riskApi.ts | `getSegments` -> GET `/risk/segments` | GET `/risk/segments` | MATCHED |
| riskApi.ts | `getSummary` -> GET `/risk/summary` | GET `/risk/summary` | MATCHED |
| complianceApi.ts | `getOverview` -> GET `/compliance/overview` | GET `/compliance/overview` | MATCHED |
| complianceApi.ts | `getRules` -> GET `/compliance/rules` | GET `/compliance/rules` | MATCHED |
| complianceApi.ts | `getViolations` -> GET `/compliance/violations` | GET `/compliance/violations` | MATCHED |
| complianceApi.ts | `getReport` -> GET `/compliance/report` | GET `/compliance/report` | MATCHED |
| reportsApi.ts | `list` -> GET `/reports` | GET `/reports` | MATCHED |
| reportsApi.ts | `generate` -> POST `/reports/generate` | POST `/reports/generate` | MATCHED |
| adminApi.ts | `getUsers` -> GET `/admin/users` | GET `/admin/users` | MATCHED |
| adminApi.ts | `getRoles` -> GET `/admin/roles` | GET `/admin/roles` | MATCHED |
| adminApi.ts | `getPermissions` -> GET `/admin/permissions` | GET `/admin/permissions` | MATCHED |
| adminApi.ts | `getActivity` -> GET `/admin/activity` | GET `/admin/activity` | MATCHED |
| profileApi.ts | `getMe` -> GET `/auth/me` | GET `/auth/me` | MATCHED |
| queryApi.ts | `submitQuery` -> POST `/query` | POST `/query` | MATCHED |

**Mark as mismatches if any frontend calls do not match backend routes.**

---

## RBAC Reference

The central router defines three role groups that gate access to endpoint domains:

| Role Group | Allowed Roles | Endpoint Domains |
|------------|--------------|-----------------|
| `business` | `analyst`, `manager`, `admin` | Dashboard, KPI, Risk, Reports |
| `compliance` | `compliance`, `admin` | Compliance, Audit |
| `admin` | `admin` | Admin (users, roles, permissions, activity) |

Additionally, fine-grained permission checks are used for:
- `read:pii` — compliance violations
- `read:audit_logs` — audit log viewer
- `write:reports` — report generation

**Default role hierarchy (from `UserRole` enum):**
```
analyst < manager < compliance < admin
```

All endpoints require JWT Bearer token authentication unless explicitly marked `Auth: No`.

---

## Service-to-Port Mapping

| Service | Container | Internal Port | Database |
|---------|-----------|---------------|----------|
| Frontend | `banking_frontend` | 80 (exposed as 3000) | — |
| API Gateway | `banking_api_gateway` | **8000** | postgres-main, postgres-audit |
| Orchestrator Agent | `banking_orchestrator` | **8001** | — (calls other agents) |
| Intent Agent | `banking_intent_agent` | **8002** | postgres-main (optional) |
| Schema Agent | `banking_schema_agent` | **8003** | postgres-main (optional) |
| Entity Resolution Agent | `banking_entity_resolution` | **8004** | postgres-main (optional) |
| SQL Agent | `banking_sql_agent` | **8005** | — |
| Validation Agent | `banking_validation_agent` | **8006** | — |
| Execution Agent | `banking_execution_agent` | **8007** | postgres-main, Redis |
| Audit Agent | `banking_audit_agent` | **8008** | postgres-audit |
| Embedding Service | `banking_embedding_service` | **8009** | postgres-embeddings |
| Secrets Manager | `banking_secrets` | **8010** | — (stub) |
| Compliance Agent | `banking_compliance_agent` | **8011** | postgres-main |
| Audit Enhancement | `banking_audit_enhancement` | **8012** | postgres-main, postgres-audit |
| Insights Agent | `banking_insights_agent` | **8013** | postgres-main |
| Debug Service | `banking_debug_service` | **8099** | — |
