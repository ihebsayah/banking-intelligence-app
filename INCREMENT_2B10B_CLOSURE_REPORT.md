# Phase 2B.10b Closure Report — Admin Orphan-Assignment Endpoint

Date: 2026-08-01
Scope: Closure of 2B.10b (AD3) per
`.specs/increment-2/increment-2B-implementation-sequence.md` §2B.10b (line 190).

## 1. Increment title and number
Phase 2B.10b — Admin Orphan-Assignment Endpoint (1 read-only endpoint: `GET /admin/orphan-assignments`).

## 2. Authoritative documents followed
- `increment-2B-implementation-sequence.md` — 2B.10b DoD (lines 190-196).
- `increment-2B-api-contracts.md` — AD3 contract (lines 703-713).
- `increment-2B-test-plan.md` — O001/O002 scenarios (lines 185-190).
- `increment-2B-frontend-workflows.md` — noted only; the API contract wins (see §23).
- Migrations `0001` (users, roles), `0002` (organisation_scopes, user_scopes), `0004` (alerts, investigations, compliance_cases), `0005` (permission seeds), `0006` (legacy_role), `0008` (system actor, identity_provider).
- Existing admin patterns: `admin_outbox` router/service/schemas, `authorise()` synthetic-resource convention, `repos.py` repo conventions, `test_expiry_worker_integration.py` env-gated real-DB pattern.

## 3. Baseline test result
`python3 -m pytest shared/tests workbench/tests -q` → **408 passed, 1 skipped**
(the skip is the env-gated real-PG expiry-worker test).

## 4. Pre-implementation alignment findings
- Contract AD3 defines the response as a grouped dict `{ alerts, investigations, cases }` — **no pagination, no filters, no reason codes, no audit** ("Audit: None (read-only)").
- Orphan conditions are the literal contract query: assignee `status NOT IN ('active','active_pending')` **OR** assignee absent from `user_scopes` for the entity's `scope_id`. Nothing else.
- `admin:orphan_monitor` is **not seeded anywhere** — new migration `0009` seeds the permission (admin role only). This is spec-driven: the contract mandates the permission; the task outline's "no new permissions" clause conflicts with the authoritative artifact, which wins.
- Entity coverage is alerts + investigations + compliance_cases only. Information requests are **not** in the DoD or contract response and were excluded. No other assignable types exist in the contract.
- The contract query has **no entity-status filter** (see §9) and no `assigned_to IS NOT NULL` guard (unassigned rows are excluded by SQL NULL semantics — see §10).
- No role/permission/legacy_role/identity_provider conditions — the contract query references only `users.status` and `user_scopes`.
- Response item shape (contract): `{ entity_id, title, status, assigned_to: { user_id, status } }` — the assignee's `status` is the diagnostic.

## 5. Endpoint matrix
| # | Method & path | Permission | Service fn | Action |
|---|---|---|---|---|
| AD3 | GET `/api/v1/admin/orphan-assignments` | `admin:orphan_monitor` | `AdminOrphanService.list` | read-only grouped orphan report |

No mutation, reassignment, bulk, repair, or delete routes exist.

## 6. Exact permission
`admin:orphan_monitor`, seeded by **migration `0009_add_admin_orphan_monitor`** (permission row + `role_permissions` grant to the `admin` role only). Present in `ALL_PERMISSION_CODES` and wired as the synthetic `"orphan_assignment"/"active"` resource in `ENTITY_TRANSITIONS` (`ORPHAN_TRANSITIONS`), mirroring `OUTBOX_TRANSITIONS`. Denied to analyst, compliance, manager, system, and unauthenticated users.

## 7. Entity coverage
| Entity | Table | ID | Title col | Assigned col | Scope col |
|---|---|---|---|---|---|
| Alert | `alerts` | `alert_id` | `title` | `assigned_to` | `scope_id` |
| Investigation | `investigations` | `investigation_id` | `title` | `assigned_to` | `scope_id` |
| Compliance case | `compliance_cases` | `case_id` | `title` | `assigned_to` | `scope_id` |

