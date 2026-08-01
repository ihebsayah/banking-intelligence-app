# Increment 2B.11 — Frontend: Alert Queue + Detail — Pre-Implementation Report

Status: Approved to proceed. Backend contract frozen (2B.10b closure). No backend changes in this phase.

## 1. Task Definition

Frontend-only implementation of the workbench Alert surfaces:

- `/workbench/alerts` — AlertQueue (`PermissionGate` `alert:read_assigned`)
- `/workbench/alerts/:alertId` — AlertDetail (`PermissionGate` `alert:read_assigned`)

Completion report is the 26-point structure prescribed by the task brief.

## 2. Stack & Conventions (verified against the running code)

- React 18.3.1 + react-router-dom 6.24 + axios 1.7.2 + lucide-react + clsx + date-fns.
- @tanstack/react-query and zustand are installed but NO existing page uses react-query; pages use `useState`/`useEffect` + object-literal API modules (`src/api/complianceApi.ts` is the canonical pattern). **Decision: follow the existing page pattern (state + API module). Do not introduce react-query usage.**
- Design tokens: CSS custom properties (`--bg-*`, `--text-*`, `--accent-*`) via inline `style` + Tailwind utility classes. Cards `rounded-xl border p-5` with `var(--bg-card)`/`var(--bg-border)`. Reuse `StatusBadge`/`RoleBadge`, `PageHeader`, `ErrorState`, `EmptyState`, `LoadingState`, `ServiceUnavailable`, `BankingHeader`.
- No shared Modal component exists today (CommandPalette has an inline overlay). One minimal `src/components/ui/Modal.tsx` will be added for the three action dialogs.
- Auth: `useAuth().hasPermission(perm)` + `hasRole(role)` + `applicationUser` (Keycloak) / `useAuthStore` (legacy). `PermissionGate` wraps feature fragments. `ProtectedRoute requiredPermission="alert:read_assigned"` wraps routes. Server is the enforcer; gates prevent round-trips only.
- Tests: vitest + @testing-library/react + jsdom; setup imports `@testing-library/jest-dom`. Existing API tests mock `src/api/client` via `vi.mock('../../api/client', ...)`.

## 3. Backend Surface Consumed (as-built, authoritative — read from routers/services, NOT prose contracts)

All under `services/workbench/`. Prefix `/api/v1`. Error envelope everywhere: `{ "error": CODE, "message": str }` with HTTP status (FastAPI `WorkbenchError.to_dict()`).

### A1 — GET `/alerts/assigned`
- Permission `alert:read_assigned`. Params: `status`, `severity`, `page` (default 1), `per_page` (default **50**, max 100).
- Response `{ total, page, page_size, items: Alert[] }` ordered `created_at DESC`.
- **QUIRK (documented, do not fix backend):** `total` is the count of the *filtered current page* (`len(items)`), not the true total; severity filter is applied in-memory after SQL. Pagination UI must therefore treat "Next" as available when `items.length === per_page` and treat `total` as informational only.

### A2 — GET `/alerts/{alert_id}`
- Own alert (assignee, scope, `alert:read_assigned`) → full `Alert` (includes `description`, `related_entity_type/id`, `source_rule_type/id`, `dismissed_*`, `resolved_*`).
- Admin with `alert:read` outside direct scope → `AlertAdminResponse` (metadata only: `alert_id, alert_type, severity, status, assigned_to, scope_id, created_at, version`; **no description/related/timestamps**).
- Neither → 404. Detail page must render without touching `description` when absent.

Alert response fields: `alert_id, alert_type, severity, title, description?, source_rule_type?, source_rule_id?, related_entity_type?, related_entity_id?, scope_id, status, assigned_to?, dismissed_reason?, dismissed_at?, dismissed_by?, resolved_at?, resolved_by?, created_at, updated_at, version`.

Statuses: `new, assigned, acknowledged, under_investigation, resolved, dismissed`. Severities: `critical, high, medium, low`.

### A4 — PATCH `/alerts/{alert_id}/acknowledge`
- Body `{ "expected_version": int }`. 200 → `MutationResponse { success, alert, version }` (header `X-Version`).
- No-op if already acknowledged (200). 409 `VERSION_CONFLICT` / `INVALID_TRANSITION`.

### A5 — PATCH `/alerts/{alert_id}/dismiss`
- Body `{ "dismissed_reason": str (required), "expected_version": int, "approval_request_id"? }`.
- 428 `APPROVAL_REQUIRED` if `severity IN (critical, high)` and approval missing/not approved. 409 `APPROVAL_EXECUTED` if already consumed.
- 200 → `MutationResponse`.

