# Branch Semantics & Master-Data Closure — Completion Report

**Date:** 2026-08-04
**Scope:** Parts 1–12 of the Branch Semantics and Master-Data Closure task
**Status:** ✅ All parts complete

---

## 1. Executive Summary

The banking intelligence pipeline now has end-to-end branch-name resolution with safe clarification UX, generic branch-filter propagation for all intent types, automatic join-graph completion, French revenue recognition, no-data UX, durable compliance-rule repair, and frontend clarification rendering. No regressions to the existing revenue implementation. No hardcoded branch aliases. All unknown branches fail closed with an actionable clarification message.

---

## 2. Branch Master-Data Audit (Part 1)

| Metric | Value |
|---|---|
| Total branches in `branches` table | 238 |
| Curated branches | 3 (`BR_TN_001` Tunis Main, `BR_TN_002` Sfax Hub, `BR_TN_003` Sousse Coastal) |
| Generated branches | 200 (`BR_TN_GEN_1..200`, "Branch N City") |
| Legacy numeric branches | 35 (`BR_001`–`BR_237`) |
| "Sfax Main Branch" rows | **0** |
| Sfax-named branches | 28 (all "Sfax City" or "Agence Sfax Centre/Hub/Nord") |
| Aliases column | Does not exist |

**Decision:** "Sfax Main Branch" = **C (remain unresolved)**. An approved-alias model is a separate future effort; this task never silently maps unknown branches.

---

## 3. Safe Clarification UX (Part 2)

### `resolve_branch` response policy (`services/sql_agent/branch_resolver.py` + `main.py`)
- `_resolve_branch` returns structured dict instead of raising:
  - `success: true, branch_id, branch_name` → resolved
  - `success: false, clarification_type: "not_found", candidates: []` → unknown branch, fail closed
  - `success: false, clarification_type: "ambiguous", candidates: [...]` → name match but no disambiguation possible

### Orchestrator routing (`orchestrator_agent.py:161–168`)
```python
clarification = sql_response.get("clarification")
if clarification:
    return {
        "status": "error",
        "error": clarification["message"],
        "requires_clarification": True,
        "clarification": clarification,
    }
```
Clarification responses are never silently swallowed; the frontend receives `requires_clarification: true` with the full clarification payload.

### Live verification
- `POST /query {"query": "clients at Sfax Main Branch"}` → `requires_clarification: true`, `"Sfax Main Branch" was not found in the branch directory`, `candidates: []`
- `POST /query {"query": "clients at Ariana Centre"}` → `requires_clarification: true`, `ambiguous`, `candidates: ["Agence Ariana Centre 2", "Agence Ariana Centre 27"]`

---

## 4. Generic Branch-Filter Propagation (Part 3)

All intent types (not just revenue) now propagate `filters["branches.name"]` through the SQL agent via a Phase 2 block in `_call_sql_agent` (`orchestrator_agent.py:633–663`):

1. Preset queries bypass propagation (they have their own hardcoded SQL).
2. Non-preset: if `intent_data["filters"]` contains `branches.name`, the orchestrator:
   - Injects `branch_context` into the SQL response data.
   - Merges filters non-destructively: `{**intent_data.get("filters") or {}, **filters}` so orchestrator-resolved values win without dropping other intent filters.
3. `_complete_branch_join` is called to ensure the query can reach the `branches` table.

### Live verification
- `"Top 10 clients à l'agence Lac 2 16 par revenu"` → intent `customer_analysis`, SQL query joins `customers→accounts→branches`, filters by `branches.name = 'Lac 2 16'`, returns `branch_context`.

---

## 5. Join-Graph Completion (Part 4)

### `_complete_branch_join` (`orchestrator_agent.py:868–916`)
Static method on `OrchestratorAgent`. Canonical path: `customers→accounts→branches` (LEFT JOINs). Direction-insensitive — if query already joins from `accounts`, only the `accounts→branches` leg is added. Returns `(extra_joins, extra_tables)` or `None` (fail closed, never fabricates joins).

