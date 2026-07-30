# Increment 2B — Test Plan

Executable scenarios. Each row: ID, category, setup, action, expected result, pass criterion.

---

## 1. Valid Transitions

| ID | Scenario | Setup | Action | Expected |
|----|----------|-------|--------|---------|
| T00 | Alert assignment via dedicated endpoint | Admin, alert status=new | PATCH /alerts/:id/assign (assigned_to=analyst) | Alert status=assigned; assigned_to set; assignment_history inserted; notification to assignee; timeline `alert.assigned`; audit outbox entry |
| T01 | Alert reassignment — same user (idempotent) | Admin, alert already assigned to user | PATCH /alerts/:id/assign (same assigned_to) | Alert unchanged; no-op; 200 |
| T02 | Alert acknowledgment | Analyst, alert assigned to them, status=assigned | PATCH /acknowledge | Alert status=acknowledged; timeline entry |
| T03 | Create investigation | Analyst, alert status=acknowledged, assigned to them | POST /investigate | Alert status=under_investigation; investigation created status=open; audit outbox entry |
| T04 | Investigation start | Analyst, investigation assigned to them, status=open | PATCH /transition target=active | Investigation status=active; started_at set |
| T05 | Update findings | Analyst, investigation status=active | PATCH /investigations/:id (findings_text) | findings_text updated; audit event emitted (hashed before/after) |
| T06 | Submit investigation | Analyst, investigation status=active, findings non-empty | PATCH /transition target=submitted | Investigation status=submitted; notification to compliance |
| T07 | Compliance approves investigation | Compliance, investigation status=submitted, linked case assigned to them | PATCH /transition target=completed | Investigation status=completed; completed_at set |
| T08 | Escalate alert to case | Analyst, alert status=under_investigation | POST /escalate | ComplianceCase created status=open; audit events for both entities |
| T09 | Case assignment | Admin, case status=open | PATCH /cases/:id/assign | Case status=assigned; assignment_history entry; notification to compliance |
| T10 | Begin case review | Compliance, case status=assigned, assigned to them | PATCH /transition target=under_review | Case status=under_review |
| T11 | Create information request | Compliance, case status=under_review | POST /information-requests | IR created status=open; case status=awaiting_information; notification to analyst |
| T12 | IR acknowledgment | Analyst, IR assigned to them, status=open | PATCH /acknowledge | IR status=acknowledged |
| T13 | IR response | Analyst, IR status=acknowledged | PATCH /respond (response_text) | IR status=responded; notification to compliance |
| T14 | IR accept | Compliance, IR status=responded, created_by=user | PATCH /accept | IR status=accepted; notification to analyst |
| T15 | Resume case after IR | Compliance, case status=awaiting_information | PATCH /transition target=under_review | Case status=under_review |
| T16 | Decision pending | Compliance, case status=under_review | PATCH /transition target=decision_pending | Case status=decision_pending |
| T17 | Record no_action decision | Compliance, case status=decision_pending | POST /decisions (no_action) | Decision inserted; case status=resolved; current_disposition_id set |
| T18 | Record closure_recommended decision | Compliance, case status=decision_pending | POST /decisions (closure_recommended) | Decision inserted; case status=resolved |
| T19 | Record warning decision | Compliance, case status=decision_pending | POST /decisions (warning) | Decision inserted; case status=awaiting_compliance_action |
| T20 | Action completed | Compliance, case status=awaiting_compliance_action | PATCH /transition target=resolved | Case status=resolved |
| T21 | Close low-risk case | Compliance, case status=resolved, risk_level=low | POST /close (no approval) | Case status=closed; closed_at set; alert resolved if linked |
| T22 | IR return | Compliance, IR status=responded | PATCH /return (return_reason) | IR status=returned; notification to analyst |
| T23 | IR re-acknowledge after return | Analyst, IR status=returned | PATCH /acknowledge | IR status=acknowledged |
| T24 | IR second response | Analyst, IR status=acknowledged (after return) | PATCH /respond | IR status=responded |
| T25 | Create approval request | Compliance, case risk_level=high, status=resolved | POST /approval-requests | ApprovalRequest status=pending; notifications to eligible approvers |
| T26 | Approve approval request | Compliance officer B, approval status=pending | POST /vote (approved) | approval_decisions inserted; if count=required → status=approved |
| T27 | Close high-risk case | Compliance, case risk_level=high, approval approved | POST /close (approval_request_id) | Case closed; approval executed_at set |
| T28 | Dismiss medium-risk alert (no approval) | Analyst, alert severity=medium | PATCH /dismiss | Alert status=dismissed; no approval required |
| T29 | Dismiss critical alert with approval | Analyst, alert severity=critical, approval approved | PATCH /dismiss (approval_request_id) | Alert dismissed; approval consumed |
| T30 | Comment on investigation | Analyst, investigation status=active | POST /comments | Comment created; timeline entry |
| T31 | Internal comment visible to compliance | Compliance, investigation with internal comment | GET /comments | is_internal=true comments visible to compliance |
| T32 | Admin redact comment | Admin | PATCH /comments/:id/redact | Content replaced by [REDACTED]; audit event |
| T33 | Timeline shows all events | Any user, entity with multiple transitions | GET /timeline | Events in occurred_at order, correct event_type for each transition |
| T34 | Notification mark read | Analyst with unread notification | PATCH /notifications/:id/read | is_read=true; read_at set |
| T35 | Reopen resolved alert | Admin, alert status=resolved | PATCH /assign (new analyst) | Alert status=assigned; assignment_history; timeline event "reopened_and_assigned" |