Information requests, decisions, approvals, comments, timeline rows, notifications, and outbox events are excluded (not assignable per the frozen contract).

## 8. Canonical orphan reasons
Exactly two conditions, verbatim from the contract query (no invented reason codes — the response shape has no reason field):
1. **Ineligible status** — assignee `users.status NOT IN ('active','active_pending')` (covers suspended, inactive, system actor, etc.).
2. **Out of scope** — assignee has no `user_scopes` row for the entity's `scope_id` (also covers FK-impossible nonexistent assignees; the `assigned_to` FK guarantees a user row exists, so condition 2's `NOT IN` is unambiguous).

## 9. Active and terminal-state rules by entity
**All entity statuses are reported.** The contract query filters on assignee only; it does not reference entity status. Per the instruction hierarchy, the frozen artifact wins over the task outline's "terminal resource excluded" expectation. A `dismissed`/`completed`/`closed` record assigned to an ineligible user **is** reported (real-DB test `test_terminal_records_reported_per_contract` pins this). Rationale: the contract is literal, and the admin report is diagnostic. Flagged in §23.

## 10. Unassigned-resource behavior
`assigned_to IS NULL` is **not** orphaned — `NULL IN (...)` / `NULL NOT IN (...)` are NULL (not TRUE), so unassigned rows fall out of the WHERE clause naturally, exactly as the contract query reads. Real-DB test seeds an unassigned alert (`44444444-…`) and asserts it is absent.

## 11. Scope behavior
Exact-match `user_scopes` join per entity `scope_id` (same as `approval_service._fetch_eligible_approvers`, no parent-scope inheritance). A user whose only scope is `global` assigned to an `hq_main` resource is flagged (real-DB `orphan_otherscope`). The mismatch is reported, never modified.

## 12. Query strategy
One `UNION ALL` over the three tables (option A) — a single round trip, zero N+1 user/scope queries. `LEFT JOIN users` per branch supplies `assigned_user_status`. Deterministic ordering: `ORDER BY entity_type, entity_id` (the contract is silent on ordering; choice documented).

## 13. Response-security design
Explicit DTO only (`OrphanAssignmentItem`: `entity_id`, `title`, `status`, `assigned_to{user_id, status}`). No findings, conclusion, rationale, question/response text, description, Keycloak subject, JWT, or credential fields. Verified by `test_restricted_dto_only` (exact key set) and the real-DB `test_no_sensitive_fields_in_result`.

## 14. Pagination and filtering
**None** — the contract response is three un-paginated lists with no query parameters. No `page`/`per_page`/`total`/filters were added (adding them would violate the frozen shape). Deterministic ordering `ORDER BY entity_type, entity_id`.

## 15. Files created
- `migrations/versions/0009_add_admin_orphan_monitor.py` — seed `admin:orphan_monitor` (admin only), downgrade removes it.
- `services/workbench/schemas/admin_orphans.py` — `OrphanAssignee`, `OrphanAssignmentItem`, `OrphanAssignmentsResponse`.
- `services/workbench/services/admin_orphan_service.py` — `AdminOrphanService.list`.
- `services/workbench/routers/admin_orphans.py` — AD3 route.
- `services/workbench/tests/test_admin_orphans.py` — 13 unit tests.
- `services/workbench/tests/test_orphan_integration.py` — 3 real-PG tests (env-gated).

## 16. Files modified
- `services/shared/authorise.py` — added `admin:orphan_monitor` to `ALL_PERMISSION_CODES`, `ORPHAN_TRANSITIONS`, `ENTITY_TRANSITIONS["orphan_assignment"]`.
- `services/workbench/repos.py` — new `OrphanRepo` (`ORPHAN_ELIGIBLE_STATUSES`, `orphan_assignments()`).
- `services/workbench/tests/test_repos.py` — 3 `TestOrphanRepo` SQL tests + `OrphanRepo` import.
- `services/shared/tests/test_authorise_2b9.py` — ADMIN user gains `admin:orphan_monitor`; appended `TestAdminOrphanActions` (5 tests).

