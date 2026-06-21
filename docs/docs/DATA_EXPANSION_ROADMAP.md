# DATA EXPANSION ROADMAP
**Phase 6 — Implementation Strategy**
*Enterprise Banking Data Foundation + Agent Accuracy Refactor*

---

> [!IMPORTANT]
> **Golden Rule**: All existing tables, APIs, KPI Governance, Risk Center, Compliance Center, and RBAC must continue to function correctly after every phase. Each phase is independently deployable and rollbackable.

---

## ROADMAP OVERVIEW

```
PHASE A: Schema Expansion       (Weeks 1-3)
  ├── A1: Fix Critical Bugs     (Day 1-2)
  ├── A2: Semantic Layer Tables (Week 1)
  ├── A3: Loan Domain           (Week 2)
  ├── A4: KYC + AML Domain      (Week 2)
  ├── A5: Finance/GL Domain     (Week 3)
  └── A6: Organization Domain   (Week 3)

PHASE B: Semantic Layer Seeding (Weeks 4-5)
  ├── B1: Business Glossary     (Week 4)
  ├── B2: Metric Registry       (Week 4)
  ├── B3: Table + Column Meta   (Week 4)
  └── B4: Join Registry         (Week 5)

PHASE C: Agent Refactor        (Weeks 6-9)
  ├── C1: Quick Wins            (Week 6)
  ├── C2: Intent Agent Upgrade  (Week 6-7)
  ├── C3: Schema Agent Upgrade  (Week 7)
  ├── C4: Entity Agent Upgrade  (Week 7-8)
  ├── C5: SQL Agent Upgrade     (Week 8)
  └── C6: Validation Upgrade    (Week 9)

PHASE D: Benchmarking          (Week 10)
  ├── D1: Golden Query Seed     (Week 10)
  ├── D2: Benchmark Runner      (Week 10)
  └── D3: Accuracy Report       (Week 10)

PHASE E: Data Population       (Weeks 11-12)
  ├── E1: Generator Script      (Week 11)
  ├── E2: Data Generation       (Week 11-12)
  ├── E3: Validation            (Week 12)
  └── E4: Final Report          (Week 12)
```

---

## PHASE A: SCHEMA EXPANSION

### A1 — Critical Bug Fixes (Day 1-2, Zero Risk)

**Effort**: 0.5 day | **Risk**: Very Low | **Impact**: +8% SQL accuracy

#### Files to modify:
- `services/sql_agent/sql_builder.py` — Fix ALLOWED_COLUMNS for `branches` and `risk_flags`
- `init/postgres-main-init.sql` — Seed `compliance_violations` (currently 0 rows)

#### Changes:
```python
# sql_builder.py — Fix branches whitelist
"branches": [
    "branch_id", "name",  # was "branch_name" — doesn't exist in schema
    "state", "city", "manager_id", "created_at",
],

# sql_builder.py — Fix risk_flags whitelist  
"risk_flags": [
    "id", "customer_id", "flag_type",  # was "risk_id" — doesn't exist
    "severity", "description", "resolved", "created_at",
],
```

#### Verification:
```sql
-- Test branches query doesn't fall back to *
SELECT branch_id, name, city FROM branches LIMIT 5;

-- Test risk_flags query works
SELECT customer_id, flag_type, severity FROM risk_flags WHERE resolved = FALSE LIMIT 10;
```

---

### A2 — Semantic Layer Tables (Week 1, 3 days)

**Effort**: 3 days | **Risk**: Low (new tables only) | **Impact**: Foundation for all agent upgrades

#### New file: `init/03-semantic-layer.sql`

