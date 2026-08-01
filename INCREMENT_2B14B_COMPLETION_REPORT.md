# Increment 2B.14b — Root-Cause Fix: Empty-Status `WorkflowStateError` in Assigned-List Reads — Completion Report

Status: COMPLETE. Verification green. No migration, table, state, permission, endpoint, DTO, pagination, or frontend change.

---

## 1. Increment Title

Backend fix — collection/list reads (all four assigned-list endpoints) no longer raise `WorkflowStateError` under the real (unmocked) `authorise()`.

## 2. Reason This Increment Is Required

Phase 2B.14's IR Inbox frontend depends on `GET /api/v1/information-requests/assigned` (delivered in 2B.14a). That endpoint — and the three pre-existing assigned-list endpoints it mirrors — constructs a `Resource(id="", status="", entity_type=...)` for its list-scope `authorise()` call. `authorise()` step 6 (workflow-state gate) then raises `WorkflowStateError("Action ... not permitted in status ")` for the empty status, so the real (unmocked) engine **never permits any assigned-list read**. The mocked service tests patched `authorise`, so the defect was latent until the 2B.14 frontend needed the real HTTP/service path.

## 3. Authoritative Documents Followed

- 2B.14 task spec — block the assigned-list `WorkflowStateError`; prefer one consistent collection-authorisation pattern for all four endpoints; forbid a blanket `if not resource.status: allow`; forbid new permissions/schema/states/endpoints/query changes; preserve 403-vs-404 conventions and the frozen `authorise()` step ordering (1 known action → 2 prohibited combo → 3 permission → 4 scope → workflow-state gate)
- `increment-2B-authorisation-policies.md` / `increment-2B-state-machines.md` — policy-step order, `OWNERSHIP_ACTIONS`/`CREATOR_ACTIONS` instance checks, transition maps unchanged
- 2B.14a completion report §16 — flags this exact runtime issue as pre-existing across all four assigned-list endpoints and defers the root-cause fix to 2B.14b

## 4. Baseline Backend Tests

`cd services && python3 -m pytest shared/tests workbench/tests -q` → **443 passed, 4 environment-gated skips** (confirmed before coding).

## 5. Files Created

- `services/shared/tests/test_authorise_collections.py` — real-policy tests for the collection authorisation pattern
- `services/workbench/tests/test_assigned_list_authorization.py` — real-`authorise` service tests for all four assigned-list endpoints

## 6. Files Modified

- `services/shared/authorise.py` — added `COLLECTION_TRANSITIONS` (synthetic `"active"` state → the four list/read actions only) and registered `"collection"` in `ENTITY_TRANSITIONS`
- `services/workbench/services/alert_service.py` — `list_assigned` now authorises `Resource(id="assigned", status="active", entity_type="collection")`
- `services/workbench/services/investigation_service.py` — same change for `list_assigned`
- `services/workbench/services/case_service.py` — same change for `list_assigned`
- `services/workbench/services/information_request_service.py` — same change for `list_assigned`

## 7. Root Cause

`services/shared/authorise.py` step 6:

```python
valid_actions = ENTITY_TRANSITIONS.get(entity_type, {}).get(status, set())
if action not in valid_actions:
    raise WorkflowStateError(status, action)
```

A collection read has no single entity instance, yet the four services passed `Resource(status="", ...)`. `""` maps to no transition set, so even a granted read permission 409'd. This is exactly the class of problem already solved for other status-less reads via synthetic states — `NOTIFICATION_TRANSITIONS` (`unread`/`read`), `TIMELINE_TRANSITIONS` (`active`), `OUTBOX_TRANSITIONS` (`active`), `ORPHAN_TRANSITIONS` (`active`) — which is the pattern 2B.14b extends.

## 8. Design Decision

One consistent collection-authorisation pattern for all four endpoints:

- The four services authorise an explicit collection resource: `Resource(id="assigned", status="active", entity_type="collection")`.
- `COLLECTION_TRANSITIONS` admits **only** the four list/read actions: `alert:read_assigned`, `investigation:read_own`, `case:read_assigned`, `info_request:read_assigned`.
- Permission, prohibited-combo, scope, and ownership/creator checks are untouched; only the workflow-state lookup changes, so collection reads flow through the same engine with no new code path.

Why this over the alternatives: it is the smallest change, follows the repo's established synthetic-state convention for status-less reads (timeline/outbox/orphan/notification), adds no flag-branching in the hot `authorise()` loop, and keeps the map narrow (reads only).

## 9. Why Instance Mutations Stay Protected

There is **no** blanket `if not resource.status: allow`. The fix is scoped to an explicit `"collection"` entity type whose map contains zero mutation actions. Verified against the real engine:

