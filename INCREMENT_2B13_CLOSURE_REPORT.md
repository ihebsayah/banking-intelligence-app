# Increment 2B.13 — Frontend: Compliance Case Workbench (Queue + Detail) — Closure Report

Status: CLOSED. All verification green. No backend files modified.

---

## 1. Executive Summary

Implemented the Compliance Case Workbench — `/workbench/cases` (Case Queue) and `/workbench/cases/:caseId` (Case Detail) — with the canonical case state machine (`assigned → under_review → decision_pending → awaiting_compliance_action → resolved`), decision recording with approval gating (report-to-authority requires an approved four-eyes approval), Information Request management (create / accept / return with optimistic-lock versioning), investigation review integration, comments + timeline tabs, admin assignment, and the 2B.14-aware `awaiting_information` guidance strip. Consumed the implemented backend exactly as built (verified from routers/services, not prose); zero backend changes. Backend regression reconfirmed at **429 passed, 4 skipped**. Frontend suite grown to **99 passed (12 files)**, production build green.

## 2. Task Definition & Scope

Frontend-only increment per `increment-2B-implementation-sequence.md` (frozen, authoritative) — 2B.13 is the current task; 2B.14 (IR Inbox) stays blocked (no assigned-IR inbox endpoint):
- Canonical routes `/workbench/cases` and `/workbench/cases/:caseId`.
- Queue (assigned cases, status/priority filters, pagination 50/page) + detail workspace with Overview / Investigation / Information Requests / Decisions / Comments / Timeline tabs.
- Transitions per the frozen `ALLOWED_TRANSITIONS` contract: `assigned→under_review`, `under_review→decision_pending`, `awaiting_compliance_action→resolved` (resolution required for `resolved`).
- Decisions: six decision types; `no_action` and `closure_recommended` → `resolved`; all others (incl. `report_to_authority_recommended`) → `awaiting_compliance_action` per `DECISION_TYPE_TARGET`.
- `report_to_authority_recommended` requires an approved `decision_report_to_authority` approval request (`approval_request_id` in the decision payload); without it the backend returns 428 `APPROVAL_REQUIRED`; a consumed approval → 409 `APPROVAL_EXECUTED`.
- IR create requires `expected_case_version` (case version); accept/return use the IR's own `expected_version`.
- Comments + timeline (generalised from the 2B.12 tabs) and admin assign.
- Out of scope (confirmed): case close/reopen (no `/cases/{id}/close` route, no `case:close` consumption, no `resolved→closed` transition — `resolved` renders terminal; Phase 2E adds close/reopen), queue `risk_level` filter (backend `GET /cases/assigned` accepts only `status`/`priority`/`page`/`per_page`), unassigned-case list endpoint, users directory endpoint (IR assignee is free-text user-id), decision sub-route (decision form is inline), `awaiting_information` continuation (no `awaiting_information→` transition — rendered as a read-only guidance strip, deferred to 2B.14), any backend/contract/RBAC change.

These six contract mismatches vs. the increment prose are documented in `INCREMENT_2B13_PRE_IMPLEMENTATION_REPORT.md` (approved in-flow; implementation matches it).

## 3. Route Integration

Added under the business layout in `frontend/src/App.tsx`:
- `/workbench/cases` → `<CaseQueuePage />`
- `/workbench/cases/:caseId` → `<CaseDetailPage />`

Both wrapped in `ProtectedRoute requiredRole={['analyst','compliance','admin']} requiredPermission="case:read_assigned"` (server remains the enforcer).

## 4. Permission Gating

- Routes gated with `case:read_assigned` via `ProtectedRoute`.
- Per-button gating in the detail action bar uses `useAuth().hasPermission` + `hasRole` (frontend gates prevent unnecessary round-trips; the backend authorise layer is authoritative):
  - Begin Review / Mark Decision Pending / Resolve Case → `case:transition` (ownership action — assignee only) + status-appropriate
  - Record Decision → `case:decision` (ownership action) + status `decision_pending`
  - Request Information → `info_request:create` + status `under_review`
  - Accept / Return IR → `info_request:accept` / `info_request:return` + IR status `responded`
  - Assign Case (when unassigned) → `case:assign` + admin role
  - Investigation approve/return (in Investigation tab) → `investigation:review`
  - Internal comments → `comment:view_internal_content`
