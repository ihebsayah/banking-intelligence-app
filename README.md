# Banking Intelligence System

Sophisticated banking intelligence platform for headquarters analysts.  
Natural-language queries → secure SQL → audited results.

## Architecture

```
API Gateway (8000)
    └── Orchestrator Agent (8001)
            ├── Intent Agent (8002)
            ├── Schema Agent (8003)
            ├── Entity Resolution Agent (8004)
            ├── SQL Agent (8005)
            ├── Validation Agent (8006)
            ├── Execution Agent (8007)
            └── Audit Agent (8008)

Infrastructure:
  postgres-main      (5432)  — banking data
  postgres-audit     (5433)  — immutable audit logs
  postgres-embeddings(5434)  — pgvector embeddings
  redis              (6379)  — query cache / sessions
  ollama             (11434) — local LLM fallback
  embedding-service  (8009)  — schema vector computation
  secrets-manager    (8010)  — credential management
```

## Quick Start

```bash
# 1. Configure environment
cp .env .env.local
# Edit .env — set your CLAUDE_API_KEY

# 2. Start all services
docker-compose up -d

# 3. Check status
docker-compose ps

# 4. Test API Gateway
curl http://localhost:8000/health

# 5. Authenticate
curl -X POST http://localhost:8000/auth/login \
  -d "username=analyst_001&password=password"
```

## Mock Users (MVP)

| Username        | Password   | Role        |
|-----------------|------------|-------------|
| analyst_001     | password   | analyst     |
| analyst_002     | password   | analyst     |
| compliance_001  | password   | compliance  |
| manager_001     | password   | manager     |

## Development Roadmap

| Week | Focus                                      | Status        |
|------|--------------------------------------------|---------------|
| 1    | Foundation: Docker + Auth + Audit Logging  | ✅ Complete   |
| 2    | Intent Recognition + Schema Understanding  | 🔜 Planned    |
| 3    | SQL Generation + Validation                | 🔜 Planned    |
| 4    | Query Execution + Results + Caching        | 🔜 Planned    |
| 5    | Polish + Security Testing + Documentation  | 🔜 Planned    |

## Security

- All queries use parameterized `$1/$2` placeholders — no string interpolation
- JWT authentication on all protected endpoints
- Rate limiting: 100 req/min per IP
- Immutable audit log (PostgreSQL RULE prevents UPDATE/DELETE)
- PII masking enforced at execution layer (Week 4)
- HMAC query signing (Week 3)

## Audit Logs

Every API call is logged to the immutable `audit_log` table:

```bash
# View latest audit entries
docker-compose exec postgres-audit \
  psql -U audit_user -d audit_logs \
  -c "SELECT audit_id, user_id, action, status, timestamp FROM audit_log ORDER BY timestamp DESC LIMIT 10"
```

## Service Health

```bash
curl http://localhost:8000/health   # API Gateway
curl http://localhost:8008/health   # Audit Agent
docker exec banking_redis redis-cli ping
docker exec banking_postgres_main psql -U banking_user -d banking_dev -c "SELECT 1"
```
