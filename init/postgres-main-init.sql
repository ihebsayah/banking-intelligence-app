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
