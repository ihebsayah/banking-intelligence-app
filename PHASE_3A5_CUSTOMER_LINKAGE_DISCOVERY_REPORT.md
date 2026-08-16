# Phase 3A.5 — Workbench Customer Linkage Validation and Remediation — Discovery Report

**Status: DISCOVERY COMPLETE. No production code, migrations, or data mutations were performed.**
**Produced: 2026-08-15**

---

## 1. Executive Summary

The investigation confirms G1 but revises its framing:

- **728 alerts** exist in `banking_integration` (one more than the previously reported 727).
- **724 carry no customer linkage** — confirmed. But the root cause is not a design flaw: **all 724 are test/benchmark artifacts** produced by prior test runs and smoke scripts that seeded the live integration DB without cleanup.
- **4 alerts carry linkage** (`related_entity_type` + `related_entity_id` both set).
- Of those 4, **1 resolves correctly** to a real customer (`CUST_00001`, direct `customer` type link, matching `customers.customer_id` in `banking_dev`).
- **2 have a format mismatch**: `CUST-00921` and `CUST-00077` use a hyphen (`-`) instead of the canonical underscore (`_`) separator. Both `CUST_00921` and `CUST_00077` exist in `banking_dev`. These are **fixable by correcting the seed data**.
- **1 has an account-type link**: `ACC-00412` uses a hyphen; the real ID is `ACC_00412`, which exists in `banking_dev` and resolves via `accounts.customer_id = CUST_00141`. **Authoritative derived linkage is possible here**.
- The 724 test/benchmark alerts have **no entity reference at all** (both fields NULL) and no attribute to deterministically infer a customer. They cannot be linked without fabricating data.

> **The G1 problem is not a missing linkage mechanism. It is test artifact pollution of the live integration database.**

**Recommended remediation:**
1. Fix 3 seed data format errors (hyphen to underscore in `seed_canonical_demo.sql`).
2. Add account-type resolution to `WorkbenchLinkRepository` and `AlertDetailPage`.
3. No new tables, no migrations, no schema changes required.

---

## 2. Current Linkage Architecture

### 2.1 Two-Database Isolation

| Database | Container | Port | Tables |
|---|---|---|---|
| `banking_dev` | `banking_postgres_main` | 5432 | `customers`, `accounts`, `transactions`, `aml_alerts` |
| `banking_integration` | `banking_postgres_integration` | 5435 | `alerts`, `investigations`, `compliance_cases` |

No FK, no cross-DB view, no shared schema. The API gateway holds both connections and composes in the service layer.

### 2.2 Alert Model (workbench)