- `awaiting_information` renders read-only with a "resumes from the Information Request workflow (2B.14)" guidance note — no transition button, matching the backend state machine (no `awaiting_information` key in `ALLOWED_TRANSITIONS`).
- Sidebar: added "Cases" (`Scale`) nav item after Investigations, role-filtered via the existing `NAV_ITEMS` mechanism.

## 5. Typed API Client — `frontend/src/api/casesApi.ts`

Object-literal module mirroring the established `alertsApi`/`investigationsApi` pattern:
- `listAssigned({ status?, priority?, page?, perPage? })` → `GET /cases/assigned` (no `risk_level` param — matches the as-built router)
- `get(id)` → `GET /cases/{case_id}`
- `assign(id, { assigned_to, expected_version })` → `PATCH /cases/{case_id}/assign`
- `transition(id, { target_status, resolution?, expected_version })` → `PATCH /cases/{case_id}/transition`
- `recordDecision(id, { decision_type, rationale, approval_request_id?, expected_version })` → `POST /cases/{case_id}/decisions`
- `listDecisions(id)` → `GET /cases/{case_id}/decisions`
- `listInformationRequests(id, page?, perPage?)` → `GET /cases/{case_id}/information-requests`
- `createInformationRequest(id, { assigned_to, question, expected_case_version })` → `POST /cases/{case_id}/information-requests`
- `acceptInformationRequest(irId, { expected_version })` / `returnInformationRequest(...)` → `PATCH /information-requests/{ir_id}/accept|return`
- `listComments(id, page?, perPage?)` / `createComment(id, content, isInternal)` → `GET|POST /cases/{case_id}/comments`
- `listTimeline(id, page?, perPage?)` → `GET /cases/{case_id}/timeline`

All mutations send `X-Request-ID`; duplicate-sensitive mutations (transition, recordDecision, assign, createInformationRequest, createComment) send `X-Idempotency-Key` (crypto.randomUUID with a fallback). No `X-Version` header (matches the existing impls; version is carried in the body).

## 6. Type Definitions — `frontend/src/types/cases.ts`

Wire shapes mirror `services/workbench/schemas/cases.py`, `decisions.py`, `information_requests.py`, `comments.py`, `timeline.py` exactly: `CaseStatus` (9 states), `CasePriority`, `RiskLevel`, `DecisionType` (6 values), `Case` (incl. `risk_level`, `regulatory_frameworks`, `resolution`/`resolved_at`/`resolved_by`, `closed_at`/`closed_by`, version + timestamps), `CaseDecision`/`CaseDecisionType`, `InformationRequest` with **`ir_id`** (the DTO field — not `information_request_id`) and optional `question`/`assigned_to` (the admin IR view omits them), list/mutation responses (mutations return `{ success, case, version }`), `Comment`/`CommentListResponse` (incl. `is_redacted`), `TimelineEntry`/`TimelineListResponse`.

## 7. Case Queue Page — `frontend/src/components/cases/CaseQueuePage.tsx`

Table of assigned cases: title + `overdue` tag + `assigned to you`/`assigned {user}` + `v{version}`, risk badge (column), priority badge, status badge, target date, updated timestamp. Row click (and Enter/Space keyboard) navigates to the detail route. Overdue highlight is **client-side** (`target_date < today && status NOT IN (resolved, closed)`) because the backend list response carries no overdue flag.

## 8. Queue Filters

Status + priority selects (`aria-label`-ed), each resetting to page 1, passed to `listAssigned` as `status`/`priority`. No risk filter — the as-built endpoint does not accept one (documented in the alignment report).

## 9. Queue Pagination

Per-page 50 with prev/next. Following the A1/2B.12 convention (and the frozen backend shape), "Next" enables when the page is full (`items.length === per_page`); `total` is informational.

## 10. Queue States

- Loading: skeleton rows.
- Empty: "No cases assigned to you" with a context-aware hint when filters are active.
- Error: structured error panel with Retry (reuses the workbench error parser `parseCaseError`).

