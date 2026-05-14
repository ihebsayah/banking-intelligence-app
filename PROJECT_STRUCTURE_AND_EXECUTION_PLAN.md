# PROJECT STRUCTURE & EXECUTION PLAN
## Banking Intelligence Agent System - MVP Development

---

## DIRECTORY STRUCTURE

```
banking-intelligence-system/
│
├── docker-compose.yml              # Docker infrastructure
├── .env                            # Environment variables
├── .gitignore
├── README.md
│
├── init/                           # Database initialization scripts
│   ├── postgres-main-init.sql      # Banking data schema
│   ├── postgres-audit-init.sql     # Audit log schema
│   └── postgres-embeddings-init.sql # Embeddings schema
│
├── services/                       # All microservices
│   │
│   ├── api_gateway/                # FastAPI gateway
│   │   ├── main.py
│   │   ├── auth.py
│   │   ├── routes.py
│   │   └── requirements.txt
│   │
│   ├── orchestrator/               # Master agent (Claude)
│   │   ├── main.py
│   │   ├── orchestrator_agent.py
│   │   ├── prompts.py              # Master orchestrator prompt
│   │   └── requirements.txt
│   │
│   ├── intent_agent/               # Intent recognition
│   │   ├── main.py
│   │   ├── intent_recognizer.py
│   │   ├── prompts.py
│   │   └── requirements.txt
│   │
│   ├── schema_agent/               # Schema understanding
│   │   ├── main.py
│   │   ├── schema_matcher.py
│   │   ├── category_mapper.py
│   │   ├── prompts.py
│   │   └── requirements.txt
│   │
│   ├── entity_resolution_agent/    # Entity resolution
│   │   ├── main.py
│   │   ├── entity_resolver.py
│   │   ├── semantic_id_correlator.py
│   │   ├── prompts.py
│   │   └── requirements.txt
│   │
│   ├── sql_agent/                  # SQL generation
│   │   ├── main.py
│   │   ├── sql_generator.py
│   │   ├── template_matcher.py
│   │   ├── prompts.py
│   │   └── requirements.txt
│   │
│   ├── validation_agent/           # Query validation
│   │   ├── main.py
│   │   ├── query_validator.py
│   │   ├── ast_parser.py
│   │   ├── query_signer.py
│   │   ├── prompts.py
│   │   └── requirements.txt
│   │
│   ├── execution_agent/            # Query execution
│   │   ├── main.py
│   │   ├── query_executor.py
│   │   ├── access_controller.py
│   │   ├── result_formatter.py
│   │   ├── prompts.py
│   │   └── requirements.txt
│   │
│   ├── audit_agent/                # Audit logging
│   │   ├── main.py
│   │   ├── audit_logger.py
│   │   ├── compliance_recorder.py
│   │   ├── prompts.py
│   │   └── requirements.txt
│   │
│   ├── embedding_service/          # Embedding computation
│   │   ├── main.py
│   │   ├── embedding_computer.py
│   │   ├── schema_embedder.py
│   │   ├── prompts.py
│   │   └── requirements.txt
│   │
│   ├── secrets_manager/            # Credential management
│   │   ├── main.py
│   │   ├── secrets_store.py
│   │   └── requirements.txt
│   │
│   └── shared/                     # Shared utilities
│       ├── __init__.py
│       ├── database.py             # DB connection pooling
│       ├── redis_client.py         # Redis caching
│       ├── logger.py               # Logging utility
│       ├── config.py               # Configuration
│       ├── models.py               # Data models
│       └── errors.py               # Custom exceptions
│
├── frontend/                       # UI (Phase 2+)
│   └── (placeholder for Web UI)
│
├── tests/                          # Test suite
│   ├── test_intent_agent.py
│   ├── test_schema_agent.py
│   ├── test_entity_resolution.py
│   ├── test_sql_generation.py
│   ├── test_validation.py
│   ├── test_execution.py
│   ├── integration_tests.py
│   └── security_tests.py           # SQL injection attempts
│
├── docs/                           # Documentation
│   ├── ARCHITECTURE.md
│   ├── API_DOCUMENTATION.md
│   ├── AGENT_PROMPTS.md
│   ├── DEPLOYMENT.md
│   └── TROUBLESHOOTING.md
│
└── monitoring/                     # Monitoring config (Phase 2)
    └── prometheus.yml
```

---

