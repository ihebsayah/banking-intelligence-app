-- =============================================================================
-- Phase 6A: Organization, Customer Extensions, and Account Extensions Schema
-- init/07-org-customer-ext.sql
-- =============================================================================

-- ==========================================
-- 1. ORGANIZATION DOMAIN
-- ==========================================

-- Regions Table
CREATE TABLE IF NOT EXISTS regions (
    region_id         VARCHAR(50) PRIMARY KEY,
    region_name_fr    VARCHAR(100) NOT NULL,          -- Grand Tunis, Nord-Est, Centre-Ouest...
    governorates      TEXT[],                        -- Gouvernorats associés
    population        INTEGER,
    gdp_contribution  DECIMAL(5,2),                  -- % contribution PIB national
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alter branches to add region_id if it doesn't exist
ALTER TABLE branches ADD COLUMN IF NOT EXISTS region_id VARCHAR(50) REFERENCES regions(region_id);

-- Alter accounts to add FK to branches if it doesn't exist
-- First make sure branch_id in branches has a unique constraint (already does in init.sql)
ALTER TABLE accounts DROP CONSTRAINT IF EXISTS fk_accounts_branch;
ALTER TABLE accounts ADD CONSTRAINT fk_accounts_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id);

-- Departments Table
CREATE TABLE IF NOT EXISTS departments (
    department_id     VARCHAR(50) PRIMARY KEY,
    name_fr           VARCHAR(100) NOT NULL,         -- e.g. "Risque", "Conformité"
    name_en           VARCHAR(100),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Business Units Table
CREATE TABLE IF NOT EXISTS business_units (
    unit_id           VARCHAR(50) PRIMARY KEY,
    name_fr           VARCHAR(100) NOT NULL,         -- e.g. "Retail Banking", "Corporate"
    name_en           VARCHAR(100),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Employees Table
CREATE TABLE IF NOT EXISTS employees (
    employee_id       VARCHAR(50) PRIMARY KEY,
    branch_id         VARCHAR(50) REFERENCES branches(branch_id),
    department_id     VARCHAR(50) REFERENCES departments(department_id),
    first_name        VARCHAR(100) NOT NULL,
    last_name         VARCHAR(100) NOT NULL,
    title             VARCHAR(100),                  -- e.g. "Chargé de clientèle"
    role              VARCHAR(50),                   -- relationship_manager, analyst, manager, compliance
    hire_date         DATE,
    is_active         BOOLEAN DEFAULT TRUE,
    email             VARCHAR(255),
    supervisor_id     VARCHAR(50) REFERENCES employees(employee_id),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Relationship Managers Table
CREATE TABLE IF NOT EXISTS relationship_managers (
    rm_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id       VARCHAR(50) NOT NULL REFERENCES employees(employee_id),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id) UNIQUE,
    portfolio_type    VARCHAR(50),                   -- Retail, Corporate, Wealth
    assigned_date     DATE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 2. CUSTOMER EXTENSION DOMAIN
-- ==========================================

-- Customer Profiles Table
CREATE TABLE IF NOT EXISTS customer_profiles (
    profile_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id) UNIQUE,
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

-- Customer Segments Table
CREATE TABLE IF NOT EXISTS customer_segments (
    segment_id        VARCHAR(50) PRIMARY KEY,
    segment_name      VARCHAR(100) NOT NULL,
    segment_label_fr  VARCHAR(100),
    min_balance       DECIMAL(15,2),
    min_annual_income DECIMAL(15,2),
    description       TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Customer Addresses Table
CREATE TABLE IF NOT EXISTS customer_addresses (
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

CREATE INDEX IF NOT EXISTS idx_cust_addr_customer ON customer_addresses(customer_id);

-- Customer Contacts Table
CREATE TABLE IF NOT EXISTS customer_contacts (
    contact_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    contact_type      VARCHAR(20),                   -- mobile, fixe, email, whatsapp
    contact_value     VARCHAR(255),
    is_primary        BOOLEAN DEFAULT FALSE,
    verified          BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cust_cont_customer ON customer_contacts(customer_id);

-- Customer Risk Scores Table
CREATE TABLE IF NOT EXISTS customer_risk_scores (
    score_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    model_id          VARCHAR(50),                   -- e.g. "retail_v1", "corporate_v2"
    score             DECIMAL(5,4),
    score_band        VARCHAR(20),                   -- faible, moyen, élevé, critique
    score_date        DATE NOT NULL,
    factors           JSONB,                         -- contributing factors
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cust_risk_scores_cust ON customer_risk_scores(customer_id);

-- Customer Relationships Table
CREATE TABLE IF NOT EXISTS customer_relationships (
    relationship_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    related_customer_id VARCHAR(50) REFERENCES customers(customer_id),
    relationship_type VARCHAR(50),                   -- conjoint, garant, mandataire, tuteur
    valid_from        DATE,
    valid_to          DATE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Customer Documents Table
CREATE TABLE IF NOT EXISTS customer_documents (
    document_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    document_type     VARCHAR(50),                   -- CIN, passeport, justificatif_revenu
    document_number   VARCHAR(100),
    issued_date       DATE,
    expiry_date       DATE,
    verified          BOOLEAN DEFAULT FALSE,
    verified_by       VARCHAR(100),
    verified_at       TIMESTAMP,
    storage_ref       TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cust_docs_customer ON customer_documents(customer_id);

-- Customer Preferences Table
CREATE TABLE IF NOT EXISTS customer_preferences (
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

-- Customer Status History Table
CREATE TABLE IF NOT EXISTS customer_status_history (
    history_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    previous_status   VARCHAR(30),
    new_status        VARCHAR(30),
    changed_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by        VARCHAR(100),
    reason            TEXT
);

CREATE INDEX IF NOT EXISTS idx_cust_status_hist_cust ON customer_status_history(customer_id);

-- ==========================================
-- 3. ACCOUNT EXTENSION DOMAIN
-- ==========================================

-- Account Types Table
CREATE TABLE IF NOT EXISTS account_types (
    type_code         VARCHAR(50) PRIMARY KEY,
    type_name_fr      VARCHAR(100) NOT NULL,          -- Compte courant, Compte d'épargne...
    type_name_en      VARCHAR(100),
    currency          VARCHAR(3) DEFAULT 'TND',
    interest_rate     DECIMAL(5,4),
    min_balance       DECIMAL(15,2) DEFAULT 0.00,
    max_balance       DECIMAL(20,2),
    is_active         BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Account Balances (Historical Daily/Monthly Snapshots) Table
CREATE TABLE IF NOT EXISTS account_balances (
    balance_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id        VARCHAR(50) NOT NULL REFERENCES accounts(account_id),
    balance           DECIMAL(15,2) NOT NULL,
    available_balance DECIMAL(15,2) NOT NULL,
    snapshot_date     DATE NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_account_balances_acc ON account_balances(account_id);
CREATE INDEX IF NOT EXISTS idx_account_balances_date ON account_balances(snapshot_date);

-- Account Status History Table
CREATE TABLE IF NOT EXISTS account_status_history (
    history_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id        VARCHAR(50) NOT NULL REFERENCES accounts(account_id),
    previous_status   VARCHAR(20),
    new_status        VARCHAR(20),
    changed_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason            TEXT
);

-- Joint Accounts Table
CREATE TABLE IF NOT EXISTS joint_accounts (
    joint_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id        VARCHAR(50) NOT NULL REFERENCES accounts(account_id),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    relationship      VARCHAR(50),                   -- conjoint, associé, parent, etc.
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, customer_id)
);

-- Account Signatories Table
CREATE TABLE IF NOT EXISTS account_signatories (
    signatory_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id        VARCHAR(50) NOT NULL REFERENCES accounts(account_id),
    customer_id       VARCHAR(50) REFERENCES customers(customer_id),
    signatory_name    VARCHAR(255) NOT NULL,
    signatory_role    VARCHAR(50),                   -- mandataire, tuteur, signataire
    signature_specimen TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
