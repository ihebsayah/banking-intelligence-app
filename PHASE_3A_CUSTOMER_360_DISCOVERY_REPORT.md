# Phase 3A — Customer 360 Discovery & Canonical Domain Model — Discovery Report

Status: DISCOVERY COMPLETE. No code, endpoints, migrations, frontend pages, or test suites were written in this increment. All conclusions below cite live evidence (schemas, FK constraints, row counts, source code).

---

## 1. Executive Verdict

The banking analytics side of the platform already has a **rich, normalized customer domain**: 74 tables, **64 foreign keys**, and a star-of-stars graph centred on `customers.customer_id`, populated with realistic live data (2,210 customers, 5,210 accounts, 50,210 transactions, 1,500 loan contracts, 606 KYC cases, 500 AML alerts, 206 risk flags).

However, the **operational side (workbench) is fully disconnected from this customer domain**:

1. Workbench entities (alerts, investigations, compliance cases, information requests, approvals, notifications, timeline) run against a **separate PostgreSQL database** (`banking_integration` on :5435) that contains **zero customer data** — not even the `customers` table (0 rows).
2. The entire `services/workbench/` Python package contains **zero references to "customer"** (0 matches across all `.py`, excluding tests). Customer linkage exists only as free-text `related_entity_type`/`related_entity_id` strings on alerts — and 724/727 alerts have them **empty**.
3. There is **no foreign key, no shared ID namespace, no cross-database view** between the two domains.

The two `compliance_cases` tables (main DB: 0 rows, customer_id FK; integration DB: 1,485 rows, operational workbench table) are an **unforced naming collision** that sharpens the split.

A Customer 360 is therefore a **feasibility-cleared but bridge-blocked** increment. The canonical subject model, capability model, auth matrix, page IA, and MVP can all be specified now (below), but **3A.2 cannot be implemented until a data-bridge decision is made** (see §15).

---

## 2. Schema Inventory (Customer Data)

### 2.1 Primary data store — MAIN DB `banking_dev` (container `banking_postgres_main` :5432, `banking_user`)

Created by `init/*.sql` (02–09), **not** by Alembic (`alembic_version` absent from main DB). 74 public tables.

### 2.2 Operational data store — INTEGRATION DB `banking_integration` (:5435, `integration_user`)

Created by Alembic revisions `0001`–`0010` (`alembic_version = 1`). Workbench + outbox + expiry workers connect here (`docker-compose.yml:779`, `INTEGRATION_DATABASE_URL`). **No customer-domain tables are populated** (verified: risk_flags, kyc_cases, aml_alerts, loan_contracts, customer_profiles, relationship_managers, branches, products all **0 rows**; customers/accounts/transactions **0 rows**).

### 2.3 Customer tables and live row counts

