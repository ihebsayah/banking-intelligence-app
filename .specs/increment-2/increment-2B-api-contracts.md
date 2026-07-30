# Increment 2B — API Contracts

Total endpoints: **44**

All paths prefixed `/api/v1`. All responses use envelope:
```json
{ "status": "success", "data": { ... }, "pagination": { ... } }
```

Errors:
```json
{ "status": "error", "error": "ERROR_CODE", "message": "human-readable" }
```

Standard error codes:
- 400 — malformed request or invalid state transition
- 401 — unauthenticated
- 403 — authenticated but forbidden (role/permission/SoD)
- 404 — not found or inaccessible (leakage prevention)
- 409 — stale version (optimistic concurrency) or conflicting state
- 422 — schema validation failure
- 428 — approval required (missing ApprovalRequest)

`expected_version` required on all mutation requests that use optimistic locking. Missing = 422.
Two separate idempotency mechanisms: (1) API idempotency via `X-Idempotency-Key` stored in `idempotency_cache` (24h TTL); (2) Audit outbox uses own deterministic key — see §0 below.

---

## 0. Idempotency Design

Two separate idempotency mechanisms:

### API Idempotency (client-facing)
- Client provides `X-Idempotency-Key: <uuid>` header on mutation requests (optional).
- Backend stores `(key, user_id, route, response_body)` in `idempotency_cache` table.
- Cache key normalized: lowercase method + path + sorted request body SHA256.
- Same key + same normalized body → return stored response (200, not 201 for creates).
- Same key + different body → 409 Conflict ("idempotency_key_mismatch").
- Keys expire after 24 hours (TTL column; cleanup worker runs hourly).
- Scope: per-user, per-route. Different users with same key do not collide.
- **Not** stored in audit_outbox — that is a separate concern (see below).

### Audit Outbox Idempotency (internal)
- The audit outbox generates its own deterministic `idempotency_key = f"{event_type}:{entity_type}:{entity_id}:{occurred_at_epoch}"`.
- `audit_outbox.idempotency_key` UNIQUE index prevents duplicate delivery to audit store.
- This is NOT the same header as the client-facing `X-Idempotency-Key`.
- See `increment-2B-audit-outbox-design.md` for details.

---

## 1. ALERTS (7 endpoints)

### A1 — GET /alerts/assigned
List alerts assigned to current user.

| Field | Value |
|-------|-------|
| Permission | `alert:read_assigned` |
| OLP | assigned_to == user.id (scope check implicit) |
| Query params | `status`, `severity`, `page` (default 1), `per_page` (default 20, max 100) |
| Response | `{ data: Alert[], pagination }` |
| Errors | 401, 403 |
| Transaction | Read only |
| Timeline | None |
| Audit | None (read) |

Alert response shape:
```json
{
  "alert_id": "uuid",
  "alert_type": "transaction_anomaly",
  "severity": "high",
  "title": "string",
  "description": "string",
  "status": "assigned",
  "assigned_to": "user_id",
  "scope_id": "hq_main",
  "version": 3,
  "created_at": "iso8601",
  "updated_at": "iso8601"
}
```

---

### A2 — GET /alerts/{alert_id}
Alert detail.

| Field | Value |
|-------|-------|
| Permission | `alert:read_assigned` (own) or `alert:read` (admin) |
| OLP | Own scope; admin global scope = metadata only (strips description) |
| Errors | 401, 403, 404 |

---

### A3 — PATCH /alerts/{alert_id}/assign
Assign alert to analyst or compliance user (admin only).