### `_complete_branch_path` (`sql_builder.py:550–586`)
Module-level `_CANONICAL_BRANCH_PATH` constant defines the standard join chain. `build()` at line ~754–773 checks if `branches` is in `filter_tables` but not in `tables` → auto-completes or raises `ValueError("no safe join path")`.

### Tests
- **TC-16** (`test_sql_agent.py`): `branches.name` filter without tables → auto-completes `customers→accounts→branches`
- **TC-17** (`test_sql_agent.py`): `accounts` already joined → adds only `accounts→branches` leg
- **TC-18** (`test_sql_agent.py`): unrelated tables only → `ValueError` (fail closed)

---

## 6. French Revenue Recognition (Part 5)

Added French vocabulary to all three keyword maps in `services/intent_agent/structured_intent.py`:

| Map | Added words |
|---|---|
| `ORIGINAL_CATEGORY_KEYWORDS["revenue_analysis"]` | `revenu`, `revenus`, `commissions`, `frais`, `bénéfice`, `bénéfices`, `pnb` |
| `SEMANTIC_CATEGORY_KEYWORDS["profitability_analysis"]` | (mirrored the same set) |
| `FRENCH_KEYWORDS` (global) | `revenu`, `revenus`, `commissions`, `frais`, `bénéfice`, `bénéfices`, `pnb` |

### Live verification
- `"revenus par agence"` → intent `revenue_analysis` (was previously misclassified as `transaction_analysis`)
- `"Top 10 clients à l'agence Lac 2 16 par revenu"` → `revenue_analysis` with branch filter + revenue SQL path

---

## 7. No-Data UX (Part 6)

`services/insights_agent/insights_generator.py` `generate()` now returns early when `request.results` is empty:

```python
if not request.results:
    return InsightResponse(
        status="no_data",
        summary="Aucune donnée disponible pour cette analyse. Vérifiez les filtres ou essayez une autre requête.",
        # ... explicit no-data fields, no statistical analysis, no Mistral calls
    )
```

- No statistical analysis is performed on empty data.
- No Mistral/LLM calls are made.
- No fabricated recommendations.
- French-language message for user clarity.

**Test updated:** `test_generate_handles_empty_results` now asserts `status == "no_data"` and `recommendations == []`.

---

## 8. Durable Compliance-Rule Repair (Part 7)

`scripts/repair_compliance_rules.py` — idempotent script that:
1. Deduplicates existing rules: `DELETE WHERE id::text NOT IN (SELECT MIN(id::text) ... GROUP BY rule_name)`
2. Creates unique index: `CREATE UNIQUE INDEX IF NOT EXISTS uq_compliance_rules_rule_name`
3. Upserts 12 canonical rules (INSERT ON CONFLICT DO UPDATE)

### Live verification
- Pre-repair: 144 rows (duplicates from prior runs)
- Post-repair: 12 rows, 12 distinct `rule_name`s
- Rerun: 0 changes (idempotent)
- Unique index `uq_compliance_rules_rule_name` confirmed created

### Canonical 12 rules
Mask PII GDPR, Right to be Forgotten 3yr, Data Portability on Request, Mask Card Numbers PCI-DSS, Restrict Card Data Access PCI-DSS, Tokenize Card Data PCI-DSS, Log All Sensitive Access SOX, Segregation of Duties SOX, Change Management Approval SOX, Monitor Large Transactions AML, Sanctions Screening AML, Enhanced Due Diligence KYC.

---

## 9. Frontend Clarification Rendering (Part 10)

### `frontend/src/types/insights.ts`
`QueryResult` extended with:
- `requires_clarification?: boolean`
- `clarification?: { requires_clarification, clarification_type, message, candidates?, raw_value? }`
- `error?: string`

### `frontend/src/api/queryApi.ts`
`submitQuery` now passes through `requires_clarification`, `clarification`, and `error` from the raw API response into the typed `QueryResult`.

