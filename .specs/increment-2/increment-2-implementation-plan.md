# Increment 2 — Implementation Plan

## Strategy
Backend-first (domain models + API), then DB schema, then frontend. AI integration last. No changes to existing agent internals.

## Phases

### Phase 1: DB Schema & Shared Models (3-4 days)
1. Create `init/03-operational-entities.sql` with all new tables
2. Add new Python models to `services/shared/models.py` (SQLAlchemy + Pydantic)
3. Add new enums to existing enum classes
4. Add new permissions to init SQL (`permissions` + `role_permissions`)
5. Extend `audit_logs` table with `entity_type`, `entity_id`, `action` columns

**Files touched:** `init/03-operational-entities.sql` (new), `services/shared/models.py` (edit), `services/shared/enums.py` (edit), `init/02-users-kpis.sql` (append permissions)

### Phase 2: Operational API Services (5-7 days)

Create `services/operational_service/` — new service for all operational endpoints.

Or add to `api_gateway` as new routers (simpler, fewer deployment units).

Decision: **Add to api_gateway** — fewer services = less operational overhead. New routers:

```
services/api_gateway/routes/alerts.py
services/api_gateway/routes/investigations.py
services/api_gateway/routes/cases.py
services/api_gateway/routes/evidence.py
services/api_gateway/routes/remediations.py
services/api_gateway/routes/watchlists.py
services/api_gateway/routes/tasks.py
services/api_gateway/routes/saved_analyses.py
services/api_gateway/routes/comments.py
services/api_gateway/routes/notifications.py
services/api_gateway/routes/timeline.py
```

Each router:
- CRUD + status transitions
- Permission checks via existing `require_permission`
- Audit logging on all mutations
- Notification creation on assignment/status changes
- Timeline entry creation on all state changes

**Sub-phases (parallel where possible):**
- 2a: Alerts + Investigations (2 days)
- 2b: Cases + Evidence + Decisions + Remediations (2 days)
- 2c: Watchlists (0.5 day)
- 2d: Tasks (0.5 day)
- 2e: Saved Analyses (0.5 day)
- 2f: Comments + Timeline + Notifications (1 day)

### Phase 3: Alert Engine (2-3 days)

Create `services/alert_engine/` — lightweight Python service:
- Scheduled tasks (APScheduler or cron via Docker)
- Polls KPI threshold tables (`kpi_thresholds` + `kpi_history`)
- Evaluates conditions
- Creates Alert records in DB
- Calls compliance_agent for severity assessment (optional)
- Creates Notification records

**ponytail:** Start with interval polling (every 60s). Move to event-driven when throughput demands it.

### Phase 4: AI Extensions (1-2 days)

1. Add `POST /api/v1/ai/investigation-suggestions` to `insights_agent`
   - Receives investigation context
   - Returns template-based suggestions (starter)
2. Add `POST /api/v1/ai/classify-evidence` to `compliance_agent`
   - Classifies document text by type and regulatory frameworks

### Phase 5: Frontend — Shared Components (2-3 days)

Build shared UI primitives first:
- Comment component (reused across all entity detail pages)
- Timeline component
- Entity Status Badge (color-coded by domain)
- Action Menu (dropdown of available transitions)
- Notification Bell + Dropdown
- Empty State component
- Slide-over Panel (for create/edit flows)

### Phase 6: Frontend — Analyst Workbench (4-5 days)

1. Alerts Inbox page + detail page
2. Investigations page + detail page
3. Investigation create flow (slide-over from alert)
4. Saved Analyses page + detail
5. Link AI Assistant "Save" button → Saved Analyses

### Phase 7: Frontend — Compliance Workbench (4-5 days)

1. Cases page + detail page (tabs: evidence, decisions, remediations, timeline, comments)
2. Evidence upload + list
3. Decision recording form
4. Remediation create/update/track
5. Watchlists page + detail + item management

### Phase 8: Frontend — Admin & Notifications (2-3 days)

1. All Tasks page (admin only — view/reassign/verify/delete all)
2. Alert Rules page (simple config view)
3. Notification center page + bell dropdown
4. Sidebar navigation updates
5. Route guards based on role + permissions

### Phase 9: Integration & Testing (3-4 days)

1. End-to-end workflows (alert→investigation→case→decision→remediation)
2. Permission boundary testing (role A cannot do role B's actions)
3. Notification delivery testing
4. Frontend state management integration
5. Error handling across all new pages
6. Backward compatibility — existing pages unchanged

## Total Estimate

| Phase | Days | Dependencies |
|-------|------|-------------|
| 1. DB + Models | 3-4 | None |
| 2. API Service | 5-7 | Phase 1 |
| 3. Alert Engine | 2-3 | Phase 2a |
| 4. AI Extensions | 1-2 | Phase 2b |
| 5. Frontend Shared | 2-3 | Phase 2 (API ready) |
| 6. Frontend Analyst | 4-5 | Phase 5 |
| 7. Frontend Compliance | 4-5 | Phase 5 |
| 8. Frontend Admin | 2-3 | Phase 5 |
| 9. Integration | 3-4 | Phases 6-8 |
| **Total** | **26-36 days** | |

## Parallelization
- Phase 1 → Phase 2 (sequential, DB must exist)
- Phase 2 → Phase 3 (sequential, API must exist for alert engine to write to)
- Phase 3 + 4 (parallel)
- Phase 5 + 2 (parallel — shared components while API is built)
- Phase 6 + 7 + 8 (parallel — different workbenches, independent)
- Phase 9 (must follow all frontend phases)

So **calendar time: ~4-5 weeks** with 1-2 devs.

## What NOT to Build (YAGNI)
- **No dashboard for alert/kpi rule builder UI** — config in DB directly
- **No real-time websockets** — polling for notifications is fine for this volume
- **No email/push notification delivery** — in-app notifications only
- **No bulk operations** (select-all, batch assign) — single-entity actions only
- **No report scheduling for saved analyses** — cron-based re-execution is enough
- **No ML model for alert severity** — rule-based + optional LLM call
- **No file storage service for evidence** — store file path in DB, serve via static or S3 later

## Rollout
1. Deploy DB migration first (Phase 1) — additive only, no backward incompatibility
2. Deploy API service (Phase 2) — new endpoints only, existing APIs unchanged
3. Deploy alert engine (Phase 3) — runs alongside existing services
4. Deploy AI extensions (Phase 4) — new endpoints on existing agents
5. Deploy frontend (Phases 5-8) — new routes + sidebar links, existing pages untouched
6. Integration testing in staging (Phase 9)
7. Production rollout — no downtime expected (additive changes only)
