# Increment 2A — Foundation Specification

Phase 2A delivers zero user-visible features. It delivers the substrate Phase 2B requires: schema, tooling, policy engine, permission seeds, and audit infrastructure.

---

## Scope

| Deliverable | Detail |
|-------------|--------|
| Alembic baseline | Snapshot existing deployed schema, stamp without re-running DDL |
| Audit outbox schema | New table in `postgres-main`; worker design |
| Operational entity DDL | All Phase 2B tables, additive only |
| Organisational scope | `organisation_scopes` and `user_scopes` tables |
| Permission seed | All Inc 2 permission codes inserted into `permissions` + `role_permissions` |
| Policy engine | `authorise()` function module, no HTTP, no framework |
| Frontend gate | `PermissionGate` component, `usePermissions` hook |
| Legacy manager migration | Mark `manager` role deprecated, zero new permissions |

---

## 1. Migration Baseline Procedure

### Decision

The project uses raw SQL init-scripts executed by `apply_migrations()` in `main.py` on every container restart. This is not versioned. Alembic replaces it for Phase 2B onward. Init-scripts are retained only for fresh local environments and are not executed against seeded databases.

### Environments

**Fresh environment (CI, dev, first install)**
```
docker-compose up → init scripts run via IF NOT EXISTS → app starts
alembic upgrade head  (runs baseline + 2A + 2B migrations atop empty schema)
```
> The baseline migration contains `CREATE TABLE IF NOT EXISTS` stanzas copied from init scripts verbatim. Running them on an empty schema is safe.

**Existing environment (staging, production)**
```
Step 1: Full database backup
        pg_dump -Fc -f backup-pre-2A-$(date +%Y%m%d).dump banking_dev

Step 2: Deploy Alembic config and migration files only — DO NOT run upgrade yet

Step 3: On staging:
        alembic stamp <baseline_revision_id>
        (records current schema as already applied — executes NO DDL)

Step 4: Run schema compatibility check script (see §1.3)

Step 5: alembic upgrade head
        (applies only 0002–0006 migrations, not the baseline)

Step 6: Deploy new application code

Step 7: Smoke test — run verification query set (see §1.4)
```

> **CRITICAL:** `alembic stamp` does NOT execute any DDL. It only writes a row to `alembic_version`. The baseline revision upgrade() must be wrapped so it is a no-op if tables already exist (uses IF NOT EXISTS throughout).

### 1.2 Migration File Layout

```
migrations/
  env.py
  script.py.mako
  versions/
    0001_baseline_existing_schema.py        # Rev a1b2c3d4 — stamp-only on existing envs
    0002_add_organisation_scope.py          # Phase 2A
    0003_add_audit_outbox.py                # Phase 2A
    0004_add_operational_entities.py        # Phase 2A
    0005_add_permission_seeds.py            # Phase 2A data migration
    0006_deprecate_manager_role.py          # Phase 2A data migration
```

Each revision:
- Has `down_revision` set correctly
- Has a working `downgrade()` unless destructive (data migrations annotate non-reversible steps)
- Is additive only (no DROP COLUMN, no RENAME, no destructive ALTER)

### 1.3 Compatibility Check Script

```sql
-- Run before alembic upgrade on existing environments.
-- Must return 0 rows for each query.

-- Required columns present on users
SELECT COUNT(*) FROM information_schema.columns
WHERE table_name='users'
  AND column_name IN ('user_id','email','role','status','bank_id')
HAVING COUNT(*) < 5;

-- No unexpected roles
SELECT COUNT(*) FROM roles WHERE role_id NOT IN ('analyst','compliance','admin','manager');

-- No naming conflicts with new tables
SELECT table_name FROM information_schema.tables
WHERE table_schema='public'
  AND table_name IN (
    'alerts','investigations','compliance_cases','decisions',
    'information_requests','approval_requests','approval_decisions',
    'comments','activity_timeline','notifications','audit_outbox',
    'organisation_scopes','user_scopes','assignment_history'
  );
-- Expected: 0 rows
```

### 1.4 Post-Migration Verification

```sql
-- All new tables created (expected: 14)
SELECT COUNT(*) FROM information_schema.tables
WHERE table_schema='public'
  AND table_name IN (
    'alerts','investigations','compliance_cases','decisions',
    'information_requests','approval_requests','approval_decisions',
    'comments','activity_timeline','notifications','audit_outbox',
    'organisation_scopes','user_scopes','assignment_history'
  );

-- Alembic on latest revision
SELECT version_num FROM alembic_version;

-- Permission seeds present
SELECT COUNT(*) FROM permissions WHERE permission_key LIKE 'alert:%';
-- Expected: >= 8

-- Manager marked deprecated
SELECT description FROM roles WHERE role_id = 'manager';
-- Expected: contains string 'DEPRECATED'
```

### 1.5 Rollback

