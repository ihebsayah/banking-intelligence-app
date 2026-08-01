# Phase 2B.10 Closure Report — Admin Outbox Endpoints

Date: 2026-08-01
Scope: Closure of 2B.10 (AD1 + AD2) per
`.specs/increment-2/increment-2B-implementation-sequence.md` §2B.10 (line 182).
AD3 (orphan-assignments) is 2B.10b and is intentionally NOT part of this increment.

## 1. Increment title
Phase 2B.10 — Admin Outbox Endpoints (2 endpoints: `GET /admin/outbox`, `POST /admin/outbox/{outbox_id}/retry`).

## 2. Documents followed
- `increment-2B-implementation-sequence.md` — 2B.10 DoD (line 182): GET /admin/outbox with status filter; POST /admin/outbox/:id/retry resets to pending; admin:outbox_monitor permission gating; AU03/AU04 scenarios pass.
- `increment-2B-api-contracts.md` §10 — AD1, AD2 contracts (lines 680-700).
- `increment-2B-audit-outbox-design.md` — outbox schema, status enum, worker, poison semantics.
- `increment-2B-authorisation-policies.md` — `admin:outbox_monitor`/`admin:outbox_retry` (lines 80-81, 131-132).
- `increment-2B-test-plan.md` — AU03, AU04 scenarios (lines 116-117).
- Migration `0003_add_audit_outbox.py`, `0005_add_permission_seeds.py`; existing `OutboxRepo`/`outbox_worker.py`/`AuditOutboxEvent`.

## 3. Baseline
`python3 -m pytest shared/tests workbench/tests -q` → **396 passed, 1 skipped**
(the skip is the env-gated real-DB integration test; `INTEGRATION_DATABASE_URL` unset).

## 4. Alignment findings
- Contract AD1 lists only `status`/`page`/`per_page` params — **no** event_type/entity/request_id/date filters exist; none were added.
- AD1 response = "outbox rows with attempt_count, last_error, poison_reason". The full row (incl. `payload`) is returned. Sensitive payload fields are already hashed by design (audit-outbox-design.md line 118), the endpoint is admin-only, and `payload.request_id` is the EC06 trace link — exposing it is safe and intended. Noted as a deliberate choice, no spec deviation.
- AD2 action matches the contract exactly: `SET status='pending', attempt_count=0, poison_reason=NULL WHERE outbox_id=$1`, audit `admin.outbox_retry`, response `{queued:true, outbox_id}`.
- Status filter passes through as a free string (repo `WHERE status=$1`), matching the approvals AP2 convention — the codebase does not enum-validate filter params.
- AU03's "admin notified" on poison is a worker concern (2B.2/2B.16); the current worker only logs poison. 2B.10 covers the endpoint half: admin *sees* poison via `GET /admin/outbox?status=poison`.

## 5. Files created
- `services/workbench/routers/admin_outbox.py` — AD1/AD2 routes (standalone APIRouter, `/api/v1` prefix, un-mounted like all workbench routers).
- `services/workbench/services/admin_outbox_service.py` — `AdminOutboxService.list` / `.retry`.
- `services/workbench/schemas/admin_outbox.py` — `OutboxListResponse`, `OutboxRetryResponse` (items reuse the `AuditOutboxEvent` domain model).
- `services/workbench/tests/test_admin_outbox.py` — 6 tests.

## 6. Files modified
- `services/shared/authorise.py` — added `OUTBOX_TRANSITIONS = {"active": {"admin:outbox_monitor", "admin:outbox_retry"}}`, registered as `"audit_outbox"` in `ENTITY_TRANSITIONS` (synthetic "active" state, mirroring NOTIFICATION/TIMELINE transitions).
- `services/workbench/repos.py` — `OutboxRepo.list(status, limit, offset)` (`ORDER BY created_at DESC`), `OutboxRepo.count(status)`, `OutboxRepo.retry(outbox_id)`.
- `services/workbench/tests/test_repos.py` — 3 SQL-level tests.
- `services/shared/tests/test_authorise_2b9.py` — 3 transition-wiring tests (`TestAdminOutboxActions`).

## 7. Endpoint matrix
| # | Method & path | Permission | Service fn | Action |
|---|---|---|---|---|
| AD1 | GET `/api/v1/admin/outbox` | `admin:outbox_monitor` | `list` | paginated rows, `status` filter |
| AD2 | POST `/api/v1/admin/outbox/{outbox_id}/retry` | `admin:outbox_retry` | `retry` | reset to pending + audit `admin.outbox_retry` |

