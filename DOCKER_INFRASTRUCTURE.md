# Docker Infrastructure for Banking Intelligence Agent System

## Complete docker-compose.yml

```yaml
version: '3.9'

services:
  
  # ============================================================================
  # API GATEWAY & AUTHENTICATION
  # ============================================================================
  
  api-gateway:
    container_name: banking_api_gateway
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./services/api_gateway:/app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://banking_user:securepass123@postgres-main:5432/banking_dev
      - REDIS_URL=redis://redis:6379/0
      - SECRETS_MANAGER=http://secrets-manager:8010
      - LOG_LEVEL=INFO
    depends_on:
      - postgres-main
      - redis
    networks:
      - banking-network
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  # ============================================================================
  # ORCHESTRATOR AGENT (Master Agent)
  # ============================================================================
  
  orchestrator-agent:
    container_name: banking_orchestrator
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./services/orchestrator:/app
    ports:
      - "8001:8001"
    environment:
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
      - DATABASE_URL=postgresql://banking_user:securepass123@postgres-main:5432/banking_dev
      - REDIS_URL=redis://redis:6379/1
      - INTENT_AGENT_URL=http://intent-agent:8002
      - SCHEMA_AGENT_URL=http://schema-agent:8003
      - ENTITY_RESOLUTION_AGENT_URL=http://entity-resolution-agent:8004
      - SQL_AGENT_URL=http://sql-agent:8005
      - VALIDATION_AGENT_URL=http://validation-agent:8006
      - EXECUTION_AGENT_URL=http://execution-agent:8007
      - AUDIT_AGENT_URL=http://audit-agent:8008
      - LOG_LEVEL=INFO
    depends_on:
      - postgres-main
      - redis
    networks:
      - banking-network
    command: python main.py

  # ============================================================================
  # MICROSERVICE AGENTS
  # ============================================================================
  
  intent-agent:
    container_name: banking_intent_agent
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./services/intent_agent:/app
    ports:
      - "8002:8002"
    environment:
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
      - LOG_LEVEL=INFO
    networks:
      - banking-network
    command: python main.py

  schema-agent:
    container_name: banking_schema_agent
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./services/schema_agent:/app
    ports:
      - "8003:8003"
    environment:
      - EMBEDDING_SERVICE_URL=http://embedding-service:8009
      - REDIS_URL=redis://redis:6379/2
      - LOG_LEVEL=INFO
    depends_on:
      - embedding-service
      - redis
    networks:
      - banking-network
    command: python main.py

  entity-resolution-agent:
    container_name: banking_entity_resolution
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./services/entity_resolution_agent:/app
    ports:
      - "8004:8004"
    environment:
      - EMBEDDING_SERVICE_URL=http://embedding-service:8009
      - POSTGRES_EMBEDDINGS_URL=postgresql://embedding_user:securepass123@postgres-embeddings:5432/embeddings
      - REDIS_URL=redis://redis:6379/3
      - LOG_LEVEL=INFO
    depends_on:
      - postgres-embeddings
      - embedding-service
      - redis
    networks:
      - banking-network
    command: python main.py

  sql-agent:
    container_name: banking_sql_agent
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./services/sql_agent:/app
    ports:
      - "8005:8005"
    environment:
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
      - REDIS_URL=redis://redis:6379/4
      - LOG_LEVEL=INFO
    depends_on:
      - redis
    networks:
      - banking-network
    command: python main.py

  validation-agent:
    container_name: banking_validation_agent
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./services/validation_agent:/app
    ports:
      - "8006:8006"
    environment:
      - LOG_LEVEL=INFO
    networks:
      - banking-network
    command: python main.py

  execution-agent:
    container_name: banking_execution_agent
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./services/execution_agent:/app
    ports:
      - "8007:8007"
    environment:
      - DATABASE_URL=postgresql://banking_user:securepass123@postgres-main:5432/banking_dev
      - AUDIT_SERVICE_URL=http://audit-agent:8008
      - LOG_LEVEL=INFO
    depends_on:
      - postgres-main
    networks:
      - banking-network
    command: python main.py

  audit-agent:
    container_name: banking_audit_agent
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./services/audit_agent:/app
    ports:
      - "8008:8008"
    environment:
      - AUDIT_DATABASE_URL=postgresql://audit_user:securepass123@postgres-audit:5432/audit_logs
      - LOG_LEVEL=INFO
    depends_on:
      - postgres-audit
    networks:
      - banking-network
    command: python main.py

  # ============================================================================
  # SUPPORTING SERVICES
  # ============================================================================
  
  embedding-service:
    container_name: banking_embedding_service
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./services/embedding_service:/app
    ports:
      - "8009:8009"
    environment:
      - POSTGRES_EMBEDDINGS_URL=postgresql://embedding_user:securepass123@postgres-embeddings:5432/embeddings
      - LOG_LEVEL=INFO
    depends_on:
      - postgres-embeddings
    networks:
      - banking-network
    command: python main.py

  secrets-manager:
    container_name: banking_secrets
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./services/secrets_manager:/app
      - banking_secrets_volume:/secrets
    ports:
      - "8010:8010"
    environment:
      - LOG_LEVEL=INFO
    networks:
      - banking-network
    command: python main.py

  # ============================================================================
  # DATABASES
  # ============================================================================
  
  postgres-main:
    container_name: banking_postgres_main
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: banking_dev
      POSTGRES_USER: banking_user
      POSTGRES_PASSWORD: securepass123
    ports:
      - "5432:5432"
    volumes:
      - postgres_main_data:/var/lib/postgresql/data
      - ./init/postgres-main-init.sql:/docker-entrypoint-initdb.d/01-init.sql
    networks:
      - banking-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U banking_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  postgres-audit:
    container_name: banking_postgres_audit
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: audit_logs
      POSTGRES_USER: audit_user
      POSTGRES_PASSWORD: securepass123
    ports:
      - "5433:5432"
    volumes:
      - postgres_audit_data:/var/lib/postgresql/data
      - ./init/postgres-audit-init.sql:/docker-entrypoint-initdb.d/01-init.sql
    networks:
      - banking-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U audit_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  postgres-embeddings:
    container_name: banking_postgres_embeddings
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: embeddings
      POSTGRES_USER: embedding_user
      POSTGRES_PASSWORD: securepass123
    ports:
      - "5434:5432"
    volumes:
      - postgres_embeddings_data:/var/lib/postgresql/data
      - ./init/postgres-embeddings-init.sql:/docker-entrypoint-initdb.d/01-init.sql
    networks:
      - banking-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U embedding_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ============================================================================
  # CACHING & SESSIONS
  # ============================================================================
  
  redis:
    container_name: banking_redis
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - banking-network
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ============================================================================
  # LOCAL LLM (FALLBACK)
  # ============================================================================
  
  ollama:
    container_name: banking_ollama
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - banking-network
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
    command: serve
    # Note: Pull model on startup
    # docker exec banking_ollama ollama pull mistral

  # ============================================================================
  # MONITORING & LOGGING (Optional for Phase 2)
  # ============================================================================
  
  # prometheus:
  #   container_name: banking_prometheus
  #   image: prom/prometheus:latest
  #   ports:
  #     - "9090:9090"
  #   volumes:
  #     - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
  #     - prometheus_data:/prometheus
  #   networks:
  #     - banking-network
  #   command: --config.file=/etc/prometheus/prometheus.yml

volumes:
  postgres_main_data:
  postgres_audit_data:
  postgres_embeddings_data:
  redis_data:
  ollama_data:
  banking_secrets_volume:

networks:
  banking-network:
    driver: bridge
```

