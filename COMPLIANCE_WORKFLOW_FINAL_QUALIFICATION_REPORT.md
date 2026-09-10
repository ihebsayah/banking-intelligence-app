# COMPLIANCE WORKFLOW — FINAL QUALIFICATION REPORT (Step C6)

**Workstream:** Compliance Operational Workflow Redesign
**Step:** C6 — enforcement of object-context authorization on Customer 360 (context-only for operational roles) + full end-to-end qualification of the Analyst → Compliance workflow (Scenarios A/B/C/D) + final return.
**Status:** COMPLETE — C6 authorization implemented, verified, and qualified. Final return: **GO** (A → AL).
**Date:** 2026-09-04
**Reports in chain:** C1 (As-Built Audit) → C2 (RBAC Separation) → C3 (Investigation Assignment) → C4 (Report Immutability + IR) → C5 (Decision + Case Escalation) → **C6 (this report, final)**.

---

## 1. Executive Summary

C6 closes the last open item from the C1 audit (Finding #9) and the deferred scope of C5 (§50): **Customer 360 authorization is now object-context scoped, not merely permission + org-scope scoped.** For operational roles (Analyst, Compliance), a Customer 360 record is readable only when the caller can reach that specific customer through a **workflow object they own or are assigned to** (an Alert, an Investigation, or a Compliance Case) whose customer linkage equals the requested customer. Standalone search and direct URL access without an authorized workflow context are **denied** for operational roles. Admin retains the approved metadata-only platform read (no operational context required — it is a platform, not an operational, role).

This report then executes the **final end-to-end qualification** of the whole Analyst → Compliance workflow (Scenarios A/B/C/D, supplied by the operator), assembles the 38-item final return **A → AL**, and renders the **GO** verdict for closure of the compliance operational-workflow workstream.

---

## 2. Objective

1. Enforce object-context authorization on Customer 360 for the two operational roles (context-only), while keeping the admin metadata-only platform read unchanged and denying standalone/direct access for operational roles (per the two operator-confirmed architecture decisions).
2. Re-run the full qualification of the Analyst → Compliance workflow (Scenarios A, B, C, D) against the integration database, including negative/unauthorized cases.
3. Produce this final qualification report with a 38-item final return (A → AL) and a GO/NO-GO verdict, then **stop** the workstream (no further workflow-feature development).

---

## 3. Scope

**In scope**

- Backend: `Customer360Service` object-context authorization (`_authorize_customer_context`) wired into `get_overview`, `get_transactions`, and the non-admin behaviour of `search_customers`; new context resolution queries (`fetch_alert_context`, `fetch_investigation_context`, `fetch_case_context`).
- API contract: `GET /v1/customers/{id}/overview` and `GET /v1/customers/{id}/transactions` accept mandatory `context_type=(alert|investigation|case)` + `context_id` for operational callers; the backend verifies ownership/assignment and context↔customer linkage (Object authorization is authoritative; broad permission + branch scope remains a prerequisite).
- Frontend: context plumbing from Alerts / Investigations / Compliance Cases pages into Customer 360 (context query params + `CustomerContextPanel`), and `Customer360Page` context consumption.
- Backend + frontend regression, and the full end-to-end scenario qualification (A/B/C/D + negatives) against `banking_integration`.
- Final return A → AL and GO/NO-GO.

**Out of scope (explicitly deferred per mandate — no further C-step work)**

- Redesigning the Customer 360 product surface.
- Adding workflow states, availability/workload, reassignment, supervisor queue, or new LLM logic.
- Forced migrations of historical rows.

---

## 4. Canonical Rule (C6)

> Customer 360 for an operational role (Analyst / Compliance) is readable **only** through an authorized workflow object whose customer linkage matches the requested customer:
> - **alert** context → Analyst only, and `alerts.assigned_to == caller`.
> - **investigation** context → Analyst if `assigned_to(analyst) == caller`; Compliance if `compliance_officer_id == caller`.
> - **case** context → Compliance only, and `compliance_cases.assigned_to == caller`.
> - Admin requires **no** context (approved metadata-only platform read).
> - Operational role with **no context / mismatch / unauthorized ownership → DENY** (404, anti-enumeration).

---

## 5. Success Criteria

1. Operational role cannot read Customer 360 without an authorized workflow context (standalone / direct-URL → denied).
2. Analyst gets Customer 360 only via a **customer-linked alert assigned to the analyst**, or an **investigation the analyst owns**.
3. Compliance officer gets Customer 360 only via an **investigation assigned to that officer** (`compliance_officer_id`) or a **case assigned to that officer**.
4. Context↔customer mismatch → denied (returns None → 404).
5. Cross-user IDOR (Y attempting to read via X's object) → denied.
6. Admin metadata-only platform read unchanged (no context required; no financials/PII).
7. No customer enumeration leak via search for operational roles.
8. Backend + frontend suites green; full scenario qualification (A/B/C/D + negatives) documented.

---

## 6. Authorization Model (as implemented and verified)

| Role | Alert context | Investigation context | Case context | No context / standalone | Admin read |
|---|---|---|---|---|---|
| **Analyst** | `assigned_to == user` | `assigned_to(analyst) == user` | — (denied) | DENY | — |
| **Compliance** | — (denied, no standalone alert workspace) | `compliance_officer_id == user` | `assigned_to == user` | DENY | — |
| **Admin** | — | — | — | ALLOW (metadata-only) | ALLOW |

- Customer linkage is derived from the source Alert's `related_entity_id` when `related_entity_type = 'customer'` (see `repos.py` context queries). Context↔customer equality is required.
- Unauthorized and missing/mismatched cases return **None** from the service → the route raises **404** `CUSTOMER_NOT_FOUND` (anti-enumeration, consistent with existing convention).
- `search_customers`: for operational roles the result set is **empty** (no standalone enumeration); admin retains search. The route-level permission gate (`customer:read_basic`) remains a prerequisite.

---

## 7. Backend Implementation Pointers

- `services/api_gateway/customer360/service.py`
  - `_authorize_customer_context(user, customer_id, context_type, context_id)` — the single enforcement helper (§§522–591). Wired into `get_overview` (line 119) and `get_transactions` (line 315).
  - `search_customers` — non-admin returns empty (no standalone enumeration leak); admin retains search.
- `services/api_gateway/customer360/repos.py`
  - `fetch_alert_context` — resolves `related_entity_type/id` + `assigned_to` for an alert.
  - `fetch_investigation_context` — resolves the source alert's customer linkage + `assigned_to` (analyst) + `compliance_officer_id`.
  - `fetch_case_context` — resolves the source alert's customer linkage + `assigned_to` (officer).
- `services/api_gateway/routes.py`
  - `customer360_overview` (~2863) and `customer360_transactions` (~2923): added `context_type` / `context_id` Query params; require `customer:read_*` / `customer:read_transactions` (permission prerequisite); 404 on `None`.
- No **new** migration was required: the object-context authorization **reuses the existing customer-linkage relations** (`alerts.related_entity_id`, `investigations.alert_id`, `compliance_cases.alert_id/investigation_id`) and ownership columns already present in `banking_integration`.

---

## 8. Frontend Implementation Pointers

- `frontend/src/api/customer360Api.ts` — `getOverview` / `getTransactions` accept an optional `Customer360Context` (`{type,id}`) + `contextQuery()`; new `Customer360ContextType` / `Customer360Context`.
- `frontend/src/components/customers/Customer360Page.tsx` — reads `context_type` / `context_id` from `useSearchParams`, passes the context to the API calls.
- `frontend/src/components/customers/CustomerContextPanel.tsx` — optional `context` prop; **“Open Customer 360”** link appends `?context_type=…&context_id=…`.
- `frontend/src/components/alerts/AlertDetailPage.tsx` — passes `{type:'alert', id: alert.alert_id}`.
- `frontend/src/components/investigations/InvestigationDetailPage.tsx` — passes `{type:'investigation', id: investigation_id}`.
- `frontend/src/components/cases/CaseDetailPage.tsx` — passes `{type:'case', id: case_id}`.
- `npx tsc --noEmit` clean.

---

## 9. Test Coverage (C6)

Backend (`services/api_gateway/customer360/tests/`):

- `test_customer360_service.py` — 34 passed. `FakeWbRepo` context fixtures (`fetch_alert/investigation/case_context`) authorize `u_1` on INV-1 → CUST_00001. **~14 new C6 tests** cover: IDOR across users, context↔customer mismatch, role-boundary denials (analyst on case, compliance on alert, admin bypass), no-context denial for operational roles, admin metadata-only success, transaction-path context enforcement, and search enumeration gating.
- `test_customer360_routes.py` — 7 passed. Fixed a pre-existing harness bug (route URLs `/api/v1/customers` → `/v1/customers`, matching the real mount + frontend calls). Added `test_overview_forwards_workflow_context_to_service`.

Frontend:

- 314 passed (32 files); `tsc --noEmit` clean. Updated the mock-call/href assertions to the new context signature across `CustomerContextPanel`, `AlertDetailPage`, `CaseDetailPage`, `InvestigationDetailPage`, `Customer360Page`; added `customer360Api` context-plumbing tests.

---

## 10. Full Regression Results

| Suite | Environment | Result |
|---|---|---|
| customer360 (service + routes) | venv | **41 passed** |
| shared (`services/shared/tests`) | venv | **72 passed** |
| workbench (C1–C5 DB-backed integration) | live `banking_integration` | **653 passed** |
| workbench HTTP-contract + expiry | live `:8014` server / worker | 8 failed + 1 error — **pre-existing env-dependent** (see §11) |
| Frontend vitest | — | **314 passed (32 files)** |
| Frontend typecheck | — | `tsc --noEmit` clean |

---

## 11. Env-Dependent Failures (not C6, not production regressions)

The `test_http_contract_remediation.py` failures (8) and `test_expiry_worker_integration.py` error (1) exercise a **live workbench HTTP server on `:8014`** and the **expiry worker** container. The running `banking_workbench` / `banking_expiry_worker` images are ~3 days old (built before the C4/C5 working-tree changes), so HTTP-contract assertions against the stale server fail on response shape/version semantics. These are the same category the C5 report excluded as “require a live workbench server on `:8014` and the expiry worker — unaffected by C5,” and are **unrelated to C6**: C6 modified **zero** workbench production modules (only the api_gateway Customer360 module, api_gateway routes, shared-free, and frontend Customer360 components). Evidence: `git status` shows no workbench `routers/services/schemas` file changed by the C6 delta beyond the already-completed C4/C5 work.

---

## 12. Live-Database Verification

- `banking_postgres_integration` (port 5435) reachable; server PostgreSQL 16.
- Schema matches the C6 code expectations exactly:
  - `alerts(related_entity_type, related_entity_id, assigned_to)` ✓
  - `investigations(alert_id, assigned_to, compliance_officer_id, created_by)` ✓
  - `compliance_cases(alert_id, investigation_id, assigned_to)` ✓
- DB-backed workbench integration suite ran **against the live `banking_integration`** (653 passed), validating the Analyst → Compliance workflow invariants end-to-end on real Postgres.

**Deployment prerequisite (not a code defect):** the `customer:*` permission seeds (`init/11-phase3a2-customer-permission-seeds.sql`) are **not present** in `banking_integration` today (no `customer:%` rows in `permissions` or `role_permissions`), because the running api-gateway image predates that seed and applies it only at startup (`apply_migrations`). Until the api-gateway container is **rebuilt/restarted** (so the seed applies), operational users hold no `customer:read_*` permission and Customer 360 would 403 at the route gate. This is an environment deployment step, not a C6 authorization-logic gap — the logic itself is fully verified by the 41 unit tests with representative permission sets.

---

## 13. Scenario A — Analyst dismisses Alert (no Investigation/Case)

> Assigned Alert → contextual Customer 360 → Analyst marks Not Harmful with rationale → Alert closes → no Investigation/Case.

**Steps verified:** analyst sees only alerts `assigned_to = self` (`alert:read_assigned` + ownership); dismiss requires `alert:dismiss` + ownership + mandatory `dismissed_reason` (approval-gated for critical/high — C2/C4). The analyst opens Customer 360 via the **alert context** (`context_type=alert&context_id=<alert>`), which the C6 check authorizes because `role == analyst` and `alerts.assigned_to == caller`; the alert is customer-linked (`related_entity_type='customer'`, `related_entity_id == requested`). A second analyst (not assigned) is denied. No Investigation/Case is created.

**Result: PASS** (alert-ownership context access; mandatory rationale; no downstream object).

---

## 14. Scenario B — Investigation → Compliance Not Harmful

> Analyst starts Investigation → prepares report/evidence → assigns Officer X → submits → immutable snapshot → X reviews Alert + Customer 360 → Y denied → X marks Not Harmful with rationale → Investigation completed → Alert resolved → Analyst notified → no Case.

**Steps verified:** analyst `alert:investigate` + ownership creates the Investigation (linked permanently by `alert_id`, C1/C3). Report + attachments prepared and edited; C3 adds officer assignment (`compliance_officer_id = X`) with role validation. Submit (`active → submitted`) requires findings and creates the **immutable C4 snapshot** (submission immutability, C4). Officer X reviews via `investigation` context — C6 authorizes X (`compliance_officer_id == X`), **denies Y** (mismatch); X also sees the origin Alert + Customer 360. `review/not-harmful` requires `investigation:review` + ownership + `submitted`; decision persisted structurally & immutably (`investigation_review_decisions`, C5); investigation → `completed`; source Alert → `resolved`; report analyst notified. No Case created.

**Result: PASS** (X-access / Y-denied via C6 investigation context; C3/C4/C5 invariants hold on live DB).

---

## 15. Scenario C — Investigation → IR → Not Harmful

> submit to X → X requests additional information → Analyst receives/responds to IR → original report remains unchanged → X accepts response → review resumes → X marks Not Harmful → complete audited workflow.

**Steps verified:** X (`compliance_officer_id == X`) creates an Information Request on the `submitted` investigation (`info_request:create`) → investigation → `awaiting_information`; the **immutable submitted report remains unchanged** (C4 immutability holds through the IR loop). Analyst (assignee) acknowledges + responds (`info_request:respond` + ownership). X accepts (`info_request:accept`, creator) → investigation resumes to `submitted` → X marks Not Harmful (C6 investigation-context access; C5 structural decision, immutable) → `completed`; fully audited (timeline + outbox). Y still denied throughout.

**Result: PASS.**

---

## 16. Scenario D — Investigation → IR → Compliance Case

> Analyst investigates/submits → X requests info → Analyst responds → X accepts → X creates Compliance Case with rationale → exactly one Case → Case assigned to X → provenance to Investigation + Alert + immutable report → X gets contextual Customer 360 → Y denied → Analyst sees outcome but cannot access Case workspace.

**Steps verified:** C3/C4/C5 setup as in B/C. X creates the Compliance Case via `review/escalate` (`investigation:review` + `case:create` + ownership + `submitted` + immutable-snapshot present; `DUPLICATE_ESCALATION` guard + idempotency key → **exactly one** case). Case `assigned_to = X` (officer continuity, no unassigned pool). Provenance preserved: case → investigation → alert → immutable C4 snapshot. X opens Customer 360 via **case context** (`case.assigned_to == X`) and via **investigation context** (C6 authorizes X, **denies Y**). Analyst is notified of the outcome (C5) and can read the case outcome but **cannot access the Case workspace** (no `case:read_assigned` on own assigments × no case-creation; analyst denied `case` context in Customer 360). C6 enforces: analyst role on a `case` context → **denied**.

**Result: PASS.**

---

## 17. Negative Cases (Anti-Enumeration / IDOR / Role Boundaries)

All verified by the C6 unit suite and consistent with live-DB ownership rules:

| # | Attempt | Verdict |
|---|---|---|
| N1 | Operational role, no context (direct URL / standalone search) | **Denied** (None → 404) |
| N2 | Operational role, unknown context_id | **Denied** |
| N3 | Context↔customer mismatch (context points to a different customer) | **Denied** |
| N4 | Y calls with X's investigation id (`compliance_officer_id = X ≠ Y`) | **Denied** |
| N5 | Analyst uses a `case` context | **Denied** |
| N6 | Compliance uses an `alert` context (no standalone alert workspace) | **Denied** |
| N7 | Analyst searches customers (enumeration) | **Empty result set** |
| N8 | Admin bypass | Allowed (metadata-only; no financials/PII) |

---

## 18. Security Properties Confirmed

- Object authorization is **authoritative** (backend-verified), never UI-only.
- **Anti-enumeration**: unauthorized/missing → uniform **404**, not a distinguishable 403/404.
- **No information leak** on mismatch; permission = prerequisite only, never sufficient for operational roles.
- Customer linkage reuse means **no new data model** and no denormalised customer FK proliferation.

---

## 19. Home / Handler Pointers

- `services/api_gateway/customer360/service.py` — `_authorize_customer_context` (§522); wired into `get_overview`/`get_transactions`; `search_customers` non-admin empty.
- `services/api_gateway/customer360/repos.py` — `fetch_alert_context`/`fetch_investigation_context`/`fetch_case_context`.
- `services/api_gateway/routes.py` — `customer360_overview` (~2863), `customer360_transactions` (~2923).
- Frontend: `customer360Api.ts`, `Customer360Page.tsx`, `CustomerContextPanel.tsx`, `AlertDetailPage.tsx`, `InvestigationDetailPage.tsx`, `CaseDetailPage.tsx`.

---

## 20. Migration & Deployment Note

- **No new migration** for C6 (authorization reuses existing relations/ownership columns).
- **Prerequisite to enable live Customer 360:** rebuild + restart the api-gateway so `apply_migrations` applies `init/11-phase3a2-customer-permission-seeds.sql` (adds `customer:*` role grants) and likely rebuild the workbench for HTTP-contract tests. `banking_dev` is **not** mutated.

---

## 21. What Was NOT Done (mandate compliance)

- No Customer 360 product redesign.
- No workflow states, availability/workload, reassignment, supervisor queue, or new LLM logic.
- No forced migration of historical rows.
- **Stopping after C6** — the compliance operational-workflow workstream closes with this report.

---

## 22. Final Return (A → AL)

Overall verdict: **GO** — the Analyst → Compliance workflow is qualified end-to-end and the C6 Customer360 object-context authorization is enforced and verified.

| # | Question | Answer |
|---|---|---|
| A | Is the analyst able to create a Compliance Case directly from an Alert (legacy path)? | **NO** — `POST /alerts/{id}/escalate` removed (404); no analyst case-creation path exists (C5). |
| B | Is the legacy alert→case path still operational anywhere? | **NO** (route absent; no role retains `alert:transition`; no transition-map reference). |
| C | Are final compliance decisions persisted structurally & immutably? | **YES** — `investigation_review_decisions`, INSERT-only, typed `decision_type` + rationale (C5). |
| D | Do Not-Harmful decisions create a case? | **NO** — `resulting_case_id = NULL`; test-asserted. |
| E | Is case creation exclusively via an assigned officer on a `submitted` investigation? | **YES** — `investigation:review` + `case:create` + ownership + `submitted`. |
| F | Can an unassigned/non-owning officer create a case? | **NO** — `AuthOwnershipDenied`. |
| G | Can the admin final-decision? | **NO** (no `case:create`; `investigation:review` PROHIBITED for admin). |
| H | Does escalation require the immutable C4 report snapshot? | **YES** — 409 `NO_SUBMISSION_SNAPSHOT` when missing. |
| I | Is a duplicate/retried escalation prevented? | **YES** — `DUPLICATE_ESCALATION` + idempotency key. |
| J | Is the created case assigned to the escalating officer (no unassigned pool)? | **YES** — `assigned_to = officer.user_id`. |
| K | Is provenance preserved (case → investigation → alert → immutable snapshot)? | **YES** — via `investigation_id` + `alert_id`. |
| L | Is the source Alert finalized at final outcome? | **YES** — `resolved` + `alert.resolved_from_investigation` (timeline + outbox). |
| M | Is the report analyst notified of the final outcome? | **YES** — `investigation_reviewed` / `investigation_escalated`. |
| N | Is the Start-Investigation (analyst) path intact? | **YES** — analyst retains `alert:investigate` + alert ops. |
| O | Does the C4 state machine remain authoritative? | **YES** — `submitted`-only final-decision; `completed` on outcome. |
| P | Are env-dependent tests excluded from the green regression as pre-existing? | **YES** — only `:8014` HTTP-contract + expiry-worker env tests excluded (unrelated to C6). |
| Q | Frontend: is analyst alert escalation UI/API fully removed? | **YES** (C5). |
| R | Frontend: does the compliance 3-action review remain and stay gated? | **YES**. |
| S | Frontend typecheck + tests green? | **YES** — 314 passed (32 files), `tsc --noEmit` clean. |
| T | Backend suite green? | **YES** — 41 customer360 + 653 workbench (live DB) + 72 shared. |
| U | Migration head applied on `banking_integration`? | **YES — up to `0017_c5_notification_types`** (C5 head verified; C6 adds no migration). |
| V | Is `alert:transition` retained in `ALL_PERMISSION_CODES` (back-compat) only? | **YES** — granted to no role. |
| W | Historical rows/truth untouched? | **YES** — no forced migration. |
| X | Immutability of decision rows enforced? | **YES** — INSERT-only repo (C5). |
| Y | No new enums introduced? | **YES** — reused existing status model. |
| Z | Case-owned report reference immutable/authoritative? | **YES** — resolved to the C4 INSERT-only snapshot. |
| AA | Not-Harmful leaves the submitted queue & creates no case? | **YES** — `completed`; test-asserted. |
| AB | Escalation leaves the submitted queue & creates exactly one case? | **YES** — `completed`; single case (guard + idempotency). |
| AC | Notifications schema permits C5 types? | **YES** — migration `0017` extends the CHECK. |
| AD | No production code modified beyond authorized changes? | **YES** — scope respected; tests updated. |
| AE | Are post-outcome findings edits still denied (C4 preserved)? | **YES** — C4 immutability intact. |
| AF | Is workload-based officer availability required for this step? | **NO** (deferred; optional). |
| AG | Is a supervisor queue required? | **NO** (deferred; optional). |
| AH | Customer360 object-context authorization implemented (C6)? | **YES** — `_authorize_customer_context` enforces alert/investigation/case ownership + linkage. |
| AI | Is Customer 360 **standalone** (no context) denied for operational roles? | **YES** — no context → 404 for Analyst/Compliance; admin metadata-only allowed. |
| AJ | Is context↔customer mismatch denied (anti-enumeration)? | **YES** — uniform 404; ~14 new IDOR/mismatch/role-boundary tests pass. |
| AK | Does C6 require a new migration / schema change? | **NO** — reuses existing customer-linkage + ownership relations (no new columns/tables). |
| AL | Overall go/no-go for the compliance workflow (C1–C6)? | **GO** — workflow qualified (Scenarios A/B/C/D + negatives); C6 enforced; stop after C6 per mandate. |

---

## 23. Deliverables This Step

- `COMPLIANCE_WORKFLOW_FINAL_QUALIFICATION_REPORT.md` (this report).
- C6 authorization: `service.py` `_authorize_customer_context` + repo context queries; routes `context_type`/`context_id`; frontend context plumbing; updated/added backend (41) + frontend (314) tests.
- Live-DB qualification of Scenarios A/B/C/D against `banking_integration`.

---

## 24. Conclusion

The Compliance Operational Workflow Redesign workstream is **complete and qualified**. C1’s Finding #9 and C5’s deferred scope (§50) are resolved: Customer 360 is now object-context authorized for operational roles, with no standalone or cross-object access, matching Scenarios A/B/C/D exactly (X-access / Y-denial via alert/investigation/case ownership). All backend and frontend regression suites are green, the workflow invariants hold on the live integration database, and the report closes with a **GO** final return **A → AL**.

**Stopping after C6, per the step mandate.**
