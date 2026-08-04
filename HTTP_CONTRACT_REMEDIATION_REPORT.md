# Workbench HTTP Contract Remediation — Completion Report

**Date**: 2026-08-03
**Session**: Phase 2B role-access remediation — Step 2 continuation (HTTP contract fixes)
**Verdict**: **FIXED**

---

## 1. Defect A — Root Cause & Fix

**Root cause**: `GET /api/v1/alerts/{alert_id}` declares `response_model=AlertResponse`. The admin path in `AlertService.get_by_id` returns an `AlertAdminResponse` instance (intentionally omitting `title` and `updated_at`). FastAPI validates the returned object against the route's declared `response_model`; because `AlertAdminResponse` lacks those required fields, Pydantic raises `ResponseValidationError` → HTTP 500.

**Fix**: Changed the route's `response_model` to `Union[AlertResponse, AlertAdminResponse]` in `services/workbench/routers/alerts.py:70`, mirroring the already-established pattern in `information_requests` and `comments`. FastAPI tries the first variant; if it fails (missing `title`/`updated_at`), it falls through to `AlertAdminResponse` which matches the restricted DTO exactly.

No changes to either response schema. No fake fields added.

## 2. Defect B — Root Cause & Serialization Strategy

**Root cause**: Every mutation router returns an explicit `JSONResponse(content=result.model_dump(), ...)`. In Pydantic v2, `model_dump()` defaults to `mode="python"`, which preserves Python `datetime` objects. `starlette.responses.JSONResponse` calls `json.dumps` on the content dict; `json.dumps` cannot serialize `datetime` → `TypeError: Object of type datetime is not JSON serializable`. The exception propagates past the endpoint, the generic handler catches it and returns `{"error":"INTERNAL_ERROR"}` (HTTP 500). **The DB transaction has already committed at this point**, so mutations succeed server-side but clients see a 500.

**Serialization strategy selected**: `model_dump(mode="json")`. This is the smallest consistent change compatible with custom status codes, custom response headers (`X-Version`), and idempotency replay responses (which store and re-return `result.model_dump_json()` via the service — round-tripping through `model_validate_json` then `model_dump(mode="json")` produces identical serialisation).

Replaced every occurrence of `result.model_dump()` with `result.model_dump(mode="json")` across 7 routers (25 occurrences). No architectural redesign. No ad-hoc datetime-to-string conversion.

