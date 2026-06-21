# BANKING DATA FOUNDATION AUDIT
**Phase 6 — Current State Assessment**
*Audited: 2026-06-21 | Scope: PostgreSQL Schema + NL-to-SQL Agent Pipeline*

---

## 1. CURRENT DATABASE SCHEMA INVENTORY

### 1.1 Tables in `banking_dev` (postgres-main)

| # | Table | Columns | Primary Key | Indexes | Seed Rows |
|---|-------|---------|-------------|---------|-----------|
| 1 | `customers` | 9 | `id` (UUID) + `customer_id` (VARCHAR) | 5 | ~215 (5 real + 5 Tunisia + 200 gen) |
| 2 | `accounts` | 9 | `id` (UUID) + `account_id` (VARCHAR) | 5 | ~210 |
| 3 | `transactions` | 9 | `id` (UUID) + `transaction_id` (VARCHAR) | 6 | ~210 |
| 4 | `risk_flags` | 7 | `id` (UUID) | 3 | ~203 |
| 5 | `branches` | 7 | `id` (UUID) + `branch_id` (VARCHAR) | 2 | ~208 |
| 6 | `products` | 5 | `id` (UUID) + `product_id` (VARCHAR) | 2 | ~205 |
| 7 | `compliance_rules` | 8 | `id` (UUID) | 2 | 12 |
| 8 | `data_lineage` | 7 | `id` (UUID) | 4 | 0 |
| 9 | `compliance_violations` | 9 | `id` (UUID) | 5 | 0 |
| 10 | `regulatory_reports` | 9 | `id` (UUID) | 3 | 0 |

### 1.2 Tables in `banking_dev` (02-users-kpis.sql)

| # | Table | Columns | Seed Rows |
|---|-------|---------|-----------|
| 11 | `roles` | 4 | 4 |
| 12 | `permissions` | 4 | 11 |
| 13 | `role_permissions` | 2 (junction) | 25 |
| 14 | `users` | 10 | 5 |
| 15 | `user_activity_log` | 6 | 0 |
| 16 | `kpi_categories` | 4 | 6 |
| 17 | `kpi_owners` | 5 | 6 |
| 18 | `kpi_definitions` | 12 | 20 |
| 19 | `kpi_thresholds` | 10 | 11 |
| 20 | `kpi_history` | 7 | 0 |

### 1.3 Tables in `embeddings` (postgres-embeddings-init.sql)

| # | Table | Purpose |
|---|-------|---------|
| 21 | `schema_embeddings` | Vector embeddings (384-dim, all-MiniLM-L6-v2) |
| 22 | `domain_categories` | Domain→table mapping with vector |
| 23 | `semantic_id_mappings` | Semantic entity→column with confidence |

**Total: 23 tables across 2 databases.**

---

## 2. SCHEMA RELATIONSHIP AUDIT

### 2.1 Foreign Key Analysis

```
customers.customer_id ──┬──► accounts.customer_id     (FK defined)
                        ├──► transactions.customer_id  (FK defined)
                        └──► risk_flags.customer_id    (FK defined)

accounts.account_id   ──────► transactions.account_id  (FK defined)

branches.branch_id    ──────► accounts.branch_id        (NO FK — branch_id is VARCHAR in accounts, 
                                                          no FK constraint declared)
```

**Critical Gap**: `accounts.branch_id` has NO foreign key constraint to `branches.branch_id`. This means referential integrity is not enforced for the branch-account relationship.

**Critical Gap**: `products` table has NO foreign key relationships to any other table. Products are disconnected from accounts and customers.

**Critical Gap**: `loans` table is referenced in `kpi_definitions.source_tables` (array field) but the actual `loans` table **does not exist** in the schema. 7 of 20 KPIs reference tables that don't exist (`financial_ledger`, `loans`, `provisions`, `collaterals`, `treasury_assets`, `cash_flows`).

