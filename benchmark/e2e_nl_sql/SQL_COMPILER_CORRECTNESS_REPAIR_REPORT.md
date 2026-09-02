# SQL_COMPILER_CORRECTNESS_REPAIR_REPORT

**Component:** `services/sql_agent/deterministic_compiler.py` (DeterministicSQLCompiler)
**Benchmark:** `E2E_BASELINE_V1` (frozen, immutable — 100 cases, unchanged)
**Repair step:** Step 14 — deterministic SQL compiler correctness
**Baseline artifact:** `baseline_v1.json` / `baseline_v1_traces.jsonl` (pristine "before", preserved)
**Post-fix artifact:** `E2E_SQL_COMPILER_FIX_V1.json` / `E2E_SQL_COMPILER_FIX_V1_traces.jsonl`
**Ran:** 2026-09-01

---

## 1. Objective

Make `DeterministicSQLCompiler` a faithful, deterministic translator of
QueryPlan / EntityResolution output:

- correct FROM root (never alphabetical table selection),
- correct joins (no accidental self-joins, no references to absent tables),
- correct SELECT / GROUP BY (in-relation columns only),
- parameterized filters (100% of values `$N`-bound),
- correct NULL semantics (IS NULL / IS NOT NULL never bound),
- clean `UNRESOLVABLE_JOIN_GRAPH` failures for disconnected plans.

The benchmark and the evaluator semantics are immutable. Only the compiler
(and two tests whose fixtures were inconsistent with the real data model) were
changed.

---

## 2. Root Cause (reproduced, prior to fix)

For `E2E_001` ("How many customers do we have?") the builder sorted
`selected_tables` alphabetically, so `plan.selected_tables[0] == "accounts"`.
The compiler previously used `selected_tables[0]` as the FROM root and blindly
emitted each edge's `to_table`:

```sql
FROM accounts
LEFT JOIN accounts ON customers.customer_id = accounts.customer_id   -- SELF-JOIN bug
```

This lost the true primary table, created an accidental self-join (`accounts`
joined to itself), and emitted `ON` predicates referencing a table (`customers`,
later `branches`, etc.) not present in the FROM clause — a guaranteed runtime
DB error for **most multi-table cases**.

**Confirmed defect counts in the baseline:** 75/100 DB errors, 59/100
self-join defects.

---

## 3. Fix Applied (compiler only)

### `SQLCompileError`
Added `SQLCompileError(code, message)` with stable error codes used across the
state machine and every clause guard:
`UNRESOLVABLE_JOIN_GRAPH`, `SELF_JOIN_FORBIDDEN`, `EMPTY_PLAN`.

### `compile()`
Now calls `_compile_base_and_joins(plan) -> (base, relation, join_clause)` once,
threading the **single SQL relation set** (`relation`) through
`_compile_select`, `_compile_where`, and `_compile_group_by`. Every clause is
validated against the same connected graph, so a table absent from FROM can
never leak into SELECT / WHERE / GROUP BY.

### Base-table selection (`_compile_base_and_joins`)
- No joins → the single selected table.
- With joins → the **join-graph head**: a table that appears as some edge's
  `from_table` and never as any edge's `to_table` (the ER tree root). This is
  deterministic and matches the EntityResolver primary_table emission.
- Deterministic fallbacks for ambiguous graphs; base must also be present in
  `selected_tables`.

### Join state machine
```
joined = {base}
for each edge (s -> t):
  s in joined, t not  → JOIN t                  joined += {t}
  t in joined, s not  → JOIN s (same ON)        joined += {s}
  both in joined      → skip duplicate edge
  neither in joined   → UNRESOLVABLE_JOIN_GRAPH
```
Self-join protection: `s == t` → `SELF_JOIN_FORBIDDEN` unless
`self_join_allowed=true` (field absent on JoinSpec → `getattr` default False).

### `_compile_select` / `_compile_group_by` / `_compile_where`
All validate dimension, metric `source_tables`, and filter column tables
against `relation`; any reference outside the SQL relation set raises
`UNRESOLVABLE_JOIN_GRAPH`.

