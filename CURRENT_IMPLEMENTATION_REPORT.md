# CURRENT IMPLEMENTATION REPORT
## Banking Intelligence System — As-Built Technical Reference

> **Generated**: 2026-07-10  
> **Method**: Produced exclusively by inspecting actual source code, SQL init files, Docker configuration, and frontend source. Nothing in this document is inferred from plans or conversation history.  
> **Status Legend**: ✅ Implemented | ⚠️ Stub / Partial | ❌ Not Implemented

---

## 1. Repository Layout

```
banking-intelligence-system/
├── frontend/                     # React/TypeScript SPA (Vite)
├── services/
│   ├── shared/                   # Shared Python library (config, DB, models, logger, Redis, Mistral client)
│   ├── api_gateway/              # FastAPI gateway — port 8000
│   ├── orchestrator_agent/       # Pipeline orchestrator — port 8001
│   ├── intent_agent/             # NL intent classifier — port 8002
│   ├── schema_agent/             # Schema resolver — port 8003
│   ├── entity_resolution_agent/  # Entity resolver — port 8004
│   ├── sql_agent/                # SQL generator — port 8005
│   ├── validation_agent/         # SQL validator — port 8006
│   ├── execution_agent/          # SQL executor + Redis cache — port 8007
│   ├── audit_agent/              # Audit log writer — port 8008
│   ├── embedding_service/        # Sentence-transformer embeddings — port 8009
│   ├── secrets_manager/          # Stub only — port 8010
│   ├── compliance_agent/         # Compliance checker — port 8011
│   ├── audit_enhancement/        # Data lineage + compliance reporter — port 8012
│   ├── insights_agent/           # Statistical analysis + Mistral summaries — port 8013
│   └── debug_service/            # Debug/trace endpoint — port 8099
├── init/                         # SQL init + seed files
└── docker-compose.yml
```

---

## 2. Infrastructure & Runtime

### 2.1 Docker Services (from `docker-compose.yml`)

| Service | Image / Built From | Port | Purpose |
|---|---|---|---|
| `frontend` | `./frontend` | 3000 | React SPA (Nginx) |
| `api-gateway` | `./services/api_gateway` | 8000 | FastAPI gateway |
| `orchestrator-agent` | `./services/orchestrator_agent` | 8001 | Pipeline orchestrator |
| `debug-service` | `./services/debug_service` | 8099 | Debug trace viewer |
| `intent-agent` | `./services/intent_agent` | 8002 | Intent classifier |
| `schema-agent` | `./services/schema_agent` | 8003 | Schema resolver |
| `entity-resolution-agent` | `./services/entity_resolution_agent` | 8004 | Entity resolver |
| `sql-agent` | `./services/sql_agent` | 8005 | SQL generator |
| `validation-agent` | `./services/validation_agent` | 8006 | SQL validator |
| `execution-agent` | `./services/execution_agent` | 8007 | SQL executor |
| `audit-agent` | `./services/audit_agent` | 8008 | Audit log writer |
| `embedding-service` | `./services/embedding_service` | 8009 | Vector embeddings |
| `secrets-manager` | `./services/secrets_manager` | 8010 | **STUB — not implemented** |
| `insights-agent` | `./services/insights_agent` | 8013 | Insights + LLM |
| `compliance-agent` | `./services/compliance_agent` | 8011 | Compliance checker |
| `audit-enhancement` | `./services/audit_enhancement` | 8012 | Lineage + reports |
| `postgres-main` | `postgres:15` | 5432 | Main banking DB |
| `postgres-audit` | `postgres:15` | 5433 | Audit logs DB |
| `postgres-embeddings` | `pgvector/pgvector` | 5434 | Vector DB |
| `redis` | `redis:7-alpine` | 6379 | Query result cache |
| `ollama` | `ollama/ollama` | 11434 | Local Mistral LLM |

### 2.2 Networking

- All services communicate on a single Docker bridge network: `banking-network`.
- CORS is set to `allow_origins=["*"]` on all FastAPI services (development configuration).

---

## 3. Database Layer

### 3.1 `postgres-main` — `banking_dev` (port 5432)

**Core tables** (`postgres-main-init.sql`):

