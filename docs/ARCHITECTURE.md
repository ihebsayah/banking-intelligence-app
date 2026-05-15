# Architecture — Banking Intelligence System

## Overview

Banking Intelligence System is a **9-agent microservice pipeline** that translates natural language banking queries into secure, role-filtered SQL results. Built on FastAPI, PostgreSQL, Redis, and Docker.

**Design philosophy:** Each agent does one thing well. No agent trusts any other. Every SQL query is validated + HMAC-signed before execution.

---

## System Components

### Infrastructure Layer
| Component | Port | Role |
|-----------|------|------|
| API Gateway | 8000 | JWT auth, rate limiting, request routing |
| Audit Agent | 8001 | Immutable WORM audit log (PostgreSQL) |
| PostgreSQL Main | 5432 | Primary banking data store |
| PostgreSQL Embeddings | 5433 | Vector embeddings for semantic search |
| Redis | 6379 | Query result caching (TTL 3600s) |

### Intelligence Layer (The Pipeline)
| Agent | Port | Responsibility |
|-------|------|----------------|
| Intent Agent | 8002 | Classify NL query into 1 of 8 categories |
| Schema Agent | 8003 | Map intent → database domain → tables |
| Entity Resolution | 8004 | Resolve join paths using business keys |
| SQL Agent | 8005 | Generate parameterized SQL (never raw values) |
| Validation Agent | 8006 | 5-check security + HMAC sign approved queries |
| Execution Agent | 8007 | Execute, cache, mask PII, format results |

---

## Data Flow

```
User (natural language query)
         │
         ▼ POST /query + JWT
┌─────────────────────────────┐
│       API Gateway :8000     │  JWT verify + rate limit
│   audit every request       │  → logs to Audit Agent
└─────────────┬───────────────┘
              │ HTTP forward
              ▼
┌─────────────────────────────┐
│   Orchestrator :8008        │  Coordinates 6 agents
└─────────────┬───────────────┘
              │
    ┌─────────┴──────────┐
    ▼                    │
┌──────────────┐         │
│ Intent :8002 │         │
│ category +   │         │
│ confidence   │         │
└──────┬───────┘         │
       │                 │
       ▼                 │
┌──────────────┐         │
│ Schema :8003 │         │
│ domain →     │         │
│ tables +     │         │
│ join paths   │         │
└──────┬───────┘         │
       │                 │
       ▼                 │
┌──────────────────┐     │
│ Entity Res :8004 │     │
│ semantic IDs +   │     │
│ join structure   │     │
└──────┬───────────┘     │
       │                 │
       ▼                 │
┌──────────────┐         │
│ SQL  :8005   │         │
│ parameterized│         │
│ SELECT only  │         │
└──────┬───────┘         │
       │                 │
       ▼                 │
┌──────────────────┐     │
│ Validation :8006 │     │
│ 5 checks +       │     │
│ HMAC signature   │     │
└──────┬───────────┘     │
       │                 │
       ▼                 ▼
┌──────────────────────────┐
│ Execution Agent :8007    │
│ ┌──────┐ ┌────────────┐ │
│ │Cache │ │AccessCtrl  │ │
│ │Redis │ │PII Masking │ │
│ └──────┘ └────────────┘ │
│ ┌──────────────────────┐│
│ │  asyncpg Pool → PG   ││
│ └──────────────────────┘│
└──────────────────────────┘
              │
              ▼
   JSON / CSV / ASCII Table
   + metadata (rows, time_ms, source)
```

---

## Security Model

### 5-Layer SQL Validation
Every SQL query must pass ALL five checks before receiving an HMAC signature:

1. **Syntax check** — Valid parseable SQL
2. **SELECT-only** — Statement type must be SELECT (no DML/DDL)
3. **Keyword blacklist** — 30+ dangerous keywords instantly rejected (DROP, DELETE, UNION, EXEC, SLEEP, BENCHMARK, etc.)
4. **LIMIT clause** — All queries must include LIMIT (prevents unbounded scans)
5. **Injection patterns** — Regex patterns block OR 1=1, time-based blind, comment injection, null bytes

### HMAC Query Signing
After validation, the Validation Agent signs the query:
```
signature = sha256:HMAC(SIGNING_KEY, sql + "|" + sorted_params):timestamp
```
The Execution Agent verifies this signature before any query runs. A tampered query = signature mismatch = rejected.

### Role-Based Access Control (RBAC)

| Role | Row Filter | Column Visibility | PII Masking |
|------|-----------|-------------------|-------------|
| `compliance` | None (sees all) | All columns | Disabled (sees raw) |
| `analyst` | None (sees all) | Curated business columns | Enabled |
| `manager` | None (simplified) | Curated + management cols | Enabled |
| `customer` | Own rows only (customer_id filter) | Limited personal cols | Enabled |

### PII Masking
Applied automatically for all roles except `compliance`:
- **SSN** `123-45-6789` → `***-**-6789`
- **Credit card** `4532-1234-5678-9012` → `****-****-****-9012`
- **Email** `alice@bank.com` → `a***@bank.com`
- **Phone** `+1-555-123-4567` → `+1-***-***-4567`