## 11. Case Detail Page — `frontend/src/components/cases/CaseDetailPage.tsx`

Header (title, `Case · created`), status + priority + risk badges, `v{version}` chip, assignee chip, workflow-guidance strip (per-status next-action, incl. the 2B.14 `awaiting_information` note), description panel, linked-alert + linked-investigation panels (navigate to their detail routes), meta grid (status, priority, risk, assigned to, created by, scope, target date, regulatory frameworks, version, created/updated), tab bar, action bar, and dialogs. Loading and not-found states render dedicated skeletons/panels with a back-to-queue action.

## 12. Case Transitions (Action Bar)

- **Begin Review** (`assigned` → `under_review`): confirmation dialog, optimistic-lock safe.
- **Request Information** (`under_review`): opens the IR create modal (see §16); the case stays `under_review` until the IR flow progresses.
- **Mark Decision Pending** (`under_review` → `decision_pending`): confirmation dialog.
- **Resolve Case** (`awaiting_compliance_action` → `resolved`): dialog with a **required resolution** (`resolutionRequired` — the backend requires it for `resolved`); submit disabled until non-empty.
- **Record Decision** (status `decision_pending`): switches to the Decisions tab and focuses the inline decision form (no `/decisions` sub-route exists — documented).
- **Assign Case** (unassigned + admin): `AdminAssignCaseDialog` (free-text assignee, `case:assign`).

## 13. Decision Form — `frontend/src/components/cases/dialogs/DecisionForm.tsx`

Inline in the Decisions tab when `canDecide && status === 'decision_pending'` (ownership + `case:decision`). Six decision types (radio): `no_action`, `closure_recommended` (→ `resolved`), `report_to_authority_recommended`, `escalate_to_senior_compliance`, `provide_training`, `improve_monitoring` (→ `awaiting_compliance_action`). Rationale textarea required. For `report_to_authority_recommended` a "Four-eyes approval required" panel appears: **Request Approval** → `approvalsApi.create({ action_type: 'decision_report_to_authority', entity_type: 'compliance_case', entity_id, rationale })` → 10s poll + a **Refresh status** button → `approvalsApi.get`; the decision submit stays disabled until the approval is `approved`, then posts with `approval_request_id`. Without approval the backend would 428 `APPROVAL_REQUIRED`; a consumed approval → 409 `APPROVAL_EXECUTED`. On success the case refetches (the target status changes per `DECISION_TYPE_TARGET`).

## 14. Information Requests Tab — `frontend/src/components/cases/CaseInformationRequestsTab.tsx`

Expandable rows (question / assigned-to / status / timestamps). When an IR is `responded`, Accept / Return actions appear (per-permission gated) via `IRAcceptReturnDialog`, posting `PATCH /information-requests/{ir_id}/accept|return` with the IR's `expected_version`; the case refetches afterwards. Paginated 50/page with prev/next. Empty/loading/error states included.

## 15. Investigation Tab — `frontend/src/components/cases/CaseInvestigationTab.tsx`

Embeds the linked investigation (`investigationsApi.get`) with its findings/refs/conclusion. Compliance reviewers (`investigation:review`, status `submitted`) get **Approve Investigation** / **Return Investigation** reusing the 2B.12 `ConfirmTransitionDialog`/`ReturnInvestigationDialog`, posting `investigation:transition`. Reuses `CommentsTab`/`TimelineTab` generalized with `entityId`.

## 16. IR Create Modal — `frontend/src/components/cases/dialogs/IRCreateModal.tsx`

Opened from "Request Information" (needs `info_request:create` + `under_review`). Fields: free-text assigned analyst user-id (no users endpoint exists — documented) and question. Posts `createInformationRequest(id, { assigned_to, question, expected_case_version })`; the case refetches afterwards. Validation + disable-while-submitting; 409 surfaces as a conflict banner.

## 17. Comments & Timeline Tabs (Generalised)