| Table | Key Columns |
|---|---|
| `customers` | `customer_id`, `name`, `email`, `kyc_verified`, `risk_score`, `segment`, `created_at` |
| `accounts` | `account_id`, `customer_id`, `account_type`, `status`, `balance`, `available_balance`, `currency`, `branch_id` |
| `transactions` | `transaction_id`, `account_id`, `customer_id`, `amount`, `transaction_type`, `status`, `transaction_date` |
| `risk_flags` | `customer_id`, `flag_type`, `severity` (low/medium/high/critical), `description`, `resolved` |
| `branches` | `branch_id`, `name`, `state`, `city`, `address`, `manager_id` |
| `products` | product catalogue |
| `compliance_rules` | regulatory rule definitions |
| `compliance_violations` | open/closed violations |
| `data_lineage` | per-field GDPR access records |
| `regulatory_reports` | GDPR/SOX report storage |

**Users & KPI tables** (`02-users-kpis.sql`):

| Table | Purpose |
|---|---|
| `roles` | Role definitions (analyst, compliance, manager, admin) |
| `permissions` | Individual permission keys |
| `role_permissions` | Junction table: role → permissions |
| `users` | Authenticated user accounts with `password_hash`, `status`, `must_change_password` |
| `user_activity_log` | Admin action audit trail |
| `kpi_categories` | KPI grouping taxonomy |
| `kpi_owners` | KPI steward registry |
| `kpi_definitions` | KPI formula, description, status, owner |
| `kpi_thresholds` | Healthy/warning/critical ranges per KPI |
| `kpi_history` | Historical KPI value snapshots |

**Semantic layer tables** (`03-semantic-layer.sql`):

| Table | Purpose |
|---|---|
| `business_glossary` | Business term definitions |
| `metric_registry` | Named metric registry |
| `table_metadata` | Human-readable table documentation |
| `column_metadata` | Human-readable column documentation |
| `join_registry` | Known join paths between tables |

**Loan domain** (`04-loan-domain.sql`):

`loan_products`, `loan_contracts`, `loan_installments`, `loan_repayments`, `loan_delinquency_events`, `loan_restructuring`, `collateral`, `guarantees`, `provisions`, `non_performing_loans`

> ⚠️ Loan domain tables exist in the schema but **are not queried by any running service or frontend page**. No loan-specific API endpoint exists in `routes.py`.

**KYC/AML domain** (`05-kyc-aml-domain.sql`):

`kyc_cases`, `kyc_documents`, `kyc_reviews`, `kyc_verifications`, `kyc_expirations`, `pep_screening`, `sanctions_screening`, `aml_alerts`, `suspicious_activity_reports`, `compliance_cases`, `compliance_reviews`, `audit_findings`

> ⚠️ KYC/AML domain tables exist but **are not directly queried by any dedicated service endpoint**. They are queryable through the NL assistant pipeline.

**Finance/GL domain** (`06-finance-gl-domain.sql`):

`general_ledger`, `ledger_entries`, `fee_income`, `interest_income`, `operating_expenses`, `profitability_metrics`, `balance_sheet_snapshots`, `income_statement_snapshots`

> ⚠️ GL domain tables exist but **are not directly queried by any service endpoint**. Queryable via NL assistant only.

**Extended org/customer tables** (`07-org-customer-ext.sql`):

`regions`, `departments`, `business_units`, `employees`, `relationship_managers`, `customer_profiles`, `customer_segments`, `customer_addresses`, `customer_contacts`, `customer_risk_scores`, `customer_relationships`, `customer_documents`, `customer_preferences`, `customer_status_history`, `account_types`, `account_balances`, `account_status_history`, `joint_accounts`, `account_signatories`

> ⚠️ Extended org tables exist but **are not queried by any explicit service endpoint**. Queryable via NL assistant only.

**Seed data** (`09-tunisian-banking-data-seed.sql`): Population of Tunisian banking demo data into core tables.

### 3.2 `postgres-audit` — `audit_logs` (port 5433)

| Table | Purpose |
|---|---|
| `audit_log` | Immutable record of every API call, query execution, login event |

Columns: `id`, `audit_id`, `user_id`, `user_role`, `action`, `query_intent`, `tables_accessed`, `rows_accessed`, `execution_time_ms`, `status`, `ip_address`, `endpoint`, `http_method`, `timestamp`

### 3.3 `postgres-embeddings` — `embeddings` (port 5434) — pgvector

| Table | Purpose |
|---|---|
| `schema_embeddings` | 384-dim embeddings for tables and semantic entities |
| `domain_categories` | 384-dim embeddings for query domain labels |
| `semantic_id_mappings` | Alias → canonical entity ID mappings |

---

## 4. Shared Library (`services/shared/`)

All Python microservices import from this package.

