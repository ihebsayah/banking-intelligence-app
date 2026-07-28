# Increment 1B — Frontend Keycloak Integration

## Overview

Integrates the React frontend with Keycloak for SSO authentication using Authorization Code Flow with PKCE.

## Quick Start

### 1. Configure environment

```bash
cd Frontend
cp .env.example .env
```

Edit `.env`:
```
VITE_AUTH_PROVIDER=keycloak
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=banking-intelligence
VITE_KEYCLOAK_CLIENT_ID=banking-portal-web
```

### 2. Start the stack

```bash
# From project root
docker compose up -d
cd Frontend && npm run dev
```

### 3. Open browser

Navigate to `http://localhost:3000`. You'll be redirected to Keycloak for login.

## Architecture

```
Browser → Keycloak (PKCE login) → Frontend gets token → API validates via JWKS → /auth/me resolves app user
```

- **Keycloak authenticates identity** (RS256, JWKS)
- **Backend resolves the linked application user** (database role + permissions)
- **Frontend uses backend role/permissions for UX** (not Keycloak realm roles)

## Key Files

| File | Purpose |
|------|---------|
| `src/auth/keycloak.ts` | Keycloak-js client initialization |
| `src/auth/AuthProvider.tsx` | Auth context, /auth/me resolution, token refresh |
| `src/api/client.ts` | Axios interceptor attaches Keycloak tokens |
| `src/config/env.ts` | Typed environment variable access |
| `src/components/auth/LoginPage.tsx` | SSO redirect (Keycloak) or legacy form |
| `src/components/auth/ProtectedRoute.tsx` | Route guard with loading states |

## Rollback

Set `VITE_AUTH_PROVIDER=legacy` in `Frontend/.env` and restart. No backend changes needed.

## Keycloak Client Configuration

The `banking-portal-web` client must be configured in Keycloak as:
- Public client (no secret)
- Standard Flow enabled
- PKCE S256
- Direct Access Grants disabled
- Valid redirect URIs: `http://localhost:3000/*`
- Valid web origins: `http://localhost:3000`
