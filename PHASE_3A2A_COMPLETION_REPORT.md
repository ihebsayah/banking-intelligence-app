# Phase 3A.2a — Customer 360 Authorization & Privacy Hardening — Completion Report

Status: **COMPLETE.** Live verification green against the running stack (Keycloak-gated gateway, both Postgres DBs, audit agent). The 3A.2 read bridge now enforces a least-privilege access matrix (Analyst masked / Compliance full-with-scope / Admin metadata-only / Manager denied), a hardened transactions endpoint, centralized PII masking, and denial auditing.

---

## 1. Task Definition & Scope

Phase 3A.2 delivered the Customer 360 read bridge (logical resolver, `customer:read_*` seeds, gateway read API). Phase 3A.2a hardens that bridge's **authorization and privacy** surface:

1. Verify the current effective access matrix against the live DB.
2. Freeze the approved least-privilege matrix.
3. Correct the permission seeds (forward repair).
4. Enforce **section-level response gating** per granted permission.
5. Harden the **transactions endpoint** (permission gate, not just scope).
6. Centralize **PII masking** with consistent, non-leaky rules.
7. Preserve **need-to-know**: compliance history and full PII remain scope-limited; admin gets a metadata-only view.
8. Harden **audit** (denial events + richer payload, no raw PII in audit).
9. Add **~8 focused tests** only (no large suite).
10. **Live verification** with the four Keycloak users.
11. **Regression** of existing suites.

Out of scope (unchanged from 3A.2): SQL aggregation, cross-DB composition, frontend, customer mutations, Workbench workflows, and the large existing test suite.

## 2. Authoritative Documents Followed

- `PHASE_3A2_COMPLETION_REPORT.md` — the 3A.2 bridge design and permission contract
- `services/shared/authorise.py` + workbench `entity_access.py` — assigned/own-first, broad-read-fallback, **404-on-out-of-scope**
- `init/11-phase3a2-customer-permission-seeds.sql` — the permission seed file corrected here
- `migrations/versions/0006_deprecate_manager_role.py` — manager role deprecated in the workbench layer; the Customer 360 bridge inherits it

## 3. Approved Access Matrix (frozen)

| Section | Analyst | Compliance (in scope) | Admin | Manager |
|---|---|---|---|---|
| identity + segment + branch/RM metadata | ✅ | ✅ | ✅ (display name, no contact/PII) | ❌ |
| email / phone / DOB / national_id / passport / tax_id / income / net_worth | masked | unmasked only with `customer:read_pii` | suppressed (null) | ❌ |
| accounts + balances | ✅ | ✅ | ❌ | ❌ |
| transactions | ✅ | ✅ | ❌ | ❌ |
| loans (amounts) | ✅ | ✅ | ❌ | ❌ |
| KYC status | status-level only | full | ❌ | ❌ |
| PEP / sanctions detail (matched name) | masked | full (with `read_pii`) | ❌ | ❌ |
| risk score / flags | ✅ | ✅ | classification summary only | ❌ |
| AML alerts metadata | ✅ (assigned) | ✅ | ❌ | ❌ |
| compliance history (SAR, case decisions) | ❌ | ✅ (`customer:read_compliance_history`) | ❌ | ❌ |
| admin metadata (counts, classification, data-quality) | ❌ | ❌ | ✅ (`customer:read_operational_metadata`) | ❌ |

## 4. Live Defect Confirmed (before)

Live `role_permissions` query (before repair):

- `admin` held **all 7** `customer:*` grants including `customer:read_pii` (PII-unmasking admin, against the approved matrix).
- `manager` held all 5 detail grants (`read_basic/financial/transactions/kyc/risk`) despite the deprecated role.
- `analyst` held 5 (correct subset), `compliance` held all 8 (correct).

## 5. Design Decision

- **Forward repair, not re-seed.** The corrected `init/11-phase3a2-customer-permission-seeds.sql` is idempotent (`DELETE` + `INSERT ... ON CONFLICT DO NOTHING`) and is re-applied on every gateway start via `apply_migrations`, so the live DB converges without destructive reseeding. No permission *definitions* were deleted.
- **Section gating at the service layer.** Each `Customer360Overview` section maps to a required permission (`SECTION_PERMISSIONS`); a section absent from the user's grant set is returned as `null`/`[]` — never filtered-in-place or replaced with placeholder data, so no section leaks partial rows.
- **Admin gets a dedicated metadata-only section** (`admin_metadata`) instead of a degraded full view — balances/loans/KYC/PEP are structurally absent for admin.

