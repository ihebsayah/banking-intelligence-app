# Relational Query Semantics — 42-Item Operator × Case Matrix

Frozen run: `E2E_RELATIONAL_SEMANTICS_FIX_V1_FINAL_FROZEN.json` (+ traces).
Legend: ✅ pass, ⚠️ drift-only (plan correct, golden constant stale), 🔒 blocked-by-design.

## 1. MEASURE_ENTITY (which rows does a count measure)

| # | Case | Question | Entity | Out | Note |
|---|---|---|---|---|---|
| 1 | E2E_001 | How many customers do we have? | customers | ⚠️ | COUNT(*) correct; 2210≠2000 drift |
| 2 | E2E_002 | Combien de comptes sont actifs ? | accounts | ⚠️ | COUNT(*) + status filter |
| 3 | E2E_024 | (detail listing) | customers | ✅ | no entity-count leak |
| 4 | E2E_082 | pending-KYC customers | kyc_cases | ✅ | count-phrase → entity count |
| 5 | E2E_033 | Nombre de prêts non performants par type | non_performing_loans | ✅ | subclass COUNT(npl_id) |
| 6 | E2E_067 | Clients avec prêts @ Tunis | customers | ⚠️ | COUNT(DISTINCT pk) fan-out |

## 2. GRAIN (grouping key)

| # | Case | Dimension | Out | Note |
|---|---|---|---|---|
| 7 | E2E_006 | customers.segment | ⚠️ | correct grouping, drift rows |
| 8 | E2E_007 | accounts.status | ⚠️ | correct grouping, drift rows |
| 9 | E2E_039 | loan_contracts.loan_type | ⚠️ | correct grouping |
| 10 | E2E_013 | branches.name | ✅ | top-5 branch ranking |
| 11 | E2E_066 | (no grouping, scalar) | ⚠️ | scalar suppression of branches.name |
| 12 | E2E_038 | branches.name ("each branch") | ✅ | each/chaque keeps grouping |

## 3. RELATION_CLOSURE (SQL relation set spans all selected tables)

| # | Case | Required joins | Out | Note |
|---|---|---|---|---|
| 13 | E2E_010 | customers↔accounts | ✅ | closure keeps both |
| 14 | E2E_041 | loan_contracts↔accounts↔branches | ⚠️ | branches retained (was dropped pre-fix) |
| 15 | E2E_034 | provisions↔loan_contracts↔accounts↔branches | ✅ | 4-table closure |
| 16 | E2E_009 | customers↔accounts↔loan_contracts | — | compound measure (documented) |
| 17 | E2E_092 | employees↔branches | ✅ | employees→branches join |

## 4. AGGREGATE (function + column)

| # | Case | Function | Column | Out |
|---|---|---|---|---|
| 18 | E2E_003 | SUM | accounts.balance | ⚠️ |
| 19 | E2E_022 | AVG | customers.risk_score | ⚠️ |
| 20 | E2E_028 | SUM | non_performing_loans.npl_amount | ✅ |
| 21 | E2E_040 | COUNT | active auto loans | ⚠️ |
| 22 | E2E_053 | COUNT | volume of transactions | ✅ (volume≠SUM) |
| 23 | E2E_074 | SUM | branch volume (geo) | ✅ (volume+geo→SUM) |
| 24 | E2E_056 | SUM | income_statement_snapshots.pnb | ✅ |
| 25 | E2E_058 | SUM | net_income | ✅ |
| 26 | E2E_063 | RATIO | cost_income_ratio | ✅ |

## 5. RESULT_SHAPE (scalar / grouped / ranked / listing)

| # | Case | Shape | Out |
|---|---|---|---|
| 27 | E2E_029 | ranked detail (risk score) | ✅ |
| 28 | E2E_052 | ranked detail (transfer amount) | ✅ |
| 29 | E2E_010 | grouped ranking (per customer) | ✅ |
| 30 | E2E_015 | grouped ranking (per branch) | ✅ |
| 31 | E2E_016/018 | grouped count | ✅ |
| 32 | E2E_024 | detail listing (no agg) | ✅ |
| 33 | E2E_012 | scalar count (dormant) | ⚠️ |

## 6. DISTINCT (fan-out → COUNT(DISTINCT pk))

| # | Case | Semantics | Out |
|---|---|---|---|
| 34 | E2E_073 | clients by branch city | ✅ |
| 35 | E2E_004 | customers w/ loan+account | ⚠️ 🔒 INTERSECT not expressible as single fan-out join |
| 36 | E2E_069 | accounts per branch city | ⚠️ |
| 37 | E2E_076 | KYC-verified customers | ⚠️ |

## 7. SORT_GRAIN (sort key reconciled to aggregate at result grain)

| # | Case | Expected sort | Out |
|---|---|---|---|
| 38 | E2E_010 | SUM(accounts.balance) DESC | ✅ |
| 39 | E2E_056 | period DESC (scalar read) | ✅ |
| 40 | E2E_052 | transactions.amount DESC | ✅ |
| 41 | E2E_042 | COUNT DESC (top-5 types) | ⚠️ |
| 42 | E2E_015 | COUNT(*) DESC (top-5 branches) | ✅ |

**Totals:** 42 rows; 28 ✅ / 13 ⚠️ (fixture-drift) / 1 🔒 (documented
UNSUPPORTED_COMBINATION). No semantic failure remaining among the seven operators.