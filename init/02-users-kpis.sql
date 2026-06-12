-- =============================================================================
-- Users & KPI Definitions Schema Extensions
-- =============================================================================

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(100) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) NOT NULL,
    bank_id VARCHAR(50) DEFAULT 'hq_main',
    password VARCHAR(255) NOT NULL,
    permissions TEXT[] DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- KPI Definitions Table
CREATE TABLE IF NOT EXISTS kpi_definitions (
    kpi_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    metric_type VARCHAR(20) NOT NULL, -- currency, percentage, count, ratio
    category VARCHAR(50),             -- profitability, operational, risk, growth
    data_freshness VARCHAR(20) DEFAULT 'real-time',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kpis_category ON kpi_definitions(category);

-- =============================================================================
-- Seed Data
-- =============================================================================

-- Seed Users
INSERT INTO users (user_id, email, name, role, bank_id, password, permissions, status) VALUES
    ('analyst_001', 'analyst_001@bankintel.hq', 'Analyst One', 'analyst', 'hq_main', 'password', 
     ARRAY['read:customers', 'read:accounts', 'read:transactions', 'read:risk_flags'], 'active'),
    ('analyst_002', 'analyst_002@bankintel.hq', 'Analyst Two', 'analyst', 'hq_main', 'password', 
     ARRAY['read:customers', 'read:accounts', 'read:transactions'], 'active'),
    ('compliance_001', 'compliance_001@bankintel.hq', 'Compliance Officer', 'compliance', 'hq_main', 'password', 
     ARRAY['read:customers', 'read:accounts', 'read:transactions', 'read:risk_flags', 'read:audit_logs', 'read:pii'], 'active'),
    ('manager_001', 'manager_001@bankintel.hq', 'HQ Branch Manager', 'manager', 'hq_main', 'password', 
     ARRAY['read:customers', 'read:accounts', 'read:transactions', 'read:branch_data', 'read:risk_summary'], 'active'),
    ('admin_001', 'admin_001@bankintel.hq', 'System Administrator', 'admin', 'hq_main', 'password', 
     ARRAY['read:customers', 'read:accounts', 'read:transactions', 'read:risk_flags', 'read:audit_logs', 'read:pii', 'admin:users', 'admin:roles'], 'active')
ON CONFLICT (user_id) DO NOTHING;

-- Seed KPI Definitions
INSERT INTO kpi_definitions (kpi_id, name, description, metric_type, category, data_freshness) VALUES
    ('total_deposits', 'Total Deposits', 'Total customer balances held across all branches', 'currency', 'profitability', 'real-time'),
    ('monthly_revenue', 'Monthly Fee Income', 'Estimated transaction fee revenue for the past 30 days', 'currency', 'profitability', 'real-time'),
    ('active_customers', 'Active Customers', 'Count of unique customers with active accounts', 'count', 'operational', 'real-time'),
    ('avg_risk_score', 'Average Portfolio Risk Score', 'Mean risk score across all bank customers', 'ratio', 'risk', 'real-time'),
    ('kyc_compliance_rate', 'KYC Compliance Rate', 'Percentage of active customers who have verified KYC status', 'percentage', 'risk', 'real-time'),
    ('total_risk_flags', 'Total Risk Flags', 'Count of active risk flags currently unresolved', 'count', 'risk', 'real-time')
ON CONFLICT (kpi_id) DO NOTHING;
