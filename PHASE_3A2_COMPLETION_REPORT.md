# Phase 3A.2 — Customer 360 Read Bridge: Logical ID Resolver + Permission Seeds + Gateway Read API — Completion Report

Status: COMPLETE. Live verification green against the running stack (Keycloak-gated gateway, both Postgres DBs, audit agent). Bridge option **A (logical resolver)** implemented — no cross-DB writes.

---

## 1. Task Definition & Scope

Per `PHASE_3A_CUSTOMER_360_DISCOVERY_REPORT.md` §13 (implementation plan) and §11 (MVP), the 3A.2 increment covers:

1. **Data bridge — Option A (logical resolver).** Customer core stays authoritative in `banking_dev`; workbench entities in `banking_integration` are joined at query time via `related_entity_id → customer_id` resolution. No cross-DB writes.
2. **`customer:read_*` permission seeds** following the existing workbench permission contract.
3. **CustomerCore read model** in the gateway (identity, demographic, risk, product, activity, compliance, relationship + CustomerOperations bridge sections).
4. **Gateway read API** `GET /api/v1/customers/{customer_id}/overview` (+ `GET /transactions`), gated by scope and permission, emitting audit.

Out of scope (deliberately, per discovery §11): physical consolidation, master-data management, customer merge/dedupe, operational write-through, and the frontend 360 detail page (3A.4).

## 2. Authoritative Documents Followed

- `PHASE_3A_CUSTOMER_360_DISCOVERY_REPORT.md` — §7 subject model + bridge option A, §8 auth matrix pattern, §11 MVP, §13 plan items 1–2, §14 test strategy
- `services/shared/authorise.py` + workbench `entity_access.py` contract — assigned/own-first, broad-read-fallback, **404-on-out-of-scope** (leakage-safe)
- `migrations/versions/0006_deprecate_manager_role.py` — manager role is deprecated in the workbench layer (`workbench:access` prohibited, no org scope); the bridge inherits this

## 3. Design Decision

**Option A logical resolver** was already the discovery recommendation and is what the phase's blocked-state condition required. Concretely:

- Main DB (`banking_dev`) is the authority for `customers`/`customer_profiles`/`accounts`/`transactions`/`risk_flags`/`kyc_cases`/`relationships`/`branches` (via `banking_postgres_main`).
- Integration DB (`banking_integration`) is the authority for workbench operations (`alerts`, `investigations`, `cases`, etc.), joined only by `related_entity_id` equality with a real `customers.customer_id`.
- The service layer composes a single `Customer360Data` from the two pools; `data_quality.unresolved_workbench_reference` flags bridge rows that reference phantom customer IDs (0 of the 3 seeded workbench customer-links resolve — known gap G1).

This makes the resolution bi-directionally safe: an out-of-scope or nonexistent customer returns **404 `CUSTOMER_NOT_FOUND`**, never an empty-but-200 "leak".

## 4. Baseline Backend Tests

`PYTHONPATH=services/api_gateway:services ./testenv/bin/python3 -m pytest services/api_gateway/customer360/tests services/shared/tests -q` → **71 passed** (shared) before the increment; **82 passed** after (71 shared + 11 new). No existing test weakened.

## 5. Files Created

- `services/api_gateway/customer360/__init__.py` — package exports (`Customer360Service`, models, exception)
- `services/api_gateway/customer360/models.py` — typed DTO contract (identity/demographic/risk/product/activity/compliance/relationship + bridge)
- `services/api_gateway/customer360/repos.py` — `Customer360Repository` (main-DB queries) + `WorkbenchBridgeRepository` (integration-DB enrichment)
- `services/api_gateway/customer360/service.py` — composition, PII masking, section gating, data-quality + audit payloads
- `services/api_gateway/customer360/tests/__init__.py`
- `services/api_gateway/customer360/tests/test_customer360_service.py` — 11 unit tests (faked repos, real service logic)
- `init/11-phase3a2-customer-permission-seeds.sql` — permission/role seed, applied by gateway startup migration runner

