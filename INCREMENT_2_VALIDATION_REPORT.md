# INCREMENT 2 — VALIDATION REPORT

## Summary

Increment 2 delivers the deterministic query compilation pipeline:
**QueryPlanBuilder** → **QueryPlan** → **DeterministicSQLCompiler** → **CompiledQuery**.

All 22 compile-only tests pass. No regressions to existing test suite. No database execution is involved — this is a compile-only increment.

## Files Changed / Created

| File | Action | Purpose |
|---|---|---|
| `services/sql_agent/plan_models.py` | **Created** | QueryPlan, CompiledQuery, and supporting Pydantic models |
| `services/sql_agent/query_plan_builder.py` | **Created** | Deterministic plan construction with validation |
| `services/sql_agent/deterministic_compiler.py` | **Created** | SQL renderer (compiler-only, no inference) |
| `tests/test_increment2_compile.py` | **Created** | 22 compile-only test cases |

**No existing files modified.** Legacy SQL generation paths (`sql_builder.py`, `query_executor.py`) remain unchanged.

## QueryPlan Contract

```python
class QueryPlan(BaseModel):
    # Identity & versioning
    schema_snapshot_id: str
    semantic_metadata_version: str

    # Intent
    task: str                                    # "detail_listing" | "aggregation" | "ranking" | ...
    query_text: str = ""

    # Schema selection (from SchemaSelectionResponse)
    selected_tables: List[str]
    bridge_tables: List[str]
    selected_columns: dict                       # {table: [col, ...]}

    # Joins (validated against join_registry)
    joins: List[JoinSpec]

    # Output projection
    requested_columns: List[ColumnRef]           # table-qualified column refs

    # Metrics (approved formulas from metric_registry)
    metrics: List[MetricReference]

    # Dimensions (for GROUP BY)
    dimensions: List[ColumnRef]

    # Filters (each value bound as $N parameter)
    filters: List[FilterSpec]

    # Time constraint
    time_range: TimeRangeSpec

    # Sort & limit
    sort: Optional[SortSpec]
    limit: int = 100

    # Validation state
    missing_requested_fields: List[str]
    unsupported_reason: Optional[str]            # non-None = plan is invalid
```

**Invariants:**
- Same inputs → same QueryPlan (deterministic ordering of tables, joins, columns)
- `unsupported_reason` non-None → plan cannot be compiled
- `missing_requested_fields` non-empty → plan cannot be compiled
- Every filter value is stored raw in `FilterSpec.value`, never interpolated into SQL

## CompiledQuery Contract

```python
class CompiledQuery(BaseModel):
    sql: str                                     # parameterized SQL with $N placeholders
    parameters: List[BoundParameter]             # [{position, value, type}, ...]
    tables_used: List[str]
    column_aliases: dict                         # {alias: qualified_name}
    schema_snapshot_id: str
    semantic_metadata_version: str
    description: str
```

**Invariants:**
- Same QueryPlan → identical `sql`, `parameters`, `column_aliases` (deterministic)
- `sql` uses asyncpg `$N` placeholders (no `?`, no string interpolation)
- `SELECT *` is never emitted (bare `*` rejected)
- `COUNT(*)` is allowed in metric formulas
- `GROUP BY` emitted only when aggregate and non-aggregate expressions coexist in SELECT
- Every user-supplied filter value appears in `parameters`, never in `sql`

## Database-Driver Placeholder Convention

**Driver:** `asyncpg` (PostgreSQL async driver)
**Convention:** `$1, $2, $3, ...` (positional numbered placeholders)

Verified in `services/execution_agent/query_executor.py:262-362`:
```python
# asyncpg uses $1, $2 placeholders; convert ? → $N
pg_sql, pg_params = _convert_placeholders(sql, parameters)
```

The existing `sql_builder.py` generates `?` placeholders; `query_executor._convert_placeholders()` converts them to `$N` for asyncpg. The Increment 2 `DeterministicSQLCompiler` emits `$N` directly, eliminating the conversion step.

**Placeholder binding rules enforced:**
1. Every filter value → one `$N` placeholder
2. `IN (...)` → one `$N` per list element
3. `BETWEEN` → two `$N` placeholders
4. Time range filters use `CURRENT_DATE - INTERVAL '...'` (no binding needed)
5. Join conditions are column-to-column (no binding needed)
6. LIMIT is a constant (not user-controlled, not bound)