### 2.2 Missing Relationships (vs. Banking Reality)
- No `loan_contracts` table
- No `collateral` table
- No `guarantees` table
- No `provisions` table
- No `non_performing_loans` table
- No `kyc_cases` / `kyc_documents` table
- No `aml_alerts` table
- No `suspicious_activity_reports` table
- No `employees` table (referenced in agent mappings but schema missing)
- No `regions` table
- No `departments` / `business_units` table
- No `general_ledger` / `ledger_entries`
- No `balance_sheet_snapshots` / `income_statement_snapshots`

---

## 3. CURRENT INDEX AUDIT

| Table | Indexed Columns | Missing Useful Indexes |
|-------|----------------|----------------------|
| customers | customer_id, kyc_verified, segment, risk_score, created_at | `name`, `email` for lookups |
| accounts | account_id, customer_id, status, branch_id, created_at | `account_type`, `balance` ranges |
| transactions | transaction_id, account_id, customer_id, transaction_date, status, transaction_type | composite (account_id + transaction_date) |
| risk_flags | customer_id, severity, flag_type | `resolved`, composite (severity + resolved) |
| branches | branch_id, state | `city` |
| products | product_id, category | — |
| compliance_rules | regulation, enabled | — |

---

## 4. SEED DATA QUALITY AUDIT

### 4.1 Volume Assessment
| Table | Target (Enterprise) | Current | Gap |
|-------|--------------------|---------|----|
| customers | 2,000+ | ~215 | **-90%** |
| accounts | 5,000+ | ~210 | **-96%** |
| transactions | 50,000+ | ~210 | **-99.6%** |
| risk_flags | 2,000+ | ~203 | **-90%** |
| branches | 50 realistic | ~208 | Excess but unrealistic |
| products | 20 realistic | ~205 | Excess, all synthetic noise |
| loan_contracts | 1,500+ | 0 | **-100%** |
| general_ledger | 5,000+ | 0 | **-100%** |
| kyc_cases | 1,000+ | 0 | **-100%** |
| aml_alerts | 500+ | 0 | **-100%** |

### 4.2 Data Realism Issues
1. **American customers seeded first** (Alice Johnson, Bob Smith) — not Tunisia-localized
2. **Generated branches** use pattern `Branch N Tunis/Sfax/...` — not realistic branch names
3. **Generated customers** have phone format `+216 20001234` — wrong Tunisian format (should be `+216 XX XXX XXX`)
4. **Transaction date distribution**: All 200 generated transactions span ~200 hours backward from NOW() — no 24-month spread
5. **Products table**: 200 entries like `Tunisian Bank Product 1..200` — no real French banking product names
6. **Currency**: Mixed USD and TND without clear separation — US customers use USD, Tunisia uses TND
7. **Risk scores**: Generated with `random()` — no realistic distribution curve
8. **Generated accounts**: `available_balance` can exceed `balance` (random independently)
9. **No relational consistency check**: generated transactions reference gen accounts/customers but no validation

### 4.3 KPI Computability
| KPI | Status | Reason |
|-----|--------|--------|
| total_deposits | ✅ Computable | accounts table exists |
| monthly_revenue | ✅ Computable | transactions table exists |
| avg_risk_score | ✅ Computable | customers table exists |
| total_risk_flags | ✅ Computable | risk_flags table exists |
| active_customers | ✅ Computable | accounts table exists |
| kyc_compliance_rate | ✅ Computable | customers table exists |
| compliance_score | ⚠️ Partial | compliance_violations table exists but has 0 rows |
| transaction_volume | ✅ Computable | transactions table exists |
| roa | ❌ Not computable | `financial_ledger` table missing |
| roe | ❌ Not computable | `financial_ledger` table missing |
| cost_to_income | ❌ Not computable | `financial_ledger` table missing |
| npl_ratio | ❌ Not computable | `loans` table missing |
| provision_coverage_ratio | ❌ Not computable | `provisions` + `loans` tables missing |
| loan_to_value | ❌ Not computable | `collaterals` + `loans` tables missing |
| loan_to_deposit_ratio | ❌ Not computable | `loans` table missing |
| lcr | ❌ Not computable | `treasury_assets` + `cash_flows` missing |
| nsfr | ❌ Not computable | `treasury_assets` + `ledger` missing |

