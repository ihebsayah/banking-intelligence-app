#!/bin/bash
# =============================================================================
# Banking Intelligence System — Week 1 Startup Script
# Run this from your Terminal (not via AI tool runner):
#   chmod +x start_week1.sh && ./start_week1.sh
# =============================================================================
set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJ_DIR"

echo ""
echo "══════════════════════════════════════════════════"
echo "  Banking Intelligence System — Week 1 Startup"
echo "══════════════════════════════════════════════════"
echo ""

# ── 1. Check Docker is running ───────────────────────────────────────────────
if ! docker info > /dev/null 2>&1; then
  echo "❌  Docker is not running. Please start Docker Desktop and try again."
  exit 1
fi
echo "✅  Docker is running"

# ── 2. Check .env exists ─────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo "❌  .env file not found. Please create it (copy .env.example)."
  exit 1
fi
echo "✅  .env file found"

# ── 3. Start containers ───────────────────────────────────────────────────────
echo ""
echo "▶  Starting all containers with docker-compose up -d ..."
docker-compose up -d
echo ""

# ── 4. Wait for healthy DBs (up to 60s) ──────────────────────────────────────
echo "⏳  Waiting for PostgreSQL instances to be healthy..."
for i in $(seq 1 12); do
  PG_MAIN=$(docker inspect --format='{{.State.Health.Status}}' banking_postgres_main 2>/dev/null || echo "unknown")
  PG_AUDIT=$(docker inspect --format='{{.State.Health.Status}}' banking_postgres_audit 2>/dev/null || echo "unknown")
  PG_EMB=$(docker inspect --format='{{.State.Health.Status}}' banking_postgres_embeddings 2>/dev/null || echo "unknown")
  REDIS=$(docker inspect --format='{{.State.Health.Status}}' banking_redis 2>/dev/null || echo "unknown")

  if [ "$PG_MAIN" = "healthy" ] && [ "$PG_AUDIT" = "healthy" ] && \
     [ "$PG_EMB" = "healthy" ] && [ "$REDIS" = "healthy" ]; then
    echo "✅  All databases healthy"
    break
  fi
  echo "   still waiting... ($i/12)  pg-main=$PG_MAIN  pg-audit=$PG_AUDIT  pg-emb=$PG_EMB  redis=$REDIS"
  sleep 5
done

# ── 5. Wait for API Gateway ───────────────────────────────────────────────────
echo ""
echo "⏳  Waiting for API Gateway to come up (installs deps first time)..."
for i in $(seq 1 24); do
  HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
  if [ "$HEALTH" = "200" ]; then
    echo "✅  API Gateway is healthy"
    break
  fi
  echo "   waiting for API Gateway... ($i/24) HTTP=$HEALTH"
  sleep 5
done

# ── 6. Wait for Audit Agent ───────────────────────────────────────────────────
echo ""
echo "⏳  Waiting for Audit Agent..."
for i in $(seq 1 24); do
  HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8008/health 2>/dev/null || echo "000")
  if [ "$HEALTH" = "200" ]; then
    echo "✅  Audit Agent is healthy"
    break
  fi
  echo "   waiting for Audit Agent... ($i/24) HTTP=$HEALTH"
  sleep 5
done

# ── 7. Final status ───────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "  Container Status"
echo "══════════════════════════════════════════════════"
docker-compose ps

# ── 8. Acceptance tests ───────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "  Week 1 Acceptance Tests"
echo "══════════════════════════════════════════════════"
echo ""

# Test /health
GW_HEALTH=$(curl -s http://localhost:8000/health)
echo "▶  GET /health:"
echo "   $GW_HEALTH"
echo ""

# Test /auth/login as analyst
echo "▶  POST /auth/login (analyst_001):"
LOGIN_RESP=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=analyst_001&password=password")
echo "   $LOGIN_RESP"
echo ""

# Extract token
TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || echo "")

if [ -n "$TOKEN" ]; then
  echo "✅  JWT token received"
  echo ""

  # Test /auth/login as compliance
  echo "▶  POST /auth/login (compliance_001):"
  COMP_RESP=$(curl -s -X POST http://localhost:8000/auth/login \
    -d "username=compliance_001&password=password")
  echo "   $COMP_RESP"
  echo ""

  # Test /auth/login as manager
  echo "▶  POST /auth/login (manager_001):"
  MGR_RESP=$(curl -s -X POST http://localhost:8000/auth/login \
    -d "username=manager_001&password=password")
  echo "   $MGR_RESP"
  echo ""

  # Test bad credentials
  echo "▶  POST /auth/login (bad credentials — expect 401):"
  BAD_RESP=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST http://localhost:8000/auth/login \
    -d "username=hacker&password=wrongpass")
  echo "   $BAD_RESP"
  echo ""
else
  echo "⚠️   No token received. Check API Gateway logs:"
  echo "    docker-compose logs api-gateway"
fi

# Verify audit log entry
echo "▶  Audit log (latest entries in postgres-audit):"
docker exec banking_postgres_audit psql -U audit_user -d audit_logs \
  -c "SELECT audit_id, user_id, action, status, timestamp FROM audit_log ORDER BY timestamp DESC LIMIT 5;" \
  2>/dev/null || echo "   (audit DB not ready yet — try again in 30s)"
echo ""

echo "══════════════════════════════════════════════════"
echo "  Week 1 startup complete."
echo "  Docs: http://localhost:8000/docs"
echo "══════════════════════════════════════════════════"