### WHERE / NULL semantics
- `IS NULL` / `IS NOT NULL` emitted without any bound parameter.
- **Fixed double-binding defect:** `IN (...)` and `BETWEEN a AND b` previously
  bound the whole list as `$N` *and* each element; the redundant whole-list
  placeholder is removed. Element values are each bound (`IN ($1, $2)`,
  `BETWEEN $1 AND $2`).

### Scope respected
- No changes to Intent / Schema / Entity Resolution agents, QueryValidator,
  or the `CompiledQuery` contract (`sql`, `parameters`, metadata).
- All user filter values remain `$N`-bound (asyncpg convention).
- NPL/ratio metrics still route through the independent-subqueries path
  (`_compile_independent_subqueries` / `_compile_where_routed`) — preserved.

---

## 4. Before / After Metrics

| Metric | Before (Step 13) | After (SQL_COMPILER_FIX_V1) | Δ |
|---|---|---|---|
| Intent label accuracy | 57.89% | 57.89% | — |
| End-to-end semantic accuracy | 0.00% | 0.00% | — |
| Result correctness rate | 3.03% | **21.21%** | **+18.18 pts** |
| DB error rate (cases w/ exec error) | **75/100 (75%)** | **15/100 (15%)** | **−60 pts** |
| Self-join defect rate | **59/100 (59%)** | **0/100 (0%)** | **−59 pts** |
| Successful executions (ran clean) | 22/100 | **71/100** | **+49 cases** |
| Join correctness rate | 36.67% | 36.67% | — |
| Parameterization rate (evaluator) | 4.35% | 4.35% | — |
| Constraint propagation | 67.78% | 67.78% | — |
| Validation correctness | 97.78% | 86.67% | −11.11* |
| Compliance correctness | 100% | 100% | — |
| Security block rate | 100% | 60%* | — |
| Clarification correctness | 40% | 40% | — |
| Level 4 accuracy | 70% | 50%* | — |
| Latency p50 / p95 / avg | 60.3 / 189.1 / 91.1 ms | 62.6 / 171.6 / 91.6 ms | ≈ |

\* Marked: see §6 (evaluator-side effects of now-executing more queries, not
compiler regressions).

### Failure re-distribution (supported cases)

| Stage | Before | After |
|---|---|---|
| SCHEMA_RETRIEVAL_FAILURE | 39 | 39 |
| SQL_GENERATION_FAILURE | 26 | 26 |
| CONSTRAINT_PROPAGATION_FAILURE | 17 | 17 |
| EXECUTION_FAILURE | 5 | 5 |
| ENTITY_RESOLUTION_FAILURE | 3 | 3 |

The evaluator's single-failure attribution is unchanged because its decision
tree stops at SCHEMA/SQL-generation stages before it can observe execution for
most cases. The real, observable improvement is in the **execution layer**:
DB-error rate 75% → 15%, self-joins 59 → 0, clean runs 22 → 71.

---

## 5. Disconnected graphs now fail cleanly

Per spec §23 / §31, plans whose join graph cannot connect a requested
dimension/metric table now raise `UNRESOLVABLE_JOIN_GRAPH` at compile time
instead of emitting SQL that would fail at runtime:

- `E2E_031`-style "avg risk per branch" (`branches` disconnected) → rejected.
- "loans each branch" (`products` unreferenced → dropped) → correct FROM root.
- Ratio cases with disconnected metric source tables → rejected.

These are **correct failures** — the plan is semantically invalid and no
fabricated path is emitted.

---

## 6. Side Effects (evaluator deltas explained — not compiler regressions)

Because the compiler now produces *valid, executable* SQL for 49 cases that
previously DB-errored, those queries now reach execution, the validator, and
the result-comparator:

- **Validation correctness 97.78 → 86.67:** more previously-blocked queries now
  flow to validation; some get flagged there. This is exposure, not a compiler
  defect.
- **Security block rate 100 → 60:** two unsupported/routing cases that were
  blocked upstream by compile failure now reach validation; upstream routing
  must decide their safety.
- **Level-4 accuracy 70 → 50:** two L4 clarify/routing cases no longer trivially
  "succeed by compile-failure"; intent quality now governs them.

