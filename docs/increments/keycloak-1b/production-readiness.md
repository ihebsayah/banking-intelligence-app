# Production Readiness — Increment 1B

## Checklist

| Item | Status | Notes |
|------|--------|-------|
| TypeScript compiles | ✅ | Zero errors |
| ESLint passes | ✅ | Only pre-existing warnings/errors |
| Production build succeeds | ✅ | `tsc && vite build` |
| Unit tests pass | ✅ | 15/15 |
| No token persistence in localStorage (Keycloak mode) | ✅ | Sentinel value `'keycloak'` stored; `partialize` strips it |
| No token persistence in sessionStorage/IndexedDB | ✅ | Not used anywhere |
| PKCE S256 enabled | ✅ | `pkceMethod: 'S256'` in `initKeycloak()` |
| check-sso (no redirect loop) | ✅ | `onLoad: 'check-sso'` |
| checkLoginIframe disabled | ✅ | Prevents cross-origin issues |
| Refresh deduplication | ✅ | `inflightRefresh` ref in AuthProvider, `refreshPromise` in client interceptor |
| /auth/me → backend role/permissions | ✅ | `hasRole()` uses `applicationUser.role` from `/auth/me`, never Keycloak realm roles |
| Route guards hide content during auth | ✅ | Bootstrapping/loading-user show spinner, not children |
| Logout clears state + Keycloak session | ✅ | Clears timers, store, state, then `kc.logout()` |
| Rollback documented | ✅ | Two paths: full rollback (A) and frontend-only (B) |
| Environment validation | ✅ | `requireKeycloakEnv()` throws on missing vars |
| No client secret in frontend | ✅ | Public client, no secret configured |
| Typed env access | ✅ | `ImportMetaEnv` interface in `vite-env.d.ts` |

## Known Limitations

| Limitation | Risk | Mitigation |
|-----------|------|-----------|
| WebSocket `/ws/monitoring` unauthenticated | Medium if exposed in production | Documented: network isolation or backend auth recommended for production |
| `queryStore` retains legacy auth fields (`authToken`, `userRole`, `userId`) | Low | Isolated: only used by `HeaderLegacy`; Keycloak mode uses `isKeycloak` prop to avoid merging |
| `keycloak-js` stores tokens in its own localStorage keys | Low | This is keycloak-js internal storage, not `auth_token`. Acceptable — tokens expire and are rotated. |
| No E2E Cypress tests with Keycloak test realm | Medium | Recommended for next increment |
| No token expiry warning UX | Low | User sees redirect to login on expiry. Proactive warning could be added later. |

## Pre-existing Issues (Not Introduced by Increment 1B)

- 2 ESLint errors in `Assistant.tsx` (`no-useless-escape`)
- 90 ESLint warnings (`@typescript-eslint/no-explicit-any`, unused vars, react-hooks deps)
- Chunk size warning (1,063 kB > 500 kB limit)
- `socket.io-client` installed but unused (plain WebSocket used instead)

## Production Deployment Requirements

1. Keycloak realm `banking-intelligence` must exist with client `banking-portal-web` configured as public, PKCE S256
2. Backend `AUTH_PROVIDER=keycloak`, `AUTH_COMPATIBILITY_MODE=true` during migration period
3. Backend `KEYCLOAK_INTERNAL_URL` and `KEYCLOAK_REALM` must match frontend `VITE_KEYCLOAK_URL` and `VITE_KEYCLOAK_REALM`
4. Frontend `.env` must set `VITE_KEYCLOAK_URL` to the publicly reachable Keycloak URL (not Docker internal URL)
5. Valid redirect URIs in Keycloak client must include production frontend domain

## Verdict

**Production ready** for development/staging. E2E testing with a real Keycloak realm recommended before production deployment.