```sql
-- Business Glossary
CREATE TABLE IF NOT EXISTS business_glossary (
    term_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term          VARCHAR(100) UNIQUE NOT NULL,
    definition    TEXT NOT NULL,
    synonyms      TEXT[],
    domain        VARCHAR(50),
    business_owner VARCHAR(100),
    source_tables TEXT[],
    formula       TEXT,
    example       TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_glossary_term ON business_glossary(term);
CREATE INDEX IF NOT EXISTS idx_glossary_domain ON business_glossary(domain);

-- Metric Registry
CREATE TABLE IF NOT EXISTS metric_registry (
    metric_id          VARCHAR(50) PRIMARY KEY,
    metric_name_fr     VARCHAR(200),
    metric_name_en     VARCHAR(200),
    formula            TEXT NOT NULL,
    description        TEXT,
    domain             VARCHAR(50),
    owner              VARCHAR(100),
    source_tables      TEXT[],
    dependencies       TEXT[],
    unit               VARCHAR(20),
    refresh_frequency  VARCHAR(20),
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table Metadata
CREATE TABLE IF NOT EXISTS table_metadata (
    table_name          VARCHAR(100) PRIMARY KEY,
    business_description TEXT,
    domain              VARCHAR(50),
    owner               VARCHAR(100),
    row_count_estimate  INTEGER,
    is_analytical       BOOLEAN DEFAULT FALSE,
    is_pii_bearing      BOOLEAN DEFAULT FALSE,
    refresh_frequency   VARCHAR(20),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Column Metadata
CREATE TABLE IF NOT EXISTS column_metadata (
    metadata_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name     VARCHAR(100) NOT NULL,
    column_name    VARCHAR(100) NOT NULL,
    business_description TEXT,
    synonyms       TEXT[],
    data_type      VARCHAR(50),
    is_pii         BOOLEAN DEFAULT FALSE,
    example_values TEXT[],
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_name, column_name)
);

-- Join Registry
CREATE TABLE IF NOT EXISTS join_registry (
    join_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table      VARCHAR(100) NOT NULL,
    source_column     VARCHAR(100) NOT NULL,
    target_table      VARCHAR(100) NOT NULL,
    target_column     VARCHAR(100) NOT NULL,
    relationship_type VARCHAR(20),
    join_type         VARCHAR(20) DEFAULT 'LEFT JOIN',
    confidence        DECIMAL(3,2) DEFAULT 1.00,
    notes             TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_table, source_column, target_table, target_column)
);
CREATE INDEX IF NOT EXISTS idx_join_registry_source ON join_registry(source_table, source_column);
CREATE INDEX IF NOT EXISTS idx_join_registry_target ON join_registry(target_table, target_column);
```

**Rollback**: `DROP TABLE IF EXISTS business_glossary, metric_registry, table_metadata, column_metadata, join_registry;`

---

### A3 — Loan Domain (Week 2, 5 days)

**Effort**: 5 days | **Risk**: Low (new tables, no FK to existing until tested) | **Impact**: +35% on loan queries, unblocks 6 KPIs

#### New file: `init/04-loan-domain.sql`

Tables to create:
1. `loan_contracts` — Core loan table
2. `loan_products` — Loan product definitions
3. `loan_installments` — Payment schedule
4. `loan_repayments` — Actual payments made
5. `loan_delinquency_events` — Payment incidents
6. `loan_restructuring` — Restructuring events
7. `collateral` — Real guarantees (mortgages)
8. `guarantees` — Personal guarantees
9. `provisions` — Provisioning
10. `non_performing_loans` — NPL register

**Migration Safety**:
- All new tables — zero risk to existing tables
- Foreign keys reference `customers.customer_id` and `accounts.account_id` (both exist)
- Use `ON CONFLICT DO NOTHING` on all seeds

**Rollback**:
```sql
DROP TABLE IF EXISTS non_performing_loans, provisions, guarantees, collateral, 
  loan_restructuring, loan_delinquency_events, loan_repayments, 
  loan_installments, loan_products, loan_contracts CASCADE;
```

---

### A4 — KYC + AML Domain (Week 2, 3 days)

**Effort**: 3 days | **Risk**: Low | **Impact**: +12% on compliance accuracy

