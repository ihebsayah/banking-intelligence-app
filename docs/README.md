# Banking Intelligence System

> Natural language → SQL → results. Production-grade AI agent pipeline for banking analytics.

## What It Solves

Banking analysts spend hours writing SQL and waiting for IT. This system lets any analyst type plain English and get instant, secure, role-filtered data insights from the bank's PostgreSQL database — with zero SQL knowledge required.

## Key Features

- 🧠 **Natural language queries** — "Top 10 customers by balance" → instant results
- 🔒 **Zero SQL injection** — 5-layer validation + HMAC signing blocks all attacks
- 👤 **Role-based access** — Analyst, Manager, Compliance, Customer roles enforced at row+column level
- 🏦 **PII protection** — SSN, credit cards, emails auto-masked
- ⚡ **Redis caching** — Repeated queries served in <500ms
- 📊 **Multi-format output** — JSON, CSV, ASCII table
- 🐳 **10 Docker containers** — Fully containerized, production-ready

## Quick Start

**1. Start the system:**
```bash
git clone <repo>
cd banking-intelligence-system
cp .env.example .env
docker-compose up -d
```

**2. Login and get a token:**
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"analyst1","password":"analyst_pass_123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

**3. Query the system:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Top 10 customers by account balance", "format": "json"}'
```

## Architecture Overview

```
User Query (natural language)
        │
        ▼
[API Gateway :8000] ── JWT Auth ── Audit Logging
        │
        ▼
[Intent Agent :8002] ── Classify query into 8 categories
        │
        ▼
[Schema Agent :8003] ── Map intent → database tables
        │
        ▼
[Entity Resolution :8004] ── Build join paths
        │
        ▼
[SQL Agent :8005] ── Generate parameterized SQL
        │
        ▼
[Validation Agent :8006] ── 5-check security + HMAC sign
        │
        ▼
[Execution Agent :8007] ── Execute, cache, mask PII, format
        │
        ▼
Results (JSON / CSV / Table) + Metadata
```

## Documentation

| Doc | Description |
|-----|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, agents, data flow |
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | All endpoints with examples |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Step-by-step deployment guide |
| [SECURITY.md](SECURITY.md) | Security model and compliance |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local setup and contribution guide |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues and fixes |

## Testing

```bash
# Run all 156 tests
pytest tests/ -v

# Unit tests only (65 tests)
pytest tests/test_*.py -v --ignore=tests/test_integration.py --ignore=tests/test_security.py --ignore=tests/test_performance.py

# Security tests (51 tests, all injections blocked)
pytest tests/test_security.py -v

# Integration tests (15 tests)  
pytest tests/test_integration.py -v
```

## Project Status

- **Week 1** ✅ Docker infrastructure + API Gateway + Audit Logging
- **Week 2** ✅ Intent Recognition + Schema Understanding + Embedding Service  
- **Week 3** ✅ Entity Resolution + SQL Generation + Validation Agent
- **Week 4** ✅ Execution Agent + Redis Caching + Orchestrator
- **Week 5** ✅ 156 tests + Security hardening + Documentation + Demo
