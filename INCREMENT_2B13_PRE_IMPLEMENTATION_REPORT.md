# Increment 2B.13 — Frontend: Case Queue + Detail — Pre-Implementation Report

Status: Approved to proceed. Backend contract frozen (2B.5–2B.8 closures). No backend changes in this phase.

## 1. Task Definition

Frontend-only implementation of the workbench Compliance Case surfaces:

- `/workbench/cases` — Case Queue (`PermissionGate` `case:read_assigned`)
- `/workbench/cases/:caseId` — Case Detail (6 tabs: Overview | Investigation | Information Requests | Decisions | Comments | Timeline)
- Decision Form surface (spec route `/workbench/cases/:id/decisions`; see §4 mismatch — the backend exposes no decision sub-route, so the form renders inline in the Decisions tab / detail flow)

Frozen DoD (`increment-2B-implementation-sequence.md` §2B.13):
1. `/workbench/cases` with filters
2. `/workbench/cases/:id` with all tabs
3. Investigation tab: compliance can approve/return investigation
4. IR tab: create IR modal; accept/return per IR
5. DecisionForm: all decision types; report_to_authority approval flow
6. CloseModal: four-eyes for high/critical
7. All 409 patterns handled

Completion report is the closure-report structure established by 2B.11/2B.12.

## 2. Stack & Conventions (verified against the running code)

Same as 2B.11/2B.12 (React 18.3.1, react-router-dom 6.24, axios 1.7.2, lucide-react, clsx, date-fns). Established this phase:
- Pages use `useState`/`useEffect` + object-literal API modules. **No react-query usage** (verified: no existing page uses it).
- Reuse: `BankingHeader`, `StatusBadge`/`RoleBadge`, `Modal`, `PermissionGate`, `ProtectedRoute`, the workbench error parser pattern, `CommentsTab`/`TimelineTab` from 2B.12 (generalised for entity segments), `ConfirmTransitionDialog`/`ReturnInvestigationDialog` patterns from 2B.12.
- Queue 409 → auto-refetch + amber banner; dialogs close on 409; no `useBlocker` under the non-data `BrowserRouter` — unsaved guard is `beforeunload` + explicit-action `window.confirm` (2B.12 convention).
- Tests: vitest + @testing-library/react + jsdom; API tests mock `src/api/client`.

## 3. Backend Surface Consumed (as-built, authoritative — read from routers/services, NOT prose contracts)

Prefix `/api/v1`. Error envelope everywhere: `{ "error": CODE, "message": str }`.

### C1 — GET `/cases/assigned`
- Permission `case:read_assigned`. Params: `status`, `priority`, `page` (default 1), `per_page` (default **50**, max 100). **No `risk_level` filter** (see §4).
- Response `{ total, page, page_size, items: CaseResponse[] }`.
- CaseResponse: `case_id, title, description?, alert_id?, investigation_id?, scope_id, status, priority, risk_level?, regulatory_frameworks?, assigned_to?, created_by, target_date?, resolution?, resolved_at?, resolved_by?, closed_at?, closed_by?, current_disposition_id?, closure_approval_id?, reopen_reason?, version, created_at, updated_at`.
- Statuses: `open, assigned, under_review, awaiting_information, decision_pending, awaiting_compliance_action, resolved, closed, cancelled`. Priority: `low, medium, high, critical`. Risk levels mirror severities (`critical, high, medium, low`).

### C2 — GET `/cases/{case_id}`
- `case:read_assigned` (assignee) or admin `case:read` → full `CaseResponse`. Neither → 404. Detail must tolerate absent optional fields (e.g. unassigned case has `assigned_to: null`).

### C3 — PATCH `/cases/{case_id}/assign` (admin)
- Body `{ assigned_to, expected_version, reason? }`. Admin-only. Use for admin assignment/reassignment of an unassigned case from the detail page.

### C4 — PATCH `/cases/{case_id}/transition`
- Body `{ target_status, expected_version, resolution? }`. Permission `case:transition`.
- `ALLOWED_TRANSITIONS` (case_service.py, authoritative): `assigned→under_review`, `under_review→decision_pending`, `awaiting_compliance_action→resolved`. **No `open→`, no `awaiting_information→`, no `decision_pending→`, no `resolved→closed`, no `closed→open`.** Anything else → 409 `INVALID_TRANSITION` (tests assert `closed` is not reachable and no `/close`/`/reopen` routes exist).
- Action-bar mapping (spec labels): Begin Review (`assigned`), Request Information (opens IRCreateModal), Mark Decision Pending (`under_review`), Mark Action Completed / Resolve Case (`awaiting_compliance_action`), Record Decision (`decision_pending`).