## 6. Files Modified

- `services/api_gateway/routes.py` — `_get_integration_db`, `_get_customer360_service`, `_customer_audit_entry`, `CustomerTransactionsResponse`; endpoints `GET /api/v1/customers/{customer_id}/overview` (routes.py:2828) and `GET /customers/{customer_id}/transactions` (routes.py:2884), registered **before** the workbench proxy catch-all
- `services/api_gateway/main.py` — lifespan opens/closes `integration_db` pool from `INTEGRATION_DATABASE_URL` (main.py:128–133, 143–144)
- `services/api_gateway/customer360/service.py` — `get_transactions`; fixed `_build_screening` guard to `if not row` (was `is None`; `_safe` returns `[]` on failure)
- `services/api_gateway/customer360/repos.py` — `fetch_recent_transactions(limit, offset)`, new `fetch_transaction_count`

## 7. Permission Model Seeded

`init/11-phase3a2-customer-permission-seeds.sql` adds seven permissions and role grants (idempotent):

| Permission | admin | compliance | analyst | manager |
|---|---|---|---|---|
| `customer:read_basic` / `read_financial` / `read_transactions` / `read_kyc` / `read_risk` | ✓ | ✓ | ✓ | ✓ |
| `customer:read_compliance_history` (workbench links) | ✓ | ✓ | ✗ | ✗ |
| `customer:read_pii` | ✓ | ✓ | ✗ | ✗ |
| `customer:read` (aggregate gate) | ✓ | ✓ | ✓ | ✓ |

Enforcement: overview gates on **any** `customer:read_*`; `workbench_links` section requires `customer:read_compliance_history`; PII fields are masked unless `customer:read_pii`; transactions require `customer:read_transactions`. Org scope is enforced per-user from `user_scopes`/`organisation_scopes` (out-of-scope → 404).

## 8. Tests Added (+11)

`test_customer360_service.py` covers: overview 200 for all roles; PII masked without `read_pii` and unmasked with it; `workbench_links` section present only with `read_compliance_history`; analyst/manager/compliance differences; transactions `(summary, rows, total, quality, audit)`; unknown customer → `CustomerNotFound`; audit payload structure. Scope defaults to `hq_main` (matches live seed). Output: **11 passed**.

## 9. Live Verification (running stack)

Gateway was recreated to pick up the new env: `docker compose -f docker-compose.yml -f docker-compose.integration.yml up -d --force-recreate --no-deps api-gateway`. `/health` 200; lifespan logs `Integration Database connection pool ready`. Auth is strict Keycloak (`AUTH_PROVIDER=keycloak`, `AUTH_COMPATIBILITY_MODE=false`).

| Case | Token | Result |
|---|---|---|
| Admin `kc_admin_001` → overview `CUST_00001` | `c360_token` | **200**; 13 sections: customer `Salma Ben Amara / PART_MASS`, unmasked `national_id=12126998`, `annual_income=16107.13`, `risk_score=0.42`, `recent_transactions[0]=TXN_013484 -322.00`, `data_quality.unavailable_sections=[]` |
| Admin → transactions `CUST_00001` | same | **200**; `total_count=33`, `recent_transactions` paginated with `limit`/`offset`, `transaction_summary.scope=hq_main` |
| Compliance `kc_compliance_001` → overview `CUST_00001` | `c360_compliance_token` | **200**; all 7 sections granted, `fields_masked=[]`, unmasked PII |
| Analyst `kc_analyst_001` → overview `CUST_00001` | `c360_analyst_token` | **200**; PII masked (`national_id=****6998`, `email=****l.tn`, `phone=****2856`, `dob=****1-23`, `annual_income=****7.13`); `workbench_links=[]` (no `read_compliance_history`) |
| Analyst/compliance → `CUST_99999` | — | **404 `CUSTOMER_NOT_FOUND`** |
| Manager `kc_manager_001` → overview | — | **404** — correct: manager is a deprecated role (migration 0006) with **no `user_scopes` row**; out-of-scope is leakage-safe 404, matching workbench behavior |

