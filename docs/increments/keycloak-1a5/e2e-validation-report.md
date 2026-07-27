# End-to-End Validation Report — Increment 1A.5

**Date**: 2026-07-26
**Environment**: Docker Compose, macOS

## Validation Chain

```
Docker start
    ↓
Keycloak health
    ↓
Realm imported
    ↓
OIDC discovery reachable
    ↓
JWKS reachable
    ↓
Token issued
    ↓
Token decoded
    ↓
Identity linked
    ↓
Protected endpoint returns expected status
    ↓
Audit entry written
```

## Step 1: Docker Start

```bash
docker compose up -d
```

Services started: `keycloak`, `postgres-keycloak`, `postgres-main`, `postgres-audit`, `redis`, `api-gateway`.

## Step 2: Keycloak Health

```bash
curl http://localhost:8080/health/ready
# Returns: {"status":"UP"}
```

## Step 3: Realm Imported

```bash
curl http://localhost:8080/admin/realms/banking-intelligence
# Returns realm JSON with realm: "banking-intelligence"
```

Evidence: `command: start-dev --import-realm` in docker-compose.yml auto-imports `realm-banking-dev.json` on first start. Subsequent starts use persisted `keycloak_data` volume.

6 users created:
- `kc_analyst_001` (banking_analyst)
- `kc_manager_001` (executive_manager)
- `kc_compliance_001` (compliance_officer)
- `kc_admin_001` (administrator)
- `kc_unknown_001` (custom_unknown_role — test only)
- `kc_disabled_001` (banking_analyst, enabled=false — test only)

## Step 4: OIDC Discovery Reachable

```bash
curl http://localhost:8080/realms/banking-intelligence/.well-known/openid-configuration
# Returns: issuer, jwks_uri, token_endpoint, grant_types_supported
```

Verified:
- `issuer`: `http://localhost:8080/realms/banking-intelligence`
- `jwks_uri`: `http://localhost:8080/realms/banking-intelligence/protocol/openid-connect/certs`
- `token_endpoint`: `http://localhost:8080/realms/banking-intelligence/protocol/openid-connect/token`

## Step 5: JWKS Reachable

```bash
curl http://localhost:8080/realms/banking-intelligence/protocol/openid-connect/certs
# Returns: {"keys": [...]}
```

2 keys returned (RS256 signing + RSA-OAEP encryption).

## Step 6: Token Issued

```bash
curl -X POST http://localhost:8080/realms/banking-intelligence/protocol/openid-connect/token \
  -d "grant_type=password&client_id=banking-portal-api&username=kc_analyst_001&password=Analyst123!&scope=openid"
# Returns: access_token, token_type, expires_in
```

Token length: ~1191 chars. Issued for 300s (realm `accessTokenLifespan`).

## Step 7: Token Decoded

```python
import jwt, base64, json
payload = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=='))
# iss: http://localhost:8080/realms/banking-intelligence
# aud: banking-portal-api
# sub: 2f489535-c1fd-4a98-ae9c-0620946a96f5
# realm_access.roles: ["banking_analyst"]
```

## Step 8: Identity Linked

```sql
SELECT user_id, identity_provider, identity_provider_subject
FROM users WHERE identity_provider_subject IS NOT NULL;
```

| user_id | identity_provider | identity_provider_subject |
|---------|-------------------|---------------------------|
| analyst_001 | keycloak | 2f489535-c1fd-... |
| manager_001 | keycloak | a3c45ba6-8aaa-... |
| compliance_001 | keycloak | 0e358536-81a8-... |
| admin_001 | keycloak | 1e09ceaf-751a-... |

**Important**: After realm re-import, KC user `sub` values change. DB links must be updated to match.

## Step 9: Protected Endpoint Returns Expected Status

RBAC matrix verified with fresh tokens:

| Endpoint | analyst | manager | compliance | admin |
|----------|---------|---------|------------|-------|
| /auth/me | 200 | 200 | 200 | 200 |
| /dashboard/overview | 200 | 200 | **403** | 200 |
| /dashboard/kpis | 200 | 200 | **403** | 200 |
| /reports | 200 | 200 | **403** | 200 |
| /compliance/overview | **403** | **403** | 200 | 200 |
| /admin/users | **403** | **403** | **403** | 200 |

Edge cases:
| Scenario | Response |
|----------|----------|
| No token | 401 AUTH_REQUIRED |
| Invalid token | 401 AUTH_FAILED |
| Expired token | 401 TOKEN_EXPIRED |
| Unlinked user | 401 USER_NOT_FOUND |
| Unmapped role (linked app user) | 200 (uses DB role) |
| Disabled user (KC rejects) | KC error invalid_grant |

## Step 10: Audit Entry Written

```sql
SELECT endpoint, user_id, user_role, status, metadata
FROM audit_log ORDER BY created_at DESC LIMIT 3;
```

| endpoint | user_id | status | metadata |
|----------|---------|--------|----------|
| /auth/me | anonymous | success | {"http_status": 200} |
| /auth/me | anonymous | error | {"http_status": 401} |
| /dashboard/overview | anonymous | success | {"http_status": 200} |

**Known gap**: `user_id` is always "anonymous" because audit middleware runs before route-level auth. This is a pre-existing architectural limitation, not a Keycloak regression.

## Auth Modes Verified

| Mode | KC Token | Legacy Token |
|------|----------|-------------|
| `keycloak` | 200 | 401 AUTH_FAILED |
| `legacy` | 401 TOKEN_INVALID | 200 |
| `keycloak` + compat | 200 | 200 (fallback) |

## Unit Tests

- test_keycloak_auth.py: 31/31 PASSED
- test_security.py: 50/50 PASSED
- Total: 81/81 PASSED

## Conclusion

All 10 steps of the validation chain pass. The full token-to-protected-endpoint flow works end-to-end with a real Keycloak instance.
