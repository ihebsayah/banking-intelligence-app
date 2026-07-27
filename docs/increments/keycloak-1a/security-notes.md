# Security Notes — Increment 1A

## Token Validation

- RS256 only for Keycloak tokens
- `alg=none` explicitly rejected
- HS256 tokens rejected in strict Keycloak mode
- Issuer and audience enforced
- JWKS keys cached with configurable TTL (default 600s)
- Per-`kid` key index for fast lookup during rotation
- Unknown `kid` triggers one JWKS refresh, then fails
- JWKS fetch failure uses stale cache if available
- Clock skew configurable (default 30s)

## Auth Modes

| Mode | Legacy Tokens | Keycloak Tokens | Login Endpoint |
|------|:------------:|:--------------:|:--------------:|
| `AUTH_PROVIDER=legacy` | Accepted | N/A | Active |
| `AUTH_PROVIDER=keycloak` | Rejected | Accepted | 404 |
| `AUTH_PROVIDER=keycloak` + `COMPAT=true` | Fallback | Primary | Active |

## Compatibility Mode Logging

When `AUTH_COMPATIBILITY_MODE=true`, every accepted legacy token produces a structured warning:
- Event: `COMPAT_MODE_LEGACY_TOKEN_ACCEPTED`
- Fields: `authentication_provider`, `user_id`, `migration_mode`, `request_id`
- No token content is ever logged

## Role Mapping Security

- Unknown Keycloak roles ignored (user gets DB role, or `"unmapped"` in DEV_MODE transient)
- Conflicting roles (multiple distinct app roles) → 403 `AMBIGUOUS_ROLE_MAPPING`
- Priority system only applies when multiple KC role names map to the same app role

## DEV_MODE Safety

`DEV_MODE=true` alone does NOT enable transient user creation. Both flags required:
- `DEV_MODE=true`
- `KEYCLOAK_DEV_TRANSIENT_USERS_ENABLED=true`

This prevents accidental exposure of unlinked KC users in development environments.

## User Status

- Suspended/inactive application users are rejected even with valid Keycloak tokens
- This check happens after token validation, using the database status field

## What Is NOT Changed

- Query HMAC signing between validation and execution agents
- Internal agent-to-agent communication
- Business permission logic (still database-backed)
- Frontend authentication flow (Increment 1B)

## Known Risks

1. **Compatibility mode**: Legacy tokens accepted alongside Keycloak tokens. Disable in production.
2. **JWKS cache**: Stale keys could briefly accept revoked tokens. TTL mitigates this.
3. **Clock skew**: 30s default. Adjust if Keycloak and API Gateway clocks drift.
4. **No token revocation**: Keycloak tokens are valid until expiry. No server-side revocation in Increment 1A.
5. **WebSocket endpoints**: Not authenticated in this increment.
6. **Audit gap**: Audit middleware runs before route-level auth, so `user_id` is always "anonymous" in API-level audit entries. Requires architecture change to fix.

## Production Checklist

- [ ] Set `AUTH_PROVIDER=keycloak`
- [ ] Set `AUTH_COMPATIBILITY_MODE=false`
- [ ] Generate strong `KEYCLOAK_ADMIN_PASSWORD`
- [ ] Generate strong `KEYCLOAK_DB_PASSWORD`
- [ ] Enable HTTPS for Keycloak (change `sslRequired` in realm)
- [ ] Disable `start-dev` mode in Keycloak
- [ ] Configure proper redirect URIs for production
- [ ] Link all application users to their Keycloak identities
- [ ] Verify JWKS cache TTL is appropriate
- [ ] Monitor Keycloak health checks