| Group | Table | Rows | Notes |
|---|---|---|---|
| Core | `customers` | 2,210 | `id, customer_id, name, email, phone, kyc_verified, risk_score, segment, created_at, updated_at` |
| Extension | `customer_profiles` | 2,000 | DOB, gender, nationality, national_id, passport, marital, employment, employer, annual_income, income_currency, net_worth_band, politically_exposed, pep_details, tax_id |
| Extension | `customer_addresses` | 2,000 | address_line1, city, governorate, postal_code, is_primary |
| Extension | `customer_contacts` | 2,000 | contact_type, contact_value, is_primary, verified |
| Extension | `customer_preferences` | 2,000 | language, contact_channel |
| Extension | `customer_documents` | **0** | |
| Extension | `customer_status_history` | **0** | |
| Extension | `customer_risk_scores` | **0** | |
| Extension | `customer_relationships` | **0** | self-referencing customer graph, unused |
| Risk/Compliance | `risk_flags` | 206 | **live PK is `id`** (agents wrongly assume `flag_id` — see §12) |
| Risk/Compliance | `kyc_cases` | 606 | + kyc_documents, kyc_reviews, kyc_verifications, kyc_expirations (all FK to kyc_case_id/customer_id) |
| Risk/Compliance | `pep_screening` | 13 | |
| Risk/Compliance | `sanctions_screening` | 45 | |
| Risk/Compliance | `aml_alerts` | 500 | alert_id, customer_id, account_id, transaction_id, alert_type, alert_label_fr, severity, status, score, triggered_at, closed_at, analyst_id, resolution |
| Risk/Compliance | `suspicious_activity_reports` | 25 | sar_id, customer_id, alert_id→aml_alerts |
| Risk/Compliance | `compliance_cases` | **0** | compliance_case_id, customer_id, case_type, status, severity, assigned_to, opened_date, closed_date — **name-collides** with workbench table |
| Financial | `accounts` | 5,210 | account_id, customer_id, account_type, status, balance, available_balance, currency, branch_id, created_at |
| Financial | `account_balances` | **0** | |
| Financial | `account_signatories` | **0** | |
| Financial | `joint_accounts` | 250 | account_id, customer_id |
| Financial | `transactions` | 50,210 | transaction_id, account_id, customer_id, amount, transaction_type, status, description, transaction_date |
| Credit | `loan_contracts` | 1,500 | loan_id, customer_id, account_id, branch_id, loan_product_id, loan_type, principal, currency, interest_rate, term_months, installment_amount, disbursement_date, maturity_date, status, outstanding_balance, days_past_due (+ loan_installments, loan_repayments, loan_delinquency_events, loan_restructuring, collateral, guarantees, provisions, non_performing_loans) |
| Relationship | `relationship_managers` | 2,000 | employee_id, customer_id, portfolio_type |
| Org | `branches` | 238 | branch_id, region_id |
| Org | `regions` | 5 | |
| Org | `employees` | 100 | branch_id, department_id, supervisor_id |
| Org | `products` | 210 | + loan_products |
| Governance | `business_glossary` | 37 | synonym→canonical terms |
| Governance | `join_registry` | 28 | explicit join paths |
| Governance | `metric_registry` | 25 | source_tables metadata |
| IAM | `users` | 6 | Keycloak-linked |

### 2.4 Seed provenance

`init/09-tunisian-banking-data-seed.sql` (86,425 lines, 36,341 INSERTs): `CUST_00001…`, `ACC_00001…`, `AML_0001…`, `LOAN_00001…`, `BR_001…`, `PROD_*`. Segments `PART_MASS`/`PART_PREM`; AML alert statuses `ouvert`/`clôturé`; loan status `contentieux`. IDs are shared **VARCHAR business keys** across tables (e.g. `accounts.customer_id` = `customers.customer_id`).

---

## 3. Relationship Graph

### 3.1 Live FK constraints (verified from `information_schema`, 64 total)

`customers.customer_id` is the hub. **Inbound FKs (22 relationships):**

`accounts`, `transactions`, `risk_flags`, `aml_alerts`, `kyc_cases`, `kyc_expirations`, `pep_screening`, `sanctions_screening`, `suspicious_activity_reports`, `compliance_cases`, `fee_income`, `profitability_metrics`, `relationship_managers`, `joint_accounts`, `account_signatories`, `customer_addresses`, `customer_contacts`, `customer_documents`, `customer_preferences`, `customer_profiles`, `customer_risk_scores`, `customer_status_history`, plus `customer_relationships` (both `customer_id` and `related_customer_id`).

**Key inter-hub edges:**

| Edge | Join key |
|---|---|
| customers → accounts | `customer_id` |
| customers → transactions | `customer_id` |
| customers → risk_flags | `customer_id` |
| customers → kyc_cases | `customer_id` |
| customers → aml_alerts | `customer_id` |
| customers → loan_contracts | `customer_id` |
| accounts → branches | `branch_id` |
| transactions → accounts | `account_id` |
| aml_alerts → accounts/transactions | `account_id` / `transaction_id` |
| loan_contracts → accounts / loan_products | `account_id` / `loan_product_id` |
| branches → regions | `region_id` |
| employees → branches / departments | `branch_id` / `department_id` |
| suspicious_activity_reports → aml_alerts | `alert_id` |