### `frontend/src/pages/Assistant.tsx`
When `result.requires_clarification` is true, the assistant renders the clarification message instead of a success/error state:
```tsx
if (result.requires_clarification && result.clarification) {
  const clarMsg = { text: `🔍 ${result.clarification.message}`, isError: false };
  // replaces loading indicator with clarification card
}
```

TypeScript compiles cleanly (`npx tsc --noEmit` passes).

---

## 10. Test Coverage (Parts 8–11)

### Python tests
| File | Tests | Status |
|---|---|---|
| `test_sql_agent.py` | 18 (TC-01 through TC-18) | ✅ all pass |
| `test_revenue_branch_queries.py` | 8 (6 original + 2 generic-propagation) | ✅ all pass |
| `test_branch_resolver.py` | 5 | ✅ all pass |
| `test_insights_agent.py` | 15 (including no-data test) | ✅ all pass |
| `test_compliance_agent.py` | 16 | ✅ all pass |
| `test_intent_agent.py` | 24 | ✅ all pass |

### Frontend tests
| File | Tests | Status |
|---|---|---|
| `Assistant.test.tsx` | 11 (including clarification test) | ✅ all pass |

**Total: 97 tests, all green.**

### Pre-existing known issue
`tests/test_insights_agent.py` causes a module-name collision when run alongside `tests/test_sql_agent.py` via a single `pytest` invocation. Workaround: run separately or use `--import-mode=importlib` (already configured in `pytest.ini`).

---

## 11. Live Verification Results

All services restarted (`banking_sql_agent banking_orchestrator banking_intent_agent`).

| Probe | Result |
|---|---|
| `POST /query "Sfax Main Branch"` | `requires_clarification: true`, `candidates: []` |
| `POST /query "Ariana Centre"` | `requires_clarification: true`, `candidates: ["Agence Ariana Centre 2", "Agence Ariana Centre 27"]` |
| `POST /query "Top 10 clients à l'agence Lac 2 16 par revenu"` | intent `revenue_analysis`, SQL joins `customers→accounts→branches`, `branch_context` in response |
| `POST /query "revenus par agence"` | intent `revenue_analysis` (was `transaction_analysis` before French vocab) |
| `GET /resolve_branch "Sfax Main Branch"` | `success: false, clarification_type: not_found` |
| `GET /resolve_branch "Ariana Centre"` | `success: false, clarification_type: ambiguous` |
| `GET /resolve_branch "Lac 2 16"` | `success: true, branch_id: "BR_TN_GEN_16"` |
| `GET /compliance/rules` | 12 rules, unique index present |
| `GET /insights/status` | Healthy (with empty-data path verified) |

**Gateway note:** `banking_keycloak` container is unhealthy; `AUTH_PROVIDER=keycloak` + `AUTH_COMPATIBILITY_MODE=false` blocks live gateway verification. Direct orchestrator verification was used throughout. Gateway testing is a separate task.

---

## 12. Architecture Decisions & Non-Goals

| Decision | Rationale |
|---|---|
| Fail-closed for unknown branches | Never silently map an unknown name; the user must disambiguate or correct |
| No alias system | Approved-alias model is a separate future effort; scope of this task is fail-closed clarification only |
| Generic propagation for all intents | Branch filter applies to customer, transaction, compliance, and revenue queries — not just revenue |
| `_complete_branch_join` as static method | Encapsulates join logic in orchestrator, callable from both `_call_sql_agent` and `_revenue_metric_request` |
| Canonical join path constant | `customers→accounts→branches` is the only safe join graph; no other table can reach `branches` |
| French revenue keywords in all three maps | Ensures both `ORIGINAL_CATEGORY_KEYWORDS` and `SEMANTIC_CATEGORY_KEYWORDS` match French revenue queries |
| No-data early return in insights | Prevents statistical analysis and LLM calls on empty data; explicit French message for UX |
| Idempotent compliance repair script | Safe to rerun; dedupe→index→upsert pattern ensures no duplicates regardless of prior state |
| Frontend clarification without new components | Reuses existing `ChatMessage` and error-style rendering; minimal diff, no new abstractions |
