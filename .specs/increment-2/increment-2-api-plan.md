# Increment 2 — API Plan

## Conventions
- Prefix: `/api/v1/`
- Auth: `Bearer <JWT>` + `Depends(get_current_user)` + `Depends(require_permission("domain:action"))`
- Response envelope: `{ "status": "success"|"error", "data": {...}, "pagination": {...} }`
- Pagination: `?page=1&per_page=20` → `{ page, per_page, total, total_pages }`
- All IDs: UUID format
- Timestamps: ISO 8601 UTC

---

## Alerts API

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/alerts` | `alert:read` | List all alerts (admin) |
| GET | `/alerts/assigned` | `alert:read_assigned` | List assigned alerts |
| GET | `/alerts/{id}` | `alert:read_assigned` | Get alert detail |
| PATCH | `/alerts/{id}/acknowledge` | `alert:acknowledge` | Acknowledge alert |
| PATCH | `/alerts/{id}/dismiss` | `alert:dismiss` | Dismiss with note |
| PATCH | `/alerts/{id}/investigate` | `alert:escalate` | Create investigation from alert |
| PATCH | `/alerts/{id}/escalate` | `alert:escalate` | Escalate to case |

**Query params for list:** `?status=triggered&severity=high&type=transaction_anomaly&assigned_to=<uuid>`

---

## Investigations API

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/investigations` | `investigation:read` | List all (admin) |
| GET | `/investigations/assigned` | `investigation:read_own` | List own investigations |
| GET | `/investigations/{id}` | `investigation:read_own` | Get detail (with timeline, comments) |
| POST | `/investigations` | `investigation:create` | Create (optionally from alert) |
| PATCH | `/investigations/{id}` | `investigation:update` | Update findings, conclusion |
| PATCH | `/investigations/{id}/status` | `investigation:transition` | Change status |
| PATCH | `/investigations/{id}/assign` | `investigation:assign` | Reassign |
| DELETE | `/investigations/{id}` | `investigation:delete` | Delete |

**Body for create:** `{ title, description, alert_id?, priority }`

---

## Compliance Cases API

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/cases` | `case:read` | List all (admin) |
| GET | `/cases/assigned` | `case:read_assigned` | List assigned cases |
| GET | `/cases/{id}` | `case:read_assigned` | Get detail (with evidence, decisions, timeline) |
| POST | `/cases` | `case:create` | Create (manually or from escalation) |
| PATCH | `/cases/{id}` | `case:update` | Update details |
| PATCH | `/cases/{id}/status` | `case:transition` | Change status |
| PATCH | `/cases/{id}/assign` | `case:assign` | Reassign |
| PATCH | `/cases/{id}/escalate` | `case:escalate` | Escalate |
| PATCH | `/cases/{id}/close` | `case:close` | Close with resolution |
| DELETE | `/cases/{id}` | `case:delete` | Delete |

---

## Decisions API

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/cases/{case_id}/decisions` | `case:decision` | Record decision |
| GET | `/cases/{case_id}/decisions` | `case:read_assigned` | List decisions on case |

---

## Evidence API

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/cases/{case_id}/evidence` | `evidence:create` | Upload evidence |
| GET | `/cases/{case_id}/evidence` | `evidence:read` | List evidence for case |
| GET | `/evidence/{id}` | `evidence:read` | Download / view |
| DELETE | `/evidence/{id}` | `evidence:delete` | Delete |

---

## Remediation Actions API

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/cases/{case_id}/remediations` | `remediation:create` | Create |
| GET | `/cases/{case_id}/remediations` | `remediation:read` | List |
| PATCH | `/remediations/{id}` | `remediation:update` | Update |
| PATCH | `/remediations/{id}/verify` | `remediation:verify` | Verify completion |
| DELETE | `/remediations/{id}` | `remediation:delete` | Delete |

---

## Watchlists API

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/watchlists` | `watchlist:read` | List |
| POST | `/watchlists` | `watchlist:create` | Create |
| GET | `/watchlists/{id}` | `watchlist:read` | Get with items |
| PATCH | `/watchlists/{id}` | `watchlist:update` | Update |
| DELETE | `/watchlists/{id}` | `watchlist:delete` | Delete |
| POST | `/watchlists/{id}/items` | `watchlist:add_item` | Add item |
| DELETE | `/watchlists/{id}/items/{item_id}` | `watchlist:remove_item` | Remove item |

---

## Tasks API

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/tasks` | `task:read` | List all (admin) |
| GET | `/tasks/assigned` | `task:read_assigned` | List assigned tasks |
| GET | `/tasks/{id}` | `task:read_assigned` | Get detail |
| POST | `/tasks` | `task:create` | Create (linked to entity) |
| PATCH | `/tasks/{id}` | `task:update` | Update |
| PATCH | `/tasks/{id}/status` | `task:transition` | Change status |
| PATCH | `/tasks/{id}/verify` | `task:verify` | Verify completion |
| PATCH | `/tasks/{id}/assign` | `task:assign` | Reassign |
| DELETE | `/tasks/{id}` | `task:delete` | Delete |

---

## Saved Analysis API

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/saved-analyses` | `saved_analysis:read_own` | List own |
| GET | `/saved-analyses/all` | `saved_analysis:read` | List all (admin) |
| POST | `/saved-analyses` | `saved_analysis:create` | Save current query |
| GET | `/saved-analyses/{id}` | `saved_analysis:read_own` | Get detail |
| PATCH | `/saved-analyses/{id}` | `saved_analysis:update` | Update |
| DELETE | `/saved-analyses/{id}` | `saved_analysis:delete` | Delete |
| PATCH | `/saved-analyses/{id}/share` | `saved_analysis:share` | Toggle sharing |
| PATCH | `/saved-analyses/{id}/schedule` | `saved_analysis:schedule` | Set cron schedule |

---

## Comments API (polymorphic)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/{entity_type}/{entity_id}/comments` | `comment:read` | List |
| POST | `/{entity_type}/{entity_id}/comments` | `comment:create` | Add |
| DELETE | `/comments/{id}` | `comment:delete` | Delete |

**entity_type:** alerts, investigations, cases, tasks, evidence, remediations

---

## Notifications API

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/notifications` | `notification:read` | List own notifications |
| GET | `/notifications/unread-count` | `notification:read` | Get unread count |
| PATCH | `/notifications/{id}/read` | `notification:update` | Mark as read |
| PATCH | `/notifications/read-all` | `notification:update` | Mark all as read |

---

## Timeline API (polymorphic)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/{entity_type}/{entity_id}/timeline` | `timeline:read` | List timeline |

---

## AI Extension API (new routes on existing agents)

| Method | Path | Service | Description |
|--------|------|---------|-------------|
| POST | `/ai/investigation-suggestions` | insights_agent | Get AI suggestions for investigation |
| POST | `/ai/classify-evidence` | compliance_agent | Classify evidence document |

## Notes
- All list endpoints support `?page=1&per_page=20&sort_by=created_at&sort_order=desc`
- All filterable fields use query params: `?status=x&priority=y&assigned_to=z`
- Polymorphic entity endpoints (`/comments`, `/timeline`) are mounted at the entity router level, not as standalone — e.g., `/investigations/{id}/comments`
- No websockets for Inc 2 — polling for notification count is fine
- 42 new endpoints total across all resources