**Result: 7 of 20 KPIs (35%) are computable. 11 of 20 KPIs (55%) reference non-existent tables.**

---

## 5. AGENT PIPELINE AUDIT

### 5.1 Intent Agent
**File**: `services/intent_agent/` (IntentRecognizer + spaCy)

| Capability | Status | Notes |
|-----------|--------|-------|
| Query classification | ✅ Working | 8 intent categories |
| spaCy NLP | ✅ Integrated | Pattern matching |
| Redis caching | ✅ Optional | Falls back gracefully |
| Banking terminology | ⚠️ Limited | No banking-specific NER |
| Arabic/French support | ❌ None | English-only patterns |
| KPI synonym resolution | ❌ None | "ROE", "return on equity" not linked |
| Tunisian context | ❌ None | No local banking term awareness |

**Intent Categories (8 total)**:
`customer_analysis`, `risk_analysis`, `revenue_analysis`, `operational_analysis`, `geographic_analysis`, `product_analysis`, `compliance_analysis`, `transaction_analysis`

**Missing categories**: `loan_analysis`, `kyc_analysis`, `aml_analysis`, `liquidity_analysis`, `profitability_analysis`, `executive_summary`

### 5.2 Schema Agent
**File**: `services/schema_agent/schema_matcher.py`

| Capability | Status | Notes |
|-----------|--------|-------|
| Intent→Domain mapping | ✅ Working | 8 intents → domains (hardcoded) |
| Domain→Table mapping | ✅ Working | Very limited (1-2 tables per domain) |
| Join path discovery | ✅ Working | Static graph, 1-hop only |
| Semantic table ranking | ❌ None | No scoring, first-match wins |
| Business glossary | ❌ None | No glossary integration |
| Domain awareness | ⚠️ Minimal | Only 8 hardcoded domains |
| Vector similarity | ⚠️ Infrastructure only | pgvector exists, not used by schema agent |
| New table onboarding | ❌ Manual | Must edit Python source to add tables |

**Critical weakness**: When the schema expands to 60-100 tables, `DOMAIN_TO_TABLES` will be unmaintainable as hardcoded Python dicts. The agent has **zero dynamic discovery capability**.

### 5.3 Entity Resolution Agent
**File**: `services/entity_resolution_agent/` (EntityResolver + SemanticIDMapper)

| Capability | Status | Notes |
|-----------|--------|-------|
| Entity→PK mapping | ✅ Working | 8 entity types |
| Join key discovery | ✅ Working | `SEMANTIC_JOIN_MAP` dict |
| Banking synonym resolution | ❌ None | "bad loans" won't resolve to `non_performing_loans` |
| KPI term recognition | ❌ None | "NPL ratio" not recognized |
| Multi-hop join paths | ❌ None | Only 1-hop joins |
| Composite key support | ❌ None | No multi-column join keys |
| Ambiguous entity resolution | ❌ None | "loan" hardcoded but `loans` table absent |

**Critical weakness**: `ENTITY_TO_PRIMARY_KEY` maps `"loan" → "loan_id"` and `ENTITY_PRIMARY_TABLE` maps `"loan" → "loans"` — but `loans` table **does not exist** in the actual database. The agent references a ghost table.

### 5.4 SQL Agent
**File**: `services/sql_agent/sql_builder.py` (SQLBuilder)

| Capability | Status | Notes |
|-----------|--------|-------|
| Parameterized queries | ✅ Excellent | All values via ? placeholders |
| Column whitelist | ✅ Working | ALLOWED_COLUMNS dict enforced |
| Join construction | ✅ Working | From EntityResolver join paths |
| Aggregate support | ✅ Working | COUNT/SUM/AVG/MIN/MAX |
| LIMIT enforcement | ✅ Always | MAX 10,000 rows |
| Metric registry usage | ❌ None | KPI formulas not consumed |
| Join registry usage | ❌ None | Relies on EntityResolver only |
| Domain-aware generation | ❌ None | No domain context |
| Banking formula support | ❌ None | NPL%, ROA, LCR not generated |
| ALLOWED_COLUMNS coverage | ⚠️ Mismatched | `branches` has `branch_name` in whitelist but schema has `name`; `risk_flags` has `risk_id` but schema uses `id` |