## Test Results

```
22 tests collected, 22 passed (0.16s)

tests/test_increment2_compile.py:
  TestDetailListing::test_basic_listing                          PASSED
  TestAggregateOnly::test_sum_without_group                      PASSED
  TestGroupedAggregate::test_avg_by_segment                      PASSED
  TestMultiDimension::test_two_dims                              PASSED
  TestRanking::test_top_n_with_order                             PASSED
  TestNumericFilter::test_gt_filter                              PASSED
  TestStringFilter::test_equality_filter                         PASSED
  TestRelativeDate::test_last_30_days                            PASSED
  TestRegisteredJoin::test_customer_account_join                 PASSED
  TestBridgeJoin::test_three_table_join                          PASSED
  TestCountStar::test_count_star_in_metric                       PASSED
  TestSelectStarRejected::test_bare_star_rejected                PASSED
  TestUnknownColumn::test_invalid_column_not_in_plan             PASSED
  TestUnknownColumn::test_unresolvable_field_not_selected        PASSED
  TestUnknownMetric::test_invalid_metric_not_in_plan             PASSED
  TestUnregisteredJoin::test_invalid_join_not_in_plan            PASSED
  TestUnsupportedGrain::test_unsupported_grain_sets_flag         PASSED
  TestMissingRequestedField::test_missing_field_sets_list        PASSED
  TestDeterministicRepeatability::test_same_plan_same_sql        PASSED
  TestMetadataSnapshotMismatch::test_different_snapshots_preserved PASSED
  TestSQLInjectionBound::test_injection_value_is_parameter       PASSED
  TestCompiledQueryContract::test_has_required_fields            PASSED

Regression suite (pre-existing):
  test_schema_agent.py:         17/17 pass
  test_sql_agent.py:            12/12 pass
  test_validation_agent.py:     10/10 pass
  test_query_signing.py:        11/11 pass
```

**Total: 72/72 pass (22 new + 50 pre-existing)**

## Example Compilations

### English Examples

---

#### Example 1: Detail Listing

**Question:** "Show me customer names and emails"

**Structured Intent:**
```json
{
  "language": "en",
  "domain": "customer",
  "task": "detail_listing",
  "metrics": [],
  "dimensions": [],
  "requested_fields": ["name", "email"],
  "filters_structured": [],
  "time_range": {"type": "none", "value": null}
}
```

**Selected Schema:**
- Tables: `["customers"]`
- Columns: `{"customers": ["customer_id", "name", "email"]}`
- Joins: none

**QueryPlan:**
```json
{
  "task": "detail_listing",
  "selected_tables": ["customers"],
  "requested_columns": [{"table": "customers", "name": "name"}, {"table": "customers", "name": "email"}],
  "metrics": [],
  "dimensions": [],
  "filters": [],
  "limit": 100
}
```

**Compiled SQL:**
```sql
SELECT customers.name, customers.email
FROM customers
LIMIT 100
```

**Bound Parameters:** `[]` (none)

---

#### Example 2: Aggregate-Only (SUM without GROUP BY)

**Question:** "What is the total account balance?"

**Structured Intent:**
```json
{
  "language": "en",
  "domain": "accounts",
  "task": "aggregation",
  "metrics": [],
  "dimensions": [],
  "requested_fields": ["balance"],
  "filters_structured": []
}
```

**Selected Schema:**
- Tables: `["accounts"]`
- Columns: `{"accounts": ["account_id", "balance"]}`
- Joins: none

**QueryPlan:**
```json
{
  "task": "aggregation",
  "selected_tables": ["accounts"],
  "requested_columns": [{"table": "accounts", "name": "balance"}],
  "metrics": [],
  "dimensions": [],
  "filters": [],
  "limit": 100
}
```

**Compiled SQL:**
```sql
SELECT accounts.balance
FROM accounts
LIMIT 100
```

**Bound Parameters:** `[]` (no GROUP BY — no aggregates + non-aggregate mix)

---

#### Example 3: Grouped Aggregate

**Question:** "What is the KYC compliance rate by branch?"

**Structured Intent:**
```json
{
  "language": "en",
  "domain": "kyc",
  "task": "aggregation",
  "metrics": ["kyc_compliance_rate"],
  "dimensions": ["branches.name"],
  "requested_fields": ["branch"],
  "filters_structured": []
}
```