Tables:
- `kyc_cases`, `kyc_documents`, `kyc_reviews`, `kyc_verifications`, `kyc_expirations`
- `pep_screening`, `sanctions_screening`
- `aml_alerts`, `suspicious_activity_reports`
- `compliance_cases`, `compliance_reviews`, `audit_findings`

---

### A5 — Finance / GL Domain (Week 3, 4 days)

**Effort**: 4 days | **Risk**: Low | **Impact**: Enables ROE, ROA, Cost-to-Income, LCR, NSFR

Tables:
- `general_ledger`, `ledger_entries`
- `fee_income`, `interest_income`, `operating_expenses`
- `profitability_metrics`
- `balance_sheet_snapshots`, `income_statement_snapshots`

**Note**: `balance_sheet_snapshots` and `income_statement_snapshots` require monthly seeding going back 24 months for time-series KPI accuracy.

---

### A6 — Organization + Customer Extensions (Week 3, 3 days)

**Effort**: 3 days | **Risk**: Low | **Impact**: Geographic analytics, relationship manager analytics

Tables:
- `regions`, `departments`, `business_units`, `employees`, `relationship_managers`
- `customer_profiles`, `customer_addresses`, `customer_contacts`
- `customer_risk_scores`, `customer_relationships`, `customer_documents`
- `customer_preferences`, `customer_status_history`
- `account_types`, `account_balances`, `account_status_history`

---

### Phase A Verification

```sql
-- Verify all domains exist
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN (
    'loan_contracts', 'non_performing_loans', 'provisions', 'collateral',
    'kyc_cases', 'aml_alerts', 'suspicious_activity_reports',
    'balance_sheet_snapshots', 'income_statement_snapshots',
    'business_glossary', 'metric_registry', 'join_registry',
    'regions', 'employees', 'customer_profiles'
  )
ORDER BY table_name;
-- Expected: 15 rows

-- Verify KPI computability after Phase A
SELECT 
    'npl_ratio' as kpi,
    COUNT(*)::text || ' loan contracts' as status
FROM loan_contracts
UNION ALL
SELECT 
    'provision_coverage',
    COUNT(*)::text || ' provisions'
FROM provisions;
```

---

## PHASE B: SEMANTIC LAYER SEEDING

### B1 — Business Glossary (Week 4, 2 days)

**Effort**: 2 days | **Risk**: None (inserts only)

Seed 37+ terms from `SEMANTIC_LAYER_DESIGN.md` into `business_glossary` table.

**File**: `init/05-semantic-layer-seed.sql`

```sql
INSERT INTO business_glossary (term, definition, synonyms, domain, source_tables, formula) VALUES
('NPL', 'Créance classée non performante...', 
 ARRAY['créances classées','bad loans','prêts non performants'],
 'loan', ARRAY['non_performing_loans','loan_contracts'],
 'COUNT(*) FROM non_performing_loans WHERE status = ''contentieux'''),
-- ... 36 more terms
ON CONFLICT (term) DO UPDATE SET synonyms = EXCLUDED.synonyms;
```

---

### B2 — Metric Registry (Week 4, 1 day)

Seed 25 metrics from `SEMANTIC_LAYER_DESIGN.md`:

```sql
INSERT INTO metric_registry (metric_id, metric_name_fr, formula, source_tables) VALUES
('npl_ratio', 'Taux de créances classées',
 'SUM(CASE WHEN days_past_due > 90 THEN outstanding_balance ELSE 0 END) / SUM(outstanding_balance) * 100',
 ARRAY['loan_contracts']),
-- ... 24 more metrics
ON CONFLICT (metric_id) DO UPDATE SET formula = EXCLUDED.formula;
```

---

### B3 — Table + Column Metadata (Week 4, 2 days)

Seed all 96 tables with business descriptions, domain tags, PII flags.

Seed critical columns (especially synonyms) for:
- `loan_contracts.*` — banking-critical columns
- `aml_alerts.*`
- `customers.*`
- `accounts.*`

---

### B4 — Join Registry (Week 5, 2 days)

Seed all 25+ canonical join paths identified in `SEMANTIC_LAYER_DESIGN.md`.

