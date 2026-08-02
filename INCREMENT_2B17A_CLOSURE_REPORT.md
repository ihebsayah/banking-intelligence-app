# Increment 2B.17a — Integration Test Infrastructure — Closure Report

Status: COMPLETE. Verification green against the live integration PostgreSQL (`banking_postgres_integration`, port 5435). No schema, permission, endpoint, or frontend change.

---

## 1. Increment Title

Integration test infrastructure for Phase 2B.17: a dedicated PostgreSQL database, session-level Alembic migration, real-HTTP audit-agent mock, and worker harnesses so the full 2B.17 test suite (T00–T35, XA, V, AU, F, IRS, DP) can run against real PostgreSQL instead of mocks.

## 2. Reason This Increment Is Required

2B.17 requires scenarios executed "against real DB" (implementation-sequence §2B.17). Before 2B.17a the workbench tests were unit tests over a mocked `DatabaseConnector`; there was no scratch database, no migration wiring for a second environment, and no way to exercise the outbox/expiry workers over real HTTP or real rows. 2B.17a adds that substrate.

## 3. Authoritative Documents Followed

- `increment-2B-implementation-sequence.md` §2B.17 — integration suite DoD; `services/workbench/tests` is the suite's home
- `increment-2B-test-plan.md` — scenario IDs the harnesses target (AU01–AU08 outbox, AP01–AP04 approvals, O001/O002 orphans)
- `increment-2B-api-contracts.md` AD3 — canonical orphan-assignment query reused by `test_orphan_integration.py`
- `migrations/` + `alembic.ini` — single migration chain, reused for the integration DB

## 4. Files Created

- `.env.integration` — integration DB credentials/URL (host `localhost`, port 5435, db `banking_integration`)
- `docker-compose.integration.yml` — dedicated `postgres-integration` service (postgres:16-alpine, port 5435, healthcheck, named volume, `banking-network`)
- `scripts/start_integration_db.sh` — `docker compose up -d` + health wait loop
- `scripts/stop_integration_db.sh` — `docker compose down`
- `scripts/reset_db.sh` — `dropdb`/`createdb` inside the container for a clean slate
- `services/workbench/tests/test_audit_mock.py` — real `http.server` audit-agent mock on port 18008; records POST events (path/method/headers/body); reset + get helpers
- `services/workbench/tests/test_infrastructure_smoke.py` — 11 tests: PG reachable; alembic head; seeded permissions load; authenticated protected HTTP; missing-permission 403; workflow-factory inserts valid graph; outbox worker real HTTP delivery; duplicate delivery idempotency-key retention; expiry worker AP5 (expire overdue + side effects); system-actor timeline FK; DB cleanup reusability
- `services/workbench/tests/test_postgresql_reachable.py` — reachability gate
- `services/workbench/tests/test_outbox_worker_harness.py` — mocked-client harness: delivery success and failure marking (AU01/AU02 state transitions)
- `services/workbench/tests/test_expiry_worker_harness.py` — real-DB harness: overdue expirations, future skips
- `services/workbench/tests/test_orphan_integration.py` — real-PostgreSQL contract tests for `OrphanRepo.orphan_assignments()` (O001/O002, terminal-status reporting, no sensitive fields)

## 5. Files Modified

- `services/workbench/tests/conftest.py` — added session-autouse `run_migrations` (upgrades the integration DB to head, skips when `INTEGRATION_DATABASE_URL` unset), `integration_db` async connector fixture, session-autouse `audit_mock_server`, `mock_audit_agent`, `seed_users`/`seed_workflow_objects`, plus the pre-existing unit fixtures retained untouched
- `migrations/env.py` — hard-fail if `sqlalchemy.url` resolves empty (prevents a silent no-op migration run)

## 6. Test Counts (run against live integration DB)

| File | Tests | Scope |
|------|-------|-------|
| `test_postgresql_reachable.py` | 1 | env gate |
| `test_infrastructure_smoke.py` | 11 | mixed real-DB + HTTP |
| `test_orphan_integration.py` | 3 | real-DB contract |
| `test_outbox_worker_harness.py` | 2 | mocked client |
| `test_expiry_worker_harness.py` | 2 | real-DB |
| **Total** | **19** | |

## 7. Verification Evidence

- All 19 2B.17a tests pass against the running `banking_postgres_integration` container (migrated to head via the session `run_migrations` fixture).
- Full backend regression: `pytest services/shared/tests services/workbench/tests -q` → **483 passed** (baseline from 2B.14b closure: 463 passed + 4 skips; +20 for the later 2B.15/2B.16/2B.17a increments). No existing test weakened.
- Outbox delivery is verified over real HTTP: worker posts to the mock audit agent on 18008, header `X-Idempotency-Key` matches the source row, and a second worker cycle does not re-deliver.
- Expiry worker verified against real rows: overdue approvals → `expired` plus `notifications` + `audit_outbox` side effects; future-dated approvals untouched.
- Orphan detection verified against real rows: suspended/inactive-assignee + scope-orphan entities returned; valid/terminal ones excluded; result shape matches the AD3 contract.

## 8. Test Invocation

```bash
scripts/start_integration_db.sh
source .env.integration
export INTEGRATION_DATABASE_URL="postgresql://${POSTGRES_INTEGRATION_USER}:${POSTGRES_INTEGRATION_PASSWORD}@${POSTGRES_INTEGRATION_HOST}:${POSTGRES_INTEGRATION_PORT}/${POSTGRES_INTEGRATION_DB}"
export PYTHONPATH="$PWD/services"
testenv/bin/pytest services/workbench/tests/test_infrastructure_smoke.py services/workbench/tests/test_orphan_integration.py -q
```

## 9. Readiness Verdict for 2B.17

**READY.** The substrate 2B.17 needs is in place and green: dedicated integration Postgres with healthchecked lifecycle scripts, one-shot Alembic upgrade to head at session start, a real-HTTP audit-agent mock, outbox/expiry/orphan harnesses, and a reusable cleanup pattern. The remaining 2B.17 work is authoring the scenario suite (T00–T35, XA01–XA10, V01–V11, AU01–AU08, F01–F18, IRS01, DP01–DP04) against this substrate.