## WEEK-BY-WEEK EXECUTION PLAN

### WEEK 1: FOUNDATION (Database + Authentication)

**Goal:** Database connectivity, user authentication, audit infrastructure ready

**Days 1-2: Project Setup**
- [ ] Create directory structure
- [ ] Copy docker-compose.yml
- [ ] Create .env file
- [ ] Create init/ SQL scripts
- [ ] Start Docker containers: `docker-compose up -d`
- [ ] Verify all 10 containers running: `docker-compose ps`
- [ ] Test database connections

**Deliverable:** `docker-compose ps` shows all green ✅

**Days 3-4: API Gateway + Authentication**
- [ ] Create services/api_gateway/main.py
- [ ] Implement FastAPI app structure
- [ ] Add authentication endpoint (/auth/login)
- [ ] Implement JWT token generation
- [ ] Add rate limiting
- [ ] Add request validation
- [ ] Create /health endpoint for monitoring

**Code structure:**
```python
# services/api_gateway/main.py
from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter

app = FastAPI()

@app.post("/auth/login")
async def login(username: str, password: str):
    # Authenticate against role repository
    # Return JWT token with user_id, role, permissions
    pass

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

**Deliverable:** API Gateway running on port 8000, can authenticate users

**Days 5-7: Database Abstraction + Audit Logging**
- [ ] Create services/shared/database.py (multi-DB abstraction)
- [ ] Implement DatabaseConnector class
- [ ] Add connection pooling
- [ ] Create services/audit_agent/audit_logger.py
- [ ] Implement write-once audit table
- [ ] Add audit logging to API Gateway
- [ ] Test: Every API call logs to audit_log table

**Code structure:**
```python
# services/shared/database.py
class DatabaseConnector:
    def __init__(self, db_type, credentials):
        self.db_type = db_type  # postgresql, mysql, oracle, sqlserver
        self.connection_pool = self._create_pool()
    
    async def execute_query(self, sql, params):
        # Execute parameterized query
        pass

# services/audit_agent/audit_logger.py
class AuditLogger:
    async def log_access(self, user_id, query, tables_accessed, rows):
        # INSERT into audit_log (immutable)
        pass
```

**Deliverable:** Audit table populated on every action, verified in postgres-audit

**WEEK 1 ACCEPTANCE CRITERIA:**
- ✅ All 10 Docker containers running
- ✅ API Gateway responding on :8000
- ✅ User authentication working (JWT tokens)
- ✅ Audit logging working (entries in postgres-audit)
- ✅ Database abstraction layer functional
- ✅ Rate limiting protecting endpoints

---

### WEEK 2: INTENT + SCHEMA UNDERSTANDING

**Goal:** System understands user queries, recognizes intent, maps to database domains

**Days 1-3: Intent Recognition Agent**
- [ ] Create services/intent_agent/intent_recognizer.py
- [ ] Create services/intent_agent/prompts.py
- [ ] Implement intent extraction (pattern matching, not LLM for cost)
- [ ] Define categories: [customer_analysis, risk_analysis, revenue_analysis, operational_analysis, geographic_analysis, product_analysis, compliance_analysis, transaction_analysis]
- [ ] Create intent classification logic
- [ ] Add confidence scoring
- [ ] Create /process_intent endpoint
- [ ] Test with 20+ example queries

**Code structure:**
```python
# services/intent_agent/intent_recognizer.py
class IntentRecognizer:
    def recognize(self, user_query: str):
        # Pattern matching to extract intent
        # NOT using LLM (cost optimization)
        # Returns: {primary_category, secondary_categories, confidence}
        pass

# services/intent_agent/main.py
@app.post("/process_intent")
async def process_intent(query: str):
    recognizer = IntentRecognizer()
    return recognizer.recognize(query)
