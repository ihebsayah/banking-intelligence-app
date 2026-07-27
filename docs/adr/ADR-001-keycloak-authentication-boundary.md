# ADR-001: Keycloak Authentication Boundary

**Status**: Accepted
**Date**: 2026-07-26
**Deciders**: Senior Backend Engineer, Security Architect

## Context

The Banking Intelligence System currently uses custom HS256 JWT authentication (PyJWT + bcrypt) with a `users` table in PostgreSQL. This approach works but lacks enterprise-grade features: no MFA, no SSO, no centralized password policies, no token revocation, no OIDC compliance.

Keycloak is the target identity provider. Increment 1A introduces Keycloak as an **optional** authentication provider without breaking the existing application.

## Decision

### Authentication Boundary

**Keycloak owns:**
- User authentication and credential verification
- Login sessions and session management
- Access tokens (RS256-signed)
- Refresh tokens (future increment)
- Logout / session termination
- Password policies and rotation
- Multi-factor authentication (MFA)
- Realm roles and groups
- Social login / upstream IdP federation (future)

**The application database owns:**
- Banking business permissions (`role_permissions` junction table)
- Branch scope, region scope, business-unit scope
- PII access controls
- Report permissions and fine-grained business authorisation
- Domain-specific authorisation rules
- Application audit metadata

### Token Validation

Keycloak access tokens authenticate the **subject** (who is calling). The application database remains the source of **business authorisation** (what they can do) during this migration.

Validation flow:
1. Keycloak signs tokens with RS256 using its private key
2. The API Gateway validates tokens against Keycloak's JWKS endpoint
3. Issuer and audience are enforced
4. The application maps Keycloak claims to its internal user model
5. Business permissions are loaded from the database as before

### Query HMAC Signing

Query HMAC signing between the validation agent and execution agent remains **unchanged**. Keycloak authentication is orthogonal to inter-service query integrity.

### Internal Agents

Internal agents continue trusting the API Gateway and orchestrator in Increment 1A. Service-to-service OAuth is deferred.

### Legacy Compatibility

The current custom JWT (HS256) path remains temporarily available in compatibility mode via `AUTH_PROVIDER=legacy` or `AUTH_COMPATIBILITY_MODE=true`. This allows:
- Zero-downtime migration
- Gradual user rollout
- Rollback capability

### POST /auth/login Behavior

- `AUTH_PROVIDER=legacy`: POST /auth/login operates normally (issues HS256 tokens)
- `AUTH_PROVIDER=keycloak` + `AUTH_COMPATIBILITY_MODE=false`: POST /auth/login returns 404
- `AUTH_PROVIDER=keycloak` + `AUTH_COMPATIBILITY_MODE=true`: POST /auth/login operates (for transitional use)

## Alternatives Considered

### Complete one-step replacement (rejected)

Replace all auth with Keycloak in a single step. Rejected because:
- Frontend migration (keycloak-js) is a separate increment
- Requires all users to have Keycloak accounts simultaneously
- No rollback path if issues are found
- Business risk: authentication is a trust boundary; gradual migration reduces blast radius

### Keycloak Admin SDK for user validation (rejected)

Using the Keycloak Admin SDK to introspect tokens or query user state on every request. Rejected because:
- Adds network dependency for every authenticated request
- JWKS validation is sufficient and local after key fetch
- Admin SDK is intended for management operations, not runtime auth

### Remove users table entirely (deferred)

The `users` table remains the source of business permissions. User CRUD migration to Keycloak Admin API is a future increment.

## Consequences

- Dual auth mode adds complexity but is necessary for safe migration
- Role mapping must be carefully tested to avoid privilege escalation
- The `identity_provider_subject` column must be added to `users` table
- JWKS key caching requires a TTL and refresh strategy
- Legacy mode must be explicitly disabled in production

## Identity Linking Strategy

- New column: `identity_provider_subject VARCHAR UNIQUE NULL` on `users` table
- New column: `identity_provider VARCHAR(50) DEFAULT 'local'` on `users` table
- Users are linked by matching `sub` claim from Keycloak to `identity_provider_subject`
- No automatic user creation in production; development mode may allow auto-provisioning via config
- Existing users remain untouched; linking happens on first Keycloak login