```sql
INSERT INTO join_registry (source_table, source_column, target_table, target_column, relationship_type) VALUES
('customers', 'customer_id', 'loan_contracts', 'customer_id', 'one_to_many'),
('loan_contracts', 'loan_id', 'non_performing_loans', 'loan_id', 'one_to_one'),
-- ... all pairs
ON CONFLICT DO NOTHING;
```

---

## PHASE C: AGENT REFACTOR

### C1 — Quick Wins (Week 6, 2 days)

- Fix ALLOWED_COLUMNS in `sql_builder.py` (from Phase A1 if not done)
- Add `loan_contracts`, `non_performing_loans`, `aml_alerts`, `kyc_cases` to ALLOWED_COLUMNS
- Update `ENTITY_TO_PRIMARY_KEY` to remove ghost references, add new entities
- Update `SEMANTIC_JOIN_MAP` with loan domain joins

**No new architecture** — pure dict updates in existing Python files.

---

### C2 — Intent Agent Upgrade (Week 6-7, 3 days)

New additions to `services/intent_agent/`:
- Add 6 new intent categories
- Add `BANKING_KPI_PATTERNS` dict (regex → intent + metric_id)
- Add `FRENCH_INTENT_PATTERNS` dict
- New method: `recognize_banking_kpis(query)` → `List[str]` (metric_ids detected)
- Extend `IntentResponse` model with `detected_kpis: Optional[List[str]]`

**Backward compat**: Existing 8 categories unchanged. New categories extend the set.

---

### C3 — Schema Agent Upgrade (Week 7, 4 days)

New additions to `services/schema_agent/`:
- Add async DB connection (asyncpg)
- New method: `match_tables_semantic(intent, resolved_terms, metric_ids)` → `List[str]`
- New method: `get_join_paths_from_registry(tables, primary_table)` → `List[JoinPath]`
- Keep existing hardcoded dicts as **fallback** if DB unavailable

---

### C4 — Entity Resolution Agent Upgrade (Week 7-8, 4 days)

New additions to `services/entity_resolution_agent/`:
- Add async DB connection
- New method: `resolve_with_glossary(request)` — glossary lookup before resolution
- New method: `_normalize_entity(term)` — synonym → canonical table name
- New method: `_recognize_banking_kpi(term)` — KPI detection
- Extend `ENTITY_TO_PRIMARY_KEY` to 20+ entities

---

### C5 — SQL Agent Upgrade (Week 8, 5 days)

New additions to `services/sql_agent/`:
- Add async DB connection for metric_registry + join_registry lookups
- New method: `build_with_metric(request)` — metric formula injection
- New method: `_build_joins_from_registry(join_paths)` — registry-validated joins
- Add all new tables to `ALLOWED_COLUMNS` (90+ tables total)
- Extend `SQLGenerationRequest` model with `detected_metric_id: Optional[str]`

---

### C6 — Validation Agent Upgrade (Week 9, 3 days)

New checks in `services/validation_agent/`:
- Add async DB connection
- Check 6: Table existence validation (against `information_schema`)
- Check 7: Join correctness validation (against `join_registry`)
- Check 8: KPI formula validation (against `metric_registry`)
- Checks 6-8 are **warnings** not rejections (to avoid regression)

---

## PHASE D: BENCHMARKING

### D1 — Golden Query Seed (Week 10, 2 days)

Create `golden_queries` table and seed all 100 queries from `GOLDEN_QUERY_FRAMEWORK.md`.

### D2 — Benchmark Runner (Week 10, 2 days)

Create `scripts/run_benchmark.py`:
- Loads golden queries from DB
- Runs each through full pipeline via HTTP
- Scores each query on 7 dimensions
- Outputs JSON results

### D3 — Live Accuracy Report (Week 10, 1 day)

Run benchmark and update `AGENT_ACCURACY_REPORT.md` with live scores.

---

## PHASE E: DATA POPULATION

### E1 — Data Generator Script (Week 11, 4 days)