**ALLOWED_COLUMNS vs Schema Mismatch** (bugs):
- `branches`: whitelist has `branch_name`, `country`, `region`, `opened_at`, `status` — none of these columns exist in `branches` table (schema has `name`, `state`, `city`, `manager_id`)
- `risk_flags`: whitelist has `risk_id`, `account_id`, `flagged_at`, `resolved_at`, `status` — schema has `id`, no `account_id`, no `flagged_at`
- `loans` table in whitelist — table does not exist in schema
- `employees` table in whitelist — table does not exist in schema

### 5.5 Validation Agent
**File**: `services/validation_agent/query_validator.py` (QueryValidator)

| Capability | Status | Notes |
|-----------|--------|-------|
| SQL injection prevention | ✅ Excellent | 5-check pipeline |
| Dangerous keyword blocking | ✅ Working | 30+ keywords |
| Suspicious pattern detection | ✅ Working | 20+ regex patterns |
| HMAC query signing | ✅ Working | SHA256 tamper detection |
| Join validation | ❌ None | Doesn't verify join correctness |
| KPI formula validation | ❌ None | No business rule checks |
| Banking rule validation | ❌ None | No domain-specific rules |
| Table existence validation | ❌ None | Accepts queries on nonexistent tables |
| Column existence validation | ❌ None | Accepts queries on nonexistent columns |

### 5.6 Compliance Agent
**File**: `services/compliance_agent/` (ComplianceChecker)

| Capability | Status | Notes |
|-----------|--------|-------|
| GDPR enforcement | ✅ Working | PII masking rules |
| PCI-DSS enforcement | ✅ Working | Card data rules |
| SOX enforcement | ✅ Working | Audit rules |
| AML monitoring | ✅ Working | Amount threshold rules |
| KYC enforcement | ✅ Working | Due diligence rules |
| RBAC integration | ✅ Working | Role-based access |
| Post-schema-expansion safety | ⚠️ Risk | Rules hardcoded for 6 tables |

---

## 6. BENCHMARK COVERAGE AUDIT

| Category | Golden Queries | Currently Working | Coverage |
|----------|---------------|-------------------|----------|
| Customer Analytics | 0 defined | 0 tested | 0% |
| Deposit Analytics | 0 defined | 0 tested | 0% |
| Loan Analytics | 0 defined | 0 tested | 0% |
| Risk Analytics | 0 defined | 0 tested | 0% |
| Compliance Analytics | 0 defined | 0 tested | 0% |
| Branch Analytics | 0 defined | 0 tested | 0% |
| Executive Analytics | 0 defined | 0 tested | 0% |

**No formal benchmarking framework exists.**

---

## 7. STRENGTHS

1. **Security-first SQL generation** — parameterized queries, column whitelist, 5-check validation, HMAC signing. This is enterprise-grade.
2. **RBAC infrastructure** — roles, permissions, role_permissions junction, user management fully implemented.
3. **KPI governance framework** — kpi_definitions, kpi_thresholds, kpi_categories, kpi_owners exist and are seeded.
4. **Compliance agent** — GDPR/PCI-DSS/SOX/AML/KYC rules implemented and working.
5. **pgvector infrastructure** — embeddings database with vector index provisioned; semantic layer foundation exists.
6. **Compliance audit tables** — data_lineage, compliance_violations, regulatory_reports exist.
7. **Frontend integration** — React/TypeScript app with multiple functional centers (Compliance, Risk, Reports, KPI Governance, Admin).

---

## 8. CRITICAL WEAKNESSES

### W1 — Schema Too Small (CRITICAL)
**Impact**: 6 operational tables total. Enterprise banking requires 60-100+. Major domains missing: Loan, Finance/GL, KYC (formal), AML, Product Subscription, Collateral, Provision.

