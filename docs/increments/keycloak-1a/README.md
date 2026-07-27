# Increment 1A — Keycloak Authentication Boundary

## Overview

Introduces Keycloak as an optional authentication provider for the API Gateway without breaking the existing application.

## What Changed

### New Files
| File | Purpose |
|------|---------|
| `services/api_gateway/keycloak_auth.py` | RS256 token validation via JWKS |
| `keycloak/realm-banking-dev.json` | Reproducible development realm import |
| `init/09-keycloak-identity-linking.sql` | DB migration: `identity_provider_subject` + `identity_provider` columns |
| `tests/test_keycloak_auth.py` | 31 focused unit tests |
| `docs/adr/ADR-001-keycloak-authentication-boundary.md` | Architecture Decision Record |

### Modified Files
| File | Change |
|------|--------|
| `services/shared/config.py` | Added AUTH_PROVIDER, AUTH_COMPATIBILITY_MODE, KEYCLOAK_* settings |
| `services/shared/models.py` | Extended User model with authentication_provider, keycloak_subject, UserRole.UNMAPPED |
| `services/shared/errors.py` | Added AmbiguousRoleMappingError exception |
| `services/api_gateway/routes.py` | Dual auth mode in get_current_user, keycloak role mapping, login guard |
| `services/api_gateway/main.py` | Migration runner now processes all .sql files idempotently |
| `docker-compose.yml` | Added keycloak + postgres-keycloak services |
| `.env.example` | Added Keycloak + auth provider env vars |
| `tests/conftest.py` | Fixed jwt stub to prefer real PyJWT when installed |

### Docker Services Added
| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `keycloak` | `quay.io/keycloak/keycloak:25.0` | 8080 | Identity provider |
| `postgres-keycloak` | `postgres:16-alpine` | internal | Keycloak database |

## How to Start

```bash
# Start all services including Keycloak
docker compose up -d

# Keycloak auto-imports realm on first start via --import-realm flag
# Subsequent starts use the persisted keycloak_data volume

# Keycloak admin console
open http://localhost:8080/admin
# Credentials: admin / (see KEYCLOAK_ADMIN_PASSWORD)

# Development users (from realm import):
# kc_analyst_001 / Analyst123!     (banking_analyst)
# kc_manager_001 / Manager123!     (executive_manager)
# kc_compliance_001 / Compliance123! (compliance_officer)
# kc_admin_001 / Admin123!         (administrator)
# kc_unknown_001 / Unknown123!     (custom_unknown_role — for testing)
# kc_disabled_001 / Disabled123!   (KC disabled — for testing)
```

## Switching Auth Modes

Set in `.env` and recreate the container (`docker compose up -d --force-recreate api-gateway`; `restart` alone does NOT reload `.env`):

```bash
# Legacy mode (default) — existing HS256 JWT
AUTH_PROVIDER=legacy

# Strict Keycloak — only RS256 tokens accepted
AUTH_PROVIDER=keycloak
AUTH_COMPATIBILITY_MODE=false

# Transitional — Keycloak first, legacy fallback
AUTH_PROVIDER=keycloak
AUTH_COMPATIBILITY_MODE=true
```

## Known Limitations

1. WebSocket authentication is deferred to Increment 1B
2. POST /auth/login returns 404 in strict Keycloak mode
3. Automatic user provisioning from Keycloak is DEV_MODE only (requires `KEYCLOAK_DEV_TRANSIENT_USERS_ENABLED=true`)
4. JWKS cache TTL is time-based, not event-driven
5. Service-to-service OAuth is not implemented
6. Audit middleware runs before auth — logged user_id is always "anonymous" for API-level calls

## Rollback

Set `AUTH_PROVIDER=legacy` and recreate the API Gateway container. No database changes are destructive — new columns are nullable with safe defaults.