## 6. Permission Seed Corrections

Rewrote `init/11-phase3a2-customer-permission-seeds.sql`:

- Added permission definitions `customer:read` (overview umbrella) and `customer:read_operational_metadata`.
- `analyst` → 6 grants: `read`, `read_basic`, `read_financial`, `read_transactions`, `read_kyc`, `read_risk` (no `read_pii`, no `read_compliance_history`).
- `compliance` → 8 grants: analyst's 6 + `read_compliance_history` + `read_pii`.
- `admin` → 3 grants: `read`, `read_basic`, `read_operational_metadata`. **All 5 detail grants deleted.**
- `manager` → **all `customer:%` grants deleted.**

Live DB verified post-application: analyst=6, compliance=8, admin=3, manager=0.

## 7. Section-Level Response Gating

`service.py`:

- `SECTION_PERMISSIONS` maps each section to its permission; `ALL_SECTIONS` now includes `admin_metadata`.
- `_build_identity` honors `suppress_pii` (admin: contact/PII → `None`, never masked tokens) vs `mask_pii` (analyst: masked tokens).
- `_build_kyc_aml` returns `kyc_case_id = None` when masking (status-level only).
- `_build_screening` returns `matched_name = None` when masking.
- Workbench links (`workbench_links`) require `_WORKBENCH_LINK_PERMISSIONS` = `customer:read_compliance_history` **or** `customer:read_operational_metadata` — admin sees assignment metadata links, compliance sees full history links, analyst sees none.

## 8. Admin Metadata-Only View

- New `AdminCustomerMetadata` model (`models.py`): `account_count`, `active_account_count`, `product_count`, `loan_count`, `risk_score`, `risk_classification`, `active_flag_count`, `highest_active_severity`, `kyc_status`.
- New `repos.fetch_customer_metadata_counts` selects **counts only** — deliberately no `balance`/`amount`/monetary columns, so a metadata viewer never touches monetary values.
- `Customer360Overview.admin_metadata` populated only for grant holders; other sections returned empty.

## 9. Transactions Endpoint Hardening

`routes.py`:

- `require_any_permission_audited("customer:read_transactions", action="customer_transactions_access")` replaces the previous dependency for `GET /api/v1/customers/{id}/transactions` — a caller without the permission is **denied 403 before scope resolution**, and the denial is audit-logged with `status=rejected`, `reason=missing_permission`, `permissions_required=[...]`.
- `_CUSTOMER_READ_PERMISSIONS` (overview gate) extended with `customer:read` + `customer:read_operational_metadata` so admin (metadata view) passes the overview gate while still being denied transactions.

## 10. Centralized PII Masking

Replaced ad-hoc last-4 masking with a single `_mask_field` policy in `service.py`:

| Field | Masked form | Rationale |
|---|---|---|
| `national_id` / `passport_number` / `tax_id` | `***` | complete suppression — no length leak |
| `annual_income` / `net_worth_band` | `***` | complete suppression |
| `date_of_birth` | `****-**-**` | complete suppression |
| `email` | `f***@***.com` (first char + domain TLD) | minimal label, no address recovery |
| `phone` | `****2856` (last 4) | standard practice |
| `pep` | stays boolean | no PII content |

Masked fields are also reported in the audit `fields_masked` list.

## 11. Need-to-Know & Compliance Scope Handling

- Compliance history and SAR content never surface without `customer:read_compliance_history`; full PII never surfaces without `customer:read_pii`.
- Out-of-scope customers return **404 `CUSTOMER_NOT_FOUND`** (leakage-safe, matching the workbench contract) — verified live by temporarily swapping `compliance_001`'s `hq_main` scope for a non-overlapping branch scope (see §15), then restored.

## 12. Audit Hardening

- New `require_any_permission_audited` dependency emits an **`AuditStatus.REJECTED`** audit event (`reason=missing_permission`, `permissions_required`) before raising 403.
- `_build_audit` payload extended with `endpoint`, `sections_denied`, and `result_status`.
- Audit payloads contain **no raw PII** (asserted by test `test_audit_payload_has_no_raw_pii`).
- Live `audit_log` rows confirm both `customer_360_access` and `customer_transactions_access` success + rejected entries with the correct `user_id` and `error_message` (`missing_permission`, `customer_not_found_or_out_of_scope`).

## 13. Tests Added/Updated

`services/api_gateway/customer360/tests/`:

- Updated 2 existing tests for the new masking policy and new audit keys.
- New in `test_customer360_service.py`: `test_admin_overview_is_metadata_only`, `test_admin_serialized_response_has_no_forbidden_fields` (walks every leaf of the serialized Admin response; asserts forbidden keys are empty and no raw PII values appear), `test_analyst_kyc_is_status_level`, `test_compliance_sees_pep_matched_name_with_pii`, `test_audit_payload_has_no_raw_pii`, plus `FakeRepository.fetch_customer_metadata_counts`.
- New `test_customer360_routes.py`: route-level guards with a faked service — manager 403 even with a scope assigned (guard fires before the service is called), admin transactions 403 + overview 200, analyst transactions 200, out-of-scope compliance 404.

Result: **20 passed** in `customer360/tests`.

## 14. Regression

Standalone runs (pre-existing cross-file `import main` sys.path quirk makes combined runs unstable — reproduced identically at HEAD, so no new breakage):

- `services/shared/tests` → **71 passed**
- `tests/test_keycloak_auth.py` → **31 passed** (installed `cryptography` into `testenv/` for the JWT-sig test — test-only dep missing from the local env)
- `tests/test_request_gating.py` → **17 passed**
- `tests/test_portal_endpoints.py` → **52 passed**

No existing test weakened.

## 15. Live Verification Evidence (Keycloak users → real gateway)

`GET /api/v1/customers/CUST_00001/overview` and `/transactions` on `localhost:8000`:

| Caller | Overview | Transactions | Verified payload |
|---|---|---|---|
| `analyst_001` (kc_analyst_001) | 200 | 200 | PII masked: email `s***@***.tn`, phone `****2856`, `national_id "***"`, DOB `****-**-**`, income `***`; balances visible; `admin_metadata: null` |
| `compliance_001` | 200 (in scope), 404 out-of-scope | — | Unmasked PII (`12126998`, `21659742856`, `1967-11-23`, income `16107.13`, `<50K`) with `customer:read_pii`; 404 `CUSTOMER_NOT_FOUND` when scope swapped to a non-overlapping branch |
| `admin_001` (kc_admin_001) | 200 | **403** | `admin_metadata` present (`account_count 4`, `risk_classification medium`, `active_flag_count 0`); `financial_summary/accounts/recent_transactions` empty; all contact/PII `null`; 403 `INSUFFICIENT_PERMISSIONS` + `permissions_required: ["customer:read_transactions"]` |
| `manager_001` (kc_manager_001) | **403** | **403** | `INSUFFICIENT_PERMISSIONS`, requires one of the `customer:read_*` list — denied before any scope resolution |

`audit_log` (banking_postgres_audit / `audit_logs`) captured: analyst/compliance/admin overview successes, admin transactions `rejected / missing_permission`, manager overview `rejected / missing_permission`, compliance out-of-scope `rejected / customer_not_found_or_out_of_scope`, compliance restored overview success.

State changes made during verification: created and deleted temporary branch scope `branch_oos_temp` for compliance's 404 check; `compliance_001`'s scope restored to `hq_main` (re-verified 200). No Keycloak credentials or other state changed.

## 16. Known Gaps + Readiness Verdict

Known gaps (carried forward, unchanged): G1 phantom workbench customer-links, and G2–G9 from the discovery report remain out of scope (see PHASE_3A2_COMPLETION_REPORT.md §13–14).

**READY.** The 3A.2 bridge now enforces the approved least-privilege matrix at every layer — permission seeds (live DB corrected and re-appliable), section-level response gating, a metadata-only admin view, permission-gated transactions, centralized non-leaky PII masking, and denial auditing with no raw PII in audit payloads. 20 focused tests + 171 regression tests pass; live verification above reproduces the matrix end-to-end for all four Keycloak roles. Remaining work is 3A.3/3A.4 (resolver surfacing + frontend) and 3A.5/3A.6 (linkage validation + gap remediation).

## Files Reference

- `init/11-phase3a2-customer-permission-seeds.sql` — corrected, idempotent forward repair
- `services/api_gateway/customer360/models.py` — `AdminCustomerMetadata`, `KycCaseSummary.kyc_case_id` Optional
- `services/api_gateway/customer360/repos.py` — `fetch_customer_metadata_counts`
- `services/api_gateway/customer360/service.py` — `SECTION_PERMISSIONS`, `_mask_field`, `_build_admin_metadata`, `_build_audit`, `_WORKBENCH_LINK_PERMISSIONS`
- `services/api_gateway/routes.py` — `require_any_permission_audited`, overview + transactions gates
- `services/api_gateway/customer360/tests/test_customer360_service.py`, `test_customer360_routes.py`