Phase 2A migrations are purely additive. Application rollback = revert code. If DB rollback needed:
```bash
alembic downgrade -1   # one step at a time, newest first
```
Downgrade functions drop only Phase 2A tables (no production data in them at rollback time).

---

## 2. Legacy Manager Role Migration

```sql
-- 0006_deprecate_manager_role upgrade()
UPDATE roles
SET description = 'DEPRECATED — Legacy role. Zero Inc 2 capabilities. Admin must reassign.'
WHERE role_id = 'manager';

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS legacy_role BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE users SET legacy_role = TRUE WHERE role = 'manager';
-- No new role_permissions rows for 'manager'.
-- Existing read:branch_data, read:risk_summary retained for backward compat.
-- workbench:access not granted -> manager gets 403 on all Inc 2 routes.

-- downgrade()
UPDATE roles SET description = 'Branch Manager / Executive' WHERE role_id = 'manager';
ALTER TABLE users DROP COLUMN IF EXISTS legacy_role;
```

---

## 3. Organisational Scope Schema

```sql
-- 0002_add_organisation_scope.py upgrade()

CREATE TABLE organisation_scopes (
    scope_id        VARCHAR(100) PRIMARY KEY,
    scope_type      VARCHAR(30) NOT NULL
                    CHECK (scope_type IN ('bank','region','branch','department')),
    label           VARCHAR(255) NOT NULL,
    parent_scope_id VARCHAR(100) REFERENCES organisation_scopes(scope_id),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO organisation_scopes (scope_id, scope_type, label) VALUES
    ('hq_main', 'bank', 'Headquarters — Main'),
    ('global',  'bank', 'Global — Admin metadata view')
ON CONFLICT DO NOTHING;

CREATE TABLE user_scopes (
    user_id     VARCHAR(100) NOT NULL REFERENCES users(user_id),
    scope_id    VARCHAR(100) NOT NULL REFERENCES organisation_scopes(scope_id),
    granted_by  VARCHAR(100) NOT NULL REFERENCES users(user_id),
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, scope_id)
);

CREATE INDEX idx_user_scopes_user  ON user_scopes(user_id);
CREATE INDEX idx_user_scopes_scope ON user_scopes(scope_id);
```

**Scope rules:**
- Every user has >= 1 scope assigned by admin at account creation.
- `global` scope grants Admin read of case metadata (title, status, assigned_to) but NOT case content (findings, decisions, rationale).
- Alerts, investigations, cases inherit scope from creator's primary `bank_id`; override allowed at creation time.
- Cross-scope cases: allowed; compliance officer must hold at least one of the case's scopes; admin assigns.
- Scope changes after creation: admin-only; creates `assignment_history` entry + audit outbox event.
- Reassignment across scopes: target user must hold the target scope.

---

## 4. Audit Outbox Schema (summary — full design in increment-2B-audit-outbox-design.md)

```sql
-- 0003_add_audit_outbox.py upgrade()

CREATE TYPE audit_outbox_status AS ENUM (
    'pending', 'delivering', 'delivered', 'failed', 'poison'
);

CREATE TABLE audit_outbox (
    outbox_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key     VARCHAR(255) NOT NULL UNIQUE,
    -- Format: {event_type}:{entity_id}:{actor_id}:{occurred_at_unix_ms}
    event_type          VARCHAR(100) NOT NULL,
    entity_type         VARCHAR(50)  NOT NULL,
    entity_id           UUID         NOT NULL,
    actor_id            VARCHAR(100) NOT NULL,
    actor_role          VARCHAR(50)  NOT NULL,
    occurred_at         TIMESTAMPTZ  NOT NULL,
    payload             JSONB        NOT NULL,
    payload_schema_ver  SMALLINT     NOT NULL DEFAULT 1,
    status              audit_outbox_status NOT NULL DEFAULT 'pending',
    attempt_count       SMALLINT     NOT NULL DEFAULT 0,
    last_attempt_at     TIMESTAMPTZ,
    last_error          TEXT,
    locked_by           VARCHAR(100),   -- worker instance id
    locked_at           TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    poison_reason       TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_outbox_pending
    ON audit_outbox(status, created_at)
    WHERE status IN ('pending','failed');

CREATE UNIQUE INDEX idx_audit_outbox_idem
    ON audit_outbox(idempotency_key);

-- downgrade()
DROP TABLE IF EXISTS audit_outbox;
DROP TYPE  IF EXISTS audit_outbox_status;
```

---

## 5. Operational Entity DDL (outline — full DDL in increment-2B-domain-model.sql)

Migration `0004_add_operational_entities.py` creates in dependency order:

1. `activity_timeline`
2. `notifications`
3. `alerts`
4. `investigations`
5. `compliance_cases`
6. `decisions`
7. `information_requests`
8. `approval_requests`
9. `approval_decisions`
10. `comments`
11. `assignment_history`

