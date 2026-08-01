# Increment 2B.11 — Frontend: Alert Queue + Detail — Closure Report

Status: CLOSED. All verification green. No backend files modified.

---

## 1. Executive Summary

Implemented the workbench Alert surfaces — `/workbench/alerts` (Alert Queue) and `/workbench/alerts/:alertId` (Alert Detail) — with the full action bar (Acknowledge, Create Investigation, Dismiss with four-eyes approval, Escalate, Assign), typed API clients, optimistic-lock conflict UX, approval-required UX, and accessibility. Consumed the implemented backend exactly as built; zero backend changes. Also fixed a pre-existing frontend build break (`src/api/auth.ts` missing `permissions`).

## 2. Task Definition & Scope

Frontend-only. Routes, permissions, typed client, queue, detail, actions, dialogs, 409/428 UX, error states, a11y, responsive layout, tests, production build, and a no-regression backend run. Out of scope (per brief, confirmed): investigation/case detail surfaces, approval queue, comments/timeline, WS live push, any backend/contract/RBAC change.

## 3. Route Integration

Added under the business layout in `frontend/src/App.tsx`:
- `/workbench/alerts` → `<AlertQueuePage />`
- `/workbench/alerts/:alertId` → `<AlertDetailPage />`

Both wrapped in `ProtectedRoute requiredRole={['analyst','compliance','admin']} requiredPermission="alert:read_assigned"` (server remains the enforcer).

## 4. Permission Gating

- Routes gated with `alert:read_assigned` via `ProtectedRoute` (Keycloak and legacy branches both handled).
- Per-button gating in the detail action bar uses `useAuth().hasPermission` + `hasRole`:
  - Acknowledge → `alert:acknowledge` + status `assigned` + assignee
  - Create Investigation → `alert:investigate` + status `acknowledged` + assignee
  - Dismiss → `alert:dismiss` + status IN (acknowledged, under_investigation) + assignee
  - Escalate → `alert:transition` + status `under_investigation` + assignee
  - Assign → `alert:assign` + role admin + status NOT IN (resolved, dismissed)
- Sidebar: added "Alert Queue" (`BellRing`) nav item, role-filtered to analyst/compliance/admin via the existing `NAV_ITEMS` mechanism (no shell redesign).

## 5. Typed API Client — `frontend/src/api/alertsApi.ts`

Object-literal module mirroring the established `complianceApi` pattern:
- `listAssigned({ status?, severity?, page?, perPage? })` → `GET /alerts/assigned`
- `get(id)` → `GET /alerts/{id}`
- `acknowledge(id, expectedVersion)` → `PATCH /alerts/{id}/acknowledge`
- `dismiss(id, { dismissed_reason, expected_version, approval_request_id? })` → `PATCH /alerts/{id}/dismiss`
- `investigate(id, { title, description?, expected_version })` → `POST /alerts/{id}/investigate`
- `escalate(id, { title, description?, priority, expected_version })` → `POST /alerts/{id}/escalate`
- `assign(id, { assigned_to, expected_version, reason? })` → `PATCH /alerts/{id}/assign`

All mutations send `X-Request-ID`; the duplicate-sensitive POSTs (investigate/escalate) and assign send `X-Idempotency-Key` (crypto.randomUUID). Types in `frontend/src/types/alerts.ts` (Alert, AlertAdminView, list/mutation/escalate/investigate responses, approval request shapes).

## 6. Approval API Client — `frontend/src/api/approvalsApi.ts`

Minimal client for the four-eyes Dismiss flow: `create({ action_type, entity_type, entity_id, proposed_payload?, rationale })` → `POST /approval-requests` and `get(id)` → `GET /approval-requests/{id}` (polling). Sends `X-Request-ID` + `X-Idempotency-Key`.

## 7. Alert Queue Page — `frontend/src/components/alerts/AlertQueuePage.tsx`

Table of assigned alerts ordered by the backend (`created_at DESC`): severity badge, title + `alert_type · #id`, assigned-to (mono), status badge, created timestamp. Critical rows get a subtle red tint. Row click navigates to the detail route.

## 8. Queue Filters

Severity + status selects (`aria-label`-ed), each resetting to page 1. Passed to `listAssigned` as `severity`/`status`.

## 9. Queue Pagination

Per-page 50 with prev/next. **Documented backend quirk:** A1's `total` is the *current-page* count (`len(items)`), not a true total, and the severity filter is applied in memory after SQL. The UI therefore enables "Next" when the page is full (`items.length === per_page`) and treats `total` as informational — no backend change (frozen contract).

## 10. Queue States

- Loading: skeleton rows.
- Empty: "No alerts assigned to you" with a context-aware hint when filters are active.
- Error: structured error panel with Retry (reuses the workbench error parser).

## 11. Alert Detail Page — `frontend/src/components/alerts/AlertDetailPage.tsx`

Header (title, `alert_type · created`), severity + status badges, `v{version}` chip, assignee chip, description panel, related-entity panel ("linkable in 2C" per spec), meta grid (alert type, scope, source rule, created, updated, dismissed-by/at when dismissed), action bar.

## 12. Detail Header & Meta

Uses `BankingHeader` with a Queue back-action. Meta grid renders only fields the current view actually provides (see §13).

## 13. Admin Metadata-Only View Handling

The backend returns `AlertAdminResponse` (no `description`/`related`/`updated_at`/`title`) for admins outside direct scope. The page detects this at runtime (`'description' in alert`), renders a "Metadata-only view — this alert is outside your direct scope" note, omits the missing panels, and falls back to `alert_type · #id` for the header title. No crash on the reduced shape.

## 14. Action Bar & Per-Action Gating