**Workbench-links bridge proof:** the 3 seeded workbench customer links (`CUST-00921`, `CUST-00077`, `CUST-00412` account) reference phantom IDs that resolve to **zero** real customers (gap G1). A temporary alert linked to real `CUST_00001` was inserted, the compliance overview returned it:

```
workbench_links: [{'entity_type':'alert','entity_id':'60b9be26-…','status':'acknowledged',
                   'assigned_to':'analyst_001','scope_id':'hq_main','source':'workbench'}]
```

The temp row was deleted afterwards (verified `0` remaining).

## 10. Audit Trail (live)

`banking_audit_agent` captured every access in `audit_log` (`banking_postgres_audit` / `audit_logs`):

- `analyst_001 customer_360_access success` — sections granted `[relationship, financial, transactions, kyc_aml, risk]`, **`fields_masked: [national_id, email, phone, date_of_birth, annual_income, net_worth_band, pep]`**, `scope_used=[hq_main]`
- `compliance_001 customer_360_access success` — all sections incl. `workbench_links`, `fields_masked: []`
- `compliance_001 customer_transactions_access success`
- `manager_001 customer_360_access rejected` — `customer_not_found_or_out_of_scope` (×2)
- `compliance_001` on `CUST-00921 rejected` — `customer_not_found_or_out_of_scope`

## 11. Final Regression Count

`PYTHONPATH=services/api_gateway:services ./testenv/bin/python3 -m pytest services/api_gateway/customer360/tests services/shared/tests -q` → **82 passed** (11 + 71). No existing test weakened.

## 12. State Changes Made During Verification

- Reset Keycloak test-user password `kc_analyst_001` → `Analyst123!` (user exists and is enabled; the stored password did not match the documented credential). The user's `identity_provider_subject` is unchanged, so scope/permission mappings are intact.

## 13. Known Gaps (carried forward, unchanged)

- **G1** — the 3 workbench customer-links reference phantom IDs; 0/3 resolve to a real `customers.customer_id`. The bridge reports them via `data_quality.unresolved_workbench_reference` and surfaces nothing under `workbench_links` for those customers (correct, leakage-safe). Fixing requires 3A.5 `related_entity_*` validation/standardization + populating the ID bridge.
- G2–G9 from the discovery report are out of 3A.2 scope (see §14).

## 14. Out of Scope & Next Steps

- **3A.3** — ID-resolution service surfacing for the frontend + `related_entity_id` validation hook in workbench reads
- **3A.4** — frontend Customer 360 detail page at `/workbench/customers/:customerId` (tabs per discovery §9)
- **3A.5** — `related_entity_type` allowed-value validation, `customer_id` enrichment on alerts/cases/investigations
- **3A.6** — empty-table seeding + gap remediation (G3 `risk_flags` PK, G4 phantom `cards`, G5 `compliance_cases` collision, G9 orchestrator key consistency)

## 15. Files Reference

- `services/api_gateway/customer360/__init__.py`, `models.py`, `repos.py`, `service.py`
- `services/api_gateway/customer360/tests/test_customer360_service.py`
- `services/api_gateway/routes.py:2828` (overview), `:2884` (transactions), `:740` (audit entry)
- `services/api_gateway/main.py:128` (integration pool)
- `init/11-phase3a2-customer-permission-seeds.sql`

## 16. Readiness Verdict

**READY.** The 3A.2 data bridge is implemented as the discovery-recommended Option A logical resolver with no cross-DB writes; `customer:read_*` permissions are seeded and enforced (permission + org scope + 404-on-out-of-scope, mirroring the workbench contract); the gateway read API (`overview` + `transactions`) is live, PII-masking verified end-to-end for analyst vs admin/compliance, workbench-links enrichment verified with a real linked alert, and every access is audit-logged. 82 backend tests pass; live evidence is reproduced above. The remaining work is 3A.3/3A.4 (frontend + resolver hardening) and 3A.5/3A.6 (linkage validation + gap remediation).