| Field | Value |
|-------|-------|
| Permission | `alert:assign` (admin only) |
| OLP | Admin only |
| Request | `{ "assigned_to": "user_id", "expected_version": int, "reason": "string?" }` |
| Response | Updated Alert |
| Errors | 400, 401, 403, 404, 409 |
| Preconditions | Target user `status = 'active'`; target user has scope access; target user has `info_request:respond` (if analyst role) or `case:read_assigned` (if compliance role) |
| Transaction | UPDATE alerts (assigned_to=target, status→assigned if status=new, version+=1 WHERE version=expected_version) + INSERT assignment_history + INSERT activity_timeline + INSERT notifications + INSERT audit_outbox |
| Timeline | `alert.assigned` |
| Notification | `alert_assigned` → new assignee |
| Audit | `alert.assigned` |
| Idempotency | No-op if already assigned to same user (compare assigned_to and status) |
| Conflict | version mismatch → 409 |

---

### A4 — PATCH /alerts/{alert_id}/acknowledge
Acknowledge assigned alert.

| Field | Value |
|-------|-------|
| Permission | `alert:acknowledge` |
| OLP | `assigned_to == user.id` |
| Request | `{ "expected_version": int }` |
| Response | Updated Alert |
| Errors | 400, 401, 403, 404, 409 |
| Transaction | UPDATE alerts + INSERT activity_timeline + INSERT audit_outbox |
| Timeline event | `alert.acknowledged` |
| Notification | None |
| Audit event | `alert.acknowledged` |
| State | assigned → acknowledged |
| Idempotency | If already acknowledged → 200 (no-op, return current state) |
| Conflict | version mismatch → 409 |

---

### A5 — PATCH /alerts/{alert_id}/dismiss
Dismiss alert (requires approval if critical/high).

| Field | Value |
|-------|-------|
| Permission | `alert:dismiss` |
| OLP | `assigned_to == user.id` OR admin with active override (Phase 2H) |
| Request | `{ "dismissed_reason": "string (required)", "expected_version": int, "approval_request_id": "uuid (required if critical/high)" }` |
| Step 8 check | If severity IN (critical, high): ApprovalRequest must exist, status=approved, executed_at=null |
| Response | Updated Alert |
| Errors | 400, 401, 403, 404, 409, 428 |
| Transaction | UPDATE alerts (status=dismissed, dismissed_reason, dismissed_at, dismissed_by, dismissal_approval_id) + INSERT activity_timeline + INSERT audit_outbox + UPDATE approval_requests SET executed_at |
| Timeline | `alert.dismissed` |
| Notification | `alert_dismissed` → compliance if high/critical |
| Audit | `alert.dismissed` |
| Forbidden | Admin cannot dismiss without `alert:dismiss` + override (admin has `alert:dismiss` but step 8 still applies) |

---

### A6 — POST /alerts/{alert_id}/investigate
Create investigation from alert. Transitions alert to under_investigation.

| Field | Value |
|-------|-------|
| Permission | `alert:investigate` |
| OLP | `assigned_to == user.id` |
| Request | `{ "title": "string", "description": "string?", "expected_version": int }` |
| Response | Created Investigation (201) |
| Errors | 400, 401, 403, 404, 409 |
| Transaction | INSERT investigation + UPDATE alert (status=under_investigation) + INSERT activity_timeline + INSERT audit_outbox |
| Preconditions | Alert status in (acknowledged, under_investigation); no non-cancelled investigation for alert |
| Timeline | `alert.investigation_created` |
| Notification | None |
| Audit | `alert.investigation_created` |
| Idempotency | If investigation already exists for alert → return existing (200, not 201) |

---

### A7 — POST /alerts/{alert_id}/escalate
Create ComplianceCase from alert. Alert stays in under_investigation.

| Field | Value |
|-------|-------|
| Permission | `alert:transition` |
| OLP | `assigned_to == user.id` |
| Request | `{ "title": "string", "description": "string?", "priority": "critical|high|medium|low", "expected_version": int }` |
| Response | Created ComplianceCase (201) |
| Errors | 400, 401, 403, 404, 409 |
| Transaction | INSERT compliance_case + INSERT activity_timeline + INSERT audit_outbox |
| Preconditions | Alert status = under_investigation |
| Timeline | `alert.escalated` (timeline event only; alert status unchanged) |
| Notification | `case_assigned` to compliance queue (if auto-assigned) |
| Audit | `alert.escalated`, `case.created` |
| Idempotency | If case already exists linked to alert → return existing case |

