# Performance and Scalability Report

**Date:** 2026-07-26
**Purpose:** Quantify system performance characteristics and identify scalability constraints.
**Method:** Code inspection + V2 blind benchmark measurements (single run, dry-run mode).

---

## 1. Pipeline Latency

### Measured (V2 Blind Benchmark, single run)

| Metric | Value | Source |
|--------|-------|--------|
| Total requests | 160 | V2 results |
| Successful completions | 142 (88.8%) | V2 results |
| Failed/unsupported | 18 (11.2%) | V2 results |

**Note:** V2 benchmark did not record per-request latency. No distributed tracing exists. The numbers below are derived from code analysis, not measured.

### Estimated Per-Stage Latency (Code Analysis)

| Stage | Mechanism | Estimated Latency | Bottleneck Risk |
|-------|-----------|-------------------|-----------------|
| JWT validation | HS256 verify | <1ms | None |
| Intent classification | spaCy NLP + keyword scoring | 10-50ms | Low (CPU-bound) |
| Schema mapping | Static dict lookup | <1ms | None |
| Entity resolution | Static dict + join construction | <1ms | None |
| SQL generation | Template + parameter binding | <1ms | None |
| Validation | 5 regex checks + sqlparse | 1-5ms | Low |
| Compliance check | Role-based rule evaluation | <1ms | None |
| HMAC signing | SHA-256 | <1ms | None |
| **Total (pre-execution)** | | **~15-60ms** | **Low** |
| PostgreSQL execution | asyncpg parameterized query | 10-500ms | **Medium** (query-dependent) |
| Redis cache lookup | GET + TTL check | 1-5ms | Low |
| PII masking | Regex column scan | 1-10ms | Low |
| RBAC filtering | Role-based WHERE injection | <1ms | None |
| Insights generation | 5 SQL queries + stats + LLM | 200-2000ms | **High** (LLM-dependent) |
| Audit logging | Fire-and-forget INSERT | <1ms | None (async) |

**Estimated end-to-end (cached):** 50-200ms
**Estimated end-to-end (uncached):** 200-2500ms (dominated by insights agent)

---

## 2. Connection Pooling

### Execution Agent (asyncpg)

| Parameter | Value | Location |
|-----------|-------|----------|
| Pool min size | 2 | `config.py:244` |
| Pool max size | 10 | `config.py:245` |
| Query timeout | 30s | `config.py:246` |
| Pool type | asyncpg (connection pool) | `query_executor.py:407` |

**Assessment:** Adequate for single-server deployment. Max 10 concurrent PostgreSQL connections. Under load, queries will queue in the pool. No connection health check code visible (asyncpg handles this internally).

### Schema Agent (Redis)

| Parameter | Value | Location |
|-----------|-------|----------|
| Cache TTL | 3600s (1h) | `config.py:227` |
| Pool max connections | 5 | `config.py:228` |
| Cache namespace | `db:{db_name}:` | `schema_service.py:43` |

### Entity Resolution Agent (Redis)

| Parameter | Value | Location |
|-----------|-------|----------|
| Cache TTL | 86400s (24h) | `config.py:138` |
| Pool max connections | 5 | `config.py:139` |
| Cache prefix | `semantic:` | `repository.py:46` |

### Insights Agent (Redis)

| Parameter | Value | Location |
|-----------|-------|----------|
| Pool max connections | 5 | `config.py:116` |
| Cache TTL | 3600s | `config.py:117` |

### Total Redis Connections

Each service opens up to 5 Redis connections. With 13 services, maximum Redis connections = 65. Default Redis max clients = 10,000. **No risk.**

---

## 3. Caching Strategy

| Service | Cache Key | TTL | Eviction |
|---------|-----------|-----|----------|
| Execution Agent | SHA-256(sql + params) | 3600s | TTL only |
| Schema Agent | SHA-256(intent + domain) | 3600s | TTL only |
| Entity Resolution | `semantic:{key}` | 86400s | TTL only |
| Insights Agent | SHA-256(sql + params) | 3600s | TTL only |

**Issues:**
- No LRU or size-based eviction — Redis memory could grow unbounded
- No cache invalidation on schema changes
- Execution cache includes RBAC-filtered results — different users with same query get different caches (correct)
- Schema/entity caches are shared across users (correct for metadata)

---

## 4. Timeout Protection

| Component | Timeout | Behavior |
|-----------|---------|----------|
| PostgreSQL query | 30s | Query canceled, error returned |
| HTTP inter-service | 30s (default aiohttp) | Request fails, error propagated |
| Redis operations | 10s (explicit) | Operation fails, error logged |
| Ollama LLM | 30s | TimeoutError caught, template fallback |
| HMAC verification | <1s | Rejects tampered queries immediately |