---

## Agent Details

### Intent Recognition Agent (Port 8002)
**Technology:** Pattern matching + spaCy NLP  
**Input:** Natural language query string  
**Output:** `{primary_category, secondary_categories, confidence, explicit_constraints}`

Classifies queries into 8 banking domains:
- `customer_analysis` — customer demographics, segments, KYC
- `risk_analysis` — credit risk, AML flags, fraud scores
- `revenue_analysis` — fees, commissions, interest income
- `transaction_analysis` — payment volumes, transaction patterns
- `geographic_analysis` — branch locations, regional performance
- `product_analysis` — loan products, account types, uptake
- `compliance_analysis` — regulatory reports, KYC status
- `operational_analysis` — branch performance, employee metrics

### Schema Understanding Agent (Port 8003)
**Technology:** Static domain-table mapping (deterministic)  
**Input:** Intent categories  
**Output:** Tables, key columns, join path graph

Maps each intent category → database domain → specific tables. Maintains a join graph for 20+ tables with correct ON conditions.

### Entity Resolution Agent (Port 8004)
**Technology:** Semantic business-key mapping  
**Input:** Primary entity + table list  
**Output:** Primary key, join structure with conditions

Resolves which tables share business keys (`customer_id`, `account_id`, etc.) and constructs semantically correct JOIN paths.

### SQL Generation Agent (Port 8005)
**Technology:** Template + dynamic WHERE/JOIN builder  
**Guarantees:**
- All filter values use `?` placeholders (never interpolated)
- LIMIT clause always present
- Columns validated against per-table whitelist
- No raw SQL in the output (structure only)

### Validation Agent (Port 8006)
**Technology:** sqlparse + custom regex patterns  
**Checks:** 5 checks described above  
**Output:** `{safe, issues, checks_passed, checks_failed, signature, sanitized_sql}`

The only agent that can produce a signature. Without a valid signature, Execution Agent rejects the query.

### Execution Agent (Port 8007)
**Technology:** asyncpg (connection pool) + Redis (cache-aside)  
**Cache TTL:** 3600 seconds (1 hour)  
**Timeout:** 30 seconds per query

Execution flow:
1. Verify HMAC signature
2. Check Redis cache (cache hit → return immediately)
3. Get connection from asyncpg pool
4. Execute query with 30s timeout
5. Apply row filter per role
6. Apply column filter per role
7. Apply PII masking (if not compliance)
8. Format result (JSON/CSV/table)
9. Store in Redis cache
10. Return with metadata

---

## Performance Characteristics

| Metric | Target | Achieved |
|--------|--------|----------|
| First query (pipeline) | < 5s | ~1-3s (with Docker) |
| Cached query | < 500ms | ~10-50ms |
| Validation (local) | < 100ms | ~1-5ms |
| PII masking 1K rows | < 500ms | ~30ms |
| 5 concurrent users | All complete | ✅ (tested) |
| Memory (100 queries) | Stable | ✅ (no leak) |

---

## Technology Choices

| Choice | Rationale |
|--------|-----------|
| **FastAPI** | Async, automatic OpenAPI docs, Pydantic validation |
| **asyncpg** | Fastest PostgreSQL driver for Python, native async |
| **Redis** | Sub-millisecond cache reads, TTL built-in |
| **HMAC-SHA256** | Standard, proven query signing (no external deps) |
| **Docker Compose** | Reproducible local + production deployments |
| **Pydantic v2** | Runtime type validation at service boundaries |
| **Pattern matching** | Deterministic intent classification (no ML model needed) |
| **sqlparse** | SQL parsing for syntax and type detection |

---

## Database Schema Summary

### Main Database (PostgreSQL :5432)
Core banking tables organized by domain:

**Customer domain:** `customers`, `customer_segments`  
**Account domain:** `accounts`, `account_types`  
**Transaction domain:** `transactions`, `transaction_details`  
**Risk domain:** `risk_flags`, `aml_flags`, `fraud_detection`, `credit_risk_scores`  
**Revenue domain:** `fees`, `commissions`, `interest_income`, `products`  
**Geography domain:** `branches`, `branch_locations`, `branch_performance`, `regions`  
**Compliance domain:** `kyc_status`, `audit_logs`, `regulatory_reports`  

### Embeddings Database (PostgreSQL :5433)
- `schema_embeddings` — Vector representations of table/column descriptions
- Used by Embedding Service for semantic similarity search

---

## Audit Logging

Every request is logged immutably:
- User ID, role, action type
- Query text (before validation)
- Validation result
- Rows returned
- Execution time
- IP address

Audit logs are write-only (WORM) — no delete API endpoint exists.

---

## Extending the System

To add a new agent:
1. Create `services/your_agent/` with `main.py`, `models.py`, `requirements.txt`, `Dockerfile`
2. Add service to `docker-compose.yml`
3. Register endpoint in Orchestrator's pipeline
4. Add unit tests in `tests/test_your_agent.py`
5. Update Schema Agent's `INTENT_TO_DOMAINS` if adding new intent category