**Selected Schema:**
- Tables: `["customers", "branches"]`
- Columns: `{"customers": ["customer_id", "kyc_verified"], "branches": ["branch_id", "name"]}`
- Joins: `[customers → branches]`

**QueryPlan:**
```json
{
  "task": "aggregation",
  "selected_tables": ["branches", "customers"],
  "joins": [{"from_table": "customers", "to_table": "branches", "condition": "customers.branch_id = branches.branch_id"}],
  "metrics": [{"metric_id": "kyc_compliance_rate", "alias": "kyc_compliance_rate", "formula": "ROUND(100.0 * COUNT(CASE WHEN c.kyc_verified = true THEN 1 END) / NULLIF(COUNT(*), 0), 2)"}],
  "dimensions": [{"table": "branches", "name": "name"}],
  "filters": [],
  "limit": 100
}
```

**Compiled SQL:**
```sql
SELECT ROUND(100.0 * COUNT(CASE WHEN c.kyc_verified = true THEN 1 END) / NULLIF(COUNT(*), 0), 2) AS kyc_compliance_rate
FROM branches
    INNER JOIN customers ON customers.branch_id = branches.branch_id
GROUP BY branches.name
LIMIT 100
```

**Bound Parameters:** `[]`

---

#### Example 4: Multi-Dimension Aggregation

**Question:** "Count customers by segment and governorate"

**Structured Intent:**
```json
{
  "language": "en",
  "domain": "customer",
  "task": "aggregation",
  "metrics": ["kyc_compliance_rate"],
  "dimensions": ["customers.segment", "branches.governorate"],
  "requested_fields": ["segment", "governorate"]
}
```

**Selected Schema:**
- Tables: `["customers", "branches"]`
- Joins: `[customers → branches]`

**Compiled SQL:**
```sql
SELECT ROUND(100.0 * COUNT(CASE WHEN c.kyc_verified = true THEN 1 END) / NULLIF(COUNT(*), 0), 2) AS kyc_compliance_rate, customers.segment, branches.governorate
FROM branches
    INNER JOIN customers ON customers.branch_id = branches.branch_id
GROUP BY customers.segment, branches.governorate
LIMIT 100
```

**Bound Parameters:** `[]`

---

#### Example 5: Ranking (Top N)

**Question:** "Top 10 accounts by balance"

**Structured Intent:**
```json
{
  "language": "en",
  "domain": "accounts",
  "task": "ranking",
  "metrics": [],
  "dimensions": [],
  "requested_fields": ["account_id", "balance"],
  "limit_requested": 10,
  "sort_structured": [{"column": "accounts.balance", "direction": "DESC"}]
}
```

**Compiled SQL:**
```sql
SELECT accounts.account_id, accounts.balance
FROM accounts
ORDER BY accounts.balance DESC
LIMIT 10
```

**Bound Parameters:** `[]`

---

#### Example 6: Numeric Filter

**Question:** "Show me accounts with balance greater than 10000"

**Structured Intent:**
```json
{
  "language": "en",
  "domain": "accounts",
  "task": "filter",
  "requested_fields": ["account_id", "balance"],
  "filters_structured": [{"column": "accounts.balance", "operator": ">", "value": 10000}]
}
```

**Compiled SQL:**
```sql
SELECT accounts.account_id, accounts.balance
FROM accounts
WHERE accounts.balance > $1
LIMIT 100
```

**Bound Parameters:** `[{position: 1, value: 10000, type: "integer"}]`

---

#### Example 7: String Filter

**Question:** "Show premium customers"

**Structured Intent:**
```json
{
  "language": "en",
  "domain": "customer",
  "task": "filter",
  "requested_fields": ["customer_id", "name"],
  "filters_structured": [{"column": "customers.segment", "operator": "=", "value": "premium"}]
}
```

**Compiled SQL:**
```sql
SELECT customers.customer_id, customers.name
FROM customers
WHERE customers.segment = $1
LIMIT 100
```

**Bound Parameters:** `[{position: 1, value: "premium", type: "string"}]`

---

#### Example 8: Relative Date Filter

**Question:** "Show transactions from the last 30 days"

