# Authentication User Journey

## SSO-First Flow

```
Application opens
    │
    ├─ Check existing Keycloak session (check-sso)
    │
    ├─ Session exists → fetch /auth/me → enter application
    │
    └─ No session → SSO Landing Page
                        │
                        └─ "Continue with SSO"
                              │
                              └─ Redirect to Keycloak
                                    │
                                    └─ User authenticates
                                          │
                                          └─ Return to application
                                                │
                                                └─ Fetch /auth/me
                                                      │
                                                      ├─ 200 → Enter application
                                                      ├─ 401 USER_NOT_FOUND → Account Not Linked screen
                                                      ├─ 401 TOKEN_EXPIRED → retry refresh → retry /auth/me
                                                      ├─ 403 → Access Suspended screen
                                                      └─ Network error → Backend Unavailable screen
```

## Auth Phases

| Phase | What the user sees |
|-------|-------------------|
| `bootstrapping` | "Connecting securely..." with animated dots |
| `loading-user` | "Loading your workspace..." with animated dots |
| `unauthenticated` | SSO Landing Page (redirect) |
| `authenticated` | Application shell |
| `unlinked` | Account Not Linked — Sign Out + Contact Administrator |
| `forbidden` | Access Suspended — Sign Out |
| `expired` | Session Expired — Sign in again |
| `error` | Auth Service Unavailable — Retry |

## Token Refresh

- Automatic refresh 60 seconds before expiry
- `onTokenExpired` callback triggers silent refresh
- If refresh fails → phase becomes `expired`
- User sees "Session Expired" with sign-in button

## Key Design Decisions

- **No password fields** in Keycloak mode — authentication belongs to Keycloak
- **No token display** — tokens are managed by keycloak-js internally
- **No remember me** — session managed by Keycloak
- **No password reset** — handled by Keycloak
- **Backend failure does not logout** — keeps identity, shows retry screen