```

**Test queries:**
```
"Show me top 10 customers by balance" → customer_analysis (0.99)
"Identify high-risk customers in NY" → risk_analysis + geographic_analysis (0.95)
"Revenue by product line this quarter" → revenue_analysis (0.98)
"Transaction volume by branch" → operational_analysis + geographic_analysis (0.94)
```

**Deliverable:** Intent Agent running on port 8002, correctly classifies 20 test queries

**Days 4-5: Schema Agent + Category Mapping**
- [ ] Create services/schema_agent/schema_matcher.py
- [ ] Create services/schema_agent/category_mapper.py
- [ ] Manually define domain categories (avoid ML for MVP):
  - customers_domain: [customers, customer_segments]
  - accounts_domain: [accounts, account_types]
  - transactions_domain: [transactions, transaction_details]
  - risk_domain: [risk_flags, aml_flags]
  - revenue_domain: [fees, commissions, interest_income]
  - branches_domain: [branches, branch_locations]
  - compliance_domain: [kyc_status, audit_logs]
  - geographic_domain: [regions, branches]
- [ ] Create mapping: category → domains
- [ ] Implement matching logic
- [ ] Test: Intent → Domains mapping works

**Code structure:**
```python
# services/schema_agent/category_mapper.py
INTENT_TO_DOMAINS = {
    "customer_analysis": ["customers_domain", "accounts_domain"],
    "risk_analysis": ["risk_domain", "customers_domain"],
    "revenue_analysis": ["revenue_domain", "accounts_domain"],
    # ... more mappings
}

class SchemaMatcher:
    def match_domains(self, intent_categories: list):
        # Map intent categories to database domains
        domains = set()
        for category in intent_categories:
            domains.update(INTENT_TO_DOMAINS[category])
        return list(domains)
```

**Deliverable:** Schema Agent on port 8003, correctly maps intents to domains

**Days 6-7: Embedding Service Setup** (prep for Week 3)
- [ ] Create services/embedding_service/embedding_computer.py
- [ ] Install sentence-transformers (all-MiniLM-L6-v2)
- [ ] Pre-compute embeddings for:
  - All domain names
  - All table names
  - All column names
  - All semantic entities
- [ ] Store embeddings in postgres-embeddings
- [ ] Create embedding API endpoints
- [ ] Test: Embedding similarity search works

**Code structure:**
```python
# services/embedding_service/embedding_computer.py
from sentence_transformers import SentenceTransformer

class EmbeddingComputer:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def compute_embedding(self, text: str):
        return self.model.encode(text)
    
    def precompute_schema_embeddings(self):
        # Embed all tables, columns, domains
        # Store in postgres-embeddings
        pass
```

**Deliverable:** Embedding Service on port 8009, embeddings stored in postgres-embeddings

**WEEK 2 ACCEPTANCE CRITERIA:**
- ✅ Intent Agent correctly classifies 20+ test queries (90%+ accuracy)
- ✅ Schema Agent maps intents to domains correctly
- ✅ Embedding Service running, embeddings computed and stored
- ✅ Integration test: Intent → Domains → Schema Subset works
- ✅ Both agents responding to HTTP requests

---

### WEEK 3: SQL GENERATION + VALIDATION

**Goal:** Generate safe SQL queries, validate before execution

**Days 1-3: Entity Resolution Agent**
- [ ] Create services/entity_resolution_agent/entity_resolver.py
- [ ] Create services/entity_resolution_agent/semantic_id_correlator.py
- [ ] Implement semantic join detection:
  - Primary entity identification
  - Find all tables containing entity's ID
  - Build join structure using semantic IDs
- [ ] Use vector correlation: if embeddings identical → same entity
- [ ] Create endpoint /resolve_entities
- [ ] Test: Correctly identifies join paths

**Code structure:**
```python
# services/entity_resolution_agent/entity_resolver.py
class EntityResolver:
    def resolve(self, primary_entity: str, schema_subset: dict):
        # Find all tables containing primary_entity's ID
        # Build join structure
        # Return: {primary_key, join_paths}
        
        join_paths = [
            {"from": "customers", "to": "accounts", "on": "customer_id"},
            {"from": "accounts", "to": "transactions", "on": "account_id"}
        ]
        return {
            "primary_entity": "customer",
            "primary_key": "customer_id",
            "join_paths": join_paths
        }