| Module | What It Provides |
|---|---|
| `config.py` | `Settings` (pydantic-settings): all env vars with defaults. Loaded once via `@lru_cache`. |
| `models.py` | Shared Pydantic models: `User`, `UserRole`, `AuditLogEntry`, `QueryRequest`, `QueryResult`, `LoginRequest/Response`, `HealthResponse` |
| `database.py` | `DatabaseConnector` — asyncpg connection pool wrapper with `fetch_one`, `fetch_all`, `execute` |
| `errors.py` | Exception hierarchy: `BankingBaseError`, `AuthenticationError`, `AuthorizationError`, `TokenExpiredError`, `InvalidTokenError` |
| `logger.py` | Structured JSON logger (`get_logger`) |
| `redis_client.py` | `RedisClient` — async Redis wrapper for caching and pub/sub |
| `mistral_client.py` | HTTP client to local Ollama `/api/generate` |

### Key Configuration Values (from `config.py` defaults)

| Setting | Default Value |
|---|---|
| `DATABASE_URL` | `postgresql://banking_user:securepass123@localhost:5432/banking_dev` |
| `AUDIT_DATABASE_URL` | `postgresql://audit_user:securepass123@localhost:5433/audit_logs` |
| `EMBEDDINGS_DATABASE_URL` | `postgresql://embedding_user:securepass123@localhost:5434/embeddings` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `MISTRAL_API_URL` | `http://localhost:11434` |
| `MISTRAL_MODEL` | `mistral` |
| `JWT_SECRET_KEY` | `change-this-in-production-do-not-use-in-prod` ⚠️ |
| `JWT_ALGORITHM` | `HS256` |
| `JWT_EXPIRE_MINUTES` | `480` (8 hours) |
| `DEV_MODE` | `True` |
| `SEMANTIC_LAYER_ENABLED` | `False` |
| `ENABLE_INSIGHTS_AGENT` | `True` |
| `ENABLE_COMPLIANCE_AGENT` | `True` |
| `ENABLE_CACHING` | `True` |

---

## 5. Backend Services (Detailed)

### 5.1 API Gateway (`services/api_gateway/` — port 8000)

**Framework**: FastAPI  
**Rate limiting**: 100 requests/minute per IP (slowapi)  
**CORS**: `allow_origins=["*"]`  
**Middleware**: Every request (except `/health`, `/docs`, `/redoc`) is logged to `audit-agent` via `httpx`.  

**Authentication** (`auth.py`):
- Password hashing: bcrypt via `passlib`
- Token format: HS256 JWT with claims `sub` (user_id), `role`, `iat`, `exp`, `jti`
- Primary auth: queries `users` table in `postgres-main`
- Fallback: in-memory `MOCK_USERS` store when `DEV_MODE=True` and DB is unreachable
- Mock users defined: `analyst_001`, `analyst_002`, `compliance_001`, `manager_001`, `admin_001` (all share same bcrypt hash)

**Startup**: On startup, `apply_migrations()` runs `init/02-users-kpis.sql` against `postgres-main`.

**All Defined API Routes** (from `routes.py`):

