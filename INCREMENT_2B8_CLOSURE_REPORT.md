# Phase 2B.8 Closure Report — Approval Expiry Worker (AP5) + System-Actor Resolution

Date: 2026-07-31
Scope: Closure of 2B.8 (approval workflow + expiry worker) per
`.specs/increment-2/increment-2B-implementation-sequence.md` (expiry worker at line 169,
inside the 2B.8 DoD).

## 1. System-actor resolution (the 2B.8 blocker)

### Authoritative review
- `activity_timeline.actor_id` is `VARCHAR(100) NOT NULL REFERENCES users(user_id)`
  (migration `0004` line 35; `.specs/increment-2/increment-2B-domain-model.sql` line 23).
- `audit_outbox.actor_id` is `VARCHAR(100) NOT NULL`, **no FK** — free-form.
- A grep of every `.specs/**` document found **no canonical system actor, service
  account, or worker-id-as-user model** anywhere in the frozen design. The AP5 spec
  (`increment-2B-state-machines.md`, "Actor=Worker, Perm=(system)") never defined a
  persistence model for the system actor — that was the architecture gap blocking 2B.8.

### Resolution (documented, forward migration)
A deterministic seeded system user via forward migration `0008_add_system_actor.py`,
so the timeline FK resolves and the audit trail is honest:

| field | value | rationale |
|---|---|---|
| `user_id` | `system_001` | follows the project's seeded `<role>_NNN` convention |
| `email` | `system_001@bankintel.hq` | reserved, unique (same convention) |
| `name` | `System Actor` | |
| `role` | `system` (new role, zero permissions) | AP5 "Perm=(system)"; worker is not an admin |
| `status` | `inactive` | login rejected at `services/api_gateway/auth.py:218` before any session |
| `identity_provider` | `system` | never issued by Keycloak; non-login marker |
| `bank_id` | `hq_main` | default |
| `password_hash` | same dummy bcrypt hash as other dev seeds | consistent; status blocks login |

- **No** `user_scopes` row (worker never checks scopes).
- `audit_outbox.actor_id` stays free-form but now records the same stable `system_001`
  (the canonical representation) so timeline and audit identities match.
- `downgrade()` deletes timeline rows by the actor first (only FK dependency), then the
  user, then the role; it is fully reversible and re-upgradable (verified).

## 2. Schema / seed changes

- `migrations/versions/0008_add_system_actor.py` (new): seeds role `system` + user
  `system_001`, idempotent (`ON CONFLICT DO NOTHING`).
- `migrations/versions/0004_add_operational_entities.py`: on any DB where the legacy
  Inc 1 `compliance_cases` exists, rename it to `legacy_compliance_cases` before
  creating the Phase 2B table. The legacy table has no column-level consumers (only
  table-name allowlists in the Inc 1 SQL agents); `compliance_reviews`' FK follows the
  rename. Idempotent (guarded on the absence of `case_id`).
- `migrations/versions/0005_add_permission_seeds.py`: seeds the four base roles
  (analyst/manager/compliance/admin) on the empty-DB chain so the `role_permissions`
  FK resolves; no-op (`ON CONFLICT`) on the stamped path.
- `migrations/env.py`: `os.path.expandvars` on the resolved `sqlalchemy.url` — alembic's
  `Config` does not expand `${DATABASE_URL}` from the environment, so `alembic upgrade`
  failed out of the box. **This was a latent defect; the migration chain had never
  actually been executed.**
- `services/shared/database.py`: per-connection type codecs (`uuid`→str, `jsonb`→dict)
  matching the pydantic model contract. Real asyncpg returns UUID objects / jsonb
  strings; every workbench model is str/dict-typed, so the workbench repo layer could
  not run against a real database without this.

## 3. Stable actor ID

`SYSTEM_ACTOR_ID = "system_001"`, `SYSTEM_ACTOR_ROLE = "system"` in
`services/workbench/expiry_worker.py`, used for the timeline `actor_id`, the outbox
`actor_id`/`actor_role`, and the audit payload. Single source of truth in code;
the seed lives in the migration.

## 4. Worker behaviour (unchanged contract, now real-DB-safe)

- `ApprovalRepo.expire_due(batch_size, conn)`: atomic `UPDATE ... WHERE id IN
  (SELECT ... FOR UPDATE SKIP LOCKED) RETURNING *`, status `pending→expired`,
  `version+1`, `updated_at` (AP5).
- One `UnitOfWork` per batch: status + timeline `approval_expired` + notification
  `approval_expired` → requester + outbox `approval.expired` commit together; any
  failure rolls back the whole batch.
- Loop: 60s interval (`APPROVAL_EXPIRY_INTERVAL_SECONDS`), batch 50
  (`APPROVAL_EXPIRY_BATCH_SIZE`); failure logs and continues.

## 5. Evidence (real PostgreSQL, container `banking_postgres_main`)

- **DoD line 16 — empty DB:** `alembic upgrade head` on a fresh DB runs cleanly through
  all revisions `a1b2c3d4e5f6 → 0008`.
- **DoD line 22/23 — seeded staging DB:** init SQL exactly as built by
  `docker-compose` (all 10 init scripts) → `alembic stamp a1b2c3d4e5f6` → `upgrade head`
  runs 0002–0008 cleanly; legacy `compliance_cases` renamed, Phase 2B tables created,
  all 6 pre-existing users untouched.
- **DoD line 15 — history:** `alembic history` runs without error (8 revisions).
- **Downgrade:** `alembic downgrade 0007` removes the system user/role + its timeline
  rows; re-`upgrade` re-seeds.
- **End-to-end worker (real DB):** overdue-pending approval → `expired v2` (single
  version bump); pending-future, approved, rejected, already-expired untouched; exactly
  one timeline/notification/outbox side-effect row each with `actor_id=system_001`
  (FK resolves against the seeded user); second run claims nothing (idempotent).
- **Codified** as `services/workbench/tests/test_expiry_worker_integration.py`:
  auto-skips unless `INTEGRATION_DATABASE_URL` is set; run via
  `INTEGRATION_DATABASE_URL=postgresql://... python3 -m pytest workbench/tests/test_expiry_worker_integration.py -q` → 1 passed.

## 6. Test counts

- Unit regression: `shared/tests workbench/tests` → **324 passed, 1 skipped**
  (313 baseline + 11 new worker tests; the skip is the env-gated integration test).
- Extended sweep including `intent_agent/tests` (exercises shared/database.py):
  **344 passed, 1 skipped**.

## 7. Phase 2B.8 closure

The expiry worker (AP5) is complete and verified against the real PostgreSQL schema:
state machine behaviour, system-actor FK, atomic side effects, idempotency, and both
`alembic` upgrade paths (empty + stamped). 2B.8 can be marked closed; the dependency
list for 2B.9 is now unblocked.