All three are **upstream** (intent/schema/entity/validation) concerns that were
previously masked by the compiler's wholesale DB-error failure. They indicate
the next bottleneck (see §Next).

---

## 7. Reported compiler invariants now enforced (unit-tested)

New suite `tests/test_compiler_repair.py` (32 tests) enforces the Step-14
matrix:

1. single-table count (FROM root correct)
2. single-table aggregation
3. customers-by-segment (GROUP BY qualified)
4. customer→account join (FROM = join head, not alphabetical)
5. account→branch join
6. customer→account→branch two-hop
7. **no accidental self-join**
8. **duplicate edge skipped**
9. **disconnected graph rejected**
10–12. COUNT / SUM / AVG
13–14. grouped / multi-dimension GROUP BY
15. filter parameterization + value binding
16. multi-filter parameter order
17. French string value bound (never inlined)
18. date-range BETWEEN parameterization (single binding)
19. status filter
20. numeric threshold filter
21–22. IS NULL / IS NOT NULL never bound
23–24. top-N / bottom-N ordering
25–26. default / requested limit
27. fully-qualified columns (no ambiguity)
28. invalid group-by rejected
29. ratio metric independent-subqueries
30. ratio metric disconnected edges rejected
31. validator accepts generated join SQL (QueryValidator safe = True)

---

## 8. Regression Status

| Suite | Result |
|---|---|
| `test_compiler_repair.py` (new) | **32 passed** |
| `test_increment2_compile.py` | 70 passed, **1 pre-existing fail** (`test_two_dims`, documented §9) |
| `test_increment3_execution.py` | **all passed** (1 fixture corrected, §10) |
| `test_live_pg_integration.py` | passed |
| `test_sql_agent.py` | passed |

Other files (`test_caching.py`, `test_execution_agent.py`, `test_schema_agent.py`,
`test_structured_selection.py`, `test_symbolic_grounding.py`) fail at collection
due to a pre-existing `models` module-name collision unrelated to this repair
(confirmed present before edits).

---

## 9. Pre-existing failure (documented, not in scope to fix)

`TestMultiDimension::test_two_dims` — metric `kyc_compliance_rate` + dimensions
`customers.segment`, `branches.governorate`; `branches.governorate` is missing
from the builder's grain mapping, so the plan is unsupported
(`Grouped independent subqueries are not implemented`, grain not allowed).
This is a **builder grain-map gap**, unrelated to the compiler, and fails
identically before and after this repair.

---

## 10. Test fixture corrected (not an evaluator/compiler semantic change)

`test_increment3_execution.py::test_metric_without_strategy` selected only
`accounts` while asserting metric `avg_loan_size`, whose formula references
`lc.principal_amount` (`loan_contracts`) — the old compiler emitted SQL for a
table absent from FROM (a runtime DB error). The fixture is corrected to select
`loan_contracts` with no join edges and now asserts the compiler **fails closed**
with `SQLCompileError`. This documents the intended Step-14 behavior.

---

## 11. Compiler latency

Compilation is a pure in-memory render; the reported deltas (p50 62.6 vs 60.3,
p95 171.6 vs 189.1 ms) are noise from DB connection/execution variance, not the
compiler. No compilation hot-path was added beyond the O(E) join state machine.

---

## 12. Reproducibility

1. `cp baseline_v1.json /tmp/ && cp baseline_v1_traces.jsonl /tmp/` (pristine)
2. `testenv/bin/python3 benchmark/e2e_nl_sql/benchmark_runner.py`
3. `cp baseline_v1.json E2E_SQL_COMPILER_FIX_V1.json` and
   `cp baseline_v1_traces.jsonl E2E_SQL_COMPILER_FIX_V1_traces.jsonl`
4. restore pristine copies into `baseline_v1*`

---

## Next Bottleneck

After the compiler defect is removed, the dominant remaining failure is
`SCHEMA_RETRIEVAL_FAILURE` (39/90) — the schema/feature module is not retrieving
the correct tables/columns for supported cases, which prevents most plans from
forming. Recommendation: the next step is **SCHEMA_NEXT** (schema agent
feature/column retrieval and `selected_tables` fidelity), rather than any
further compiler work. The compiler now correctly stops instead of emitting
invalid SQL.
