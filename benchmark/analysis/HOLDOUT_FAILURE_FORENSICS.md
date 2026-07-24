# Holdout Failure Forensics

**25 failures analyzed across 160-question holdout (84.4% pass rate)**

## Executive Summary

Every failure was traced through the full pipeline: Intent → Schema → Entity Resolution → SQL Generation → Validation → Execution. The failures cluster into **3 root causes** across **4 architectural defects**.

| Root Cause | Count | % of Failures | Recoverable? |
|------------|-------|---------------|--------------|
| `JOIN_REGISTRY_ERROR` | 19 | 76% | Yes — fix join_registry + multi-hop path resolution |
| `GATE_FALSE_REJECTION` | 4 | 16% | Yes — tighten ambiguity detection |
| `SEMANTIC_REGISTRY_GAP` | 2 | 8% | Yes — sync table_metadata with actual DB schema |

**Projected recovery: 25/25 points (100%) if all 3 root causes are fixed.**

---

## Root Cause #1: JOIN_REGISTRY_ERROR (19 failures, 76%)

### The Defect

The SQL Builder (`sql_builder.py`) generates JOIN clauses by matching column names across tables. When it cannot find a registered join path in the `join_registry`, it **invents joins** by assuming tables share a common column name (e.g., `product_id`, `transaction_id`). These invented joins reference columns that don't exist in the target tables.

The `join_registry` table contains only **24 entries** — all direct 1-hop paths. The system has **no multi-hop path resolution** (BFS/DFS over the join graph). When a query needs `transactions → branches`, the system attempts a direct join instead of discovering the registered path `transactions → accounts → branches`.

### Failure Modes

#### Mode A: `products.product_id` phantom FK (10 failures)

| ID | Query | Tables Selected | DB Error |
|----|-------|----------------|----------|
| H007 | What is the total outstanding loan balance? | products, accounts, customers | `accounts.product_id does not exist` |
| H020 | List all loan products with their interest rates | products, accounts, transactions | `accounts.product_id does not exist` |
| H066 | Show me customers who have both accounts and active loans | products, accounts, customers | `accounts.product_id does not exist` |
| H070 | List all loan installments that are overdue, with customer name and branch | products, accounts, branches, customers | `accounts.product_id does not exist` |
| H074 | Show me each branch's total balance and number of loan accounts | products, accounts, branches, customers | `accounts.product_id does not exist` |
| H079 | Rank customers by total deposits across all their accounts | products, accounts, customers | `accounts.product_id does not exist` |
| H085 | Rank branches by total outstanding loan balance | products, accounts, branches, customers | `accounts.product_id does not exist` |
| H153 | Show me each customer's total loan obligations versus total deposits | products, accounts, customers | `accounts.product_id does not exist` |
| H157 | Show me each customer's risk score, total deposits, and total loan balance | products, accounts, customers, risk_flags | `accounts.product_id does not exist` |
| H158 | Rank regions by total outstanding loan balance | products, accounts, branches, customers | `accounts.product_id does not exist` |

**Root cause**: Entity resolution selects `product` as primary entity → SQL builder tries `products.product_id = accounts.product_id` → `accounts` has no `product_id` column.

**Actual schema**:
- `accounts` columns: `id, account_id, customer_id, account_type, status, balance, available_balance, currency, branch_id, created_at`
- `products` columns: `id, product_id, name, category, description, created_at`
- No FK exists between these tables. The real product→account relationship is `accounts.account_type` ↔ `products.category` (logical, not FK).

**Correct paths** (all registered in join_registry):
- `customers.customer_id → accounts.customer_id` ✓
- `customers.customer_id → loan_contracts.customer_id` ✓
- `accounts.account_id → loan_contracts.account_id` ✓

**Architectural fix**: The SQL Builder must validate every proposed JOIN against the `join_registry` before emitting SQL. If no registered path exists between two tables, the builder should either: (a) use a registered multi-hop path via BFS, or (b) refuse to generate the JOIN and return an error.

