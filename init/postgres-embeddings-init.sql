-- =============================================================================
-- Embeddings Database (pgvector)
-- postgres-embeddings: embeddings
-- =============================================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Table Schema Embeddings
-- Stores vector embeddings for table/column names, domains, entities
CREATE TABLE IF NOT EXISTS schema_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL,   -- 'table', 'column', 'domain', 'entity'
    entity_name VARCHAR(255) NOT NULL,
    embedding vector(384),              -- all-MiniLM-L6-v2 model (384 dims)
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_schema_embeddings_entity_type ON schema_embeddings(entity_type);
CREATE INDEX IF NOT EXISTS idx_schema_embeddings_entity_name ON schema_embeddings(entity_name);
-- Vector similarity index (IVFFlat for cosine similarity)
CREATE INDEX IF NOT EXISTS idx_schema_embeddings_vector
    ON schema_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Domain Categories
-- Pre-defined domain → table mappings used by Schema Agent
CREATE TABLE IF NOT EXISTS domain_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    tables TEXT[],                      -- array of table names in this domain
    embedding vector(384),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_domain_categories_domain_name ON domain_categories(domain_name);

-- Semantic ID Mappings
-- Maps semantic entities (customer, account) to actual DB columns
CREATE TABLE IF NOT EXISTS semantic_id_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    semantic_entity VARCHAR(100) NOT NULL, -- 'customer', 'account', 'transaction'
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100) NOT NULL,
    id_embedding vector(384),
    confidence DECIMAL(3,2) DEFAULT 1.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(semantic_entity, table_name, column_name)
);

CREATE INDEX IF NOT EXISTS idx_semantic_id_mappings_entity ON semantic_id_mappings(semantic_entity);
CREATE INDEX IF NOT EXISTS idx_semantic_id_mappings_table ON semantic_id_mappings(table_name);

-- =============================================================================
-- Seed: Pre-defined domain categories (used by Schema Agent without embeddings)
-- =============================================================================
INSERT INTO domain_categories (domain_name, description, tables) VALUES
    ('customers_domain',    'Customer profiles, segments, KYC data',           ARRAY['customers']),
    ('accounts_domain',     'Bank accounts, balances, account types',           ARRAY['accounts']),
    ('transactions_domain', 'Payment transactions, transfers, transaction history', ARRAY['transactions']),
    ('risk_domain',         'Risk flags, AML alerts, fraud detection',          ARRAY['risk_flags']),
    ('branches_domain',     'Branch locations, branch performance, managers',   ARRAY['branches']),
    ('products_domain',     'Banking products, categories, offerings',          ARRAY['products']),
    ('geographic_domain',   'Geographic analysis, states, cities, regions',     ARRAY['branches', 'customers']),
    ('compliance_domain',   'Compliance, KYC status, audit trail',              ARRAY['risk_flags', 'customers'])
ON CONFLICT (domain_name) DO NOTHING;

-- Seed: Semantic ID mappings (which column = which entity key)
INSERT INTO semantic_id_mappings (semantic_entity, table_name, column_name, confidence) VALUES
    ('customer', 'customers',    'customer_id', 1.00),
    ('customer', 'accounts',     'customer_id', 1.00),
    ('customer', 'transactions', 'customer_id', 1.00),
    ('customer', 'risk_flags',   'customer_id', 1.00),
    ('account',  'accounts',     'account_id',  1.00),
    ('account',  'transactions', 'account_id',  1.00),
    ('branch',   'branches',     'branch_id',   1.00),
    ('branch',   'accounts',     'branch_id',   0.95),
    ('product',  'products',     'product_id',  1.00)
ON CONFLICT (semantic_entity, table_name, column_name) DO NOTHING;