All additive. No foreign key cascades to DROP or SET NULL on regulated records (uses RESTRICT or deferred).

---

## 6. Permission Seed Migration

`0005_add_permission_seeds.py` — data migration.

Inserts all permission codes into `permissions` table and maps them in `role_permissions` per the matrix in increment-2B-authorisation-policies.md. Downgrade deletes them.

---

## 7. Policy Engine Module

Module location: `services/shared/authorise.py`

```python
async def authorise(
    user: ApplicationUser,
    action: str,            # permission code
    resource: dict,         # {id, status, assigned_to, scope_id, version, ...}
    db: DatabaseConnector,
    request_context: dict,  # {request_id, ip_address, override_id?}
) -> None:
    # Raises HTTPException on deny.
    # Returns None on allow.
    # All allow paths emit to audit outbox inside same tx if called within tx context.
```

Evaluation order — no exceptions, no shortcuts:

| Step | Check | Deny code |
|------|-------|-----------|
| 1 | `action` is known permission code | 400 |
| 2 | `(user.role, action)` not in PROHIBITED | 403 |
| 3 | `action` in `user.permissions` (from role + overrides) | 403 |
| 4 | User scope intersects resource scope (or global + metadata-only action) | 404 |
| 5 | Ownership check if `_own`/`_assigned` permission | 404 |
| 6 | Workflow state permits action | 409 / 400 |
| 7 | Conflict-of-interest check | 403 |
| 8 | Approval prerequisite satisfied | 428 |
| 9 | Emergency override active for action (if overrideable action) | — (allow + mark exercised) |
| 10 | Default deny | 403 |

**Prohibited combos (hardcoded):**
```python
PROHIBITED: set[tuple[str, str]] = {
    ('admin',    'case:decision'),
    ('admin',    'case:close'),
    ('admin',    'remediation:verify'),
    ('admin',    'investigation:modify_findings'),
    ('admin',    'evidence:destroy'),
    ('admin',    'regulatory:approve'),
    ('analyst',  'case:decision'),
    ('analyst',  'case:close'),
    ('analyst',  'case:assign'),
    ('analyst',  'approval:approve'),
    ('manager',  'workbench:access'),  # legacy role
}
```

No `admin:*` bypass exists. Emergency override is a named, time-limited, single-use, logged exception.

---

## 8. Frontend Permission Gate

```typescript
// frontend/src/lib/permissions.ts
// Single source of truth for permission codes used in UI gates.
// Server is the actual enforcer — this prevents unnecessary round-trips only.

export type Permission = string; // constrained by union in full type file

export function usePermissions() {
  const { user } = useAuth();
  return {
    hasPermission: (p: Permission): boolean =>
      user?.permissions?.includes(p) ?? false,
    hasAnyPermission: (ps: Permission[]): boolean =>
      ps.some(p => user?.permissions?.includes(p) ?? false),
  };
}
```

```tsx
// frontend/src/components/PermissionGate.tsx
export function PermissionGate({
  requires,
  requireAll = false,
  fallback = null,
  children,
}: {
  requires: Permission | Permission[];
  requireAll?: boolean;
  fallback?: ReactNode;
  children: ReactNode;
}) {
  const { hasPermission, hasAnyPermission } = usePermissions();
  const ps = Array.isArray(requires) ? requires : [requires];
  const ok = requireAll ? ps.every(hasPermission) : hasAnyPermission(ps);
  return ok ? <>{children}</> : <>{fallback}</>;
}
```

---

## 9. Init Script Retirement Plan

| Stage | Action |
|-------|--------|
| Phase 2A shipped | Alembic added; init scripts kept for fresh-env docker-compose only |
| After 2B on staging | Remove `apply_migrations()` from `main.py`; add startup check that alembic_version = current head |
| After all envs on Alembic | Move init SQL to `init/legacy/`; update README |

---

## 10. Phase 2A Checklist

- [ ] `alembic.ini` + `migrations/env.py` configured for `postgres-main`
- [ ] `0001_baseline_existing_schema.py` stamped on existing, safe on fresh
- [ ] `0002_add_organisation_scope.py` DDL + hq_main seed
- [ ] `0003_add_audit_outbox.py` DDL + enum
- [ ] `0004_add_operational_entities.py` 11 new tables
- [ ] `0005_add_permission_seeds.py` permissions + role_permissions data
- [ ] `0006_deprecate_manager_role.py` data update + legacy_role column
- [ ] `services/shared/authorise.py` policy engine + unit tests for all prohibited combos
- [ ] `frontend/src/lib/permissions.ts` type-safe permission set
- [ ] `frontend/src/components/PermissionGate.tsx` gate component
- [ ] Compatibility check script passes on staging
- [ ] Post-migration verification passes

**2A complete when:** `alembic upgrade head` runs cleanly on both fresh and stamped-existing environments; all 14 tables exist; policy engine passes unit tests; manager users get 403 on workbench:access.
