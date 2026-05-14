# Week 2: Intelligence Layer

## Overview
Week 2 establishes the intelligence layer of the banking system, enabling it to understand user intent and map natural language queries to database domains and tables without relying entirely on LLMs for core routing logic.

## Services Built

### 1. Intent Recognition Agent (`services/intent_agent/`)
- **Port:** `8002`
- **Purpose:** Extract user intent from natural language queries using pattern matching and NLP.
- **Key Technologies:** `spaCy` (tokenisation/lemmatisation), `FastAPI`, `Redis` (caching).
- **Features:** 
  - Classifies queries into 8 distinct categories (e.g., `customer_analysis`, `risk_analysis`, `revenue_analysis`).
  - Extracts explicit constraints (time period, geography, segment, thresholds).
  - Detects ambiguities requiring clarification.
  - Contains a 20-case `pytest` suite for verification.

### 2. Embedding Service (`services/embedding_service/`)
- **Port:** `8009`
- **Purpose:** Pre-compute and serve vector embeddings for semantic matching.
- **Key Technologies:** `sentence-transformers` (`all-MiniLM-L6-v2`), `asyncpg`, `FastAPI`.
- **Features:** 
  - Computes 384-dimensional embeddings.
  - Pre-computes and seeds embeddings for all schema domains, tables, and entities into the `postgres-embeddings` database on startup.
  - Provides a `/embed` endpoint for real-time text embedding.

### 3. Schema Understanding Agent (`services/schema_agent/`)
- **Port:** `8003`
- **Purpose:** Map user intent categories directly to the corresponding database schema structure.
- **Key Technologies:** `FastAPI`.
- **Features:** 
  - Uses static mapping (MVP) to resolve intent categories to database domains.
  - Resolves domains to specific physical tables.
  - Generates simple JOIN paths between primary entities (e.g., `customers` to `accounts` via `LEFT JOIN`).
  - Identifies relevant filtering columns.

## Example Flow
User Query: `"Show me top 10 customers by balance"`

1. **Intent Agent:**
   - Intent: `customer_analysis`
   - Constraints: `{"threshold": "top_10"}`
2. **Schema Agent:**
   - Domains: `customer_analysis`, `account_analysis`
   - Tables: `customers`, `accounts`, `customer_segments`
   - Join Path: `customers` `LEFT JOIN` `accounts` ON `customer_id`

## Current Status
- ✅ Code implementation complete.
- ✅ Services added to `docker-compose.yml`.
- ⚠️ Local testing constrained by lack of internet access within the build environment (prevented `pip install` and `docker daemon` access).
- ✅ Tagged as `v0.2-week2`.