Create `scripts/generate_tunisian_banking_data.py`:

```python
"""
Deterministic synthetic data generator for Tunisian banking data.

Usage:
    python generate_tunisian_banking_data.py \
        --customers 2000 \
        --accounts 5000 \
        --transactions 50000 \
        --loans 1500 \
        --months 24 \
        --seed 42 \
        --output-format sql \
        --output-file data/tunisian_banking_data.sql

Requirements:
    pip install faker psycopg2-binary
"""
import random
from faker import Faker
from datetime import datetime, timedelta

SEED = 42
random.seed(SEED)

TUNISIAN_FIRST_NAMES = [
    "Ahmed", "Mohamed", "Youssef", "Sami", "Mehdi", "Amine", "Karim",
    "Anis", "Walid", "Mourad", "Firas", "Iheb", "Omar", "Ali", "Hichem",
    "Salma", "Ons", "Mariem", "Yasmine", "Nour", "Amira", "Ines", "Syrine",
    "Rania", "Malek", "Fatma", "Leila", "Kenza", "Sonia", "Rim"
]

TUNISIAN_LAST_NAMES = [
    "Ben Ali", "Trabelsi", "Ben Salah", "Mansouri", "Gharbi", "Chouchane",
    "Jlassi", "Khelifi", "Haddad", "Dridi", "Ayari", "Mejri", "Bouzid",
    "Cherif", "Baccouche", "Saidi", "Hamdi", "Ferchichi", "Zribi",
    "Kessentini", "Marzouki", "Chaabane", "Tlili", "Ouerghi", "Guediri"
]

TUNISIAN_CITIES = [
    ("Tunis", "Tunis", "Grand Tunis"),
    ("Ariana", "Ariana", "Grand Tunis"),
    ("Ben Arous", "Ben Arous", "Grand Tunis"),
    ("Manouba", "Manouba", "Grand Tunis"),
    ("Sfax", "Sfax", "Centre-Est"),
    ("Sousse", "Sousse", "Centre-Est"),
    ("Monastir", "Monastir", "Centre-Est"),
    ("Mahdia", "Mahdia", "Centre-Est"),
    ("Nabeul", "Nabeul", "Nord-Est"),
    ("Bizerte", "Bizerte", "Nord-Est"),
    ("Kairouan", "Kairouan", "Centre-Ouest"),
    ("Gabès", "Gabès", "Sud-Est"),
    ("Médenine", "Médenine", "Sud-Est"),
    ("Gafsa", "Gafsa", "Sud-Ouest"),
    ("Tozeur", "Tozeur", "Sud-Ouest"),
    ("Kasserine", "Kasserine", "Centre-Ouest"),
    ("Jendouba", "Jendouba", "Nord-Ouest"),
    ("Béja", "Béja", "Nord-Ouest"),
    ("Tataouine", "Tataouine", "Sud-Est"),
    ("Kébili", "Kébili", "Sud-Ouest"),
]

# City distribution weights (realistic Tunisian distribution)
CITY_WEIGHTS = [20, 12, 8, 5, 15, 10, 7, 3, 5, 4, 2, 2, 1, 1, 1, 1, 1, 1, 0.5, 0.5]

TRANSACTION_LABELS_FR = [
    "Virement entrant", "Virement sortant", "Retrait DAB",
    "Versement espèces", "Paiement carte", "Prélèvement automatique",
    "Frais bancaires", "Remboursement crédit", "Salaire", "Paiement fournisseur"
]

LOAN_TYPES = ["immobilier", "consommation", "automobile", "professionnel"]
LOAN_STATUS = ["actif", "actif", "actif", "en_retard", "contentieux", "remboursé"]

RISK_LABELS_FR = [
    "KYC incomplet", "Suspicion AML", "Client politiquement exposé",
    "Alerte transaction inhabituelle", "Dépassement seuil réglementaire",
    "Risque crédit élevé", "Retard de paiement", "Compte sous surveillance"
]
```

