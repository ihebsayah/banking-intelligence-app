# Local Setup — Keycloak Development

## Prerequisites

- Docker Compose v2+
- Ports available: 8080 (Keycloak), 8000 (API Gateway)

## Quick Start

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Set Keycloak passwords in .env
KEYCLOAK_ADMIN_PASSWORD=admin
KEYCLOAK_DB_PASSWORD=keycloak_pass
KEYCLOAK_ADMIN=admin

# 3. Start all services
docker compose up -d

# 4. Wait for Keycloak to be healthy (~30-60s)
docker compose logs -f keycloak
# Look for: "Keycloak ... started"

# 5. Access Keycloak Admin Console
open http://localhost:8080/admin
# Login: admin / <your KEYCLOAK_ADMIN_PASSWORD>
```

## Obtain a Development Token

### Option A: Direct Access Grant (API testing)

```bash
curl -X POST http://localhost:8080/realms/banking-intelligence/protocol/openid-connect/token \
  -d "grant_type=password" \
  -d "client_id=banking-portal-web" \
  -d "username=kc_analyst_001" \
  -d "password=Analyst123!" \
  | python3 -m json.tool
```

Note: Direct Access Grant must be enabled on the `banking-portal-web` client in Keycloak admin for this to work. By default it's disabled for public clients.

### Option B: Use the Keycloak Admin CLI

```bash
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh get-users \
  --realm banking-intelligence \
  --no-config \
  --server http://localhost:8080 \
  --realm banking-intelligence \
  --user admin --password <admin_password>
```

## Call a Protected Endpoint

```bash
TOKEN="<paste access_token from above>"

# Legacy mode (default)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/dashboard/overview

# Keycloak mode: set AUTH_PROVIDER=keycloak in .env, restart api-gateway
```

## Development Users

| Username | Password | Keycloak Role | App Role |
|----------|----------|---------------|----------|
| kc_analyst_001 | Analyst123! | banking_analyst | analyst |
| kc_manager_001 | Manager123! | executive_manager | manager |
| kc_compliance_001 | Compliance123! | compliance_officer | compliance |
| kc_admin_001 | Admin123! | administrator | admin |

**WARNING**: These passwords are for development only. Do not use in production.

## Linking a Keycloak User to an Application User

After authenticating with Keycloak and obtaining the `sub` claim:

```sql
-- Connect to the banking database
docker compose exec postgres-main psql -U banking_user -d banking_dev

-- Link the user
UPDATE users
SET identity_provider_subject = '<keycloak-sub-claim>',
    identity_provider = 'keycloak'
WHERE user_id = 'analyst_001';
```

## Troubleshooting

### Keycloak won't start

```bash
docker compose logs keycloak
# Common: database connection refused -> check postgres-keycloak health
docker compose ps postgres-keycloak
```

### Token validation fails

1. Check AUTH_PROVIDER setting: `docker compose exec api-gateway env | grep AUTH`
2. Check JWKS endpoint: `curl http://localhost:8080/realms/banking-intelligence/protocol/openid-connect/certs`
3. Check API Gateway logs: `docker compose logs api-gateway | grep -i keycloak`
