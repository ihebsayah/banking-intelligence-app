-- =============================================================================
-- Users, Roles, Permissions & KPI Definitions Schema Extensions
-- =============================================================================

-- 1. Roles Table
CREATE TABLE IF NOT EXISTS roles (
    role_id VARCHAR(50) PRIMARY KEY,
    label VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Permissions Table
CREATE TABLE IF NOT EXISTS permissions (
    permission_key VARCHAR(100) PRIMARY KEY,
    label VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL -- read | admin | write
);

-- 3. Role-Permissions Junction Table
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id VARCHAR(50) REFERENCES roles(role_id) ON DELETE CASCADE,
    permission_key VARCHAR(100) REFERENCES permissions(permission_key) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_key)
);

-- 4. Users Table (Modified with password_hash and must_change_password)
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(100) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) NOT NULL REFERENCES roles(role_id),
    bank_id VARCHAR(50) DEFAULT 'hq_main',
    password_hash VARCHAR(255) NOT NULL,
    permissions TEXT[] DEFAULT '{}', -- user-specific custom permission overrides
    must_change_password BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- 5. User Activity Log (Audit Trail)
CREATE TABLE IF NOT EXISTS user_activity_log (
    id BIGSERIAL PRIMARY KEY,
    actor_id VARCHAR(100) NOT NULL,
    target_id VARCHAR(100),
    action VARCHAR(100) NOT NULL,
    detail JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_activity_actor ON user_activity_log(actor_id);
CREATE INDEX IF NOT EXISTS idx_user_activity_created ON user_activity_log(created_at);

-- 6. KPI Categories Table
CREATE TABLE IF NOT EXISTS kpi_categories (
    category_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. KPI Owners Table
CREATE TABLE IF NOT EXISTS kpi_owners (
    owner_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. KPI Definitions Table (Altered safely below)
CREATE TABLE IF NOT EXISTS kpi_definitions (
    kpi_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    metric_type VARCHAR(20) NOT NULL, -- currency, percentage, count, ratio
    category VARCHAR(50),             -- category_id reference
    data_freshness VARCHAR(20) DEFAULT 'real-time',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Safe migrations: Add columns to kpi_definitions if they do not exist
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS formula TEXT;
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS owner_id VARCHAR(50);
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS source_tables TEXT[];
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS refresh_frequency VARCHAR(50) DEFAULT 'real-time';
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active';
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS reason TEXT;

-- 9. KPI Thresholds Table
CREATE TABLE IF NOT EXISTS kpi_thresholds (
    kpi_id VARCHAR(50) PRIMARY KEY REFERENCES kpi_definitions(kpi_id) ON DELETE CASCADE,
    healthy_min DECIMAL(15,4),
    healthy_max DECIMAL(15,4),
    warning_min DECIMAL(15,4),
    warning_max DECIMAL(15,4),
    critical_min DECIMAL(15,4),
    critical_max DECIMAL(15,4),
    healthy_label VARCHAR(50) DEFAULT 'Healthy',
    warning_label VARCHAR(50) DEFAULT 'Warning',
    critical_label VARCHAR(50) DEFAULT 'Critical',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. KPI History Table
CREATE TABLE IF NOT EXISTS kpi_history (
    history_id SERIAL PRIMARY KEY,
    kpi_id VARCHAR(50) REFERENCES kpi_definitions(kpi_id) ON DELETE CASCADE,
    changed_by VARCHAR(100) NOT NULL,
    change_type VARCHAR(50) NOT NULL, -- 'definition_update', 'threshold_change', 'owner_assignment', 'status_change'
    old_value JSONB,
    new_value JSONB,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kpis_category ON kpi_definitions(category);

-- =============================================================================
-- Seed Data
-- =============================================================================

-- Seed Roles
INSERT INTO roles (role_id, label, description) VALUES
    ('analyst', 'Analyst', 'Financial data analyst with read access to reports and key metrics'),
    ('manager', 'Branch Manager', 'Branch manager with operational reporting and summary performance access'),
    ('compliance', 'Compliance Officer', 'Compliance and risk officer with access to risk flags and audit trails'),
    ('admin', 'System Administrator', 'IT administrator with full access to user management and permission governance')
ON CONFLICT (role_id) DO NOTHING;

-- Seed Permissions
INSERT INTO permissions (permission_key, label, description, category) VALUES
    ('read:customers', 'Read Customer Data', 'View customer profile information', 'read'),
    ('read:accounts', 'Read Account Data', 'View account balances and details', 'read'),
    ('read:transactions', 'Read Transaction Data', 'View transaction history', 'read'),
    ('read:risk_flags', 'Read Risk Flags', 'View compliance risk flags', 'read'),
    ('read:risk_summary', 'Read Risk Summary', 'View aggregated portfolio risk metrics', 'read'),
    ('read:branch_data', 'Read Branch Data', 'View branch-specific performance metrics', 'read'),
    ('read:audit_logs', 'Read Audit Logs', 'View admin and system audit trails', 'read'),
    ('read:pii', 'Read PII Data', 'View personally identifiable customer details', 'read'),
    ('admin:users', 'Manage Users', 'Create, update, disable users', 'admin'),
    ('admin:roles', 'Manage Roles', 'Assign and modify roles and permissions', 'admin'),
    ('write:reports', 'Generate Reports', 'Generate and export system reports', 'write')
ON CONFLICT (permission_key) DO NOTHING;

-- Seed Role Permissions Junction
INSERT INTO role_permissions (role_id, permission_key) VALUES
    ('analyst', 'read:customers'),
    ('analyst', 'read:accounts'),
    ('analyst', 'read:transactions'),
    ('analyst', 'read:risk_flags'),
    ('manager', 'read:customers'),
    ('manager', 'read:accounts'),
    ('manager', 'read:transactions'),
    ('manager', 'read:branch_data'),
    ('manager', 'read:risk_summary'),
    ('compliance', 'read:customers'),
    ('compliance', 'read:accounts'),
    ('compliance', 'read:transactions'),
    ('compliance', 'read:risk_flags'),
    ('compliance', 'read:audit_logs'),
    ('compliance', 'read:pii'),
    ('admin', 'read:customers'),
    ('admin', 'read:accounts'),
    ('admin', 'read:transactions'),
    ('admin', 'read:risk_flags'),
    ('admin', 'read:audit_logs'),
    ('admin', 'read:pii'),
    ('admin', 'admin:users'),
    ('admin', 'admin:roles'),
    ('admin', 'write:reports')
ON CONFLICT DO NOTHING;

-- Seed Users
INSERT INTO users (user_id, email, name, role, bank_id, password_hash, permissions, status) VALUES
    ('analyst_001', 'analyst_001@bankintel.hq', 'Analyst One', 'analyst', 'hq_main', 
     '$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y', ARRAY['read:risk_flags'], 'active'),
    ('analyst_002', 'analyst_002@bankintel.hq', 'Analyst Two', 'analyst', 'hq_main', 
     '$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y', ARRAY[]::TEXT[], 'active'),
    ('compliance_001', 'compliance_001@bankintel.hq', 'Compliance Officer', 'compliance', 'hq_main', 
     '$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y', ARRAY[]::TEXT[], 'active'),
    ('manager_001', 'manager_001@bankintel.hq', 'HQ Branch Manager', 'manager', 'hq_main', 
     '$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y', ARRAY[]::TEXT[], 'active'),
    ('admin_001', 'admin_001@bankintel.hq', 'System Administrator', 'admin', 'hq_main', 
     '$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y', ARRAY[]::TEXT[], 'active')
ON CONFLICT (user_id) DO NOTHING;

-- Seed KPI Categories
INSERT INTO kpi_categories (category_id, name, description) VALUES
    ('profitability', 'Profitability', 'KPIs measuring return on investment, margins, and cost efficiency'),
    ('credit_risk', 'Credit Risk', 'Metrics measuring loan portfolio risk and coverage ratios'),
    ('liquidity', 'Liquidity', 'Liquidity coverage and Net Stable Funding indicators'),
    ('customer', 'Customer Growth & Retention', 'Indicators of client base growth, activity, and retention'),
    ('compliance', 'Regulatory Compliance', 'Compliance score, KYC status, and security audit metrics'),
    ('operations', 'Branch & Transaction Operations', 'Operational statistics for transaction processing')
ON CONFLICT (category_id) DO NOTHING;

-- Seed KPI Owners
INSERT INTO kpi_owners (owner_id, name, email, role) VALUES
    ('finance_lead', 'Sarah Jenkins', 'sarah.jenkins@bankintel.hq', 'finance'),
    ('risk_lead', 'Marcus Vance', 'marcus.vance@bankintel.hq', 'compliance'),
    ('treasury_lead', 'Helena Rostova', 'helena.rostova@bankintel.hq', 'manager'),
    ('compliance_officer', 'David Kross', 'david.kross@bankintel.hq', 'compliance'),
    ('ops_lead', 'Tariq Mansour', 'tariq.mansour@bankintel.hq', 'analyst'),
    ('customer_success', 'Sophia Chen', 'sophia.chen@bankintel.hq', 'manager')
ON CONFLICT (owner_id) DO NOTHING;

-- Seed KPI Definitions
INSERT INTO kpi_definitions (kpi_id, name, description, metric_type, category, data_freshness, formula, owner_id, source_tables, refresh_frequency, status, reason) VALUES
    ('total_deposits', 'Total Deposits', 'Total customer balances held across all branches', 'currency', 'profitability', 'real-time', 'SUM(balance) FROM accounts WHERE status = ''active''', 'finance_lead', ARRAY['accounts'], 'real-time', 'active', NULL),
    ('monthly_revenue', 'Monthly Fee Income', 'Estimated transaction fee revenue for the past 30 days', 'currency', 'profitability', 'real-time', 'SUM(ABS(amount)) * 0.002 FROM transactions WHERE transaction_date >= NOW() - INTERVAL ''30 days''', 'finance_lead', ARRAY['transactions'], 'real-time', 'active', NULL),
    ('avg_risk_score', 'Average Portfolio Risk Score', 'Mean risk score across all bank customers', 'ratio', 'compliance', 'real-time', 'AVG(risk_score) FROM customers', 'compliance_officer', ARRAY['customers'], 'real-time', 'active', NULL),
    ('total_risk_flags', 'Total Risk Flags', 'Count of active risk flags currently unresolved', 'count', 'compliance', 'real-time', 'COUNT(*) FROM risk_flags WHERE resolved = FALSE', 'compliance_officer', ARRAY['risk_flags'], 'real-time', 'active', NULL),
    ('roa', 'Return on Assets (ROA)', 'Measures profitability relative to total bank assets', 'percentage', 'profitability', 'monthly', 'Net_Income / Total_Assets * 100', 'finance_lead', ARRAY['financial_ledger'], 'monthly', 'unavailable', 'Required financial ledger data is not currently available.'),
    ('roe', 'Return on Equity (ROE)', 'Measures net income returned as a percentage of shareholders equity', 'percentage', 'profitability', 'monthly', 'Net_Income / Shareholder_Equity * 100', 'finance_lead', ARRAY['financial_ledger'], 'monthly', 'unavailable', 'Required financial ledger data is not currently available.'),
    ('cost_to_income', 'Cost-to-Income Ratio', 'Measures operating costs as a percentage of operating income', 'percentage', 'profitability', 'quarterly', 'Operating_Expenses / Operating_Income * 100', 'finance_lead', ARRAY['financial_ledger'], 'quarterly', 'unavailable', 'Required financial ledger data is not currently available.'),
    ('npl_ratio', 'Non-Performing Loans (NPL) Ratio', 'Ratio of non-performing loans to total outstanding loans', 'percentage', 'credit_risk', 'monthly', 'Non_Performing_Loans / Total_Outstanding_Loans * 100', 'risk_lead', ARRAY['loans'], 'monthly', 'unavailable', 'Required financial ledger data is not currently available.'),
    ('provision_coverage_ratio', 'Provision Coverage Ratio', 'Percentage of bad assets set aside for provisioning', 'percentage', 'credit_risk', 'monthly', 'Loss_Provisions / Non_Performing_Loans * 100', 'risk_lead', ARRAY['provisions', 'loans'], 'monthly', 'unavailable', 'Required financial ledger data is not currently available.'),
    ('loan_to_value', 'Loan-to-Value (LTV) Ratio', 'LTV ratio indicating lending risk based on collaterals', 'percentage', 'credit_risk', 'monthly', 'Loan_Amount / Collateral_Value * 100', 'risk_lead', ARRAY['collaterals', 'loans'], 'monthly', 'unavailable', 'Required financial ledger data is not currently available.'),
    ('loan_to_deposit_ratio', 'Loan-to-Deposit Ratio (LDR)', 'Ratio of total loans outstanding to total deposits', 'percentage', 'liquidity', 'real-time', 'Total_Loans / Total_Deposits * 100', 'treasury_lead', ARRAY['loans', 'accounts'], 'real-time', 'unavailable', 'Required financial ledger data is not currently available.'),
    ('lcr', 'Liquidity Coverage Ratio (LCR)', 'Measures high-quality liquid assets against total net cash outflows', 'percentage', 'liquidity', 'monthly', 'HQLA / Total_Net_Cash_Outflows * 100', 'treasury_lead', ARRAY['treasury_assets', 'cash_flows'], 'monthly', 'unavailable', 'Required financial ledger data is not currently available.'),
    ('nsfr', 'Net Stable Funding Ratio (NSFR)', 'Required stable funding relative to available stable funding', 'percentage', 'liquidity', 'quarterly', 'Available_Stable_Funding / Required_Stable_Funding * 100', 'treasury_lead', ARRAY['treasury_assets', 'ledger'], 'quarterly', 'unavailable', 'Required financial ledger data is not currently available.'),
    ('active_customers', 'Active Customers', 'Count of unique customers with active accounts', 'count', 'customer', 'real-time', 'COUNT(DISTINCT customer_id) FROM accounts WHERE status = ''active''', 'customer_success', ARRAY['accounts'], 'real-time', 'active', NULL),
    ('customer_growth_rate', 'Customer Growth Rate', 'MoM new customer acquisition rate', 'percentage', 'customer', 'monthly', '(Current_Month_Customers - Prev_Month_Customers) / Prev_Month_Customers * 100', 'customer_success', ARRAY['customers'], 'monthly', 'active', NULL),
    ('customer_retention_rate', 'Customer Retention Rate', 'Ratio of active customer retention based on active accounts', 'percentage', 'customer', 'monthly', 'Active_Customers / Total_Customers * 100', 'customer_success', ARRAY['accounts', 'customers'], 'monthly', 'active', NULL),
    ('kyc_compliance_rate', 'KYC Compliance Rate', 'Percentage of active customers who have verified KYC status', 'percentage', 'compliance', 'real-time', '100.0 * COUNT(kyc_verified) / COUNT(customer_id)', 'compliance_officer', ARRAY['customers'], 'real-time', 'active', NULL),
    ('compliance_score', 'Regulatory Compliance Score', 'Overall compliance score incorporating open violations and rules', 'percentage', 'compliance', 'real-time', '100.0 - (Open_Violations * 10.0)', 'compliance_officer', ARRAY['compliance_rules', 'compliance_violations'], 'real-time', 'active', NULL),
    ('transaction_volume', 'Transaction Volume (30D)', 'Total number of transactions processed over the last 30 days', 'count', 'operations', 'real-time', 'COUNT(*) FROM transactions WHERE transaction_date >= NOW() - INTERVAL ''30 days''', 'ops_lead', ARRAY['transactions'], 'real-time', 'active', NULL),
    ('avg_transaction_amount', 'Average Transaction Amount (30D)', 'Mean absolute transaction size processed over the last 30 days', 'currency', 'operations', 'real-time', 'AVG(ABS(amount)) FROM transactions WHERE transaction_date >= NOW() - INTERVAL ''30 days''', 'ops_lead', ARRAY['transactions'], 'real-time', 'active', NULL)
ON CONFLICT (kpi_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    metric_type = EXCLUDED.metric_type,
    category = EXCLUDED.category,
    data_freshness = EXCLUDED.data_freshness,
    formula = EXCLUDED.formula,
    owner_id = EXCLUDED.owner_id,
    source_tables = EXCLUDED.source_tables,
    refresh_frequency = EXCLUDED.refresh_frequency,
    status = EXCLUDED.status,
    reason = EXCLUDED.reason;

-- Seed KPI Thresholds
INSERT INTO kpi_thresholds (kpi_id, healthy_min, healthy_max, warning_min, warning_max, critical_min, critical_max, healthy_label, warning_label, critical_label) VALUES
    ('total_deposits', 5000000.00, NULL, 2000000.00, 5000000.00, NULL, 2000000.00, 'Healthy', 'Warning', 'Critical'),
    ('monthly_revenue', 10000.00, NULL, 5000.00, 10000.00, NULL, 5000.00, 'Healthy', 'Warning', 'Critical'),
    ('avg_risk_score', NULL, 0.4000, 0.4000, 0.6000, 0.6000, NULL, 'Low Risk', 'Medium Risk', 'High Risk'),
    ('total_risk_flags', NULL, 10.00, 10.00, 30.00, 30.00, NULL, 'Acceptable', 'Elevated', 'Critical'),
    ('active_customers', 150.00, NULL, 100.00, 150.00, NULL, 100.00, 'Healthy', 'Warning', 'Critical'),
    ('customer_growth_rate', 2.00, NULL, 0.00, 2.00, NULL, 0.00, 'Healthy', 'Warning', 'Critical'),
    ('customer_retention_rate', 90.00, NULL, 75.00, 90.00, NULL, 75.00, 'Healthy', 'Warning', 'Critical'),
    ('kyc_compliance_rate', 95.00, NULL, 85.00, 95.00, NULL, 85.00, 'Healthy', 'Warning', 'Critical'),
    ('compliance_score', 90.00, NULL, 75.00, 90.00, NULL, 75.00, 'Healthy', 'Warning', 'Critical'),
    ('transaction_volume', 100.00, NULL, 50.00, 100.00, NULL, 50.00, 'Healthy', 'Warning', 'Critical'),
    ('avg_transaction_amount', 100.00, NULL, 50.00, 100.00, NULL, 50.00, 'Healthy', 'Warning', 'Critical')
ON CONFLICT (kpi_id) DO UPDATE SET
    healthy_min = EXCLUDED.healthy_min,
    healthy_max = EXCLUDED.healthy_max,
    warning_min = EXCLUDED.warning_min,
    warning_max = EXCLUDED.warning_max,
    critical_min = EXCLUDED.critical_min,
    critical_max = EXCLUDED.critical_max;

