# Authentication User Journey

## Flow Overview

```
Landing Page → Keycloak SSO → Auth Callback → /auth/me → Dashboard
     ↑                                                          |
     └──────────── Session Expired ←────────────────────────────┘
```

## States

### Bootstrapping
- **Visual**: Pulsing dots animation
- **Action**: None — system loading auth state
- **Duration**: Typically <1s

### Unauthenticated
- **Visual**: Redirect to Keycloak login
- **Action**: Automatic — no user input needed
- **Keycloak URL**: Configured via `VITE_KEYCLOAK_URL`

### Authenticated
- **Visual**: Redirect to `/banking` (or stored return URL)
- **Action**: Full sidebar + topbar visible, all features accessible per role

### Session Expired
- **Visual**: "Session Expired" card with re-login button
- **Action**: Click "Re-authenticate" → Keycloak redirect
- **Auto-redirect**: 5s countdown before automatic redirect

### Unlinked User
- **Visual**: "Account Not Linked" card
- **Action**: Contact admin to link Keycloak identity to internal user record
- **Backend**: `/auth/me` returns 404 for unknown Keycloak sub

### Forbidden
- **Visual**: "Access Suspended" card
- **Action**: Contact administrator
- **Backend**: User record has `is_active: false`

### Error
- **Visual**: "Connection Error" card with retry button
- **Action**: Click "Try Again" to retry `/auth/me` fetch

## Dual Auth Mode

### Keycloak (Production)
```env
VITE_AUTH_PROVIDER=keycloak
```
- SSO-only login page (no form inputs)
- "Continue with SSO" button triggers Keycloak redirect
- Full token refresh cycle handled by `AuthProvider`

### Legacy (Demo)
```env
VITE_AUTH_PROVIDER=legacy
```
- Username/password form (admin/admin123, analyst/analyst123)
- No external dependencies
- Mock JWT tokens for development

## Token Management

- **Storage**: localStorage (`auth_token`)
- **Refresh**: Automatic before expiry via `AuthProvider`
- **Headers**: `Authorization: Bearer <token>` on all API calls
- **Logout**: Clears token, redirects to `/`