---

## 2. Forbidden Transitions

| ID | Scenario | Setup | Action | Expected |
|----|----------|-------|--------|---------|
| F01 | Admin attempts case:decision | Admin, case status=decision_pending | POST /decisions | 403 — PROHIBITED combo (admin, case:decision) |
| F02 | Admin attempts case:close | Admin, case status=resolved | POST /close | 403 — PROHIBITED |
| F03 | Analyst attempts case:decision | Analyst | POST /decisions | 403 |
| F04 | Analyst attempts case:close | Analyst | POST /close | 403 |
| F05 | Analyst approves own approval request | Analyst, alert severity=high | POST /vote | 403 — PROHIBITED (analyst, approval:approve) |
| F06 | Compliance approves own approval request | Compliance A created approval, Compliance A votes | POST /vote | 403 — conflict of interest (step 7) |
| F07 | Analyst assigns case | Analyst | PATCH /cases/:id/assign | 403 |
| F08 | Admin modifies investigation findings | Admin | PATCH /investigations/:id (findings_text) | 403 — investigation:modify_findings PROHIBITED for admin |
| F09 | Acknowledge already-dismissed alert | Analyst, alert status=dismissed | PATCH /acknowledge | 409 — action not permitted in current state |
| F10 | Submit investigation with empty findings | Analyst, investigation status=active, no findings | PATCH /transition target=submitted | 400 — findings required |
| F11 | Close case without resolution | Compliance, case status=resolved, resolution null | POST /close | 400 |
| F12 | Record decision when case not in decision_pending | Compliance, case status=under_review | POST /decisions | 409 |
| F13 | Transition alert from new directly to acknowledged | Anyone | PATCH /acknowledge (alert status=new) | 409 — must be assigned first |
| F14 | IR respond without acknowledgment | Analyst, IR status=open | PATCH /respond | 409 — must acknowledge first |
| F15 | IR accept before response | Compliance, IR status=open | PATCH /accept | 409 |
| F16 | Case:close without approval when risk_level=high | Compliance, case risk_level=high, no approval | POST /close | 428 — approval required |
| F17 | Execute approval twice | Compliance, approval executed_at already set | POST /close (same approval_request_id) | 409 — approval already consumed |
| F18 | Assign alert to suspended user | Admin, target user status=suspended | PATCH /alerts/:id/assign (assigned_to=suspended_user) | 400 — target user is not active |

---

## 3. Cross-Entity Access Control

