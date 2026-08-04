-- =============================================================================
-- Banking Main Database Schema
-- postgres-main: banking_dev
-- =============================================================================

-- Customers Table
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    kyc_verified BOOLEAN DEFAULT FALSE,
    risk_score DECIMAL(3,2),
    segment VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_customers_customer_id ON customers(customer_id);
CREATE INDEX IF NOT EXISTS idx_customers_kyc ON customers(kyc_verified);
CREATE INDEX IF NOT EXISTS idx_customers_segment ON customers(segment);
CREATE INDEX IF NOT EXISTS idx_customers_risk_score ON customers(risk_score);
CREATE INDEX IF NOT EXISTS idx_customers_created ON customers(created_at);

-- Accounts Table
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(50) UNIQUE NOT NULL,
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    account_type VARCHAR(50),
    status VARCHAR(20),
    balance DECIMAL(15,2),
    available_balance DECIMAL(15,2),
    currency VARCHAR(3) DEFAULT 'USD',
    branch_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts(account_id);
CREATE INDEX IF NOT EXISTS idx_accounts_customer_id ON accounts(customer_id);
CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);
CREATE INDEX IF NOT EXISTS idx_accounts_branch_id ON accounts(branch_id);
CREATE INDEX IF NOT EXISTS idx_accounts_created ON accounts(created_at);

-- Transactions Table
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id VARCHAR(50) UNIQUE NOT NULL,
    account_id VARCHAR(50) NOT NULL REFERENCES accounts(account_id),
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    amount DECIMAL(15,2),
    transaction_type VARCHAR(50),
    status VARCHAR(20),
    description TEXT,
    transaction_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_transaction_id ON transactions(transaction_id);
CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_customer_id ON transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);

-- Risk Flags Table
CREATE TABLE IF NOT EXISTS risk_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    flag_type VARCHAR(50),
    severity VARCHAR(20),  -- low, medium, high, critical
    description TEXT,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_flags_customer_id ON risk_flags(customer_id);
CREATE INDEX IF NOT EXISTS idx_risk_flags_severity ON risk_flags(severity);
CREATE INDEX IF NOT EXISTS idx_risk_flags_type ON risk_flags(flag_type);

-- Branches Table
CREATE TABLE IF NOT EXISTS branches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255),
    state VARCHAR(50),
    city VARCHAR(100),
    manager_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_branches_branch_id ON branches(branch_id);
CREATE INDEX IF NOT EXISTS idx_branches_state ON branches(state);

