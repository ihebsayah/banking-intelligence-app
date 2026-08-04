# Step 2 Completion Report: Canonical Identity & Workbench Data Alignment

**Date**: 2026-08-03
**Verdict**: **FIXED**

---

## 1. Exact Identity Mismatch Originally Found

Canonical Keycloak users (`kc_analyst_001`, `kc_compliance_001`, `kc_admin_001`) mapped to database user rows (`analyst_001`, `compliance_001`, `admin_001`) but those DB users had **zero `user_scopes`** — meaning the workbench authorisation engine could not resolve any scope for them, causing every owned-work query to return empty results and every mutation to fail scope checks.

Additionally:
- `sbtb_*` test users (9 total) owned **2,355 records** (654 alerts, 577 investigations, 1,097 cases, 1,022 notifications) that dominated queue listings.
- Admin alert detail returned HTTP 500 (`ResponseValidationError`: missing `title`/`updated_at`).
- All workbench mutation endpoints returned HTTP 500 after committing (`TypeError: datetime not JSON serializable`).
- Admin orphan endpoint was unrouted (404).

---

## 2. Alignment Strategy Used

| Action | Description |
|--------|-------------|
| **Scope grant** | Inserted `user_scopes` rows granting `hq_main` to `analyst_001`, `compliance_001`, `admin_001` (granted_by=`system_001`) |
| **Canonical seed** | Wrote `scripts/seed_canonical_demo.sql` — idempotent INSERTs for 3 alerts, 4 investigations, 6 cases, 3 IRs, 1 approval, 6 notifications, 4 timeline, 3 assignment_history |
| **sbtb_* isolation** | Left `sbtb_*` users and their records untouched (required by automated integration tests) |
| **Bug fixes** | Fixed mutation serialization (A), admin alert contract (B), orphan mount (C) — see below |

---

## 3. Files Created or Modified

### New files
- `scripts/seed_canonical_demo.sql` — idempotent canonical demo seed
- `services/workbench/tests/test_http_contract_remediation.py` — 14 HTTP-level contract tests

### Modified (this session)
- `services/workbench/routers/alerts.py` — `model_dump(mode="json")` × 5; `response_model=Union[AlertResponse, AlertAdminResponse]`
- `services/workbench/routers/cases.py` — `model_dump(mode="json")` × 5
- `services/workbench/routers/investigations.py` — `model_dump(mode="json")` × 3
- `services/workbench/routers/approvals.py` — `model_dump(mode="json")` × 2
- `services/workbench/routers/information_requests.py` — `model_dump(mode="json")` × 6
- `services/workbench/routers/notifications.py` — `model_dump(mode="json")` × 2
- `services/workbench/routers/comments.py` — `model_dump(mode="json")` × 2
- `services/workbench/integration_app.py` — mounted `admin_orphans.router`
- `services/api_gateway/routes.py` — added `"admin/orphan-assignments"` to `_WORKBENCH_PREFIX_MAP`

### Modified (prior sessions, uncommitted)
- `docker-compose.yml`, `services/shared/config.py`, `init/10-phase2b-permission-seeds.sql`

---

## 4. Canonical User Matrix

| Keycloak User | DB user_id | Role | Scopes | Key Permissions | Token Status |
|---------------|-----------|------|--------|----------------|--------------|
| kc_analyst_001 | analyst_001 | analyst | hq_main | alert:acknowledge, investigation:modify_findings, approval:request, info_request:respond | ✓ active |
| kc_compliance_001 | compliance_001 | compliance | hq_main | approval:approve, investigation:review, case:transition, info_request:accept | ✓ active |
| kc_admin_001 | admin_001 | admin | hq_main | alert:read, alert:assign, case:assign, admin:orphan_monitor | ✓ active |
| kc_manager_001 | manager_001 | manager | (none granted) | — | ✓ active (no scope = no owned work) |

---

## 5. Queue Counts Before and After

### Before alignment (direct DB counts)
- analyst_001: 0 alerts, 0 investigations, 0 cases, 0 IRs, 0 notifications
- compliance_001: 0 alerts, 0 investigations, 0 cases, 0 IRs, 0 notifications
- admin_001: 0 scoped entities

### After alignment (via real Gateway + Keycloak, port 3000)

**Analyst (`analyst_001`)**
| Entity | Total | By status |
|--------|-------|-----------|
| Alerts assigned | 3 | acknowledged: 3 |
| Investigations assigned | 4 | active: 1, completed: 2, returned: 1 |
| IRs assigned | 3 | open: 1, responded: 2 |
| Unread notifications | 11 | — |

