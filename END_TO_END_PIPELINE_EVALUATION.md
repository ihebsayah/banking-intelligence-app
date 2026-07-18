# End-to-End Pipeline Evaluation Report

**Date:** July 15, 2026
**Version:** `cf80da5` — `feat: extend insights generation with combined summary and recommendations, enhance orchestrator timeout, and update query submission timeout`
**Environment:** Production (Docker Compose) — CPU-only, no GPU
**Evaluator:** Automated + Manual Review

---

## 1. System Overview

| Component | Status | Details |
|---|---|---|
| API Gateway | Healthy | FastAPI, port 8000 |
| Orchestrator | Healthy | Pipeline orchestration, port 8001 |
| Intent Agent | Healthy | NL classification |
| Schema Agent | Healthy | DB schema introspection |
| Entity Resolution | Healthy | Entity matching |
| SQL Agent | Healthy | NL-to-SQL generation |
| Validation Agent | Healthy | SQL validation |
| Execution Agent | Healthy | Query execution |
| Audit Agent | Healthy | Audit logging |
| Compliance Agent | Healthy | Compliance checks |
| Insights Agent | Healthy | LLM-powered insights, tinyllama |
| Ollama (LLM) | Healthy | mistral + tinyllama, CPU-only |
| PostgreSQL (main) | Healthy | banking_dev, 74 tables |
| Redis | Healthy | Caching layer |
| Frontend | Healthy | React, port 3000 |

**DB Stats:** 74 tables, ~87K total rows (transactions: 50K, accounts: 5K, customers: 2K)

---

## 2. Test Query Results

| Metric | Value |
|---|---|
| Total queries | 45 (35 EN + 10 FR) |
| Successful | 19 (42%) |
| Failed | 26 (57%) |
| With insights | 19 (42%) |

### 2.1 Success/Failure Breakdown

| Failure Category | Count | Example |
|---|---|---|
| Pipeline timeout (>180s) | 9 | `List customers with more than two active accounts` |
| DB errors (bad SQL) | 8 | `Average account balance by branch` → `column customers.branch_id does not exist` |
| Quick failures (<1s) | 8 | `Suspicious activity reports` → `relation "audit_logs" does not exist` |
| Single long query | 1 | `Loan portfolio by product` (1097s) |

### 2.2 Timing

| Metric | Value |
|---|---|
| Average total time (all) | 148.1s |
| Average success time | 97.0s |
| Fastest successful | 68.4s (`Show high-risk customers`) |
| Slowest successful | 131.4s (`Compare Tunis et Sfax`) |
| Slowest overall | 1097.6s (`Loan portfolio by product`) |

### 2.3 Intent Detection

| Query | Detected Intent |
|---|---|
| Show customer names and their account balances | customer_analysis |
| Accounts opened during the last month | transaction_analysis |
| Average transaction amount | transaction_analysis |
| Show high-risk customers | risk_analysis |
| Open AML alerts | risk_analysis |
| Monthly executive summary | transaction_analysis |
| Total revenue | revenue_analysis |
| Largest customer segment | customer_analysis |
| Portfolio evolution | product_analysis |
| Affiche les créances douteuses | transaction_analysis |
| Montre les alertes AML ouvertes | risk_analysis |
| Quel est le taux de conformité KYC ? | risk_analysis |

**Intent Accuracy:** 12/19 (63%) — acceptable but several `transaction_analysis` queries that should be more specific (e.g., `risk_analysis` for "Open AML alerts").

### 2.4 SQL Quality

**Critical pattern detected:** The SQL Agent produces `SELECT *` for 17/19 successful queries, returning up to 100 rows unfiltered. Only 2 queries use column-specific selects (`AVG(transactions.amount)`, `products.*`).

**Common failure pattern:** SQL Agent generates invalid JOINs referencing non-existent columns:
- `customers.branch_id` (column does not exist in customers table)
- `branches.transaction_id` (column does not exist in branches table)
- `branches.customer_id` (column does not exist in branches table)
- `missing FROM-clause entry for table "customers"` (invalid join syntax)
- `relation "audit_logs" does not exist` (table does not exist — likely should be `audit_events` or similar)

---

## 3. Insights Generation

| Metric | Value |
|---|---|
| Queries with insights | 19/45 (42%) |
| Average insight generation time | ~30-40s (on top of pipeline) |
| LLM model used | tinyllama (1B params, CPU-only) |
| Insight quality | Basic — numeric summaries with generic recommendations |