| Method | Path | Function | Auth Required |
|---|---|---|---|
| GET | `/health` | `health` | No |
| POST | `/auth/login` | `login` | No |
| POST | `/query` | `submit_query` | JWT |
| GET | `/dashboard/overview` | `dashboard_overview` | JWT |
| GET | `/dashboard/kpis` | `dashboard_kpis` | JWT |
| GET | `/dashboard/recent-activity` | `dashboard_recent_activity` | JWT |
| GET | `/dashboard/charts/{chart_id}` | `dashboard_chart` | JWT |
| GET | `/kpi/catalog` | `kpi_catalog` | JWT |
| GET | `/kpi/dashboard` | `kpi_dashboard` | JWT |
| GET | `/kpi/values` | `kpi_values` | JWT |
| GET | `/kpi/metrics` | `kpi_metrics` | JWT |
| GET | `/kpi/trends` | `kpi_trends` | JWT |
| GET | `/kpi/{kpi_id}/insights` | `kpi_insights` | JWT |
| GET | `/kpi/{kpi_id}` | `kpi_detail` | JWT |
| GET | `/risk/overview` | `risk_overview` | JWT |
| GET | `/risk/flags` | `risk_flags` | JWT |
| GET | `/risk/segments` | `risk_segments` | JWT |
| GET | `/risk/summary` | `risk_summary` | JWT |
| GET | `/compliance/overview` | `compliance_overview` | JWT |
| GET | `/compliance/report` | `compliance_report` | JWT |
| GET | `/compliance/rules` | `compliance_rules` | JWT |
| GET | `/compliance/violations` | `compliance_violations` | JWT |
| GET | `/audit/logs` | `audit_logs` | JWT |
| GET | `/reports` | `list_reports` | JWT |
| POST | `/reports/generate` | `generate_report` | JWT |
| GET | `/users/me` | `get_user_me` | JWT |
| GET | `/auth/me` | `get_auth_me` | JWT |
| GET | `/admin/users` | `admin_users` | JWT |
| GET | `/admin/users/{user_id}` | `get_admin_user_detail` | JWT |
| POST | `/admin/users` | `create_admin_user` | JWT |
| PATCH | `/admin/users/{user_id}` | `update_admin_user` | JWT |
| PATCH | `/admin/users/{user_id}/status` | `update_admin_user_status` | JWT |
| POST | `/admin/users/{user_id}/reset-password` | `reset_admin_user_password` | JWT |
| PATCH | `/admin/users/{user_id}/roles` | `update_admin_user_role` | JWT |
| POST | `/admin/roles` | `create_admin_role` | JWT |
| PATCH | `/admin/roles/{role_id}` | `update_admin_role` | JWT |
| PATCH | `/admin/roles/{role_id}/permissions` | `update_role_permissions` | JWT |
| GET | `/admin/roles` | `admin_roles` | JWT |
| GET | `/admin/permissions` | `admin_permissions` | JWT |
| GET | `/admin/activity` | `admin_activity_log` | JWT |

> ❌ `/branches`, `/queries/history` — **Called by the frontend but not defined in `routes.py`**. Branches fall back to hardcoded `MOCK_BRANCHES` in `frontend/src/api/branches.ts`. Query history falls back gracefully to "unavailable" state in the UI.

> ❌ `/auth/logout` — Called by frontend `auth.ts` but **not defined** as a route. The call is fire-and-forget with a silent catch, so it does not break logout flow.

> ❌ `/dashboard/refresh` — Called by `frontend/src/api/dashboard.ts` but **not defined** in `routes.py`.

> ❌ `/test/sql` — Called by the dev `agents.ts` API module but **not a defined route** (the debug service at port 8099 may handle this).

**KPI Service** (`kpi_service.py`):  
A self-contained class `KPIService` implements live computation for all KPIs directly from the database. Computed KPIs:

| KPI ID | Computation Method |
|---|---|
| `total_deposits` | `SUM(balance) FROM accounts` |
| `monthly_revenue` | `SUM(ABS(amount)) * 0.002 FROM transactions` (last 30 days) |
| `active_customers` | `COUNT(DISTINCT customer_id) FROM accounts WHERE status='active'` |
| `avg_risk_score` | `AVG(risk_score) FROM customers` |
| `kyc_compliance_rate` | verified/total customers × 100 |
| `total_risk_flags` | `COUNT(*) FROM risk_flags WHERE resolved=FALSE` |
| `customer_growth_rate` | (current 30d new - prior 30d new) / prior × 100 |
| `customer_retention_rate` | active accounts / total customers × 100 |
| `compliance_score` | `100 - (violations × 10)` |
| `transaction_volume` | `COUNT(*) FROM transactions` (last 30 days) |
| `avg_transaction_amount` | `AVG(ABS(amount)) FROM transactions` (last 30 days) |

Threshold evaluation: compares live value against `kpi_thresholds` table rows, returns `healthy` / `warning` / `critical` / `unknown`.  
Time-series trend data is supported for: `monthly_revenue`, `transaction_volume`, `avg_transaction_amount`, `total_deposits`, `active_customers`, `kyc_compliance_rate`.

---

### 5.2 Orchestrator Agent (`services/orchestrator_agent/` — port 8001)

**Framework**: FastAPI  
**Role**: Receives NL queries from API Gateway and coordinates the full 8-step agent pipeline.

**Pipeline steps** (executed sequentially via HTTP calls to agents):

1. **intent-agent** (port 8002) → classify query intent
2. **schema-agent** (port 8003) → resolve relevant tables
3. **entity-resolution-agent** (port 8004) → resolve named entities
4. **sql-agent** (port 8005) → generate SQL
5. **validation-agent** (port 8006) → validate SQL
6. **execution-agent** (port 8007) → execute SQL + Redis cache lookup
7. **compliance-agent** (port 8011) → check compliance (if `ENABLE_COMPLIANCE_AGENT=True`)
8. **insights-agent** (port 8013) → generate statistical analysis + Mistral summary (if `ENABLE_INSIGHTS_AGENT=True`)

