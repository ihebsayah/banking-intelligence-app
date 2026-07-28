# Rollback Procedure

## Rollback Path A — Full Rollback (Recommended)

Revert both frontend and backend to legacy mode.

### Steps

1. Frontend — edit `Frontend/.env`:
   ```
   VITE_AUTH_PROVIDER=legacy
   ```

2. Backend — edit `services/.env`:
   ```
   AUTH_PROVIDER=legacy
   AUTH_COMPATIBILITY_MODE=false
   ```

3. Restart both:
   ```bash
   docker compose restart api-gateway api-processor
   cd Frontend && npm run dev
   ```

4. Verify: legacy login form appears, `analyst_001` / `password` works.

---

## Rollback Path B — Frontend-Only Rollback

Revert frontend to legacy while backend stays in Keycloak mode with compatibility.

### Steps

1. Frontend — edit `Frontend/.env`:
   ```
   VITE_AUTH_PROVIDER=legacy
   ```

2. Backend — ensure compatibility mode is ON:
   ```
   AUTH_PROVIDER=keycloak
   AUTH_COMPATIBILITY_MODE=true
   ```

3. Restart frontend:
   ```bash
   cd Frontend && npm run dev
   ```

### Limitation

Backend still expects Keycloak RS256 tokens for `/auth/me` and protected endpoints. Legacy frontend sends HS256 tokens. This works **only if** `AUTH_COMPATIBILITY_MODE=true` (backend accepts both token types). If compatibility mode is off, legacy frontend requests will be rejected.

---

## What Changes

| Aspect | Keycloak mode | Legacy mode |
|--------|--------------|-------------|
| Login | Keycloak SSO redirect | Username/password form |
| Token source | keycloak-js in-memory | localStorage |
| API auth header | Keycloak RS256 token | Legacy HS256 token |
| /auth/me | Called after Keycloak auth | Not called on login |

## No Database Rollback Needed

User records, bank data, and role mappings are unchanged. Only the authentication provider changes.

## Verify Rollback

1. Open `http://localhost:3000`
2. Should see legacy login form (not Keycloak redirect)
3. Login with `analyst_001` / `password`
4. Dashboard loads normally
5. Confirm `localStorage.getItem('auth_token')` is set (legacy mode stores tokens there)
