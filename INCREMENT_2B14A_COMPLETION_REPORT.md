# Increment 2B.14a — Backend Prerequisite: Assigned Information Request Inbox — Completion Report

Status: COMPLETE. Verification green. No migration, table, state, permission, or frontend change.

---

## 1. Increment Title

Backend Prerequisite — `GET /api/v1/information-requests/assigned` (Analyst IR Inbox).

## 2. Reason This Prerequisite Is Required

The frozen 2B.14 frontend (`/workbench/information-requests`) is an analyst view of IRs assigned to self across all cases. Implementation discovery confirmed the existing IR endpoints (`POST|GET /cases/{case_id}/information-requests`, `GET|PATCH /information-requests/{ir_id}…`) only expose IRs via a specific case or specific IR id — there was no cross-case assigned-list endpoint. Without this endpoint the IR Inbox frontend has no data source, so the 2B.14 frontend remained blocked.

## 3. Authoritative Documents Followed

- `increment-2B-implementation-sequence.md` — 2B.14 DoD (lines 229–235)
- `increment-2B-frontend-workflows.md` §1.5/1.6 — IR Inbox: status filter (open, acknowledged, responded, returned), columns (case id, question, due_date, status), overdue derived client-side from `due_date`, empty state, acknowledge/respond actions (existing endpoints)
- `increment-2B-api-contracts.md` / `increment-2B-state-machines.md` / `increment-2B-authorisation-policies.md` — permission `info_request:read_assigned`, IR state machine unchanged
- Existing IR router/service/schemas/repos and the Alert/Investigation/Case `list_assigned` patterns

No conflict found between the frozen frontend need and the existing backend: the spec's `due_date`/`return_reason` fields already exist on `InformationRequest`; overdue is a frontend-derived indicator (spec: "due_date < today" client-side), so no due-date filter is added.

## 4. Baseline Backend Tests

`cd services && python3 -m pytest shared/tests workbench/tests -q` → **429 passed, 4 environment-gated skips** (confirmed before coding).

## 5. Files Created

None. The increment is additive code in existing files only (plus a standalone throwaway real-DB verification script that was deleted after passing).

## 6. Files Modified

- `services/workbench/repos.py` — `InfoRequestRepo.list_assigned` + `count_assigned`
- `services/workbench/services/information_request_service.py` — `InformationRequestService.list_assigned`
- `services/workbench/routers/information_requests.py` — new `GET /information-requests/assigned` route
- `services/workbench/tests/test_information_requests.py` — service tests + route-registration updates
- `services/workbench/tests/test_repos.py` — repo tests

## 7. Endpoint Contract

`GET /api/v1/information-requests/assigned`
- Query params: `status` (optional string), `page` (default 1, ge 1), `per_page` (default 50, ge 1, le 100)
- Response: canonical `InformationRequestListResponse` (`total`, `page`, `page_size`, `items`)
- Items use the **full** `InformationRequestResponse` DTO (the assignee legitimately sees `question`, `response_text`, `return_reason`, etc.) — restricted fields are not omitted for the assigned analyst
- No mutation headers (`X-Request-ID`/`X-Idempotency-Key`) — read-only

## 8. Permission and Ownership Behavior

- Route requires `info_request:read_assigned` (seeded permission; no new permission, no broad `info_request:read`)
- Object-level policy: SQL predicate `ir.assigned_to = current_user.user_id` — the endpoint **cannot** return another user's assigned request, and does not return requests merely because the user created them (no `created_by` broadening)
- Scope behavior: IR scope lives on the owning `compliance_cases.scope_id`; the query joins to the case and filters `c.scope_id = ANY(user scopes)` (falls back to the request scope when `ApplicationUser.scopes` is empty) — an IR on a case outside the user's scopes is excluded even if assigned to them
- Compliance: receives only IRs assigned directly to that compliance user (creator ownership is not re-interpreted as assignment)
- Admin: does **not** receive all IRs through this endpoint — the same `assigned_to` predicate applies; broader case-linked compliance access remains via `GET /cases/{case_id}/information-requests`
- Manager/system: no new grants; access requires `info_request:read_assigned` in the user's permission set, same as the existing per-case list

## 9. Query / Filter / Pagination Behavior

