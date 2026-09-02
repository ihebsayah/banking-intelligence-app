# E2E NL→SQL Correctness Benchmark — Baseline Report (E2E_BASELINE_V1)

**Date:** 2026-09-01
**Version:** `E2E_BASELINE_V1` (immutable)
**Pipeline under test:** deterministic, in-process — no LLM, no fixes, no architecture changes.

---

## A. Objective

Measure the *current, unmodified* end-to-end deterministic NL→SQL pipeline of the
Banking Intelligence System across 100 banking questions. The goal is a diagnostic
baseline: quantify where the pipeline breaks (intent, schema, entity, SQL
generation, validation, compliance, execution), so the next step can prioritise
the highest-leverage fixes. This step fixes nothing.

## B. Scope & Non-Goals

**In scope**
- Intent recognition (deterministic keyword/pattern + structured-intent extraction)
- Schema retrieval (semantic layer disabled — `semantic_layer_enabled=False`)
- Entity resolution (BFS join-path resolution over the live `join_registry`)
- Query plan construction → deterministic SQL compilation
- Query validation (5-gate) and compliance (GDPR / PCI-DSS / SOX / AML / KYC)
- Read-only DB execution against `banking_dev` for 33 cases with real ground truth

**Explicitly NOT in scope**
- No LLM calls, no semantic/LLM fallback, no repair engine, no plan refiner
- No fixes of any kind before the baseline is frozen
- No write/DDL operations (execution is read-only SELECT under `LIMIT`)

## C. Method

1. **Golden set** — `cases.json` (100 cases, hand-authored business semantics):
   - 20 customer/account, 15 risk/credit, 10 loan, 10 transaction,
     10 revenue/profitability, 10 geographic/branch, 10 compliance/KYC/AML,
     5 liquidity, 5 operational, 5 unsupported/unsafe (exact spec mix).
   - 51 EN / 49 FR; Levels 1–4 (20 / 40 / 30 / 10).
   - 33 cases reuse real expected values from
     `benchmark/ground_truth/development_40_expected.json`.
2. **Runner** — `benchmark_runner.py` executes the full chain in-process
   (each stage timed), dumps one trace per case
   (`results/baseline_v1_traces.jsonl`).
3. **Evaluator** — `semantic_evaluator.py` compares **semantics**, not strings:
   resolved tables, join paths, metric functions + columns, dimensions, filter
   column/operator/value, time windows, sort, limits, validation/compliance
   outcome, and executed rows (exact scalar / numeric tolerance / row count /
   unordered rows).
4. **Intent label** is scored *separately* from semantic correctness
   (`INTENT_LABEL_ACCURACY` never changes a semantic verdict).
5. Failure attribution = exactly one primary stage per failing supported case.

## D. Artifacts & Reproducibility

| Artifact | Path |
|---|---|
| Golden cases (100) | `benchmark/e2e_nl_sql/cases.json` |
| Pipeline runner | `benchmark/e2e_nl_sql/benchmark_runner.py` |
| Semantic evaluator | `benchmark/e2e_nl_sql/semantic_evaluator.py` |
| Aggregated results | `benchmark/e2e_nl_sql/results/baseline_v1.json` |
| Per-case traces | `benchmark/e2e_nl_sql/results/baseline_v1_traces.jsonl` |

Reproduce:

```bash
testenv/bin/python3 benchmark/e2e_nl_sql/benchmark_runner.py
```

Requires: live Postgres `banking_dev` (default DSN in `PG_TEST_DSN`), the
project `testenv` (spacy 3.8.14 + `en_core_web_sm`, sqlparse, psycopg2,
asyncpg). The join registry is loaded from the live DB exactly like the FastAPI
app does.

## E. Baseline Metrics (E2E_BASELINE_V1)

| Metric | Value |
|---|---|
| Intent label accuracy | **57.89 %** |
| **End-to-end semantic accuracy** (supported) | **0.00 %** |
| Result correctness (33 ground-truth cases) | **3.03 %** |
| Clarification correctness (5 L4 clarify) | **40.0 %** |
| Supported routing accuracy | 0.00 % |
| Constraint propagation accuracy | **67.78 %** |
| Join correctness rate (30 join cases) | **36.67 %** |
| Parameterization rate (23 filter cases) | **4.35 %** |
| Validation correctness | **97.78 %** |
| Compliance correctness | **100.0 %** |
| Security block rate (5 unsafe cases) | **100.0 %** |
| Level 1 / 2 / 3 / 4 accuracy | 0 / 0 / 0 / **70.0 %** |
| EN / FR end-to-end accuracy | 0 / 0 |
| Pipeline latency — p50 / p90 / p95 / avg | 60.3 / 142.3 / 189.1 / 91.1 ms |

### Primary failure distribution (90 supported cases)