---

## Database Initialization Scripts

### init/postgres-main-init.sql

```sql
-- Banking Main Database Schema

-- Customers Table
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    kyc_verified BOOLEAN DEFAULT FALSE,
    risk_score DECIMAL(3,2),
    segment VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_customer_id (customer_id),
    INDEX idx_kyc (kyc_verified),
    INDEX idx_segment (segment)
);

-- Accounts Table
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(50) UNIQUE NOT NULL,
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    account_type VARCHAR(50),
    status VARCHAR(20),
    balance DECIMAL(15,2),
    available_balance DECIMAL(15,2),
    currency VARCHAR(3) DEFAULT 'USD',
    branch_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_account_id (account_id),
    INDEX idx_customer_id (customer_id),
    INDEX idx_status (status)
);

-- Transactions Table
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id VARCHAR(50) UNIQUE NOT NULL,
    account_id VARCHAR(50) NOT NULL REFERENCES accounts(account_id),
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    amount DECIMAL(15,2),
    transaction_type VARCHAR(50),
    status VARCHAR(20),
    transaction_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_transaction_id (transaction_id),
    INDEX idx_account_id (account_id),
    INDEX idx_customer_id (customer_id),
    INDEX idx_date (transaction_date)
);

-- Risk Flags Table
CREATE TABLE risk_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    flag_type VARCHAR(50),
    severity VARCHAR(20),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_customer_id (customer_id),
    INDEX idx_severity (severity)
);

-- Branches Table
CREATE TABLE branches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255),
    state VARCHAR(50),
    city VARCHAR(100),
    manager_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_branch_id (branch_id),
    INDEX idx_state (state)
);

-- Products Table
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255),
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product_id (product_id)
);

-- Create indexes
CREATE INDEX idx_customers_created ON customers(created_at);
CREATE INDEX idx_accounts_created ON accounts(created_at);
CREATE INDEX idx_transactions_created ON transactions(created_at);
```