[`services/workbench/models.py`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/workbench/models.py#L10-L32) — [`migrations/versions/0004_add_operational_entities.py`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/migrations/versions/0004_add_operational_entities.py#L79-L112)

```sql
related_entity_type VARCHAR(50),    -- no CHECK constraint, no FK
related_entity_id   VARCHAR(100),   -- no CHECK constraint, no FK
```

### 2.3 WorkbenchLinkRepository

[`services/api_gateway/customer360/repos.py:392-426`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/api_gateway/customer360/repos.py#L392-L426) — reads workbench alerts for a customer exclusively via:

```sql
WHERE related_entity_type = 'customer' AND related_entity_id = $1
```

No account-type or transaction-type resolution exists today.

### 2.4 CustomerContextPanel (frontend)

[`frontend/src/components/customers/CustomerContextPanel.tsx`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/components/customers/CustomerContextPanel.tsx) — triggered in:

- `AlertDetailPage`: fires when `related_entity_type === 'customer' && related_entity_id`.
- `InvestigationDetailPage` / `CaseDetailPage`: resolves via linked alert's entity fields.

The panel **does not handle `related_entity_type='account'`**.

---

## 3. Relevant Files / Components

| File | Role |
|---|---|
| [`services/workbench/models.py`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/workbench/models.py) | Alert Pydantic model |
| [`services/workbench/schemas/alerts.py`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/workbench/schemas/alerts.py) | Alert API schemas |
| [`services/workbench/repos.py`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/workbench/repos.py#L75-L140) | AlertRepo, InvestigationRepo |
| [`migrations/versions/0004_add_operational_entities.py`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/migrations/versions/0004_add_operational_entities.py#L77-L116) | Alerts DDL |
| [`scripts/seed_canonical_demo.sql`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/scripts/seed_canonical_demo.sql) | **Primary seed — 3 alerts with format errors** |
| [`services/workbench/tests/test_2b17b_scenarios.py:185`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/workbench/tests/test_2b17b_scenarios.py#L185-L194) | `_seed_alert()` — **root cause of 672 "Seed Alert" rows** |
| [`scripts/staging_smoke_test.sh`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/scripts/staging_smoke_test.sh#L82-L84) | "Smoke Alert" seed (1 row) |
| [`services/api_gateway/customer360/repos.py`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/api_gateway/customer360/repos.py#L392-L470) | WorkbenchLinkRepository |
| [`frontend/src/components/alerts/AlertDetailPage.tsx`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/components/alerts/AlertDetailPage.tsx) | Panel trigger (customer-type only) |
| [`init/09-tunisian-banking-data-seed.sql`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/init/09-tunisian-banking-data-seed.sql) | Main DB seed: `CUST_NNNNN` / `ACC_NNNNN` format |

---

## 4. Database Relationships

### 4.1 Alert to customer resolution paths

```
alerts.related_entity_type = 'customer'
alerts.related_entity_id = CUST_XXXXX
  → banking_dev.customers.customer_id          ← Type A (direct)

alerts.related_entity_type = 'account'
alerts.related_entity_id = ACC_XXXXX
  → banking_dev.accounts.account_id
  → banking_dev.accounts.customer_id
  → banking_dev.customers.customer_id          ← Type B (one hop, authoritative)

alerts.related_entity_type IS NULL (724 rows)
  → NO LINKAGE POSSIBLE                        ← Type D
```

### 4.2 Investigation / case inherit via alert

```
investigations.alert_id → alerts → related_entity_{type,id}
compliance_cases.alert_id → alerts → related_entity_{type,id}
compliance_cases.investigation_id → investigations → alert → ...
```

No independent customer field exists on investigations or cases.

---

## 5. Current Data Distribution (live, verified 2026-08-15)

### 5.1 Alerts table

| Metric | Count |
|---|---|
| **Total alerts** | **728** |
| Has entity_type set | 4 |
| Has entity_id set | 4 |
| Has both | 4 |
| `related_entity_type = 'customer'` | 3 |
| `related_entity_type = 'account'` | 1 |
| Both NULL (no linkage) | **724** |

### 5.2 Alert title distribution (identifies origin)

| Title | Count | Has linkage |
|---|---|---|
| "Seed Alert" | 672 | 0 — `test_2b17b_scenarios.py` artifact |
| "Test Alert" | 30 | 0 — test artifact |
| "t" | 21 | 0 — test artifact (hand-typed) |
| "Smoke Alert" | 1 | 0 — staging smoke script |
| "Unusual deposit pattern on CUST_00001" | 1 | customer / CUST_00001 (resolves) |
| "Unusual rapid same-account transfers" | 1 | account / ACC-00412 (format error) |
| "KPI breach: customer onboarding timeliness" | 1 | customer / CUST-00921 (format error) |
| "Unassigned pattern-match alert" | 1 | customer / CUST-00077 (format error) |

### 5.3 Resolvability of the 4 linked alerts

| Alert ID prefix | Entity type | Entity ID (workbench) | Exists in main DB? | Notes |
|---|---|---|---|---|
| `cccccccc-1111` | customer | `CUST_00001` | YES | **Fully resolves** |
| `11111111-1111` | customer | `CUST-00921` | NO | `CUST_00921` exists — format error |
| `33333333-3333` | customer | `CUST-00077` | NO | `CUST_00077` exists — format error |
| `22222222-2222` | account | `ACC-00412` | NO | `ACC_00412` exists → `CUST_00141` — format error |

### 5.4 Investigations and cases

| Metric | Count |
|---|---|
| Total investigations | 717 |
| With alert_id | 173 |
| Whose alert has linkage | 3 |
| Total compliance cases | 1,486 |
| With alert_id | 71 |
| Whose alert has linkage | 1 |

---

## 6. Reproduction of G1

G1 was reported as "724/727 alerts carry no resolved customer entity."

**Verified:** 724/728 — same 724 NULL-linkage rows, but total is now 728 (one new test artifact added since last report). G1 stands.

---

## 7. Root-Cause Analysis

### 7.1 The 724 NULL-linkage alerts

**Root cause: test suite and smoke scripts ran against the live integration DB without cleanup.**

- [`test_2b17b_scenarios.py:185-194`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/workbench/tests/test_2b17b_scenarios.py#L185-L194) — `_seed_alert()` inserts `"Seed Alert"` rows using `asyncpg` directly against `INTEGRATION_DATABASE_URL`. Each test call leaves a row. **672 rows** from multiple runs.
- [`scripts/staging_smoke_test.sh:82-84`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/scripts/staging_smoke_test.sh#L82-L84) — seeds "Smoke Alert". **1 row**.
- Other test files (`test_infrastructure_smoke.py`, `conftest.py`, ad-hoc runs) — **51 rows** ("Test Alert", "t").

None of these 724 alerts have any `related_entity_type`, `related_entity_id`, `source_rule_type`, or `source_rule_id`. **There is no deterministic path to a customer for any of them.**

### 7.2 The 3 format-error alerts

**Root cause: `scripts/seed_canonical_demo.sql` uses hyphen (`-`) in entity IDs instead of the canonical underscore (`_`).**

Main DB seed (`init/09-tunisian-banking-data-seed.sql`) consistently uses `CUST_NNNNN` and `ACC_NNNNN`. The canonical demo seed was written with `CUST-NNNNN` / `ACC-NNNNN` — a transcription error:

```sql
-- seed_canonical_demo.sql (WRONG):
'customer', 'CUST-00921'   -- line 38, should be CUST_00921
'customer', 'CUST-00077'   -- line 46, should be CUST_00077
'account',  'ACC-00412'    -- line 42, should be ACC_00412
```

The linkage break is at the point of insertion. The chain in `banking_dev` is fully intact:

```
banking_dev.customers:  CUST_00921 exists ✓
banking_integration:    alert.related_entity_id = 'CUST-00921'  ← WRONG
Resolution:             Customer360Service.get_overview('CUST-00921') → None
```

---

## 8. Deterministic Linkage Paths Discovered

### Classification A — Authoritative direct linkage

- Alerts with `related_entity_type='customer'` + matching `customers.customer_id`.
- Currently resolves: 1 alert. After seed fix: 3 alerts.
- **Already fully implemented** in CustomerContextPanel + WorkbenchLinkRepository.

### Classification B — Authoritative derived linkage

- Alerts with `related_entity_type='account'` + matching `accounts.account_id`.
- `accounts.account_id` is PK; `accounts.customer_id` is FK to `customers` (authoritative, unambiguous).
- Currently resolves: 0 (format error). After seed fix + account resolver: 1 alert (`ACC_00412` → `CUST_00141`).
- **Not yet implemented.** Requires `SELECT customer_id FROM accounts WHERE account_id = $1` in `WorkbenchLinkRepository`.

### Classification C — Authoritative derived (transaction, not needed)

- No transaction-type alerts exist. Same pattern as B if ever needed. Skip for now.

### Classification D — No linkage possible

- All 724 NULL-entity alerts. No attribute can be used to deterministically infer a customer. Must remain unlinked.

---

## 9. Ambiguous / Unresolvable Cases

All 724 test-artifact alerts are **D — genuinely unresolvable**. They continue to render no CustomerContextPanel per Phase 3A.4 behavior. No fuzzy matching applies.

---

## 10. Security Implications

### Format-fix

No new code path. After fix, the existing server-side Customer 360 authorization (permission check + org-scope 404 + PII masking + audit) handles the lookup identically. A corrected entity ID does not elevate access.

### Account resolver (Path B)

- Query: `SELECT customer_id FROM accounts WHERE account_id = $1` — PK lookup, returns only `customer_id`.
- Result passed to `Customer360Service.get_overview()` which applies the full auth stack.
- No bypass, no leak, no org-scope violation.

### Test artifact cleanup

Deleting the 724 rows is out of 3A.5 scope and requires explicit user approval. The rows are harmless — no panel renders, no customer data exposed.

---

## 11. Options Considered

| Option | Impact | Recommendation |
|---|---|---|
| **1: Fix seed + add account resolver** | 3-line seed fix, ~10 lines new code, 0 migrations | **Recommended** |
| 2: Fix seed only | 3-line fix, 2 new resolving alerts (not 3) | Acceptable minimum |
| 3: Add `customer_id` column to workbench alerts | New migration, backfill, no FK possible | Over-engineered |
| 4: Clean up 724 test artifacts | Requires explicit approval, separate from 3A.5 | Hold |

---

## 12. Recommended Minimal Remediation

**Implement Option 1:**

1. **Fix `scripts/seed_canonical_demo.sql`** — 3 lines: `CUST-` → `CUST_`, `ACC-` → `ACC_`.

2. **Add `resolve_customer_id_for_account()` to `WorkbenchLinkRepository`** (~8 lines):
   ```python
   async def resolve_customer_id_for_account(self, account_id: str) -> Optional[str]:
       row = await self._db.fetch_one(
           "SELECT customer_id FROM accounts WHERE account_id = $1", [account_id]
       )
       return row["customer_id"] if row else None
   ```

3. **Enrich Alert Response server-side** — add `resolved_customer_id` field to the alert API response (workbench returns it already resolved). Keeps resolution server-side, no new public endpoint, no additional auth surface.

4. **Update `AlertDetailPage`** — when `related_entity_type === 'account'` and `resolved_customer_id` is present, render `<CustomerContextPanel customerId={resolved_customer_id} />`.

5. **Re-run `seed_canonical_demo.sql`** (idempotent, `ON CONFLICT DO NOTHING`).

**Result after remediation**: 3 customer-type alerts resolve (up from 1), 1 account-type alert also resolves. 724 test artifacts remain without panel (correct behavior).

---

## 13. Exact Files Likely to Change

| File | Change |
|---|---|
| [`scripts/seed_canonical_demo.sql`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/scripts/seed_canonical_demo.sql#L36-L48) | Fix 3 entity ID format errors (`-` → `_`) |
| [`services/api_gateway/customer360/repos.py`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/api_gateway/customer360/repos.py#L392-L470) | Add `resolve_customer_id_for_account()` to `WorkbenchLinkRepository` |
| [`services/api_gateway/routes.py`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/api_gateway/routes.py) | Enrich alert response with `resolved_customer_id` |
| [`frontend/src/components/alerts/AlertDetailPage.tsx`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/components/alerts/AlertDetailPage.tsx) | Handle `related_entity_type='account'` for panel trigger |
| [`frontend/src/components/alerts/__tests__/AlertDetailPage.test.tsx`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/components/alerts/__tests__/AlertDetailPage.test.tsx) | New test: account-type alert shows panel |

**Not changing:** `migrations/`, `services/workbench/`, `InvestigationDetailPage`, `CaseDetailPage`, `CustomerContextPanel`.

---

## 14. Test Strategy

**Frontend:**
- `AlertDetailPage.test.tsx`: account-type alert + resolver returns `CUST_00141` → panel renders.
- `AlertDetailPage.test.tsx`: account-type alert + resolver returns null → panel absent.

**Backend:**
- `WorkbenchLinkRepository`: `resolve_customer_id_for_account('ACC_00412')` → `'CUST_00141'`.
- `WorkbenchLinkRepository`: unknown account → `None`.

**Regression:**
- 261/261 frontend tests pass.
- 20/20 backend Customer 360 tests pass.
- 724 test-artifact alerts continue to show no panel.

---

## 15. Risks / Regression Considerations

| Risk | Severity | Mitigation |
|---|---|---|
| Re-running seed overwrites existing rows | Low | `ON CONFLICT DO NOTHING` — alert_id conflicts skip |
| Account resolver adds cross-DB call on alert load | Low | Single indexed PK lookup, same pattern as existing WorkbenchLinkRepository queries |
| Account in joint_accounts | Low | `accounts.customer_id` is primary holder; joint is a separate table. Document. |
| Test artifact cleanup changes alert count | Medium | Out of 3A.5 scope; no test relies on exact count |

---

## 16. Go / No-Go Recommendation

| Item | Verdict |
|---|---|
| Seed format fix (3 lines) | **GO** — zero risk |
| Account resolver (~10 lines) | **GO** — authoritative FK chain, no schema change |
| Test artifact cleanup (DELETE 724 rows) | **HOLD** — needs explicit user approval |
| Fuzzy/heuristic linkage on test alerts | **NO-GO** — not production data |

---

## Appendix: Evidence Queries (run against live DBs, 2026-08-15)

```sql
-- banking_integration
SELECT COUNT(*), COUNT(CASE WHEN related_entity_type IS NOT NULL THEN 1 END),
       COUNT(CASE WHEN related_entity_type='customer' THEN 1 END),
       COUNT(CASE WHEN related_entity_type='account' THEN 1 END),
       COUNT(CASE WHEN related_entity_type IS NULL THEN 1 END)
FROM alerts;
-- 728 | 4 | 3 | 1 | 724

SELECT title, COUNT(*) FROM alerts GROUP BY title ORDER BY 2 DESC;
-- Seed Alert=672, Test Alert=30, t=21, Smoke Alert=1, (4 canonical demo)

-- banking_dev
SELECT account_id, customer_id FROM accounts WHERE account_id = 'ACC_00412';
-- ACC_00412 | CUST_00141

SELECT customer_id FROM customers WHERE customer_id IN ('CUST_00001','CUST_00921','CUST_00077');
-- all 3 exist with underscore format
```