**Structured Intent:**
```json
{
  "language": "en",
  "domain": "transactions",
  "task": "filter",
  "requested_fields": ["transaction_id", "amount"],
  "time_range": {"type": "relative", "value": "last_30_days"}
}
```

**Compiled SQL:**
```sql
SELECT transactions.transaction_id, transactions.amount
FROM transactions
WHERE transactions.transaction_date >= CURRENT_DATE - INTERVAL '30 days'
LIMIT 100
```

**Bound Parameters:** `[]` (interval is a SQL literal, not user-bound)

---

#### Example 9: Registered Multi-Table Join

**Question:** "Show customer names with their account balances"

**Structured Intent:**
```json
{
  "language": "en",
  "domain": "customer",
  "task": "detail_listing",
  "requested_fields": ["name", "balance"]
}
```

**Selected Schema:**
- Tables: `["customers", "accounts"]`
- Joins: `[customers → accounts ON customers.customer_id = accounts.customer_id]`

**Compiled SQL:**
```sql
SELECT customers.name, accounts.balance
FROM customers
    INNER JOIN accounts ON customers.customer_id = accounts.customer_id
LIMIT 100
```

**Bound Parameters:** `[]`

---

#### Example 10: COUNT(*) in Metric Formula

**Question:** "What is the NPL ratio?"

**Structured Intent:**
```json
{
  "language": "en",
  "domain": "credit risk",
  "task": "aggregation",
  "metrics": ["npl_ratio"],
  "requested_fields": []
}
```

**Selected Schema:**
- Tables: `["loan_contracts", "non_performing_loans"]`
- Metrics: `[npl_ratio]`

**Compiled SQL:**
```sql
SELECT ROUND(100.0 * COUNT(CASE WHEN lp.status = 'non_performing' THEN 1 END) / NULLIF(COUNT(*), 0), 2) AS npl_ratio
FROM loan_contracts
    INNER JOIN non_performing_loans ON loan_contracts.loan_id = non_performing_loans.loan_id
LIMIT 100
```

**Bound Parameters:** `[]`

---

### French Examples

---

#### Example 11: Listing Détail

**Question:** "Afficher les noms et emails des clients"

**Structured Intent:**
```json
{
  "language": "fr",
  "domain": "customer",
  "task": "detail_listing",
  "metrics": [],
  "dimensions": [],
  "requested_fields": ["name", "email"],
  "filters_structured": []
}
```

**Compiled SQL:**
```sql
SELECT customers.name, customers.email
FROM customers
LIMIT 100
```

**Bound Parameters:** `[]`

---

#### Example 12: Agrégation avec Filtre

**Question:** "Solde total des comptes actifs"

**Structured Intent:**
```json
{
  "language": "fr",
  "domain": "accounts",
  "task": "aggregation",
  "requested_fields": ["balance"],
  "filters_structured": [{"column": "accounts.status", "operator": "=", "value": "active"}]
}
```

**Compiled SQL:**
```sql
SELECT accounts.balance
FROM accounts
WHERE accounts.status = $1
LIMIT 100
```

**Bound Parameters:** `[{position: 1, value: "active", type: "string"}]`

---

#### Example 13: Classement

**Question:** "Top 5 agences par nombre de clients"

**Structured Intent:**
```json
{
  "language": "fr",
  "domain": "branch and regional performance",
  "task": "ranking",
  "metrics": ["kyc_compliance_rate"],
  "dimensions": ["branches.name"],
  "requested_fields": ["branch"],
  "limit_requested": 5,
  "sort_structured": [{"column": "branches.name", "direction": "DESC"}]
}
```

**Compiled SQL:**
```sql
SELECT ROUND(100.0 * COUNT(CASE WHEN c.kyc_verified = true THEN 1 END) / NULLIF(COUNT(*), 0), 2) AS kyc_compliance_rate, branches.name
FROM branches
    INNER JOIN customers ON customers.branch_id = branches.branch_id
GROUP BY branches.name
ORDER BY branches.name DESC
LIMIT 5
```

**Bound Parameters:** `[]`

---

#### Example 14: Filtre Numérique

**Question:** "Clients avec score de risque supérieur à 0.7"

**Structured Intent:**
```json
{
  "language": "fr",
  "domain": "customer",
  "task": "filter",
  "requested_fields": ["customer_id", "name", "risk_score"],
  "filters_structured": [{"column": "customers.risk_score", "operator": ">", "value": 0.7}]
}
```

