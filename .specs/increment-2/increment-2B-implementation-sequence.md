# Increment 2B — Implementation Sequence

Ordered task list. Each task: definition of done. No task starts until its dependency list is complete.

---

## Phase 2A Tasks (Foundation — complete before any 2B backend work)

### 2A.1 — Alembic Setup
**Depends on:** nothing
**DoD:**
- `alembic.ini` configured for `postgres-main`
- `migrations/env.py` imports existing DatabaseConnector DSN from settings
- `migrations/script.py.mako` standard template
- `alembic history` runs without error
- Dev: `alembic upgrade head` on empty DB runs cleanly through all revisions

### 2A.2 — Baseline Migration
**Depends on:** 2A.1
**DoD:**
- `0001_baseline_existing_schema.py` created — copies existing init SQL verbatim with IF NOT EXISTS
- `alembic stamp a1b2c3d4` on seeded staging DB succeeds without error
- `alembic upgrade head` from baseline runs 0002–0006 correctly

### 2A.3 — Organisation Scope Migration
**Depends on:** 2A.2
**DoD:**
- `0002_add_organisation_scope.py` creates `organisation_scopes` and `user_scopes`
- `hq_main` and `global` seeds inserted
- All existing users auto-granted `hq_main` scope by migration data step
- Downgrade drops tables without error

### 2A.4 — Audit Outbox Migration
**Depends on:** 2A.2
**DoD:**
- `0003_add_audit_outbox.py` creates `audit_outbox` table and `audit_outbox_status` enum
- Unique index on `idempotency_key` present
- Partial index on `status IN (pending, failed)` present
- Downgrade drops cleanly

### 2A.5 — Operational Entity Migration
**Depends on:** 2A.3, 2A.4
**DoD:**
- `0004_add_operational_entities.py` creates all 11 tables in correct dependency order
- All FK constraints present; deferred FK constraints for circular references
- All indexes from domain-model.sql present
- Downgrade drops all 11 tables in reverse order

### 2A.6 — Permission Seed Migration
**Depends on:** 2A.5
**DoD:**
- `0005_add_permission_seeds.py` inserts all permission codes from authorisation-policies.md
- `role_permissions` junction populated for analyst, compliance, admin
- `workbench:access` granted to analyst, compliance, admin
- SENSITIVE permissions inserted but NOT granted to admin
- `manager` gets zero new permissions
- Downgrade removes seeded rows

### 2A.7 — Manager Deprecation Migration
**Depends on:** 2A.6
**DoD:**
- `0006_deprecate_manager_role.py` updates `roles.description`
- `legacy_role` column added to `users`
- Existing manager users have `legacy_role=TRUE`
- Manager user login still works; workbench routes return 403

### 2A.8 — Authorise() Policy Engine
**Depends on:** 2A.6
**DoD:**
- `services/shared/authorise.py` implements all 10 evaluation steps
- Unit tests cover all PROHIBITED combos (each returns 403)
- Unit tests cover scope denial (returns 404)
- Unit tests cover ownership denial (returns 404)
- Unit tests cover workflow state denial (returns 409)
- Unit tests cover approval prerequisite denial (returns 428)
- Unit tests cover conflict of interest (returns 403)
- No HTTP in policy engine; all checks use passed `db` or passed `user` object

### 2A.9 — Audit Agent Idempotency
**Depends on:** 2A.4
**DoD:**
- `audit_log` table in `postgres-audit` has `idempotency_key VARCHAR(255) UNIQUE`
- `audit_agent/audit_logger.py` handles duplicate key on INSERT: returns existing row, status 200
- `X-Idempotency-Key` header accepted on `POST /log_access`

### 2A.10 — Frontend Permission Gate
**Depends on:** nothing (parallel with backend 2A)
**DoD:**
- `frontend/src/lib/permissions.ts` type file created
- `frontend/src/components/PermissionGate.tsx` implemented
- `usePermissions()` hook reads from `useAuth()` user.permissions
- Existing `ProtectedRoute` updated: Inc 2 routes use `PermissionGate` not `requiredRole`
- Manager user sees no sidebar links to workbench routes

