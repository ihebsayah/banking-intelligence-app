# Architecture Validation Report

**Date:** 2026-07-25
**Scope:** Full system architecture review against implementation

---

## 1. System Overview

The Banking Intelligence System is a **multi-agent microservice pipeline** that translates natural language banking queries (English and French) into parameterized SQL, executes them against PostgreSQL, and returns role-filtered, PII-masked results with statistical insights.

### Design Philosophy
- Each agent is an independent FastAPI microservice
- No agent trusts any other
- Every SQL query is validated and HMAC-signed before execution
- Read-only: no data modification is possible through the system

---

## 2. Agent Responsibilities

| Agent | Port | Responsibility | Implementation Status |
|-------|------|----------------|----------------------|
| API Gateway | 8000 | JWT auth, routing, rate limiting | Complete |
| Orchestrator | 8001 | Pipeline coordination, 8-agent orchestration | Complete |
| Intent Agent | 8002 | NL classification, parameter extraction | Complete |
| Schema Agent | 8003 | Intent→domain→table mapping, join paths | Complete |
| Entity Resolution | 8004 | Business key resolution, join structure | Complete |
| SQL Agent | 8005 | Parameterized SQL generation | Complete |
| Validation Agent | 8006 | 5-check security + HMAC signing | Complete |
| Execution Agent | 8007 | Query execution, caching, PII masking | Complete |
| Audit Agent | 8008 | Immutable WORM audit logging | Complete |
| Embedding Service | 8009 | Vector embeddings for semantic search | Complete |
| Compliance Agent | 8011 | GDPR/PCI-DSS/SOX/AML/KYC checks | Complete |
| Audit Enhancement | 8012 | Extended audit analytics | Complete |
| Insights Agent | 8013 | Statistics, context, trends, NL summaries | Complete (template-driven) |
| Secrets Manager | 8010 | Secrets storage | Stub only |

---

## 3. Request Lifecycle

```
1. Client → POST /query (JWT + natural language query)
2. API Gateway → JWT verify → RBAC extraction → rate limit
3. Orchestrator → receives request, initializes pipeline
4. Intent Agent → classify intent (spaCy + keyword scoring + structured intent)
5. Gate Check → supported_capability? risk_level? requires_clarification?
6. Schema Agent → map intent to tables, columns, join paths
7. Entity Resolution → resolve business keys, construct JOIN structure
8. SQL Agent → generate parameterized SELECT query
9. Validation Agent → 5-check security + HMAC sign
10. Compliance Agent → GDPR/PCI-DSS/SOX/AML/KYC checks
11. Execution Agent → verify signature → cache check → execute → RBAC filter → PII mask → format
12. Insights Agent → statistics + context + trends + NL summary
13. Orchestrator → assemble final response
14. Audit Agent → immutable log entry
15. Client ← JSON response
```

---

## 4. Intent Pipeline

### Classification Methods (Two Independent Signals)

**Signal 1: Keyword Recognizer** (`intent_recognizer.py`)
- spaCy NLP tokenization + lemmatization
- 8 (or 11 with SEMANTIC_LAYER_ENABLED) banking domain keyword categories
- Confidence = token match density in top category
- Sets `requires_clarification = confidence < 0.85 or len(ambiguities) > 0`

**Signal 2: Structured Intent** (`structured_intent.py`)
- Rule-based domain detection from bilingual keyword tables
- Task extraction (aggregation, comparison, listing, etc.)
- Metric detection from user text
- Filter extraction (risk thresholds, account types, etc.)
- Time range extraction
- Sets `requires_clarification = len(ambiguities) > 0 and not has_explicit_intent`

### Merge Logic
- Structured intent fields are merged INTO keyword recognizer output
- `requires_clarification` can be overridden from True→False by structured intent when sufficient structure is detected
- Other fields use OR-merge for booleans

### Known Issue
The structured intent override makes the confidence gate's threshold check unreachable (see CONFIDENCE_CALIBRATION_AUDIT.md).

---

## 5. Schema Pipeline

The Schema Agent maps intent categories to database domains and tables:

| Intent Category | Domain | Tables |
|----------------|--------|--------|
| customer_analysis | customers | customers, accounts, kyc_status |
| risk_analysis | risk | risk_flags, credit_risk_scores, aml_flags |
| revenue_analysis | revenue | fees, commissions, interest_income, products |
| transaction_analysis | transactions | transactions, transaction_details |
| geographic_analysis | geography | branches, branch_locations, regions |
| product_analysis | products | products, accounts |
| compliance_analysis | compliance | risk_flags, kyc_cases, compliance_violations |
| operational_analysis | operations | branches, employees, accounts |