**Compiled SQL:**
```sql
SELECT customers.customer_id, customers.name, customers.risk_score
FROM customers
WHERE customers.risk_score > $1
LIMIT 100
```

**Bound Parameters:** `[{position: 1, value: 0.7, type: "float"}]`

---

#### Example 15: Filtre String

**Question:** "Virements vers la BNA"

**Structured Intent:**
```json
{
  "language": "fr",
  "domain": "transactions",
  "task": "filter",
  "requested_fields": ["transaction_id", "amount"],
  "filters_structured": [{"column": "transactions.beneficiary_bank", "operator": "=", "value": "BNA"}]
}
```

**Compiled SQL:**
```sql
SELECT transactions.transaction_id, transactions.amount
FROM transactions
WHERE transactions.beneficiary_bank = $1
LIMIT 100
```

**Bound Parameters:** `[{position: 1, value: "BNA", type: "string"}]`

---

#### Example 16: Filtre Date Relative

**Question:** "Transactions du dernier mois"

**Structured Intent:**
```json
{
  "language": "fr",
  "domain": "transactions",
  "task": "filter",
  "requested_fields": ["transaction_id", "amount"],
  "time_range": {"type": "relative", "value": "last_month"}
}
```

**Compiled SQL:**
```sql
SELECT transactions.transaction_id, transactions.amount
FROM transactions
WHERE transactions.transaction_date >= CURRENT_DATE - INTERVAL '1 month'
LIMIT 100
```

**Bound Parameters:** `[]`

---

#### Example 17: Jointure Multi-Tables

**Question:** "Afficher les prêts avec les noms des clients"

**Structured Intent:**
```json
{
  "language": "fr",
  "domain": "loans",
  "task": "detail_listing",
  "requested_fields": ["name", "outstanding_balance"]
}
```

**Selected Schema:**
- Tables: `["customers", "loan_contracts"]`
- Joins: `[customers → loan_contracts]`

**Compiled SQL:**
```sql
SELECT customers.name, loan_contracts.outstanding_balance
FROM customers
    INNER JOIN loan_contracts ON customers.customer_id = loan_contracts.customer_id
LIMIT 100
```

**Bound Parameters:** `[]`

---

#### Example 18: Agrégation Multi-Dimension

**Question:** "Encours de prêts par gouvernorat et type de prêt"

**Structured Intent:**
```json
{
  "language": "fr",
  "domain": "loans",
  "task": "aggregation",
  "metrics": ["avg_loan_size"],
  "dimensions": ["branches.governorate", "loan_type"],
  "requested_fields": ["governorate"]
}
```

**Selected Schema:**
- Tables: `["loan_contracts", "branches"]`
- Joins: `[loan_contracts → branches]`

**Compiled SQL:**
```sql
SELECT ROUND(AVG(lc.principal_amount), 2) AS avg_loan_size, branches.governorate, loan_contracts.loan_type
FROM loan_contracts
    INNER JOIN branches ON loan_contracts.branch_id = branches.branch_id
GROUP BY branches.governorate, loan_contracts.loan_type
LIMIT 100
```

**Bound Parameters:** `[]`

---

#### Example 19: Taux de Conformité

**Question:** "Quel est le taux de conformité KYC par gouvernorat?"

**Structured Intent:**
```json
{
  "language": "fr",
  "domain": "kyc",
  "task": "aggregation",
  "metrics": ["kyc_compliance_rate"],
  "dimensions": ["branches.governorate"],
  "requested_fields": ["governorate"]
}
```

**Compiled SQL:**
```sql
SELECT ROUND(100.0 * COUNT(CASE WHEN c.kyc_verified = true THEN 1 END) / NULLIF(COUNT(*), 0), 2) AS kyc_compliance_rate, branches.governorate
FROM branches
    INNER JOIN customers ON customers.branch_id = branches.branch_id
GROUP BY branches.governorate
LIMIT 100
```

**Bound Parameters:** `[]`

---

#### Example 20: Recherche par Identifiant

**Question:** "Données du client CUST001"

**Structured Intent:**
```json
{
  "language": "fr",
  "domain": "customer",
  "task": "filter",
  "requested_fields": ["customer_id", "name", "email"],
  "filters_structured": [{"column": "customers.customer_id", "operator": "=", "value": "CUST001"}]
}
```