---

## Phase 2B Tasks (Vertical Slice — in order)

### 2B.1 — Database Layer (asyncpg query functions)
**Depends on:** 2A.5
**DoD:**
- Query functions for all 11 new tables: `fetch_alert`, `update_alert`, `insert_investigation`, etc.
- All use `WHERE version = $N` for optimistic locking
- All return typed Pydantic models (no raw dicts at service layer)
- `insert_audit_outbox()` helper: computes idempotency_key, inserts atomically

### 2B.2 — Outbox Worker
**Depends on:** 2A.9, 2B.1
**DoD:**
- `services/api_gateway/outbox_worker.py` asyncio task
- Worker runs every 5s in API gateway lifespan
- `SELECT FOR UPDATE SKIP LOCKED` — no double-delivery from concurrent workers
- Retry backoff table: [10, 30, 120, 600, 1800] seconds
- Poison at attempt_count=5; notify admin
- Reconciliation task runs every 15min
- Unit tests: mock audit agent HTTP; verify state transitions pending→delivered, pending→failed, failed→poison

### 2B.3 — Alert Endpoints (6)
**Depends on:** 2A.8, 2B.1, 2B.2
**DoD:**
- All 6 alert endpoints implemented per API contracts
- `authorise()` called before each mutation
- Each mutation: atomic transaction with activity_timeline + notifications + audit_outbox
- State machine transitions match increment-2B-state-machines.md exactly
- Optimistic lock: 409 on version mismatch
- Idempotency: re-investigate, re-escalate return existing entities
- Integration tests: T01–T35 relevant alert rows pass
- Forbidden tests: F01, F09, F13 pass (403/409)

### 2B.4 — Investigation Endpoints (5)
**Depends on:** 2A.8, 2B.1, 2B.2
**DoD:**
- All 5 investigation endpoints implemented
- Findings update emits hashed before/after in audit payload
- Transition endpoint validates state machine
- Integration tests pass

### 2B.5 — Case Endpoints (7)
**Depends on:** 2A.8, 2B.1, 2B.2, 2B.3
**DoD:**
- All 7 case endpoints implemented
- `current_disposition_id` validation: application-level check that decision.case_id matches
- Admin content stripping on `case:read` with global scope
- Integration tests pass
- PROHIBITED: admin case:decision, case:close enforced

### 2B.6 — InformationRequest Endpoints (8)
**Depends on:** 2A.8, 2B.1, 2B.2, 2B.5
**DoD:**
- All 8 IR endpoints implemented
- IR state machine matches increment-2B-state-machines.md IR section
- IR accept triggers notification to case assignee to manually trigger C4
- Integration tests for IRS01 full cycle pass

### 2B.7 — Decision Endpoints (2)
**Depends on:** 2A.8, 2B.1, 2B.2, 2B.5
**DoD:**
- POST /cases/:id/decisions records decision, updates case status per decision_type
- current_disposition_id updated atomically
- report_to_authority requires approval (step 8 in authorise())
- DP01–DP05 scenarios pass

### 2B.8 — Approval Endpoints (4)
**Depends on:** 2A.8, 2B.1, 2B.2
**DoD:**
- All 4 approval endpoints implemented
- Conflict of interest check: requester != approver
- Unique constraint on (approval_request_id, approver_id) surfaced as 409
- Expiry worker: asyncio task, runs every 60s, sets expired approval rows
- AP01–AP04 scenarios pass
- EC03 (multiple required approvals) pass

### 2B.9 — Comment + Timeline + Notification Endpoints (8)
**Depends on:** 2B.1
**DoD:**
- All comment, timeline, notification endpoints implemented
- Internal comment visibility: compliance + admin only
- Comment redact (admin only): replaces content, emits audit event
- Timeline ordered by occurred_at ASC
- Notification unread count returned on GET

