# Role Mapping — Keycloak to Application

## Keycloak Realm Roles → Application Roles

| Keycloak Realm Role | Application Role | Notes |
|--------------------|-----------------|-------|
| `banking_analyst` | `analyst` | Direct mapping |
| `executive_manager` | `manager` | Direct mapping |
| `risk_officer` | `analyst` | Temporary — dedicated role in later increment |
| `compliance_officer` | `compliance` | Direct mapping |
| `internal_auditor` | `compliance` | Temporary — dedicated role in later increment |
| `administrator` | `admin` | Direct mapping |

Unknown Keycloak roles are ignored.

## Resolution Rule

The mapping function `_map_keycloak_roles_to_application_role()` handles two cases:

1. **No mapped roles found** → returns `None`. The user's application role comes from the database (the `users.role` column), not from Keycloak. Authentication succeeds; authorization depends on the DB role.

2. **Multiple distinct app roles found** (e.g. `banking_analyst` + `administrator` → `analyst` + `admin`) → raises `AmbiguousRoleMappingError`, returns HTTP 403. Each token must resolve to exactly one application role.

3. **Single mapped role, multiple KC role names** (e.g. `risk_officer` + `banking_analyst` → both map to `analyst`) → highest priority wins:

```
admin (4) > compliance (3) > manager (2) > analyst (1)
```

## When Mapping Runs

- **Linked users (production)**: Mapping does NOT run. The application role is read from `users.role` in the database. Keycloak roles in the token are recorded in `keycloak_realm_roles` for audit but not used for authorization.
- **DEV_MODE transient users** (no DB): Mapping runs against Keycloak token roles. Returns `"unmapped"` if no roles map.

## Implementation

Central mapping function: `routes.py:_map_keycloak_roles_to_application_role()`

Do NOT scatter role-name conversion throughout routes. All role mapping goes through this single function.

## Database Permissions

After resolving the application role, the system loads business permissions from:
1. `role_permissions` junction table (for the application role)
2. `users.permissions` column (custom per-user overrides)

These are merged and additive — the application role determines the base role, database permissions determine fine-grained access.