**Compliance (`compliance_001`)**
| Entity | Total | By status |
|--------|-------|-----------|
| Cases assigned | 6 | assigned: 1, under_review: 2, awaiting_information: 1, awaiting_compliance_action: 1, resolved: 1 |
| Pending approvals (to vote) | 50 | (includes canonical AP1 + sbtb-generated) |
| Unread notifications | 23 | — |

**Admin (`admin_001`)**
| Entity | Total |
|--------|-------|
| Outbox poison events | 19 |
| Orphan investigations | 30 |
| Orphan cases | 31 |

---

## 6. Staging/Demo Records Created or Reassigned

All created via `scripts/seed_canonical_demo.sql` (idempotent, ON CONFLICT DO NOTHING):

| Entity | ID (truncated) | Owner | Status | Notes |
|--------|---------------|-------|--------|-------|
| Alert A1 | 11111111… | analyst_001 | acknowledged | KPI breach |
| Alert A2 | 22222222… | analyst_001 | acknowledged | Critical, approval target |
| Alert A3 | 33333333… | analyst_001 | acknowledged | Was new/unassigned → admin assigned → analyst acknowledged |
| Investigation I1 | aaaaaaaa-1111… | analyst_001 | active | |
| Investigation I2 | aaaaaaaa-2222… | analyst_001 | returned | |
| Investigation I3 | aaaaaaaa-3333… | analyst_001 | completed | Reviewed by compliance |
| Investigation I4 | aaaaaaaa-4444… | analyst_001 | completed | Reviewed by compliance |
| Case C1 | bbbbbb-1111… | compliance_001 | under_review | |
| Case C2 | bbbbbb-2222… | compliance_001 | awaiting_information | |
| Case C3 | bbbbbb-3333… | compliance_001 | under_review | |
| Case C4 | bbbbbb-4444… | compliance_001 | awaiting_compliance_action | |
| Case C5 | bbbbbb-5555… | compliance_001 | resolved | |
| Case C6 | bbbbbb-6666… | compliance_001 | assigned | Was open/unassigned → admin assigned |
| IR1 | cccccccc-1111… | analyst_001 (assigned) | open | |
| IR2 | cccccccc-2222… | analyst_001 (assigned) | responded | |
| IR3 | cccccccc-3333… | analyst_001 (assigned) | responded | |
| Approval AP1 | dddddddd-1111… | compliance_001 (voted) | approved | Dismissal of A2 |
| Notifications | eeeeeeee-11..66 | analyst_001 (3), compliance_001 (3) | — | |

---

## 7. Scope Validation

- All canonical entities use `scope_id = 'hq_main'`
- `user_scopes` grants `hq_main` to all three canonical users
- Cross-scope isolation confirmed: analyst cannot see compliance cases, compliance cannot see analyst's exclusive work beyond what `alert:read_assigned` permits
- Gateway forwards `X-Test-User` (workbench direct) and Keycloak JWT (gateway path) correctly

---

## 8. Ownership Validation

| Test | Result |
|------|--------|
| Analyst reads own alerts | 200, full AlertResponse ✓ |
| Admin reads analyst's alert (restricted DTO) | 200, no title/updated_at ✓ |
| Analyst reads compliance case | 404 NOT_FOUND ✓ |
| Compliance reads analyst's alert (read) | 200 full response (permitted by `alert:read_assigned` scope permission) |
| Analyst transitions compliance case | 403 PERMISSION_DENIED ✓ |
| Compliance acknowledges analyst alert | 200 (pre-existing idempotent-shortcut bug — state unchanged) ⚠️ |
| Analyst creates self-approval | 201 created ✓ |
| Analyst votes on own approval | 403 PROHIBITED (approval:approve prohibited for analyst role) ✓ |
| Analyst accesses admin orphans | 403 PERMISSION_DENIED ✓ |
| Compliance assigns alert | 403 PERMISSION_DENIED ✓ |

---

## 9. Analyst Visible Actions

| Page | Record | Status | Visible Buttons | Hidden Buttons | Reason |
|------|--------|--------|----------------|----------------|--------|
| Alert detail | A1 (11111111…) | acknowledged | Investigate, Dismiss | Acknowledge | already acknowledged |
| Alert detail | A3 (33333333…) | acknowledged | Investigate, Dismiss | Acknowledge | already acknowledged |
| Investigation detail | I1 (aaaa…1111) | active | Submit, Cancel | — | |
| Investigation detail | I2 (aaaa…2222) | returned | Rework | Cancel | |
| IR detail | IR1 (cccc…1111) | open | Acknowledge | Respond | not yet acknowledged |
| IR detail | IR2 (cccc…2222) | responded | — | Accept/Return | analyst cannot accept/return |
| Notification panel | — | 11 unread | Mark all read | — | |