### 2B.10 — Admin Outbox Endpoints (2)
**Depends on:** 2B.2
**DoD:**
- GET /admin/outbox with status filter
- POST /admin/outbox/:id/retry resets to pending
- admin:outbox_monitor permission gating
- AU03, AU04 scenarios pass

### 2B.11 — Frontend: Alert Queue + Detail
**Depends on:** 2A.10, 2B.3
**DoD:**
- `/workbench/alerts` renders assigned alert list with filters
- `/workbench/alerts/:id` renders alert detail with action bar
- All four action buttons (acknowledge, create investigation, dismiss, escalate) render conditionally
- DismissModal: four-eyes flow for critical/high
- EscalateModal: creates case, navigates to it
- 409 handling: auto-refetch, banner shown
- InvestigationCreateModal: navigates to new investigation on 201

### 2B.12 — Frontend: Investigation Detail + Findings Editor
**Depends on:** 2A.10, 2B.4, 2B.11
**DoD:**
- `/workbench/investigations/:id` with 4 tabs
- Findings editor: textarea + refs list + auto-save with debounce
- Evidence tab: disabled panel "Available in Phase 2D"
- Return handling: yellow banner, return_reason visible
- All transition buttons conditional on status + permission

### 2B.13 — Frontend: Case Queue + Detail
**Depends on:** 2A.10, 2B.5, 2B.6, 2B.7, 2B.8
**DoD:**
- `/workbench/cases` with filters
- `/workbench/cases/:id` with all tabs
- Investigation tab: compliance can approve/return investigation
- IR tab: create IR modal; accept/return per IR
- DecisionForm: all decision types; report_to_authority approval flow
- CloseModal: four-eyes for high/critical
- All 409 patterns handled

### 2B.14 — Frontend: IR Inbox
**Depends on:** 2A.10, 2B.6
**DoD:**
- `/workbench/information-requests` analyst view
- Overdue badge on past due_date
- IR response form: acknowledge + respond buttons
- Returned IR: reason banner + re-acknowledge flow

### 2B.15 — Frontend: Approval Queue
**Depends on:** 2A.10, 2B.8
**DoD:**
- `/workbench/approvals` compliance view
- Approval detail modal with vote buttons
- Conflict of interest guard: own request → vote buttons hidden + message shown

### 2B.16 — Frontend: Notification Bell + Outbox Monitor
**Depends on:** 2A.10, 2B.9, 2B.10
**DoD:**
- Global notification bell with unread count
- Dropdown with last 10; mark all read
- `/workbench/admin/outbox` table with retry buttons
- Poison events highlighted in red

### 2B.17 — Integration Test Suite
**Depends on:** all 2B.1–2B.16
**DoD:**
- Full workflow test: T01 → T35 (valid transitions) pass sequentially against real DB
- XA01–XA10 (access control) pass
- V01–V08 (versioning) pass
- AU01–AU08 (outbox) pass with mock audit agent
- F01–F17 (forbidden) pass
- IRS01 full cycle passes
- DP01–DP05 decision paths pass

### 2B.18 — Staging Deployment + Smoke Test
**Depends on:** 2B.17
**DoD:**
- `alembic upgrade head` on staging succeeds
- Verification SQL from 2A §1.4 passes
- Health endpoints for all services return 200
- Manual workflow: alert → investigation → case → IR → decision → close performed end-to-end by tester
- Outbox monitor shows delivered events

---

## Timeline

| Task Group | Tasks | Est. Days |
|------------|-------|-----------|
| 2A Foundation | 2A.1–2A.10 | 5–6 |
| 2B Backend | 2B.1–2B.10 | 8–10 |
| 2B Frontend | 2B.11–2B.16 | 6–8 |
| 2B Testing + Staging | 2B.17–2B.18 | 3–4 |
| **Total** | | **22–28 days** |

**1 developer sequential:** 22–28 calendar days
**2 developers parallel** (backend + frontend after 2A): 14–18 calendar days

First implementation task: **2A.1 (Alembic setup)**. Takes < 1 hour. Unblocks entire 2A chain.