---

## 2. INVESTIGATIONS (5 endpoints)

### I1 — GET /investigations/assigned
List investigations assigned to current user.

| Field | Value |
|-------|-------|
| Permission | `investigation:read_assigned` |
| Query params | `status`, `page`, `per_page` |
| Response | `{ data: Investigation[], pagination }` |

Investigation shape:
```json
{
  "investigation_id": "uuid",
  "title": "string",
  "description": "string",
  "alert_id": "uuid",
  "status": "active",
  "priority": "high",
  "assigned_to": "user_id",
  "findings_text": "string",
  "findings_refs": [],
  "conclusion": "string",
  "started_at": "iso8601",
  "submitted_at": null,
  "completed_at": null,
  "version": 2,
  "created_at": "iso8601",
  "updated_at": "iso8601"
}
```

---

### I2 — GET /investigations/{investigation_id}
Investigation detail.

| Field | Value |
|-------|-------|
| Permission | `investigation:read_assigned` (assignee) or `investigation:read` (compliance on linked case, admin) |
| OLP | Own, or case assignee for linked case, or admin (metadata only) |
| Errors | 401, 403, 404 |

---

### I3 — PATCH /investigations/{investigation_id}
Update findings and conclusion.

| Field | Value |
|-------|-------|
| Permission | `investigation:modify_findings` |
| OLP | `assigned_to == user.id` |
| Request | `{ "findings_text": "string?", "findings_refs": []?, "conclusion": "string?", "expected_version": int }` |
| Response | Updated Investigation |
| Errors | 400, 401, 403, 404, 409 |
| Preconditions | status IN (active, returned) |
| Transaction | UPDATE investigation + INSERT activity_timeline + INSERT audit_outbox |
| Timeline | `investigation.findings_updated` |
| Audit | `investigation.findings_updated` (hashed before/after for findings_text) |
| Idempotency | Same values → 200 no-op |

---

### I4 — PATCH /investigations/{investigation_id}/transition
Transition investigation status.

| Field | Value |
|-------|-------|
| Permission | `investigation:transition` (assignee) or `investigation:review` (compliance for submit approval) |
| OLP | Varies per transition (see state machine) |
| Request | `{ "target_status": "active|awaiting_information|submitted|completed|returned", "return_reason": "string (required if target=returned)", "expected_version": int }` |
| Response | Updated Investigation |
| Errors | 400, 401, 403, 404, 409 |
| Transaction | UPDATE investigation + INSERT activity_timeline + INSERT notifications (if applicable) + INSERT audit_outbox |
| Timeline | Per transition event type |
| Notification | Per transition (see state machine) |
| Audit | `investigation.{transition}` |

---

### I5 — DELETE /investigations/{investigation_id} → PATCH /cancel
Cancel investigation (admin only).

| Field | Value |
|-------|-------|
| Method/Path | POST `/investigations/{investigation_id}/cancel` |
| Permission | `investigation:assign` (admin) |
| Request | `{ "cancel_reason": "string (required)", "expected_version": int }` |
| Response | Updated Investigation |
| Errors | 400, 401, 403, 404, 409 |
| Preconditions | status NOT IN (completed, cancelled) |
| Transaction | UPDATE investigation (status=cancelled) + INSERT comment (cancel_reason) + INSERT activity_timeline + INSERT audit_outbox |
| Notification | `investigation_cancelled` → assignee |
| Audit | `investigation.cancelled` |

---

## 3. CASES (7 endpoints)

### C1 — GET /cases/assigned
List cases assigned to current user.

| Field | Value |
|-------|-------|
| Permission | `case:read_assigned` |
| Query params | `status`, `risk_level`, `page`, `per_page` |

---