```

**Deliverable:** Entity Resolution Agent on port 8004, correctly finds join paths

**Days 4-5: SQL Generation Agent**
- [ ] Create services/sql_agent/sql_generator.py
- [ ] Create services/sql_agent/template_matcher.py
- [ ] Implement SQL generation:
  - Use join paths from Entity Resolution Agent
  - Generate parameterized SELECT queries
  - Add WHERE filters, GROUP BY if needed
  - Add LIMIT (10000 max)
  - Use ? placeholders (NO string interpolation)
- [ ] Create endpoint /generate_sql
- [ ] Test: Generates valid SQL for 15+ scenarios

**Code structure:**
```python
# services/sql_agent/sql_generator.py
class SQLGenerator:
    def generate(self, intent, schema_subset, join_paths, filters):
        # Build SELECT clause
        # Add FROM clause
        # Add JOINs using join_paths
        # Add WHERE clause
        # Add GROUP BY, ORDER BY
        # Add LIMIT 10000
        # Return: {sql: "SELECT...", parameters: [...]}
        
        sql = """
        SELECT c.*, COUNT(t.id) as transaction_count
        FROM customers c
        LEFT JOIN accounts a ON c.customer_id = a.customer_id
        LEFT JOIN transactions t ON a.account_id = t.account_id
        WHERE c.risk_score > ?
        GROUP BY c.customer_id
        ORDER BY transaction_count DESC
        LIMIT ?
        """
        
        parameters = [
            {"name": "risk_threshold", "value": "user_provided"},
            {"name": "limit", "value": 10000}
        ]
        
        return {"sql": sql, "parameters": parameters}
```

**Deliverable:** SQL Agent on port 8005, generates safe parameterized SQL

**Days 6-7: Validation Agent**
- [ ] Create services/validation_agent/query_validator.py
- [ ] Create services/validation_agent/ast_parser.py
- [ ] Create services/validation_agent/query_signer.py
- [ ] Implement validation checks:
  - Syntax validation
  - No dangerous keywords (DELETE, DROP, ALTER)
  - Only SELECT statements
  - No subqueries (for MVP)
  - Performance estimation
- [ ] Implement query signing (HMAC)
- [ ] Create endpoint /validate_query
- [ ] Test: Rejects 20+ SQL injection attempts

**Code structure:**
```python
# services/validation_agent/query_validator.py
class QueryValidator:
    def validate(self, sql: str, parameters: list):
        # Check 1: Syntax
        # Check 2: Safety (no DELETE, DROP, etc.)
        # Check 3: Access control
        # Check 4: Performance estimation
        
        if not self._is_safe(sql):
            return {"safe": False, "issue": "SQL injection detected"}
        
        signature = self._sign_query(sql, parameters)
        
        return {
            "safe": True,
            "confidence": 0.98,
            "signature": signature,
            "estimated_rows": 100,
            "estimated_time_ms": 250
        }
    
    def _sign_query(self, sql: str, parameters: list):
        # HMAC signature for verification
        import hmac, hashlib
        message = f"{sql}:{parameters}"
        return hmac.new(b'secret', message.encode(), hashlib.sha256).hexdigest()
```

**SQL Injection Test Cases:**
```
"SELECT * FROM customers; DROP TABLE accounts"  → REJECT
"SELECT * FROM customers WHERE id = 1 OR 1=1"  → REJECT
"SELECT * FROM customers UNION SELECT * FROM employees" → REJECT
"SELECT * FROM customers WHERE id = ?"         → ACCEPT
"SELECT * FROM customers LIMIT ?"              → ACCEPT
```

**Deliverable:** Validation Agent on port 8006, catches all injection attempts

**WEEK 3 ACCEPTANCE CRITERIA:**
- ✅ Entity Resolution Agent correctly finds join paths
- ✅ SQL Agent generates valid parameterized SQL
- ✅ Validation Agent rejects 20+ SQL injection attempts
- ✅ Validation Agent verifies query signatures
- ✅ Integration test: Intent → Schema → Entity Resolution → SQL → Validation works
- ✅ 100% of queries use parameterized format (no string interpolation)

---

### WEEK 4: EXECUTION + RESULTS

**Goal:** Execute queries safely, return results with metadata

**Days 1-3: Execution Agent**
- [ ] Create services/execution_agent/query_executor.py
- [ ] Create services/execution_agent/access_controller.py
- [ ] Implement query execution:
  - Verify signature (prevent tampering)
  - Apply role-based row filters
  - Execute parameterized query
  - Capture execution time
  - Capture actual row count
- [ ] Create endpoint /execute_query
- [ ] Test: Executes 15+ queries successfully

**Code structure:**
```python
# services/execution_agent/query_executor.py
class QueryExecutor:
    async def execute(self, sql: str, parameters: list, 
                     signature: str, user_role: str):
        # Verify signature
        if not self._verify_signature(sql, signature):
            raise SecurityError("Query signature invalid")
        
        # Apply role filters
        filtered_sql = self._apply_role_filters(sql, user_role)
        
        # Execute with timeout
        results = await self._execute_with_timeout(filtered_sql, parameters, 30)
        
        return {
            "status": "success",
            "data": results,
            "metadata": {
                "rows_returned": len(results),
                "execution_time_ms": elapsed_time
            }
        }
    
    def _apply_role_filters(self, sql: str, user_role: str):
        # If analyst → add customer segment filter
        # If manager → add branch filter
        # If compliance → no filter (see all)
        pass