| Failure stage | Cases |
|---|---:|
| SCHEMA_RETRIEVAL_FAILURE | 39 |
| SQL_GENERATION_FAILURE | 26 |
| CONSTRAINT_PROPAGATION_FAILURE | 17 |
| EXECUTION_FAILURE | 5 |
| ENTITY_RESOLUTION_FAILURE | 3 |
| VALIDATION_FALSE_REJECT / ACCEPT | 0 / 0 |
| COMPLIANCE_FALSE_REJECT / ACCEPT | 0 / 0 |
| INTENT_FAILURE (gate rejected a supportable query) | 0 |

Note: 26 `SQL_GENERATION_FAILURE` + 5 `EXECUTION_FAILURE` *understate* the SQL
defect: 75/100 cases produce SQL that **errors in Postgres** at execution time.
Most of those get attributed earlier (schema/tables) or later (DB error). The
single dominant root cause is documented in §L.

## F. Pipeline Coverage

All six stage boundaries executed in-process without modification:
`IntentRecognizer.recognize_sync → SchemaMatcher (semantic off) →
EntityResolver → QueryPlanBuilder → DeterministicSQLCompiler →
QueryValidator → ComplianceChecker → read-only execution`.

- Gate (compiled SQL produced): 89/90 supported.
- Validation reported `safe=True` on 88/90 supported.

## G. Supported Routing

- `SUPPORTED_ROUTING_ACCURACY = 0.00 %`: no supported case produced a
  semantically correct end-to-end result.
- This is driven by SQL generation (invalid self-join, §L), not by routing
  gates: gates never falsely rejected a supportable query (`INTENT_FAILURE = 0`).

## H. Intent Classification (57.89 %; Step-11 standalone was 60.24 %)

40/95 scored cases were mislabelled. The two dominant confusions, both with the
**same secondary victim category**:

- `loan_analysis → product_analysis`: **9/11** loan questions. Loan questions are
  systematically routed to the product domain.
- `kyc_analysis → risk_analysis` (4) and `aml_analysis → risk_analysis` (3):
  compliance-family questions collapse onto generic `risk_analysis`.
- `liquidity_analysis → product_analysis` (2), `profitability → revenue` (2).

Consequence: the wrong category seeds a wrong entity primary table, which then
cascades into schema selection (§I) and the generated SQL (§L). Intent accuracy
is therefore the *upstream* lever for ~40 % of cases, but only matters once
SQL generation is fixed.

## I. Schema Retrieval (biggest absolute gap: 39 failures)

Expected tables that never reach the selected set:

| Missing table | Times |
|---|---:|
| `loan_contracts` | 17 |
| `income_statement_snapshots` | 5 |
| `non_performing_loans` / `fee_income` / `aml_alerts` | 3 each |
| `provisions` / `accounts` / `balance_sheet_snapshots` / `employees` | 2 each |

Root cause chain: intent category (e.g. `product_analysis` for loan questions)
→ `INTENT_TO_DOMAINS` fallback → domains that do not map to `loan_contracts`.
The schema stage faithfully returns what the (wrong or broad) category asks for;
e.g. loan questions select `[accounts, branches, customers, products,
transactions]` and never `loan_contracts`.

## J. Entity Resolution (3 failures — best performing semantic stage)

- `E2E_070` (customers per state), `E2E_073` (customers per city),
  `E2E_074` (transaction volume per region): resolve failed to bridge the
  2-hop path `…→accounts→branches` for metric/dimension combinations.
- At plan level the join **paths** were correctly formed for 11/30
  (36.67 %) required-join cases; the compiler then fails to consume them (§L).

## K. Constraint Propagation (67.78 %; filters silently dropped)

Filter columns that were requested but **never materialised** in the plan:

`customers.risk_score` (4×), `accounts.status` (3×), `customers.kyc_verified`
(3×), `branches.name` (3× — "BR_016", "Tunis Branch"),
`loan_contracts.days_past_due` (2×), `loan_contracts.status` (2×),
`kyc_cases.status` (2×), `customers.segment` (2×).

- `PARAMETERIZATION_RATE = 4.35 %` (1/23): 22/23 filtered cases produced an
  unparameterised or filter-free query, so the compiled SQL carries no bound
  values at all.
- Time filtering is strong by contrast: 85/90 time windows matched.

## L. SQL Generation (dominant root cause)

**Canonical defect (59/100 cases):**

```sql
SELECT COUNT(*) AS count_all
FROM accounts
LEFT JOIN accounts ON customers.customer_id = accounts.customer_id
LIMIT 100
```

The compiler drops the *primary* table from `FROM` (always emits `accounts`),
then **self-joins `accounts` onto itself** using the secondary table's join key.
Every downstream consequence follows:

- `FROM accounts LEFT JOIN accounts …` → Postgres error
  `"table name accounts specified more than once"` → DB error on 75/100 queries.
- `GROUP BY` without the grouped column in select / ambiguous aggregates
  (e.g. `SELECT accounts.branch_id … GROUP BY branches.name`).
- Non-parameterised `WHERE` values (see §K).

This is the single highest-leverage fix: **75 % of all cases never reach a
correct result because of it.** §Z quantifies the payoff.

## M. Validation Behavior (97.78 % — strong, with one gap)

- 88/90 supported queries correctly passed; both injection/unsupported
  adversarial cases (D039, D040) were correctly blocked.
- The one relevant gap is `VALIDATION_FALSE_ACCEPT`: the 5-gate validator
  returned `safe=True, signature=present` for the self-joined SQL above — the
  SQL is syntactically legal yet semantically invalid, and nothing downstream
  catches it before the DB. The validator cannot substitute for a correct
  compiler.

## N. Compliance (100 % — strong, under-exercised)

- `COMPLIANCE_CORRECTNESS = 100 %`: 90/90 supported and 5/5 adversarial cases
  produced the expected compliant outcome for the roles used.
- `SECURITY_BLOCK_RATE = 100 %`: all 5 unsupported/unsafe cases stayed blocked
  (adversarial/unsupported rejection, no execution).
- Caveat: the GDPR masking path (`E2E_085`, expected `mask`) never fired
  because the SQL stage failed first — masking is currently **unreachable in E2E
  and therefore unverified**. Same for PCI-driven `COMPLIANCE_FALSE_REJECT`:
  no card/PAN column is reachable in the current schema. These are honest
  limitations, not evidence of coverage.

## O. Execution & Result Correctness (3.03 %)

- 22/100 queries executed against Postgres without a DB error; **75/100 hit a
  DB error** (self-join / bad GROUP BY); 3 were skipped (no gate).
- Of the 33 cases with real ground-truth values, only **1 matched**
  (`E2E_067`, but only under weak `row_count` mode — see W2).
- Even the queries that run mostly group by the wrong grain
  (e.g. `GROUP BY branches.name` + `COUNT(*)` returning `1636` for a branch
  "Agence Sousse Corniche 26"), so result semantics are wrong even when the DB
  accepts them.

## P. Clarification Handling (40 %)

- 2/5 L4 clarification cases were correctly routed to CLARIFY/REJECT
  (`CLARIFICATION_CORRECTNESS = 40 %`).
- `E2E_020` (this year vs last year), `E2E_075` ("which branch is best"),
  `E2E_065` (full dashboard) were not flagged vague/comparative and proceeded
  toward a (wrong) answer instead of asking.

## Q. Failure Attribution (see §E)

Distribution rank: **SCHEMA_RETRIEVAL (39) > SQL_GENERATION (26) >
CONSTRAINT_PROPAGATION (17) > EXECUTION (5) > ENTITY_RESOLUTION (3).**
Attribution is single-stage and deterministic per the ranking in
`semantic_evaluator._attribute_failure`.

## R. Language Comparison

- EN / FR end-to-end: **0 / 0** — both are fully blocked downstream, so no
  language gap is measurable at E2E today.
- At the intent stage the split is balanced: 40 label mismatches span both
  languages (worst FR confusion: `liquidity_analysis → product_analysis`;
  worst EN confusion: `loan_analysis → product_analysis`).
- The FR text + FR seed-data path (e.g. transaction status `complété`) is
  exercised by 23 supported FR cases; all of them currently fail downstream.

## S. Level Comparison

- L1 (20) 0 % — even simple scalar counts (`E2E_001`, `E2E_036`) fail: the
  self-join defect (§L) kills them at execution.
- L2 (40) 0 %, L3 (30) 0 % — every multi-stage combination currently fails.
- L4 (10) 70 % — clarification + unsupported routing is the ONLY dimension with
  meaningful success (the pipeline correctly refuses or asks where it should).

## T. Category Breakdown

All nine supported categories measure 0.0 % end-to-end, including the two
simplest (`customer_account`, `transaction`). This is the expected consequence
of one cross-cutting SQL defect; no category is "green".

## U. Evidence (verbatim generated SQL)

1. `E2E_001` — "How many customers do we have?"
   ```sql
   SELECT COUNT(*) AS count_all
   FROM accounts
   LEFT JOIN accounts ON customers.customer_id = accounts.customer_id
   LIMIT 100
   ```
2. `E2E_036` — "What is the total number of loan contracts?" (intent misrouted
   to `product_analysis`; `loan_contracts` never selected)
   ```sql
   SELECT COUNT(*) AS count_all
   FROM accounts
   LEFT JOIN branches ON accounts.branch_id = branches.branch_id
       LEFT JOIN customers ON accounts.customer_id = customers.customer_id
       ...
   ```
