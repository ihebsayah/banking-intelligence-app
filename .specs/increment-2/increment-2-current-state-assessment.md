# Increment 2 — Current State Assessment

## Why This Exists
The platform today is a **read-only consultation dashboard**. Inc 2 makes it an **operational platform** where Analyst, Compliance Officer, and Admin workbenches drive real actions — alerts, investigations, compliance cases, tasks.

## Architecture Summary

### Backend: `services/`
| Service | Role | Port |
|---------|------|------|
| `api_gateway` | FastAPI main app → all routes, auth, business logic | 8000 |
| `orchestrator` | AI query pipeline — intent→schema→entity→SQL→validation→execution→insights | 8001 |
| `compliance_agent` | GDPR/PCI/SOX/AML/KYC checks via LLM | 8010 |
| `audit_agent` | Immutable audit trail for queries | 8012 |
| `insights_agent` | NLP insight generation from query results | 8014 |
| `schema_agent` | DB schema introspection | 8004 |
| `entity_agent` | Entity resolution (customer, account, etc.) | 8005 |
| `sql_agent` | NL→SQL generation | 8006 |
| `validation_agent` | SQL validation | 8007 |
| `execution_agent` | SQL execution | 8008 |
| `intent_agent` | Query intent classification | 8003 |

### Frontend: `Frontend/src/`
- React 18 + TypeScript + Vite
- Chakra UI + Tailwind CSS
- Zustand stores (auth, dashboard, kpi, risk, compliance, reports, admin, assistant, theme)
- Axios API client (dynamic base URL from env)
- React Router v6 with lazy-loaded pages
- 17 pages, all read-only

### Database: PostgreSQL `banking_dev`
23 existing tables — analytical/reporting entities only. No operational workflow tables.

### Auth
- Dual path: Legacy HS256 JWT (`auth.py`) + Keycloak RS256/JWKS (`keycloak_auth.py`)
- `UserRole` enum: `analyst`, `manager`, `compliance`, `admin`, `unmapped`
- Granular `permissions` table with `role_permissions` junction
- `get_current_user` dependency in every router

## What Exists (good)
- Dashboard: 3 KPI cards, recent queries, risk summary
- KPI: full CRUD for definitions, thresholds, owners, categories, history
- Risk: risk flags, heatmap, trends, scenario analysis
- Compliance: rules engine, violations, regulatory reports, data lineage
- Reports: scheduled/generated reports
- Admin: user management (CRUD), role assignment, system config
- AI Assistant: natural-language query → SQL → results → insights (full agent pipeline)
- Audit logging: immutable `audit_logs` DB for all queries
- Permissions: granular `read:*`, `write:*`, `admin:*` with role-permission mapping

## What's Missing (Inc 2 scope)

### No operational domain entities
- `alerts`, `investigations`, `compliance_cases`, `tasks`, `evidence`, `decisions`
- `watchlists`, `watchlist_items`, `saved_analyses`
- `notifications`, `remediation_actions`
- `activity_timeline`, `assignments`, `comments`

### No workflow state
- No alert lifecycle (triggered→acknowledged→investigating→resolved)
- No case lifecycle (open→under_review→escalated→closed)
- No task management (pending→in_progress→completed→verified)
- No investigation workflow (draft→active→completed→archived)

### No operational APIs
- Endpoints exist for analytics/read but not for create/update/transition/assign

### Frontend is read-only
- No forms to create alerts, investigations, cases, tasks
- No workbench layout (inbox, queue, actions)
- No notification UI

### Role mismatch
- `manager` role exists in enums/DB but is not in Inc 2 spec (3 roles: analyst, compliance, admin)
- Decision needed: merge manager into admin or keep as-is

## Key Technical Constraints
- `models.py` uses SQLAlchemy 2.0 async with `async def` operations
- Router pattern: `APIRouter(prefix="/api/v1/...")` with `Depends(get_current_user)`
- No Alembic — schema is `init/*.sql` run at container start
- Redis available for caching/queues (existing `redis_client.py`)
- AI agents communicate as HTTP microservices (not message queue)
- Frontend stores use `create()` from Zustand with `devtools` middleware
- All API calls go through typed client modules in `src/api/`

## Existing Routes Inventory
See `services/api_gateway/routes.py` — ~200+ endpoints across 18 routers. All are read-heavy. No operational mutation endpoints exist.