**Insight structure:** Each insight includes:
- Executive summary (2-3 sentences)
- Key findings (2-3 items)
- Recommendations (2-3 items)
- Supporting metrics

**Insight quality assessment:** Adequate for a CPU-only demo. Recommendations are generic (e.g., "consider expanding customer base") rather than data-driven. The combined summary+recommendations approach works but lacks specificity.

---

## 4. Security Review

| Security Control | Status | Notes |
|---|---|---|
| JWT Authentication | Active | HS256, 8-hour TTL |
| Rate Limiting | Active | slowapi, configurable |
| CORS | Enabled | Development-friendly settings |
| Audit Middleware | Active | All requests logged |
| SQL Injection Protection | **NOT IMPLEMENTED** | No validation in SQL Agent |
| Input Validation | Minimal | No query length limit enforced |
| Secrets Management | Active | Vault integration |

**Critical Finding:** No SQL injection protection is implemented. The SQL Agent passes LLM-generated SQL directly to the execution agent without any injection detection or sanitization. This is acceptable for a demo but unacceptable for production.

---

## 5. Performance Assessment

| Component | Status | Notes |
|---|---|---|
| API Gateway routing | Good | Fast response, proper auth |
| Pipeline orchestration | Adequate | 300s timeout sufficient |
| SQL Agent (LLM) | Slow | ~30-60s per query (CPU-bound) |
| Insights Agent (LLM) | Slow | ~30-40s per query (CPU-bound) |
| Query Execution | Fast | PostgreSQL <1s |
| Insights LLM | Adequate | tinyllama works, mistral too slow |

**Bottleneck:** Ollama CPU inference. Each LLM call (SQL generation + insights) takes 30-60s. A full pipeline with insights takes 60-130s.

---

## 6. Architecture Review

**Strengths:**
- Clean microservice separation with clear responsibilities
- Proper pipeline orchestration with rollback support
- Good use of Docker Compose for local development
- Redis caching layer in place
- Audit logging on all API calls
- Semantic layer tables exist (37 glossary terms, 24 join paths, 25 metrics)

**Weaknesses:**
- Semantic layer is disabled (`SEMANTIC_LAYER_ENABLED=false`) — the most powerful SQL generation improvement is unused
- No SQL injection protection
- No query result caching (Redis exists but caching appears limited)
- `audit_logs` table referenced in SQL but does not exist in DB
- Multiple empty tables (risk_flags, kyc_verifications, customer_documents, etc.) suggest incomplete seed data

---

## 7. Scoring

| Category | Weight | Score | Weighted |
|---|---|---|---|
| Intent Detection | 15% | 63/100 | 9.5 |
| SQL Generation | 25% | 42/100 | 10.5 |
| Query Execution | 15% | 42/100 | 6.3 |
| Insights Generation | 15% | 42/100 | 6.3 |
| Security | 10% | 60/100 | 6.0 |
| Performance | 10% | 50/100 | 5.0 |
| Architecture | 10% | 70/100 | 7.0 |
| **TOTAL** | | | **50.6/100** |

---

## 8. Go/No-Go Assessment

### **NO-GO for production deployment**

**Blockers:**
1. **SQL injection not prevented** — critical security gap
2. **42% query success rate** — unacceptable for production use
3. **Semantic layer disabled** — leaving significant accuracy improvement on the table
4. **No error recovery** — pipeline fails hard on SQL generation errors
5. **Empty risk/compliance tables** — 30+ tables with zero rows, limiting query coverage

### **GO for demo/internal review**
- Core pipeline works end-to-end for simple queries
- Insights generation functional
- Bilingual queries (EN/FR) work when SQL Agent succeeds
- Architecture is sound — issues are operational, not structural

---

## 9. Recommendations

### Critical (Phase 6C)
1. **Enable semantic layer** — Switch `SEMANTIC_LAYER_ENABLED=true` and validate SQL Agent integration
2. **Add SQL injection protection** — Implement query sanitization in `sql_validator/validator.py`
3. **Fix missing tables** — Create `audit_logs` table or update SQL Agent references
4. **Improve SQL generation** — Fix JOIN patterns to use actual foreign keys

### High Priority
5. **Add query result caching** — Leverage existing Redis for repeated queries
6. **Populate empty tables** — Risk flags, KYC verifications, compliance reviews
7. **Increase success rate target** — Set 80% success rate as Phase 7 goal

