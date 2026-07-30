# Authentication User Journey

## Production Mode (`VITE_AUTH_PROVIDER=keycloak`)

```
App boot → Keycloak init (login-required)
    ↓
[no session] → auto-redirect to Keycloak login
    ↓
[login success] → redirect back to app → /auth/me
    ↓
/user found + active → dashboard
/user not found    → "Account Not Linked" (contact admin)
/user inactive     → "Access Suspended" (contact admin)
/api error         → "Service Unavailable" (retry)
    ↓
On session expiry → auto-redirect to Keycloak login
```

**No intermediate page. No login UI. No "Continue with SSO" button.**

Keycloak owns all authentication UI. The app never shows a login form, email field, password field, or SSO button in production mode.

### States

| Phase | Visual | Duration |
|-------|--------|----------|
| bootstrapping | Pulsing dots, "Connecting securely..." | <1s (inline redirect if no session) |
| loading-user | Pulsing dots, "Loading your workspace..." | ~200ms |
| authenticated | Full app | Until expiry |
| unlinked | "Account Not Linked" card, contact admin button | Blocking |
| forbidden | "Access Suspended" card, sign out button | Blocking |
| error | "Service Unavailable" card, retry button | Blocking |

## Demo Mode (`VITE_AUTH_PROVIDER=legacy`)

```
App boot → set unauthenticated → redirect to /login
    ↓
LoginPage renders with email/password form
    ↓
Submit → /auth/login → token → store in localStorage
    ↓
Redirect to /dashboard
```

Credentials: `admin/admin123`, `analyst/analyst123`

## Token Management

### Keycloak Mode
- **Storage**: None — `keycloak-js` manages tokens in memory/session
- **Refresh**: Automatic via `kc.updateToken(30)` — 60s before expiry
- **Headers**: `Authorization: Bearer <token>` on all API calls via axios interceptor
- **Logout**: `kc.logout()` redirects to Keycloak, clears app state
- **The application NEVER persists the access token itself**

### Legacy Mode
- **Storage**: `localStorage ('auth_token')`
- **Refresh**: Not supported (short-lived mock tokens)
- **Logout**: Clear localStorage, redirect to `/login`

## Auth Architecture

```
Keycloak owns: authentication, token issuance, token refresh, session management
Application owns: authorization (role-based), user profile (/auth/me), RBAC enforcement
```

The application:
- Calls `/auth/me` to resolve Keycloak identity → internal user profile
- Checks `user.role` for sidebar visibility and route access
- Never stores or manages tokens in Keycloak mode
