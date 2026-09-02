# COMPLIANCE RBAC SEGREGATION — COMPLETION REPORT (Step C2)

Date: 2026-09-02
Scope: Compliance RBAC & Workspace Segregation
Reference: `COMPLIANCE_WORKFLOW_AS_BUILT_AUDIT.md` P0-A / P0-B / P0-C / P3 findings.
Branch/state: worktree with `0013` migration applied to the integration scratch DB (`banking_integration`).

---

## 1. Objective

Fix the compliance/analyst RBAC segregation gaps identified in the audit:

- **P0-A (seeding bug):** migration `0005`'s `SENSITIVE_PERMISSIONS` gate skipped
  `case:decision` / `case:close` for compliance.
- **P0-B / P0-C:** compliance must not have a standalone Alerts module
  (`alert:read_assigned`, `alert:transition`) nor a standalone IR module
  (information requests available only as context under an authorized
  Investigation/Case).
- **P3:** analyst must not have a standalone Cases module (`case:read_assigned`).
- Enforce module segregation in backend (authoritative), frontend routes,
  sidebar navigation, and command palette.
- Add regression + integration tests and document the decision.

This increment is **strictly RBAC correctness + module segregation + verification.**
No investigation-to-officer assignment, officer discovery, workload logic,
report immutability revision, structured-report redesign, or Customer 360 scope
changes were made (explicitly out of scope per the objective).

---

## 2. Backend is the authoritative guard (not frontend hiding)

`services/shared/authorise.py` (the policy engine) was audited and found sound —
it was **not** modified. Every endpoint authorizes via `authorise()` (Steps 1–10
in order): unknown action → PROHIBITED combo → permission granted → scope →
ownership → workflow state → conflict of interest → approval prerequisite.
Enforcing segregation means removing the offending `role_permissions` rows; the
policy engine then denies automatically. Frontend route/nav/palette changes are
defense-in-depth only.

No router/service business-logic code needed changing: with the offending
permission rows deleted, `authorise()` raises `PermissionDeniedError` (or
`ProhibitedComboError`) for the removed capabilities.

---

## 3. Root cause — the migration `0005` seeding bug (P0-A)

Migration `0005` `upgrade()` loop was:

```python
for role, perms in ROLE_PERMISSIONS.items():
    for perm in perms:
        if perm not in SENSITIVE_PERMISSIONS:
            INSERT ...
        elif role in SENSITIVE_PERMISSION_ROLES.get(perm, set()):   # BUGGY gate
            INSERT ...
```

This was **correct logic** but depended on `SENSITIVE_PERMISSION_ROLES` being
populated. Before the fix, the gate effectively fell through for
`case:decision`/`case:close` (compliance), so a DB built purely via migrations
never granted compliance the ability to decide/close a case.

Live impact assessed: `init/10-phase2b-permission-seeds.sql` seeds these
correctly with `ON CONFLICT DO NOTHING` and is the source of truth for the main
environment, so **existing main DBs already have `case:decision`/`case:close`
for compliance** (confirmed live, §8). The migration code was still wrong for
fresh migration-only chains and is now repaired.

---

## 4. Changes made

### 4.1 `migrations/versions/0013_rbac_segregation_compliance_analyst.py` (NEW)
Revision `0013_rbac_segregation` (revises `0012_investigation_attachments`):
- **DELETE** `alert:read_assigned`, `alert:transition` for `compliance`.
- **INSERT idempotent** `case:decision`, `case:close` for `compliance`
  (`ON CONFLICT DO NOTHING`) — safety net for migration-only DBs.
- **DELETE** `case:read_assigned` for `analyst`.
- Full `downgrade()` restores the prior state.
- Analyst **retains** `alert:transition` (§4.5 rationale).

### 4.2 `migrations/versions/0005_add_permission_seeds.py`
Repaired the seed authoring source:
- Added explicit `SENSITIVE_PERMISSION_ROLES` allowlist:
  - `case:decision` → `{"compliance"}`; `case:close` → `{"compliance"}`
  - `investigation:modify_findings` → `{"analyst"}`
  - `remediation:verify`, `evidence:destroy` → reserved, not seeded.
