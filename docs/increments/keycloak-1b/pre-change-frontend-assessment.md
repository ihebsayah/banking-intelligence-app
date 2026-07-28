# Pre-Change Frontend Assessment — Increment 1B

## Technology Stack

| Item | Value |
|------|-------|
| Package manager | npm |
| React | 18.3.1 |
| TypeScript | 5.2.2 |
| Build tool | Vite 5.3.1 |
| Routing | react-router-dom 6.24.0 |
| State management | Zustand 4.5.2 |
| Data fetching | @tanstack/react-query 5.45.0 |
| HTTP client | Axios 1.7.2 |
| Styling | Tailwind CSS 3.4.4 |
| Lint | ESLint 8.57 + @typescript-eslint 7.13 |
| Test framework | None installed |
| WebSocket | Native WebSocket (socket.io-client installed but unused) |

## Source Structure

```
src/
  api/           — 14 API modules (client.ts is the central Axios instance)
  components/    — auth/, Layout/, dashboard/, etc.
  hooks/         — useWebSocket.ts, useQuery.ts, useAgentMonitoring.ts
  pages/         — 17 page components
  stores/        — 8 Zustand stores (authStore, queryStore, uiStore, configStore, etc.)
  types/         — TypeScript interfaces
  utils/         — formatters.ts
```

## Current Auth Flow

1. `LoginPage.tsx` collects email/password, calls `authApi.login()` (POST `/auth/login` form-urlencoded)
2. Backend returns `{ access_token, user_id, user_role, expires_in }`
3. `authStore.setUser()` stores user + token, persists to localStorage as `banking-auth`
4. `apiClient` request interceptor reads `auth_token` from localStorage, attaches `Authorization: Bearer`
5. `apiClient` response interceptor catches 401 → clears localStorage → redirects to `/login`
6. `ProtectedRoute` checks `authStore.isAuthenticated`, redirects to `/login` if false
7. `BankingSidebar` reads `user` from authStore for role-based nav filtering
8. `queryStore` also stores `authToken`, `userRole`, `userId` in localStorage (separate auth state for dev header)

## Key Files

- `src/api/client.ts` — Central Axios instance with token interceptor
- `src/api/auth.ts` — Legacy login/logout/me API calls
- `src/stores/authStore.ts` — Zustand store with persist middleware (localStorage `banking-auth`)
- `src/stores/queryStore.ts` — Separate auth state for dev header
- `src/types/auth.ts` — User, AuthState, LoginRequest, LoginResponse types
- `src/components/auth/LoginPage.tsx` — Legacy login form
- `src/components/auth/ProtectedRoute.tsx` — Route guard
- `src/components/Layout/BankingSidebar.tsx` — Nav with role filtering + logout
- `src/components/Layout/BankingHeader.tsx` — Header with user chip
- `src/pages/ProfilePage.tsx` — Fetches `/users/me`

## Backend Contracts

- `POST /auth/login` — form-urlencoded, returns `{ access_token, user_id, user_role, expires_in }`
- `GET /auth/me` — returns `{ user_id, email, name, role, bank_id, created_at, last_login, status, must_change_password }`
- `GET /users/me` — same as `/auth/me` (alias)
- Backend supports dual auth: `AUTH_PROVIDER=legacy|keycloak`
- Keycloak mode validates RS256 via JWKS, resolves user via `identity_provider_subject`
- Backend KEYCLOAK_ROLE_MAP maps realm roles → application roles
- Expected audience: `banking-portal-api`
- Expected issuer: `{KEYCLOAK_INTERNAL_URL}/realms/{KEYCLOAK_REALM}`

## WebSocket Usage

- `useWebSocket.ts` connects to `/ws/monitoring` — unauthenticated
- No auth token passed in WebSocket connection
- Impact: None for this increment (unauthenticated monitoring WS)

## localStorage Keys

- `auth_token` — JWT (set by authStore + apiClient)
- `banking-auth` — Zustand persisted state (user, token, isAuthenticated)
- `banking-dashboard-config` — Config store
- `banking-ui-prefs` — UI preferences
- `user_role`, `user_id` — queryStore auth state
- `banking_remember` — Remember-me email

## Findings

1. **No existing frontend .env** — Only backend `.env` files exist
2. **No test framework** — No vitest, jest, or test files
3. **No existing Keycloak frontend config** — The `banking-portal-web` client ID is referenced in `.env.example` but no frontend code uses it
4. **Dual auth state** — `authStore` and `queryStore` both manage auth tokens independently
5. **Token in localStorage** — Current implementation persists tokens in localStorage (security concern for Keycloak mode)
6. **WebSocket is unauthenticated** — No impact from auth changes
7. **Dev header login** — `Header.tsx` has its own inline login modal using `queryStore.setAuth()`