After pipeline completion:
- A request record is saved to the query history store (Redis or DB)
- An audit log entry is sent to **audit-agent** (port 8008)

Each pipeline step result is collected and returned as `pipeline_steps[]` in the final response, enabling the frontend to display the agent trace.

**Redis caching**: Execution agent checks Redis for identical SQL query results before hitting the database.

---

### 5.3 Intent Agent (`services/intent_agent/` — port 8002)

**Framework**: FastAPI  
**Model**: `all-MiniLM-L6-v2` (384-dim sentence-transformer) via `EmbeddingComputer`  
**Method**: Cosine similarity between the query embedding and pre-computed domain category embeddings.

**Implemented intent categories** (8 domains):

| Domain | Description |
|---|---|
| `customer_analysis` | Customer data, segments, demographics |
| `risk_analysis` | Fraud, defaults, AML/KYC violations |
| `revenue_analysis` | Income, fees, commissions, profitability |
| `operational_analysis` | Transaction volume and throughput |
| `geographic_analysis` | Branch, region, city, state queries |
| `product_analysis` | Banking product and account type queries |
| `compliance_analysis` | Regulatory compliance, audit findings |
| `transaction_analysis` | Payments, wire transfers, ACH flows |

---

### 5.4 Schema Agent (`services/schema_agent/` — port 8003)

**Framework**: FastAPI  
**Method**: Combines vector similarity search against `schema_embeddings` table (postgres-embeddings) with keyword-based fallback matching.  
**Output**: List of relevant table names from the banking schema.

---

### 5.5 Entity Resolution Agent (`services/entity_resolution_agent/` — port 8004)

**Framework**: FastAPI  
**Function**: Resolves named entities (customer names, branch names, segment labels) from the NL query into canonical database IDs/values.  
**Data source**: Queries `customers`, `branches`, `products` tables + `semantic_id_mappings` in the embeddings DB.

---

### 5.6 SQL Agent (`services/sql_agent/` — port 8005)

**Framework**: FastAPI  
**Method**: Template-based SQL generation + Mistral LLM fallback.  
**Input**: intent category, resolved tables, resolved entities, original query text.  
**Output**: One raw SQL string.

**SQL generation strategy** (from `sql_generator.py`):
- Primary: Intent-specific SQL templates with entity injection
- Fallback: Mistral LLM prompt → `SELECT … FROM … WHERE … LIMIT 50`
- Hard safety limit: `LIMIT 50` always injected if not present

---

### 5.7 Validation Agent (`services/validation_agent/` — port 8006)

**Framework**: FastAPI  
**Function**: Validates generated SQL before execution.