- Filters implemented: `status`, `page`, `per_page` only — nothing invented (no priority/title/search/case-status/due-date range)
- Ordering: `created_at DESC`, stable `ir_id` tie-breaker (task fallback; the frontend spec defines no ordering)
- Pagination: page >= 1, per_page 1..100, LIMIT/OFFSET, **real `total` count** (`SELECT COUNT(*)` with the same predicate — not the Alert queue's page-length quirk)
- Overdue: not filtered server-side; `due_date` is returned and the frontend derives the overdue badge (frozen spec)

## 10. Route-Order Safety

The static route is registered **before** `GET /information-requests/{ir_id}` in the router; FastAPI matches in registration order, so `/information-requests/assigned` can never be captured as `{ir_id} = "assigned"`. Existing eight IR routes are untouched and still registered (confirmed by the updated `TestRouteRegistration` suite, route count 8 → 9).

## 11. Tests Added (+14)

- `test_repos.py` `TestInfoRequestAssignedRepo` (5): assignee+scope JOIN predicate and ordering; status filter + LIMIT/OFFSET; no `created_by` broadening + SELECT-only; `count_assigned` same predicate; empty count
- `test_information_requests.py` `TestListAssigned` (8): own assigned returned with full DTO (question, due_date); query restricted to current user; status filter + pagination + real total; empty inbox; `authorise` called once with `info_request:read_assigned`; permission-denied propagation; no mutation side effects (no UoW/timeline/outbox/notification writes)
- `test_information_requests.py` `TestRouteRegistration` (updated): new route present as GET; **static `assigned` precedes dynamic `{ir_id}`**; obsolete routes still absent; exact route count 9

## 12. Real-Database Verification

Against the migrated `banking_worker_integration` PostgreSQL scratch DB (uuid columns, FKs), a standalone script seeded two analysts, cases in two scopes, and four IRs, then exercised `InfoRequestRepo` directly:

- Own assigned only returned; other analyst's IR excluded
- Out-of-scope IR (case in `global` scope, user scoped to `hq_main`) excluded even though assigned to the user
- Ordering `created_at DESC` verified; `due_date` and `return_reason` survive typed conversion
- Status filter (`returned`) correct; `count_assigned` real totals (2 / 1 / 1) with pagination (`limit=1` → 1 row)
- No `activity_timeline` / `notifications` / `audit_outbox` / `api_idempotency` rows created by the read
- All scratch rows cleaned up afterwards (verified 0 rows remain)

Output: `REAL-DB VERIFICATION PASSED: filtering, scope, order, pagination, total, DTO, read-only`

## 13. Final Backend Regression Count

`python3 -m pytest shared/tests workbench/tests -q` → **443 passed, 4 skipped** (baseline 429 + 14 new tests). No existing test weakened.

## 14. Frontend Regression / Build Confirmation

Frontend untouched (`git status` shows backend-only files). Baseline reconfirmed:
- `npm test -- --run` → **99 passed (12 files)**
- `npm run build` → **passes** (only pre-existing chunk-size / keycloak dynamic-import warnings)

## 15. Confirmation of No Schema Change

No new migration, table, state, or permission was added. The endpoint reuses the existing `information_requests` + `compliance_cases` tables, the existing `info_request:read_assigned` seeded permission, the existing IR state machine, and the existing response/pagination envelopes.

## 16. Remaining Limitation

The endpoint mirrors the established Alert/Investigation/Case `list_assigned` pattern, including its list-scope `authorise()` call with an empty-status `Resource`. That call currently raises `WorkflowStateError` (409) under the real (unmocked) `authorise()` because the workflow gate has no empty-status allowance — a pre-existing condition affecting all four assigned-list endpoints, exercised only by mocked tests. It is deliberately not touched here (task: "do not change existing endpoints", "do not redesign"). If the real queues hit it, the root-cause fix is a single empty-status allowance in `authorise()` — out of 2B.14a scope, flag for the next backend increment.

## 17. Readiness Verdict for 2B.14 Frontend: Information Request Inbox

**READY.** The assigned inbox endpoint exists, returns only the authenticated assignee's requests (scope-joined), pagination is correct with a real total, route shadowing is impossible (static-before-dynamic, tested), no existing IR endpoint changed, the complete backend regression passes (443 + 4 skips), the frontend baseline remains green (99 tests + build), and real-PostgreSQL verification passed.