## 8. Permission matrix
| Permission | analyst | compliance | admin | Used by |
|-----------|---------|-----------|-------|---------|
| `admin:outbox_monitor` | — | — | ✓ | AD1 |
| `admin:outbox_retry` | — | — | ✓ | AD2 |

Both seeded (`0005` lines 72-73) and present in `ALL_PERMISSION_CODES`. **No new permissions.** Neither action is ownership-, creator-, scope-, or approval-gated; admin-only by role matrix + permission check through `authorise()`.

## 9. Pagination / filtering
Canonical pagination: `page` (ge=1), `per_page` (ge=1, le=100), cap `min(per_page, 100)`, offset `(page-1)*limit`; response `{total, page, page_size, items}`; `ORDER BY created_at DESC` (most recent first). Single filter: `status` (free string). Repo SQL pinned by tests (`WHERE status=$1 ... ORDER BY created_at DESC LIMIT $2 OFFSET $3`).

## 10. Replay / retry behavior
Retry (AD2) resets `status→pending`, `attempt_count→0`, `poison_reason→NULL` for the targeted row — the exact contract SQL. The next worker cycle (`claim_next_batch`, which selects `pending`/`failed` with `next_attempt_at <= NOW()`) picks it up. No replay endpoint exists in the spec — none was added.

## 11. Worker interaction
AD2 writes only the outbox row + a new `admin.outbox_retry` audit row; it does not touch the worker's `delivering`/`failed` state machine beyond the reset. The worker's `mark_failed` backoff path (`next_attempt_at` delay) is preserved — retry sets `attempt_count=0` so the backoff restarts fresh. `reconcile_stuck`/`count_poison` untouched.

## 12. Audit safety
- No duplicate audit events: the retry emits a **new** `admin.outbox_retry` event (idempotency_key `audit_outbox.{outbox_id}.admin.outbox_retry.{uuid}`), distinct from the original event being retried.
- Exactly-once delivery preserved: re-delivering a retried event re-sends the same `idempotency_key` to the audit agent, which dedupes (AU05).
- Payloads in AD1 are the already-hashed-by-design envelopes; no verbatim sensitive content crosses the admin boundary.

## 13. Idempotency guarantees
The retry UPDATE is idempotent by construction (unconditional reset — retrying a pending row is a no-op on state). Re-delivery safety is delegated to the audit agent's `X-Idempotency-Key` dedup, matching AU05. No client `X-Idempotency-Key` cache was added because the contract defines none for AD2 and the operation is naturally idempotent.

## 14. Tests added
- `test_admin_outbox.py` (6): AD1 admin list + status filter + pagination; AD1 permission denied; AD2 retry resets + emits `admin.outbox_retry` with correct before/after payload; AD2 404 on missing; AD2 permission denied; exact route registration (2).
- `test_repos.py` (3): list SQL (`WHERE status=$1`, `ORDER BY created_at DESC`, limit/offset), count SQL, retry SQL (`status='pending'`, `attempt_count=0`, `poison_reason=NULL`).
- `test_authorise_2b9.py` (3): `admin:outbox_monitor`/`admin:outbox_retry` allowed for admin on the synthetic resource; retry denied for compliance.

## 15. PostgreSQL verification
No migration was added or changed (outbox schema already exists from `0003`; permissions from `0005`). The env-gated real-DB integration suite (`test_expiry_worker_integration.py`) remains valid but is not exercised here (`INTEGRATION_DATABASE_URL` unset). All new SQL is pinned by unit SQL-assertion tests.

## 16. Final regression count
`python3 -m pytest shared/tests workbench/tests -q` → **408 passed, 1 skipped** in 2.37s (+12 tests; the 1 skip is the unchanged env-gated integration test).

## 17. No existing tests weakened
Confirmed — 396→408 with zero modifications to pre-existing test behavior; nothing skipped, xfailed, or de-prioritised.

## 18. No unauthorized schema changes
Confirmed — zero migration files touched or added. No new tables, roles, permissions, or workflow states (the two admin permissions and the outbox table were already seeded/created in `0003`/`0005`). The only authorise change is a transition-map registration reusing existing permissions.

## 19. Phase 2B.10 complete?
**Yes.** All four DoD bullets verified: AD1 with status filter; AD2 reset-to-pending; `admin:outbox_monitor` (and `admin:outbox_retry`) permission gating; AU03 (poison visible via `?status=poison`) and AU04 (retry → attempt_count=0, pending, worker picks up) implemented and test-covered.

## 20. Exact next canonical increment
**2B.10b — Admin Orphan-Assignment Endpoint** (`GET /admin/orphan-assignments`, `admin:orphan_monitor`, O001/O002), per `increment-2B-implementation-sequence.md` line 190.