### init/postgres-audit-init.sql

```sql
-- Audit Log Database (Write-Once, Immutable)

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id VARCHAR(100) UNIQUE NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(100) NOT NULL,
    user_role VARCHAR(50) NOT NULL,
    query_intent VARCHAR(255),
    tables_accessed TEXT,
    rows_accessed INTEGER,
    execution_time_ms INTEGER,
    status VARCHAR(20),
    ip_address VARCHAR(50),
    query_signature VARCHAR(255),
    data_freshness VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Constraints: Write-once (no updates, no deletes)
    INDEX idx_timestamp (timestamp),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status)
);

-- Enforce immutability (no updates, no deletes)
CREATE RULE audit_log_no_update AS
    ON UPDATE TO audit_log DO INSTEAD NOTHING;

CREATE RULE audit_log_no_delete AS
    ON DELETE TO audit_log DO INSTEAD NOTHING;

-- Grant limited permissions
GRANT INSERT ON audit_log TO audit_user;
GRANT SELECT ON audit_log TO banking_user;
```

### init/postgres-embeddings-init.sql

```sql
-- Embeddings Database (pgvector)

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Table Schema Embeddings
CREATE TABLE schema_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50),  -- 'table', 'column', 'domain', 'entity'
    entity_name VARCHAR(255),
    embedding vector(384),  -- Using all-MiniLM-L6-v2 model (384 dims)
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_entity_type (entity_type),
    INDEX idx_embedding USING ivfflat (embedding vector_cosine_ops)
);

-- Domain Categories
CREATE TABLE domain_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    tables TEXT[],
    embedding vector(384),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_domain_name (domain_name)
);

-- Semantic ID Mappings
CREATE TABLE semantic_id_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    semantic_entity VARCHAR(100),  -- 'customer', 'account', 'transaction'
    table_name VARCHAR(100),
    column_name VARCHAR(100),
    id_embedding vector(384),
    confidence DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(semantic_entity, table_name, column_name),
    INDEX idx_semantic_entity (semantic_entity)
);
```

---

## Environment Configuration

### .env (Create this file)

```bash
# Claude API
CLAUDE_API_KEY=sk-your-api-key-here

# Database Credentials
POSTGRES_MAIN_USER=banking_user
POSTGRES_MAIN_PASSWORD=securepass123
POSTGRES_AUDIT_USER=audit_user
POSTGRES_AUDIT_PASSWORD=securepass123
POSTGRES_EMBEDDINGS_USER=embedding_user
POSTGRES_EMBEDDINGS_PASSWORD=securepass123

# Service URLs (internal)
API_GATEWAY_URL=http://api-gateway:8000
ORCHESTRATOR_URL=http://orchestrator-agent:8001
INTENT_AGENT_URL=http://intent-agent:8002
SCHEMA_AGENT_URL=http://schema-agent:8003
ENTITY_RESOLUTION_AGENT_URL=http://entity-resolution-agent:8004
SQL_AGENT_URL=http://sql-agent:8005
VALIDATION_AGENT_URL=http://validation-agent:8006
EXECUTION_AGENT_URL=http://execution-agent:8007
AUDIT_AGENT_URL=http://audit-agent:8008
EMBEDDING_SERVICE_URL=http://embedding-service:8009

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# Logging
LOG_LEVEL=INFO

# Feature Flags (for Phase 2)
ENABLE_INSIGHTS_AGENT=false
ENABLE_ADVANCED_ML=false
ENABLE_CACHING=true
```

---

## Docker Commands

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs for specific service
docker-compose logs -f orchestrator-agent

# Pull Ollama model (if using local LLM)
docker exec banking_ollama ollama pull mistral

# Stop all services
docker-compose down

# Clean up (delete volumes)
docker-compose down -v

# Rebuild after code changes
docker-compose up -d --build
```

---

## Health Checks

```bash
# Test API Gateway
curl http://localhost:8000/health

# Test Intent Agent
curl http://localhost:8002/health

# Test PostgreSQL
docker exec banking_postgres_main psql -U banking_user -d banking_dev -c "SELECT 1"

# Test Redis
docker exec banking_redis redis-cli ping

# Test Ollama
curl http://localhost:11434/api/tags
```

---

## Next Steps

1. Create directory structure
2. Copy docker-compose.yml to project root
3. Create .env file
4. Create init/ directory and SQL files
5. Create services/ directories for each microservice
6. Run: `docker-compose up -d`
7. Verify all containers are running: `docker-compose ps`
8. Begin implementing individual agent services

