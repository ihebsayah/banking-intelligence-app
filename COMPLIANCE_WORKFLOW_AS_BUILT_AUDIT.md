# COMPLIANCE WORKFLOW — AS-BUILT AUDIT

**Workstream:** Compliance Operational Workflow Redesign (READ-ONLY AUDIT)
**Scope:** Compare current backend/frontend implementation against the newly approved canonical business workflow.
**Status:** COMPLETE — no code changes made.
**Date:** 2026-09-02

> This document is a point-in-time, read-only snapshot of the current system. It makes **no modifications** to routes, permissions, sidebar, statuses, migrations, DB data, or code. It proposes — but does not implement — a future state.

---

## 1. Executive Summary

The system already implements a substantial and largely well-architected operational workflow spanning **Alerts → Investigations → Compliance Cases → Information Requests**, backed by a two-database architecture, an outbox-based audit trail, optimistic locking, idempotency, and a 10-step centralized policy engine (`services/shared/authorise.py`). The design intent is a **close match** to the canonical workflow: an **Analyst** triages alerts, starts investigations, writes reports, and submits; a **Compliance Officer** reviews submitted investigations, requests information, closes as not-harmful, or escalates to a Compliance Case; and the **Admin** role is explicitly **prohibited** from operational compliance decisions (segregation of duties is partially enforced).

However, the audit found a **critical Seeded-Permission bug** that breaks the compliance role, plus several **segmentation / module-segregation gaps** relative to the canonical target.

### Headline findings (with severity)

| # | Severity | Finding |
|---|----------|---------|
| 1 | **CRITICAL (P0)** | Migration `0005`'s `SENSITIVE_PERMISSIONS` gate fails to seed `case:decision` and `case:close` for the **compliance** role. Compliance cannot record decisions or close cases (the two actions the canonical workflow assigns exclusively to the Compliance Officer). |
| 2 | **CRITICAL (P0)** | Compliance **has `alert:read_assigned` + `alert:transition` seeded**, and the frontend gives compliance a **standalone Alerts module** (`/workbench/alerts`) and a **standalone Information Requests module** (`/workbench/information-requests`). The canonical workflow forbids both standalone modules for the Compliance Officer. |
| 3 | **CRITICAL (P0)** | Compliance has **`alert:transition`** and **`alert:dismiss` (via admin? no — compliance does NOT have dismiss)**, but it **does** have `alert:transition`; the canonical workflow says the Compliance Officer must **NOT** be able to dismiss alerts or start investigations. Compliance's seeded set lacks `alert:dismiss`/`alert:investigate` (good), but retains `alert:transition` (escalate/resolve on alerts) and `alert:read_assigned` (standalone alert visibility) — both inconsistent with the canonical target. |
| 4 | **HIGH (P1)** | **No Investigation-assignment endpoint exists.** The canonical workflow requires the Analyst to "select an eligible Compliance Officer" and "assign the investigation." Currently the investigation is auto-assigned to the creating analyst, and the handoff to compliance is implicit (status `submitted` → compliance review queue). There is no `assigned_to = officer` transition, and **no officer-discovery endpoint** — only the admin-only `GET /admin/users`. |
| 5 | **HIGH (P1)** | **No role validation on assignment.** The generic `_validate_assignee()` helper checks only existence/status/scope — it never checks the target user's role. Any discovery endpoint built for officer selection must add a role check. |
| 6 | **MED (P2)** | **Report immutability is incomplete.** While `submitted` cannot be edited directly, a compliance officer can **Return for Revision** (`submitted → returned → active`), after which the analyst can silently edit the report. The canonical workflow requires the submitted report to be permanently immutable, with later analyst input flowing only through Information Requests. |
| 7 | **MED (P2)** | No mandatory statement recorded for several decisions in machine-readable form — they are persisted as **internal comments** (`[Not Harmful] …`, `[Escalated to Case …] …`) rather than structured decision/statement columns. Functionally present; not structured. |
| 8 | **LOW (P3)** | Frontend shows **same "Cases" nav item to Analyst and Compliance**; the canonical workflow gives the Analyst **no** standalone Cases module. Backend prohibits analyst from case decisions/close/assign (SoD), so the UI gap is largely presentational, but the nav/module visibility itself conflicts with the target. |
| 9 | **LOW (P3)** | Customer 360 authorization is role/permission-scoped but **not object-scoped**: any user with `customer:read_*` and the `hq_main`/`global` scope sees **all customers** in the org. Canonical target calls for workflow/authorization-scoped Customer 360. |

---

## 2. Current Frontend Architecture

- **Framework:** React (Vite) + React Router v6 + React Query + Zustand (`frontend/src`).
- **Auth:** Dual-mode — Keycloak SSO or legacy JWT. User profile (role + permissions) resolved via `GET /auth/me`.
- **Authorization primitives:**
  - `ProtectedRoute` — route-level guard (`requiredRole`, `requiredPermission`, OR logic for permissions).
  - `PermissionGate` — inline component-level guard.
  - `usePermissions()` / `canAccess()` (`frontend/src/lib/permissions.ts`) — central permission+role evaluation used by routes, sidebar, command palette.
- **Sidebar** (`frontend/src/lib/navigation.ts` + `BankingSidebar.tsx`): items filtered by `requiredPermissions` (any-match) and/or `requiredRoles`.

### Key routes / pages (workflow-relevant)

| Route | Component | Route Role Gate | Route Permission Gate | Sidebar Visibility |
|---|---|---|---|---|
| `/workbench/alerts` | `AlertQueuePage` | analyst, compliance, admin | `alert:read_assigned`/`alert:read` | permission-based |
| `/workbench/alerts/:alertId` | `AlertDetailPage` | analyst, compliance, admin | same | — |
| `/workbench/investigations` | `InvestigationQueuePage` | analyst, compliance, admin | `investigation:read_own`/`read` | permission-based |
| `/workbench/investigations/:id` | `InvestigationDetailPage` | analyst, compliance, admin | same | — |
| `/workbench/cases` | `CaseQueuePage` | analyst, compliance, admin | `case:read_assigned`/`read` | permission-based |
| `/workbench/cases/:id` | `CaseDetailPage` | analyst, compliance, admin | same | — |
| `/workbench/information-requests` | `IRInboxPage` | analyst, compliance, admin | `info_request:read_assigned`/`read` | permission-based |
| `/workbench/approvals` | `ApprovalQueuePage` | compliance | `approval:approve` | compliance-only |
| `/workbench/customers` | `CustomerSearchPage` | any | `customer:read_basic` | permission-based |
| `/workbench/customers/:id` | `Customer360Page` | any | `customer:read_basic` | permission-based |
| `/compliance` | `CompliancePage` | compliance, manager, admin | `workbench:access` | role-based |
| `/notifications` | `NotificationsPanel` | analyst, compliance, admin | `notification:read` | bell (no nav) |

**Nav groups:** General (Dashboard, Branches); Operational Workbench (Customer 360, Alert Queue, Investigations, Cases, Information Requests, Approvals); Intelligence & Analytics (Assistant, KPI, KPI Governance, Risk, Compliance, Reports); Administration (Outbox, Admin).

**Important:** All workbench queue items are gated **by permission only** (no `requiredRoles`). So Analyst and Compliance see the **same** set of workbench modules (Alerts, Investigations, Cases, Information Requests). There is **no compliance-only workbench surface** and **no analyst-only surface** currently — module visibility is identical for both roles (varying only by permission grants).

---

## 3. Current Backend Architecture

**Two FastAPI apps + shared library:**

- **API Gateway** (`services/api_gateway`, port 8000): portal, dashboard, KPI, compliance, customer360, admin, auth. RBAC via `require_roles`, `require_permission`, `require_any_permission(_audited)`.
- **Workbench** (`services/workbench`, port 8014): operational workflow — alerts, investigations, cases, IRs, approvals, comments, notifications, timeline, attachments, admin outbox/orphans. Policy via `shared.authorise.authorise()` (10-step engine).
- **Shared** (`services/shared`): `authorise.py` (policy engine), `models.py` (Pydantic), config, DB connector.

### Key backend patterns

- **UnitOfWork** (`services/workbench/uow.py`): atomic transaction + outbox flush.
- **Optimistic locking** (`version` column + `expected_version`).
- **Idempotency** (`X-Idempotency-Key`).
- **Outbox** (`audit_outbox`) for reliable audit/event delivery.
- **Entity access fallback** (`services/workbench/services/entity_access.py`): assigned-read vs broad-read.

### Workbench routers / services / endpoints (workflow)