| ID | Scenario | Expected |
|----|----------|---------|
| XA01 | Analyst A reads investigation assigned to Analyst B | 404 (scope: own only) |
| XA02 | Analyst A reads case assigned to Compliance B | 404 (analyst: case:read_assigned but not assignee) |
| XA03 | Compliance reads investigation not linked to their case | 404 |
| XA04 | Compliance A reads case assigned to Compliance B | 404 (case:read_assigned but not assignee) |
| XA05 | Admin reads case with global scope | 200 but content fields stripped (metadata only) |
| XA06 | Admin reads investigation of any scope | 200 metadata only |
| XA07 | Legacy manager role attempts alert:acknowledge | 403 — workbench:access PROHIBITED for manager |
| XA08 | Out-of-scope user reads case in different scope | 404 |
| XA09 | Cross-scope assignment (analyst to case in different scope) | 403 from admin assign endpoint — target user lacks target scope |
| XA10 | Analyst views internal comment | 200 but is_internal=true comments excluded from response |

---

## 4. Concurrency and Versioning

| ID | Scenario | Expected |
|----|----------|---------|
| V01 | Stale version on acknowledge | Two analysts, one submits first; second submits with old version | 409 from second; message: Conflict |
| V02 | Missing expected_version on dismiss | PATCH /dismiss without expected_version field | 422 — field required |
| V03 | Duplicate escalation | Alert already has linked non-cancelled case; POST /escalate again | 200 — idempotent, returns existing case |
| V04 | Duplicate investigation creation | Alert already has non-cancelled investigation; POST /investigate again | 200 — idempotent, returns existing investigation |
| V05 | Duplicate IR acknowledgment | IR already acknowledged; PATCH /acknowledge again | 200 — no-op |
| V06 | Concurrent case close attempts | Two compliance officers both attempt close on same case | First succeeds (200); second receives 409 (stale version) |
| V07 | Approval already consumed | POST /close with approval_request_id that has executed_at set | 409 |
| V08 | Approval expired then used | ApprovalRequest expired; attempt to close case | 428 — approval not in approved state |
| V09 | Idempotent replay — same key + same body | Mutation with X-Idempotency-Key, first call succeeds | Second call with same key + same body | 200 — stored response returned (not 201 for creates) |
| V10 | Idempotent conflict — same key + different body | Mutation with X-Idempotency-Key, first call succeeds | Second call with same key + different body | 409 — idempotency_key_mismatch |
| V11 | Idempotent key expired — new request allowed | Idempotency key stored > 24h ago | Request with same key + same body | 200 — key expired, treated as new; original response not replayed |

---

## 5. Audit Outbox Scenarios

| ID | Scenario | Expected |
|----|----------|---------|
| AU01 | Audit agent down during mutation | Mutation commits; outbox row inserted status=pending; HTTP delivery fails; status=failed; retry on next worker cycle |
| AU02 | Audit agent recovers after outage | Worker retries pending/failed rows; delivery succeeds; status=delivered |
| AU03 | Audit agent unreachable for 5 attempts | outbox row status=poison; admin notified; admin can see via GET /admin/outbox?status=poison |
| AU04 | Admin retries poison event | POST /admin/outbox/:id/retry | attempt_count=0, status=pending; next worker picks up |
| AU05 | Duplicate delivery (worker restart mid-delivery) | Audit agent receives same idempotency_key twice | Second insert → UNIQUE violation → audit agent returns 200; worker marks delivered; no duplicate in audit_log |
| AU06 | Transaction rollback | DB error rolls back mutation transaction | audit_outbox row not inserted; no phantom audit event |
| AU07 | Stuck delivery (worker crashed mid-lock) | audit_outbox row in 'delivering' for > 5 min | Reconciliation worker resets to pending; delivery retried |
| AU08 | Notification failure (notification INSERT fails) | Notification table error mid-transaction | Full transaction rolls back including business mutation; entity unchanged |

---

## 6. Notification Scenarios

| ID | Scenario | Expected |
|----|----------|---------|
| NF01 | Suspended user with active assignment | Alert assigned to suspended user | Assignment still exists; notifications delivered to DB (no email in 2B); admin sees suspended user via outbox monitor; admin reassigns |
| NF02 | Notification on alert assignment | Admin assigns alert | `alert_assigned` notification in DB for target analyst |
| NF03 | Notification on case decision recorded | Decision recorded | `case_decision_recorded` notification for admin |
| NF04 | Mark-all-read | Analyst has 5 unread notifications, calls PATCH /read-all | All 5 marked read; unread_count=0 on next GET |