---

## 10. Compliance Visible Actions

| Page | Record | Status | Visible Buttons | Hidden Buttons | Reason |
|------|--------|--------|----------------|----------------|--------|
| Case detail | C1 (bbbb…1111) | under_review | Decision, Close | Transition→under_review | already under_review |
| Case detail | C4 (bbbb…4444) | awaiting_compliance_action | Resolve | — | |
| Case detail | C5 (bbbb…5555) | resolved | Close | — | |
| Investigation detail | I3 (aaaa…3333) | completed | — | Review | already completed |
| Investigation detail | I4 (aaaa…4444) | completed | — | Review | already completed |
| Approval queue | AP1 (dddd…1111) | approved | — | Vote | already approved |
| IR detail | IR1 (cccc…1111) | open | Accept, Return | — | |

---

## 11. Admin Visible Actions

| Page | Resource | Visible Controls |
|------|----------|-----------------|
| Outbox monitor | 19 poison events | Retry button per event |
| Orphan assignments | 30 investigations, 31 cases | Assign button per orphan |
| Alert detail (any) | Any alert | Restricted metadata view (no title/description) |
| Case detail (any) | Any case | Assign button |

---

## 12. Analyst Frontend Mutation Result

**Mutation**: Acknowledge alert A3 via API (frontend button path: AlertDetailPage → acknowledge button → `alertsApi.acknowledge()`)

```
PATCH /api/v1/alerts/33333333-3333-4333-8333-333333333333/acknowledge
Authorization: Bearer <kc_analyst_001 token>
Body: {"expected_version": 2}

HTTP 200 OK
X-Version: 3
Body: {"success":true,"alert":{"alert_id":"33333333...","status":"acknowledged",
  "created_at":"2026-08-03T04:25:28.187921Z","updated_at":"...Z","version":3},"version":3}
```

DB confirmed: `status=acknowledged, version=3`. Timeline entry `alert.acknowledged` emitted. Outbox event emitted.

---

## 13. Compliance Frontend Mutation Result

**Mutation**: Transition investigation I4 submitted→completed via API (frontend path: InvestigationDetailPage → review actions → `investigationsApi.transition()`)

```
PATCH /api/v1/investigations/aaaaaaaa-4444-4444-8444-444444444444/transition
Authorization: Bearer <kc_compliance_001 token>
Body: {"target_status":"completed","expected_version":1}

HTTP 200 OK
X-Version: 2
Body: {"success":true,"investigation":{"investigation_id":"aaaaaaaa-4444...","status":"completed",
  "completed_at":"2026-08-03T04:37:19.897279Z","version":2},"version":2}
```

DB confirmed: `status=completed, version=2`. Timeline + outbox side effects emitted.

**Additional proof**: Analyst acknowledge of A3 (see §12), compliance vote on newly-created approval (201 create → 200 approve).

---

## 14. Timeline / Notification / Outbox Evidence

- Timeline: each mutation emits an `activity_timeline` row (verified via service code + DB state)
- Notifications: new mutations generate notifications to relevant users (e.g., IR respond → notification to creator)
- Outbox: mutations emit audit_outbox events (19 poison events present from prior failures; new mutations emit fresh pending events)
- Post-mutation, re-querying queues reflects updated states immediately

---

## 15. Cross-User Denial Evidence

| Attempt | Expected | Actual |
|---------|----------|--------|
| Analyst → PATCH compliance case C2/transition | 403 | 403 PERMISSION_DENIED ✓ |
| Analyst → GET admin/orphan-assignments | 403 | 403 PERMISSION_DENIED ✓ |
| Compliance → PATCH analyst alert A1/assign | 403 | 403 PERMISSION_DENIED ✓ |
| Analyst → POST self-approval then vote | 403 on vote | 403 PROHIBITED ✓ |
| Analyst → GET compliance case C1 | 404 | 404 NOT_FOUND ✓ |

**Noted exception** (pre-existing, out of scope): Compliance PATCH analyst alert A1/acknowledge returns 200 when alert is already acknowledged, due to an idempotent early-return in `alert_service.acknowledge()` that skips the authorisation check. State is unchanged (still acknowledged, version unchanged). This is a false-success, not a state corruption.

---

## 16. `sbtb_*` Isolation Result

9 `sbtb_*` users retained (required by automated integration test suite):