**Alerts** (`alert_service.py`):
- `GET /alerts/assigned` → `alert:read_assigned` (scope + assigned_to)
- `GET /alerts/{id}` → `alert:read_assigned` or `alert:read`
- `PATCH /alerts/{id}/assign` → `alert:assign`
- `PATCH /alerts/{id}/acknowledge` → `alert:acknowledge` (ownership)
- `PATCH /alerts/{id}/dismiss` → `alert:dismiss` (ownership; approval-gated critical/high)
- `POST /alerts/{id}/investigate` → `alert:investigate` (ownership; creates Investigation)
- `POST /alerts/{id}/escalate` → `alert:investigate` (ownership)

**Investigations** (`investigation_service.py`):
- `GET /investigations/assigned` → `investigation:read_own` (scope + assigned_to)
- `GET /investigations/submitted` → `investigation:review` (scope + status=submitted — all in scope, NOT assigned_to)
- `GET /investigations/{id}` → `read_own` or `read`
- `PATCH /investigations/{id}` → `investigation:update` / `modify_findings`
- `PATCH /investigations/{id}/transition` → `investigation:transition`
- `POST /investigations/{id}/cancel` → `investigation:transition` (+ admin)
- `POST /investigations/{id}/review/not-harmful` → `investigation:review`
- `POST /investigations/{id}/review/escalate` → `investigation:review` + `case:create`
- Attachments: `POST/GET {id}/attachments`, `GET download`, `DELETE`.

**Compliance Cases** (`case_service.py`):
- `GET /cases/assigned` → `case:read_assigned` (scope + assigned_to)
- `GET /cases/unassigned` → `case:read` (scope + assigned_to IS NULL)
- `GET /cases/{id}` → `read_assigned` or `read`
- `PATCH /cases/{id}/assign` → `case:assign`
- `PATCH /cases/{id}/transition` → `case:transition`
- `POST /cases/{id}/close` → `case:close` (approval-gated critical/high)
- `POST /cases/{id}/reopen` → `case:reopen` (approval-gated)
- `POST /cases/{id}/decisions` → `case:decision`
- `GET /cases/{id}/decisions` → `read_assigned` or `read`

**Information Requests** (`information_request_service.py`):
- `POST /cases/{id}/information-requests` → `info_request:create`
- `POST /investigations/{id}/information-requests` → `info_request:create`
- `GET /cases/{id}/information-requests`, `GET /investigations/{id}/information-requests` → `read_assigned`/`read`
- `GET /information-requests/assigned` → `info_request:read_assigned` (assigned_to inbox)
- `GET /information-requests/{id}` → `read_assigned`/`read`
- `PATCH /information-requests/{id}/acknowledge`
- `PATCH /information-requests/{id}/respond` → `info_request:respond`
- `PATCH /information-requests/{id}/accept` → `info_request:accept` (creator)
- `PATCH /information-requests/{id}/return` → `info_request:return` (creator)
- `POST /information-requests/{id}/cancel` → `info_request:cancel` (creator or admin)

**Approvals** (`approval_service.py`): `POST /approval-requests`, `GET /approval-requests`, `GET /approval-requests/{id}`, `POST /approval-requests/{id}/vote` (`approval:approve`; conflict-of-interest: cannot vote own).

**Comments / Timeline / Notifications:** polymorphic `/{entity_type}/{entity_id}/comments|timeline`, plus own-timeline, notifications.

**Admin:** `GET/PATCH /admin/outbox` (+retry), `GET /admin/orphan-assignments`.

---

## 4. Current Data Model

**Two databases:** `banking_dev` (core data) and `banking_integration` (operational workflow). Schema is raw SQL DDL via Alembic (migrations in `migrations/versions/`), mirrored by Pydantic DTOs (not SQLAlchemy ORM).

### Workflow tables (migration 0004, 0011, 0012)

| Table | PK | Key FKs | Owner/Assignee | Status values | Decision/statement fields | created_by | timestamps |
|---|---|---|---|---|---|---|---|
| `alerts` | `alert_id` | `assigned_to→users`, `dismissed_by`, `resolved_by`, `dismissal_approval_id→approval_requests` | `assigned_to` | new, assigned, acknowledged, under_investigation, resolved, dismissed | `dismissed_reason`, `dismissed_at` | (none; `dismissed_by`/`resolved_by`) | `created_at`, `updated_at`, `version` |
| `investigations` | `investigation_id` | `alert_id→alerts` (RESTRICT), `created_by→users`, `assigned_to→users`, `scope_id` | `created_by` (NOT NULL), `assigned_to` | open, active, awaiting_information, submitted, returned, completed, cancelled | `findings_text`, `findings_refs` (JSONB), `conclusion`, `return_reason` | `created_by` ✓ | `started_at`,`submitted_at`,`completed_at`,`created_at`,`updated_at`,`version` |
| `investigation_attachments` | `attachment_id` | `investigation_id` (RESTRICT), `uploaded_by→users` | `uploaded_by` | — | `sha256_hash`, `size_bytes` (≤10MB), `description` | `uploaded_by` | `uploaded_at` |
| `compliance_cases` | `case_id` | `alert_id`, `investigation_id` (RESTRICT), `created_by`, `assigned_to`, `closed_by`, `closure_approval_id`, `current_disposition_id→decisions` | `created_by` (NOT NULL), `assigned_to` | open, assigned, under_review, awaiting_information, decision_pending, awaiting_compliance_action, resolved, closed, cancelled | `resolution`, `reopen_reason`, `current_disposition_id` | `created_by` ✓ | `resolved_at`,`closed_at`,`target_date`,`created_at`,`updated_at`,`version` |
| `decisions` | `decision_id` | `case_id` (NOT NULL RESTRICT), `decided_by→users`, `supersedes_decision_id`, `approval_id` | `decided_by` | decision_type: no_action, warning, enhanced_due_diligence_recommended, report_to_authority_recommended, account_action_recommended, closure_recommended | `rationale` (NOT NULL), `is_final` | — | `decided_at`,`created_at`,`version` |
| `information_requests` | `ir_id` | `case_id` (nullable), `investigation_id` (XOR parent), `created_by` (NOT NULL), `assigned_to` (NOT NULL), `accepted_by`,`returned_by`,`cancelled_by` | `created_by` (NOT NULL), `assigned_to` (NOT NULL) | open, acknowledged, responded, accepted, returned, cancelled | `question` (NOT NULL), `response_text`, `acceptance_note`, `return_reason`, `cancel_reason`, `due_date` | `created_by` ✓ | `accepted_at`,`returned_at`,`cancelled_at`,`responded_at`,`created_at`,`updated_at`,`version` |
| `approval_requests` | `approval_request_id` | `requested_by→users`; `entity_id` loose | `requested_by` | pending, approved, rejected, expired, cancelled | `rationale` (NOT NULL) | — | `expires_at`,`executed_at`,`created_at`,`version` |
| `approval_decisions` | `approval_decision_id` | `approval_request_id`, `approver_id` (unique per approver) | `approver_id` | decision: approved, rejected | `rationale` | — | `decided_at` |
| `comments` | `comment_id` | `author_id→users`, `redacted_by`; `entity_type`+`entity_id` loose | `author_id` | — | `content`, `is_internal`, `is_redacted`, `original_content_hash` | — | `created_at`,`updated_at`,`version` |
| `activity_timeline` | `timeline_id` | `actor_id→users` (`system_001` for workers); `entity_type`+`entity_id` loose | `actor_id` | — | `event_type`, `old_value` (JSONB), `new_value` (JSONB), `metadata` | — | `occurred_at` |
| `notifications` | `notification_id` | `user_id→users` | `user_id` (recipient) | — | `title`, `body`, `notification_type` | — | `created_at` |
| `assignment_history` | `history_id` | `assigned_from`,`assigned_to`,`assigned_by→users`; `entity_type`+`entity_id` loose | `assigned_by` | — | `reason` | — | `assigned_at` |
| `audit_outbox` | `outbox_id` | — | `actor_id` (loose, no FK) | PostgreSQL ENUM: pending, delivering, delivered, failed, poison | `payload` (JSONB), `event_type` | — | `created_at`,`occurred_at` |

**Supporting tables:** `organisation_scopes`, `user_scopes`, `users`, `roles`, `role_permissions`, `permissions`, `api_idempotency`. Legacy (Inc 1) tables retained: `legacy_compliance_cases`, `aml_alerts`, `kyc_cases`, `compliance_reviews`.

**No `updated_by` columns** on any operational table (only `updated_at` + `version`).

---

## 5. Alerts

**Statuses:** `new → assigned → acknowledged → under_investigation → resolved/dismissed`

**Behavior:**
- **Owner/assignee:** `assigned_to`. Action gating requires ownership (Step 5 of authorise).
- **Analyst visibility:** sees only alerts `assigned_to = self` (`GET /alerts/assigned`).
- **Compliance visibility:** has `alert:read_assigned` → sees alerts assigned to itself only. There is **no** "all alerts" view used by the frontend, though `alert:read` exists (admin-only grant). Compliance **does** have standalone Alert module visibility.
- **Actions:** acknowledge, dismiss (approval-gated for critical/high), investigate (creates Investigation), escalate, assign (admin).