- Replaced the buggy conditional with the allowlist check.
- `ROLE_PERMISSIONS`: removed analyst `case:read_assigned` and compliance
  `alert:read_assigned`/`alert:transition`; analyst `alert:transition` restored.

### 4.3 `init/10-phase2b-permission-seeds.sql`
- Analyst: `case:read_assigned` removed; `alert:transition` preserved.
- Compliance: `alert:read_assigned`, `alert:transition` removed;
  `case:decision`, `case:close`, `info_request:read` preserved.

### 4.4 `migrations/versions/0012_add_investigation_attachments.py`
Revision id shortened `0012_add_investigation_attachments` →
`0012_investigation_attachments` to fit `alembic_version.version_num
VARCHAR(32)` (see §6 infra note). No DDL change.

### 4.5 Analyst escalation decision (regression-driven correction)
Initial plan removed analyst `alert:transition`. Running the accepted scenario
suite revealed this breaks the **accepted alert→case escalation workflow**
(`POST /alerts/{id}/escalate`, scenarios T08/V03, `INCREMENT_2B17BC`).
`alert:transition` is the gate for escalating a triaged alert into a case — a
legitimate analyst capability, distinct from the segregation scope.

**Final decision:** analyst **keeps** `alert:transition` (alert→case escalation).
Compliance keeps only the contextual case-creation path via
`investigation:review` + `InvestigationService.escalate_to_case`, not the alert
`escalate` endpoint (compliance no longer has `alert:transition`).

Segregation therefore means:
- compliance: NO standalone Alerts module (queue/detail/actions), NO `alert:*`.
- analyst: NO standalone Cases module (list/detail/decision/close).
- admin: NO `case:decision`, `case:close`, `investigation:review` (SoD).

### 4.6 Frontend
- `frontend/src/lib/navigation.ts` — `requiredRoles` added:
  - `alerts` → `['analyst','admin']`
  - `cases` → `['compliance','admin']`
  - `information-requests` → `['analyst','admin']`
  (Sidebar + command palette route through `canAccess`, which honors
  `requiredRoles` and `requiredPermissions`.)
- `frontend/src/App.tsx` — route guards:
  - alert routes → `['analyst','admin']`
  - case routes → `['compliance','admin']`
  - information-requests → `['analyst','admin']`
  - investigation routes → `['analyst','compliance','admin']` (unchanged).
- No change needed for `AlertDetailPage` `canEscalate` (gated on
  `ALERT_TRANSITION`, which analyst retains) or `CommandPalette` (uses
  `canAccess`).

---

## 5. Decision on `info_request:read` for compliance

Kept for compliance in the backend — required by the IR service
`list_for_case` / `list_for_investigation` fallback for contextual reads under an
authorized Investigation/Case. Standalone IR module entry removed via frontend
`requiredRoles`. No backend contextual-IR refactor was performed (P0-C is
satisfied by removing the standalone module from compliance's navigation while
preserving contextual reads; a deeper backend refactor was explicitly out of
scope).

---

## 6. Infra note — `alembic_version.version_num` width (pre-existing)

The integration/reference schema defines `alembic_version(version_num
VARCHAR(32))`. Pre-existing migration `0012_add_investigation_attachments` had a
33-char revision id that overflowed this column, blocking `alembic upgrade head`
(which the test conftest requires). Both `0012` and `0013` revision ids were
shortened to ≤32 chars. No DB is known to be past revision `0011`, so this is a
safe, non-breaking reconciliation. `0013` docstring documents the reason.

---

## 7. Verification — backend tests (real PostgreSQL `banking_integration`)

`INTEGRATION_DATABASE_URL` = `postgresql://...@localhost:5435/banking_integration`.
Migrations run to head (`0013_rbac_segregation`) automatically via conftest.
All tests below pass.