### C2 — GET /cases/{case_id}
Case detail.

| Field | Value |
|-------|-------|
| Permission | `case:read_assigned` (own) or `case:read` (admin, metadata only) |
| OLP | Own scope; admin stripped of content fields |

---

### C3 — PATCH /cases/{case_id}/assign
Assign case to compliance user (admin).

| Field | Value |
|-------|-------|
| Permission | `case:assign` |
| OLP | Admin only |
| Request | `{ "assigned_to": "user_id", "expected_version": int }` |
| Errors | 400, 401, 403, 404, 409 |
| Transaction | UPDATE case + INSERT assignment_history + INSERT activity_timeline + INSERT notifications + INSERT audit_outbox |
| Notification | `case_assigned` → new assignee |

---

### C4 — PATCH /cases/{case_id}/transition
Transition case status.

| Field | Value |
|-------|-------|
| Permission | `case:transition` |
| OLP | `assigned_to == user.id` |
| Request | `{ "target_status": "under_review|awaiting_information|decision_pending|awaiting_compliance_action|resolved", "resolution": "string (required if target=resolved)", "expected_version": int }` |
| Errors | 400, 401, 403, 404, 409 |
| Preconditions | See state machine C2–C8 |
| Transaction | UPDATE case + INSERT activity_timeline + INSERT notifications + INSERT audit_outbox |
| Forbidden | Admin: 403 (PROHIBITED) |

---

### C5 — POST /cases/{case_id}/close
Close resolved case.

| Field | Value |
|-------|-------|
| Permission | `case:close` |
| OLP | `assigned_to == user.id` |
| Request | `{ "resolution": "string (required if not set)", "expected_version": int, "approval_request_id": "uuid (required if risk_level IN critical/high)" }` |
| Step 8 check | If risk_level IN (critical, high): ApprovalRequest must exist, approved, not yet consumed |
| Errors | 400, 401, 403, 404, 409, 428 |
| Transaction | UPDATE case (status=closed, closed_at, closed_by, closure_approval_id) + activity_timeline + audit_outbox + UPDATE approval consumed |
| Notification | `case_closed` → admin, investigation assignee |
| Audit | `case.closed` |
| Forbidden | Admin: 403 (PROHIBITED) |

---

### C6 — POST /cases/{case_id}/reopen
Reopen closed case (admin, with approval).

| Field | Value |
|-------|-------|
| Permission | `case:reopen` |
| OLP | Admin only |
| Request | `{ "reopen_reason": "string (required)", "expected_version": int, "approval_request_id": "uuid (required always)" }` |
| Errors | 400, 401, 403, 404, 409, 428 |
| Transaction | UPDATE case (status=open, clear closed_*, reopen_reason) + activity_timeline + audit_outbox + UPDATE approval consumed |
| Notification | `case_reopened` → compliance assignee |

---

### C7 — POST /cases/{case_id}/cancel
Cancel open/assigned case (admin).

| Field | Value |
|-------|-------|
| Permission | `case:assign` (admin) |
| Request | `{ "cancel_reason": "string", "expected_version": int }` |
| Preconditions | status IN (open, assigned) |
| Transaction | UPDATE case (status=cancelled) + INSERT comment + activity_timeline + audit_outbox |

---

## 4. INFORMATION REQUESTS (8 endpoints)

### IR1 — POST /cases/{case_id}/information-requests
Create information request. Atomically transitions case to `awaiting_information`.

| Field | Value |
|-------|-------|
| Permission | `info_request:create` |
| OLP | `case.assigned_to == user.id` |
| Request | `{ "assigned_to": "user_id (analyst)", "question": "string", "due_date": "date?", "expected_case_version": int }` |
| Response | Created InformationRequest (201) |
| Errors | 400, 401, 403, 404, 409 |
| Preconditions | `case.status = under_review` (status pre-check) |
| Transaction | UPDATE case (status=awaiting_information, version+=1 WHERE version=expected_case_version) + INSERT information_request + INSERT activity_timeline (case.awaiting_information) + INSERT activity_timeline (ir.created) + INSERT notifications + INSERT audit_outbox |
| Notification | `ir_created` → assigned analyst |
| Audit | `ir.created`, `case.awaiting_info` |
| Idempotency | Same IR request with same key → 200 (case already awaiting_information due to this IR) |
| Conflict | case version mismatch → 409 |