Conditional rendering per §4. Each action maps to the correct backend endpoint; the bar renders nothing when no action applies (e.g. resolved/dismissed terminal states).

## 15. Acknowledge Action

Inline button → `acknowledge(id, version)` → refetch. No-op-safe per backend idempotency. 409 → conflict banner + auto-refetch.

## 16. Create Investigation Dialog

Fields: title (required), description (optional). Submit → `POST investigate`; on success navigates to `/workbench/investigations/{id}` (route lands with 2B.12). 409 → close + conflict banner. Actual backend returns HTTP 200 (not 201 as prose docs state) — success is 2xx-based.

## 17. Dismiss Dialog + Four-Eyes Approval Flow

Fields: dismissal reason (required). For critical/high severity: "Four-eyes approval required" notice; when the actor holds `approval:request`, a "Request Approval" button creates the ApprovalRequest (`alert_dismissal_critical_high`) and polls `GET /approval-requests/{id}` until a terminal status, showing `{approval_count}/{required_approvals}` and a status badge. Submit is enabled only when `status === 'approved' && !executed_at`. Without the permission, the dialog shows "Contact a compliance officer to approve this dismissal." On success refetch; 409 → conflict banner.

## 18. Escalate Dialog

Fields: title (required), description (optional), priority select (default medium). Submit → `POST escalate`; on success navigates to `/workbench/cases/{id}` (route lands with 2B.12). 409 → conflict banner.

## 19. Assign Dialog

Admin-only (`alert:assign` + admin role). Loads active analyst + compliance users via the existing `adminApi.getUsers` (role/status filters), deduped and merged. Shows current assignee + expected version. Reason required when reassigning or reopening (matches backend `InvalidAssignee` semantics for reassignment/reopen). Submit → `PATCH assign`; 409 → conflict banner.

## 20. Optimistic-Lock Conflict UX (409)

Any 409 (`VERSION_CONFLICT` / `INVALID_TRANSITION` / `APPROVAL_EXECUTED` / `IDEMPOTENCY_MISMATCH`) surfaces the amber banner "Alert was updated — refresh and try again." with a Refresh button. The dialog closes, an auto-refetch pulls fresh data, and the banner persists until the user explicitly clicks Refresh (clearing `conflict`). Matches the 2B.11 DoD (409 auto-refetch + banner).

## 21. Approval-Required UX (428)

Handled structurally: the Dismiss dialog enforces the four-eyes precondition client-side (approval `approved` + not `executed_at`) so a bare 428 is not normally reachable; the workflow-doc message "Approval not yet granted — waiting for compliance officer" is represented by the pending-state notice and the contact-compliance guidance. Any unexpected `APPROVAL_REQUIRED` is still parsed to the approval_required kind by `parseAlertError`.

## 22. Idempotency & Trace Headers

`X-Request-ID` on every mutation; `X-Idempotency-Key` on investigate/escalate/assign and approval-request creation (dedupe-safe against double-submit / network retry, matching the backend idempotency store).

## 23. Error Handling (401/403/404/409/422/428)

Central `parseAlertError` (`frontend/src/components/alerts/alertErrors.ts`) maps status + `error` code to kinds: conflict, approval_required, forbidden, not_found, validation, unknown — each with an actionable message. 401 handled by the existing `apiClient` interceptor (Keycloak refresh → redirect; legacy redirect). 403/404 render a not-found panel with a back-to-queue action. 422 surfaces the validation message.

## 24. Accessibility & Responsive

- Modal shell (`frontend/src/components/ui/Modal.tsx`): `role="dialog"`, `aria-modal`, `aria-labelledby`, Esc-to-close, overlay-click close, scroll-lock while open.
- Form fields have explicit `<label>`s; queue selects have `aria-label`s; pagination buttons have `aria-label`s; close buttons are labelled.
- Responsive: queue table scrolls horizontally on small screens; filter bar wraps; detail grid collapses 3→2→1 columns; badges/actions wrap.

## 25. Frontend Tests + Production Build

- Baseline: **15 passed (3 files)**; build **FAILED** (`src/api/auth.ts` TS2741 — legacy login omitted required `User.permissions`).
- After 2B.11: **34 passed (6 files)**, +19 new tests:
  - `alertsApi.test.ts` — 10 tests (query params, defaults, bodies, X-Request-ID / X-Idempotency-Key presence, approval create/get).
  - `AlertQueuePage.test.tsx` — 4 tests (render + badges, empty state, filter→refetch, row navigation).
  - `AlertDetailPage.test.tsx` — 5 tests (render fields, acknowledge + refetch, 409 conflict banner, dismiss four-eyes flow with `approval_request_id`, escalate navigation).
- Production build: **passes** (tsc + vite build). The only build output warnings are pre-existing (dynamic/static `keycloak.ts` import mix, chunk-size advisory) — not introduced here.

## 26. Backend Regression, Out of Scope, Next Steps

- Backend untouched (`git status` shows frontend-only + reports). Core regression reconfirmed: **429 passed, 4 skipped** (`cd services && python3 -m pytest shared/tests workbench/tests -q`); extended run (with `INTEGRATION_DATABASE_URL`) yields 433/0.
- Out of scope: investigation/case detail pages, approval queue, comments/timeline, notifications, WS live push, backend/contract/RBAC changes.
- Next canonical task: **2B.12 — Frontend: Investigation Queue + Detail** (routes `/workbench/investigations`, `/workbench/investigations/:id`). The 2B.11 flows already navigate to the investigation/case routes that phase will implement.
- Documented, decision-bound quirks (frozen backend, no changes): A1 `total`/pagination semantics (§9); alert mutations return HTTP 200 not 201 (§16/§18); admin metadata-only detail shape (§13); four-eyes approval requires `approval:request` to self-serve (§17/§21).