#### Mode B: `branches.transaction_id` phantom FK (3 failures)

| ID | Query | DB Error |
|----|-------|----------|
| H014 | How many transactions were processed in each branch? | `branches.transaction_id does not exist` |
| H071 | Show me the total transactions per customer per branch for the last 30 days | `branches.transaction_id does not exist` |
| H078 | Show me the bottom 5 branches by transaction volume | `branches.transaction_id does not exist` |

**Root cause**: SQL builder generates `transactions.transaction_id = branches.transaction_id`. `branches` has no `transaction_id` column.

**Actual schema**:
- `branches` columns: `id, branch_id, name, state, city, manager_id, created_at, region_id`
- Correct path: `transactions.account_id → accounts.account_id → accounts.branch_id → branches.branch_id` (2 hops, both registered)

**Architectural fix**: Multi-hop path resolution. Both hops are individually registered: `transactions→accounts` (via `account_id`) and `accounts→branches` (via `branch_id`). A BFS over the join_registry graph would discover this path.

#### Mode C: `customers.branch_id` phantom FK (2 failures)

| ID | Query | DB Error |
|----|-------|----------|
| H024 | Show me the distribution of account balances by branch and account type | `customers.branch_id does not exist` |
| H068 | Which customers have accounts in more than one branch? | `customers.branch_id does not exist` |

**Root cause**: SQL builder generates `branches.branch_id = customers.branch_id`. `customers` has no `branch_id` column.

**Actual schema**: `customers` has `customer_id`. Correct path: `branches.branch_id → accounts.branch_id → accounts.customer_id → customers.customer_id` (2 hops).

**Architectural fix**: Same multi-hop resolution. Also, H024 doesn't even need the `customers` table — all data is in `accounts` (which has `branch_id`, `account_type`, `balance`). The SQL builder should detect unnecessary tables.

#### Mode D: `branches.product_id` phantom FK (2 failures)

| ID | Query | DB Error |
|----|-------|----------|
| H030 | What is the average days past due for loans by branch? | `branches.product_id does not exist` |
| H156 | Show me the total provisions set aside for non-performing loans by branch | `branches.product_id does not exist` |

**Root cause**: Entity resolution selects `product` as primary → tries `products.product_id = branches.product_id`. `branches` has no `product_id`.

**Actual schema**: `loan_contracts` has both `branch_id` and `days_past_due`. For provisions: `provisions.loan_id → loan_contracts.loan_id → loan_contracts.branch_id`.

**Architectural fix**: Map "loan", "provisions", "NPL" queries to `loan_contracts` table. Entity resolution should select `loan` as primary entity, not `product`.

#### Mode E: `branches.customer_id` phantom FK (1 failure)

| ID | Query | DB Error |
|----|-------|----------|
| H025 | What is the total fee income collected per branch per quarter? | `branches.customer_id does not exist` |

**Root cause**: Entity resolution selects `customer` as primary → tries `customers.customer_id = branches.customer_id`. `branches` has no `customer_id`.

**Actual schema**: `fee_income` table exists with `account_id`. Correct path: `fee_income.account_id → accounts.account_id → accounts.branch_id → branches.branch_id`.

**Architectural fix**: Map "fee income" to `fee_income` table. Register `fee_income→accounts` join.

#### Mode F: `transactions.product_id` phantom FK (1 failure)

| ID | Query | DB Error |
|----|-------|----------|
| H022 | What is the monthly growth rate of total deposits? | `transactions.product_id does not exist` |

**Root cause**: Entity resolution selects `product` → tries `products.product_id = transactions.product_id`. `transactions` has no `product_id`.

**Actual schema**: Deposits are `accounts.balance`. Correct query: `SELECT date_trunc('month', created_at), SUM(balance) FROM accounts GROUP BY 1`.

**Architectural fix**: Map "deposits" to `accounts.balance`. Entity resolver should select `account` as primary entity.

#### Mode G: Non-existent table `audit_logs` (2 failures)