### C5 — POST `/cases/{case_id}/decisions`
- Body `{ decision_type, rationale, approval_request_id?, expected_version }`. Permission `case:decision`. Precondition: status `decision_pending`. 201 → `CaseDecisionResponse { success, case, decision, version }`.
- `DECISION_TYPE_TARGET` (verified, all six resolve): `no_action→resolved`, `closure_recommended→resolved`, `warning→awaiting_compliance_action`, `enhanced_due_diligence_recommended→awaiting_compliance_action`, `report_to_authority_recommended→awaiting_compliance_action`, `account_action_recommended→awaiting_compliance_action`.
- **Approval gate:** `report_to_authority_recommended` requires `approval_request_id` whose approval is `entity_type=compliance_case`, `action_type=decision_report_to_authority`, status `approved`, unconsumed. Missing/not-approved → 428 `APPROVAL_REQUIRED`; already consumed → 409 `APPROVAL_EXECUTED`.

### C6 — GET `/cases/{case_id}/decisions`
- `{ data: DecisionResponse[] }` — newest first per spec. DecisionResponse: `decision_id, case_id, decision_type, rationale, decided_by, decided_at, is_final, supersedes_decision_id?, approval_id?, version, created_at`.

### C7 — IR router (compliance + analyst)
- `POST /cases/{case_id}/information-requests` (201): body `{ assigned_to, question, due_date?, expected_case_version }`. Create gates on case `under_review`; on success the case moves to `awaiting_information` (see §4 dead-end note). `expected_case_version` is the case version.
- `GET /cases/{case_id}/information-requests` (`status`, `page`, `per_page`) → IR list for the case.
- `GET /information-requests/{ir_id}` → full IR (assignee/`info_request:read_assigned`) or admin metadata-only view.
- `PATCH /information-requests/{ir_id}/accept` — body `{ acceptance_note?, expected_version }` (IR `expected_version`).
- `PATCH /information-requests/{ir_id}/return` — body `{ return_reason, expected_version }`.
- (Analyst-side ack/respond exist but are the 2B.14 IR Inbox surface; the 2B.13 case detail shows IR status + accept/return for `responded` IRs per spec.)
- IRResponse fields: `information_request_id, case_id, assigned_to, question, due_date?, status, responded_at?, acceptance_note?, accepted_at?, accepted_by?, ...`.

### C8 — Comments / Timeline (generic routers)
- `GET/POST /cases/{case_id}/comments`, `GET /cases/{case_id}/timeline` — segment `cases` resolves to canonical `compliance_case` via `entity_access.ENTITY_TYPE_SEGMENTS` (verified). Same shapes as 2B.12. Admin sees comment metadata + public content only (internal text hidden); compliance sees internal toggle (`comment:view_internal_content`).

### C9 — Approvals (four-eyes, compliance side)
- `POST /approval-requests` (201): body `{ action_type, entity_type, entity_id, proposed_payload?, rationale }`. Permission `approval:request`.
- `GET /approval-requests/{id}` — poll status.
- Action types for cases: `decision_report_to_authority` (compliance; entity state `decision_pending`) — **consumed** by C5. `case_closure_critical_high` (compliance; state `resolved`) and `case_reopen` (admin; state `closed`) exist in `ACTION_STATES` but are **never consumed** — no `/close`/`/reopen` endpoints exist (see §4).
- Poll cadence for approval status: every 10s or on focus (spec §2.3/§2.5).

### Headers
- Mutations send `X-Request-ID`; duplicate-sensitive mutations (assign, transition, decisions, IR create/accept/return, comments) send `X-Idempotency-Key`. No `X-Version` header sent (alerts/investigations impl sends none; backend does not require it — optimistic lock is via body `expected_version`).

### Error-code map (frontend handling)
| Code | HTTP | UI |
|---|---|---|
| `VERSION_CONFLICT` / `INVALID_TRANSITION` / `APPROVAL_EXECUTED` / `IDEMPOTENCY_MISMATCH` | 409 | Conflict banner: case updated elsewhere → auto-refetch + Refresh button |
| `APPROVAL_REQUIRED` | 428 | Approval-required notice ("waiting for compliance approval") |
| `NOT_FOUND` | 404 | Not-found state (back to queue) |
| `FORBIDDEN` | 403 | Permission-required state |
| `INVALID_ENTITY_TYPE` | 400 | (not expected in normal flow) |
| 422 (Pydantic) | 422 | Field validation messages from `detail` |
| 401 | 401 | Handled by `apiClient` interceptor |

