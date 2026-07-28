# E2E Validation — Increment 1B

## Browser Validation Scenarios

> **Note**: These scenarios require a running Keycloak instance with the `banking-intelligence` realm and `banking-portal-web` client configured. Full automated E2E validation is deferred to the next increment (Cypress + Keycloak test realm).

### 1. Protected page redirects to Keycloak

**Setup**: `VITE_AUTH_PROVIDER=keycloak`, Keycloak running at `localhost:8080`

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open `http://localhost:3000/dashboard` | Redirects to Keycloak login page |
| 2 | Keycloak login page shows | URL: `localhost:8080/realms/banking-intelligence/protocol/openid-connect/auth?...` |
| 3 | PKCE params present | `code_challenge_method=S256` in URL |

### 2. Analyst login via Keycloak

| Step | Action | Expected |
|------|--------|----------|
| 1 | Enter analyst credentials in Keycloak | Keycloak authenticates |
| 2 | Redirect back to `http://localhost:3000` | Frontend calls `/auth/me` |
| 3 | `/auth/me` returns analyst profile | Dashboard loads with analyst nav items |
| 4 | Sidebar shows analyst role | Role badge: "analyst" |

### 3. Admin login via Keycloak

| Step | Action | Expected |
|------|--------|----------|
| 1 | Login with admin credentials | Keycloak authenticates |
| 2 | Redirect back, `/auth/me` called | Admin profile returned |
| 3 | Dashboard loads | Admin sees all nav items including "Admin Portal" |
| 4 | `/dev/*` routes accessible | Developer Monitor visible in sidebar |

### 4. Compliance login via Keycloak

| Step | Action | Expected |
|------|--------|----------|
| 1 | Login with compliance credentials | Keycloak authenticates |
| 2 | `/auth/me` returns compliance role | Compliance nav item visible |
| 3 | `/reports` route | Redirected to `/unauthorized` (compliance can't access reports) |

### 5. Unlinked user

| Step | Action | Expected |
|------|--------|----------|
| 1 | Login with Keycloak identity not linked to any app user | `/auth/me` returns 401 USER_NOT_FOUND |
| 2 | Frontend shows unlinked screen | "Account Not Linked — Contact an administrator" message |
| 3 | No dashboard content visible | Correct — user has no app role |

### 6. Logout

| Step | Action | Expected |
|------|--------|----------|
| 1 | Click Logout in sidebar | Frontend clears state |
| 2 | Keycloak session terminated | `kc.logout()` called with redirect |
| 3 | Redirect to login page | Keycloak login page shown |
| 4 | Navigate to `/dashboard` | Redirects back to Keycloak (no session) |

### 7. Browser refresh (authenticated session)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Login as analyst | Dashboard loads |
| 2 | Refresh browser (F5) | `initKeycloak()` with `check-sso` |
| 3 | Keycloak session still valid | `/auth/me` called, dashboard loads without re-login |

### 8. Expired token

| Step | Action | Expected |
|------|--------|----------|
| 1 | Login as analyst | Dashboard loads |
| 2 | Wait for token expiry (or manually expire) | `onTokenExpired` fires |
| 3 | Frontend attempts `updateToken(30)` | If refresh succeeds: session continues |
| 4 | If refresh fails | Redirect to login with "session expired" message |

### 9. Keycloak unavailable

| Step | Action | Expected |
|------|--------|----------|
| 1 | Stop Keycloak container | Keycloak unreachable |
| 2 | Open `http://localhost:3000` | `initKeycloak()` fails |
| 3 | Frontend shows error state | "Failed to initialize authentication. Check your configuration." |

### 10. API unavailable

| Step | Action | Expected |
|------|--------|----------|
| 1 | Login via Keycloak | Keycloak auth succeeds |
| 2 | API gateway down | `/auth/me` request fails |
| 3 | Frontend shows error state | "Unable to load your profile. Please try again later." |

### 11. Legacy mode unaffected

| Step | Action | Expected |
|------|--------|----------|
| 1 | Set `VITE_AUTH_PROVIDER=legacy` | Restart dev server |
| 2 | Open `http://localhost:3000` | Legacy login form (no Keycloak redirect) |
| 3 | Login with `analyst_001` / `password` | Dashboard loads, localStorage has `auth_token` |
| 4 | Token attached to API requests | `Authorization: Bearer <legacy-token>` |

## Validation Status

| Scenario | Automated | Manual | Status |
|----------|-----------|--------|--------|
| 1. Redirect to Keycloak | No | Not performed | DEFERRED |
| 2. Analyst login | No | Not performed | DEFERRED |
| 3. Admin login | No | Not performed | DEFERRED |
| 4. Compliance login | No | Not performed | DEFERRED |
| 5. Unlinked user | Unit test only | Not performed | DEFERRED |
| 6. Logout | Unit test only | Not performed | DEFERRED |
| 7. Browser refresh | No | Not performed | DEFERRED |
| 8. Expired token | Unit test only | Not performed | DEFERRED |
| 9. Keycloak unavailable | No | Not performed | DEFERRED |
| 10. API unavailable | Unit test only | Not performed | DEFERRED |
| 11. Legacy mode | No | Not performed | DEFERRED |

**Reason for deferral**: Requires running Keycloak instance with configured test realm and test users. Recommend adding Cypress E2E tests with Keycloak test realm in next increment.
