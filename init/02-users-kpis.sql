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

-- 6. KPI Definitions Table
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
    -- Analyst Permissions
    ('analyst', 'read:customers'),
    ('analyst', 'read:accounts'),
    ('analyst', 'read:transactions'),
    -- Manager Permissions
    ('manager', 'read:customers'),
    ('manager', 'read:accounts'),
    ('manager', 'read:transactions'),
    ('manager', 'read:branch_data'),
    ('manager', 'read:risk_summary'),
    -- Compliance Permissions
    ('compliance', 'read:customers'),
    ('compliance', 'read:accounts'),
    ('compliance', 'read:transactions'),
    ('compliance', 'read:risk_flags'),
    ('compliance', 'read:audit_logs'),
    ('compliance', 'read:pii'),
    -- Admin Permissions
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

-- Seed Users (Bcrypt hash of 'password' is used for all seed users)
-- Hash: $2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y
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

-- Seed KPI Definitions
INSERT INTO kpi_definitions (kpi_id, name, description, metric_type, category, data_freshness) VALUES
    ('total_deposits', 'Total Deposits', 'Total customer balances held across all branches', 'currency', 'profitability', 'real-time'),
    ('monthly_revenue', 'Monthly Fee Income', 'Estimated transaction fee revenue for the past 30 days', 'currency', 'profitability', 'real-time'),
    ('active_customers', 'Active Customers', 'Count of unique customers with active accounts', 'count', 'operational', 'real-time'),
    ('avg_risk_score', 'Average Portfolio Risk Score', 'Mean risk score across all bank customers', 'ratio', 'risk', 'real-time'),
    ('kyc_compliance_rate', 'KYC Compliance Rate', 'Percentage of active customers who have verified KYC status', 'percentage', 'risk', 'real-time'),
    ('total_risk_flags', 'Total Risk Flags', 'Count of active risk flags currently unresolved', 'count', 'risk', 'real-time')
ON CONFLICT (kpi_id) DO NOTHING;