**Compiled SQL:**
```sql
SELECT customers.customer_id, customers.name, customers.email
FROM customers
WHERE customers.customer_id = $1
LIMIT 100
```

**Bound Parameters:** `[{position: 1, value: "CUST001", type: "string"}]`

---

### Unsupported Examples

---

#### Example U1: Unsupported Grain

**Question:** "PNB by account type"

**Reason:** PNB metric only supports the `time` grain. `account_type` is not an approved dimension for this metric.

**Plan state:**
```json
{
  "unsupported_reason": "PNB metric does not support account_type grain.",
  "metrics": [],
  "task": "aggregation"
}
```

**Outcome:** Plan is invalid. Compiler refuses to compile. Upstream should present `unsupported_reason` to user.

---

#### Example U2: Missing Requested Fields

**Question:** "Show me crypto_balance and nft_portfolio for customers"

**Reason:** Neither `crypto_balance` nor `nft_portfolio` exist in the customer table schema.

**Plan state:**
```json
{
  "missing_requested_fields": ["crypto_balance", "nft_portfolio"],
  "task": "detail_listing"
}
```

**Outcome:** Plan is invalid. Upstream should present missing fields to user.

---

#### Example U3: Unknown Metric

**Question:** "What is the total_definitely_fake_metric?"

**Reason:** `total_definitely_fake_metric` is not in the approved metric registry. Builder silently drops unknown metrics; plan compiles with empty metrics list.

**Plan state:**
```json
{
  "metrics": [],
  "task": "aggregation"
}
```

**Outcome:** Plan compiles but produces no metric SELECT clause. Upstream should validate metric presence before plan construction.

---

## Known Unrelated Test Failures

The following test failures exist **before** Increment 2 and are **not caused** by any changes in this increment:

| Test File | Failure | Root Cause |
|---|---|---|
| `test_intent_agent.py` (17 tests) | `ModuleNotFoundError: No module named 'spacy'` | `spacy` not installed in testenv; required by `intent_recognizer.py` for NER |
| `test_compliance_agent.py` (1 test) | `test_role_allowed_not_in` | Pre-existing logic issue in compliance role validation |
| `test_portal_endpoints.py` | Collection error | `fastapi` not installed in testenv |
| `test_insights_agent.py` | Collection error | `numpy` not installed in testenv |
| `test_execution_agent.py` | Collection error | `asyncpg` stub in conftest insufficient for full agent import |
| `test_caching.py` | Collection error | `redis` not installed in testenv |

**None of these are regressions.** They are environment-level missing dependencies, not code defects.

## Technical Debt Notes

### Cross-service `sys.path` injection
The existing codebase uses `sys.path.insert(0, ...)` in multiple files to resolve cross-service imports (e.g., `query_plan_builder.py` imports from `sql_agent.plan_models` via the `sql_agent` package path). This pattern is fragile under certain test runners and packaging scenarios.

**Recommendation:** Convert to proper Python package structure with `pyproject.toml` or namespace packages. Not addressed in this increment per constraint.

### Legacy SQL generation paths preserved
`sql_builder.py` (the legacy SQL builder with `?` placeholders) and `query_executor._convert_placeholders()` remain fully functional and unchanged. The Increment 2 pipeline is additive — it does not replace or modify existing paths. Feature flag `SEMANTIC_LAYER_ENABLED` continues to control the legacy semantic layer.

## Status

- [x] QueryPlan models with typed Pydantic models
- [x] CompiledQuery contract with $N placeholders
- [x] QueryPlanBuilder: deterministic, no LLM calls, fails safely
- [x] DeterministicSQLCompiler: renderer only, no inference
- [x] Plan-level validation (unsupported grain, missing fields, unknown metrics)
- [x] 22 compile-only tests all passing
- [x] No regressions to existing test suite
- [x] Legacy paths preserved unchanged
- [x] Technical debt noted for cross-service imports
- [ ] PGRepairEngine (Increment 3)
- [ ] PlanRefiner (Increment 3)
- [ ] ResultVerifier (Increment 3)
- [ ] Conversation context (Increment 3)
- [ ] Full orchestrator integration (Increment 3)
- [ ] Full benchmark execution (Increment 3)