## 4. Contract Mismatches (frozen backend — resolved in frontend, NO backend change)

These are the alignment findings for the alignment report.

1. **CloseModal / Close Case (`case:close`) — NOT implementable.** DoD item 6 and spec CloseModal (§2.2) reference `POST /cases/:id/close` with `case:close`; the backend has **no** close route, no `case:close` permission action, and `resolved→closed` is absent from `ALLOWED_TRANSITIONS` (test_cases.py asserts transition-to-`closed` raises `InvalidTransition` and that no `/close`/`/reopen` routes exist). `case_closure_critical_high` approval is thus never consumable. **Resolution:** no Close button/modal is rendered; `resolved` is terminal in 2B.13. Rationale is recorded at decision time (`closure_recommended→resolved`). Flagged for backend increments (Phase 2E) to add close/reopen + consume the approval actions.

2. **Queue risk_level filter — not implementable.** Spec filter list is `status, risk_level, priority`; the C1 endpoint supports only `status` and `priority`. **Resolution:** render status + priority filters (server-filtered); risk-level is displayed as a column/badge only. Overdue row highlight (target_date < today and status NOT IN resolved/closed) is computed client-side.

3. **Unassigned sub-section — not implementable.** Spec §2.1 "Unassigned" sub-section requires listing unassigned cases; no endpoint lists them (C1 returns only assigned). **Resolution:** admin assignment is offered on the Case Detail page when `assigned_to` is null (C3 PATCH `/cases/{id}/assign`), satisfying "in 2B admin assigns". The full unassigned queue is Phase 2E.

4. **IR assignee selector — free text.** Spec IRCreateModal wants a users select filtered by `info_request:respond`; the workbench routers expose **no** users-list endpoint (the admin users endpoint used by 2B.11 AssignModal exists at `GET /admin/users`, but it is admin-only and not scoped to `info_request:respond`). **Resolution:** `assigned_to` is a free-text user-id field. Backend `_validate_assignee` remains authoritative.

5. **Decision Form route.** Spec puts it at `/workbench/cases/:id/decisions`; the backend has no such sub-route and the DoD only requires "DecisionForm: all decision types; report_to_authority approval flow". **Resolution:** render the Decision Form inline in the Decisions tab (and/or a case action that scrolls to it), consistent with the spec's inline four-eyes flow.

6. **IR lifecycle dead-end (verified, flagged, not fixed).** IR create sets the case → `awaiting_information`, but `ALLOWED_TRANSITIONS` has no `awaiting_information` key and no transition leads out of it; IR accept/return only notify (no case-status resume). **Resolution:** while a case is `awaiting_information`, the action bar renders the "resumes from the Information Request workflow (2B.14)" guidance note — no transition button, matching the backend state machine (same convention as 2B.12 `awaiting_information`).

## 5. Implementation Plan (ponytail — minimal, reuse-first)