**Checks performed** (from `sql_validator.py`):
1. Statement must start with `SELECT` (no DDL/DML allowed)
2. Disallowed keywords: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`, `TRUNCATE`, `EXEC`, `EXECUTE`
3. Must reference at least one known table from the schema whitelist
4. No raw `*` wildcard SELECT (forces explicit column selection unless overridden)
5. `LIMIT` clause required — injected automatically if missing (max 50)
6. Basic SQL parse check (parentheses balance)

---

### 5.8 Execution Agent (`services/execution_agent/` — port 8007)

**Framework**: FastAPI  
**Function**: Executes validated SQL against `postgres-main`.

**Caching**:
- Checks Redis for SHA256 hash of the SQL string before DB execution
- Cache TTL: configurable (default 300s)
- On cache hit: returns cached rows without touching the DB

**Output**: Raw result rows + row count + execution time in ms.

---

### 5.9 Audit Agent (`services/audit_agent/` — port 8008)

**Framework**: FastAPI  
**Endpoint**: `POST /log_access`  
**Function**: Receives `AuditLogEntry` objects from the API Gateway middleware and from the orchestrator after each pipeline run.  
**Storage**: Inserts into the `audit_log` table in `postgres-audit`.  
**Isolation**: Uses a dedicated asyncpg pool connecting to `postgres-audit` only.

---

### 5.10 Embedding Service (`services/embedding_service/` — port 8009)

**Framework**: FastAPI  
**Model**: `all-MiniLM-L6-v2` (sentence-transformers, 384-dim vectors)

**Endpoints**:
- `POST /embed` — compute embedding for a single text string
- `POST /similarity` — cosine similarity between two text strings
- `GET /health`

**On startup**: Pre-computes and stores embeddings for 8 domains, 20 tables, and 7 semantic entities into `postgres-embeddings`. Operation is idempotent (DELETE + INSERT).

---

### 5.11 Compliance Agent (`services/compliance_agent/` — port 8011)

**Framework**: FastAPI  
**Function**: Checks query results and SQL against compliance rules stored in the `compliance_rules` table.

Checks for:
- PII exposure (access to `pii`-tagged columns without `read:pii` permission)
- Large transaction monitoring thresholds
- AML flag exposure rules
- Role-based data access restrictions

---

### 5.12 Audit Enhancement (`services/audit_enhancement/` — port 8012)

**Framework**: FastAPI  
Contains two components:

**DataLineageTracker** (`data_lineage_tracker.py`):
- Records per-field, per-table data access into `data_lineage` table
- Supports GDPR right-to-access audit trail

**ComplianceReporter** (`compliance_reporter.py`):
- `generate_gdpr_report(user_id, days)` — queries `data_lineage` + `audit_log`, stores in `regulatory_reports`
- `generate_sox_report(days)` — queries `audit_log` by role, stores in `regulatory_reports`
- Report types generated: `GDPR_Right_to_Access`, `SOX_Access_Log`

---

### 5.13 Insights Agent (`services/insights_agent/` — port 8013)

**Framework**: FastAPI  
Contains three components:

**StatisticalAnalyzer** (`statistical_analyzer.py`):
- Auto-detects numeric columns in result rows
- Computes: `total_sum`, `average`, `median`, `std_dev`, `min`, `max`, `p25`, `p50`, `p75`, `p90`, `p99`
- Outlier detection: values > 2 standard deviations from mean

**ContextGatherer** (`context_gatherer.py`):
- Queries `postgres-main` for system-wide totals: `total_deposits`, `total_customers`, `total_transactions`
- Builds `regional_breakdown` from `branches` grouped by state
- Builds `segment_breakdown` from `customers` grouped by segment

**MistralIntegrator** (`mistral_integrator.py`):
- Calls local Ollama at `MISTRAL_API_URL/api/generate` with `stream=False`, `temperature=0.6`, `num_predict=400`
- `generate_summary()` — produces a 2–3 sentence executive summary; falls back to a dynamic template if Mistral is unavailable
- `generate_recommendations()` — produces exactly 3 numbered recommendations; falls back to data-driven template recommendations

---

### 5.14 Secrets Manager (`services/secrets_manager/` — port 8010)

**Status**: ❌ **STUB ONLY**  
Only exposes `GET /health` returning `{"status": "healthy", "note": "Credential management — Week 2"}`.  
All POST routes return `501 Not Implemented`.  
No actual secret storage or retrieval is implemented.

---

### 5.15 Debug Service (`services/debug_service/` — port 8099)

Exposes pipeline trace inspection endpoints used by the frontend developer tools (`/dev/debug`). Allows looking up a full request trace by `request_id`.

---

## 6. Query Processing Pipeline (End-to-End)

```
User types NL query in Assistant page
    ↓
Frontend → POST /query to API Gateway (port 8000) with {query, user_role}
    ↓
API Gateway authenticates JWT, extracts user_id + role
    ↓
API Gateway → POST to Orchestrator (port 8001)
    ↓
Orchestrator runs sequential pipeline:
  1. Intent Agent   → classify domain (customer/risk/revenue/...)
  2. Schema Agent   → find relevant tables (vector + keyword)
  3. Entity Agent   → resolve named entities to DB IDs
  4. SQL Agent      → generate SQL (template or Mistral)
  5. Validation     → check SELECT-only, no DDL, table whitelist, LIMIT ≤50
  6. Execution      → Redis cache check → asyncpg execute on postgres-main
  7. Compliance     → check PII/AML/role rules
  8. Insights       → statistics + Mistral summary + recommendations
    ↓
Orchestrator returns: {results, insights, pipeline_steps, request_id, metadata}
    ↓
API Gateway middleware sends AuditLogEntry → Audit Agent (port 8008)
    ↓
Response returned to frontend with:
  - result rows (table/chart/JSON/CSV viewable)
  - statistical insights + summary
  - executive recommendations
  - agent pipeline trace
  - debug_url linking to debug service
