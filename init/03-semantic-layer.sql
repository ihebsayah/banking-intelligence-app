-- =============================================================================
-- Phase 6A: Semantic Layer Schema
-- init/03-semantic-layer.sql
-- =============================================================================

-- 1. Business Glossary Table
CREATE TABLE IF NOT EXISTS business_glossary (
    term_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term              VARCHAR(100) UNIQUE NOT NULL,   -- "NPL", "ROE", "Encours"
    definition        TEXT NOT NULL,
    synonyms          TEXT[],                          -- ["créances classées", "bad loans", "NPL"]
    domain            VARCHAR(50),
    business_owner    VARCHAR(100),
    source_tables     TEXT[],
    formula           TEXT,
    example           TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_glossary_term ON business_glossary(term);
CREATE INDEX IF NOT EXISTS idx_glossary_domain ON business_glossary(domain);

-- 2. Metric Registry Table
CREATE TABLE IF NOT EXISTS metric_registry (
    metric_id         VARCHAR(50) PRIMARY KEY,
    metric_name_fr    VARCHAR(200),
    metric_name_en    VARCHAR(200),
    formula           TEXT NOT NULL,
    description       TEXT,
    domain            VARCHAR(50),
    owner             VARCHAR(100),
    source_tables     TEXT[],
    dependencies      TEXT[],                          -- other metric_ids
    unit              VARCHAR(20),                     -- %, TND, count, ratio
    refresh_frequency VARCHAR(20),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_metrics_domain ON metric_registry(domain);

-- 3. Table Metadata Table
CREATE TABLE IF NOT EXISTS table_metadata (
    table_name        VARCHAR(100) PRIMARY KEY,
    business_description TEXT,
    domain            VARCHAR(50),
    owner             VARCHAR(100),
    row_count_estimate INTEGER,
    is_analytical     BOOLEAN DEFAULT FALSE,            -- snapshot vs operational
    is_pii_bearing    BOOLEAN DEFAULT FALSE,
    refresh_frequency VARCHAR(20),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_table_metadata_domain ON table_metadata(domain);

-- 4. Column Metadata Table
CREATE TABLE IF NOT EXISTS column_metadata (
    metadata_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name        VARCHAR(100) NOT NULL,
    column_name       VARCHAR(100) NOT NULL,
    business_description TEXT,
    synonyms          TEXT[],
    data_type         VARCHAR(50),
    is_pii            BOOLEAN DEFAULT FALSE,
    example_values    TEXT[],
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_name, column_name)
);

CREATE INDEX IF NOT EXISTS idx_column_metadata_lookup ON column_metadata(table_name, column_name);

-- 5. Join Registry Table
CREATE TABLE IF NOT EXISTS join_registry (
    join_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table      VARCHAR(100) NOT NULL,
    source_column     VARCHAR(100) NOT NULL,
    target_table      VARCHAR(100) NOT NULL,
    target_column     VARCHAR(100) NOT NULL,
    relationship_type VARCHAR(20),                     -- one_to_many, many_to_one, one_to_one
    join_type         VARCHAR(20) DEFAULT 'LEFT JOIN',
    confidence        DECIMAL(3,2) DEFAULT 1.00,
    notes             TEXT,
    is_bidirectional  BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_table, source_column, target_table, target_column)
);

CREATE INDEX IF NOT EXISTS idx_join_registry_lookup ON join_registry(source_table, target_table);