**Answers to canonical sub-questions:**
- Can analyst view alert? **YES** (assigned only).
- Can analyst dismiss alert? **YES** (`alert:dismiss` + ownership + state).
- Can analyst provide justification? **YES** — `dismissed_reason` is **MANDATORY** (schema required; frontend required).
- Can analyst create investigation? **YES** (`alert:investigate` + ownership + `acknowledged`).
- Can compliance access Alerts page? **YES** — route allows compliance, permission `alert:read_assigned` seeded (gives compliance a standalone Alerts module — **conflicts with canonical**).
- Can compliance access Alert APIs directly? **YES** — `GET /alerts/assigned` (read_assigned), `PATCH /alerts/{id}/escalate` (`alert:transition`). **Conflicts with canonical** (mandatory statement on dismiss does not apply to compliance since compliance cannot dismiss; but `alert:transition` escalation by compliance is non-canonical).

---

## 6. Investigations

**Statuses:** `open → active → submitted → completed | returned → active`, plus `awaiting_information` (from IR creation), `cancelled` (admin).

**Lifecycle (current):**
1. **Create:** Analyst (or assignee) calls `POST /alerts/{id}/investigate`. New Investigation is auto-assigned to `alert.assigned_to` (the analyst), `created_by=analyst`. Status `open`. Alert → `under_investigation`. Permanently linked via `investigation.alert_id` (FK RESTRICT).
2. **Start:** `open → active` (ownership).
3. **Findings:** edit while `active`/`returned` (`investigation:modify_findings` + ownership).
4. **Submit:** `active → submitted` requires findings present; sets `submitted_at`. Compliance review queue (`/investigations/submitted`) shows **all** submitted in scope.
5. **Review:** compliance `Mark Not Harmful` (`submitted → completed`) or `Escalate to Case` (`submitted → completed` + creates case) or `Return for Revision` (`submitted → returned`) or `Request Additional Info` (`submitted → awaiting_information` via IR creation).
6. **Return/resume:** `returned → active` (analyst edits) → resubmit.

**Who owns / views:**
- Created by analyst; assigned to analyst (inherited from alert).
- Compliance views only **submitted** investigations (all in scope) and explicitly assigned ones.
- **There is NO investigation `assigned_to` handoff to a compliance officer.**

**Answers to canonical sub-questions:**
- Who creates?: **Analyst** (alert assignee) — or any user with `alert:investigate` + ownership.
- Who owns?: `created_by` = analyst; `assigned_to` = analyst.
- Who views?: analyst (own/assigned), compliance (submitted in scope + assigned).
- Alert link: `investigation.alert_id` (1:1 active, partial unique index). ✓
- Customer link: `investigation.alert_id → alerts → related_entity` (no direct customer FK). Customer 360 link inferred via alert's `related_entity_id`.
- Report model: `findings_text` (free text) + `findings_refs` (JSONB) + `conclusion` — **semi-structured/free-text**, on the same row (not a separate table).
- Comments: separate `comments` polymorphic table (`entity_type='investigation'`).
- Evidence: `investigation_attachments` table.
- Submission: `active → submitted`.
- Assignment: **none** (the gap).

**Can Analyst A see Analyst B's investigations?** **NO** — `GET /investigations/assigned` filters `assigned_to = A`. `GET /investigations/submitted` (compliance/`investigation:review`) returns all in scope, but analysts lack `investigation:review`. Analysts lack `investigation:read` (broad). So Analyst A cannot see B's investigations via list endpoints.

---

## 7. Investigation Reports

- **Format:** free text `findings_text` + JSONB `findings_refs` + `conclusion`, stored on the `investigations` row. Not a separate `investigation_reports` table. No structured "findings/observed facts/mitigating elements/conclusion" field decomposition — a single free-text field plus conclusion.
- **Edit rules:** require `investigation:modify_findings` + ownership + status `active`/`returned`.
- **Submission rules:** `active → submitted` requires `findings_text` or `findings_refs` non-empty.
- **Immutability rules:** cannot edit while `submitted`/`completed` (service status guard + workflow-state gate). **BUT** a compliance Return (`submitted → returned → active`) re-enables editing — so the submitted report is **not permanently immutable**. Once `completed`, it is terminal.

**Answers:**
- Can report be edited after handoff? **NO while `submitted`; YES after Return-for-Revision** (the immutability desired invariant is not fully met).

---

## 8. Assignment

- **Investigation assigned_to:** set at creation to the alert's assignee. **No `PATCH /investigations/{id}/assign` endpoint exists.** The `investigation:assign` permission exists but is admin-only and only used for `cancel`.
- **Alert / Case / IR assignment:** `assign` endpoints exist (admin-driven for alerts/cases; IR assignee passed by requester).
- **Role validation:** `_validate_assignee()` checks existence/status/scope only — **never role**. So even the existing assign paths do not validate that the target is a Compliance Officer.
- **Officer discovery endpoint:** **NONE.** Only admin-only `GET /admin/users`. `approval_service._fetch_eligible_approvers()` is a private helper, not exposed. The frontend uses free-text input for IR assignee, not a populated officer dropdown.

**Answers:**
- Can Analyst choose a Compliance Officer? **NO** (no investigation-assign endpoint, no officer picker).
- Does assignment validate target role == compliance? **NO** — no role check anywhere.

---

## 9. Information Requests

