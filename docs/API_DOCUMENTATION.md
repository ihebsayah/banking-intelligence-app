# API Documentation — Banking Intelligence System

Base URL: `http://localhost:8000`  
All authenticated endpoints require: `Authorization: Bearer <JWT_TOKEN>`

---

## Authentication

### POST /auth/login
Get a JWT access token.

**Request:**
```json
{
  "username": "analyst1",
  "password": "analyst_pass_123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user_role": "analyst"
}
```

**Test users:**

| Username | Password | Role |
|----------|----------|------|
| `analyst1` | `analyst_pass_123` | analyst |
| `manager1` | `manager_pass_456` | manager |
| `compliance1` | `compliance_pass_789` | compliance |

---

## Core Query Endpoint

### POST /query ⭐
**The main endpoint.** Accepts natural language and returns results.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request:**
```json
{
  "query": "Top 10 customers by account balance",
  "format": "json",
  "limit": 10
}
```

**Parameters:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Natural language banking query |
| `format` | enum | `"json"` | `"json"` \| `"csv"` \| `"table"` |
| `limit` | int | `10` | Max rows returned (1-1000) |

**Response (JSON format):**
```json
{
  "success": true,
  "data": [
    {"customer_id": 1001, "name": "Alice Johnson", "balance": 250000.00},
    {"customer_id": 1002, "name": "Bob Smith", "balance": 198500.50}
  ],
  "metadata": {
    "rows_returned": 2,
    "source": "live",
    "time_ms": 145,
    "intent": "customer_analysis",
    "sql_generated": "SELECT c.customer_id, c.name, a.balance FROM customers c LEFT JOIN accounts a ON c.customer_id = a.customer_id ORDER BY a.balance DESC LIMIT 10",
    "tables_used": ["customers", "accounts"],
    "columns_masked": [],
    "validation_checks": ["syntax_check", "select_only", "keyword_check", "limit_check", "pattern_check"]
  }
}
```

**Response (CSV format):**
```
customer_id,name,balance
1001,Alice Johnson,250000.00
1002,Bob Smith,198500.50
```

**Response (Table format):**
```
+─────────────+──────────────────+─────────────+
| customer_id | name             | balance     |
+─────────────+──────────────────+─────────────+
| 1001        | Alice Johnson    | 250000.00   |
| 1002        | Bob Smith        | 198500.50   |
+─────────────+──────────────────+─────────────+
```

**Cached response:**
```json
{
  "success": true,
  "data": [...],
  "metadata": {
    "source": "cache",
    "time_ms": 12,
    ...
  }
}
```

---

## Example Queries

### Customer Analysis
```bash
# Top customers by balance
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Top 10 customers by account balance", "format": "json"}'

# High-value customer segments
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Premium segment customers with balance over 100k", "limit": 50}'

# Customer KYC status
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Customers who have not completed KYC verification"}'
```

### Risk Analysis
```bash
# High-risk customers (compliance role gets unmasked SSN)
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $COMPLIANCE_TOKEN" \
  -d '{"query": "Customers with high risk scores and active AML flags"}'

# Recent fraud flags
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Transactions flagged as suspicious in last 30 days", "limit": 100}'
```

### Revenue Analysis
```bash
# Revenue by product type
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Revenue by product type this quarter", "format": "csv"}'

# Branch revenue
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Top 5 branches by total fee income"}'
```

### Transaction Analysis
```bash
# High-value transactions
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Transactions over 50000 in the last month"}'

# Transaction volume by type
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Transaction count and volume by transaction type"}'
```

### Geographic Analysis
```bash
# Performance by region
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Customer distribution by city and state"}'
```

### Compliance Analysis
```bash
# KYC audit
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $COMPLIANCE_TOKEN" \
  -d '{"query": "Customers pending KYC with account activity in last 90 days"}'
```

---

## Health & Monitoring Endpoints

### GET /health
System health check.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.5.0-week5-mvp",
  "agents": {
    "intent": "healthy",
    "schema": "healthy",
    "entity_resolution": "healthy",
    "sql": "healthy",
    "validation": "healthy",
    "execution": "healthy"
  },
  "database": "connected",
  "cache": "connected",
  "timestamp": "2025-05-15T01:00:00Z"
}
```

### GET /metrics
System metrics (no auth required for monitoring).

```json
{
  "requests_total": 1542,
  "cache_hits": 891,
  "cache_misses": 651,
  "cache_hit_rate": 0.577,
  "avg_response_ms": 234,
  "errors_total": 12,
  "active_connections": 4
}
```

---

## Error Responses

All errors return a consistent envelope:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Query blocked: dangerous keyword detected (UNION)",
    "issues": ["Dangerous keyword(s) detected: UNION"],
    "checks_failed": ["keyword_check"]
  }
}
```

**Error codes:**

| Code | HTTP | Cause |
|------|------|-------|
| `AUTH_REQUIRED` | 401 | Missing or invalid JWT |
| `TOKEN_EXPIRED` | 401 | Token past expiry |
| `PERMISSION_DENIED` | 403 | Role insufficient for operation |
| `VALIDATION_FAILED` | 400 | SQL blocked by security checks |
| `QUERY_TIMEOUT` | 408 | Query exceeded 30s timeout |
| `PIPELINE_ERROR` | 500 | Internal agent failure |
| `RATE_LIMITED` | 429 | Too many requests (100/min default) |

---

## Individual Agent Endpoints

Each agent is also directly accessible (for debugging/testing):

### POST /api/intent/classify
```json
Request:  {"query": "Top customers by balance"}
Response: {"primary_category": "customer_analysis", "confidence": 0.85, ...}
```

### POST /api/schema/match
```json
Request:  {"intents": ["customer_analysis"]}
Response: {"tables": ["customers", "accounts", ...], "domains": [...]}
```

### POST /api/sql/generate
```json
Request:  {"primary_entity": "customer", "tables": [...], "limit": 10, ...}
Response: {"sql": "SELECT ...", "parameters": [], "is_parameterized": true}
```

### POST /api/validation/validate
```json
Request:  {"sql": "SELECT ... LIMIT 10", "parameters": []}
Response: {"safe": true, "signature": "sha256:abc...:1234", "checks_passed": [...]}
```

### POST /api/execution/execute
```json
Request:  {"sql": "...", "parameters": [], "signature": "sha256:...", "format": "json"}
Response: {"rows": [...], "metadata": {...}}
```

---

## Rate Limiting

Default limits per user:
- **100 requests/minute** — standard
- **1000 requests/hour** — burst protection
- **Compliance role:** 500 requests/minute (higher for audit use cases)

Rate limit headers included in all responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1715731200
```

---

## Pagination

For large result sets, use `limit` and page via query constraints:

```bash
# Page 1
curl -X POST http://localhost:8000/query \
  -d '{"query": "All active accounts", "limit": 100}'

# Page 2 (use last seen ID as constraint)
curl -X POST http://localhost:8000/query \
  -d '{"query": "Active accounts where account_id > 100", "limit": 100}'
```

> **Note:** For production, consider adding explicit pagination with cursor-based pagination to the `/query` endpoint.

---

## WebSocket Streaming (Future)

Planned for v0.6: `ws://localhost:8000/query/stream` will stream results row-by-row for large queries.