### A6 — POST `/alerts/{alert_id}/investigate`
- Body `{ "title": str, "description"?, "expected_version": int }`. Precondition: status `acknowledged`. Existing investigation → returns existing (200).
- **QUIRK:** actual router returns HTTP **200** (JSONResponse without status_code), not 201 as the workflow doc states. Response `InvestigateResponse { success, alert, investigation_id, version }`. Frontend must treat 2xx as success and navigate to `/workbench/investigations/{investigation_id}` (route lands in 2B.12; the DoD says navigate — navigate there; it is the canonical location).
- 409 `VERSION_CONFLICT` / `INVALID_TRANSITION`.

### A7 — POST `/alerts/{alert_id}/escalate`
- Body `{ "title": str, "description"?, "priority": critical|high|medium|low (default medium), "expected_version": int }`. Precondition: status `under_investigation` AND a linked investigation exists (else 404 `INVALID_TRANSITION` on missing investigation).
- Existing case for alert → returns existing (200). Actual HTTP **200**, not 201. Response `EscalateResponse { success, alert, case_id, version }`.

### AP1/AP3 — Approval requests (four-eyes Dismiss flow)
- `POST /approval-requests` (201): body `{ action_type: "alert_dismissal_critical_high", entity_type: "alert", entity_id, proposed_payload?, rationale }`. Permission `approval:request`. Response `{ success, approval_request { approval_request_id, status, approval_count, required_approvals, ... }, version }`.
- `GET /approval-requests/{id}`: detail incl. `status`, `executed_at`. Used to poll for `approved` before enabling Dismiss Submit.

### Headers
- Mutations accept `X-Request-ID` and `X-Idempotency-Key`. Send `X-Request-ID` (crypto.randomUUID) on all mutations. Send `X-Idempotency-Key` on the duplicate-sensitive POSTs (investigate/escalate) and on approval-request creation. Idempotency mismatch → 409 `IDEMPOTENCY_MISMATCH`.

### Error-code map (frontend handling)
| Code | HTTP | UI |
|---|---|---|
| `VERSION_CONFLICT` / `INVALID_TRANSITION` / `APPROVAL_EXECUTED` / `IDEMPOTENCY_MISMATCH` | 409 | Conflict banner: "Alert was updated — refresh and try again" + Refresh button; refetch alert |
| `APPROVAL_REQUIRED` | 428 | Approval-required banner: "Approval not yet granted — waiting for compliance officer" |
| `NOT_FOUND` | 404 | Not-found state (queue back link) |
| `FORBIDDEN` | 403 | Permission-required state |
| 422 (Pydantic) | 422 | Field validation messages from `detail` |
| 401 | 401 | Handled by `apiClient` interceptor (Keycloak refresh / legacy redirect) |

## 4. Implementation Plan (ponytail — minimal, reuse-first)

