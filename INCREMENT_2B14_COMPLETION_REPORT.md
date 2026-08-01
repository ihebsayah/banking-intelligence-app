# Increment 2B.14 — Analyst Information Request Inbox (`/workbench/information-requests`) — Completion Report

Status: COMPLETE. Verification green. No backend change, migration, schema, state, permission, or endpoint change. Pure frontend increment on top of the 2B.14a endpoint and the 2B.14b runtime fix.

---

## 1. Increment Title

Analyst-facing Information Request Inbox at `/workbench/information-requests`: assigned-IR queue with status filtering, overdue badges, and a modal response form implementing acknowledge → respond and the returned/re-acknowledge flow. Canonical sidebar + route registration, permission-gated like every workbench surface.

## 2. Reason This Increment Is Required

Phase 2B.14 is the final canonical analyst surface. Compliance creates information requests against cases; analysts must see what is assigned to them, which are overdue, and act on them (acknowledge, answer, re-acknowledge after a return) without leaving the workbench. The backend endpoint (`GET /information-requests/assigned`) and runtime fix shipped in 2B.14a/2B.14b; this increment delivers the consuming UI.

## 3. Authoritative Documents Followed

- `increment-2B-implementation-sequence.md` lines 229–235 — frozen 2B.14 DoD: `/workbench/information-requests` analyst view; overdue badge on past `due_date`; IR response form with acknowledge + respond; returned IR shows reason banner + re-acknowledge flow; no detail route, no comments/timeline in 2B.14 (documented deferment).
- `increment-2B-frontend-workflows.md` §1.5–1.6 — queue columns (case link id, truncated question, due_date, status badge); status filter open/acknowledged/responded/returned; empty "No information requests assigned to you"; overdue applied to `due_date < today` with status not terminal (red due_date + non-color "Overdue" text); response form = modal from inbox row with read-only question/case link/due date/status badge, Acknowledge when open|returned, textarea enabled when acknowledged|returned, Submit via PATCH respond, returned banner `Returned — reason: {return_reason}`, 409 → refresh notice with draft preserved.
- `increment-2B-api-contracts.md` / `increment-2B-state-machines.md` / `increment-2B-authorisation-policies.md` — consumed, **not modified**. Acknowledge = only `expected_version`; Respond = `response_text` + `expected_version`; headers `X-Request-ID`/`X-Idempotency-Key`; states open → acknowledged → responded ↔ returned → accepted/cancelled.
- 2B.14a / 2B.14b completion reports — endpoint shape and the collection-authorisation fix this UI depends on.

## 4. Baseline Frontend Tests

`cd Frontend && npm test` → **99 passed (12 files)**; `npm run build` → passes (pre-existing chunk-size + keycloak dynamic-import warnings only). Backend baseline reconfirmed: **463 passed, 4 skipped**.

## 5. Files Created

- `Frontend/src/api/informationRequestsApi.ts` — typed client: `listAssigned` (status/page/per_page → `GET /information-requests/assigned`), `get` (`GET /information-requests/{ir_id}`, used for the 409 latest-state refresh), `acknowledge` (`PATCH /information-requests/{ir_id}/acknowledge`), `respond` (`PATCH /information-requests/{ir_id}/respond`). Both mutations send `X-Request-ID` + `X-Idempotency-Key`.
- `Frontend/src/components/informationRequests/IRInboxPage.tsx` — queue page (filter, table, overdue, loading/empty/error/retry, pagination, row-select → dialog, conflict refetch of the selected row).
- `Frontend/src/components/informationRequests/IRResponseDialog.tsx` — modal response form (status badge, read-only question, case/investigation links, due date, Acknowledge / Re-acknowledge, response editor, returned banner, 409 conflict banner with draft preserved, read-only terminal states).
- `Frontend/src/api/__tests__/informationRequestsApi.test.ts` — client contract tests (7).
- `Frontend/src/components/informationRequests/__tests__/IRInboxPage.test.tsx` — queue behavior tests (10).
- `Frontend/src/components/informationRequests/__tests__/IRResponseDialog.test.tsx` — action-state tests (10).

## 6. Files Modified

- `Frontend/src/App.tsx:104` — route `/workbench/information-requests` → `IRInboxPage`, gated `requiredRole={analyst, compliance, admin}` + `requiredPermission="info_request:read_assigned"`.
- `Frontend/src/components/Layout/BankingSidebar.tsx:38` — canonical nav item `Information Requests` (MessageSquare icon) for analyst/compliance/admin, mirroring the Alerts/Investigations/Cases entries.