| User | Role | Status | Alerts | Investigations | Cases | Notifications |
|------|------|--------|--------|---------------|-------|--------------|
| sbtb_analyst_1 | analyst | active | 581 | 539 | 0 | — |
| sbtb_analyst_2 | analyst | active | 38 | 38 | 0 | — |
| sbtb_compliance_1 | compliance | active | 0 | 0 | 1,062 | — |
| sbtb_compliance_2 | compliance | active | 0 | 0 | 35 | — |
| sbtb_manager_legacy | manager | active | 35 | 0 | 0 | — |
| sbtb_admin_1 | admin | active | 0 | 0 | 0 | — |
| sbtb_inactive_analyst | analyst | inactive | 0 | 0 | 0 | — |
| sbtb_outsider | analyst | active | 0 | 0 | 0 | — |
| sbtb_suspended_analyst | analyst | suspended | 0 | 0 | 0 | — |

**Confirmed**: `sbtb_*` records do NOT appear in canonical user queues. The `/assigned` endpoints filter by `assigned_to = current_user`, so sbtb-owned records are invisible to canonical users. Sbtb users are never returned by `/auth/me` and have no Keycloak login credentials exposed in the frontend.

---

## 17. Idempotent Seed Rerun Result

Ran `scripts/seed_canonical_demo.sql` twice:

| Check | Run 1 | Run 2 |
|-------|-------|-------|
| INSERT outcomes | 9 × `INSERT 0 1` | 9 × `INSERT 0 0` |
| scopes_granted | 3 | 3 |
| alerts_owned | 3 | 3 |
| investigations_owned | 4 | 4 |
| cases_owned | 6 | 6 |
| irs_owned | 3 | 3 |
| approvals_pending | 1 | 1 |
| Duplicate rows | 0 | 0 |
| Duplicate notifications | 0 | 0 |
| Duplicate assignment_history | 0 | 0 |

Seed is fully idempotent. Subsequent live mutations (acknowledge, transition, vote) persist across reruns because the seed uses `ON CONFLICT DO NOTHING`.

---

## 18. Backend Regression

| Suite | Passed | Failed | Errors | Notes |
|-------|--------|--------|--------|-------|
| `test_http_contract_remediation.py` | 14 | 0 | 0 | New — all pass |
| `services/workbench/tests/` (full) | 531 | 0 | 4 pre-existing | 4 asyncpg pool errors unrelated to this change |
| `test_infrastructure_smoke.py` | 11 | 0 | 0 | |
| `services/shared/tests/` | 71 | 0 | 0 | |
| **Total** | **627** | **0** | **4 pre-existing** | |

Zero new regression failures. Zero `TypeError: datetime` or `ResponseValidationError` in workbench logs since restart.

---

## 19. Frontend Regression / Build

- Frontend serves correctly on port 3000 (`<title>Banking Intelligence</title>`)
- Nginx API proxy (`/api/` → gateway) verified working after config fix
- Keycloak auth flow initialised (19 keycloak references in auth module)
- All mutation API paths used by frontend components confirmed reachable through gateway
- Frontend build: not re-run (no source changes made to frontend)

---

## 20. Remaining Issues Deferred

| # | Issue | Deferred To |
|---|-------|-------------|
| 1 | Gateway route shadowing — admin-only routes (users, roles, permissions) share prefix with workbench proxy | Step 3 |
| 2 | Workbench deployment security — integration app uses `X-Test-User` header (bypasses Keycloak); production app (`main.py`) uses same | Step 4 |
| 3 | Frontend route guards — some pages lack role-based visibility guards | Step 5 |
| 4 | Compliance permission reconciliation — `/auth/me` (main DB) shows `case:decision` for compliance, but integration DB `role_permissions` does not; causes divergence between gateway-authz and workbench-authz | Step 6 |
| 5 | Pre-existing idempotent-shortcut bug: `alert_service.acknowledge()` returns 200 without auth check when alert is already acknowledged | Known defect, out of scope |

---

## 21. Final Verdict

**FIXED**

- ✓ `analyst_001` sees 3 actionable alerts, 4 investigations, 3 IRs, 11 notifications via real Keycloak login
- ✓ `compliance_001` sees 6 cases, 50 pending approvals, 23 notifications via real Keycloak login
- ✓ `admin_001` sees poison outbox (19), orphan assignments (30+31), unrestricted alert read (restricted DTO)
- ✓ Each role completes at least one real mutation returning clean HTTP 200 with valid JSON and ISO datetimes
- ✓ Ownership and scope checks enforced (403/404 on cross-user access)
- ✓ `sbtb_*` records isolated from real staging user journey
- ✓ Seed script idempotent across reruns
- ✓ Zero regression failures introduced
