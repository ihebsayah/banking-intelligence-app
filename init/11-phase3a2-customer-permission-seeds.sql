-- =============================================================================
-- Migration: Seed + forward-repair Phase 3A.2 Customer 360 permission codes and
-- role assignments (Phase 3A.2a authorization/privacy hardening).
-- Idempotent — safe to run multiple times. Applied by api-gateway startup
-- (apply_migrations in services/api_gateway/main.py) and postgres-main init.
-- Complements init/10-phase2b-permission-seeds.sql.
--
-- Policy (Phase 3A.2a approved access matrix):
--   Analyst     operational financial/risk view, PII masked, status-level KYC
--   Compliance  full detail within org scope; PII only with customer:read_pii
--   Admin       metadata-only (customer:read_operational_metadata)
--   Manager     no Customer 360 detail (legacy/deprecated role)
--
-- Customer 360 section gate map (see customer360/service.py):
--   relationship          -> customer:read_basic
--   financial             -> customer:read_financial
--   transactions          -> customer:read_transactions
--   kyc_aml               -> customer:read_kyc
--   risk                  -> customer:read_risk
--   workbench_links       -> customer:read_compliance_history
--                            OR customer:read_operational_metadata (metadata only)
--   admin_metadata        -> customer:read_operational_metadata
--   PII masking off       -> customer:read_pii
--
-- The role_permissions DELETEs below are the forward repair: they strip the
-- over-broad grants (admin detail + PII, manager detail) seeded in 3A.2. No
-- permission *definitions* are deleted — historical audit rows reference them.
-- =============================================================================

-- Seed Customer 360 permission codes (definitions are never removed).
INSERT INTO permissions (permission_key, label, description, category) VALUES
    ('customer:read', 'Read Customer 360', 'Aggregate gate for the Customer 360 detail surface', 'read'),
    ('customer:read_basic', 'Read Customer Identity', 'Read customer identity + relationship summary (Customer 360)', 'read'),
    ('customer:read_financial', 'Read Customer Financials', 'Read customer accounts, loans and financial summary', 'read'),
    ('customer:read_transactions', 'Read Customer Transactions', 'Read customer transaction history and summary', 'read'),
    ('customer:read_kyc', 'Read Customer KYC/AML', 'Read customer KYC status, PEP/sanctions screening and AML alert metadata', 'read'),
    ('customer:read_risk', 'Read Customer Risk', 'Read customer risk score and active risk flags', 'read'),
    ('customer:read_compliance_history', 'Read Customer Compliance History', 'Read workbench alerts/investigations/cases linked to the customer', 'read'),
    ('customer:read_operational_metadata', 'Read Customer Operational Metadata', 'Metadata-only Customer 360 view: counts, risk classification, linked entity IDs/status (no financials, no PII, no KYC content)', 'read'),
    ('customer:read_pii', 'Read Customer PII', 'View unmasked PII in Customer 360 (national id, passport, income...)', 'read')
ON CONFLICT (permission_key) DO NOTHING;

-- ── Analyst ───────────────────────────────────────────────────────────────────
-- Operational financial/risk view. PII is masked by the service (no read_pii).
-- read_kyc is kept only because the service returns status-level KYC data for
-- users without read_pii (internal case ids suppressed, screening names masked).
DELETE FROM role_permissions
 WHERE role_id = 'analyst'
   AND permission_key LIKE 'customer:%'
   AND permission_key NOT IN (
        'customer:read', 'customer:read_basic', 'customer:read_financial',
        'customer:read_transactions', 'customer:read_kyc', 'customer:read_risk'
   );
INSERT INTO role_permissions (role_id, permission_key) VALUES
    ('analyst', 'customer:read'),
    ('analyst', 'customer:read_basic'),
    ('analyst', 'customer:read_financial'),
    ('analyst', 'customer:read_transactions'),
    ('analyst', 'customer:read_kyc'),
    ('analyst', 'customer:read_risk')
ON CONFLICT DO NOTHING;

-- ── Compliance ────────────────────────────────────────────────────────────────
-- Full detail + PII + compliance history within org scope.
DELETE FROM role_permissions
 WHERE role_id = 'compliance'
   AND permission_key LIKE 'customer:%'
   AND permission_key NOT IN (
        'customer:read', 'customer:read_basic', 'customer:read_financial',
        'customer:read_transactions', 'customer:read_kyc', 'customer:read_risk',
        'customer:read_compliance_history', 'customer:read_pii'
   );
INSERT INTO role_permissions (role_id, permission_key) VALUES
    ('compliance', 'customer:read'),
    ('compliance', 'customer:read_basic'),
    ('compliance', 'customer:read_financial'),
    ('compliance', 'customer:read_transactions'),
    ('compliance', 'customer:read_kyc'),
    ('compliance', 'customer:read_risk'),
    ('compliance', 'customer:read_compliance_history'),
    ('compliance', 'customer:read_pii')
ON CONFLICT DO NOTHING;

-- ── Admin ─────────────────────────────────────────────────────────────────────
-- Metadata-only: identity + relationship + operational metadata + linked entity
-- metadata. No financials, transactions, KYC content, risk detail, or PII.
DELETE FROM role_permissions
 WHERE role_id = 'admin'
   AND permission_key LIKE 'customer:%'
   AND permission_key NOT IN (
        'customer:read', 'customer:read_basic', 'customer:read_operational_metadata'
   );
INSERT INTO role_permissions (role_id, permission_key) VALUES
    ('admin', 'customer:read'),
    ('admin', 'customer:read_basic'),
    ('admin', 'customer:read_operational_metadata')
ON CONFLICT DO NOTHING;

-- ── Manager / legacy ──────────────────────────────────────────────────────────
-- Denied all Customer 360 detail. Denial is permission-based, so it holds even
-- if a scope row is later assigned to the role/user.
DELETE FROM role_permissions
 WHERE role_id = 'manager'
   AND permission_key LIKE 'customer:%';