No backend files touched (`git status` confirms frontend-only).

## 7. Route Matrix

| Route | Component | Gate |
|---|---|---|
| `/workbench/information-requests` | `IRInboxPage` + `IRResponseDialog` | `info_request:read_assigned` (OR `info_request:read` per frozen route map; `read_assigned` is the canonical assigned-view gate) |

## 8. API-Client Matrix

| Client method | HTTP | Path | Body | Idempotency headers |
|---|---|---|---|---|
| `listAssigned` | GET | `/information-requests/assigned?status&page&per_page` | — | — |
| `get` | GET | `/information-requests/{ir_id}` | — | — |
| `acknowledge` | PATCH | `/information-requests/{ir_id}/acknowledge` | `{ expected_version }` | X-Request-ID, X-Idempotency-Key |
| `respond` | PATCH | `/information-requests/{ir_id}/respond` | `{ response_text, expected_version }` | X-Request-ID, X-Idempotency-Key |

Types reused from the canonical `Frontend/src/types/cases.ts` (`InformationRequest`, `InformationRequestListResponse`, `InformationRequestMutationResponse`). Error handling reuses the workbench parser `parseCaseError` (VERSION_CONFLICT / INVALID_TRANSITION / IDEMPOTENCY_MISMATCH → conflict; 403/404/422/503 → actionable messages). Mutation response shape matches the backend `{ success, information_request, version }` — the returned full IR (non-admin) drives the post-acknowledge editor state.

## 9. Permission Gates

- Route gate: `info_request:read_assigned` — server stays authoritative; `ProtectedRoute` prevents unnecessary round-trips.
- In-dialog gates: actions render only when the current user is the assignee (`ir.assigned_to === applicationUser.user_id`) **and** holds `info_request:respond`. Non-assignees or users without the permission see the request read-only regardless of status.
- Sidebar visibility: analyst/compliance/admin.

## 10. Inbox Behavior

- Filter: All statuses + open / acknowledged / responded / returned (server-driven; changing the filter resets to page 1 and refetches).
- Columns: Case (id link to `/workbench/cases/{id}`, with "assigned to you · vN" meta), Question (truncated), Due date, Status badge, Updated.
- Overdue: `due_date < today` and status not terminal (accepted/cancelled excluded — work no longer owed) → red due date + red "Overdue" label (non-color text, per DoD).
- Empty: "No information requests assigned to you" (+ "Try adjusting the filters." when a filter is active).
- Loading skeleton, error + Retry, pagination (per_page 50, prev/next), keyboard row activation (Enter/Space), case link stops propagation so clicking it opens the case, not the dialog.

## 11. Selected-Request Workspace (modal)

- Read-only: question, case link (`/workbench/cases/{case_id}`), investigation link (`/workbench/investigations/{investigation_id}`) when present, due date, status badge, version.
- Acknowledge (status=open|returned): PATCH acknowledge with `expected_version`; on success the dialog stays open, updates to the server-returned IR (status → acknowledged, new version) and the editor becomes enabled.
- Returned: amber banner "Returned — reason: {return_reason}" with `returned_at` / `returned_by` above the response field; prior response pre-loaded into the editor; Re-acknowledge (same canonical acknowledge endpoint, new expected_version); submitted response goes straight to respond.
- Response editor: enabled when acknowledged|returned; Submit Response disabled while empty or in flight; responds with `response_text` + `expected_version`; on success the dialog closes and the queue refetches.

## 12. Read-Only States

responded / accepted / cancelled render with the editor locked, no acknowledge, no submit, and a "request is complete" hint — the analyst cannot act on a request that is with compliance or closed. Non-assignee and missing-permission views are also read-only.

## 13. Overdue UX

Per DoD, overdue is a past `due_date` on a non-terminal request → red due-date cell and a red "overdue" text label in the row (non-color, keyboard/AT friendly), plus a red "overdue" marker in the dialog header. Terminal states (accepted, cancelled) never show overdue.

## 14. Locking / Idempotency / Conflict Handling

