# Banking Intelligence System

> AI-powered NL-to-SQL banking intelligence platform.
> Natural language → 6-agent pipeline → PostgreSQL → structured results.

---

## Quick Start

```bash
# 1. Copy env template
cp .env.example .env
# Edit .env — set real secrets before running

# 2. Start all services
docker compose up -d

# 3. Verify
curl http://localhost:8000/health
# → {"service":"api-gateway","status":"healthy"}

# 4. Login
curl -X POST http://localhost:8000/auth/login \
  -d "username=analyst_001&password=password"
# → {"access_token": "eyJ...", "user_role": "analyst"}

# 5. Query
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me high-risk customers in New York", "format": "json"}'
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend  (React/TS/Vite)                    :3000              │
│  BankingDashboard · Branches · Assistant                         │
│  Developer tools at /dev/* (no auth guard)                       │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTP/REST
┌─────────────────────▼───────────────────────────────────────────┐
│  API Gateway  (FastAPI)                       :8000              │
│  JWT auth · Rate limiting (100/min) · Audit middleware           │
│  Routes: POST /auth/login · POST /query · GET /health · /users/me │
│          /dashboard/* · /kpi/* · /risk/* · /compliance/*         │
│          /audit/logs · /reports/* · /admin/*                    │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTP
┌─────────────────────▼───────────────────────────────────────────┐
│  Orchestrator Agent  (FastAPI)                :8001              │
│  Coordinates full 6-agent NL-to-SQL pipeline                    │
└──┬──────┬──────┬──────┬──────┬───────┬────────────────────────┘
   │      │      │      │      │       │
   ▼      ▼      ▼      ▼      ▼       ▼
Intent  Schema  Entity  SQL   Valid.  Compli.  Execution
:8002   :8003   :8004  :8005  :8006   :8011    :8007
spaCy   embed.  pgvec  Mist.  safety  GDPR     RBAC+mask
                             /rules  PCI SOX   DB query
                                               └→ Audit :8008
                                               └→ Insights :8013

Support:
  Embedding Service   :8009  (sentence-transformers)
  Secrets Manager     :8010
  Debug Service       :8099  (WebSocket dev tool)
```

### Databases

| DB | Port | Contents |
|---|---|---|
| postgres-main | 5432 | customers · accounts · transactions · risk_flags · branches · compliance_rules |
| postgres-audit | 5433 | audit_log (all access events) |
| postgres-embeddings | 5434 | schema_embeddings · entity_embeddings (pgvector) |
| redis | 6379 | query cache (DB 0–5, per service) |
| ollama | 11434 | mistral model (local LLM) |

---

## Service Port Map

| Port | Service |
|---|---|
| 3000 | Frontend (Nginx) |
| 8000 | API Gateway |
| 8001 | Orchestrator |
| 8002 | Intent Agent |
| 8003 | Schema Agent |
| 8004 | Entity Resolution Agent |
| 8005 | SQL Agent |
| 8006 | Validation Agent |
| 8007 | Execution Agent |
| 8008 | Audit Agent |
| 8009 | Embedding Service |
| 8010 | Secrets Manager |
| 8011 | Compliance Agent |
| 8012 | Audit Enhancement |
| 8013 | Insights Agent |
| 8099 | Debug Service |
| 5432 | postgres-main |
| 5433 | postgres-audit |
| 5434 | postgres-embeddings |
| 6379 | Redis |
| 11434 | Ollama |

---

## Mock & DB Users

The API Gateway queries the real `users` table populated by `init/02-users-kpis.sql` for active users. If the database is temporarily unreachable, it falls back to the local mock user store.

| Username | Password | Role | Permissions |
|---|---|---|---|
| admin_001 | password | admin | read: customers, accounts, transactions, risk_flags, audit_logs, pii, admin:users, admin:roles |
| compliance_001 | password | compliance | read: customers, accounts, transactions, risk_flags, audit_logs, pii |
| manager_001 | password | manager | read: customers, accounts, transactions, branch_data, risk_summary |
| analyst_001 | password | analyst | read: customers, accounts, transactions, risk_flags |
| analyst_002 | password | analyst | read: customers, accounts, transactions |

> **Warning:** Plaintext passwords for demo/testing only. Use hashed passwords (e.g. bcrypt) in production.

---

## Running Tests

```bash
# Install test requirements (no Docker needed — stubs in conftest.py)
cd banking-intelligence-system
pip install pytest pytest-asyncio

# Run the complete Portal Endpoints test suite (52 tests)
pytest tests/test_portal_endpoints.py -v

# Run all tests
pytest tests/ -v
```

---

## Environment Variables

See `.env.example` for full list. Key variables:

```bash
JWT_SECRET_KEY=<256-bit random>           # CHANGE THIS
QUERY_SIGNING_KEY=<random>                # CHANGE THIS
MISTRAL_MODEL=mistral                     # or mistral:7b-instruct
LOG_LEVEL=INFO                            # DEBUG for dev
ENABLE_INSIGHTS_AGENT=false              # enable when stable
```

---

## Project Structure

```
banking-intelligence-system/
├── services/
│   ├── api_gateway/          ← JWT auth, rate limiting, audit middleware
│   ├── orchestrator/         ← Master agent, pipeline coordinator
│   ├── intent_agent/         ← NL intent classification
│   ├── schema_agent/         ← Table/column mapping
│   ├── entity_resolution_agent/ ← Entity normalization
│   ├── sql_agent/            ← SQL generation (Mistral)
│   ├── validation_agent/     ← SQL safety validation
│   ├── execution_agent/      ← DB execution, RBAC, masking
│   ├── audit_agent/          ← Access logging
│   ├── compliance_agent/     ← GDPR/PCI/SOX/AML/KYC checks
│   ├── insights_agent/       ← LLM narrative (Phase 2)
│   ├── audit_enhancement/    ← Lineage + compliance reports (Phase 2)
│   ├── embedding_service/    ← Sentence embeddings
│   ├── secrets_manager/      ← Secret rotation
│   └── shared/               ← config, models, errors, logger, redis, db
├── frontend/                 ← React/TS/Vite + Tailwind
├── init/                     ← DB init SQL scripts
├── tests/                    ← pytest unit + integration tests
├── docs/                     ← API docs, architecture, security
├── monitoring/               ← Prometheus/Grafana (planned)
├── docker-compose.yml
├── .env                      ← Never commit — use .env.example
├── CURRENT_STATE.md          ← Architecture audit
└── PLATFORM_ROADMAP.md       ← Phase planning
```

---

## Current Status

- **Phase 1 (NL-to-SQL pipeline):** ✅ Complete and operational
- **Phase 2 (Insights, Compliance, Audit Enhancement):** 🔄 Services deployed, integration partial
- **Phase 3 (Stabilization):** 🔜 In progress — see PLATFORM_ROADMAP.md

See [CURRENT_STATE.md](./CURRENT_STATE.md) for full audit.
See [PLATFORM_ROADMAP.md](./PLATFORM_ROADMAP.md) for next steps.
See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for deep-dive.