```

**Deliverable:** Execution Agent on port 8007, executes queries with access control

**Days 4-5: Result Formatting + Masking**
- [ ] Create services/execution_agent/result_formatter.py
- [ ] Implement PII masking:
  - SSN: "***-**-1234" (last 4 only)
  - Email: "u***@example.com" (partial)
  - Credit Score: MASKED (if not authorized)
  - Credit Card: "****-****-****-1234" (last 4 only)
- [ ] Implement result formatting:
  - JSON format
  - CSV format (for export)
  - Table format (for display)
- [ ] Add metadata:
  - Rows returned
  - Execution time
  - Data freshness
  - Columns masked
- [ ] Create endpoint /format_results

**Code structure:**
```python
# services/execution_agent/result_formatter.py
class ResultFormatter:
    def format(self, results: list, user_role: str, format_type: str):
        # Apply PII masking
        masked_results = self._mask_pii(results, user_role)
        
        # Format as requested
        if format_type == "json":
            return json.dumps(masked_results)
        elif format_type == "csv":
            return self._to_csv(masked_results)
        elif format_type == "table":
            return self._to_table(masked_results)
    
    def _mask_pii(self, results: list, user_role: str):
        # If analyst: mask credit_score
        # Always: mask SSN, credit cards
        for result in results:
            if "ssn" in result:
                result["ssn"] = f"***-**-{result['ssn'][-4:]}"
            if "credit_score" in result and user_role != "compliance":
                result["credit_score"] = "MASKED"
        return results
```

**Deliverable:** Results properly formatted with PII masking

**Days 6-7: Caching + Performance**
- [ ] Implement Redis caching (services/shared/redis_client.py)
- [ ] Cache duplicate queries (same intent, same parameters)
- [ ] Cache schema information
- [ ] Cache embedding vectors
- [ ] Add query_cache key: hash(sql + parameters)
- [ ] TTL: 1 hour for results, 24 hours for schema
- [ ] Test: Cached queries return instantly

**Code structure:**
```python
# services/shared/redis_client.py
class RedisCache:
    async def get_cached_result(self, query_hash: str):
        return await redis.get(f"query:{query_hash}")
    
    async def cache_result(self, query_hash: str, results: dict, ttl: int = 3600):
        await redis.setex(f"query:{query_hash}", ttl, json.dumps(results))
    
    def query_hash(self, sql: str, parameters: list):
        message = f"{sql}:{json.dumps(parameters)}"
        return hashlib.sha256(message.encode()).hexdigest()