### E2 — Data Generation Targets

| Table | Target Rows | Distribution Notes |
|-------|------------|-------------------|
| customers | 2,000 | 60% Grand Tunis, 20% Sfax/Sousse, 20% others |
| customer_profiles | 2,000 | 1:1 with customers |
| customer_addresses | 4,000 | 2 addresses per customer avg |
| customer_contacts | 4,000 | 2 contacts per customer avg |
| customer_risk_scores | 24,000 | Monthly scores per customer × 12 months |
| accounts | 5,000 | 2.5 accounts per customer avg |
| account_balances | 60,000 | Monthly snapshots × 24 months |
| transactions | 50,000 | Distributed over 24 months |
| loan_contracts | 1,500 | 75% actif, 15% en_retard, 10% contentieux |
| loan_installments | 18,000 | Avg 12 installments per loan |
| loan_repayments | 15,000 | ~83% of installments paid |
| loan_delinquency_events | 800 | For loans in_retard/contentieux |
| collateral | 900 | 60% of loans have collateral |
| guarantees | 600 | 40% of loans have guarantees |
| provisions | 300 | For NPL loans only |
| non_performing_loans | 150 | DPD > 90 days |
| kyc_cases | 2,200 | 1.1 per customer (some have reviews) |
| kyc_reviews | 1,800 | For closed cases |
| kyc_verifications | 6,600 | 3 verifications per case avg |
| aml_alerts | 800 | ~40% of transactions flagged get alerts |
| suspicious_activity_reports | 80 | 10% of AML alerts become SARs |
| compliance_cases | 150 | |
| compliance_reviews | 300 | |
| compliance_violations | 200 | |
| audit_findings | 120 | |
| risk_flags | 3,000 | |
| risk_events | 1,000 | |
| risk_assessments | 2,000 | |
| risk_score_history | 24,000 | Monthly per customer |
| risk_exposure | 2,000 | |
| portfolio_risk_summary | 24 | Monthly snapshots |
| general_ledger | 200 | Chart of accounts |
| ledger_entries | 100,000 | All transactions journal entries |
| fee_income | 576 | Monthly × 24 months × 24 branches |
| interest_income | 576 | Same |
| operating_expenses | 576 | Same |
| balance_sheet_snapshots | 24 | Monthly × 24 months |
| income_statement_snapshots | 24 | Monthly × 24 months |
| regions | 7 | Fixed Tunisian regions |
| branches | 40 | Realistic Tunisian branch names |
| departments | 12 | Functional departments |
| employees | 200 | Staff across all branches |
| relationship_managers | 80 | RM-client assignments |

---

### E3 — Validation Queries

```sql
-- Row count validation
SELECT table_name, reltuples::bigint as estimated_rows
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
ORDER BY reltuples DESC;

-- Orphan check
SELECT COUNT(*) as orphan_transactions
FROM transactions t
WHERE NOT EXISTS (SELECT 1 FROM accounts a WHERE a.account_id = t.account_id);

SELECT COUNT(*) as orphan_loans
FROM loan_contracts l
WHERE NOT EXISTS (SELECT 1 FROM customers c WHERE c.customer_id = l.customer_id);

-- Date distribution check
SELECT 
    date_trunc('month', transaction_date) as month,
    COUNT(*) as transaction_count
FROM transactions
GROUP BY 1
ORDER BY 1;

-- KPI computability check
SELECT 
    'NPL Ratio' as kpi,
    ROUND(
        SUM(CASE WHEN days_past_due > 90 THEN outstanding_balance ELSE 0 END)
        / NULLIF(SUM(outstanding_balance), 0) * 100, 2
    ) as value
FROM loan_contracts
UNION ALL
SELECT 'Total Deposits', ROUND(SUM(balance), 2) FROM accounts WHERE status = 'active'
UNION ALL
SELECT 'Active Customers', COUNT(DISTINCT customer_id)::numeric FROM accounts WHERE status = 'active'
UNION ALL
SELECT 'Open AML Alerts', COUNT(*)::numeric FROM aml_alerts WHERE status = 'ouvert';
```