---

### IR2 — GET /cases/{case_id}/information-requests
List IRs for a case.

| Field | Value |
|-------|-------|
| Permission | `info_request:read` (compliance assignee) or `info_request:read_assigned` (analyst, filtered to own) |
| Query params | `status`, `page`, `per_page` |

---

### IR3 — GET /information-requests/{ir_id}
IR detail.

| Field | Value |
|-------|-------|
| Permission | `info_request:read` or `info_request:read_assigned` |
| OLP | Compliance on own case, or analyst assigned_to == user.id |

---

### IR4 — PATCH /information-requests/{ir_id}/acknowledge
Analyst acknowledges IR.

| Field | Value |
|-------|-------|
| Permission | `info_request:respond` |
| OLP | `assigned_to == user.id` |
| Request | `{ "expected_version": int }` |
| State | open → acknowledged |
| Idempotency | Already acknowledged → 200 no-op |

---

### IR5 — PATCH /information-requests/{ir_id}/respond
Analyst responds to IR.

| Field | Value |
|-------|-------|
| Permission | `info_request:respond` |
| OLP | `assigned_to == user.id` |
| Request | `{ "response_text": "string (required)", "expected_version": int }` |
| State | acknowledged → responded |
| Preconditions | `response_text` non-empty |
| Notification | `ir_responded` → IR creator (compliance) |

---

### IR6 — PATCH /information-requests/{ir_id}/accept
Compliance accepts response.

| Field | Value |
|-------|-------|
| Permission | `info_request:accept` |
| OLP | `created_by == user.id` |
| Request | `{ "acceptance_note": "string?", "expected_version": int }` |
| State | responded → accepted |
| Side effects | If case status = awaiting_information → INSERT notification to case assignee to trigger C4 manually |
| Notification | `ir_accepted` → analyst |

---

### IR7 — PATCH /information-requests/{ir_id}/return
Compliance returns response.

| Field | Value |
|-------|-------|
| Permission | `info_request:return` |
| OLP | `created_by == user.id` |
| Request | `{ "return_reason": "string (required)", "expected_version": int }` |
| State | responded → returned |
| Notification | `ir_returned` → analyst |

---

### IR8 — POST /information-requests/{ir_id}/cancel
Cancel IR.

| Field | Value |
|-------|-------|
| Permission | `info_request:cancel` |
| OLP | `created_by == user.id` OR admin |
| Request | `{ "cancel_reason": "string (required)", "expected_version": int }` |
| Preconditions | status IN (open, acknowledged) |
| Notification | None (minor lifecycle event) |

---

## 5. DECISIONS (2 endpoints)

### D1 — POST /cases/{case_id}/decisions
Record compliance decision.

| Field | Value |
|-------|-------|
| Permission | `case:decision` — PROHIBITED for admin and analyst |
| OLP | `case.assigned_to == user.id` |
| Request | `{ "decision_type": "no_action|warning|enhanced_due_diligence_recommended|report_to_authority_recommended|account_action_recommended|closure_recommended", "rationale": "string (required)", "expected_version": int, "approval_request_id": "uuid (required if decision_type=report_to_authority_recommended)" }` |
| Response | Created Decision (201) |
| Errors | 400, 401, 403, 404, 409, 428 |
| Preconditions | case.status = decision_pending; if decision_type=report_to_authority_recommended: approval_request_id must reference an ApprovalRequest with entity_type=compliance_case, entity_id=case_id, action_type=decision_report_to_authority, status=approved, executed_at IS NULL, and proposed_payload.decision_type must match |
| Transaction | INSERT decision + UPDATE case (current_disposition_id, status based on decision_type) + activity_timeline + audit_outbox + UPDATE approval SET executed_at=NOW() WHERE approval_request_id=$1 (if applicable) |
| Decision → case status | `no_action`, `closure_recommended` → resolved | `warning`, `edd`, `account_action`, `report_to_authority` → awaiting_compliance_action |
| Notification | `case_decision_recorded` → admin |
| Audit | `case.decision_recorded` |

