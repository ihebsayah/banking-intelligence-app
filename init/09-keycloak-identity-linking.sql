-- =============================================================================
-- Migration: Add Keycloak identity linking columns to users table
-- Idempotent — safe to run multiple times.
-- =============================================================================

-- Add identity_provider_subject for Keycloak sub claim linking
ALTER TABLE users ADD COLUMN IF NOT EXISTS identity_provider_subject VARCHAR(255) UNIQUE NULL;

-- Add identity_provider to distinguish local vs Keycloak users
ALTER TABLE users ADD COLUMN IF NOT EXISTS identity_provider VARCHAR(50) DEFAULT 'local';

-- Index for fast lookups during Keycloak token validation
CREATE INDEX IF NOT EXISTS idx_users_identity_provider_subject
    ON users(identity_provider_subject)
    WHERE identity_provider_subject IS NOT NULL;

-- Document the column purpose
COMMENT ON COLUMN users.identity_provider_subject IS 'Keycloak subject (sub claim) for linked Keycloak users. NULL for local-only users.';
COMMENT ON COLUMN users.identity_provider IS 'Authentication provider: local (default) or keycloak';