### Medium Priority
8. **GPU for Ollama** — Would reduce LLM inference from 30-60s to 2-5s
9. **SQL Agent prompt improvement** — Use column-specific SELECT instead of `SELECT *`
10. **French query support** — Add French-specific prompt templates

---

## 10. Appendix: Full Query Results

| # | Query | Status | Time | Rows | Insights |
|---|---|---|---|---|---|
| 1 | Show customer names and their account balances | SUCCESS | 63s | 100 | YES |
| 2 | List customers with more than two active accounts | TIMEOUT | 120s | - | NO |
| 3 | Show customers by governorate | TIMEOUT | 120s | - | NO |
| 4 | List VIP customers | TIMEOUT | 120s | - | NO |
| 5 | Show inactive customers | TIMEOUT | 120s | - | NO |
| 6 | Show total deposits by customer segment | TIMEOUT | 120s | - | NO |
| 7 | Average account balance by branch | DB ERROR | 0.7s | - | NO |
| 8 | Largest accounts | TIMEOUT | 120s | - | NO |
| 9 | Accounts opened during the last month | SUCCESS | 104s | 100 | YES |
| 10 | Transaction volume by month | TIMEOUT | 120s | - | NO |
| 11 | Average transaction amount | SUCCESS | 85s | 1 | YES |
| 12 | Most active customers | SUCCESS | 115s | 100 | YES |
| 13 | Top branches by transaction count | DB ERROR | 0.2s | - | NO |
| 14 | Show high-risk customers | SUCCESS | 68s | 100 | YES |
| 15 | Average portfolio risk score | DB ERROR | 0.3s | - | NO |
| 16 | Risk score by governorate | TIMEOUT | 120s | - | NO |
| 17 | Customers with critical risk flags | SUCCESS | 98s | 100 | YES |
| 18 | List non-performing loans | TIMEOUT | 120s | - | NO |
| 19 | Loan portfolio by product | TIMEOUT | 1098s | - | NO |
| 20 | Average loan size | TIMEOUT | 1010s | - | NO |
| 21 | Delinquent customers | TIMEOUT | 436s | - | NO |
| 22 | Collateral coverage | TIMEOUT | 296s | - | NO |
| 23 | KYC completion rate | TIMEOUT | 181s | - | NO |
| 24 | Customers with expired KYC | TIMEOUT | 180s | - | NO |
| 25 | Pending verification cases | TIMEOUT | 180s | - | NO |
| 26 | Open AML alerts | SUCCESS | 97s | 100 | YES |
| 27 | Suspicious activity reports | DB ERROR | 0.5s | - | NO |
| 28 | AML alerts by branch | DB ERROR | 0.3s | - | NO |
| 29 | Compliance score | DB ERROR | 0.3s | - | NO |
| 30 | Compliance violations | DB ERROR | 0.2s | - | NO |
| 31 | Audit events | DB ERROR | 0.3s | - | NO |
| 32 | Monthly executive summary | SUCCESS | 93s | 100 | YES |
| 33 | Total revenue | SUCCESS | 90s | 100 | YES |
| 34 | Largest customer segment | SUCCESS | 86s | 100 | YES |
| 35 | Portfolio evolution | SUCCESS | 130s | 5 | YES |
| 36 | Montre-moi les clients à haut risque | TIMEOUT | 180s | - | NO |
| 37 | Quel est le montant total des dépôts par segment ? | TIMEOUT | 180s | - | NO |
| 38 | Affiche les créances douteuses | SUCCESS | 109s | 100 | YES |
| 39 | Quel est le taux de conformité KYC ? | SUCCESS | 103s | 100 | YES |
| 40 | Montre les alertes AML ouvertes | SUCCESS | 76s | 100 | YES |
| 41 | Classe les agences selon leur volume de transactions | SUCCESS | 99s | 100 | YES |
| 42 | Quels sont les clients VIP ? | SUCCESS | 103s | 100 | YES |
| 43 | Quels sont les prêts en défaut ? | SUCCESS | 108s | 100 | YES |
| 44 | Montre les clients de Tunis | SUCCESS | 86s | 100 | YES |
| 45 | Compare Tunis et Sfax | SUCCESS | 131s | 100 | YES |

---

**Report generated:** July 15, 2026
**Baseline for:** Phase 6C improvements