- **Who creates:** compliance (or any user with `info_request:create`); on an investigation only while `submitted`; transitions investigation to `awaiting_information`. On a case while under review.
- **Parent object:** exactly one of `case_id` XOR `investigation_id` (enforced by DB constraint).
- **Who receives:** `assigned_to` supplied by requester (required field; NOT auto-assigned to the investigation's analyst — though the frontend preselects `investigation.assigned_to` by default).
- **Statuses:** open, acknowledged, responded, accepted, returned, cancelled.
- **Response fields:** `response_text`, `acceptance_note`, `return_reason`; timestamps `responded_at`, `accepted_at`, `returned_at`.
- **Frontend:** dedicated `/workbench/information-requests` inbox (analyst + compliance) + IR tabs inside Case/Investigation detail.
- **Ownership enforcement:** `respond` requires ownership (`assigned_to == self`); `accept`/`return` require creator; `cancel` requires creator or admin.
- **Compliance standalone IR module:** **YES** — compliance sees `/workbench/information-requests` nav + has `info_request:read`/`accept`/`return`. **Conflicts with canonical** (officer should see IRs only inside the investigation, no standalone module).

**Complete lifecycle (current):**
```
Investigation submitted
   ↓ compliance creates IR
Investigation → awaiting_information ; IR open (assigned_to analyst)
   ↓ analyst acknowledge
IR acknowledged
   ↓ analyst respond
IR responded
   ↓ compliance accept OR return
IR accepted (→ investigation resumed to submitted)  |  IR returned → analyst re-responds
```

---

## 10. Compliance Cases

- **Who can create:** compliance via `escalate_to_case` (`investigation:review` + `case:create`). Analyst/admin are Prohibited from `case:create`? — No: analyst lacks `case:create` permission (not seeded); admin has `case:reopen` but **not** `case:create` (not seeded). So only compliance can create cases.
- **Originates from:** an Investigation (and transitively its Alert) — `case.investigation_id` + `case.alert_id` both set. Provenance ALERT → INVESTIGATION → CASE preserved via FK RESTRICT.
- **Mandatory fields:** `escalate_to_case` requires `rationale` (min_length=1) — persisted as internal comment `[Escalated to Case …]`. Title required; priority defaulted.
- **Decision statement:** required for each `RecordDecision` (`rationale` NOT NULL on `decisions`).
- **Status lifecycle:** open → assigned → under_review → decision_pending → … → resolved → closed (with close/reopen approval gating for critical/high).
- **Customer linkage:** inherited via alert's `related_entity_id`; inferred (no direct customer FK).
- **Officer ownership:** `assigned_to`; cases unassigned appear in pool, admin claims/assigns.
- **Analyst access:** has `case:read_assigned` — but an analyst is rarely assigned a case; nav shows Cases module to analysts (presentational gap; backend blocks their actions via missing permission + PROHIBITED).

---

## 11. Customer 360 Access

- **Permissions (seeded via `init/11-phase3a2-customer-permission-seeds.sql`, applied at gateway startup):**
  - **Analyst:** `customer:read` (aggregate), `read_basic`, `read_financial`, `read_transactions`, `read_kyc`, `read_risk` — **PII masked** (no `read_pii`).
  - **Compliance:** all of the above **+** `read_compliance_history`, `read_pii` — full detail incl. unmasked PII within org scope.
  - **Admin:** `read` + `read_basic` + `read_operational_metadata` — metadata-only (no financials/PII).
  - **Manager:** none (denied).
- **Endpoint gate:** `/api/v1/customers/{id}/overview` requires **any** `customer:read_*` (`require_any_permission_audited`); transactions requires `customer:read_transactions`.
- **Row/scope scoping:** `customer360/service.py` `_resolve_scope` — if user holds `hq_main` or `global` scope → **unrestricted** (all customers). Otherwise restricts to branch/region scopes overlapping the customer's branches. Demo users are seeded with `hq_main` scope → **effectively see all customers**.
- **Section masking:** per-section permission gating + PII masking.

**Answers to canonical sub-questions:**
- Can analyst access any customer? **YES** (any customer in org scope, PII masked).
- Can compliance access any customer? **YES** (any customer in org scope, full detail + PII).
- Object-scoped? **NO** — scope is org (hq_main) not per-customer/alert/investigation.
- Alert/investigation influences authorization? **NO** — authorization is permission+scope only; workflow context is not a factor.

---

## 12. Current RBAC Matrix

Permissions loaded from `role_permissions` in DB. Derived from migration 0005 (workbench) + init/11 (customer). **Note the 0005 seeding bug** (§ "Sensitive Permissions").

| Permission | Analyst | Compliance | Admin | Notes |
|---|:--:|:--:|:--:|---|
| `workbench:access` | ✓ | ✓ | ✓ | |
| `alert:read_assigned` | ✓ | ✓ | | compliance standalone alerts = non-canonical |
| `alert:read` | | | ✓ | broad read |
| `alert:assign` | | | ✓ | |
| `alert:acknowledge` | ✓ | | | |
| `alert:dismiss` | ✓ | | **admin has** | compliance NO (good) |
| `alert:investigate` | ✓ | | | |
| `alert:transition` | ✓ | **✓** | | compliance `alert:transition` = non-canonical |
| `investigation:read_own` | ✓ | | | |
| `investigation:read` | | ✓ | ✓ | compliance broad-read investigations |
| `investigation:update` | ✓ | | | |
| `investigation:modify_findings` | ✓ | | | (SoD prohibits admin) |
| `investigation:transition` | ✓ | | | |
| `investigation:review` | | **✓(bug affected? no—not in SENSITIVE)** | (prohibited) | compliance review |
| `investigation:assign` | | | ✓ | only for cancel; no assign endpoint |
| `case:create` | | ✓ | | |
| `case:read_assigned` | ✓ | ✓ | | analyst sees Cases module (non-canonical) |
| `case:read` | | | ✓ | |
| `case:transition` | | ✓ | | |
| `case:decision` | (prohibited) | **BUG — NOT SEEDED** | (prohibited) | **CRITICAL** |
| `case:close` | (prohibited) | **BUG — NOT SEEDED** | (prohibited) | **CRITICAL** |
| `case:assign` | (prohibited) | | ✓ | |
| `case:reopen` | | | ✓ | |
| `info_request:create` | | ✓ | | compliance creates IRs (canonical ✓) |
| `info_request:read_assigned` | ✓ | | | |
| `info_request:read` | | ✓ | ✓ | compliance broad IR read |
| `info_request:respond` | ✓ | | | analyst answers (canonical ✓) |
| `info_request:accept` | | ✓ | | |
| `info_request:return` | | ✓ | | |
| `info_request:cancel` | | ✓ | ✓ | |
| `approval:request` | ✓ | ✓ | ✓ | |
| `approval:approve` | (prohibited) | ✓ | | |
| `approval:read` | ✓ | ✓ | ✓ | |
| `comment:create`/`read` | ✓ | ✓ | ✓ | |
| `comment:view_internal_content` | | ✓ | | compliance reads internal comments |
| `comment:view_metadata` | | | ✓ | |
| `comment:redact` | | | ✓ | |
| `timeline:read` | ✓ | ✓ | ✓ | |
| `notification:read/update` | ✓ | ✓ | ✓ | |
| `admin:outbox_monitor/retry` | | | ✓ | |
| `customer:*` | basic/financial/txn/kyc/risk (no PII) | + hist + PII | metadata only | manager denied |

**`manager`:** deprecated role, zero workbench permissions, PROHIBITED from `workbench:access` and operational actions.

### The Seeded-Permission Bug (CRITICAL)

Migration `0005_add_permission_seeds.py`:
```python
SENSITIVE_PERMISSIONS = {"case:decision","case:close","investigation:modify_findings","remediation:verify","evidence:destroy"}
for role, perms in ROLE_PERMISSIONS.items():
    for perm in perms:
        if perm not in SENSITIVE_PERMISSIONS or role == "analyst":
            conn.execute(INSERT role_permissions ...)
```
- `case:decision` and `case:close` (in SENSITIVE, role != analyst) → **skipped for compliance and admin**. They are only seeded for **analyst** (who is then PROHIBITED from using them).
- **Result:** compliance **cannot** record decisions or close cases at the permission layer. `case_service.record_decision()`/`close()` would fail at authorise Step 3. This is a P0 blocker for the canonical workflow (Compliance Officer must close-not-harmful and create cases — case creation works via `case:create`, but the down-stream `case:decision`/`case:close` do not).
- `investigation:modify_findings` is correctly seeded for analyst (role == analyst branch).

---

## 13. Row-Level Ownership

| Endpoint list | Filters by | Can A see B's? |
|---|---|---|
| `GET /alerts/assigned` | `assigned_to = self` + `scope_id` | A cannot see B's alerts (unless same assignment) |
| `GET /alerts/{id}` | `alert:read_assigned`(ownership) OR `alert:read`(admin) | analyst no; compliance no (unless assigned); admin yes (broad) |
| `GET /investigations/assigned` | `assigned_to = self` + `scope_id` | Analyst A **cannot** see B's investigations |
| `GET /investigations/submitted` | `scope_id` + status=submitted (NO assigned_to filter) | compliance sees **all** submitted in scope (= B's too) |
| `GET /investigations/{id}` | `read_own`(ownership) OR `read`(compliance/admin) | compliance/admin yes; analyst only own |
| `GET /cases/assigned` | `assigned_to = self` + `scope_id` | Compliance A cannot see B's assigned (unless same) |
| `GET /cases/unassigned` | `assigned_to IS NULL` + `scope_id` | any with `case:read` sees unassigned pool |
| `GET /cases/{id}` | `read_assigned`(ownership) OR `read`(admin) | analyst only assigned; compliance/admin broader |
| `GET /information-requests/assigned` | `assigned_to = self` + parent scope | Analyst A sees only own IRs |
| `GET /information-requests/{id}` | `read_assigned`(ownership) OR `read`(compliance) | compliance broad |
| `GET /cases/{id}/information-requests` & `/investigations/{id}/information-requests` | service post-filters by role: read_assigned→own; read→created_by or case.assigned_to; admin→all | Analyst sees own; compliance sees created/own-case |
| `GET /approval-requests` | role: compliance→others' requests; analyst/admin→own | scoped |

**Direct answers:**
- **Can Analyst A see Analyst B's investigations?** **NO** (list scoped to `assigned_to=A`; no broad read).
- **Can Analyst A see Analyst B's information requests?** **NO** (`assigned_to=A` only).
- **Can Analysis A see B's reports?** **NO** (reports embedded in investigations, scoped above).
- **Can Compliance A see Compliance B's assigned investigations?** Through `/investigations/submitted` **YES** for any `submitted` investigation in scope; through `/investigations/{id}` **YES** (broad `investigation:read`). The canonical "assigned investigations only" is **not** enforced for compliance on submitted/read.

---

## 14. Frontend vs Backend Authorization

**Frontend visibility is NOT authorization for most actions** — backend policy engine is authoritative. Main deviations:

| Area | Frontend (UI) | Backend reality | Verdict |
|---|---|---|---|
| Analyst sees Cases module/nav | YES (permission `case:read_assigned`) | Analyst CAN read assigned cases; cannot decide/close/assign/case:create (no perms + PROHIBITED) | **Consistent** functionally, but module visibility violates canonical (see §22) |
| Analyst sees IR create button on investigation | only if `investigation:review` OR `info_request:create` — analyst has neither → button hidden | backend also denies (no `info_request:create`) | **Consistent** |
| Compliance sees Create Investigation | only if `alert:investigate` + assignee — compliance lacks permission → hidden | backend denies | **Consistent** |
| Compliance sees Dismiss | only if `alert:dismiss` + assignee — compliance lacks → hidden | backend denies | **Consistent** |
| Compliance standalone Alerts/IR modules | **shown** (route + permission) | backend allows read via `alert:read_assigned`/`info_request:read` | **Conflicting with canonical target** (module segregation), though not a backend permission escalation for actions |
| Admin broad reads | admin has `alert:read`, `investigation:read`, `case:read` but **no UI** to use them (queues all call `/assigned`) | backend allows broad GET | **Latent capability, no exposed gap** |
| Analyst "Record Decision"/"Close" | hidden (no `case:decision`/`case:close` perm) | backend denies (permission + PROHIBITED) | **Consistent** |

**Authorization gaps found** (UI hides but backend permits / role can do something canonical says it shouldn't):

- **P0** — Compliance **can** read/submit within Alerts + Information Requests modules and **can** call `/alerts/assigned`, `/alerts/{id}/escalate` (`alert:transition`), `/information-requests/assigned` — violating the canonical "Compliance has NO standalone Alerts / NO standalone Information Requests modules."
- **P0** — Compliance **lacks** `case:decision`/`case:close` due to seed bug (reverse gap: UI would show if backend allowed, but backend denies → compliance cannot do canonical actions).
- **P2** — Compliance can read **any** submitted investigation in scope (`investigation:read`), not just assigned ones — violates canonical "assigned investigations only."
- **P2** — Analyst is shown the Cases module (can read assigned via `case:read_assigned`), violating canonical "Analyst has NO standalone Compliance Cases."

---

## 15. Current State Machines

Definitions from enums/CHECK constraints (do not invent states).

### Alert
```
new ──assign──▶ assigned ──acknowledge──▶ acknowledged
                                              │
            assign ┌─────────────────────────┤
                   ▼                         ▼ (investigate)
           (any, admin)                under_investigation ──escalate/resolve──▶ resolved
                                     acknowledged/under_investigation
                                           │
                                           ▼ (dismiss, approval-gated crit/high)
                                        dismissed
```
Statuses: **new, assigned, acknowledged, under_investigation, resolved, dismissed**

### Investigation
```
open ──(start)──▶ active ──(submit, findings req)──▶ submitted ──(review not-harmful)──▶ completed
                    ▲                                    │
                    └────(resume) returned ◀──(return for revision, review)──┘
                              │
                              └──(IR created while submitted)──▶ awaiting_information
                              (open ─▶ cancelled by admin)
```
Statuses: **open, active, awaiting_information, submitted, returned, completed, cancelled**
(The canonical "UNDER_COMPLIANCE_REVIEW" is represented by `submitted`; "ADDITIONAL_INFO_REQUESTED" by `awaiting_information`; "ESCALATED_TO_COMPLIANCE_CASE" is a completed investigation + a created case.)

### InformationRequest
```
open ──acknowledge──▶ acknowledged ──respond──▶ responded ──accept──▶ accepted
                          ▲                        │
                          └─────────return─────────┘
   (open/acknowledged ─▶ cancelled)
```
Statuses: **open, acknowledged, responded, accepted, returned, cancelled**

### ComplianceCase
```
open ─▶ assigned ─▶ under_review ─▶ decision_pending ─▶ … ─▶ resolved ─▶ closed
                                                              (approval-gated crit/high)
   open ─▶ cancelled ; closed ─(reopen, approval-gated)──▶ open/assigned
   under_review ─(request info)──▶ awaiting_information
```
Statuses: **open, assigned, under_review, awaiting_information, decision_pending, awaiting_compliance_action, resolved, closed, cancelled**

### ApprovalRequest
**pending → approved / rejected / expired / cancelled**

---

## 16. Audit Trail

**Audited (via `audit_outbox` + `activity_timeline`):**

| Event | Timeline event | Outbox | Notes |
|---|---|---|---|
| Alert assign/ack/dismiss/investigate/escalate | ✓ | ✓ | via outbox in UoW |
| Alert dismissal justification | stored in `alerts.dismissed_reason` | ✓ | |
| Investigation creation | ✓ | ✓ | |
| Report update (findings) | ✓ | ✓ | version-bumped |
| Submission (`active→submitted`) | ✓ | ✓ | `submitted_at` |
| **Assignment** | recorded in `assignment_history` | — | only alert/case/IR assignment; **no investigation assignment exists** |
| Information request create/ack/respond/accept/return | ✓ | ✓ | |
| Compliance decision | ✓ | ✓ | `decisions.rationale` |
| Not-harmful close | ✓(via completed timeline) | ✓ | rationale as internal comment |
| Case creation (escalate) | ✓ | ✓ | |
| Case close/reopen | ✓ + approval | ✓ | |

**Missing / notable:**
- No dedicated **`investigation` assignment** event (feature absent).
- Statements for not-harmful / escalate are embedded in comment text, not a structured `decision_statement` / `escalation_statement` column/event.
- No `updated_by` tracking on operational tables (only `version`).

---

## 17. Comments / Evidence

### Comments
- Who can add: `comment:create`; who can read: `comment:read` (+`comment:view_internal_content` for compliance internal).
- **Not immutable:** comments can be redacted (admin, `comment:redact`) with `original_content_hash`; no hard immutability.
- Author/time stored: `author_id`, `created_at`. ✓
- Analyst vs compliance distinguished: via `author_id` + role at read time; no explicit "analyst"/"compliance" authoring column, but `is_internal` flag exists.

### Evidence / Attachments
- **Support EXISTS:** `investigation_attachments` table + attachment endpoints (upload/download/delete, ≤10MB, SHA-256, content-type). Upload requires `investigation:update`/`modify_findings` + ownership + status active/returned. Evidence is per-investigation.

---

## 18. Compliance Officer Discovery

- **No dedicated "available / eligible Compliance Officers" endpoint exists.**
- Only admin-only `GET /admin/users` lists users (with roles) — **not usable by an analyst or compliance officer** for assignment pickers.
- `approval_service._fetch_eligible_approvers()` is a private helper (queries active in-scope compliance officers) — not exposed as an API.
- **No availability or workload logic anywhere.**
- **Conclusion:** Only **role-eligibility** is conceptually possible (via querying users by role=compliance); no availability/workload. No safe public endpoint today. New endpoint required.

---

## 19. Decision Statements (mandatory justification audit)

| Decision | Classification | Sourced From |
|---|---|---|
| Analyst dismiss alert | **MANDATORY** | `DismissAlertRequest.dismissed_reason` (required) + frontend required |
| Compliance request additional info (IR) | **MANDATORY** | `CreateInformationRequest.question` (NOT NULL) — question is the statement |
| Compliance close not-harmful | **MANDATORY** | `ReviewNotHarmfulRequest.rationale` (min_length=1), persisted as `[Not Harmful] …` comment |
| Compliance create case (escalate) | **MANDATORY** | `EscalateInvestigationRequest.rationale` (min_length=1), persisted as comment |
| Record decision on case | **MANDATORY** | `RecordDecisionRequest.rationale` (NOT NULL) |
| IR return / cancel | **OPTIONAL** | `return_reason`/`cancel_reason` nullable |

**All four canonical mandatory statements are present and enforced (required).** The gap is that not-harmful/escalate statements are stored as comment text rather than structured columns.

---

## 20. API Contract Map (workflow APIs)

Format: METHOD / PATH / PERMISSION / ROW SCOPE / PURPOSE

| METHOD | PATH | PERMISSION | ROW SCOPE | PURPOSE |
|---|---|---|---|---|
| GET | /alerts/assigned | alert:read_assigned | own+scope | analyst queue |
| GET | /alerts/{id} | read_assigned \| read | own / broad | alert detail |
| PATCH | /alerts/{id}/assign | alert:assign | admin | assign alert |
| PATCH | /alerts/{id}/acknowledge | alert:acknowledge | ownership | ack |
| PATCH | /alerts/{id}/dismiss | alert:dismiss | ownership | dismiss (approval crit/high) |
| POST | /alerts/{id}/investigate | alert:investigate | ownership | create investigation |
| POST | /alerts/{id}/escalate | alert:investigate | ownership | escalate alert |
| GET | /investigations/assigned | investigation:read_own | own+scope | my investigations |
| GET | /investigations/submitted | investigation:review | all submitted in scope | compliance review queue |
| GET | /investigations/{id} | read_own \| read | own / broad | detail |
| PATCH | /investigations/{id} | update / modify_findings | ownership+state | edit findings |
| PATCH | /investigations/{id}/transition | investigation:transition | ownership+state | status transition |
| POST | /investigations/{id}/cancel | investigation:transition | admin | cancel |
| POST | /investigations/{id}/review/not-harmful | investigation:review | state=submitted | close not-harmful |
| POST | /investigations/{id}/review/escalate | review + case:create | state=submitted | escalate to case |
| POST/GET/DELETE | /investigations/{id}/attachments… | update / read_own\|read | ownership | evidence |
| GET | /cases/assigned | case:read_assigned | own+scope | my cases |
| GET | /cases/unassigned | case:read | unassigned+scope | pool |
| GET | /cases/{id} | read_assigned \| read | own / broad | detail |
| PATCH | /cases/{id}/assign | case:assign | admin | assign/claim |
| PATCH | /cases/{id}/transition | case:transition | ownership | transition |
| POST | /cases/{id}/close | case:close | ownership/compliance + approval | close |
| POST | /cases/{id}/reopen | case:reopen | admin + approval | reopen |
| POST | /cases/{id}/decisions | case:decision | ownership+state | record decision |
| GET | /cases/{id}/decisions | read_assigned \| read | own / broad | list decisions |
| POST | /cases/{id}/information-requests | info_request:create | — | create IR on case |
| POST | /investigations/{id}/information-requests | info_request:create | — | create IR on investigation |
| GET | /information-requests/assigned | info_request:read_assigned | own | analyst inbox |
| GET | /information-requests/{id} | read_assigned \| read | own / broad | IR detail |
| PATCH | /information-requests/{id}/acknowledge | (status) | ownership | ack |
| PATCH | /information-requests/{id}/respond | info_request:respond | ownership | respond |
| PATCH | /information-requests/{id}/accept | info_request:accept | creator | accept |
| PATCH | /information-requests/{id}/return | info_request:return | creator | return |
| POST | /information-requests/{id}/cancel | info_request:cancel | creator/admin | cancel |
| GET/POST | /approval-requests | approval:read / request | role-scoped | approvals |
| POST | /approval-requests/{id}/vote | approval:approve | no-coi | vote |
| GET/POST | /{type}/{id}/comments | comment:read / create | workflow-gated | comments |
| PATCH | /comments/{id}/redact | comment:redact | admin | redact |
| GET | /{type}/{id}/timeline | timeline:read | workflow-gated | timeline |
| GET | /api/v1/customers/{id}/overview | any customer:read_* | org scope | customer 360 |
| GET | /api/v1/customers/{id}/transactions | customer:read_transactions | org scope | customer txn |
| GET | /admin/users | admin | all | officer discovery (admin only) |
| GET | /admin/outbox, /admin/orphan-assignments | admin:outbox_monitor, admin:orphan_monitor | all | ops |

---

## 21. Canonical Target Workflow (restated)

**Analyst:** triage alerts (dismiss w/ justification | start investigation) → build investigation report (editable pre-submit) → select eligible Compliance Officer → submit (report becomes immutable) → answer own Information Requests. Customer 360 only as authorized.

**Compliance Officer:** assigned Investigations → review origin alert in context → view analyst report + Customer 360 → Request Additional Info | Declare Not Harmful | Create Compliance Case (each with mandatory statement). No standalone Alerts / no standalone Information Requests modules.

**Ownership:** Alert = triage object; Investigation = analyst+handoff object; InformationRequest = feedback loop inside an Investigation; ComplianceCase = formal escalation.

**Target matrix** per §E (Analyst vs Officer).

---

## 22. Gap Analysis (current vs canonical)

Classification legend: ✅ ALREADY_CORRECT · 🟡 PARTIALLY_IMPLEMENTED · ❌ MISSING · ⚠️ CONFLICTING · 🔴 SECURITY_GAP · 🗄️ NEEDS_MIGRATION

| Requirement | Class | Detail |
|---|---|---|
| Analyst views authorized alerts | ✅ | assigned only |
| Analyst dismiss alert w/ mandatory justification | ✅ | required reason |
| Analyst starts investigation (linked to alert) | ✅ | `alert:investigate`, permanent FK |
| Analyst report structured fields | 🟡 | free-text findings + conclusion + refs; not decomposed |
| Analyst edits report pre-submit | ✅ | active/returned |
| Report immutable post-submit | ⚠️ | immutable while submitted, but Return→active re-enables edits |
| Analyst selects Compliance Officer | ❌ | no assign endpoint, no officer picker |
| Submit investigation | ✅ | active→submitted (+findings req) |
| Assignment validated to officer role | ❌ | no role check anywhere |
| Officer standalone Alerts module | ⚠️ | compliance has route+`alert:read_assigned` (should be NO) |
| Officer standalone Info Requests module | ⚠️ | compliance has route+`info_request:read` (should be NO) |
| Officer requests additional info | ✅ | IR create on investigation (but should be within investigation workflow, not standalone) |
| Officer closes not-harmful w/ statement | ✅ | required rationale (as comment) |
| Officer creates Compliance Case w/ statement | ✅ | required rationale (as comment) |
| Officer records decision / close case | 🔴 | **`case:decision`/`case:close` not seeded for compliance (P0)** |
| Officer reviews only assigned investigations | ⚠️ | sees all submitted in scope + broad `investigation:read` |
| Analyst no standalone Compliance Cases | ⚠️ | analyst has `case:read_assigned` + Cases nav |
| Proofence ALERT→INVESTIGATION→CASE | ✅ | FK RESTRICT chain |
| Customer 360 scoped through workflow | 🟡 | permission+org-scope, not object-scoped |
| Mandatory decision statements | ✅ | all four required present |
| Segregation of duties (admin ≠ compliance) | ✅ | PROHIBITED blocks admin decision/close/review/findings |
| Audit trail for all workflow events | 🟡 | present, but statements unstructured, no investigation-assign event |
| Attachments/evidence | ✅ | per-investigation upload |

**SUMMARY BY CATEGORY:**
- **ALREADY_CORRECT:** analyst triage/dismiss/investigate, alert→investigation link, report pre-submit editing, submission, not-harmful+case creation with mandatory statements, provenance chain, attachments, admin compliance SoD.
- **PARTIALLY_IMPLEMENTED:** additional-info (within investigation, but standalone module leak), Immutability (Return→active), Compliance review scope (all submitted not just assigned), Customer 360 scope, audit structure.
- **MISSING:** officer discovery/assignment endpoint, role validation on assignment, analyst report structured fields, structured decision-statement columns, client-side analyst-specific vs officer-specific workspace segregation.
- **CONFLICTING:** Compliance standalone Alerts module, Compliance standalone Info Requests module, Analyst Cases module.
- **SECURITY_GAP:** Seeded-permission bug denying compliance decision/close (P0); Compliance `alert:transition`/`alert:read_assigned` enabling non-canonical alert ops; Compliance broad `investigation:read`.
- **NEEDS_MIGRATION:** only if seeding corrected (`role_permissions`) and/or new structured columns/assignment fields added.

---

## 23. P0 / P1 / P2 / P3 Priorities

### P0 — Authorization / SoD / data exposure
1. **Seed bug:** compliance missing `case:decision` + `case:close` (migration 0005 gate). Compliance cannot close cases or record decisions.
2. **Module segregation:** Compliance has standalone Alerts (`alert:read_assigned`, route) and standalone Info Requests (`info_request:read`) modules — violates canonical "no standalone Alerts / no standalone IR for Officer."
3. **Compliance `alert:transition` + `alert:read_assigned`** — allows non-canonical officer action on alerts (escalate) and standalone alert read.

### P1 — Workflow correctness
4. **No Investigation assignment / officer handoff:** the canonical "assign to eligible Compliance Officer" step is absent; no `assigned_to=officer`.
5. **No role validation** in assignment paths (`_validate_assignee` ignores role).
6. **No officer-discovery endpoint** (safe, role-filtered) for assignment pickers.
7. **Report immutability incomplete:** Return-for-Revision silently re-enables report edits post-submit (canonical wants immutable-with-IR-channel).

### P2 — Missing business capability
8. Structured report fields (findings/observed/mitigating/conclusion) — optional per architecture.
9. Structured decision/escalation statements (currently comment-text).
10. Compliance "assigned investigations" scope (currently all submitted in scope).
11. Analyst module segregation (Analyst should not see standalone Cases).

### P3 — UX / presentation
12. Role-specific workbench surfaces (analyst-only vs officer-only nav).
13. Officer picker UX (needs P1 backend endpoint first).
14. Compliance-not-harmful / case-create statements surfaced as structured fields.

---

## 24. Reusable Existing Components

**Do NOT rewrite.** The following can be reused as-is:

- **Policy engine** `services/shared/authorise.py` (10-step) — the ownership/SoD/state-machine backbone.
- **All tables** in `banking_integration` (alerts, investigations, information_requests, compliance_cases, decisions, comments, timeline, notifications, attachments, assignment_history, audit_outbox, approval_*).
- **Service classes** (alert/investigation/case/information-request/approval/comment/attachment/timeline/notification) — the state machines and ownership checks align closely with canonical.
- **Endpoints** — most are canonical-compatible (dismiss with mandatory reason, IR workflow, not-harmful, escalate, decision with rationale).
- **Frontend pages** — `AlertDetailPage`, `AlertQueuePage`, `InvestigationQueuePage` ("Submitted for Review" tab), `InvestigationDetailPage`, `CaseDetailPage`, `CaseQueuePage`, `IRInboxPage`, `RequestInfoDialog`, `MarkNotHarmfulDialog`, `EscalateToCaseDialog`, `Customer360Page`, `CustomerContextPanel`.
- **Customer 360** section-gating + PII masking model.
- **Outbox / audit / idempotency / optimistic-locking** infrastructure.

---

## 25. Proposed Minimal Future State Machines

Smallest compatible model, reusing current state names where possible (CONCEPTUAL ONLY — not implemented):

### Alert
```
OPEN(new/assigned/acknowledged)
   │
   ├── MARK_NOT_HARMFUL ──▶ DISMISSED
   └── START_INVESTIGATION ──▶ UNDER_INVESTIGATION ──▶ RESOLVED (on investigation completion)
```
(Maps to current: `new/assigned/acknowledged` ≙ OPEN; keep current sub-states. Add conceptually `UNDER_INVESTIGATION` already = current.)

### Investigation (reuse current statuses)
```
DRAFT(open) ─▶ IN_PROGRESS(active) ─▶ SUBMITTED_TO_COMPLIANCE(submitted)
                                              │
                    ┌─────────────────────────┤
                    ▼                          ▼
   ADDITIONAL_INFO_REQUESTED(awaiting_information)   UNDER_COMPLIANCE_REVIEW(=submitted, officer assigned)
                    │                               ├── CLOSED_NOT_HARMFUL(completed)
                    └── resume ─▶ active            └── ESCALATED_TO_COMPLIANCE_CASE(completed + case)
```
**Proposed addition requirements (minimal):**
- Add an assignment of the investigation to the compliance officer (**no new status)**: `submitted` + `assigned_to=officer` represents `SUBMITTED_TO_COMPLIANCE`.
- Keep `completed` for both CLOSED_NOT_HARMFUL and ESCALATED_TO_CASE (escalation evidenced by linked case).

### InformationRequest
```
OPEN(open) ─▶ ANSWERED(responded/acknowledged) ─▶ CLOSED(accepted)
                (returned re-opens)
```
(Maps to current statuses; no change.)

### ComplianceCase
```
OPEN(open) ─▶ UNDER_COMPLIANCE_REVIEW(assigned/under_review)
            ─▶ (decision_pending) ─▶ RESOLVED ─▶ CLOSED
```
(No new statuses required.)

**Migration impact of minimal model:** mostly **permission seeding** (role_permissions) + optionally a column for structured statements / an investigation `assigned officer` semtric. No new status enum migration needed if fully reusing current states.

---

## 26. Recommended Implementation Increments

All increments are **proposals only** (not implemented). Prefer 4–7 small increments.

### Increment 1 — Fix the Seeded-Permission Bug + Compliance SoD (P0, do first)
- **Backend:** Correct migration/seed so `case:decision` + `case:close` are granted to `compliance` (and removed from analyst); ensure admin remains PROHIBITED. Remove compliance's `alert:transition` and, if module segregation confirmed, `alert:read_assigned` + `info_request:read`/`accept`/`return` (or gate by context).
- **Frontend:** none or minimal boolean cleanup.
- **Migration:** **YES** (data-only `role_permissions` repair + `permissions` re-seed).
- **Security impact:** fixes P0 authorization correctness and SoD.
- **Tests:** seed-state tests asserting compliance can decide/close; regression on analyst/admin PROHIBITED; integration test for `case:decision`/`case:close` success after fix.

### Increment 2 — Compliance Investigation assignment + officer discovery (P1)
- **Backend:** add `GET /officers` (or use user service) role=compliance, active, in-scope; add `PATCH /investigations/{id}/assign` with **role validation** (target must be compliance), transition `submitted` (optionally set `assigned_to=officer`).
- **Frontend:** Submission flow lets analyst pick officer from discovered list.
- **Migration:** **NO** (uses existing `assigned_to` on investigations).
- **Security impact:** enables canonical handoff; closes P1 officer-role validation.
- **Tests:** role-validation unit tests; officer-discovery access control; analyst-assign flow.

### Increment 3 — Enforce report immutability post-submit (P1/P2)
- **Backend:** make Return-for-Revision produce an explicit, audited new-revision (or lock original report and require IR channel), instead of silently re-editing `findings_text`. Add structured `decision_statement`/`escalation_statement` columns or a `statements` artifact table.
- **Frontend:** surface immutable original + new IR responses.
- **Migration:** **PARTIAL** (new columns or table; no status changes).
- **Sustainability/test:** audit-trail test asserting original report byte-identical pre/post-submit.

### Increment 4 — Analyst vs Officer workspace/module segregation (P2/P3)
- **Backend:** strengthen so compliance cannot read standalone alerts/IRs (remove those broad perms or make them context-only), analyst cannot see Cases module.
- **Frontend:** role-specific nav grouping (hide Cases for analyst, hide Alerts/IR standalone for officer; keep IRs inside investigation).
- **Migration:** **NO** (frontend + role_permissions).
- **Tests:** sidebar-render per role; module-access backend tests.

### Increment 5 — Customer 360 workflow-scoping (P2/P3)
- **Backend:** make Customer 360 detail conditional on an authorized alert/investigation/case context (object-scope the overview), rather than purely org-scope.
- **Frontend:** keep context panel; restrict standalone customer search result set.
- **Migration:** **NO** (logic only) or **PARTIAL** for link-back.
- **Tests:** object-scoped authorization tests.

### Increment 6 — Audit/statement hardening (P3)
- **Backend:** emit structured audit events for investigation assignment, not-harmful statement, escalation statement; ensure every canonical action has a dedicated audit event + statement field.
- **Frontend:** display statements in timeline/case decision history.
- **Migration:** **PARTIAL** (columns/events) if needed.
- **Tests:** audit-event presence assertions.

Good practice: **Increment 1 first** (P0). Sequence 1→3→2→4→5→6 after re-prioritization per business.

---

## 27. Migration Impact

- **Required for correctness:** **PARTIAL** (data-only `role_permissions` repair for the seed bug; possible permission re-seed). No new status enums needed.
- **Optional enhancements:** new structured statement columns (`decision_statement`, `escalation_statement`) and / or an `investigation.assigned_officer` semantics use existing `assigned_to`. All are additive `ADD COLUMN` or new artifact table; **no status-machine migration** required (current enums already sufficient).
- Files: `migrations/versions/` (new revision for permission repair); `init/11-phase3a2…` untouched; `init/10-phase2b-permission-seeds.sql` (role_permissions) is the analogous seed that may need the same fix.
- **No DB data changes** unless a decision to backfill statements.

---

## 28. Risks / Open Questions

1. **Seed-bug blast radius:** confirm the production `role_permissions` truly lack `case:decision`/`case:close` for compliance (verify current DB, not just migration 0005 — `init/10-phase2b…` may already repair). If already repaired, downgrade P0-1.
2. **Module-segregation intent:** confirm business wants compliance to **fully remove** standalone Alerts/IR modules (canonical) vs. merely hide them. Backend enforcement decision needed.
3. **Compliance review scope:** whether compliance should see **only assigned** investigations (canonical) vs. all submitted in scope (current). This changes `GET /investigations/submitted` (P1/P2).
4. **Report immutability:** whether Return-for-Revision should create a new version/IR channel or genuinely lock the submitted report.
5. **Officer discovery authz:** whether a new officer-endpoint is security-sensitive (should it expose names? mask? require specific role).
6. **Customer 360 object-scoping:** substantial evolution; confirm scope/priority.
7. **Keycloak seeding:** verify Keycloak role→permission mapping also reflects these perms (the DB `role_permissions` is authoritative for workbench; SSO maps roles only).
8. **Legacy tables** (`aml_alerts`, `legacy_compliance_cases`): ensure the new workflow doesn't accidentally write to legacy tables.

---

## 29. GO / NO-GO for implementation

**RECOMMENDATION: CONDITIONAL GO — after resolving the P0 seed-bug confirmation and the module-segregation scoping decisions.**

- The system already implements **≈70%** of the canonical workflow correctly (triage, investigation, submission, IR loop, not-harmful, escalation, evidence, audit, SoD).
- The **single hard blocker** is the **P0 seed bug** denying Compliance `case:decision`/`case:close`, plus the **module-segregation** of standalone Alerts/IR for Compliance.
- **GO** for Increment 1 (P0 fixes) once the seed-state is verified in the live DB.
- **NO-GO** for any full rewrite — reuse the existing tables, services, and policy engine.

---

---

# FINAL RETURN (A–AE)

**A. Relevant frontend files**
- `frontend/src/App.tsx`, `frontend/src/lib/navigation.ts`, `frontend/src/lib/permissions.ts`, `frontend/src/components/auth/ProtectedRoute.tsx`, `frontend/src/components/PermissionGate.tsx`, `frontend/src/components/Layout/BankingSidebar.tsx`, `frontend/src/components/CommandPalette.tsx`
- Alerts: `components/alerts/AlertQueuePage.tsx`, `AlertDetailPage.tsx`, `dialogs/DismissAlertDialog.tsx`, `InvestigateAlertDialog.tsx`, `EscalateAlertDialog.tsx`, `AssignAlertDialog.tsx`
- Investigations: `components/investigations/*` (Queue, Detail, FindingsEditor, EvidenceUploadPanel, CommentsTab, TimelineTab, `dialogs/*`)
- Cases: `components/cases/*` (Queue, Detail, `dialogs/*`)
- Info Requests: `components/informationRequests/IRInboxPage.tsx`, `IRResponseDialog.tsx`
- Approvals: `components/approvals/*`
- Customer 360: `components/customers/CustomerSearchPage.tsx`, `Customer360Page.tsx`, `CustomerContextPanel.tsx`
- Aberrations: `frontend/src/api/{alerts,investigations,cases,informationRequests,approvals,customer360}Api.ts`, `frontend/src/types/{alerts,investigations,cases,customer360}.ts`

**B. Relevant backend files**
- Policy: `services/shared/authorise.py`
- Workbench: `services/workbench/services/{alert,investigation,case,information_request,approval,comment,attachment,timeline,notification,entity_access,admin_outbox,admin_orphan}_service.py`, `repos.py`, `uow.py`, `routers/*`, `schemas/*`, `models.py`, `integration_app.py`
- Gateway: `services/api_gateway/routes.py`, `services/api_gateway/auth.py`, `keycloak_auth.py`, `services/api_gateway/customer360/{service,models,repos}.py`
- Shared: `services/shared/models.py`

**C. Relevant DB tables**
- `alerts`, `investigations`, `investigation_attachments`, `compliance_cases`, `decisions`, `information_requests`, `approval_requests`, `approval_decisions`, `comments`, `activity_timeline`, `notifications`, `assignment_history`, `audit_outbox`, `api_idempotency`, `organisation_scopes`, `user_scopes`, `users`, `roles`, `role_permissions`, `permissions` (in `banking_integration`). Legacy (Inc 1, banking_dev): `legacy_compliance_cases`, `aml_alerts`, `kyc_cases`, `compliance_reviews`.

**D. Existing Alert statuses**
`new, assigned, acknowledged, under_investigation, resolved, dismissed`

**E. Existing Investigation statuses**
`open, active, awaiting_information, submitted, returned, completed, cancelled`

**F. Existing InformationRequest statuses**
`open, acknowledged, responded, accepted, returned, cancelled`

**G. Existing ComplianceCase statuses**
`open, assigned, under_review, awaiting_information, decision_pending, awaiting_compliance_action, resolved, closed, cancelled`

**H. Analyst current capabilities**
Triage assigned alerts; acknowledge; dismiss (mandatory reason, approval-gated crit/high); start investigation; build/edit findings + conclusion pre-submit; submit investigation; answer own information requests (`info_request:respond`); read own investigations/alerts/IRs/cases; add/read comments; request approvals; read customer 360 (basic/financial/txn/KYC/risk, PII masked). NOT: create cases, decide/close, review, assign, approve, create IRs, access all-in-scope.

**I. Compliance current capabilities**
Read assigned alerts (standalone Alerts module); escalate alerts (`alert:transition`); read all submitted investigations in scope + review (Not Harmful / Return / Escalate to Case); create IRs on investigations/cases; accept/return IRs; create cases; standalone IR + Cases modules; read customer 360 full detail + PII. **BLOCKED (bug): cannot record `case:decision` or `case:close`.**

**J. Admin current capabilities**
Broad reads (`alert:read`, `investigation:read`, `case:read`, `info_request:read`); assign/reassign alerts/cases/investigations; reopen cases; cancel investigations; redact comments; view internal/metadata; monitor/retry outbox; user/role admin; customer 360 metadata-only. **PROHIBITED (SoD):** `case:decision`, `case:close`, `investigation:review`, `investigation:modify_findings`.

**K. Can Analyst A see Analyst B investigations?** **NO** — scoped to `assigned_to=A`.

**L. Can Analyst A see Analyst B information requests?** **NO** — scoped to `assigned_to=A`.

**M. Can Compliance A see Compliance B investigations?** **YES** (via `GET /investigations/submitted` for all in scope, and `GET /investigations/{id}` via broad `investigation:read`). Contradicts canonical "assigned only."

**N. Can Compliance access standalone Alerts?** **YES** — route + `alert:read_assigned` seeded. **CONFLICTS with canonical (should be NO).**

**O. Can Compliance access standalone Information Requests?** **YES** — route + `info_request:read` seeded. **CONFLICTS with canonical (should be NO).**

**P. Is alert dismissal justification mandatory?** **YES** (MANDATORY).

**Q. Is compliance info-request statement mandatory?** **YES** (MANDATORY; `question` NOT NULL).

**R. Is compliance not-harmful statement mandatory?** **YES** (MANDATORY; `rationale` min_length=1).

**S. Is compliance-case escalation statement mandatory?** **YES** (MANDATORY; `rationale` min_length=1).

**T. Can analyst report be edited after submission?** **NO while `submitted`; YES after Return-for-Revision** (`returned→active`). Not permanently immutable.

**U. Can Analyst assign a Compliance Officer?** **NO** — no investigation-assign endpoint exists.

**V. Is target role validated?** **NO** — `_validate_assignee()` checks existence/status/scope only, never role.

**W. Current Customer360 authorization behavior**
Permission-based (any `customer:read_*` gate; per-section masking) + org-scope-based (hq_main/global = unrestricted all customers; else branch/region). Not object-scoped by alert/investigation/case. Analyst: no PII; Compliance: full + PII; Admin: metadata-only; Manager: none.

**X. P0 security gaps**
1. Compliance missing `case:decision`+`case:close` (seed bug) — cannot do canonical officer decisions/closes. 2. Compliance standalone Alerts module (`alert:read_assigned`) + `alert:transition` escalation — non-canonical officer alert ops. 3. Compliance standalone Info Requests module (`info_request:read`). No role-validation on assignment remains P1 but is authorization-relevant.

**Y. P1 workflow gaps**
Investigation-to-officer assignment (missing), officer discovery endpoint (missing), role validation on assignment (missing), report immutability incomplete (Return→active), compliance review scope (all submitted, should be assigned-only).

**Z. Missing capabilities**
Officer discovery endpoint; investigation assignment; role-validated assignment; structured officer decision/escalation statements; structured report fields; role-specific workspace segregation (analyst-only vs officer-only nav); object-scoped Customer 360.

**AA. Components that can be reused**
Policy engine (`authorise.py`); all workflow tables; alert/investigation/case/IR/approval/comment/attachment/timeline/notification service classes; most endpoints; frontend Alert/Investigation/Case/IR pages + dialogs + Customer 360. Outbox/audit/idempotency/optimistic-lock infrastructure.

**AB. Migration required?** **PARTIAL** — data-only `role_permissions` repair for the P0 seed bug is required; optional additive columns/table for structured statements; **no status-enum migration needed** (current enums sufficient).

**AC. Recommended first implementation increment**
**Increment 1 — Fix the Seeded-Permission Bug + Compliance SoD** (grant `case:decision`/`case:close` to compliance, remove compliance `alert:transition`, and resolve/remove compliance standalone Alerts + IR modules).

**AD. Exact files likely to change in first increment**
- `migrations/versions/` (new revision repairing `role_permissions`; possibly `init/10-phase2b-permission-seeds.sql`, `init/11-phase3a2-customer-permission-seeds.sql` if needed)
- `services/shared/authorise.py` (PROHIBITED / permission set if changing compliance capability)
- `services/workbench/services/{case,alert}_service.py` (guard consistency)
- `frontend/src/lib/navigation.ts`, `frontend/src/lib/permissions.ts`, `frontend/src/components/Layout/BankingSidebar.tsx` (module segregation)
- `frontend/src/App.tsx` (route role/permission gates)
- Tests: `services/workbench/tests/*` (permission + integration), `services/api_gateway/customer360/tests/*` if touched.

**AE. GO / NO-GO**
**CONDITIONAL GO** — proceed with Increment 1 after (1) confirming the current live DB `role_permissions` still lacks `case:decision`/`case:close` for compliance, and (2) confirming the business decision to remove compliance standalone Alerts + Information Requests modules. No full rewrite is warranted.