---

### D2 — GET /cases/{case_id}/decisions
List decisions for a case.

| Field | Value |
|-------|-------|
| Permission | `case:read_assigned` (own) or `case:read` (admin) |
| Response | `{ data: Decision[] }` ordered by decided_at DESC |

---

## 6. APPROVALS (4 endpoints)

### AP1 — POST /approval-requests
Create approval request.

| Field | Value |
|-------|-------|
| Permission | `approval:request` |
| Request | `{ "action_type": "alert_dismissal_critical_high|case_closure_critical_high|decision_report_to_authority|case_reopen", "entity_type": "alert|compliance_case", "entity_id": "uuid", "proposed_payload": "object?", "rationale": "string" }` |
| Response | Created ApprovalRequest (201) |
| Errors | 400, 401, 403, 404 |
| Preconditions | Entity exists, user has scope access, action_type matches entity state. **When action_type=decision_report_to_authority:** entity_type MUST be `compliance_case` (not `decision`) and entity_id MUST be the case UUID. `proposed_payload` shape: `{ "decision_type": "report_to_authority_recommended" }`. |
| Transaction | INSERT approval_request + INSERT activity_timeline + INSERT notifications (all eligible approvers) + INSERT audit_outbox |
| Notification | `approval_requested` → all compliance officers in scope |
| Audit | `approval.created` |

---

### AP2 — GET /approval-requests
List pending approval requests visible to user.

| Field | Value |
|-------|-------|
| Permission | `approval:read` |
| OLP | Compliance: IRs where they are eligible approver; Analyst: own requests; Admin: all in scope |
| Query params | `status`, `action_type`, `page`, `per_page` |

---

### AP3 — GET /approval-requests/{approval_request_id}
Approval request detail with all votes.

| Field | Value |
|-------|-------|
| Permission | `approval:read` |

---

### AP4 — POST /approval-requests/{approval_request_id}/vote
Cast approval vote.

| Field | Value |
|-------|-------|
| Permission | `approval:approve` — PROHIBITED for analyst |
| OLP | `requester != user.id` (step 7); not already voted |
| Request | `{ "decision": "approved|rejected", "rationale": "string (required if rejected)" }` |
| Response | Updated ApprovalRequest |
| Errors | 400, 401, 403, 404, 409 |
| Transaction | INSERT approval_decision + UPDATE approval_requests (increment approval_count, update status if count >= required) + activity_timeline + audit_outbox |
| Side effects | If status → approved: notify requester; if rejected: notify requester |
| Notification | `approval_decided` → requester |
| Audit | `approval.vote` or `approval.approved` or `approval.rejected` |
| Conflict | Already voted for same request: 409 (unique constraint) |

---

## 7. COMMENTS (3 endpoints)

### CM1 — GET /{entity_type}/{entity_id}/comments
List comments on entity. `entity_type` ∈ `alerts|investigations|cases|information-requests`

| Field | Value |
|-------|-------|
| Permission | `comment:read` + entity read permission |
| OLP | Internal comments (`is_internal=true`): only compliance + admin (`comment:view_internal`) |
| Query params | `page`, `per_page` |

---

### CM2 — POST /{entity_type}/{entity_id}/comments
Create comment.

