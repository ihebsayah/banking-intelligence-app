# Phase 2B.9 Closure Report — Comment + Timeline + Notification Endpoints

Date: 2026-07-31
Scope: Closure of 2B.9 (8 canonical endpoints: CM1–CM3, TL1–TL2, N1–N3) per
`.specs/increment-2/increment-2B-implementation-sequence.md` §2B.9 (line 173). The
full 2B.9 DoD is satisfied; this report is the mandated 26-section completion report.

## 1. Title & scope
2B.9 — Comment, Timeline, and Notification Endpoints (8 endpoints). All comment,
timeline, and notification endpoints are implemented, wired to the frozen
`shared/authorise.py` transition maps, and covered by unit + repo SQL tests. Workbench
routers remain standalone `APIRouter` modules (not mounted in the gateway), consistent
with the frozen architecture; tests exercise services/repos directly.

## 2. Documents followed
- `.specs/increment-2/increment-2B-implementation-sequence.md` — 2B.9 DoD (line 173).
- `.specs/increment-2/increment-2B-api-contracts.md` — CM1/CM2/CM3 (§§5–7), TL1/TL2 (§8), N1/N2/N3 (§9).
- `.specs/increment-2/increment-2B-authorisation-policies.md` — permission codes, role matrix, OLP.
- `.specs/increment-2/increment-2B-domain-model.md` + `increment-2B-domain-model.sql` — `comments`,
  `activity_timeline`, `notifications` table shapes.
- `.specs/increment-2/increment-2B-test-plan.md` — T30–T33 rows for comments/timeline.
- `.specs/increment-2/increment-2B-audit-outbox-design.md` — outbox payload envelope.

## 3. Migration decision
**No new migrations required.** The `comments`, `activity_timeline`, and `notifications`
tables already exist (migration `0004_add_operational_entities.py`) with the exact columns
the 2B.9 endpoints need (`comments.original_content_hash`, `redaction_reason`, `version`;
`activity_timeline.occurred_at`; `notifications.is_read`/`read_at`). No new tables, roles,
permissions, or workflow states were introduced. Permission codes `comment:create/read/
view_internal_content/view_metadata/redact`, `timeline:read`, `notification:read/update`
were seeded in `0005_add_permission_seeds.py` in earlier phases.

## 4. Baseline regression (pre-change)
`services/shared/tests` + `services/workbench/tests` → **324 passed, 1 skipped** in 2.21s
(the skip is the env-gated real-DB integration test, `INTEGRATION_DATABASE_URL` unset).
All 2B.9 work was additive on top of this green baseline.

## 5. Alignment findings (contract vs implementation)
- **CM1** returns the comment list; internal comments excluded at the query level for
  analysts (`include_internal=False` → `AND is_internal=FALSE`), content-view/metadata-view
  for compliance/admin per permission. Response shape `{total,page,page_size,items}` — matches
  contract's list convention used by TL1/N1.
- **CM2** does `INSERT comment + INSERT activity_timeline + INSERT audit_outbox` in one
  `UnitOfWork`, returns **201** with `X-Version` header (mirrors EC-style mutation responses).
- **CM3** `redact_reason` required (pydantic `min_length=1`); contract shows no
  `expected_version`, so it was added as an **optional optimistic-lock field** — consistent
  with the workbench versioning convention (409 `VERSION_CONFLICT` on stale). Content becomes
  `[REDACTED — {reason}]`; audit `comment.redacted` emitted.
- **TL1/TL2** are read-only (no UoW). Ordering (`occurred_at ASC`) is enforced in the repo SQL
  (`ORDER BY occurred_at` / `ORDER BY t.occurred_at ASC`).
- **N1** returns `unread_count` alongside `{data, ...}` items and total. **N2/N3** are
  mutations gated by `notification:update`.