```

**Deliverable:** Query caching working, repeated queries return from cache

**WEEK 4 ACCEPTANCE CRITERIA:**
- ✅ Execution Agent executes 15+ queries successfully
- ✅ Role-based access control enforced
- ✅ PII masked correctly (SSN, credit cards)
- ✅ Results formatted in JSON, CSV, Table
- ✅ Query caching working (repeated queries instant)
- ✅ Metadata (rows, time, freshness) included in response
- ✅ End-to-end test: User query → Result with metadata works

---

### WEEK 5: POLISH + TESTING

**Goal:** Production-ready MVP

**Days 1-2: End-to-End Testing**
- [ ] Create tests/integration_tests.py
- [ ] Test 30+ real banking queries:
  - "Top 10 customers by balance"
  - "High-risk customers in NY"
  - "Revenue by product line"
  - "Transaction volume by branch"
  - "Compliance violations this month"
  - etc.
- [ ] Verify accuracy of results
- [ ] Test with 5+ concurrent users
- [ ] Measure response times

**Deliverable:** 30 integration tests pass, response times <5 seconds

**Days 3-4: Security Testing**
- [ ] Create tests/security_tests.py
- [ ] Test 50+ SQL injection attempts
- [ ] Test unauthorized access (wrong role)
- [ ] Test PII masking (verify SSN masked)
- [ ] Test query signing (detect tampering)
- [ ] Penetration testing (if possible)

**Deliverable:** All 50 security tests pass, zero vulnerabilities found

**Days 5-6: Documentation**
- [ ] Create docs/ARCHITECTURE.md
- [ ] Create docs/API_DOCUMENTATION.md
- [ ] Create docs/DEPLOYMENT.md
- [ ] Create docs/TROUBLESHOOTING.md
- [ ] Create comprehensive README.md

**Deliverable:** Complete documentation for deployment

**Day 7: Demo Preparation**
- [ ] Create demo script (5-10 queries to show system)
- [ ] Practice demo
- [ ] Document any issues found
- [ ] Prepare for Phase 2 features

**Deliverable:** Working demo, ready for stakeholders

**WEEK 5 ACCEPTANCE CRITERIA:**
- ✅ 30 integration tests pass
- ✅ 50 security tests pass
- ✅ 5+ concurrent users handled
- ✅ Response time <5 seconds for all queries
- ✅ Zero SQL injection vulnerabilities
- ✅ Zero unauthorized access possible
- ✅ Complete documentation
- ✅ Demo works smoothly

---

## FINAL MVP CHECKLIST

### Functional Requirements
- ✅ User can query banking data in natural language
- ✅ System understands intent (90%+ accuracy)
- ✅ Results are correct and relevant
- ✅ Response time acceptable (<5 seconds)
- ✅ Ambiguous queries ask for clarification
- ✅ Results returned in JSON, CSV, Table format

### Security Requirements
- ✅ No SQL injection vulnerabilities (tested 50+ cases)
- ✅ Parameterized queries only (no string concatenation)
- ✅ Query signature verification (tampering detected)
- ✅ Role-based access control enforced
- ✅ PII masked in results (SSN, credit cards, etc.)
- ✅ Every access logged and audited

### Infrastructure Requirements
- ✅ All services run in Docker containers
- ✅ All services communicate via HTTP APIs
- ✅ Can start with docker-compose up -d
- ✅ Health checks on all services
- ✅ Logging to console and files
- ✅ Error handling and recovery

### Compliance Requirements
- ✅ Audit log captures all queries
- ✅ Immutable audit table (write-once)
- ✅ User, role, timestamp logged
- ✅ Data freshness indicators
- ✅ Access control audit trail

### Documentation Requirements
- ✅ ARCHITECTURE.md explains all components
- ✅ API_DOCUMENTATION.md lists all endpoints
- ✅ DEPLOYMENT.md explains how to run
- ✅ TROUBLESHOOTING.md for common issues
- ✅ README.md with quick start

---

## PHASE 2 ROADMAP (After MVP)

Once MVP is complete and working:

1. **Insights Agent** (Natural language summaries)
2. **Advanced Schema Categorization** (ML-based classification)
3. **Clarification Agent Improvements** (Better disambiguation)
4. **Frontend UI** (Web interface instead of chat)
5. **Query Templates Library** (Common queries pre-defined)
6. **Multi-Database Support** (Oracle, SQL Server, MySQL)
7. **Compliance Reporting** (GDPR, PCI-DSS)
8. **Mobile App** (Phase 3)
9. **Power BI Integration** (Phase 3)

---

## SUCCESS DEFINITION

MVP is successful when:

1. **User can ask natural language questions and get correct answers** ✅
2. **System is secure (no SQL injection, no unauthorized access)** ✅
3. **System is auditable (full compliance trail)** ✅
4. **System is fast (response time <5 seconds)** ✅
5. **System is reliable (99%+ uptime, graceful errors)** ✅
6. **Analysts are happy (productive, no frustrations)** ✅

---

## Getting Started

```bash
# 1. Clone repository
git clone <repo>
cd banking-intelligence-system

# 2. Create environment file
cp .env.example .env

# 3. Start Docker containers
docker-compose up -d

# 4. Wait for containers to be healthy
docker-compose ps

# 5. Initialize databases
# (Run SQL scripts automatically via init/ directory)

# 6. Run tests
docker-compose exec api-gateway pytest tests/

# 7. Start development
# - Implement Week 1 components
# - Test as you go
# - Commit frequently

# 8. Deploy
# Follow docs/DEPLOYMENT.md
```

---

Good luck. You've got a solid plan. Execute it step by step, test frequently, and ship iteratively.

