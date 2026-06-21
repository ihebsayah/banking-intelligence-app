# TARGET BANKING DOMAIN MODEL
**Phase 6 — Enterprise Banking Analytical Schema Design**
*Target: 75 meaningful tables organized across 10 domains*

---

## DESIGN PRINCIPLES

1. **Additive only** — all new tables; existing 23 tables remain untouched
2. **Referential integrity** — every FK explicitly declared
3. **Tunisia-native** — currency TND, Tunisian geography, French labels
4. **Analytics-first** — wide tables preferred over normalized snapshots for KPI computation
5. **Audit-safe** — `created_at`, `updated_at`, `created_by` on every major table
6. **Separation of concern** — operational tables vs. analytical snapshots clearly marked

---

## DOMAIN MAP (10 Domains, 75 New Tables)

```
CUSTOMER DOMAIN      (10 tables)
KYC DOMAIN           (7 tables)
ACCOUNT DOMAIN       (4 new tables, extends existing accounts)
PRODUCT DOMAIN       (4 tables)
LOAN DOMAIN          (10 tables)
PAYMENT DOMAIN       (6 new tables, extends existing transactions)
RISK DOMAIN          (8 tables)
COMPLIANCE DOMAIN    (7 tables)
FINANCE DOMAIN       (8 tables)
ORGANIZATION DOMAIN  (6 tables)
REPORTING DOMAIN     (5 tables)
```

---

## DOMAIN 1 — CUSTOMER (10 tables)

