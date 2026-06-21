-- =============================================================================
-- Phase 6A: Loan Domain Schema
-- init/04-loan-domain.sql
-- =============================================================================

-- 1. Loan Products Table
CREATE TABLE IF NOT EXISTS loan_products (
    loan_product_id   VARCHAR(50) PRIMARY KEY,
    name              VARCHAR(255) NOT NULL,         -- e.g. "Crédit Immobilier"
    description       TEXT,
    min_amount        DECIMAL(15,2),
    max_amount        DECIMAL(15,2),
    min_interest_rate DECIMAL(5,4),
    max_interest_rate DECIMAL(5,4),
    min_term_months   INTEGER,
    max_term_months   INTEGER,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Loan Contracts Table
CREATE TABLE IF NOT EXISTS loan_contracts (
    loan_id           VARCHAR(50) PRIMARY KEY,
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    account_id        VARCHAR(50) REFERENCES accounts(account_id),
    branch_id         VARCHAR(50),
    loan_product_id   VARCHAR(50) REFERENCES loan_products(loan_product_id),
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

CREATE INDEX IF NOT EXISTS idx_loan_contracts_customer ON loan_contracts(customer_id);
CREATE INDEX IF NOT EXISTS idx_loan_contracts_account ON loan_contracts(account_id);
CREATE INDEX IF NOT EXISTS idx_loan_contracts_branch ON loan_contracts(branch_id);
CREATE INDEX IF NOT EXISTS idx_loan_contracts_status ON loan_contracts(status);

-- 3. Loan Installments Table
CREATE TABLE IF NOT EXISTS loan_installments (
    installment_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id            VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
    installment_number INTEGER NOT NULL,
    due_date           DATE NOT NULL,
    principal_amount   DECIMAL(15,2) NOT NULL,
    interest_amount    DECIMAL(15,2) NOT NULL,
    total_amount       DECIMAL(15,2) NOT NULL,
    status             VARCHAR(20) DEFAULT 'unpaid', -- paid, unpaid, partially_paid
    paid_amount        DECIMAL(15,2) DEFAULT 0,
    paid_date          DATE,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_loan_installments_loan ON loan_installments(loan_id);
CREATE INDEX IF NOT EXISTS idx_loan_installments_due ON loan_installments(due_date);

-- 4. Loan Repayments Table
CREATE TABLE IF NOT EXISTS loan_repayments (
    repayment_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id            VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
    installment_id     UUID REFERENCES loan_installments(installment_id),
    amount             DECIMAL(15,2) NOT NULL,
    repayment_date     DATE NOT NULL,
    payment_method     VARCHAR(50), -- virement, prélèvement, versement
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_loan_repayments_loan ON loan_repayments(loan_id);

-- 5. Loan Delinquency Events Table
CREATE TABLE IF NOT EXISTS loan_delinquency_events (
    event_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id            VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
    event_date         DATE NOT NULL,
    days_past_due      INTEGER NOT NULL,
    outstanding_balance DECIMAL(15,2) NOT NULL,
    resolved           BOOLEAN DEFAULT FALSE,
    resolved_date      DATE,
    notes              TEXT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_loan_delinquency_loan ON loan_delinquency_events(loan_id);

-- 6. Loan Restructuring Table
CREATE TABLE IF NOT EXISTS loan_restructuring (
    restructuring_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id            VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
    request_date       DATE NOT NULL,
    approval_date      DATE,
    previous_principal DECIMAL(15,2),
    previous_interest_rate DECIMAL(5,4),
    previous_term      INTEGER,
    new_principal      DECIMAL(15,2),
    new_interest_rate  DECIMAL(5,4),
    new_term           INTEGER,
    reason             TEXT,
    status             VARCHAR(30), -- approuvé, rejeté, en_attente
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_loan_restruct_loan ON loan_restructuring(loan_id);

-- 7. Collateral Table
CREATE TABLE IF NOT EXISTS collateral (
    collateral_id      VARCHAR(50) PRIMARY KEY,
    loan_id            VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
    collateral_type    VARCHAR(50), -- hypothèque, nantissement, gage, dépôt
    description        TEXT,
    estimated_value    DECIMAL(15,2) NOT NULL,
    valuation_date     DATE,
    valuer_name        VARCHAR(100),
    status             VARCHAR(30), -- actif, libéré, réalisé
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_collateral_loan ON collateral(loan_id);

-- 8. Guarantees Table
CREATE TABLE IF NOT EXISTS guarantees (
    guarantee_id       VARCHAR(50) PRIMARY KEY,
    loan_id            VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
    guarantor_name     VARCHAR(255) NOT NULL,
    guarantor_id       VARCHAR(50), -- CIN or customer_id
    guarantee_amount   DECIMAL(15,2) NOT NULL,
    guarantee_type     VARCHAR(50), -- caution_solidaire, caution_simple
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_guarantees_loan ON guarantees(loan_id);

-- 9. Provisions Table
CREATE TABLE IF NOT EXISTS provisions (
    provision_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id            VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
    provision_date     DATE NOT NULL,
    provision_amount   DECIMAL(15,2) NOT NULL,
    calculation_model  VARCHAR(50), -- IFRS9, BCT_standard
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_provisions_loan ON provisions(loan_id);

-- 10. Non-Performing Loans Table
CREATE TABLE IF NOT EXISTS non_performing_loans (
    npl_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id            VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id) UNIQUE,
    npl_amount         DECIMAL(15,2) NOT NULL,
    npl_date           DATE NOT NULL,
    classification     VARCHAR(50) NOT NULL, -- pré-douteux, douteux, compromis
    recovery_status    VARCHAR(30) DEFAULT 'unrecovered', -- unrecovered, partially_recovered, fully_recovered
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_npl_loan ON non_performing_loans(loan_id);