### 3.2 Agent-side join map (agrees with FKs)

- `services/entity_resolution_agent/semantic_id_mapper.py`: `ENTITY_TO_PRIMARY_KEY` (customer→customer_id, account→account_id, transaction→transaction_id, branch→branch_id, product→product_id, loan→loan_id, risk→flag_id, kyc_case→kyc_case_id, aml_alert→alert_id), `SEMANTIC_JOIN_MAP` (28 pairs), `TABLE_ENTITY_COLUMNS`, `ENTITY_PRIMARY_TABLE`.
- `services/orchestrator/orchestrator_agent.py:527-590`: hardcoded customer templates — `top 10 customers by balance`, `average balance by customer segment`, `customer count by state`, `high-risk customers in new york`, `aml flags by customer`, `kyc status by customer` — all joining on `customers.customer_id = accounts.customer_id`, `accounts.branch_id = branches.branch_id`, `customers.customer_id = risk_flags.customer_id`.
- `services/sql_agent/query_plan_builder.py`: `ENTITY_IDENTITIES`, metric-registry source tables, dimension→grain mapping, documented fan-out (loan_contracts × accounts duplicates rows, ~line 935).
- `services/schema_agent/schema_matcher.py`: domain→table map (compliance_analysis → risk_flags, kyc_cases, compliance_violations; risk_analysis → risk_flags).

### 3.3 The missing bridge (the defining finding)

- Workbench operational tables in `banking_integration` have **no FK to any customer table** (only intra-workbench FKs exist).
- `alerts.related_entity_type`/`related_entity_id` are **unvalidated VARCHAR free-text** (models.py, schemas/alerts.py). Live: 724/727 empty; 2 = `customer`, 1 = `account` (test fixtures).
- `services/workbench/` contains **0** occurrences of "customer" in non-test Python.

**Graph conclusion:** the customer graph is complete and queryable *within* `banking_dev`; the operational graph is complete *within* `banking_integration`; the two graphs **do not intersect**.

---

## 4. API & Frontend Coverage

### 4.1 Customer-facing API (api_gateway, `services/api_gateway/routes.py`)

- `GET /dashboard/overview` — `total_customers, total_accounts, active_accounts, total_deposits, monthly_transactions, high_risk_customers`; guarded `require_roles("business")` = {analyst, manager, admin}.
- `GET /risk/overview` — risk_flags × customers aggregates (avg_risk_score, high_risk_customer_count, kyc_incomplete_count).
- `GET /dashboard/kpis`, `GET /kpi/catalog`, `GET /dashboard/chart`, `GET /query` (NL→SQL), `GET /query/history`.
- Workbench proxy `/{path:path}` → rewrites via `_WORKBENCH_PREFIX_MAP` (`alerts|cases|investigations|information-requests|approval-requests|notifications|admin/outbox|admin/orphan-assignments` → `api/v1/…`), forwards `X-Test-User`. **No proxy route touches customer data.**

### 4.2 Auth (services/api_gateway/auth.py, services/shared/authorise.py)

- JWT (Keycloak) with `MOCK_USERS` fallback; `analyst_001` legacy perms: `read:customers, read:accounts, read:transactions, read:risk_flags`.
- `_map_keycloak_roles_to_application_role` in routes.py.
- Authorise engine: `AuthorisationError` hierarchy (`PermissionDeniedError`, `ScopeDeniedError`, `OwnershipDeniedError`, `ProhibitedComboError`, `ActionUnknownError`); scope-based (user_scopes/organisation_scopes) + ownership (assigned/own) + permission checks; out-of-scope entities return **404** (leakage-safe).

### 4.3 Frontend