- `alert:transition` with empty status → `WorkflowStateError` (workflow gate intact)
- `alert:acknowledge` with empty status → `OwnershipDeniedError` (ownership gate fires first; still fail-closed)
- `case:reopen` on the collection resource → `WorkflowStateError` (mutation not in collection map)
- `info_request:create` on the collection resource → `OwnershipDeniedError` (fail-closed)
- `timeline:read`, `info_request:read`, `info_request:create` (all granted) on the collection resource → denied — the map admits only the four list/read actions
- `info_request:read_assigned` on an empty-status `information_request` instance → `WorkflowStateError` — instance reads still require a real status

## 10. Behavior Preserved

- `authorise()` step ordering unchanged (action-known → prohibited → permission → scope → workflow-state). No new permission, state, schema, endpoint, path, DTO, or query change.
- 403 vs 404 vs 409 semantics preserved: missing permission → 403 `PERMISSION_DENIED`; out-of-scope collection resource → 404 `SCOPE_DENIED`; wrong-state instance mutation → 409 `WORKFLOW_STATE`; unknown action → 400 `UNKNOWN_ACTION`.
- `OWNERSHIP_ACTIONS` / `CREATOR_ACTIONS` instance checks unchanged and still evaluated for instance mutations.

## 11. Tests Added (+20)

- `services/shared/tests/test_authorise_collections.py` (13): all four list actions allowed on the collection resource; missing permission denied (all four); manager without permission denied; scope check still applies; unknown action fails; non-list action rejected; other read action rejected; workflow mutation rejected; empty-status workflow-gated mutation still 409s; empty-status ownership-gated mutation still denied; instance read still requires a real status.
- `services/workbench/tests/test_assigned_list_authorization.py` (7): each of the four services (`AlertService`, `InvestigationService`, `CaseService`, `InformationRequestService`) runs `list_assigned` with the **real** `authorise()` (only repo fetches patched) and succeeds; missing-permission user is denied through the real engine for each; an empty-status instance read still 409s.

All new tests exercise the real (unmocked) `authorise()` — the existing service tests that patch `authorise` are untouched and still pass.

## 12. Real-Database + Real HTTP Route Verification

Against the migrated `banking_worker_integration` PostgreSQL scratch DB (FKs on `users`, `organisation_scopes`, etc.), a standalone script seeded two analysts, a compliance user, three cases (two `hq_main`, one `eu_main`), and four IRs, then mounted the actual `information_requests` router in a FastAPI app (`app.state.db` = live connector; middleware injects the authenticated `ApplicationUser` and scope) and drove `GET /api/v1/information-requests/assigned` over ASGI with the real `authorise()` engine:

- Valid analyst → **200**, only the two own `hq_main` IRs; `eu_main` row (assigned to the same user but out of scope) excluded; real `total` 2
- `status=returned` filter → 1 row; pagination `per_page=1` → `total` 2, 1 item
- Second analyst → only their own row (own-only enforcement)
- User without `info_request:read_assigned` → **403 `PERMISSION_DENIED`** (not 409 `WORKFLOW_STATE`)
- No writes to `activity_timeline`, `notifications`, `audit_outbox`, `comments`, `approval_requests`, `decisions`, `assignment_history`
- All scratch rows cleaned up afterwards

Output: `ALL REAL-PATH CHECKS PASSED` (200 own-only, scope exclusion, filter, pagination, 403-vs-409, read-only, cleanup).

## 13. Final Backend Regression Count

`python3 -m pytest shared/tests workbench/tests -q` → **463 passed, 4 skipped** (baseline 443 + 20 new tests). No existing test weakened.

## 14. Frontend Regression / Build Confirmation

Frontend untouched (`git status` shows backend-only changes). Baseline reconfirmed:
- `npm test` → **99 passed (12 files)**
- `npm run build` → **passes** (only pre-existing chunk-size / keycloak dynamic-import warnings)

## 15. Confirmation of No Schema Change

No new migration, table, state, permission, endpoint, path, DTO, or query. The change is confined to the authorisation policy layer (`COLLECTION_TRANSITIONS`) and the four services' list-scope resource objects.

## 16. Files Modified Reference

- `services/shared/authorise.py:313-327` — `COLLECTION_TRANSITIONS` + `ENTITY_TRANSITIONS["collection"]`
- `services/workbench/services/alert_service.py:161` — collection resource
- `services/workbench/services/investigation_service.py:175` — collection resource
- `services/workbench/services/case_service.py:205` — collection resource
- `services/workbench/services/information_request_service.py:359` — collection resource

## 17. Readiness Verdict for 2B.14 Frontend: Information Request Inbox

**READY.** The empty-status `WorkflowStateError` is root-caused and fixed for all four assigned-list endpoints via one consistent collection-authorisation pattern; instance mutations remain workflow/ownership-gated (verified against the real engine); 403/404/409 semantics and the frozen `authorise()` step order are preserved; 20 new unmocked authorization tests pass; full backend regression is green (463 + 4 skips); real-PostgreSQL + real-HTTP-route verification passed with zero side-effect writes; the frontend baseline remains green (99 tests + build).