## 17. Tests added by category
- **Authorization (8):** admin allowed; denied for analyst, compliance, manager, system, and admin-without-permission (5 parametrized) in `test_admin_orphans.py`; plus authorise-level allow/deny in `test_authorise_2b9.py` (5, incl. manager and system denial).
- **Detection (4):** grouping by entity type, terminal-status reporting, empty-when-clean, assignee status carried.
- **Response security (2):** restricted DTO key set; no pagination fields on the response model.
- **Route (1):** exactly one route, GET only, exact path.
- **Repository SQL (3):** UNION ALL over 3 tables + both conditions + ordering; no entity-status filter; eligible-status params.
- **Real-PostgreSQL (3):** orphan detection + valid/exclusion, terminal per contract, no sensitive fields.

## 18. Real-database verification
Scratch DB `banking_orphan_integration` (docker `postgres:16`), migrated via `alembic upgrade head` through **0009**. Real-DB tests pass (3). Seeded: valid/active assignee, suspended/inactive assignees, scope-missing and global-only users, unassigned + terminal records. Verified: only the 5 expected orphans returned; 3 valid assignments excluded; unassigned excluded; `assigned_user_status` correct for status-orphans (`suspended`) vs scope-orphans (`active`); terminal records reported; result keys exact. Migration **downgrade/upgrade round-trip** verified (permission removed then re-seeded, `role_permissions` grant restored).

## 19. Final core regression count
`python3 -m pytest shared/tests workbench/tests -q` → **429 passed, 4 skipped** (skips = 4 env-gated real-PG tests; unchanged pass-set otherwise).

## 20. Final extended regression count
With `INTEGRATION_DATABASE_URL` set: **433 passed, 0 skipped, 0 failures** (all real-DB tests run).

## 21. No tests weakened
Confirmed — the only pre-existing test edits are additions (a permission on the shared-test ADMIN fixture and an appended test class). 408 → 429 (+21 unit tests). No test skipped, xfailed, or de-prioritised. One earlier failure during development (expiry-worker FK) was caused by an over-broad integration-test cleanup and fixed by scoping cleanup to `orphan%` fixtures, not by altering any pre-existing test.

## 22. No unauthorized schema changes
Confirmed with one spec-driven exception: **one permission row added** (`admin:orphan_monitor`, migration `0009`) because the frozen contract AD3 requires it and it was not previously seeded — no tables, columns, roles, workflow states, or other migrations added. No assignment-history, notification, timeline, or outbox writes occur anywhere in the endpoint.

## 23. Remaining ambiguity or limitation
- **Terminal-state exclusion** was expected by the task brief but is **not** in the frozen contract query; implemented per the contract (all entity statuses reported). If terminal exclusion is wanted, it is a one-line `WHERE` addition per branch + DoD/spec change — not made here.
- **Legacy manager** and **identity-link** (`identity_provider_subject`) are not orphan conditions — the contract query does not reference `users.role`, `legacy_role`, or identity columns. A legacy manager with `status='active'` and the resource scope is not flagged. Contract-faithful; flagged, not silently broadened.
- `increment-2B-frontend-workflows.md:23` lists the orphan page gate as `admin:outbox_monitor`; the API contract AD3 (`admin:orphan_monitor`) is authoritative for this increment. The frontend phase (2B.19) should reconcile.

## 24. Is 2B.10b closed?
**Yes.** The canonical endpoint is implemented (exact path/method); both orphan conditions are detected; valid assignments are excluded; sensitive business content is not exposed (DTO verified in unit + real-DB tests); authorization is admin-only (analyst/compliance/manager/system denied); no mutation side effects occur (pure read, no audit event); the full regression suite passes (core 429/4skip, extended 433/0); and real-PostgreSQL validation succeeded.

## 25. Exact next canonical task
**Phase 2B.11 — Frontend: Alert Queue + Detail** (`/workbench/alerts` + `/workbench/alerts/:id`), per `increment-2B-implementation-sequence.md` line 198.