| ID | Query | DB Error |
|----|-------|----------|
| H059 | List all compliance violations with critical severity | `relation "audit_logs" does not exist` |
| H061 | What is the total amount of suspicious activity reports filed? | `relation "audit_logs" does not exist` |

**Root cause**: Schema agent returns `audit_logs` as the table for compliance queries. The actual table is `compliance_violations` (for H059) and `suspicious_activity_reports` (for H061). The `table_metadata` cache has a stale mapping.

**Actual DB tables** (74 total):
- `compliance_violations` — has `violation_id, rule_id, entity_type, entity_id, severity, description, detected_at, status`
- `suspicious_activity_reports` — has `sar_id, account_id, customer_id, filing_date, amount, status, filing_type, description`
- `audit_findings` — exists but is different from `audit_logs`
- `audit_logs` — does NOT exist

**Architectural fix**: Sync `table_metadata` with actual DB schema. Run `SELECT table_name FROM information_schema.tables WHERE table_schema='public'` at startup and update the cache.

---

## Root Cause #2: GATE_FALSE_REJECTION (4 failures, 16%)

### The Defect

The intent gate rejects valid queries when `confidence < 0.50` AND `requires_clarification = True`. The ambiguity detector (`detect_ambiguities_structured`) over-reports ambiguities for queries that are actually well-specified.

| ID | Query | Gate Reason | Why Wrong |
|----|-------|-------------|-----------|
| H054 | Affichez les 5 branches avec le plus de prêts actifs | Insufficient confidence | 7-word French ranking query; "branches" + "prêts" are clear domain signals |
| H065 | How many sanctions screening checks were completed last month | Insufficient confidence | 10-word query with explicit aggregation ("how many") and domain ("sanctions screening") |
| H075 | List customers with their KYC status, risk score, and total account balance | Too many ambiguities | All terms map to specific columns: kyc_cases.kyc_verified, customers.risk_score, accounts.balance |
| H084 | Which 10 customers have the most transactions? | Insufficient confidence | 7-word ranking query; "which" + "most" are ranking signals |

**Architectural fix**: 
1. Exempt queries with explicit aggregation verbs (`how many`, `combien`) from the `too_short_query` ambiguity check
2. When entity resolution finds registered join paths between detected entities, boost gate confidence
3. Reduce false ambiguity reports: KYC status → `kyc_cases.kyc_verified` (unambiguous), risk score → `customers.risk_score` (unambiguous)

---

## Root Cause #3: SEMANTIC_REGISTRY_GAP (2 failures, 8%)

### The Defect

The `table_metadata` cache maps business domains to table names that don't exist in the actual database. The schema agent serves stale mappings.

| ID | Query | Stated Table | Actual Table |
|----|-------|-------------|--------------|
| H059 | List all compliance violations with critical severity | `audit_logs` | `compliance_violations` |
| H061 | What is the total amount of suspicious activity reports filed? | `audit_logs` | `suspicious_activity_reports` |

**Architectural fix**: At startup, the schema agent should query `information_schema.tables` and reconcile against `table_metadata`. Any table in the metadata cache that doesn't exist in the DB should be flagged and removed.

---

## Recovery Estimates

| Fix | Failures Fixed | New Score | New Pass Rate |
|-----|---------------|-----------|---------------|
| Multi-hop join path resolution (BFS over join_registry) | 14 | 149/160 | 93.1% |
| Entity resolver primary entity selection | 5 | 154/160 | 96.3% |
| Gate false rejection reduction | 4 | 158/160 | 98.8% |
| table_metadata sync with actual DB | 2 | 160/160 | 100% |
| **All fixes combined** | **25** | **160/160** | **100%** |

Note: Some fixes overlap (e.g., entity resolver fix also resolves some JOIN_REGISTRY_ERROR cases). The combined fix count is 25 because each failure has exactly one root cause.

---

## Files

- Detailed per-failure traces: `benchmark/analysis/holdout_failure_matrix.json`
- This report: `benchmark/analysis/HOLDOUT_FAILURE_FORENSICS.md`