- Customer-touching pages: `BankingDashboard` (total_customers, high_risk_customers, recent txs showing `customer_id`), `Branches` (active_customers, customer_growth_rate), `RiskPage` (risk segments + flags), `CompliancePage`, `Assistant`/`AiAssistantPanel` (NL→SQL via orchestrator).
- Workbench pages (`components/{alerts,investigations,cases,informationRequests,approvals}/…`): **0 occurrences of "customer"** — no customer context anywhere in operational UI.
- `frontend/src/types/api.ts` mirrors the API contract (DashboardOverview, RiskOverview, RiskFlag, RiskSegment, ComplianceOverview).

### 4.4 Coverage verdict

Aggregation of customer data: **present** (dashboard/risk/query). **Operational touchpoint of customer data: absent.** No single endpoint returns a unified customer view (identity + accounts + risk + KYC/AML + loans + operational alerts/cases/investigations).

---

## 5. Capability Model

Business capabilities already exercisable today (each backed by live schema + agent join maps):

1. **Customer Identity & Profile** — customers + customer_profiles/addresses/contacts/preferences.
2. **Product Holding** — accounts (single + joint via joint_accounts), products, loan_contracts.
3. **Transaction & Activity** — transactions (50k), recent activity.
4. **Risk Assessment** — risk_flags, risk_score, customer_risk_scores (empty), segments.
5. **KYC/AML & Sanctions** — kyc_cases, pep_screening, sanctions_screening, aml_alerts, SARs.
6. **Credit & Collections** — loan_contracts + installments/repayments/delinquency/restructuring/NPL/provisions.
7. **Relationship Management** — relationship_managers, employees, branches, regions.
8. **Operational Response** (disconnected from customers) — alerts, investigations, cases, decisions, IRs, approvals, notifications, timeline.
9. **Analytics/Governance** — KPI registry, metric registry, business glossary, join registry.

**Missing capability (the 360 itself):** cross-domain entity view joining 1–8 on `customer_id`, plus enrichment of operational records with `customer_id` (currently opaque `related_entity_id`).

---

## 6. Field Classification

| Category | Tables | Cardinal fields |
|---|---|---|
| Core identity | `customers` | customer_id, name, email, phone, kyc_verified, risk_score, segment |
| Demographic/AML identity | `customer_profiles` | date_of_birth, gender, nationality, national_id, passport_number, marital_status, employment_status, employer_name, annual_income, income_currency, net_worth_band, politically_exposed, pep_details, tax_id |
| Contact/preference | `customer_addresses`, `customer_contacts`, `customer_preferences` | address, phone/email/type, language, contact_channel |
| Financial position | `accounts`, `account_balances`(empty), `joint_accounts`, `transactions`, `fee_income`(empty), `interest_income` | balance, available_balance, currency, amount, tx_type/status/date |
| Credit | `loan_contracts` + installments/repayments/delinquency/restructuring/collateral/guarantees/provisions/NPL | principal, rate, term, outstanding_balance, days_past_due, status |
| Risk | `risk_flags`, `customer_risk_scores`(empty) | flag_type, severity, resolved |
| KYC/AML | `kyc_cases`+docs/reviews/verifications/expirations, `pep_screening`, `sanctions_screening`, `aml_alerts`, `suspicious_activity_reports` | case status, screening status/result, alert severity/status/score |
| Relationship/org | `relationship_managers`, `employees`, `branches`, `regions` | portfolio_type, branch/region |
| Compliance ops | `compliance_cases`(main, empty) | case_type, status, severity, assigned_to |
| Metadata | `business_glossary`, `metric_registry`, `table_metadata`, `column_metadata`, `join_registry` | canonical terms, sources, joins |

---

## 7. Canonical Customer Subject Model — Recommendation

Recommend a **logical, federation-friendly subject model** (not a new master table). All fields already exist; nothing new is invented.

```
CustomerCore (source of truth: customers + customer_profiles)
├─ identity      : customer_id, name, email, phone, segment, kyc_verified
├─ demographic   : gender, dob, nationality, national_id, employment, annual_income, net_worth_band, pep
├─ risk          : risk_score, risk_flags[] (severity/resolved), highest-flag severity
├─ product       : accounts[] (type/status/balance/currency/branch), loans[] (status/outstanding/dpd)
├─ activity      : tx counts, sums (30/90d), last-transaction-date
├─ compliance    : kyc_cases[] (status), aml_alerts[] (severity/status), pep/sanctions status, SARs[]
└─ relationship  : relationship_managers[], branches[], regions[]
CustomerOperations (bridge target — workbench enrichment)
└─ alerts[], investigations[], compliance_cases[], information_requests[], approvals[]
```