### `customer_profiles`
Extends `customers` with rich demographic and financial data.
```sql
CREATE TABLE customer_profiles (
    profile_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    date_of_birth     DATE,
    gender            VARCHAR(10),                   -- M, F, Autre
    nationality       VARCHAR(50) DEFAULT 'TN',
    national_id       VARCHAR(20),                   -- CIN tunisien
    passport_number   VARCHAR(20),
    marital_status    VARCHAR(20),                   -- célibataire, marié, divorcé, veuf
    employment_status VARCHAR(50),                   -- salarié, indépendant, retraité, chômeur
    employer_name     VARCHAR(255),
    annual_income     DECIMAL(15,2),
    income_currency   VARCHAR(3) DEFAULT 'TND',
    net_worth_band    VARCHAR(20),                   -- <50K, 50K-200K, 200K-1M, >1M
    politically_exposed BOOLEAN DEFAULT FALSE,       -- PEP flag
    pep_details       TEXT,
    tax_id            VARCHAR(30),                   -- Matricule fiscal
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `customer_segments`
Business segmentation definitions.
```sql
CREATE TABLE customer_segments (
    segment_id        VARCHAR(50) PRIMARY KEY,
    segment_name      VARCHAR(100) NOT NULL,         -- e.g. "Particulier Premium"
    segment_label_fr  VARCHAR(100),
    min_balance       DECIMAL(15,2),
    min_annual_income DECIMAL(15,2),
    description       TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `customer_addresses`
Multiple addresses per customer (domicile, travail, correspondance).
```sql
CREATE TABLE customer_addresses (
    address_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    address_type      VARCHAR(20),                   -- domicile, travail, correspondance
    address_line1     VARCHAR(255),
    address_line2     VARCHAR(255),
    city              VARCHAR(100),
    governorate       VARCHAR(100),                  -- Gouvernorat tunisien
    postal_code       VARCHAR(10),
    country           VARCHAR(50) DEFAULT 'Tunisie',
    is_primary        BOOLEAN DEFAULT FALSE,
    valid_from        DATE,
    valid_to          DATE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `customer_contacts`
Phone, email, preferred contact channel.
```sql
CREATE TABLE customer_contacts (
    contact_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    contact_type      VARCHAR(20),                   -- mobile, fixe, email, whatsapp
    contact_value     VARCHAR(255),
    is_primary        BOOLEAN DEFAULT FALSE,
    verified          BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `customer_risk_scores`
Time-series of calculated risk scores per model.
```sql
CREATE TABLE customer_risk_scores (
    score_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    model_id          VARCHAR(50),                   -- FK to risk_models
    score             DECIMAL(5,4),
    score_band        VARCHAR(20),                   -- faible, moyen, élevé, critique
    score_date        DATE NOT NULL,
    factors           JSONB,                         -- contributing factors
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `customer_relationships`
Customer-to-customer relationships (spouse, parent, guarantor, etc.).
```sql
CREATE TABLE customer_relationships (
    relationship_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    related_customer_id VARCHAR(50) REFERENCES customers(customer_id),
    relationship_type VARCHAR(50),                   -- conjoint, garant, mandataire, tuteur
    valid_from        DATE,
    valid_to          DATE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `customer_documents`
Documents uploaded per customer (CIN, passeport, justificatif de domicile).
```sql
CREATE TABLE customer_documents (
    document_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    document_type     VARCHAR(50),                   -- CIN, passeport, justificatif_revenu
    document_number   VARCHAR(100),
    issued_date       DATE,
    expiry_date       DATE,
    verified          BOOLEAN DEFAULT FALSE,
    verified_by       VARCHAR(100),
    verified_at       TIMESTAMP,
    storage_ref       TEXT,                          -- document storage path/URL
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `customer_preferences`
Communication and product preferences.
```sql
CREATE TABLE customer_preferences (
    preference_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id) UNIQUE,
    language          VARCHAR(10) DEFAULT 'fr',
    contact_channel   VARCHAR(20) DEFAULT 'email',   -- email, sms, agence, application
    marketing_consent BOOLEAN DEFAULT FALSE,
    digital_banking   BOOLEAN DEFAULT TRUE,
    sms_alerts        BOOLEAN DEFAULT TRUE,
    email_alerts      BOOLEAN DEFAULT TRUE,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `customer_status_history`
Tracks status transitions over time (active → dormant → closed).
```sql
CREATE TABLE customer_status_history (
    history_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    previous_status   VARCHAR(30),
    new_status        VARCHAR(30),
    changed_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by        VARCHAR(100),
    reason            TEXT
);
```

---

## DOMAIN 2 — KYC (7 tables)

### `kyc_cases`
```sql
CREATE TABLE kyc_cases (
    kyc_case_id       VARCHAR(50) UNIQUE NOT NULL,
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    case_type         VARCHAR(30),         -- initial_kyc, periodic_review, enhanced_dd
    status            VARCHAR(30),         -- ouvert, en_cours, approuvé, rejeté, expiré
    risk_level        VARCHAR(20),         -- standard, élevé, pep
    assigned_to       VARCHAR(100),
    opened_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at         TIMESTAMP,
    due_date          DATE,
    notes             TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `kyc_documents` — Documents attached to KYC cases
### `kyc_reviews` — Review audit trail (reviewer, decision, date)
### `kyc_verifications` — Individual verification steps (identity, address, income, PEP)
### `kyc_expirations` — Scheduled review/expiry tracking
### `pep_screening` — Politically Exposed Person screening results
### `sanctions_screening` — OFAC/UN sanctions list screening

---

## DOMAIN 3 — ACCOUNT (4 new tables)

### `account_types` — Définition des types de compte
```sql
CREATE TABLE account_types (
    type_code         VARCHAR(50) PRIMARY KEY,
    type_name_fr      VARCHAR(100),        -- Compte courant, Compte épargne...
    type_name_en      VARCHAR(100),
    currency          VARCHAR(3) DEFAULT 'TND',
    interest_rate     DECIMAL(5,4),
    min_balance       DECIMAL(15,2) DEFAULT 0,
    max_balance       DECIMAL(20,2),
    is_active         BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `account_balances` — Daily balance snapshots (time series)
### `account_status_history` — Status transition audit
### `joint_accounts` — Joint account ownership
### `account_signatories` — Signatories per account

---

## DOMAIN 4 — PRODUCT (4 tables)

### `banking_products`
```sql
CREATE TABLE banking_products (
    product_id        VARCHAR(50) PRIMARY KEY,
    product_name_fr   VARCHAR(100),       -- Crédit immobilier, Carte Gold...
    product_name_en   VARCHAR(100),
    category_id       VARCHAR(50) REFERENCES product_categories(category_id),
    product_type      VARCHAR(30),        -- compte, crédit, carte, assurance, épargne
    min_amount        DECIMAL(15,2),
    max_amount        DECIMAL(15,2),
    interest_rate     DECIMAL(5,4),
    fee_monthly       DECIMAL(10,2),
    is_active         BOOLEAN DEFAULT TRUE,
    launch_date       DATE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `product_categories` — Catégories de produits bancaires
### `product_subscriptions` — Client product subscriptions
### `product_pricing` — Grille tarifaire par produit

---

## DOMAIN 5 — LOAN (10 tables) ← MOST CRITICAL MISSING DOMAIN

### `loan_contracts`
```sql
CREATE TABLE loan_contracts (
    loan_id           VARCHAR(50) UNIQUE NOT NULL,
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    account_id        VARCHAR(50) REFERENCES accounts(account_id),
    branch_id         VARCHAR(50),
    loan_product_id   VARCHAR(50),
    loan_type         VARCHAR(50),        -- immobilier, consommation, automobile, professionnel
    principal_amount  DECIMAL(15,2) NOT NULL,
    currency          VARCHAR(3) DEFAULT 'TND',
    interest_rate     DECIMAL(5,4) NOT NULL,
    term_months       INTEGER NOT NULL,
    installment_amount DECIMAL(15,2),
    disbursement_date DATE,
    maturity_date     DATE,
    status            VARCHAR(30),        -- actif, remboursé, en_retard, contentieux, restructuré
    outstanding_balance DECIMAL(15,2),
    days_past_due     INTEGER DEFAULT 0,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `loan_products` — Définitions des produits de crédit
### `loan_installments` — Échéancier de remboursement
### `loan_repayments` — Paiements effectués
### `loan_delinquency_events` — Incidents de paiement
### `loan_restructuring` — Historique de restructuration
### `collateral` — Garanties réelles (hypothèques, nantissements)
### `guarantees` — Cautions personnelles
### `provisions` — Provisions pour créances douteuses
### `non_performing_loans` — Créances classées / NPL

---

## DOMAIN 6 — PAYMENT (6 tables)

### `payment_methods` — Reference table of payment methods
### `transaction_channels` — Canal de transaction (agence, DAB, internet, mobile)
### `transfers` — Virements inter-comptes et interbancaires
### `cash_operations` — Opérations espèces (versement/retrait DAB)
### `merchant_payments` — Paiements commerçants (TPE, e-commerce)
### `standing_orders` — Ordres permanents (virements automatiques récurrents)
### `failed_transactions` — Transactions rejetées avec motif

---

## DOMAIN 7 — RISK (8 tables)

### `risk_events` — Événements de risque ponctuels
### `risk_models` — Modèles de scoring (crédit, fraude, liquidité)
### `risk_assessments` — Évaluations périodiques par modèle
### `risk_score_history` — Historique des scores (time series 24 months)
### `risk_limits` — Limites d'exposition par client/produit
### `risk_exposure` — Exposition actuelle par type de risque
### `portfolio_risk_summary` — Vue agrégée du portefeuille risque (monthly snapshots)

---

## DOMAIN 8 — COMPLIANCE (7 tables)

### `compliance_cases` — Cases ouverts pour investigation
### `compliance_reviews` — Revues compliance périodiques
### `audit_findings` — Constats d'audit interne/externe
### `aml_alerts` — Alertes LCB-FT (Anti-Money Laundering)
```sql
CREATE TABLE aml_alerts (
    alert_id          VARCHAR(50) UNIQUE NOT NULL,
    customer_id       VARCHAR(50) REFERENCES customers(customer_id),
    account_id        VARCHAR(50) REFERENCES accounts(account_id),
    transaction_id    VARCHAR(50) REFERENCES transactions(transaction_id),
    alert_type        VARCHAR(50),        -- transaction_inhabituelle, seuil_dépassé, structuring, PEP
    alert_label_fr    VARCHAR(255),       -- "Suspicion AML: Dépôt espèces atypique"
    severity          VARCHAR(20),        -- faible, moyen, élevé, critique
    status            VARCHAR(20),        -- ouvert, en_cours, clôturé, faux_positif
    score             DECIMAL(5,2),
    triggered_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at         TIMESTAMP,
    analyst_id        VARCHAR(100),
    resolution        TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `suspicious_activity_reports` — DSFR (Déclaration de Soupçon — CTAF Tunisia)
### `regulatory_reports` ← already exists, extend

---

## DOMAIN 9 — FINANCE / GL (8 tables)

### `general_ledger`
```sql
CREATE TABLE general_ledger (
    ledger_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_code      VARCHAR(20) NOT NULL,           -- Plan comptable bancaire
    account_name_fr   VARCHAR(200),
    account_type      VARCHAR(30),                    -- actif, passif, produit, charge
    parent_code       VARCHAR(20),
    is_active         BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `ledger_entries` — Écritures comptables (debit/credit)
### `fee_income` — Produits de commissions par type et période
### `interest_income` — Produits d'intérêts par portefeuille
### `operating_expenses` — Charges d'exploitation
### `profitability_metrics` — Métriques de rentabilité calculées
### `balance_sheet_snapshots` — Bilan mensuel (actif/passif)
### `income_statement_snapshots` — Compte de résultat mensuel

---

## DOMAIN 10 — ORGANIZATION (6 tables)

### `regions`
```sql
CREATE TABLE regions (
    region_id         VARCHAR(50) PRIMARY KEY,
    region_name_fr    VARCHAR(100),       -- Grand Tunis, Nord-Est, Centre-Ouest...
    governorates      TEXT[],             -- Array of governorates in this region
    population        INTEGER,
    gdp_contribution  DECIMAL(5,2),       -- % of national GDP
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `departments` — Départements fonctionnels (Risque, Conformité, Commercial...)
### `business_units` — Unités métier
### `employees`
```sql
CREATE TABLE employees (
    employee_id       VARCHAR(50) UNIQUE NOT NULL,
    branch_id         VARCHAR(50) REFERENCES branches(branch_id),
    department_id     VARCHAR(50),
    first_name        VARCHAR(100),
    last_name         VARCHAR(100),
    title             VARCHAR(100),       -- Chargé de clientèle, Directeur d'agence...
    role              VARCHAR(50),        -- relationship_manager, analyst, manager, compliance
    hire_date         DATE,
    is_active         BOOLEAN DEFAULT TRUE,
    email             VARCHAR(255),
    supervisor_id     VARCHAR(50),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `relationship_managers` — RM-to-customer portfolio assignments

---

## DOMAIN 11 — SEMANTIC LAYER (5 tables — NEW, CRITICAL)

### `business_glossary`
```sql
CREATE TABLE business_glossary (
    term_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term              VARCHAR(100) UNIQUE NOT NULL,   -- "NPL", "ROE", "Encours"
    definition        TEXT NOT NULL,
    synonyms          TEXT[],                          -- ["créances classées", "bad loans", "NPL"]
    domain            VARCHAR(50),
    business_owner    VARCHAR(100),
    source_tables     TEXT[],
    formula           TEXT,
    example           TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `metric_registry`
```sql
CREATE TABLE metric_registry (
    metric_id         VARCHAR(50) PRIMARY KEY,
    metric_name_fr    VARCHAR(200),
    metric_name_en    VARCHAR(200),
    formula           TEXT NOT NULL,
    description       TEXT,
    domain            VARCHAR(50),
    owner             VARCHAR(100),
    source_tables     TEXT[],
    dependencies      TEXT[],                          -- other metric_ids
    unit              VARCHAR(20),                     -- %, TND, count, ratio
    refresh_frequency VARCHAR(20),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `table_metadata`
```sql
CREATE TABLE table_metadata (
    table_name        VARCHAR(100) PRIMARY KEY,
    business_description TEXT,
    domain            VARCHAR(50),
    owner             VARCHAR(100),
    row_count_estimate INTEGER,
    is_analytical     BOOLEAN DEFAULT FALSE,            -- snapshot vs operational
    is_pii_bearing    BOOLEAN DEFAULT FALSE,
    refresh_frequency VARCHAR(20),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `column_metadata`
```sql
CREATE TABLE column_metadata (
    metadata_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name        VARCHAR(100) NOT NULL,
    column_name       VARCHAR(100) NOT NULL,
    business_description TEXT,
    synonyms          TEXT[],
    data_type         VARCHAR(50),
    is_pii            BOOLEAN DEFAULT FALSE,
    example_values    TEXT[],
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_name, column_name)
);
```

### `join_registry`
```sql
CREATE TABLE join_registry (
    join_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table      VARCHAR(100) NOT NULL,
    source_column     VARCHAR(100) NOT NULL,
    target_table      VARCHAR(100) NOT NULL,
    target_column     VARCHAR(100) NOT NULL,
    relationship_type VARCHAR(20),                     -- one_to_many, many_to_one, one_to_one
    join_type         VARCHAR(20) DEFAULT 'LEFT JOIN',
    confidence        DECIMAL(3,2) DEFAULT 1.00,
    notes             TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_table, source_column, target_table, target_column)
);
```

---

## TABLE COUNT SUMMARY

| Domain | New Tables | Total with Existing |
|--------|-----------|---------------------|
| Existing (unchanged) | — | 23 |
| Customer | 10 | +10 |
| KYC | 7 | +7 |
| Account (extensions) | 5 | +5 |
| Product | 4 | +4 |
| Loan | 10 | +10 |
| Payment (extensions) | 6 | +6 |
| Risk (extensions) | 7 | +7 |
| Compliance (extensions) | 5 | +5 |
| Finance / GL | 8 | +8 |
| Organization | 6 | +6 |
| Semantic Layer | 5 | +5 |
| **TOTAL** | **73 new** | **96 tables** |

---

## FOREIGN KEY INTEGRITY MAP (Critical Relationships)

```
regions ──────────────────► branches.region_id
branches ─────────────────► accounts.branch_id        (FK now enforced)
branches ─────────────────► employees.branch_id
departments ──────────────► employees.department_id

customers ────────────────► customer_profiles.customer_id
customers ────────────────► customer_addresses.customer_id
customers ────────────────► customer_contacts.customer_id
customers ────────────────► customer_risk_scores.customer_id
customers ────────────────► customer_documents.customer_id
customers ────────────────► customer_preferences.customer_id
customers ────────────────► customer_status_history.customer_id

customers ────────────────► kyc_cases.customer_id
kyc_cases ────────────────► kyc_reviews.kyc_case_id
kyc_cases ────────────────► kyc_documents.kyc_case_id
kyc_cases ────────────────► kyc_verifications.kyc_case_id
customers ────────────────► pep_screening.customer_id
customers ────────────────► sanctions_screening.customer_id

customers ────────────────► loan_contracts.customer_id
accounts ─────────────────► loan_contracts.account_id
loan_contracts ───────────► loan_installments.loan_id
loan_contracts ───────────► loan_repayments.loan_id
loan_contracts ───────────► loan_delinquency_events.loan_id
loan_contracts ───────────► collateral.loan_id
loan_contracts ───────────► provisions.loan_id
loan_contracts ───────────► non_performing_loans.loan_id

transactions ─────────────► aml_alerts.transaction_id
customers ────────────────► aml_alerts.customer_id
accounts ─────────────────► aml_alerts.account_id
aml_alerts ───────────────► suspicious_activity_reports.alert_id

general_ledger ───────────► ledger_entries.account_code
```

---

## IMPLEMENTATION NOTES

1. **No table drops** — all 23 existing tables preserved
2. **FK backfill** — add missing `accounts.branch_id` FK to `branches`
3. **Column fix** — fix `sql_builder.py` ALLOWED_COLUMNS for `branches` and `risk_flags`
4. **Semantic layer first** — `business_glossary`, `metric_registry`, `table_metadata`, `column_metadata`, `join_registry` deployed before agents consume them
5. **Loan domain priority** — deploys before Finance domain; unblocks 6 unavailable KPIs
6. **GL domain** — enables ROA, ROE, Cost-to-Income, LCR, NSFR computation