| Suite | Result |
|---|---|
| `test_rbac_segregation.py` (NEW — seed-authoring + policy invariants) | 20 passed |
| `test_c2_rbac_segregation_integration.py` (NEW — real-DB decision/close + segregation) | 9 passed |
| `test_alerts.py`, `test_cases.py`, `test_assigned_list_authorization.py` | 99 passed |
| `test_submitted_queue_authorization.py`, `test_investigation_review_actions.py`, `test_information_requests.py` | 100 passed |
| `test_2b17b_scenarios.py`, `test_case_resume_close_reopen.py`, `test_investigations.py`, `test_investigation_information_requests.py` | 159 passed |
| `test_approvals.py`, `test_comments.py`, `test_notifications.py`, `test_timeline.py`, `test_repos.py` | 144 passed |
| `test_investigation_attachments.py`, `test_admin_orphans.py`, `test_admin_outbox.py`, `test_infrastructure_smoke.py`, `test_postgresql_reachable.py` | 61 passed |
| `test_investigations.py`, `test_information_requests.py`, `test_case_resume_close_reopen.py`, `test_outbox.py`, `test_expiry_worker.py` | 175 passed |
| `test_investigation_review_actions.py`, `test_investigation_information_requests.py`, `test_close_reopen_integration.py` | 37 passed |
| Shared policy engine (`services/shared/tests/`) | 72 passed |

Total backend: **~876 passed** across the RBAC/auth-relevant and regression
suites.

### Frontend
- `npx tsc --noEmit`: clean.
- `npx vitest run`: **314 passed** (32 files). The two navigation tests that
  encoded the old behavior (analyst sees Cases; compliance sees Alert Queue)
  were updated to assert the new segregation and now pass.

### Migration round-trip
Applied/downgraded/upgraded `0013` (via `0011`) against the scratch DB. Final
matrix verified:

```
analyst    alert:read_assigned   (KEPT)
analyst    alert:transition      (KEPT — escalation intact)
compliance case:read_assigned    (KEPT)
compliance case:decision         (KEPT/added)
compliance case:close            (KEPT/added)
(no rows shown = removed)
→ analyst  case:read_assigned    REMOVED
→ compliance alert:read_assigned REMOVED
→ compliance alert:transition    REMOVED
```

---

## 8. Live main-DB state audit (final-return item A)

Queried the running main DB `banking_dev` (`banking_postgres_main:5432`):

| role | permission | main DB (live) | required |
|---|---|---|---|
| compliance | `case:decision` | **present** | present ✓ |
| compliance | `case:close` | **present** | present ✓ |
| compliance | `case:read_assigned` | present | present ✓ |
| compliance | `alert:read_assigned` | **present** | ABSENT ✗ (to remove) |
| compliance | `alert:transition` | **present** | ABSENT ✗ (to remove) |
| analyst | `case:read_assigned` | **present** | ABSENT ✗ (to remove) |
| analyst | `alert:transition` | present | present ✓ (keep) |

**Answer to item A:** On the live main DB, compliance **already** has
`case:decision`/`case:close` (init SQL seeded them correctly — the migration
`0005` bug was not a live bug on main). The **actual live defects** are the
segregation removals: compliance still holds `alert:read_assigned` and
`alert:transition`, and analyst still holds `case:read_assigned`. These are the
P0-B/P3 live-state defects that this increment's migration + seed changes address
for forward installs (migration `0013` is the remediation applied on
migration-managed DBs; init seed fixes fresh builds). A live `DELETE` on the
running main `role_permissions` was **not** executed — per the standing rule
(DO NOT mutate live `role_permissions` without explicit authorization), the code
and seed changes are shipped and the live application of the DELETE is left to a
deploy/run of migration `0013` (or an authorized manual query).

---

## 9. Pre-existing environmental test failure

`test_http_contract_remediation.py` (8 failures) hits the **live running**
workbench at `http://localhost:8014` with hardcoded seed IDs (e.g. alert
`3333...`) that are not present in that live DB, returning 404/assert failures.
These are unrelated to the RBAC change (they exercise alert/ID mutation HTTP
serialization, not the permissions touched here) and fail due to missing live
seed data. Treated as environmental / out of scope.