**Bridge design decision required (options):**
- **A. Logical only (recommended for 3A.2 scope):** a read model/API in `banking_dev` exposing CustomerCore; operational side stays separate with `related_entity_id` resolved to `customer_id` at query time via an ID-resolution service (no cross-DB writes).
- **B. Physical sync:** replicate the customer ID namespace (id-only, or id+core) into `banking_integration` for FK enforcement on workbench entities.
- **C. Consolidation:** move operational entities to `banking_dev` (breaks the existing two-DB isolation; large change).

Do **not** introduce new fields (e.g. credit limit, KYC tier enum) that do not already exist in the schema — that violates the discovery constraint.

---

## 8. Auth Matrix

| Capability | Minimum permission | Roles holding it (source: `0005_add_permission_seeds.py`, `0009`, `0010`) |
|---|---|---|
| Read customer aggregates | `read:customers` (legacy) | analyst (MOCK_USERS), admin |
| Read accounts/transactions | `read:accounts` / `read:transactions` | analyst, admin |
| Read risk data | `read:risk_flags` | analyst, admin |
| Workbench access | `workbench:access` | all business roles |
| Alerts (own/assigned → broad) | `alert:read_assigned` → `alert:read` | analyst/manager/compliance/admin per seed |
| Alert actions | `alert:assign/acknowledge/dismiss/investigate/transition` | role-gated per seed |
| Investigations | `investigation:read_own` → `investigation:read`, `investigation:update`, `investigation:review` | per seed |
| Cases | `case:read_assigned` → `case:read`, `case:transition`, `case:decision`, `case:assign` | per seed |
| IRs | `info_request:create/accept/return` | per seed |
| Comments | `comment:view_internal_content` | per seed |
| Admin | `admin:orphan_monitor`, admin role | admin |
| Scope | `user_scopes`/`organisation_scopes` | per-user |

Pattern to reuse for Customer 360: **assigned/own-first, broad-read-fallback, 404-on-out-of-scope** (entity_access.py), object-level `customer:read_assigned`/`customer:read` analogues would follow the identical contract.

---

## 9. Page IA

Existing routes (`frontend/src/App.tsx`): Dashboard, BankingDashboard, Branches, Risk, Compliance, KPI, Reporting, Assistant, Workbench (Alerts/Investigations/Cases/IR/Approvals), Admin.

**Proposed 360 IA** (front-end only, no new backend needed for IA):
- `/workbench/customers/:customerId` → Customer 360 detail (tabs: Overview / Accounts & Loans / Transactions / Risk & KYC-AML / Alerts & Cases).
- `AlertDetail`/`CaseDetail`/`InvestigationDetail` gain a read-only "Customer context" panel resolving `related_entity_id` when it is a customer.
- Customer navigation: drill-down from BankingDashboard/RiskPage rows; link-back from workbench detail pages.

---

## 10. Operational Actions Required (pre-implementation, none taken this increment)

1. **Populate the ID bridge:** decide Option A/B (§7) and, if B, seed customer-id namespace into `banking_integration`.
2. **Standardize `related_entity_type`:** add allowed-value validation (`customer|account|transaction|alert`) + required-non-null for entity-linked alert types (currently free-text, 724/727 empty).
3. **Resolve the `risk_flags` PK mismatch:** live PK = `id`; `semantic_id_mapper.py` and `schema_agent/progressive_schema.py` assume `flag_id`. Fix the maps or alias.
4. **Remove the `cards` phantom:** `query_plan_builder.py` lists `cards→card_id`; no `cards` table exists in the live schema or `init/` — either drop the entry or add the table deliberately.
5. **Fix orchestrator `risk_flags.id`** reference (line 568 uses `risk_flags.id`, line 560/570 mixes `flag_type` counting — align to one key).
6. **Reconcile the `compliance_cases` name collision** (main 0-row compliance table vs integration 1,485-row workbench table) — rename or document the boundary in the glossary.
7. **Seed empties** where the 360 needs them: `customer_risk_scores`, `customer_relationships`, `fee_income`, `customer_documents`, `customer_status_history`, `account_balances`, `account_signatories`.