Join paths maintained as an adjacency graph with BFS discovery (when SEMANTIC_LAYER_ENABLED=True) or hardcoded static paths (when False).

---

## 6. Entity Resolution

Two modes:
- **Legacy** (SEMANTIC_LAYER_ENABLED=False): Hardcoded join key lookup, fixed transitive joins
- **Semantic** (SEMANTIC_LAYER_ENABLED=True): Business glossary normalization, BFS join discovery over join_registry graph

---

## 7. SQL Generation

- Template-based + dynamic WHERE/JOIN builder
- All filter values use `$N` parameterized placeholders
- Columns validated against per-table whitelist
- LIMIT clause always injected
- JOIN deduplication prevents duplicate JOIN clauses
- Metric formula injection (when SEMANTIC_LAYER_ENABLED=True)

---

## 8. Validation

### 5-Check Pipeline (all must pass)
1. **Syntax check** — sqlparse validates structure
2. **SELECT-only** — no DML/DDL allowed
3. **Keyword blacklist** — 30+ dangerous keywords blocked
4. **LIMIT clause** — prevents unbounded scans
5. **Pattern detection** — 22 regex patterns for injection, encoding, comment stripping

### HMAC Signing
Safe queries receive `sha256:HMAC_HEX:TIMESTAMP` signature. Execution Agent verifies before execution.

### Semantic Warnings (non-blocking, when SEMANTIC_LAYER_ENABLED=True)
- Unknown table references
- Raw arithmetic in SELECT

---

## 9. Compliance

Compliance Agent checks:
- GDPR: PII access logging, data minimization
- PCI-DSS: Card data masking, access logging
- SOX: Financial data audit trail
- AML: Suspicious activity pattern detection
- KYC: Customer verification status checks

---

## 10. Execution

Execution flow:
1. Verify HMAC signature
2. Check Redis cache (TTL 3600s)
3. Execute via asyncpg connection pool (30s timeout)
4. Apply row-level filter (role-based WHERE)
5. Apply column filter (role-based column list)
6. Apply PII masking (all roles except compliance)
7. Format output (JSON/CSV/ASCII table)
8. Store in Redis cache

Recovery mechanisms (Increment 3.1):
- Transient errors → retry once
- Mechanical SQL errors → repair (GROUP BY, syntax)
- Structural errors → replan request
- Verification against expected answers (advisory-only)

---

## 11. Audit

Every request creates an immutable audit record:
- User ID, role, action, query text
- Validation result, rows returned
- Execution time, IP address
- Write-only (WORM) — no DELETE endpoint

---

## 12. Insights

See INSIGHTS_AGENT_EVALUATION.md for detailed analysis.

Summary: Statistical computation is genuine. Context, trends, and recommendations are template-driven. NL summary depends on LLM availability (Ollama/tinyllama).

---

## 13. Semantic Layer

### Tables (in banking_dev database)
- `business_glossary` — synonym→canonical entity mapping
- `metric_registry` — KPI definitions with SQL formulas
- `table_metadata` — table descriptions and domain tags
- `column_metadata` — column descriptions and types
- `join_registry` — valid join paths between tables

### Current Status
**Fully disabled.** All 7 services with conditional semantic layer code have SEMANTIC_LAYER_ENABLED=false. The entire pipeline runs in hardcoded fallback mode. No semantic layer table queries are executed at runtime.

---

## 14. Embedding Layer

- pgvector extension on PostgreSQL (port 5434)
- Schema embeddings for semantic similarity search
- Used by Schema Agent and Entity Resolution Agent for fuzzy matching
- Independent of SEMANTIC_LAYER_ENABLED flag

---

## 15. Redis

Used for:
- Query result caching (TTL 3600s, SHA-256 keyed on sql+params)
- Schema metadata caching (per-service Redis databases 0-5)
- Session management

---

## 16. Databases

| Database | Port | Purpose | Technology |
|----------|------|---------|------------|
| banking_dev | 5432 | Primary banking data | PostgreSQL 16 |
| audit_logs | 5433 | Immutable audit records | PostgreSQL 16 |
| embeddings | 5434 | Vector embeddings | pgvector (PostgreSQL 16) |
| Redis | 6379 | Caching, sessions | Redis 7 |

### Schema: 20+ banking tables
- customers, accounts, transactions, branches, products
- risk_flags, aml_flags, fraud_detection, credit_risk_scores
- fees, commissions, interest_income
- kyc_cases, compliance_violations
- employees, loans, cards, beneficiaries
- Semantic layer tables: business_glossary, metric_registry, table_metadata, column_metadata, join_registry

---

## 17. Security Model

