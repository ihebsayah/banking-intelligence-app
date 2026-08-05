-- =============================================================================
-- Migration: Seed Phase 3A.2 Customer 360 permission codes and role assignments
-- Idempotent — safe to run multiple times. Applied by api-gateway startup
-- (apply_migrations in services/api_gateway/main.py) and postgres-main init.
-- Complements init/10-phase2b-permission-seeds.sql.
--
-- Customer 360 section gate map (see customer360/service.py):
--   relationship          -> customer:read_basic
--   financial             -> customer:read_financial
--   transactions          -> customer:read_transactions
--   kyc_aml               -> customer:read_kyc
--   risk                  -> customer:read_risk
--   workbench_links       -> customer:read_compliance_history
--   PII masking off       -> customer:read_pii
-- =============================================================================

-- Seed Customer 360 permission codes
INSERT INTO permissions (permission_key, label, description, category) VALUES
    ('customer:read_basic', 'Read Customer Identity', 'Read customer identity + relationship summary (Customer 360)', 'read'),
    ('customer:read_financial', 'Read Customer Financials', 'Read customer accounts, loans and financial summary', 'read'),
    ('customer:read_transactions', 'Read Customer Transactions', 'Read customer transaction history and summary', 'read'),
    ('customer:read_kyc', 'Read Customer KYC/AML', 'Read customer KYC cases, PEP/sanctions screening and AML alerts', 'read'),
    ('customer:read_risk', 'Read Customer Risk', 'Read customer risk score and active risk flags', 'read'),
    ('customer:read_compliance_history', 'Read Customer Compliance History', 'Read workbench alerts/investigations/cases linked to the customer', 'read'),
    ('customer:read_pii', 'Read Customer PII', 'View unmasked PII in Customer 360 (national id, passport, income...)', 'read')
ON CONFLICT (permission_key) DO NOTHING;

-- Seed role_permissions for analyst (business read-only view, PII masked)
INSERT INTO role_permissions (role_id, permission_key) VALUES
    ('analyst', 'customer:read_basic'),
    ('analyst', 'customer:read_financial'),
    ('analyst', 'customer:read_transactions'),
    ('analyst', 'customer:read_kyc'),
    ('analyst', 'customer:read_risk')
ON CONFLICT DO NOTHING;

-- Seed role_permissions for manager (business read-only view, PII masked)
INSERT INTO role_permissions (role_id, permission_key) VALUES
    ('manager', 'customer:read_basic'),
    ('manager', 'customer:read_financial'),
    ('manager', 'customer:read_transactions'),
    ('manager', 'customer:read_kyc'),
    ('manager', 'customer:read_risk')
ON CONFLICT DO NOTHING;

-- Seed role_permissions for compliance (full 360 + PII + compliance history)
INSERT INTO role_permissions (role_id, permission_key) VALUES
    ('compliance', 'customer:read_basic'),
    ('compliance', 'customer:read_financial'),
    ('compliance', 'customer:read_transactions'),
    ('compliance', 'customer:read_kyc'),
    ('compliance', 'customer:read_risk'),
    ('compliance', 'customer:read_compliance_history'),
    ('compliance', 'customer:read_pii')
ON CONFLICT DO NOTHING;

-- Seed role_permissions for admin (everything)
INSERT INTO role_permissions (role_id, permission_key) VALUES
    ('admin', 'customer:read_basic'),
    ('admin', 'customer:read_financial'),
    ('admin', 'customer:read_transactions'),
    ('admin', 'customer:read_kyc'),
    ('admin', 'customer:read_risk'),
    ('admin', 'customer:read_compliance_history'),
    ('admin', 'customer:read_pii')
ON CONFLICT DO NOTHING;