**Assessment:** All external calls have timeout protection. No infinite loops detected. Circuit breaker pattern not implemented — a failing PostgreSQL will cause all requests to timeout at 30s.

---

## 5. Scalability Constraints

### Current: Single-Server Deployment

| Constraint | Limit | Impact |
|------------|-------|--------|
| PostgreSQL connections | 10 (pool max) | Max ~10 concurrent queries |
| Ollama LLM | Single model instance | Serial insight generation |
| Redis | Single instance | No HA, no clustering |
| Docker Compose | Single-host | No horizontal scaling |
| spaCy model | In-memory per service | ~500MB per intent/schema service |

### Bottleneck Analysis

| Bottleneck | Severity | Mitigation |
|------------|----------|------------|
| PostgreSQL pool exhaustion | **HIGH** | Under 10 concurrent queries, new requests queue. Under sustained load, requests timeout at 30s. |
| Ollama LLM throughput | **HIGH** | tinyllama is serial. Insight generation for 10 concurrent requests = sequential queue. |
| Redis single instance | **MEDIUM** | Cache miss on restart causes cold-start stampede to PostgreSQL. |
| spaCy memory | **LOW** | Each service loads its own spaCy model (~500MB). 13 services = ~6.5GB just for NLP models. |
| No horizontal scaling | **MEDIUM** | Docker Compose is single-host. Cannot add more API Gateway or Orchestrator instances without load balancer. |

### Horizontal Scaling Feasibility

| Component | Stateless? | Scale-out Ready? |
|-----------|-----------|-----------------|
| API Gateway | Yes (JWT stateless) | Yes (add instances + LB) |
| Orchestrator | Yes (per-request state) | Yes |
| Intent Agent | Yes | Yes |
| Schema Agent | Yes (Redis shared) | Yes |
| Entity Resolution | Yes (Redis shared) | Yes |
| SQL Agent | Yes | Yes |
| Validation Agent | Yes | Yes |
| Execution Agent | Yes (asyncpg pool per instance) | Yes (but PostgreSQL is bottleneck) |
| Insights Agent | Yes | Yes (but Ollama is bottleneck) |
| Audit Agent | Yes (separate DB) | Yes |
| Compliance Agent | Yes | Yes |

**Verdict:** All services are stateless and technically scale-out ready. The real bottlenecks are PostgreSQL (single writer) and Ollama (single model instance).

---

## 6. Resource Consumption (Estimated)

| Resource | Per Service | Total (13 services) |
|----------|------------|---------------------|
| CPU (idle) | 0.1-0.5 cores | 1.3-6.5 cores |
| Memory (base) | 100-300MB | 1.3-3.9GB |
| Memory (spaCy loaded) | +500MB (intent, schema) | +1GB |
| Memory (Redis) | N/A | 100-500MB |
| Memory (PostgreSQL) | N/A | 500MB-2GB |
| Disk (PostgreSQL) | N/A | 1-10GB (data dependent) |
| **Total estimated** | | **3-8GB RAM, 2-4 CPU cores** |

---

## 7. Concurrency Characteristics

| Scenario | Behavior | Risk |
|----------|----------|------|
| 1 concurrent query | Normal execution | None |
| 5 concurrent queries | Pool half-utilized, all complete | Low |
| 10 concurrent queries | Pool saturated, new requests queue | **Medium** — queuing delay |
| 20 concurrent queries | Pool exhausted, 10 waiting, 30s timeouts | **High** — 50% failure rate |
| 100 concurrent queries | Massive queuing, widespread timeouts | **Critical** — system unusable |

---

## 8. Recommendations

### Before Production
1. **Add request-level latency tracking** — Currently impossible to measure actual performance
2. **Set Redis maxmemory** — Prevent unbounded memory growth
3. **Add connection pool metrics** — Monitor pool exhaustion

### Before Wider Deployment
4. **Add connection pool monitoring** — Track utilization, wait times
5. **Consider read replicas** — Offload SELECT queries from primary PostgreSQL
6. **Add load balancer** — Enable horizontal scaling of stateless services
7. **Benchmark with concurrent users** — V2 was single-run, no concurrency testing

### For Scale
8. **Ollama clustering** — Multiple model instances for parallel insight generation
9. **Redis Sentinel/Cluster** — HA for caching layer
10. **Kubernetes migration** — Replace Docker Compose for auto-scaling