New files:
1. `src/types/cases.ts` — `CaseStatus`, `CasePriority`, `CaseRiskLevel`, `DecisionType`, `Case`, `CaseListResponse`, `CaseMutationResponse`, `CaseDecisionResponse`, `Decision`, `CaseDecisionListResponse`, IR shapes (or reuse a shared IR type), approval shapes.
2. `src/api/casesApi.ts` — `listAssigned({status?, priority?, page?, per_page?})`, `get(id)`, `assign(id, {assigned_to, expected_version, reason?})`, `transition(id, {target_status, resolution?, expected_version})`, `recordDecision(id, payload)`, `listDecisions(id)`, `listInformationRequests(id, page?)`, `createInformationRequest(id, payload)`, `acceptInformationRequest(irId, payload)`, `returnInformationRequest(irId, payload)`, `listComments/createComment/listTimeline` (reuse/generalise the 2B.12 modules or add thin wrappers). `X-Request-ID` + `X-Idempotency-Key` on mutations.
3. `src/components/cases/caseErrors.ts` — `parseCaseError` (mirror of `parseInvestigationError`, incl. 428 `APPROVAL_REQUIRED`).
4. `src/components/cases/CaseBadges.tsx` — `CaseStatusBadge` (open=gray, assigned=yellow, under_review=blue, awaiting_information=purple, decision_pending=purple/blue, awaiting_compliance_action=yellow, resolved=green, closed=gray, cancelled=gray), `CaseRiskBadge` (critical=dark-red, high=red, medium=amber, low=gray), `CasePriorityBadge`, `DecisionTypeBadge`.
5. `src/components/cases/CaseQueuePage.tsx` — filter bar (status + priority), table (title, status badge, risk badge, priority badge, assigned_to=self, target_date, updated_at), overdue highlight (target_date < today && status NOT IN resolved/closed), pagination 50/page (Next when `items.length === per_page`), loading skeleton, empty, error+retry.
6. `src/components/cases/CaseDetailPage.tsx` — fetch case; header (title, status/risk/priority badges, `v{version}`, assignee), tabs Overview/Investigation/IR/Decisions/Comments/Timeline; action bar per spec §2.2 minus Close (see §4.1); `awaiting_information` guidance strip; admin Assign dialog when unassigned; 409 conflict banner + refetch.
7. Tabs: `CaseOverviewTab`, `CaseInvestigationTab` (read-only findings + Approve/Return when investigation.status=submitted and user holds `investigation:review` → PATCH `/investigations/{id}/transition`), `CaseInformationRequestsTab` (list + expand + Accept/Return when IR `responded`), `CaseDecisionsTab` (list newest-first + inline Decision Form), Comments/Timeline reuse.
8. Dialogs: `dialogs/AdminAssignCaseDialog.tsx`, `dialogs/TransitionCaseDialog.tsx` (Begin Review / Mark Decision Pending / Mark Action Completed / Resolve), `dialogs/IRCreateModal.tsx` (free-text assignee + question + due_date), `dialogs/IRAcceptReturnDialog.tsx`, `dialogs/DecisionForm.tsx` (radio decision types, rationale required, Report-to-Authority inline four-eyes via `approvalsApi.create` + poll every 10s, Submit enabled only when approved).
9. Routes in `src/App.tsx`: `/workbench/cases` and `/workbench/cases/:caseId` under the business layout with `ProtectedRoute requiredPermission="case:read_assigned"`.
10. Sidebar `BankingSidebar.tsx`: "Cases" nav item (`Scale`/`Briefcase`), roles `['compliance','admin','analyst']` via the existing `NAV_ITEMS` mechanism.

Tests (matching existing conventions):
- `src/api/__tests__/casesApi.test.ts` — URL/params/headers/body per method (incl. X-Request-ID + idempotency, decision payload, IR create `expected_case_version`).
- `src/components/cases/__tests__/CaseQueuePage.test.tsx` — render + badges + overdue highlight, filters refetch, empty, error+retry, row navigation.
- `src/components/cases/__tests__/CaseDetailPage.test.tsx` — render fields, tabs, Begin Review transition, Mark Decision Pending, Resolve, decision record (each type target), report_to_authority approval flow (428 banner / 428 in-dialog / poll-enable), IR create + accept + return, investigation approve/return, comments/timeline, 409 conflict banner, admin assign, awaiting_information guidance.

Verification:
- `npm test` (Frontend) — must keep 66 baseline + new green.
- `npm run build` — must pass.
- Backend regression unchanged: `cd services && python3 -m pytest shared/tests workbench/tests -q` → 429 passed / 4 skipped. **No backend files touched** (`git status` shows frontend-only changes).

## 6. Out of Scope (per task brief, confirmed)

IR Inbox analyst surface (2B.14), Approval Queue page (2B.15), notifications/outbox (2B.16), evidence file upload (Phase 2D), case close/reopen (backend has no endpoints — Phase 2E), any backend/contract/RBAC/schema change, WS live push.

## 7. Known Risks / Decisions

- CloseModal is explicitly dropped (backend gap, §4.1) — DoD item 6 is scoped out in the closure report; `resolved` is terminal.
- Queue `risk_level` filter dropped; risk displayed as badge only (§4.2).
- Unassigned queue sub-section dropped; admin assigns from detail (§4.3).
- IR assignee is free-text user-id (§4.4).
- Decision Form is inline (no `/decisions` sub-route) (§4.5).
- `awaiting_information` renders read-only with a 2B.14 guidance note (backend state machine dead-end, §4.6).
- All case mutations return 2xx success; success handling is 2xx-based; IR create is the only 201 case and triggers an IR tab refresh per spec.
