# Benchmark Runtime Invocation Map

## Classification: C — Core NL-to-SQL Component Benchmark

The benchmark runners (`run_development.py`, `run_smoke.py`) test the
**core deterministic pipeline** only. They do not invoke the distributed
agent system.

## What the runner imports

| Module | File | Purpose |
|--------|------|---------|
| `QueryPlanBuilder` | `services/sql_agent/query_plan_builder.py` | Builds QueryPlan from pre-resolved structured intent |
| `initialize_join_registry` | (same) | Loads join graph from PostgreSQL |
| `DeterministicSQLCompiler` | `services/sql_agent/deterministic_compiler.py` | Compiles QueryPlan → parameterized SQL |
| `ResultVerifier` | `services/execution_agent/result_verifier.py` | Verifies query results against expected answer types |
| `PGRepairEngine` | `services/execution_agent/pg_repair_engine.py` | Diagnoses PG errors (instantiated, safety-only usage) |

## What the runner does NOT invoke

| Component | Status |
|-----------|--------|
| API Gateway (`services/api_gateway/`) | **BYPASSED** — no HTTP endpoints called |
| Orchestrator (`services/orchestrator/`) | **BYPASSED** — no agent coordination |
| Intent Agent (`services/intent_agent/`) | **BYPASSED** — pre-resolved inputs provided |
| Schema Agent (`services/schema_agent/`) | **BYPASSED** — tables/columns pre-selected |
| Compliance Agent | **BYPASSED** — not tested |
| Audit Agent | **BYPASSED** — not tested |
| Entity Resolution Agent (`services/entity_resolution_agent/`) | **BYPASSED** — not imported |
| SQL Generation Agent (standalone) | **BYPASSED** — compiler used directly |
| Execution Agent (full flow) | **BYPASSED** — only ResultVerifier imported |

## Pipeline traced per question

```
development_40.json (pre-resolved structured inputs)
  → QueryPlanBuilder.build()          [planning]
  → DeterministicSQLCompiler.compile() [compilation]
  → Unsafe SQL pattern check           [safety gate]
  → psycopg2.execute()                [direct PG execution]
  → ResultVerifier.verify()           [verification]
  → ground_truth comparison           [scoring]
```

## What the benchmark proves

1. The core NL→SQL **deterministic pipeline** (plan building + SQL compilation)
   handles all 40 development questions correctly.
2. Aggregate handling, multi-table join resolution, and governed metric
   compilation work for the tested categories.
3. Unsafe SQL is correctly blocked.
4. Result verification logic is correct.

## What the benchmark does NOT prove

1. That the Intent Agent correctly classifies free-text questions.
2. That the Schema Agent correctly selects tables/columns from NL.
3. That the Orchestrator correctly coordinates the multi-agent flow.
4. That HTTP endpoints work end-to-end.
5. That the Compliance Agent blocks unauthorized requests through the full stack.
6. That the system works under concurrent load or network latency.

## Holdout implication

A 160-question holdout on this benchmark would validate the
**core NL→SQL engine strength** — not the complete deployed agent system.
The report must state this clearly.
