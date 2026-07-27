# Identity Linking — Keycloak to Application User

## Strategy

Keycloak authenticates the user. The application database stores business permissions. Linking connects a Keycloak identity to an application user record.

## New Database Columns

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS identity_provider_subject VARCHAR(255) UNIQUE NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS identity_provider VARCHAR(50) DEFAULT 'local';
```

- `identity_provider_subject`: The Keycloak `sub` claim value
- `identity_provider`: `'local'` (default) or `'keycloak'`

## Linking Flow

1. User authenticates via Keycloak and receives an RS256 access token
2. API Gateway validates the token and extracts the `sub` claim
3. System looks up `users.identity_provider_subject = sub`
4. If found: loads the application user and their database permissions
5. If not found: returns 401 "Keycloak user not linked to application account"

## Linking a User

```sql
-- Link an existing application user to their Keycloak identity
UPDATE users
SET identity_provider_subject = '<keycloak-sub-claim>',
    identity_provider = 'keycloak'
WHERE user_id = 'analyst_001';
```

The Keycloak `sub` claim can be obtained from the token payload or the Keycloak Admin Console.

## Development Mode

Requires both `DEV_MODE=true` and `KEYCLOAK_DEV_TRANSIENT_USERS_ENABLED=true`. Without both, unlinked Keycloak users get 401.

When enabled and no database is available, a transient user is created from Keycloak claims:
- `user_id` = `preferred_username` from the token
- `role` = mapped from Keycloak realm roles (or `"unmapped"` if no roles map)
- No database permissions (empty list)

## Safety

- New columns are nullable — existing users are unaffected
- No automatic user creation in production
- The `UNIQUE` constraint on `identity_provider_subject` prevents duplicate linking
- Suspended/inactive application users are rejected even with valid Keycloak tokens