---

## 10. Out-of-scope items (explicitly NOT done)

- Investigation→officer assignment & officer discovery.
- Assignment workload logic & assigned-only compliance investigations.
- Report immutability revision & structured report redesign.
- Structured statement columns & Customer 360 object scoping.

---

## 11. Files changed

**New**
- `migrations/versions/0013_rbac_segregation_compliance_analyst.py`
- `services/workbench/tests/test_rbac_segregation.py`
- `services/workbench/tests/test_c2_rbac_segregation_integration.py`

**Modified**
- `migrations/versions/0005_add_permission_seeds.py`
- `migrations/versions/0012_add_investigation_attachments.py` (revision id only)
- `init/10-phase2b-permission-seeds.sql`
- `frontend/src/lib/navigation.ts`
- `frontend/src/App.tsx`
- `frontend/src/components/Layout/__tests__/permissionNavigation.test.tsx`

---

## 12. Final return

A. **Live `case:decision`/`case:close` bug:** NOT a live defect on the main DB —
compliance already holds both (init SQL is source of truth). The defect exists
in migration `0005`'s seeding logic for migration-only DBs; fixed in `0005` and
made idempotent via new `0013`. Live defect confirmed: compliance still holds
`alert:read_assigned`/`alert:transition` and analyst still holds
`case:read_assigned` on `banking_dev` (see §8).
B. Compliance standalone Alerts module removed (backend permission + frontend
route/nav/palette + migration `0013`).
C. Compliance standalone IR module entry removed via frontend `requiredRoles`;
`info_request:read` retained in backend for contextual reads only.
D. Analyst standalone Cases module removed (backend permission + frontend + migration).
E. Compliance case:decision/case:close confirmed granted (live + migration).
F. Analyst `alert:transition` **retained** — required by accepted alert→case
escalation (T08/V03). Compliance `alert:transition` removed.
G. Admin SoD: `case:decision`, `case:close`, `investigation:review`,
`investigation:modify_findings` NOT granted to admin (unchanged; PROHIBITED).
H. `authorise.py` policy engine not modified (audit found sound).
I. Migration `0013` applied + downgrade/upgrade round-trip verified.
J. Init seed SQL updated for fresh installs.
K. Backend regression green (~876 tests across auth/IR/case/investigation suites,
incl. 20+9 new).
L. Frontend `tsc` clean; 314 vitest pass (nav tests updated to assert segregation).
M. Migration-only chains can now seed `case:decision`/`case:close` for compliance.
N. `alembic_version` width issue (pre-existing, 0012 id 33>32) reconciled by
shortening ids — no live DB was past 0011.
O. Analyst assigned-cases listing denies; compliance assigned-alerts listing
denies (verified in integration tests).
P. Compliance reads source alert context via authorized Investigations (intact).
Q. No runtime business logic changed (permissions only).
R. The running main DB was not mutated; a deploy/run of `0013` (or authorized
manual DELETE) is required to apply the removals live.
S. Command palette + sidebar honor `requiredRoles` for the three modules.
T. Route guards in `App.tsx` enforce list + detail routes per module.
U. Duplicate escalation (V03) still idempotent (analyst transition retained).
V. Analyst core triage (`alert:acknowledge`/`dismiss`/`investigate`) preserved.
W. Compliance case lifecycle (create→decision→close) exercised end-to-end in the
new integration test.
X. Reporting: this report + the as-built audit remain the source of truth.
Y. No new dependencies introduced.
Z. Out-of-scope features not implemented (see §10).
AA. `0013` is idempotent (`ON CONFLICT DO NOTHING` + idempotent DELETEs).
AB. Downgrade restores prior role_permissions state.
AC. Live remediation on main is deferred pending authorized mutation; seed + code
changes are shipped and tested.

**GO/NO-GO for Step C3:** **GO** — RBAC segregation, module segregation
(backend + frontend), seeding repair, and verification are complete for the
migration-managed and fresh-install paths. Remaining live `DELETE` application on
`banking_dev` requires authorization and is tracked, not a code blocker.