-- Products Table
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255),
    category VARCHAR(50),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_product_id ON products(product_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- =============================================================================
-- Seed Data (Sample records for testing)
-- =============================================================================

-- Insert sample branches
INSERT INTO branches (branch_id, name, state, city, manager_id) VALUES
    ('BR001', 'New York HQ Branch', 'NY', 'New York', 'MGR001'),
    ('BR002', 'Los Angeles Branch', 'CA', 'Los Angeles', 'MGR002'),
    ('BR003', 'Chicago Branch', 'IL', 'Chicago', 'MGR003'),
    ('BR004', 'Houston Branch', 'TX', 'Houston', 'MGR004'),
    ('BR005', 'Boston Branch', 'MA', 'Boston', 'MGR005')
ON CONFLICT (branch_id) DO NOTHING;

-- Insert sample customers
INSERT INTO customers (customer_id, name, email, phone, kyc_verified, risk_score, segment) VALUES
    ('CUST001', 'Alice Johnson', 'alice@example.com', '555-0101', TRUE, 0.12, 'premium'),
    ('CUST002', 'Bob Smith', 'bob@example.com', '555-0102', TRUE, 0.45, 'standard'),
    ('CUST003', 'Carol Williams', 'carol@example.com', '555-0103', FALSE, 0.78, 'high_risk'),
    ('CUST004', 'David Brown', 'david@example.com', '555-0104', TRUE, 0.23, 'premium'),
    ('CUST005', 'Eve Davis', 'eve@example.com', '555-0105', TRUE, 0.15, 'premium')
ON CONFLICT (customer_id) DO NOTHING;

-- Insert sample accounts
INSERT INTO accounts (account_id, customer_id, account_type, status, balance, available_balance, currency, branch_id) VALUES
    ('ACC001', 'CUST001', 'checking', 'active', 150000.00, 148000.00, 'USD', 'BR001'),
    ('ACC002', 'CUST001', 'savings', 'active', 500000.00, 500000.00, 'USD', 'BR001'),
    ('ACC003', 'CUST002', 'checking', 'active', 25000.00, 24000.00, 'USD', 'BR002'),
    ('ACC004', 'CUST003', 'checking', 'frozen', 5000.00, 0.00, 'USD', 'BR003'),
    ('ACC005', 'CUST004', 'savings', 'active', 320000.00, 320000.00, 'USD', 'BR001')
ON CONFLICT (account_id) DO NOTHING;

-- Insert sample transactions
INSERT INTO transactions (transaction_id, account_id, customer_id, amount, transaction_type, status, description, transaction_date) VALUES
    ('TXN001', 'ACC001', 'CUST001', 5000.00, 'credit', 'completed', 'Salary deposit', NOW() - INTERVAL '5 days'),
    ('TXN002', 'ACC001', 'CUST001', -1200.00, 'debit', 'completed', 'Mortgage payment', NOW() - INTERVAL '4 days'),
    ('TXN003', 'ACC003', 'CUST002', 250.00, 'credit', 'completed', 'Freelance payment', NOW() - INTERVAL '3 days'),
    ('TXN004', 'ACC004', 'CUST003', 15000.00, 'credit', 'flagged', 'Cash deposit - suspicious', NOW() - INTERVAL '2 days'),
    ('TXN005', 'ACC005', 'CUST004', 10000.00, 'debit', 'completed', 'Wire transfer', NOW() - INTERVAL '1 day')
ON CONFLICT (transaction_id) DO NOTHING;

-- Insert sample risk flags
INSERT INTO risk_flags (customer_id, flag_type, severity, description) VALUES
    ('CUST003', 'aml_suspicious', 'high', 'Large cash deposit without explanation'),
    ('CUST003', 'kyc_incomplete', 'medium', 'KYC verification not completed'),
    ('CUST002', 'unusual_pattern', 'low', 'Transaction pattern changed significantly')
ON CONFLICT DO NOTHING;

-- Insert sample products
INSERT INTO products (product_id, name, category) VALUES
    ('PROD001', 'Premium Checking Account', 'checking'),
    ('PROD002', 'High-Yield Savings', 'savings'),
    ('PROD003', 'Personal Loan', 'loan'),
    ('PROD004', 'Business Credit Line', 'credit'),
    ('PROD005', 'Investment Portfolio', 'investment')
ON CONFLICT (product_id) DO NOTHING;

-- =============================================================================
-- Tunisia Seed Data
-- =============================================================================

-- Insert Tunisia branches
INSERT INTO branches (branch_id, name, state, city, manager_id) VALUES
    ('BR_TN_001', 'Tunis Main Branch', 'Tunis', 'Tunis', 'MGR_TN_001'),
    ('BR_TN_002', 'Sfax Hub Branch', 'Sfax', 'Sfax', 'MGR_TN_002'),
    ('BR_TN_003', 'Sousse Coastal Branch', 'Sousse', 'Sousse', 'MGR_TN_003')
ON CONFLICT (branch_id) DO NOTHING;

-- Insert Tunisia customers
INSERT INTO customers (customer_id, name, email, phone, kyc_verified, risk_score, segment) VALUES
    ('CUST_TN_001', 'Ahmed Trabelsi', 'ahmed.t@example.tn', '+216 20 123 456', TRUE, 0.10, 'premium'),
    ('CUST_TN_002', 'Fatma Ben Ali', 'fatma.b@example.tn', '+216 21 987 654', TRUE, 0.25, 'standard'),
    ('CUST_TN_003', 'Mohamed Gharbi', 'mohamed.g@example.tn', '+216 55 111 222', FALSE, 0.65, 'high_risk'),
    ('CUST_TN_004', 'Youssef Khemiri', 'youssef.k@example.tn', '+216 98 333 444', TRUE, 0.15, 'premium'),
    ('CUST_TN_005', 'Amina Baccar', 'amina.b@example.tn', '+216 50 555 666', TRUE, 0.05, 'standard')
ON CONFLICT (customer_id) DO NOTHING;

-- Insert Tunisia accounts (Currency TND)
INSERT INTO accounts (account_id, customer_id, account_type, status, balance, available_balance, currency, branch_id) VALUES
    ('ACC_TN_001', 'CUST_TN_001', 'checking', 'active', 45000.00, 44000.00, 'TND', 'BR_TN_001'),
    ('ACC_TN_002', 'CUST_TN_001', 'savings', 'active', 120000.00, 120000.00, 'TND', 'BR_TN_001'),
    ('ACC_TN_003', 'CUST_TN_002', 'checking', 'active', 8500.00, 8000.00, 'TND', 'BR_TN_002'),
    ('ACC_TN_004', 'CUST_TN_003', 'checking', 'frozen', 1500.00, 0.00, 'TND', 'BR_TN_003'),
    ('ACC_TN_005', 'CUST_TN_004', 'savings', 'active', 75000.00, 75000.00, 'TND', 'BR_TN_001')
ON CONFLICT (account_id) DO NOTHING;

-- Insert Tunisia transactions
INSERT INTO transactions (transaction_id, account_id, customer_id, amount, transaction_type, status, description, transaction_date) VALUES
    ('TXN_TN_001', 'ACC_TN_001', 'CUST_TN_001', 3500.00, 'credit', 'completed', 'Salary deposit (Tunis)', NOW() - INTERVAL '3 days'),
    ('TXN_TN_002', 'ACC_TN_001', 'CUST_TN_001', -800.00, 'debit', 'completed', 'Utility bills STEG/SONEDE', NOW() - INTERVAL '2 days'),
    ('TXN_TN_003', 'ACC_TN_003', 'CUST_TN_002', 450.00, 'credit', 'completed', 'Freelance payment from abroad', NOW() - INTERVAL '1 day'),
    ('TXN_TN_004', 'ACC_TN_004', 'CUST_TN_003', 12000.00, 'credit', 'flagged', 'Unexplained large cash deposit in Sousse', NOW() - INTERVAL '4 days'),
    ('TXN_TN_005', 'ACC_TN_005', 'CUST_TN_004', -2000.00, 'debit', 'completed', 'Car loan installment', NOW() - INTERVAL '5 days')
ON CONFLICT (transaction_id) DO NOTHING;

-- Insert Tunisia risk flags
INSERT INTO risk_flags (customer_id, flag_type, severity, description) VALUES
    ('CUST_TN_003', 'aml_suspicious', 'high', 'Unexplained large cash deposit in Sousse branch'),
    ('CUST_TN_003', 'kyc_incomplete', 'medium', 'Missing national ID update (CIN)'),
    ('CUST_TN_002', 'unusual_pattern', 'low', 'Frequent small international transfers')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Bulk Tunisia Seed Data (200 rows per table)
-- =============================================================================

-- 200 Branches
INSERT INTO branches (branch_id, name, state, city, manager_id)
SELECT 
    'BR_TN_GEN_' || i, 
    'Branch ' || i || ' ' || (ARRAY['Tunis', 'Sfax', 'Sousse', 'Bizerte', 'Gabes', 'Ariana', 'Gafsa', 'Monastir'])[1 + (i % 8)], 
    (ARRAY['Tunis', 'Sfax', 'Sousse', 'Bizerte', 'Gabes', 'Ariana', 'Gafsa', 'Monastir'])[1 + (i % 8)], 
    (ARRAY['Tunis', 'Sfax', 'Sousse', 'Bizerte', 'Gabes', 'Ariana', 'Gafsa', 'Monastir'])[1 + (i % 8)], 
    'MGR_TN_GEN_' || i
FROM generate_series(1, 200) AS i
ON CONFLICT (branch_id) DO NOTHING;

-- 200 Customers
INSERT INTO customers (customer_id, name, email, phone, kyc_verified, risk_score, segment)
SELECT 
    'CUST_TN_GEN_' || i, 
    (ARRAY['Ahmed', 'Fatma', 'Mohamed', 'Youssef', 'Amina', 'Ali', 'Samir', 'Nour', 'Omar', 'Leila'])[1 + (i % 10)] || ' ' || (ARRAY['Trabelsi', 'Ben Ali', 'Gharbi', 'Khemiri', 'Baccar', 'Ayari', 'Mejri', 'Driss'])[1 + (i % 8)] || ' ' || i,
    'user' || i || '@example.tn',
    '+216 ' || (20000000 + i),
    (i % 5 != 0),
    (random() * 0.9)::numeric(3,2),
    (ARRAY['standard', 'premium', 'high_risk'])[1 + (i % 3)]
FROM generate_series(1, 200) AS i
ON CONFLICT (customer_id) DO NOTHING;

-- 200 Accounts
INSERT INTO accounts (account_id, customer_id, account_type, status, balance, available_balance, currency, branch_id)
SELECT 
    'ACC_TN_GEN_' || i,
    'CUST_TN_GEN_' || i,
    (ARRAY['checking', 'savings', 'business'])[1 + (i % 3)],
    (ARRAY['active', 'active', 'active', 'frozen', 'closed'])[1 + (i % 5)],
    ROUND((random() * 100000)::numeric, 2),
    ROUND((random() * 90000)::numeric, 2),
    'TND',
    'BR_TN_GEN_' || (1 + (i % 200))
FROM generate_series(1, 200) AS i
ON CONFLICT (account_id) DO NOTHING;

-- 200 Transactions
INSERT INTO transactions (transaction_id, account_id, customer_id, amount, transaction_type, status, description, transaction_date)
SELECT 
    'TXN_TN_GEN_' || i,
    'ACC_TN_GEN_' || (1 + (i % 200)),
    'CUST_TN_GEN_' || (1 + (i % 200)),
    ROUND(((random() * 5000) - 2000)::numeric, 2),
    CASE WHEN (i % 2) = 0 THEN 'credit' ELSE 'debit' END,
    (ARRAY['completed', 'completed', 'completed', 'pending', 'flagged'])[1 + (i % 5)],
    (ARRAY['Salary deposit', 'Utility bill STEG', 'Online purchase', 'Transfer to Tunis', 'ATM Withdrawal'])[1 + (i % 5)],
    NOW() - (i || ' hours')::interval
FROM generate_series(1, 200) AS i
ON CONFLICT (transaction_id) DO NOTHING;

-- 200 Risk Flags
INSERT INTO risk_flags (customer_id, flag_type, severity, description)
SELECT 
    'CUST_TN_GEN_' || (1 + (i % 200)),
    (ARRAY['aml_suspicious', 'kyc_incomplete', 'unusual_pattern'])[1 + (i % 3)],
    (ARRAY['low', 'medium', 'high', 'critical'])[1 + (i % 4)],
    'Automated risk detection flag ' || i
FROM generate_series(1, 200) AS i
ON CONFLICT DO NOTHING;

-- 200 Products
INSERT INTO products (product_id, name, category, description)
SELECT 
    'PROD_TN_GEN_' || i,
    'Tunisian Bank Product ' || i,
    (ARRAY['checking', 'savings', 'loan', 'credit', 'investment'])[1 + (i % 5)],
    'Locally tailored financial product for Tunisian market ' || i
FROM generate_series(1, 200) AS i
ON CONFLICT (product_id) DO NOTHING;

-- =============================================================================
-- PHASE 2: Compliance & Audit Enhancement Schema
-- =============================================================================

-- Compliance Rules Table
CREATE TABLE IF NOT EXISTS compliance_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name VARCHAR(255) NOT NULL,
    regulation VARCHAR(50),
    rule_type VARCHAR(50),
    condition VARCHAR(500),
    action VARCHAR(500),
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_compliance_rules_regulation ON compliance_rules(regulation);
CREATE INDEX IF NOT EXISTS idx_compliance_rules_enabled    ON compliance_rules(enabled);

-- Data Lineage Table
CREATE TABLE IF NOT EXISTS data_lineage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id VARCHAR(100),
    source_table VARCHAR(100),
    source_column VARCHAR(100),
    destination_column VARCHAR(100),
    user_id VARCHAR(100),
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lineage_query_id     ON data_lineage(query_id);
CREATE INDEX IF NOT EXISTS idx_lineage_source_table ON data_lineage(source_table);
CREATE INDEX IF NOT EXISTS idx_lineage_user_id      ON data_lineage(user_id);
CREATE INDEX IF NOT EXISTS idx_lineage_accessed_at  ON data_lineage(accessed_at);

-- Compliance Violations Table
CREATE TABLE IF NOT EXISTS compliance_violations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id VARCHAR(100),
    user_id VARCHAR(100),
    violation_type VARCHAR(50),
    severity VARCHAR(20),
    description TEXT,
    regulation VARCHAR(50),
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'open',
    resolution_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_violations_query_id    ON compliance_violations(query_id);
CREATE INDEX IF NOT EXISTS idx_violations_user_id     ON compliance_violations(user_id);
CREATE INDEX IF NOT EXISTS idx_violations_severity    ON compliance_violations(severity);
CREATE INDEX IF NOT EXISTS idx_violations_status      ON compliance_violations(status);
CREATE INDEX IF NOT EXISTS idx_violations_detected_at ON compliance_violations(detected_at);

-- Regulatory Reports Table
CREATE TABLE IF NOT EXISTS regulatory_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_type VARCHAR(100),
    regulation VARCHAR(50),
    report_period_start DATE,
    report_period_end DATE,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    report_content TEXT,
    status VARCHAR(20) DEFAULT 'draft',
    submitted_to VARCHAR(255),
    submitted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reports_report_type ON regulatory_reports(report_type);
CREATE INDEX IF NOT EXISTS idx_reports_regulation  ON regulatory_reports(regulation);
CREATE INDEX IF NOT EXISTS idx_reports_status      ON regulatory_reports(status);

-- =============================================================================
-- Seed Compliance Rules (12 rules: GDPR x3, PCI-DSS x3, SOX x3, AML/KYC x3)
-- =============================================================================

INSERT INTO compliance_rules (rule_name, regulation, rule_type, condition, action, enabled) VALUES
    ('Mask PII - GDPR',                      'GDPR',    'data_masking',   'column IN (ssn, email, phone, national_id)', 'MASK_VALUE',       true),
    ('Right to be Forgotten - 3yr',           'GDPR',    'data_retention', 'last_activity < NOW() - INTERVAL 3 YEAR',   'DELETE_RECORD',    true),
    ('Data Portability on Request',           'GDPR',    'data_export',    'user_requests_export = true',               'EXPORT_JSON',      true),
    ('Mask Card Numbers - PCI-DSS',           'PCI-DSS', 'data_masking',   'column IN (credit_card, card_number, pan)', 'MASK_LAST4',       true),
    ('Restrict Card Data Access - PCI-DSS',   'PCI-DSS', 'access_control', 'user_role NOT IN (compliance, admin)',      'DENY_ACCESS',      true),
    ('Tokenize Card Data - PCI-DSS',          'PCI-DSS', 'data_handling',  'column = credit_card',                      'TOKENIZE',         true),
    ('Log All Sensitive Access - SOX',        'SOX',     'audit',          'table IN (accounts, transactions, risk_flags)', 'LOG_ACCESS',   true),
    ('Segregation of Duties - SOX',           'SOX',     'access_control', 'user_role IN (maker_checker)',           'DENY_ACCESS',      true),
    ('Change Management Approval - SOX',      'SOX',     'change_control', 'schema_change = true',                      'REQUIRE_APPROVAL', true),
    ('Monitor Large Transactions - AML',      'AML',     'monitoring',     'amount > 10000',                            'FLAG_TRANSACTION', true),
    ('Sanctions Screening - AML',             'AML',     'screening',      'new_customer = true',                       'SCREEN_NAMES',     true),
    ('Enhanced Due Diligence - KYC',          'KYC',     'due_diligence',  'pep_status = true',                         'REQUIRE_EDD',      true)
ON CONFLICT DO NOTHING;