Affected mutation routes: all `PATCH`/`POST` endpoints that manually construct a `JSONResponse`. GET/list endpoints were unaffected (they rely on FastAPI's normal response-model serialization).

## 3. Affected Routes / Files (Defect B)

| Router | Lines changed | Mutations fixed |
|--------|--------------|-----------------|
| `services/workbench/routers/alerts.py` | 5 | assign, acknowledge, dismiss, investigate, escalate |
| `services/workbench/routers/cases.py` | 5 | assign, transition, close, reopen, record_decision |
| `services/workbench/routers/investigations.py` | 3 | update, transition, cancel |
| `services/workbench/routers/approvals.py` | 2 | create, vote |
| `services/workbench/routers/information_requests.py` | 6 | create, acknowledge, respond, accept, return, cancel |
| `services/workbench/routers/notifications.py` | 2 | mark_read, mark_all_read |
| `services/workbench/routers/comments.py` | 2 | create, redact |

Also audited (no `model_dump()` calls): `admin_outbox.py`, `admin_orphans.py`, `timeline.py` — these already return models directly and were not affected.

## 4. Defect C — Root Cause & Fix

**Root cause**: `admin_orphans.router` existed and was tested in `tests/test_infrastructure_smoke.py` (the smoke test mounts it explicitly), but `integration_app.py` (the deployed staging app, also used by production entrypoint `main.py`) never included it in its router inventory. The `_WORKBENCH_PREFIX_MAP` in `api_gateway/routes.py` also lacked a mapping, so the gateway returned `NOT_FOUND` for `/admin/orphan-assignments`.

**Fix**:
- Added `admin_orphans` import and `admin_orphans.router` to the mount loop in `services/workbench/integration_app.py:189-200`.
- Added `"admin/orphan-assignments": "api/v1/admin/orphan-assignments"` to `_WORKBENCH_PREFIX_MAP` in `services/api_gateway/routes.py:1873`.

Both `main.py` (production) and `integration_app.py` (staging) share the same router inventory because `main.py` calls `build_integration_app()`.

## 5. Files Modified (This Session)

```
services/workbench/integration_app.py          # mount admin_orphans
services/workbench/routers/alerts.py           # Union response_model + model_dump(mode="json") x5
services/workbench/routers/cases.py            # model_dump(mode="json") x5
services/workbench/routers/investigations.py   # model_dump(mode="json") x3
services/workbench/routers/approvals.py        # model_dump(mode="json") x2
services/workbench/routers/information_requests.py  # model_dump(mode="json") x6
services/workbench/routers/notifications.py    # model_dump(mode="json") x2
services/workbench/routers/comments.py         # model_dump(mode="json") x2
services/api_gateway/routes.py                 # _WORKBENCH_PREFIX_MAP orphan entry
services/workbench/tests/test_http_contract_remediation.py  # NEW: 14 HTTP contract tests
```

## 6. Tests Added

`services/workbench/tests/test_http_contract_remediation.py` — 14 tests across 9 classes:

- `TestLiveness::test_workbench_health` — connectivity gate.
- `TestAlertMutationSerialization` — analyst acknowledge on already-acknowledged alert (proves no 500, valid JSON, ISO datetimes).
- `TestCaseMutationSerialization` — compliance case transition assigned→under_review (version delta, ISO datetimes).
- `TestInvestigationMutationSerialization` — analyst findings update (version delta, ISO datetimes).
- `TestApprovalMutationSerialization` — analyst create + compliance vote (201 then 200, approval_count, decisions array).
- `TestInformationRequestMutationSerialization` — analyst IR respond (status+version delta, responded_at ISO).
- `TestNotificationMutationSerialization` — analyst mark read (is_read=true).
- `TestCommentMutationSerialization` — analyst comment create (201, entity_type/entity_id/author_id).
- `TestAdminAlertContract` — analyst full view vs admin restricted view (title present/absent, updated_at present/absent).
- `TestAdminOrphanMount` — OpenAPI path presence, admin 200, non-admin 403.
- `TestIdempotencyReplay` — fresh request → replay identical body → body-mismatch → 409 IDEMPOTENCY_MISMATCH.

A session-scoped autouse fixture resets the canonical demo entities to seeded state before each test run, making the suite re-runnable without side effects.

## 7. HTTP Test Results

```
======================== 14 passed in 1.17s ========================
```

All assertions pass including ISO-datetime validation, version deltas, schema shape checks, and the 409 idempotency mismatch.

## 8. Live Analyst Mutation Result

Endpoint: `PATCH /alerts/{A3}/acknowledge` (A3 = 33333333-3333-4333-8333-333333333333, already assigned to analyst_001)

```
HTTP 200 OK
X-Version: 3
Body (truncated): {"success":true,"alert":{"alert_id":"33333333-...","title":"Unassigned pattern-match alert",
  ... "created_at":"2026-08-03T04:25:28.187921Z","updated_at":"2026-08-03T04:37:19.812029Z","version":3},
  "version":3}
```

Previously returned HTTP 500 `INTERNAL_ERROR` due to datetime TypeError. Now returns 200 with clean ISO-8601 datetimes.

## 9. Live Compliance Mutation Result

Endpoint: `PATCH /investigations/{I4}/transition` (I4 = aaaaaaaa-4444-4444-8444-444444444444, submitted)

```
HTTP 200 OK
X-Version: 2
Body (truncated): {"success":true,"investigation":{"investigation_id":"aaaaaaaa-4444-...","title":"Threshold avoidance analysis",
  ... "completed_at":"2026-08-03T04:37:19.897279Z","version":2}, "version":2}
```

Previously returned HTTP 500. Now 200.

## 10. Live Admin Alert-Read Result

Endpoint: `GET /alerts/{A1}` as admin_001 (A1 = 11111111-1111-4111-8111-111111111111)

```
HTTP 200 OK
{"alert_id":"11111111-1111-4111-8111-111111111111","alert_type":"kpi_breach","severity":"high",
 "status":"acknowledged","assigned_to":"analyst_001","scope_id":"hq_main",
 "created_at":"2026-08-03T04:25:28.187921Z","version":2}
```

Restricted DTO confirmed: NO `title`, NO `updated_at`. Previously HTTP 500 ResponseValidationError.

## 11. Live Orphan-Assignment Result

Endpoint: `GET /admin/orphan-assignments` as admin_001

```
HTTP 200 OK
Body: {"alerts":[],"investigations":[...28 items...],"cases":[...29 items...]}
```

Also verified non-admin denial: `analyst_001` → 403 `PERMISSION_DENIED` (admin:orphan_monitor). Route appears in OpenAPI.

## 12. Idempotency Replay Verification

Using investigation update on I1 with `X-Idempotency-Key: http:remediation:idem:i1:v1`:

- Fresh request: 200, body captured.
- Replay with same key + same body: 200, body byte-identical to fresh. Datetime fields parse as ISO-8601 on replay.
- Mismatch with same key + different body: 409 `IDEMPOTENCY_MISMATCH` (canonical error).

## 13. Backend Regression Count

| Suite | Passed | Errors | Notes |
|-------|--------|--------|-------|
| `services/workbench/tests/` (full, excl. smoke) | 531 | 4 | 4 pre-existing async-pool errors in integration-style tests unrelated to this change |
| `services/workbench/tests/test_infrastructure_smoke.py` | 11 | 0 | |
| `services/shared/tests/` (auth) | 71 | 0 | |
| New: `test_http_contract_remediation.py` | 14 | 0 | |
| **Total** | **627** | **4** | All 4 errors are pre-existing (asyncpg pool + event-loop issues in long-running integration tests) |

No new regressions introduced.

## 14. Frontend Regression / Build

Not applicable. No frontend code was touched. The gateway prefix-map addition is server-side only; the frontend was not exercised in this session.

## 15. Remaining Issues

None outstanding. All three defects are resolved. The 4 pre-existing workbench integration-test errors (asyncpg connection-pool reuse across event loops) are outside the scope of this remediation and were present before any changes in this session.

## 16. Final Verdict

**FIXED**

- All affected mutations return valid JSON instead of 500 ✓
- Admin Alert detail returns 200 with the restricted DTO (no title/updated_at leak) ✓
- Admin orphan endpoint is mounted, reachable through Gateway, and permission-gated ✓
- Idempotency replay serializes cleanly and mismatch yields canonical 409 ✓
- No existing tests regress ✓
- Zero `TypeError: datetime` / `ResponseValidationError` in workbench logs since restart ✓
