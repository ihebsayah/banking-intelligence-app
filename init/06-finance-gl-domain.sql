-- =============================================================================
-- Phase 6A: Finance & General Ledger Domain Schema
-- init/06-finance-gl-domain.sql
-- =============================================================================

-- 1. General Ledger Table
CREATE TABLE IF NOT EXISTS general_ledger (
    ledger_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_code      VARCHAR(20) UNIQUE NOT NULL,    -- Plan comptable bancaire
    account_name_fr   VARCHAR(200),
    account_type      VARCHAR(30),                    -- actif, passif, produit, charge
    parent_code       VARCHAR(20),
    is_active         BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gl_account_code ON general_ledger(account_code);

-- 2. Ledger Entries Table
CREATE TABLE IF NOT EXISTS ledger_entries (
    entry_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_code      VARCHAR(20) NOT NULL REFERENCES general_ledger(account_code),
    transaction_id    VARCHAR(50),                   -- References transactions if applicable
    debit_amount      DECIMAL(15,2) DEFAULT 0.00,
    credit_amount     DECIMAL(15,2) DEFAULT 0.00,
    currency          VARCHAR(3) DEFAULT 'TND',
    value_date        DATE NOT NULL,
    description       TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ledger_entries_code ON ledger_entries(account_code);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_date ON ledger_entries(value_date);

-- 3. Fee Income Table
CREATE TABLE IF NOT EXISTS fee_income (
    fee_income_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) REFERENCES customers(customer_id),
    account_id        VARCHAR(50) REFERENCES accounts(account_id),
    fee_type          VARCHAR(50) NOT NULL,          -- tenue_compte, découvert, transaction, prélèvement
    amount            DECIMAL(15,2) NOT NULL,
    value_date        DATE NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fee_income_customer ON fee_income(customer_id);

-- 4. Interest Income Table
CREATE TABLE IF NOT EXISTS interest_income (
    interest_income_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id           VARCHAR(50) REFERENCES loan_contracts(loan_id),
    account_id        VARCHAR(50) REFERENCES accounts(account_id),
    amount            DECIMAL(15,2) NOT NULL,
    value_date        DATE NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Operating Expenses Table
CREATE TABLE IF NOT EXISTS operating_expenses (
    expense_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expense_type      VARCHAR(50) NOT NULL,          -- personnel, loyer, informatique, marketing
    amount            DECIMAL(15,2) NOT NULL,
    value_date        DATE NOT NULL,
    branch_id         VARCHAR(50),
    description       TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_operating_expenses_type ON operating_expenses(expense_type);
CREATE INDEX IF NOT EXISTS idx_operating_expenses_date ON operating_expenses(value_date);

-- 6. Profitability Metrics Table
CREATE TABLE IF NOT EXISTS profitability_metrics (
    metric_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id         VARCHAR(50),
    product_id        VARCHAR(50),
    customer_id       VARCHAR(50) REFERENCES customers(customer_id),
    pnb               DECIMAL(15,2) NOT NULL,        -- Produit Net Bancaire
    net_income        DECIMAL(15,2) NOT NULL,
    cost_to_income_ratio DECIMAL(5,2),
    calculation_date  DATE NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Balance Sheet Snapshots Table
CREATE TABLE IF NOT EXISTS balance_sheet_snapshots (
    snapshot_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period            VARCHAR(7) NOT NULL,           -- YYYY-MM
    total_assets      DECIMAL(20,2) NOT NULL,
    total_liabilities DECIMAL(20,2) NOT NULL,
    total_equity      DECIMAL(20,2) NOT NULL,
    hqla              DECIMAL(20,2),                 -- High Quality Liquid Assets (for LCR)
    net_outflows_30d  DECIMAL(20,2),                 -- (for LCR)
    available_stable_funding DECIMAL(20,2),          -- (for NSFR)
    required_stable_funding DECIMAL(20,2),           -- (for NSFR)
    snapshot_date     DATE NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_balance_sheet_period ON balance_sheet_snapshots(period);

-- 8. Income Statement Snapshots Table
CREATE TABLE IF NOT EXISTS income_statement_snapshots (
    snapshot_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period            VARCHAR(7) NOT NULL,           -- YYYY-MM
    interest_income   DECIMAL(20,2) NOT NULL,
    interest_expense  DECIMAL(20,2) NOT NULL,
    fee_income        DECIMAL(20,2) NOT NULL,
    net_banking_income DECIMAL(20,2) NOT NULL,       -- PNB
    operating_expenses DECIMAL(20,2) NOT NULL,
    pnb               DECIMAL(20,2) NOT NULL,        -- net banking income duplicate for metric alignment
    net_income        DECIMAL(20,2) NOT NULL,
    snapshot_date     DATE NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_income_statement_period ON income_statement_snapshots(period);