| Field | Value |
|-------|-------|
| Permission | `comment:create` + entity read permission |
| Request | `{ "content": "string (required)", "is_internal": false }` |
| Response | Created Comment (201) |
| Errors | 400, 401, 403, 404 |
| Transaction | INSERT comment + INSERT activity_timeline + INSERT audit_outbox |
| Audit | `comment.created` |

---

### CM3 — PATCH /comments/{comment_id}/redact
Redact comment content (admin only).

| Field | Value |
|-------|-------|
| Permission | `comment:redact` |
| OLP | Admin only |
| Request | `{ "redact_reason": "string (required)" }` |
| Response | Updated Comment (content replaced by `[REDACTED — {reason}]`) |
| Transaction | UPDATE comment + INSERT audit_outbox |
| Audit | `comment.redacted` |

---

## 8. TIMELINE (2 endpoints)

### TL1 — GET /{entity_type}/{entity_id}/timeline
Full timeline for entity.

| Field | Value |
|-------|-------|
| Permission | `timeline:read` + entity read permission |
| Query params | `page`, `per_page`, `event_type` |
| Response | `{ data: TimelineEntry[] }` ordered by occurred_at ASC |

---

### TL2 — GET /timeline
Cross-entity timeline for current user (own entities only).

| Field | Value |
|-------|-------|
| Permission | `timeline:read` |
| Query params | `entity_type`, `since`, `page`, `per_page` |

---

## 9. NOTIFICATIONS (3 endpoints)

### N1 — GET /notifications
List own notifications.

| Field | Value |
|-------|-------|
| Permission | `notification:read` |
| Query params | `is_read`, `page`, `per_page` |
| Response | `{ data: Notification[], unread_count: int }` |

---

### N2 — PATCH /notifications/{notification_id}/read
Mark notification read.

| Field | Value |
|-------|-------|
| Permission | `notification:update` |
| OLP | `user_id == user.id` |
| Response | Updated Notification |

---

### N3 — PATCH /notifications/read-all
Mark all own notifications read.

| Field | Value |
|-------|-------|
| Permission | `notification:update` |
| Response | `{ marked_read: int }` |

---

## 10. ADMIN OPERATIONAL (3 endpoints)

### AD1 — GET /admin/outbox
List audit outbox records (admin only).

| Field | Value |
|-------|-------|
| Permission | `admin:outbox_monitor` |
| Query params | `status`, `page`, `per_page` |
| Response | Paginated outbox rows with attempt_count, last_error, poison_reason |

---

### AD2 — POST /admin/outbox/{outbox_id}/retry
Force retry of failed/poison outbox record (admin).

| Field | Value |
|-------|-------|
| Permission | `admin:outbox_retry` |
| Response | `{ queued: true, outbox_id }` |
| Action | SET status='pending', attempt_count=0, poison_reason=NULL WHERE outbox_id = $1 |
| Audit | `admin.outbox_retry` |

---

### AD3 — GET /admin/orphan-assignments
Detect entities assigned to suspended, inactive, or out-of-scope users (admin).

| Field | Value |
|-------|-------|
| Permission | `admin:orphan_monitor` |
| Response | `{ "alerts": [...], "investigations": [...], "cases": [...] }` |
| Each entity | `{ "entity_id": "uuid", "title": "string", "status": "string", "assigned_to": { "user_id": "uuid", "status": "string" } }` |
| Query | `SELECT entities where assigned_to IN (SELECT user_id FROM users WHERE status NOT IN ('active', 'active_pending')) OR assigned_to NOT IN (SELECT user_id FROM user_scopes WHERE scope_id = entity.scope_id)` |
| Errors | 401, 403 |
| Audit | None (read-only) |

---

## Common Request Headers

```
Authorization: Bearer <jwt>
X-Request-ID: <uuid>           (tracing; generated by client or gateway)
X-Idempotency-Key: <uuid>      (optional for mutations; stored in idempotency_cache for 24h; 409 if same key + different body)
```

## Common Response Headers

```
X-Request-ID: <echo>
X-Version: <entity_version>    (on mutation responses)
```