```

---

## 7. Frontend Application

**Framework**: React 18 + TypeScript + Vite  
**Styling**: Tailwind CSS (utility classes used throughout)  
**State management**: Zustand (`authStore`, `branchStore`, `bankingQueryStore`)  
**HTTP client**: Axios (`apiClient` in `frontend/src/api/client.ts`)  
**Charts**: Recharts  
**Auth persistence**: JWT stored in `localStorage` under key `auth_token`; Zustand store also persisted in `localStorage` under `banking-auth`

### 7.1 Routing Structure (`App.tsx`)

Three layout zones:

| Path Pattern | Layout | Role Required |
|---|---|---|
| `/login` | No layout | None |
| `/unauthorized` | No layout | None |
| `/dev/*` | Developer sidebar + header | `admin` only |
| All other paths | Banking sidebar | Authenticated user |

**Business Portal Routes**:

| Path | Component | Role Required |
|---|---|---|
| `/`, `/dashboard` | `BankingDashboard` | Any authenticated |
| `/branches` | `Branches` | Any authenticated |
| `/assistant` | `Assistant` | Any authenticated |
| `/kpi` | `KpiPage` | Any authenticated |
| `/kpi-governance` | `KpiGovernancePage` | analyst, manager, compliance, admin |
| `/risk` | `RiskPage` | analyst, manager, compliance, admin |
| `/compliance` | `CompliancePage` | compliance, manager, admin |
| `/reports` | `ReportsPage` | manager, admin |
| `/admin` | `AdminPage` | admin only |
| `/profile` | `ProfilePage` | Any authenticated |
| `/settings` | `Settings` | Any authenticated |

**Developer Routes**:

| Path | Component | Role Required |
|---|---|---|
| `/dev` | `Dashboard` | admin |
| `/dev/query` | `QueryTester` | admin |
| `/dev/agents` | `AgentMonitorPage` | admin |
| `/dev/performance` | `PerformanceMonitor` | admin |
| `/dev/settings` | `Settings` | admin |
| `/dev/debug` | `DebugPage` | admin |

### 7.2 Authentication Flow

1. User submits username + password on `LoginPage`
2. Frontend calls `POST /auth/login`
3. On success, `authStore.setUser(user, token)` stores user object and token in Zustand + `localStorage`
4. `ProtectedRoute` reads `authStore.isAuthenticated` and `user.role` on every route change
5. Unauthenticated → redirect to `/login`; wrong role → redirect to `/unauthorized`

### 7.3 Frontend Pages — API Consumption

| Page | API Calls |
|---|---|
| `Assistant` | `POST /query`, `GET /queries/history` (optional, degrades gracefully) |
| `KpiPage` | `GET /kpi/values`, `GET /kpi/catalog`, `GET /kpi/trends` |
| `KpiGovernancePage` | `GET /kpi/dashboard`, `GET /kpi/catalog`, `GET /kpi/{id}`, `GET /kpi/{id}/insights`, `GET /kpi/trends` |
| `RiskPage` | `GET /risk/overview`, `GET /risk/segments`, `GET /risk/flags` (paginated) |
| `CompliancePage` | `GET /compliance/overview`, `GET /compliance/rules`, `GET /compliance/violations`, `GET /audit/logs` |
| `ReportsPage` | `GET /reports`, `POST /reports/generate` |
| `AdminPage` | `GET /admin/users`, `POST /admin/users`, `PATCH /admin/users/*`, `GET /admin/roles`, `POST /admin/roles`, `PATCH /admin/roles/*`, `GET /admin/permissions`, `GET /admin/activity`, `GET /health` |
| `Branches` | `GET /branches` (API — **not implemented** → falls back to `MOCK_BRANCHES`) |
| `BankingDashboard` | `GET /dashboard/overview`, `GET /dashboard/kpis`, `GET /dashboard/recent-activity`, `GET /dashboard/charts/{id}` |
| `ProfilePage` | `GET /users/me` |
| `Settings` | Local state only |

### 7.4 Real-Time Features

**WebSocket**: `useWebSocket` hook is initialized once in `AppShell`. The hook connects to the backend WebSocket endpoint and pushes events into the app. The WebSocket endpoint definition is in `routes.py` or `orchestrator_agent` (not fully inspected here).

### 7.5 Assistant Page Features

- Chat-style UI with user/assistant message bubbles
- 15 pre-loaded suggested queries across 5 categories (Customer, Risk, Revenue, Operations, Compliance)
- Results displayed in 4 tabs: Table, Chart (Recharts bar chart), JSON, CSV download
- Executive Insights panel: summary, key metrics grid, trends, anomalies, recommendations
- Agent Pipeline Trace: visual bar chart of each step's execution time
- Query history sidebar (from `GET /queries/history`)
- All numeric columns auto-formatted: monetary (>$1M shows $XM notation), counts with thousand separators

---

## 8. RBAC Summary

### Backend Roles (defined in shared `UserRole` enum)

| Role | Key Permissions |
|---|---|
| `analyst` | read:customers, read:accounts, read:transactions, read:risk_flags |
| `compliance` | all analyst permissions + read:audit_logs, read:pii |
| `manager` | all analyst permissions + read:branch_data, read:risk_summary |
| `admin` | all permissions + admin:users, admin:roles |

### Frontend Route Guard

`ProtectedRoute` component checks `user.role` against `requiredRole` prop (string or string[]). Wrong role → `/unauthorized` with context about which role was required.

### Backend JWT

- Every protected route reads `Authorization: Bearer <token>` header
- `verify_token()` in `auth.py` decodes and validates HS256 JWT
- `user_id` and `user_role` are extracted and attached to `request.state` for middleware logging

---

## 9. Caching Strategy

**Redis** (`redis:7-alpine`, port 6379):
- Used by **Execution Agent** to cache SQL query results
- Cache key: SHA256 of the SQL string
- Cache TTL: configurable via `Settings.REDIS_URL` environment

> No session-level caching, no frontend caching layer (beyond browser default).

---

## 10. Embedding & Semantic Layer

### Vector Embeddings

- Model: `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional)
- Stored in: `postgres-embeddings` (pgvector extension)
- Pre-computed on startup by `embedding_service`
- Used by: `intent-agent` (domain classification), `schema-agent` (table relevance)
- Similarity metric: cosine similarity

### Semantic Layer

- Tables `business_glossary`, `metric_registry`, `table_metadata`, `column_metadata`, `join_registry` exist in `postgres-main`
- **`SEMANTIC_LAYER_ENABLED=False`** in config defaults — the semantic layer tables are populated but not actively used in pipeline routing

---

## 11. Not Implemented / Stubs

| Feature | Status | Evidence |
|---|---|---|
| Secrets Manager (credential vault) | ❌ Stub only | `secrets_manager/main.py` — all POST routes return 501 |
| `/branches` API endpoint | ❌ Not in `routes.py` | Frontend falls back to `MOCK_BRANCHES` hardcoded data |
| `/queries/history` endpoint | ❌ Not in `routes.py` | Frontend shows "History service not available" |
| `/auth/logout` endpoint | ❌ Not in `routes.py` | Frontend call is silently ignored |
| `/dashboard/refresh` endpoint | ❌ Not in `routes.py` | Frontend call would fail |
| Loan domain API endpoints | ❌ No routes defined | Tables created in `04-loan-domain.sql` but no service queries them |
| Finance/GL domain API endpoints | ❌ No routes defined | Tables created in `06-finance-gl-domain.sql` |
| KYC/AML dedicated endpoints | ❌ No routes defined | Tables exist; data queryable via NL assistant only |
| Extended org/customer endpoints | ❌ No routes defined | Tables exist; queryable via NL assistant only |
| Semantic layer routing | ❌ `SEMANTIC_LAYER_ENABLED=False` | Feature flag disabled |
| Token revocation (JTI blocklist) | ❌ Not implemented | `jti` claim generated in JWT but never checked against a blocklist |
| Refresh tokens | ❌ Not implemented | Only access tokens issued |
| Password change flow | ❌ `must_change_password` column exists but no endpoint | Column in `users` table; no force-change API |
| Multi-tenant data isolation | ❌ Not implemented | Single shared schema |
| PDF/Excel report export | ❌ Not implemented | `POST /reports/generate` creates DB records only, no file output |

---

## 12. Security Observations (As-Built)

| Item | Current State |
|---|---|
| JWT secret | Default value `change-this-in-production-do-not-use-in-prod` in config (must be overridden via env) |
| CORS | `allow_origins=["*"]` on all services |
| SQL injection | Mitigated: all user SQL is generated internally; `asyncpg` uses parameterized queries |
| DDL/DML injection | Mitigated: `ValidationAgent` blocks all non-SELECT statements |
| PII access | Partially mitigated: compliance agent checks `read:pii` permission |
| Audit trail | ✅ Every API request logged to immutable `audit_log` table |
| Data lineage | ✅ Per-field access logged to `data_lineage` table (GDPR support) |
| Rate limiting | ✅ 100 req/min per IP on API Gateway |
| Password hashing | ✅ bcrypt via passlib |
| Timing attack mitigation | ✅ Dummy hash verification when user not found |

---

*End of As-Built Report*
