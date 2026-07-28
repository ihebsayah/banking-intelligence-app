# Frontend Auth Architecture

## Trust Model

```
Keycloak authenticates identity
        ↓
Frontend obtains and refreshes Keycloak tokens
        ↓
API Gateway validates the token (RS256 JWKS)
        ↓
Application resolves the linked user (database)
        ↓
Application database role and permissions authorize access
```

The frontend never trusts Keycloak realm roles for business authorization. All role/permission checks use data from `/auth/me`.

## Authentication States

| Phase | Meaning |
|-------|---------|
| `bootstrapping` | Keycloak SDK initializing |
| `unauthenticated` | No valid Keycloak session |
| `loading-user` | Keycloak authenticated, fetching /auth/me |
| `authenticated` | Linked application user loaded |
| `unlinked` | Keycloak identity has no linked app user |
| `forbidden` | User is inactive/suspended or lacks access |
| `expired` | Token refresh failed |
| `error` | Fatal configuration or network error |

## Token Flow

1. `keycloak-js` handles Authorization Code Flow + PKCE
2. On app boot, `initKeycloak()` checks for existing SSO session (`check-sso`)
3. If authenticated, `updateToken(30)` ensures a fresh token before API calls
4. Axios interceptor calls `updateToken(30)` before every request
5. On 401, interceptor retries once after successful refresh
6. Tokens live in `keycloak-js` internal storage (NOT localStorage)

## Legacy Mode

When `VITE_AUTH_PROVIDER=legacy`, the original login form and flow remain unchanged. No Keycloak code is loaded.
