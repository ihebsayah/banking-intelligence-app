# Week 3: Query Generation & Safety

## Overview
Week 3 establishes the query translation and security layer of the banking intelligence system. It handles semantic entity resolution, safe parameterized SQL generation, and strict AST-based query validation with HMAC signing to block SQL injections and ensure complete data security.

## Services Built

### 1. Entity Resolution Agent (`services/entity_resolution_agent/`)
- **Port:** `8004`
- **Purpose:** Find semantic join paths using business-key correlation instead of simple structural table IDs.
- **Key Technologies:** `FastAPI`, `Pydantic`.
- **Features:** 
  - Maps natural language entities to canonical PK columns (e.g., `customer` -> `customer_id`).
  - Identifies which target tables contain the entity's foreign keys.
  - Dynamically builds precise inner join conditions between the primary table and target tables.
  - Exposes an automated `/test_resolution` endpoint handling 10 distinct entity relationship cases.

### 2. SQL Generation Agent (`services/sql_agent/`)
- **Port:** `8005`
- **Purpose:** Generate robust, fully parameterized SQL queries from intent, entities, and join paths.
- **Key Technologies:** `FastAPI`, `Pydantic`.
- **Features:** 
  - Generates strictly parameterized queries (using `?` placeholders) to eliminate string concatenation vulnerabilities.
  - Validates all requested columns against a hardcoded whitelist of allowed schema columns per table.
  - Automatically appends a `LIMIT` clause (default 100, max 10,000) to protect database resources.
  - Processes complex SQL components including `WHERE` conditions, `JOIN`s, `GROUP BY` aggregations, and `ORDER BY`.

### 3. Validation Agent (`services/validation_agent/`)
- **Port:** `8006`
- **Purpose:** Perform AST-level safety checks to detect/block SQL injection attacks, and apply cryptographic signing to verified queries.
- **Key Technologies:** `FastAPI`, `sqlparse`, `hmac` (SHA-256).
- **Features:** 
  - Executes a strict 5-check validation pipeline: verifies syntax, ensures `SELECT`-only operations, rejects dangerous keywords (`DROP`, `DELETE`, etc.), enforces `LIMIT` clauses, and scans for suspicious injection regex patterns.
  - Blocks 22+ real SQL injection attack vectors, including `UNION SELECT`, `OR 1=1`, stacked queries, time-based blind attacks (`SLEEP`, `BENCHMARK`), hex/encoding bypasses, and nested subquery abuse.
  - Signs approved queries using an HMAC-SHA256 signature to prevent downstream tampering.
  - Includes a pure-Python string parsing fallback for scenarios where `sqlparse` is unavailable.
  - Validates queries robustly against an internal `/test_injections` attack suite.

## Example Flow
User Query: `"Find all accounts for customer 123 where balance is greater than 1000"`

1. **Entity Resolution Agent:**
   - Resolves `customer` to `customer_id` and maps to tables `customers` and `accounts`.
   - Constructs Join Path: `INNER JOIN accounts ON customers.customer_id = accounts.customer_id`.
2. **SQL Generation Agent:**
   - Validates columns (`customer_id`, `balance`) against whitelists.
   - Generates Parameterized SQL: `SELECT customers.customer_id, accounts.balance FROM customers INNER JOIN accounts ON customers.customer_id = accounts.customer_id WHERE customers.customer_id = ? AND accounts.balance > ? LIMIT 100`.
   - Returns parameters: `[123, 1000]`.
3. **Validation Agent:**
   - Parses AST and confirms it's a `SELECT`-only query with a `LIMIT` clause.
   - Confirms no dangerous keywords or suspicious patterns exist.
   - Signs the payload (SQL string + parameters array) with an HMAC signature.

## Current Status
- ✅ Code implementation complete for all three agents.
- ✅ Local `uvicorn` startup configured accurately in `docker-compose.yml`.
- ✅ Complete in-process test runner developed (`tests/week3_local_test.py`) mapping 100% of acceptance criteria without needing a Docker daemon.
- ✅ Comprehensive tests passing successfully (Entity: 10/10, SQL: 5/5, Validation: 22/22 injection blocks, Good Queries: 4/4).
- ✅ Tagged in git as `v0.3-week3`.