`CommentsTab` and `TimelineTab` (previously investigation-specific, 2B.12) were generalised to take `entityId` + optional `api` props (validated `CommentsApiLike` / `TimelineApiLike` shapes) and reused for cases; `InvestigationDetailPage` callsites updated to `entityId=…`. `humanise()` now also strips the `case.` event prefix (timeline prefixes are `investigation.*` and `case.*`). Comments: post form with internal-comment checkbox gated on `comment:view_internal_content`; Redacted chip and `content ?? 'Internal comment — content restricted in this view.'` for the metadata view. Timeline: `case.status_changed` rendered as "status changed" with delta "status assigned → under_review".

## 18. Error Handling

Central `parseCaseError` (`frontend/src/components/cases/caseErrors.ts`) maps status + `error` code to kinds: `conflict` (409 incl. `APPROVAL_EXECUTED`), `approval_required` (428 `APPROVAL_REQUIRED`), forbidden, not_found, validation, service_unavailable, unknown — each with an actionable message (e.g. `DB_UNAVAILABLE`/503 → "Service temporarily unavailable"). 401 is handled by the existing `apiClient` interceptor. 403/404 render a not-found panel with a back-to-queue action. 422 surfaces the validation message in the relevant dialog/form. 409s close the dialog and surface the amber "Case was updated by someone else" banner with a Refresh button that refetches server state.

## 19. Idempotency & Trace Headers

`X-Request-ID` on every mutation; `X-Idempotency-Key` on transition, recordDecision, assign, createInformationRequest, createComment (dedupe-safe against double-submit / network retry, matching the backend idempotency store).

## 20. Accessibility & Responsive

- Tabs use `role="tablist"/"tab"`/`aria-selected`/`aria-controls` and labelled tab panels; keyboard focusable via native buttons.
- Modal shell reused: `role="dialog"`, `aria-modal`, `aria-labelledby`, Esc-to-close, overlay-click close, scroll-lock.
- Form fields have explicit `<label>`s; queue selects, pagination buttons, and icon buttons have `aria-label`s; error/success regions use `role="alert"` / `role="status"`.
- Responsive: queue table scrolls horizontally on small screens; filter bar and action bar wrap; meta grid collapses; badges/actions wrap.

## 21. Frontend Tests + Production Build

- Baseline after 2B.12: **66 passed (9 files)**; production build **passed**.
- After 2B.13: **99 passed (12 files)**, +33 new tests:
  - `casesApi.test.ts` — 14 tests (query params + defaults, get, assign, transition with/without resolution, recordDecision incl. approval_request_id, decisions list, IR list/create with `expected_case_version`/`ir_id`, accept/return with `expected_version`, comments list/create, timeline list, header presence).
  - `CaseQueuePage.test.tsx` — 6 tests (render + risk/priority/status badges + assigned-to + version, overdue highlight with resolved excluded, empty state, filter→refetch, error + retry, row navigation).
  - `CaseDetailPage.test.tsx` — 13 tests (render fields/badges/version/assignee/frameworks, not-found + back-to-queue, Begin Review payload, Mark Decision Pending, Resolve with required resolution, no_action decision record payload, report_to_authority four-eyes flow (request → poll → submit enabled), IR create payload + refetch, investigation approve, awaiting_information guidance with no transitions, 409 conflict banner + refetch, comments + timeline tabs, admin assign of unassigned case).
- Production build: **passes** (tsc + vite build). The only build output warnings are the pre-existing chunk-size advisory and keycloak dynamic-import notice.

## 22. Backend Regression

Backend untouched (`git status` shows frontend-only files). Core regression reconfirmed at the same command as the 2B.12 baseline:
- `cd services && python3 -m pytest shared/tests workbench/tests -q` → **429 passed, 4 skipped** (identical to baseline).
- Case/decision/information-request/approval/comment/timeline backend suites all green; no contract drift.

## 23. Out of Scope & Next Steps

- Out of scope (documented in the approved alignment report): case close/reopen (Phase 2E), queue `risk_level` filter, unassigned-case list endpoint, users directory, `/cases/{id}/decisions` sub-route (inline form), `awaiting_information` continuation (2B.14 IR Inbox), evidence file upload (Phase 2D), notifications surface, WS live push, approval queue, any backend/contract/RBAC change.
- Next canonical task: the Information Request (IR) Inbox increment (2B.14) — unlocks the `awaiting_information` lifecycle UI; then the approval queue and Phase 2D/2E follow-ons.