### Defense Layers
1. **JWT Authentication** — HS256 tokens with role, expiry, JTI
2. **Intent Gate** — adversarial/unsupported/ambiguous query rejection
3. **SQL Validation** — 5-check pipeline + HMAC signing
4. **Execution Verification** — HMAC signature check before SQL execution
5. **RBAC** — Role-based row filtering, column visibility, PII masking
6. **Compliance** — GDPR/PCI-DSS/SOX/AML/KYC checks

### Known Weaknesses
- Adversarial pattern detection misses conversational prompt injection
- DEV_MODE allows mock auth fallback (auth bypass under certain conditions)
- Mutation verbs not in unsupported capability list
- Confidence gate is dead code due to requires_clarification override

---

## 18. Deterministic vs. LLM Components

### Deterministic (No LLM)
- Schema Agent (static mapping)
- Entity Resolution (graph traversal)
- SQL Agent (template-based generation)
- Validation Agent (pattern matching)
- Execution Agent (query execution)
- Access Controller (role-based filtering)
- PII Masking (regex-based)

### LLM-Dependent
- Intent Agent (spaCy NLP — not LLM, but ML model)
- Insights Agent (Ollama/tinyllama for NL summaries)
- Orchestrator (optional LLM for plan refinement)

### Impact
The core pipeline (intent→schema→entity→SQL→validation→execution) is entirely deterministic. The LLM is only used for NL insight summaries, which have a template fallback. System reliability is not dependent on LLM availability.

---

## 19. Configuration

See CONFIGURATION_AUDIT.md for detailed analysis.

Key flags:
| Flag | Default | Benchmark Value | Effect |
|------|---------|-----------------|--------|
| DEV_MODE | True | True | Auth fallback to mock users |
| SEMANTIC_LAYER_ENABLED | False | False (mixed) | Gates semantic layer features |
| INTENT_CONFIDENCE_THRESHOLD | 0.31 | 0.31 | Confidence gate threshold (currently dead code) |
| ENABLE_INSIGHTS_AGENT | True | True | Insights pipeline on/off |
| ENABLE_COMPLIANCE_AGENT | True | True | Compliance checks on/off |

---

## 20. Benchmark Methodology

See BENCHMARK_METRIC_STANDARD.md for metric definitions.

### V1 Holdout (Tuned Data)
- 160 questions, system tuned on same questions
- Result: 160/160 (100%) — NOT an independent estimate
- Post-holdout fixes included threshold tuning (HIGH overfitting risk)

### V2 Blind (Unseen Data)
- 160 questions across 12 categories, written after system freeze
- System frozen at commit `55930e4`, tag `blind-v2-freeze`
- Result: 142/160 (88.8%) routing accuracy
- 113/115 (98.3%) supported query completion
- 29/45 (64.4%) safety rejection rate

### Limitations
- No SQL correctness scoring (only pipeline completion)
- No content quality scoring
- Single execution run (no repeatability measurement)
- Dry-run mode (SQL generation not always executed)
- Authorization tested with DEV_MODE=True (invalid)

---

## 21. Known Limitations

1. **Confidence gate is dead code** — requires_clarification override makes threshold unreachable
2. **Semantic layer fully disabled** — all 7 services have SEMANTIC_LAYER_ENABLED=false; hardcoded fallbacks used everywhere
3. **Insights are template-driven** — not genuine analytical reasoning
4. **Adversarial detection gaps** — misses conversational prompt injection
5. **No SQL correctness scoring** — pipeline completion ≠ correct results
6. **Authorization not tested** — DEV_MODE bypasses real auth
7. **Secrets Manager is a stub** — no actual secrets management
8. **Monitoring/observability empty** — no production monitoring
9. **Demo signing key** — `DEMO_KEY_CHANGE_IN_PRODUCTION_DO_NOT_USE_IN_PROD`
10. **Single LLM model** — Ollama/tinyllama for insights, no fallback

---

## 22. Future Work

### Critical (Before Production)
1. Fix confidence gate: ensure threshold is actually evaluated
2. Enable DEV_MODE=False for real authorization testing
3. Enforce authorization on all requests (no mock fallback)
4. Expand adversarial pattern detection
5. Add mutation verb detection

### Important (Before Wider Deployment)
6. Enable SEMANTIC_LAYER_ENABLED across all services (currently all `false`, semantic layer tables seeded but never queried)
7. Replace insights template with query-specific analysis
8. Add SQL correctness scoring to benchmarks
9. Implement Secrets Manager
10. Add monitoring and observability

### Quality (Ongoing)
11. French spaCy model for FR query parity
12. Multi-column insights analysis
13. Period-over-period comparison
14. Benchmark repeatability testing