- Submitting disables all actions in the dialog (`submitting` flag + disabled buttons) — no duplicate acknowledge/respond.
- Every mutation sends a fresh `X-Request-ID` + `X-Idempotency-Key`.
- On 409 (`VERSION_CONFLICT` / `INVALID_TRANSITION` / `IDEMPOTENCY_MISMATCH`): the dialog stays open, shows an amber "updated by another user — your draft was kept" banner, **never auto-retries the mutation**, the parent refetches the selected IR via `get` and refreshes the queue, and the draft text is preserved (draft state initialises only on dialog open / on a different `ir_id` — never on background refetch). Resubmission uses the refreshed `expected_version`.

## 15. Loading / Empty / Error States

Loading: row skeletons. Empty: icon + "No information requests assigned to you". Error: message + Retry button that refetches the current filter/page.

## 16. Accessibility

- Filter select and response textarea have labels (`Filter by status`, `Your response`).
- Rows are keyboard-activatable (`tabIndex=0`, Enter/Space) with `aria-label="Open information request {id}"`.
- Dialog is a proper `role="dialog"` with `aria-modal` + labelled title; Escape closes it.
- Conflict and error messages use `role="alert"`.
- Overdue is conveyed with text, not color alone.

## 17. Responsive

Table wrapped in `overflow-x-auto`; meta/subtitle collapse on narrow widths; modal scrolls its body (`max-h-[60vh]`). Consistent with the existing alert/investigation/case queues.

## 18. Tests Added (+27)

- `informationRequestsApi.test.ts` (7): listAssigned params + defaults; get path; acknowledge path/body + idempotency headers; respond path/body + headers; no obsolete `/submit` or `/close` routes.
- `IRInboxPage.test.tsx` (10): render of rows; overdue shown for past-due active but not accepted; empty state; error + retry; filter sends status + resets page; row click and keyboard open dialog; case link does not open dialog; pagination next/prev; conflict refetches the selected request and keeps the dialog open.
- `IRResponseDialog.test.tsx` (10): open → Acknowledge + disabled editor; acknowledge with expected_version keeps dialog open; returned banner shows the reason; returned enables editing with prior response preserved + Re-acknowledge; respond submits text + expected_version and closes; empty response not submittable; responded/accepted/cancelled read-only; actions hidden without permission; actions hidden for non-assignee; submit disabled while in flight; conflict banner + draft preserved + no auto-retry.

All tests mock only the API client; the components render real DOM (React Testing Library + MemoryRouter).

## 19. Final Counts

- `npm test` → **126 passed (15 files)** = 99 baseline + 27 new. No existing test changed.
- `npm run build` → **passes** (only the pre-existing chunk-size and keycloak dynamic-import warnings).

## 20. Backend Regression

`cd services && python3 -m pytest shared/tests workbench/tests -q` → **463 passed, 4 skipped** — unchanged. No backend edits.

## 21. Confirmation of No Contract Change

No endpoint, path, query, DTO, state, permission, schema, or migration changed. The frontend consumes exactly the frozen 2B.14a/2B.14b contracts: `GET /information-requests/assigned`, `GET /information-requests/{ir_id}`, `PATCH …/acknowledge`, `PATCH …/respond`, `X-Request-ID` / `X-Idempotency-Key`, `{ success, information_request, version }` mutation response, and the open → acknowledged → responded ↔ returned → accepted/cancelled state machine.

## 22. Remaining Limitation (Deferred)

- No dedicated IR detail route and no comments/timeline on IRs — deferred out of 2B.14 by the frozen DoD. Case-internal IR history remains available on the case detail **Information Requests** tab.
- Sidebar count/badge for unread/overdue IRs is not in the 2B.14 scope.
- The dialog refreshes the selected request on conflict via `get`; the queue row is refreshed by the same flow.

## 23. Is 2B.14 Closed?

**YES — CLOSED.** All frozen DoD items (inbox route, assigned-only queue, status filter, overdue badges, acknowledge/respond/returned re-acknowledge workflow, returned reason banner, 409 refresh-notice with draft preserved) are implemented, permission-gated, tested (27 new frontend tests, 126 total), building clean, and riding on a green backend (463 + 4 skips) with no contract changes.

## 24. Next Canonical Task

**2B.15 — Approval Queue** (compliance/manager approve/reject of four-eyes approval requests for high-risk case closure and report-to-authority decisions). Backend work (approval_request store, approval:approve/approval:reject transitions, outbox publish) is largely in place from the case-close path; the canonical surface is the remaining frontend work.
