# Production Readiness Report — Increment 1A

**Date**: 2026-07-26
**Status**: GO for Increment 1B

## Implemented Architecture

```
Browser → Keycloak (RS256 OIDC) → API Gateway → Application DB
                       ↓                    ↓
                   JWKS certs         identity_provider_subject lookup
                       ↓                    ↓
                  Token validated     User resolved + permissions loaded
```

- Dual auth mode: `legacy` (HS256), `keycloak` (RS256), `keycloak` + `compat` (transitional)
- Role mapping: single function `routes.py:_map_keycloak_roles_to_application_role()`
- Identity linking: `identity_provider_subject` column on `users` table
- JWKS: per-kid indexed cache, configurable TTL, stale fallback on fetch failure
- DEV_MODE transient users: opt-in via `KEYCLOAK_DEV_TRANSIENT_USERS_ENABLED=true`

## Security Improvements

1. RS256 token validation with local JWKS — no Keycloak round-trip per request
2. Per-kid key index for fast rotation handling
3. Unknown kid triggers exactly one JWKS refresh
4. Stale cache fallback on JWKS fetch failure
5. `alg=none` explicitly rejected
6. HS256 rejected in Keycloak mode
7. Issuer and audience enforced
8. Conflicting role mapping → 403 AMBIGUOUS_ROLE_MAPPING
9. DEV_MODE transient users require explicit opt-in flag
10. Compatibility mode logs structured warnings
11. Suspended/inactive users rejected after token validation

## Remaining Limitations

| Limitation | Severity | Mitigation |
|-----------|----------|------------|
| No token revocation (KC tokens valid until expiry) | Medium | Short TTL (300s), refresh token rotation in Increment 1B |
| Audit middleware captures "anonymous" user_id | Low | Architecture change needed — separate auth middleware |
| WebSocket endpoints not authenticated | Medium | Increment 1B |
| No automatic user provisioning | Low | Manual linking via SQL, acceptable for banking domain |
| JWKS cache time-based only (no event-driven invalidation) | Low | Unknown kid refresh covers rotation; TTL covers revocation |
| `start-dev` mode in Keycloak | Low | Must change for production deployment |

## Known Risks

1. **Compatibility mode**: Legacy tokens accepted alongside Keycloak. Disable in production.
2. **JWKS stale cache**: Brief window where revoked keys could be accepted. TTL mitigates.
3. **Clock skew**: 30s default. Verify clocks are synced in production.
4. **Realm re-import**: Changes KC user `sub` values. DB links become stale. Must re-link after re-import.
5. **KC Admin API users**: Cannot authenticate with password grant. Must use realm import for user provisioning.

## Rollback Procedure

1. Set `AUTH_PROVIDER=legacy` in `.env`
2. Recreate API Gateway: `docker compose up -d --force-recreate api-gateway`
3. All existing HS256 tokens continue working
4. No database rollback needed (new columns are nullable)
5. No Keycloak changes needed

Estimated rollback time: < 30 seconds.

## Production Checklist

- [ ] Set `AUTH_PROVIDER=keycloak`
- [ ] Set `AUTH_COMPATIBILITY_MODE=false`
- [ ] Generate strong `KEYCLOAK_ADMIN_PASSWORD` (not `CHANGE_ME_KEYCLOAK_ADMIN`)
- [ ] Generate strong `KEYCLOAK_DB_PASSWORD` (not `CHANGE_ME_KEYCLOAK_DB`)
- [ ] Change `JWT_SECRET_KEY` from default value
- [ ] Change `QUERY_SIGNING_KEY` from default value
- [ ] Enable HTTPS for Keycloak (`sslRequired: "external"` in realm)
- [ ] Disable `start-dev` mode (use `start --import-realm` or `start`)
- [ ] Configure proper redirect URIs for production domain
- [ ] Link all application users to their Keycloak identities
- [ ] Verify JWKS cache TTL is appropriate for your environment
- [ ] Monitor Keycloak health checks (`/health/ready`)
- [ ] Set up Keycloak replication for high availability
- [ ] Configure rate limiting on token endpoint
- [ ] Review and adjust `accessTokenLifespan` (currently 300s) for production needs

## GO / NO-GO for Increment 1B

**GO**

All security properties validated end-to-end. Documentation updated to reflect actual implementation. Rollback is fast and non-destructive. The system is ready for frontend keycloak-js integration in Increment 1B.