---

## 7. Approval Scenarios

| ID | Scenario | Expected |
|----|----------|---------|
| AP01 | Report-to-authority decision without approval | Compliance, decision_type=report_to_authority_recommended, no approval | 428 |
| AP02 | Approval expires before use | Create approval, let it expire (or force expires_at to past) | ApprovalRequest status=expired; close attempt returns 428 |
| AP03 | Rejection stops approval | Compliance B rejects approval created by Compliance A | status=rejected; Compliance A cannot close (428 since status != approved) |
| AP04 | Case reopening approval | Admin requests case reopen; approval created; compliance votes; admin executes | Case status=open; approval consumed |

---

## 8. Information Request Scenarios

| ID | Scenario | Expected |
|----|----------|---------|
| IRS01 | Returned IR full cycle | compliance creates IR → analyst acknowledges → responds → compliance returns (return_reason) → analyst re-acknowledges → responds → compliance accepts | IR final status=accepted; all states traversed; all timeline events present |
| IRS02 | Cancel open IR | Compliance cancels IR before analyst responds | IR status=cancelled; analyst notified (or silently, as configured) |
| IRS03 | Cancel acknowledged IR | Same but after acknowledge | IR status=cancelled |
| IRS04 | IR past due_date | IR due_date < today, status=open | API returns IR normally; frontend shows red overdue badge; no automatic cancellation in 2B |

---

## 9. Decision Path Scenarios

| ID | Scenario | Expected |
|----|----------|---------|
| DP01 | No-action decision → case resolved | decision_type=no_action | Case status=resolved; resolution required on close |
| DP02 | Warning decision → awaiting_compliance_action → resolved | decision_type=warning | Case status=awaiting_compliance_action; compliance marks action completed → resolved |
| DP03 | EDD decision → awaiting_compliance_action → resolved | decision_type=enhanced_due_diligence_recommended | Same flow as DP02 |
| DP04 | Account action decision | decision_type=account_action_recommended | Case status=awaiting_compliance_action; compliance must document action in resolution text; no actual account freeze in 2B |
| DP05 | *(removed — decision superseding is Phase 2D)* | | | |

---

## 10. Edge Cases

| ID | Scenario | Expected |
|----|----------|---------|
| EC01 | Manager user accesses workbench | Legacy manager role, valid JWT | 403 on all workbench routes — workbench:access PROHIBITED |
| EC02 | User with zero scopes | User created without scope grant | 404 on all entity reads (scope check step 4 fails for all resources) |
| EC03 | Approval with multiple required votes | required_approvals=2; one compliance votes approved | ApprovalRequest status remains pending until second vote |
| EC04 | Alert with no linked investigation | Alert status=under_investigation, investigation deleted/cancelled | GET /alerts/:id returns alert correctly; investigate action available again (idempotency returns new investigation) |
| EC05 | Comment on closed case | Case status=closed | Comment creation: 409 (action not permitted in state closed — comment:create requires case status NOT IN (closed, cancelled)) |
| EC06 | Request ID tracing | Client sends X-Request-ID | X-Request-ID echoed in response; stored in audit_outbox payload.request_id |
| EC07 | Unknown action in authorise() | Non-existent permission code passed | 400 — Unknown action |
| EC08 | Version overflow | version = 2147483647 (INT max) | 400 — implementation should use BIGINT or detect and reject; mark as tech debt |

---

## 11. Orphan Assignment Detection

| ID | Scenario | Expected |
|----|----------|---------|
| O001 | Suspended user has active assignments | Alert, investigation, or case assigned to suspended user | GET /admin/orphan-assignments returns them in appropriate list(s) |
| O002 | All users active — no orphans | All assigned-to users have status=active | GET /admin/orphan-assignments returns empty lists `{ alerts: [], investigations: [], cases: [] }` |