- The one deviation is **response content**: `original_content_hash` is stored and audited but
  intentionally **not** exposed on `CommentResponse` (CM3's "Updated Comment" shape). See §13.

## 6. Files created
- `services/shared/tests/test_authorise_2b9.py` — transition-map tests (16).
- `services/workbench/services/entity_access.py` — shared polymorphic parent resolution
  (`ENTITY_TYPE_SEGMENTS`, `fetch_parent`, `_build_resource`, `assert_entity_readable`).
- `services/workbench/services/comment_service.py` — CM1/CM2/CM3.
- `services/workbench/services/timeline_service.py` — TL1/TL2.
- `services/workbench/services/notification_service.py` — N1/N2/N3.
- `services/workbench/schemas/comments.py` — `CreateCommentRequest`, `RedactCommentRequest`,
  `CommentResponse`, `CommentMetadataView`, `CommentListResponse`, `CommentMutationResponse`.
- `services/workbench/schemas/timeline.py` — `TimelineEntryResponse`, `TimelineListResponse`.
- `services/workbench/schemas/notifications.py` — `NotificationResponse`, `NotificationListResponse`
  (with `unread_count`), `NotificationMutationResponse`, `MarkAllReadResponse`.
- `services/workbench/routers/comments.py` (3 routes), `routers/timeline.py` (2 routes),
  `routers/notifications.py` (3 routes).
- `services/workbench/tests/test_comments.py` (29), `test_timeline.py` (7), `test_notifications.py` (11).

## 7. Files modified
- `services/shared/authorise.py` — added `COMMENT_ACTIONS`/`COMMENT_READ_ACTIONS` frozensets,
  unioned into `ALERT_TRANSITIONS`/`INVESTIGATION_TRANSITIONS`/`CASE_TRANSITIONS`/
  `IR_TRANSITIONS`; closed/cancelled case states exclude `comment:create` (blocks post-close
  comments) but allow `comment:read`/`comment:redact`; registered `NOTIFICATION_TRANSITIONS`
  (`unread`/`read` → `notification:read/update`) and `TIMELINE_TRANSITIONS` (`active` →
  `timeline:read`) in `ENTITY_TRANSITIONS`.
- `services/workbench/repos.py` — `CommentRepo.list_for_entity` (+`limit`/`offset`/
  `include_internal`), `CommentRepo.count_for_entity`; `TimelineRepo.list_for_entity`
  (+`event_type`/`limit`/`offset`), `TimelineRepo.count_for_entity`, `TimelineRepo.list_for_user`/
  `count_for_user` (module-level `_own_entity_timeline_sql` cross-entity OR group);
  `NotificationRepo.fetch_by_id`, `list_for_user` (signature change → `is_read`/`limit`/`offset`),
  `count_for_user`, `unread_count`, `mark_all_read` (`RETURNING` count).
- `services/workbench/tests/test_repos.py` — 9 new SQL-level tests (§22).

## 8. Endpoint matrix (8 canonical endpoints)
| # | Method & path | Service fn | Auth | Notes |
|---|---------------|------------|------|-------|
| CM1 | GET `/api/v1/{entity_type}/{entity_id}/comments` | `CommentService.list_for_entity` | `comment:read` + entity read | internal filtered per permission |
| CM2 | POST `/api/v1/{entity_type}/{entity_id}/comments` | `CommentService.create` | `comment:create` | 201, `X-Version`, comment+timeline+outbox |
| CM3 | PATCH `/api/v1/comments/{comment_id}/redact` | `CommentService.redact` | `comment:redact` (admin) | replaces content, audit `comment.redacted` |
| TL1 | GET `/api/v1/{entity_type}/{entity_id}/timeline` | `TimelineService.list_for_entity` | `timeline:read` + entity read | `occurred_at` ASC |
| TL2 | GET `/api/v1/timeline` | `TimelineService.list_for_user` | `timeline:read` | own entities only |
| N1 | GET `/api/v1/notifications` | `NotificationService.list` | `notification:read` | returns `unread_count` |
| N2 | PATCH `/api/v1/notifications/{id}/read` | `NotificationService.mark_read` | `notification:update` | ownership → 404 on foreign |
| N3 | PATCH `/api/v1/notifications/read-all` | `NotificationService.mark_all_read` | `notification:update` | returns `marked_read` count |

`entity_type` segment maps: `alerts→alert`, `investigations→investigation`,
`cases→compliance_case`, `information-requests→information_request` (400 `INVALID_ENTITY_TYPE`
otherwise).

## 9. Permission matrix
| Permission | analyst | compliance | admin | Used by |
|-----------|---------|-----------|-------|---------|
| `comment:read` | ✓ | ✓ | ✓ | CM1 |
| `comment:create` | ✓ | ✓ | — | CM2 (excluded on closed/cancelled cases) |
| `comment:view_internal_content` | — | ✓ | — | CM1 (full internal content) |
| `comment:view_metadata` | — | — | ✓ | CM1 (metadata-only view for internal) |
| `comment:redact` | — | — | ✓ (admin only) | CM3 |
| `timeline:read` | ✓ | ✓ | ✓ | TL1/TL2 |
| `notification:read` | ✓ | ✓ | ✓ | N1 |
| `notification:update` | ✓ | ✓ | ✓ | N2/N3 |

(Matches `0005_add_permission_seeds.py` role matrix.)

## 10. Ownership & object-leakage policy (OLP) matrix
- **Parent read gate (CM1/CM2/TL1):** `assert_entity_readable` tries assigned/own read
  (`alert:read_assigned`, `investigation:read_own`, `case:read_assigned`,
  `info_request:read_assigned`), then the broad read; both fail → **404 `NOT_FOUND`** so the
  entity appears nonexistent (leakage prevention). IR broad path additionally requires the user
  to be the IR creator or the owning case assignee (or admin).
- **Notification ownership (N2):** `fetch_by_id` then `n.user_id != user.user_id` → **404**.
- **CM3 redact:** parent must resolve; `comment:redact` is admin-only in the role matrix and in
  `authorise()` (compliance denied — `test_compliance_lacks_redact_permission`).
- **TL2:** scope is the caller's own user_id by construction; the synthetic
  `Resource(entity_type="timeline")` carries `timeline:read` only.

## 11. Comment immutability & optimistic versioning
Comments are append-only: **no edit/delete endpoints exist** (out of scope). The only mutation
is admin redaction, which preserves the row and bumps `version`. All create/redact mutations use
optimistic locking — stale `expected_version` raises 409 `VERSION_CONFLICT`; the redact path is a
versioned no-op if already redacted (idempotent, version unchanged).

## 12. Internal-comment visibility OLP (DoD: "compliance + admin only")
- **Analyst:** internal comments excluded at the **repo/query level** (`AND is_internal=FALSE`),
  so they never cross the service boundary.
- **Compliance** (`comment:view_internal_content`): full content.
- **Admin** (`comment:view_metadata`): internal comments return `CommentMetadataView` —
  existence metadata **without the content attribute** (mirrors the IR admin-view convention).
- Public comments are full-view for anyone with `comment:read`.

## 13. Redaction (CM3)
- `redact_reason` required (`min_length=1`).
- Content replaced with `[REDACTED — {reason}]`; `is_redacted=TRUE`, `redacted_at`/`redacted_by`
  set, `redaction_reason` stored, `version+1`, `updated_at` refreshed.
- `original_content_hash` (SHA-256 of pre-redaction content) is computed, **persisted**, and
  carried in the audit payload's `before.content_sha256` — the hash is verifiable without
  leaking content. It is deliberately **not exposed** on `CommentResponse` (CM3's response is
  simply the "Updated Comment").
- No timeline entry on redact (contract specifies only the audit event).

## 14. Notification ownership
Notifications carry no workflow status; the synthetic resource maps `is_read` onto the
registered `"unread"`/`"read"` states (`NOTIFICATION_TRANSITIONS`). N2 authorises with the
target notification's **actual** `is_read` (so `notification:update` is only exercised on
`unread`); foreign or missing notifications resolve to 404 before authorisation. `unread_count`
reflects the user's current unread total regardless of the `is_read` filter.