### W2 — Ghost Table References (CRITICAL)
**Impact**: 11 of 20 KPIs reference tables that don't exist. SQL agent has `loans` and `employees` in its whitelist for non-existent tables. Agent will generate queries that fail at execution.

### W3 — ALLOWED_COLUMNS Mismatch (HIGH)
**Impact**: SQL agent column whitelist has wrong column names for `branches` and `risk_flags`. Queries on these tables will silently fall back to `table.*` due to whitelist rejection.

### W4 — No Business Glossary (HIGH)
**Impact**: No banking term normalization. "NPL" → `non_performing_loans`, "bad loans" → same, "deposits" → `accounts WHERE account_type IN (...)` — none of these mappings exist.

### W5 — No 24-Month Time Series Data (HIGH)
**Impact**: Trend analytics, KPI history, MoM comparisons all fail. All 200 generated transactions span only ~200 hours (~8 days).

### W6 — No Loan Domain (HIGH)
**Impact**: Loans represent 40-60% of banking analytics queries. No loan contracts, installments, repayments, delinquency, NPL, provisions, collateral, or guarantees exist.

### W7 — Static Hardcoded Agent Mappings (MEDIUM)
**Impact**: Every table addition requires Python source edits in 4+ files. Not scalable to 60-100 tables. No dynamic schema discovery.

### W8 — No Golden Query Benchmark (MEDIUM)
**Impact**: Accuracy is completely unmeasured. No regression protection. No way to know if agent changes improve or degrade accuracy.

### W9 — No Semantic Layer (MEDIUM)
**Impact**: pgvector infrastructure exists but isn't used for table/column selection. Domain categories are seeded but agent uses Python dicts instead.

### W10 — Missing Tunisian Localization (LOW-MEDIUM)
**Impact**: American seed data (Alice Johnson, Bob Smith, USD, US states) coexists with Tunisian data. No French banking product labels. No realistic Tunisian phone/address format.

---

## 9. SCALABILITY CONCERNS

| Concern | Current | At 60-100 Tables |
|---------|---------|-----------------|
| `DOMAIN_TO_TABLES` dict maintenance | 8 entries, manual | Would need 100+ entries manually |
| `SEMANTIC_JOIN_MAP` dict | 16 pairs, manual | Would need 500+ pairs |
| `ALLOWED_COLUMNS` dict | 8 tables, manual | Would need 100 tables |
| `TABLE_FILTER_COLUMNS` dict | 6 tables, manual | Would need 100 tables |
| Schema agent join discovery | 1-hop only | Multi-domain queries require 3-4 hops |
| Vector similarity (unused) | Seeded, idle | Could replace all hardcoded dicts |

---

## 10. ACCURACY CONCERNS (NL-to-SQL)

Based on architecture analysis (no formal benchmark exists):

| Query Type | Estimated Accuracy | Primary Failure Mode |
|-----------|-------------------|---------------------|
| Simple single-table retrieval | ~85% | Column whitelist mismatch |
| Aggregation (COUNT/SUM) | ~80% | Group-by column validation |
| Multi-table joins | ~60% | 1-hop only, wrong FK assumptions |
| KPI computation | ~30% | Missing tables (loans, ledger, provisions) |
| Banking term queries | ~20% | No synonym/glossary resolution |
| Loan analytics | ~5% | loans table doesn't exist |
| Compliance analytics | ~50% | compliance_violations has 0 rows |
| French-language queries | ~0% | English-only intent patterns |

---

## AUDIT CONCLUSION

The current platform has **excellent security and governance infrastructure** but **insufficient data foundation** for enterprise banking analytics. The primary blockers are:

1. Missing 40+ core banking tables (Loan, Finance, KYC, AML domains)
2. ~65% of KPIs reference non-existent tables
3. No business glossary or semantic layer in active use
4. Toy-scale seed data with no time-series distribution
5. Hardcoded agent mappings that cannot scale to target schema
6. Zero formal benchmarking

The system is **Phase 1-ready** (demo/MVP) but **not Phase 6-ready** (enterprise banking intelligence).