---

## RISK MATRIX

| Phase | Risk | Mitigation | Rollback |
|-------|------|-----------|----------|
| A1 (Bug fix) | Very Low | Test in dev first | Git revert |
| A2 (Semantic tables) | Low | New tables only | DROP TABLE cascade |
| A3 (Loan domain) | Low | No existing table touched | DROP TABLE cascade |
| A4 (KYC/AML) | Low | New tables only | DROP TABLE cascade |
| A5 (Finance/GL) | Low | New tables only | DROP TABLE cascade |
| B (Seed semantic) | Very Low | INSERT/UPDATE only | TRUNCATE tables |
| C1 (Dict updates) | Low | Python dict edits, no API change | Git revert |
| C2-C6 (Agent refactor) | Medium | Feature flags, fallback to hardcoded | Disable new code path via env var |
| D (Benchmarking) | Very Low | Read-only | N/A |
| E (Data population) | Low | Deterministic seed, can re-run | TRUNCATE + re-seed |

---

## MIGRATION STRATEGY

### Docker Compose Init Order
```yaml
# New init files mount order (postgres-main service)
volumes:
  - ./init/postgres-main-init.sql:/docker-entrypoint-initdb.d/01-main.sql
  - ./init/02-users-kpis.sql:/docker-entrypoint-initdb.d/02-users-kpis.sql
  - ./init/03-semantic-layer.sql:/docker-entrypoint-initdb.d/03-semantic-layer.sql    # NEW
  - ./init/04-loan-domain.sql:/docker-entrypoint-initdb.d/04-loan-domain.sql          # NEW
  - ./init/05-kyc-aml-domain.sql:/docker-entrypoint-initdb.d/05-kyc-aml.sql          # NEW
  - ./init/06-finance-gl-domain.sql:/docker-entrypoint-initdb.d/06-finance-gl.sql    # NEW
  - ./init/07-org-customer-ext.sql:/docker-entrypoint-initdb.d/07-org-customer.sql   # NEW
  - ./init/08-semantic-layer-seed.sql:/docker-entrypoint-initdb.d/08-sem-seed.sql    # NEW
  - ./init/09-golden-queries.sql:/docker-entrypoint-initdb.d/09-golden.sql           # NEW
```

### Existing Database Migration (if DB already running)
```bash
# Apply new schemas without destroying existing data
psql -h localhost -U banking_user -d banking_dev < init/03-semantic-layer.sql
psql -h localhost -U banking_user -d banking_dev < init/04-loan-domain.sql
# ... etc
# Use IF NOT EXISTS on all CREATE TABLE statements
# Use ON CONFLICT DO NOTHING on all INSERTs
```

---

## EFFORT SUMMARY

| Phase | Duration | Developer Days | Risk |
|-------|----------|---------------|------|
| A — Schema Expansion | 3 weeks | 18 dev-days | Low |
| B — Semantic Layer Seeding | 2 weeks | 7 dev-days | Very Low |
| C — Agent Refactor | 4 weeks | 21 dev-days | Medium |
| D — Benchmarking | 1 week | 5 dev-days | Very Low |
| E — Data Population | 2 weeks | 8 dev-days | Low |
| **TOTAL** | **12 weeks** | **59 dev-days** | **Low-Medium** |

---

## SUCCESS CRITERIA

| Milestone | Success Condition |
|-----------|-----------------|
| Phase A complete | `SELECT COUNT(*) FROM loan_contracts` returns > 0 |
| Phase B complete | `SELECT * FROM business_glossary WHERE term = 'NPL'` returns 1 row |
| Phase C complete | `run_benchmark.py` overall score ≥ 65% (up from 38%) |
| Phase D complete | Live accuracy report published with real scores |
| Phase E complete | All major tables ≥ 500 rows, 24-month time series present |
| **Project complete** | Overall benchmark ≥ 78%, KPI computation ≥ 85%, no regression |