## 15. Timeline ordering (DoD: "ordered by occurred_at ASC")
Enforced in repo SQL and verified by SQL assertions: `list_for_entity` → `ORDER BY occurred_at`
(ASC default), `list_for_user` → `ORDER BY t.occurred_at ASC`. Service tests assert the ASC
serialisation contract; repo tests pin the SQL.

## 16. Pagination
Consistent across CM1, TL1, TL2, N1: `page` (ge=1) + `per_page` (ge=1, **le=100**), service cap
`min(per_page, 100)`, offset `(page-1)*limit`; responses carry `total`, `page`, `page_size`.
Repo signatures take `limit`/`offset`; SQL tests assert the appended `LIMIT $n OFFSET $m`.

## 17. System actor
No system-actor writes were needed: all 2B.9 side effects originate from a real authenticated
user (`actor_id`/`author_id` = caller, `actor_role` = caller's role). The `system_001` actor from
2B.8 remains for worker-initiated events (expiry) only; out of scope here.

## 18. Side effects
CM2 (create) in a single `UnitOfWork`: `INSERT comment` + `INSERT activity_timeline`
(`comment.created`, `new_value` carries `content_sha256` — never verbatim) + `INSERT
audit_outbox` (`comment.created`). CM3: `UPDATE comment` + `INSERT audit_outbox`
(`comment.redacted`). No notifications are emitted for comment/timeline actions (none in
contract). N2/N3: `UPDATE notifications` only. Rollback is atomic per UoW.

## 19. Idempotency
CM2/CM3 and N2/N3 accept optional `X-Idempotency-Key`: replay returns the stored response
(status + body); a matching key with a different body → 409 `IDEMPOTENCY_MISMATCH`. N2/N3
additionally treat already-read as a natural no-op (no UPDATE, same response). Covered by
`test_create_idempotent_replay`/`test_create_idempotency_mismatch`,
`test_redact_already_redacted_is_idempotent`, and the notification replay/mismatch tests.

## 20. Audit trail
All outbox events use the 2B.8 envelope `{schema_version, event_type, entity_type, entity_id,
actor_id, actor_role, occurred_at, request_id, before, after, metadata}`. `comment.created`
carries `before={}`, `after={content_sha256, is_internal, version}`; `comment.redacted` carries
`before={content_sha256, version}` and `after={is_redacted, version, redacted_by,
redaction_reason_sha256}` — original content and reason are never written verbatim.

## 21. Tests by category
- **Authorisation transition maps** (`shared/tests/test_authorise_2b9.py`, 16): comment create on
  open/active, 409 on closed/cancelled, read on closed/cancelled, redact admin-only across all 9
  case states, timeline/notification state homes, missing-permission rejections.
- **Comment endpoints** (`test_comments.py`, 29): entity-access helpers (8), CM1 list
  visibility/filtering (7), CM2 create + side effects + idempotency (8), CM3 redact (5), route
  registration (1).
- **Timeline endpoints** (`test_timeline.py`, 7): TL1 read gate + serialisation, filters,
  pagination, invalid entity type, 404 (4); TL2 synthetic-resource authorise + delegation (2);
  route registration (1).
- **Notification endpoints** (`test_notifications.py`, 11): N1 list + unread_count (2); N2
  ownership 404s, idempotent already-read, replay/mismatch (6); N3 mark-all count + mismatch (2);
  route registration (1).
- **Repo SQL level** (`test_repos.py`, 9 new): §22.

## 22. Repo SQL-level tests (DoD-critical query behaviours)
Internal-comment query filter (`AND is_internal=FALSE`, default off), `count_for_entity`,
`original_content_hash` in the redact UPDATE, timeline `ORDER BY occurred_at` (ASC) + event_type
filter, TL2 own-entities SQL (cross-entity OR group, `ORDER BY t.occurred_at ASC`,
entity-type/since filters), notification `is_read` filter + `created_at DESC`, `unread_count`
(`is_read=FALSE`), and `mark_all_read` (`RETURNING notification_id`, count returned).

## 23. Real-DB tests
The existing env-gated integration suite (`test_expiry_worker_integration.py`) still passes when
`INTEGRATION_DATABASE_URL` is set; it is not relevant to 2B.9's read paths but confirms the
migration chain (`alembic upgrade head`) is intact. `INTEGRATION_DATABASE_URL` is unset in this
environment, so the 1 skip remains. No new real-DB test was required — 2B.9 adds no migrations,
and repo SQL is pinned by the §22 assertions.

## 24. Regression counts
- Baseline before 2B.9: **324 passed, 1 skipped**.
- After 2B.9: **396 passed, 1 skipped** (2.20s). +72 tests, all green; the skip is the unchanged
  env-gated integration test.
- Router route-set assertions confirm exactly **8** new endpoints (3+2+3), no extras.

## 25. No weakened tests / no unapproved additions
- Every pre-existing test is unchanged in intent and still passes; nothing was skipped, marked
  xfail, or de-prioritised.
- No new migrations, roles, permissions, workflow states, tables, or routes beyond the 8 frozen
  endpoints. The only repo signature change (`NotificationRepo.list_for_user`) had zero pre-existing
  callers (verified by grep; `expiry_worker.py` does not touch it).
- Out of scope preserved: frontend, websocket/email/SMS, notification prefs/deletion, arbitrary
  timeline creation, comment edit/delete, mentions, attachments, evidence, remediation, reporting,
  AI summarization, search.

## 26. Remaining ambiguity, closure, next canonical task
- **Remaining ambiguity:** CM3's contract omits optimistic locking, so `expected_version` was added
  as an optional (backward-compatible) field consistent with workbench convention; the 
  `original_content_hash` exposure decision is documented in §13. Neither requires a spec change.
- **Closure:** 2B.9 is **closed**. All five DoD bullets (all 8 endpoints; internal-comment
  visibility compliance+admin only; admin-only redact replacing content + audit; `occurred_at` ASC;
  `unread_count` on GET) are implemented and test-verified.
- **Next canonical task:** **2B.10 — Admin Outbox Endpoints (2)**, depending on 2B.2, per
  `increment-2B-implementation-sequence.md` line 182.