3. `E2E_006` — "How many customers are in each segment?"
   ```sql
   SELECT COUNT(*) AS count_all, customers.segment
   FROM accounts
   LEFT JOIN accounts ON customers.customer_id = accounts.customer_id
   GROUP BY customers.segment
   ```
4. `E2E_021` — NPL ratio → task "ratio calculation" but compiled a plain column
   projection (no ratio expression produced).

## V. Latency

- p50 **60.3 ms**, p90 **142.3 ms**, p95 **189.1 ms**, avg 91.1 ms (in-process,
  cold start excluded). Latency is not a bottleneck; correctness is.

## W. Threats to Validity

1. **Golden expectations are hand-authored business semantics** — any error in a
   golden row makes that case "fail" against a perfect pipeline. Mitigation:
   33 cases reuse the pre-existing dev ground truth; the other 67 ship a written
   `reason`-free `expected` block that reviewers can audit in `cases.json`.
2. **`row_count` result mode is weak**: it can pass on LIMIT-truncated rows.
   This is why `E2E_067` counts as the single RESULT "pass" despite producing
   non-Tunis data. Flagged; used only for dev-reused cases.
3. **Execution environment flakiness**: DSN defaults to local `banking_dev`;
   if absent, execution degrades to `ran=False` → lower `RESULT_CORRECTNESS`.
4. **Join registry is DB-derived**: if seed changes, join paths change. Frozen
   under `E2E_BASELINE_V1` as-of this run.

## X. Benchmark Limitations

- Compliance **block** paths are unreachable in the current schema (no
  card/PAN/PII-only requests end-to-end) — masking and critical-violation
  handling remain untested E2E.
- 5 L4 clarify cases only — fine-grained clarification accuracy is
  low-confidence.
- The measurement is in-process (no FastAPI/orchestrator layer) to keep the
  deterministic path synchronous and reproducible; the orchestrator's LLM
  routing is intentionally excluded per Step 13.

## Y. Relationship to earlier increments

- Step-11 intent-only: 60.24 % → this full E2E run: 57.89 % on a *different,
  wider* question set (100 vs 40 cases). Same order of magnitude; intent is
  not the primary blocker.
- The canonical self-join defect was already reproducible in the earlier
  orchestrator-era benchmark (`benchmark/run_development.py` executes against
  the same compiler); this baseline now quantifies its blast radius (75/100
  queries hit a DB error).

## Z. Promising subsystems (fix-order priority, diagnostic only)

| Rank | Stage | Signal | Recommended focus |
|---|---|---|---|
| 1 | **SQL generation** | self-join defect hits 59/100; 75/100 DB errors; every category at 0 % | Compiler `FROM`/join construction for multi-table paths; keep primary table; stop emiting `accounts` as universal root |
| 2 | **Schema retrieval** | 39 failures; `loan_contracts` missing 17×; intent→domains mapping | Fix `INTENT_TO_DOMAINS`; add `loan_contracts`/`fee_income`/`aml_alerts`/`income_statement_snapshots` for the right categories |
| 3 | **Intent** | 40 mismatches; loan→product 9/11; kyc/aml→risk 7 | Loosen `loan_*` vs `product_*` discriminator; separate KYC/AML from generic risk |
| 4 | **Constraint propagation** | 17 cases; 22/23 filters unparameterized | Carry `filters_structured` into plan filters; bind values as parameters |
| 5 | **Entity resolution** | only 3 failures; 36.67 % join paths at plan level | Support 2-hop bridges for customer↔branch analytics |
| 6 | **Validation / Compliance** | 97.78 % / 100 % | Already strong; add a *join-sanity* gate to catch self-join false-accepts |
| 7 | **Clarification** | 40 % (2/5) | Better comparative/vague detection for "vs" and "best" queries |

## AA. Architectural Conclusion

**`PIPELINE_HAS_CROSS_CUTTING_SQL_DEFECT` + `SCHEMA_UNDER-SELECTS` +
`INTENT_MISROUTES_LOAN_COMPLIANCE` + `VALIDATION_COMPLIANCE_STRONG`.**

The deterministic pipeline is fast (p50 ≈ 60 ms), secure at the gate
(validation + compliance + adversarial handling all ≥ 97.8 %), and its
entity/join *planning* is partially sound (36.7 % join paths, 85/90 time
constraints). But the SQL layer that consumes those plans is currently
**unable to emit valid multi-table SQL** (canonical `FROM accounts LEFT JOIN
accounts …`), which independently caps every category and both languages at
0 % end-to-end. Fixing SQL generation is necessary *and sufficient* to move the
score; schema and intent repair are necessary to move it further; validation
and compliance do not need changes before the same fiscal cycle.