---

## 11. MVP Scope (for the subsequent build increment, NOT executed here)

- Customer 360 read API in api_gateway: `GET /customers/{customer_id}/overview` returning CustomerCore (identity + risk + products + compliance + recent alerts/cases joined via bridge).
- ID-bridge (Option A resolver or Option B sync seed).
- Customer 360 detail page at `/workbench/customers/:customerId` with tabs from §9.
- Permission `customer:read_assigned`/`customer:read` following the existing workbench contract.
- Out of MVP: physical consolidation, master-data management, customer merge/dedupe (customer_relationships), operational write-through.

## 12. Gaps

| # | Gap | Evidence |
|---|---|---|
| G1 | No cross-DB customer linkage | two DBs, 0 workbench "customer" refs, alerts related_entity empty |
| G2 | No FK on alerts.related_entity_* | models.py/schemas/alerts.py free-text |
| G3 | risk_flags PK mismatch (`id` vs `flag_id`) | live columns vs semantic_id_mapper/progressive_schema |
| G4 | Phantom `cards` entity | query_plan_builder ENTITY_IDENTITIES vs live schema/init |
| G5 | `compliance_cases` name collision | main(0) vs integration(1485) |
| G6 | Empty customer extension tables | §2.3 row counts |
| G7 | No composite KYC status materialized | kyc_verified flag only; kyc_cases separate |
| G8 | No unified 360 endpoint | api_gateway route inventory |
| G9 | Orchestrator key inconsistency | `risk_flags.id` vs `flag_id` usage |

## 13. Implementation Plan (future increments)

1. **3A.2** — data bridge (decide §7 option) + `customer:read_*` permissions seed + CustomerCore SQL view/read model in `banking_dev`.
2. **3A.3** — api_gateway 360 endpoint(s) + ID-resolution service for workbench `related_entity_id`.
3. **3A.4** — frontend Customer 360 page + customer-context panels in workbench details.
4. **3A.5** — operational entity customer-enrichment (alerts/cases/investigations carry customer_id), related_entity validation.
5. **3A.6** — empty-table seeding, gap remediation (G3/G4/G5/G9), closure report.

## 14. Test Strategy

- **FK/integrity:** assert 64 FKs intact; assert every alert/investigation/case with `related_entity_type='customer'` resolves to an existing `customers.customer_id` (currently 0/3 do).
- **Join-path regression:** reuse orchestrator/sql_agent template tests for the §3.2 joins.
- **Authz:** extend workbench contract tests to `customer:read_assigned`/`customer:read` + scope/ownership + 404-on-out-of-scope.
- **Data-volume:** CustomerCore query must return ≤ 1 row per customer (fan-out guard for loans × accounts, per query_plan_builder note).
- **E2E:** NL query "customer 360 for CUST_00001" → resolved join across both DBs.

## 15. Readiness Verdict

**READY WITH CONDITIONS — conditional on the data-bridge decision (§7).**

- The **analytics foundation is fully ready**: complete normalized customer schema, 64 verified FKs, live realistic data, working aggregation endpoints and NL→SQL paths.
- The **360 unification is blocked today** by the two-database isolation and the absent customer-ID linkage in the operational layer (G1/G2). No amount of front-end work can surface a unified customer view until the bridge exists.

Condition: before 3A.2 implementation begins, the owner must pick bridge **Option A (logical resolver — recommended, smallest change)** or **Option B (ID sync)**. Under A, implementation can proceed immediately. Under the current state with no decision, 3A.2 is BLOCKED on data-bridge selection.