New files:
1. `src/types/alerts.ts` — `AlertSeverity`, `AlertStatus`, `Alert`, `AlertListResponse`, `MutationResponse`, `InvestigateResponse`, `EscalateResponse`, `ApprovalRequestStatus`, `ApprovalRequest`, `ApprovalRequestMutationResponse`, `DismissPayload`… (one file, matching `types/api.ts` style).
2. `src/api/alertsApi.ts` — `listAssigned({status?, severity?, page?, per_page?})`, `get(id)`, `acknowledge(id, expectedVersion)`, `dismiss(id, payload)`, `investigate(id, payload)`, `escalate(id, payload)`; internal `uuid()` helper; sets `X-Request-ID` (+ `X-Idempotency-Key` on POSTs).
3. `src/api/approvalsApi.ts` — `create({action_type, entity_type, entity_id, proposed_payload?, rationale})`, `get(id)`.
4. `src/components/ui/Modal.tsx` — minimal overlay/dialog shell (aria-labelledby, Esc/overlay close, focus on open, `role="dialog"`).
5. `src/components/alerts/AlertSeverityBadge.tsx` + `AlertStatusBadge.tsx` — thin wrappers over `StatusBadge` (critical=red, high=red, medium=yellow, low=blue; status map: new=gray, assigned=yellow, acknowledged=purple, under_investigation=blue, resolved=green, dismissed=gray).
6. `src/components/alerts/AlertQueuePage.tsx` — filter bar (severity + status selects, resets page), table (severity badge, title, assigned_to=user, status, created_at via `formatDateTime`), row click → detail, pagination (prev/next per the A1 total quirk), loading skeleton, empty ("No alerts assigned to you"), error + retry.
7. `src/components/alerts/AlertDetailPage.tsx` — fetch alert; header (severity + status badges, title, alert_type, created_at), description panel (guard absent description), related entity (type + id, not linkable in 2B), version display, action bar gated per button:
   - Acknowledge: `alert:acknowledge` + status `assigned` + assignee → inline confirm → PATCH → refetch.
   - Create Investigation: `alert:investigate` + status `acknowledged` → InvestigateDialog → on 2xx navigate `/workbench/investigations/{id}`; on 409 conflict banner + refetch.
   - Dismiss: `alert:dismiss` + status IN (acknowledged, under_investigation) + assignee → DismissDialog (four-eyes for critical/high via approvalsApi create+poll; 428 → approval banner; 409 → conflict banner).
   - Escalate: `alert:transition` + status `under_investigation` → EscalateDialog → on 2xx success + navigate `/workbench/cases/{id}`.
   - Assign: `alert:assign` + role admin + status not in (resolved, dismissed) → AssignModal. User selector source resolved: `adminApi.getUsers(1, 100, role?, 'active')` exists on the frontend already (backend `GET /admin/users?role=&status=active` returns `{ total, page, page_size, items: AdminUserRow { user_id, email, name, role, status, ... } }`, admin-only). Load `role=analyst` and `role=compliance`, `status=active`; backend `_validate_assignee` additionally enforces scope + role capability. Reason field required when reassigning/reopening. expected_version shown.
8. `src/components/alerts/dialogs/InvestigateAlertDialog.tsx`, `DismissAlertDialog.tsx`, `EscalateAlertDialog.tsx`, `AssignAlertDialog.tsx` — form + submit + error handling + `Modal` shell. Assign uses `adminApi.getUsers` (analyst + compliance, active).
9. Routes in `src/App.tsx`: add `/workbench/alerts` and `/workbench/alerts/:id` under the business layout with `ProtectedRoute requiredPermission="alert:read_assigned"`.
10. Sidebar `src/components/Layout/BankingSidebar.tsx`: add nav item `{ to: '/workbench/alerts', icon: Bell/ShieldAlert, label: 'Alerts', roles: ['analyst','compliance','admin'] }` — keeps the existing role-filtered mechanism (no shell redesign). Manager excluded per capability matrix (read_assigned is analyst/compliance; admin reads all).
11. Fix baseline build break: `src/api/auth.ts` login path omits `permissions` (required by `User`). Add `permissions: []` in the returned user.

Tests (new, matching existing conventions):
- `src/api/__tests__/alertsApi.test.ts` — mocks `apiClient`; asserts URL/params/headers/body for each method (incl. X-Request-ID + idempotency presence).
- `src/components/alerts/__tests__/AlertQueuePage.test.tsx` — render with mocked api + AuthProvider context; empty state, rows render, filter change refetches, row click navigates.
- `src/components/alerts/__tests__/AlertDetailPage.test.tsx` — renders fields; acknowledge flow; 409 conflict banner; 428 approval banner in Dismiss; escalate navigate.

Verification:
- `npm test` (Frontend) — must keep 15 baseline + new green.
- `npm run build` — must pass (fixes baseline auth.ts error).
- Backend regression unchanged: `cd services && python3 -m pytest shared/tests workbench/tests -q` → 429 passed / 4 skipped (extended 433/0 with `INTEGRATION_DATABASE_URL`). No backend files touched.

## 5. Out of Scope (per task brief, confirmed)

Investigation detail/queue, case queue/detail, decision form, IR inbox, approval queue page, notifications page, comment/timeline surfaces, any backend/contract/RBAC/schema change, WS live push for the queue.

## 6. Known Risks / Decisions

- A1 `total` semantics (pagination UX adapted; backend untouched).
- All alert mutations return 200 (not 201); success handling is 2xx-based.
- Admin detail view is a metadata-only shape; renderer tolerates missing description/related fields.
- Assign action: in scope using `adminApi.getUsers` (analyst + compliance, active) for the selector; backend `_validate_assignee` enforces scope + role capability; `reason` required for reassignment/reopen.
- 428 UX requires creating an ApprovalRequest via AP1 when the actor holds `approval:request`; poll AP3 until `approved`/`rejected`/`expired`. If the actor lacks `approval:request`, the DismissModal shows the approval-required notice with guidance to contact compliance (matching "waiting for compliance officer").
