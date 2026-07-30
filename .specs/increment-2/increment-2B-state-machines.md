# Increment 2B — State Machines

One canonical transition table per entity. Each row is a complete specification of one transition.

Legend:
- **Actor**: who initiates
- **Perm**: permission code checked by `authorise()`
- **OLP**: object-level policy (beyond permission)
- **Required fields**: must be non-null before transition succeeds
- **Approval**: ApprovalRequest required before execution
- **Side effects**: atomic in same transaction
- **Idempotency**: behaviour if same transition requested again
- **Conflict**: behaviour if version mismatch

---

## 1. Alert State Machine

### States

```
new → assigned → acknowledged → under_investigation → resolved
                acknowledged → dismissed (needs approval if critical/high)
resolved → assigned (admin reopens via new assignment — no 'reopened' state)
dismissed → assigned (admin reopens via new assignment — no 'reopened' state)
```

**States:** `new`, `assigned`, `acknowledged`, `under_investigation`, `resolved`, `dismissed`

Rationale: `escalated` and `reopened` removed. Escalation creates a ComplianceCase; the alert moves to `under_investigation`. Reopening is an admin action that creates a new assignment cycle from terminal states.

### Transition Table

| # | From | To | Action | Actor | Perm | OLP | Required Fields | Approval | Side Effects | Notification | Timeline Event | Audit Event | Idempotency | Conflict |
|---|------|----|--------|-------|------|-----|-----------------|----------|--------------|--------------|----------------|-------------|-------------|----------|
| A1 | new | assigned | assign | Admin | `alert:assign` | none | `assigned_to` valid user | No | Insert assignment_history | `alert_assigned` → assignee | `assigned` | `alert.assigned` | No-op if already assigned to same user | 409 |
| A2 | assigned | acknowledged | acknowledge | Assignee | `alert:acknowledge` | `assigned_to == user.id` | none | No | none | none | `acknowledged` | `alert.acknowledged` | No-op if already acknowledged | 409 |
| A3 | acknowledged | under_investigation | create_investigation | Assignee | `alert:investigate` | `assigned_to == user.id` | `title` on new investigation | No | Insert investigation (status=open, alert_id=this) | none | `investigation_created` | `alert.investigation_created` | Return existing investigation if one exists for alert | 409 |
| A4 | acknowledged | dismissed | dismiss | Assignee | `alert:dismiss` | `assigned_to == user.id` | `dismissed_reason` | Yes if severity IN (critical, high) | Set dismissed_at, dismissed_by, dismissed_reason | `alert_dismissed` → compliance (if applicable) | `dismissed` | `alert.dismissed` | No-op if already dismissed | 409 |
| A4b | under_investigation | dismissed | dismiss | Assignee | `alert:dismiss` | `assigned_to == user.id` | `dismissed_reason` | Yes if severity IN (critical, high) | Same as A4 | same | `dismissed` | `alert.dismissed` | No-op | 409 |
| A5 | under_investigation | resolved | resolve | System/Compliance | `alert:transition` | Case closed with this alert_id | `resolved_at` auto | No | Set resolved_at, resolved_by | none (case closure notifies separately) | `resolved` | `alert.resolved` | No-op if already resolved | 409 |
| A6 | dismissed | assigned | reopen | Admin | `alert:assign` | none | `assigned_to`, reason as comment | No | Clear dismissed_* fields, set assigned_to, insert assignment_history, insert comment with reason | `alert_assigned` → new assignee | `reopened_and_assigned` | `alert.reopened` | No-op if already assigned to same user | 409 |
| A7 | resolved | assigned | reopen | Admin | `alert:assign` | none | `assigned_to`, reason as comment | No | Same as A6 | same | `reopened_and_assigned` | `alert.reopened` | No-op | 409 |

**Forbidden conditions for all transitions:**
- `manager` role: 403 on any alert transition (workbench:access denied upstream)
- `analyst` attempting to assign: 403 (missing `alert:assign`)
- Admin attempting A4 without override: allowed (admin has `alert:dismiss`); four-eyes approval still required for critical/high
- Transition from `resolved` or `dismissed` to any state except `assigned` via A6/A7: 400
- Version mismatch: 409 always (no silent merge)

---

## 2. Investigation State Machine

### States

```
open → active → awaiting_information → active (loop)
active → submitted → completed
submitted → returned → active (loop)
active → completed (direct, by assignee with findings)
any non-terminal → cancelled (admin only)
```

**States:** `open`, `active`, `awaiting_information`, `submitted`, `returned`, `completed`, `cancelled`

Note: `draft`, `assigned`, `escalated`, `archived`, `reopened` from previous architecture removed. Investigations are created open and immediately assignable. Escalation is an alert action (creates ComplianceCase), not an investigation state.

### Transition Table

| # | From | To | Action | Actor | Perm | OLP | Required Fields | Approval | Side Effects | Notification | Timeline | Audit | Idempotency | Conflict |
|---|------|----|--------|-------|------|-----|-----------------|----------|--------------|--------------|----------|-------|-------------|----------|
| I1 | open | active | start | Assignee | `investigation:transition` | `assigned_to == user.id` | none | No | Set started_at | none | `started` | `investigation.started` | No-op | 409 |
| I2 | active | awaiting_information | request_info | Assignee | `investigation:transition` | `assigned_to == user.id` | reason (as IR or comment) | No | Insert information_request if case exists | `ir_created` → IR assignee | `awaiting_information` | `investigation.awaiting_info` | No-op if already awaiting | 409 |
| I3 | awaiting_information | active | info_received | Assignee | `investigation:transition` | `assigned_to == user.id` | IR responded | No | none | none | `resumed` | `investigation.resumed` | No-op | 409 |
| I4 | active | submitted | submit | Assignee | `investigation:transition` | `assigned_to == user.id` | `findings_text` non-empty OR `findings_refs` non-empty | No | Set submitted_at | `investigation_submitted` → compliance if case linked | `submitted` | `investigation.submitted` | No-op | 409 |
| I5 | submitted | completed | approve | Compliance | `investigation:review` | linked case assigned_to == user.id | none | No | Set completed_at | `investigation_completed` → analyst | `completed` | `investigation.completed` | No-op | 409 |
| I6 | submitted | returned | return | Compliance | `investigation:review` | linked case assigned_to == user.id | `return_reason` | No | Set return_reason | `investigation_returned` → analyst | `returned` | `investigation.returned` | No-op | 409 |
| I7 | returned | active | revise | Assignee | `investigation:transition` | `assigned_to == user.id` | none | No | Clear submitted_at | none | `revision_started` | `investigation.revision_started` | No-op | 409 |
| I8 | active | completed | complete | Assignee | `investigation:transition` | `assigned_to == user.id` | `findings_text` or `findings_refs` + `conclusion` | No | Set completed_at | none | `completed` | `investigation.completed` | No-op | 409 |
| I9 | any non-terminal | cancelled | cancel | Admin | `investigation:assign` | none | `cancel_reason` as comment | No | Insert comment with reason | `investigation_cancelled` → assignee | `cancelled` | `investigation.cancelled` | No-op if already cancelled | 409 |

**Forbidden:**
- Analyst cannot approve/return own submitted investigation (no `investigation:review` permission)
- Admin cannot modify `findings_text` (missing `investigation:modify_findings` — analyst-only sensitive perm)
- Completed investigation: no further transitions; read-only

---

## 3. ComplianceCase State Machine

### States

```
open → assigned → under_review → awaiting_information → under_review (loop)
under_review → decision_pending → resolved (no_action / closure_recommended / warning)
decision_pending → awaiting_compliance_action → resolved (edd / report_to_authority / account_action)
resolved → closed (needs approval if critical/high)
open → cancelled (admin)
assigned → cancelled (admin)
closed → open (admin reopen; needs approval)
```

**States:** `open`, `assigned`, `under_review`, `awaiting_information`, `decision_pending`, `awaiting_compliance_action`, `resolved`, `closed`, `cancelled`

Note: `escalated`, `reopened`, `remediation_required`, `remediation_in_progress`, `triage`, `draft` removed. Cases are created open. Escalation references are audit events, not states. Remediation is Phase 2D.

### Transition Table

| # | From | To | Action | Actor | Perm | OLP | Required Fields | Approval | Side Effects | Notification | Timeline | Audit | Idempotency | Conflict |
|---|------|----|--------|-------|------|-----|-----------------|----------|--------------|--------------|----------|-------|-------------|----------|
| C1 | open | assigned | assign | Admin | `case:assign` | none | `assigned_to` | No | Insert assignment_history | `case_assigned` → assignee | `assigned` | `case.assigned` | No-op if same user | 409 |
| C2 | assigned | under_review | begin_review | Assignee | `case:transition` | `assigned_to == user.id` | none | No | none | none | `under_review` | `case.under_review` | No-op | 409 |
| C3 | under_review | awaiting_information | request_information | Assignee | `case:transition` | `assigned_to == user.id` | `expected_case_version`, IR question + assigned analyst | No | Atomic tx: lock/version-check case, verify status=under_review, insert information_request, set case.status=awaiting_information, increment case.version, insert timeline (ir_created + case.awaiting_info), insert notification → analyst, insert audit outbox (ir.created + case.awaiting_info) | `ir_created` → analyst | `awaiting_information` | `case.awaiting_info` | No-op | 409 |
| C4 | awaiting_information | under_review | info_received | Assignee | `case:transition` | `assigned_to == user.id` | IR status = accepted | No | none | none | `under_review_resumed` | `case.resumed` | No-op | 409 |
| C5 | under_review | decision_pending | ready_for_decision | Assignee | `case:transition` | `assigned_to == user.id` | none | No | none | `case_decision_pending` → compliance admin | `decision_pending` | `case.decision_pending` | No-op | 409 |
| C6 | decision_pending | resolved | record_decision_no_action | Compliance | `case:decision` | `assigned_to == user.id` | Decision: no_action or closure_recommended, `rationale` | No | Insert decision, set current_disposition_id, set resolved_at, resolved_by | `case_resolved` → admin | `resolved` | `case.resolved` | 409 if already resolved |  409 |
| C7 | decision_pending | awaiting_compliance_action | record_decision_requires_action | Compliance | `case:decision` | `assigned_to == user.id` | Decision type IN (warning, enhanced_due_diligence_recommended, account_action_recommended) or report_to_authority_recommended + approval (entity_type=compliance_case, action_type=decision_report_to_authority) with proposed_payload containing decision_type | Yes (entity_type=compliance_case, action_type=decision_report_to_authority; approval approved, unconsumed, same case, decision_type matches) | Insert decision, set current_disposition_id, consume approval (set executed_at) | `case_decision_recorded` → admin | `awaiting_compliance_action` | `case.decision_recorded` | No-op | 409 |
| C8 | awaiting_compliance_action | resolved | action_completed | Compliance | `case:transition` | `assigned_to == user.id` | `resolution` text | No | Set resolved_at, resolved_by | `case_resolved` → admin | `resolved` | `case.resolved` | No-op | 409 |
| C9 | resolved | closed | close | Compliance | `case:close` | `assigned_to == user.id` | `resolution` non-empty | Approval if risk_level IN (critical, high) | Set closed_at, closed_by; insert audit event | `case_closed` → admin | `closed` | `case.closed` | No-op if already closed | 409 |
| C10 | open | cancelled | cancel | Admin | `case:assign` | none | `cancel_reason` as comment | No | Insert comment | `case_cancelled` → assignee (if any) | `cancelled` | `case.cancelled` | No-op | 409 |
| C11 | assigned | cancelled | cancel | Admin | `case:assign` | none | `cancel_reason` as comment | No | same | same | `cancelled` | `case.cancelled` | No-op | 409 |
| C12 | closed | open | reopen | Admin | `case:reopen` | none | `reopen_reason` | Yes (Compliance approval; Admin requests reopening via `approval:request` with `action_type=case_reopen`, does not vote) | Clear closed_at/closed_by, set reopen_reason, insert assignment_history | `case_reopened` → compliance | `reopened` (event only; state = open) | `case.reopened` | No-op if already open | 409 |

**Forbidden:**
- Admin: `case:decision`, `case:close`, `case:transition` — PROHIBITED
- Analyst: `case:decision`, `case:close`, `case:assign` — PROHIBITED
- Transition from `closed` to any state except `open` via C12: 400
- C6/C7 requires `decided_by != approved_by` for report_to_authority: checked at approval decision step
- Once a decision moves the case out of `decision_pending`, no further decisions are accepted until the case is reopened.
- **Decision reconsideration and superseding is Phase 2D.**

---

## 4. InformationRequest State Machine

### States

```
open → acknowledged → responded → accepted
responded → returned → acknowledged (loop)
open → cancelled
acknowledged → cancelled
```

**States:** `open`, `acknowledged`, `responded`, `accepted`, `returned`, `cancelled`

### Transition Table

| # | From | To | Action | Actor | Perm | OLP | Required Fields | Approval | Side Effects | Notification | Timeline | Audit | Idempotency | Conflict |
|---|------|----|--------|-------|------|-----|-----------------|----------|--------------|--------------|----------|-------|-------------|----------|
| IR1 | open | acknowledged | acknowledge | Assigned Analyst | `info_request:respond` | `assigned_to == user.id` | none | No | insert timeline event, insert notification → compliance IR creator, insert audit outbox event | `ir_acknowledged` → compliance IR creator | `ir_acknowledged` | `ir.acknowledged` | No-op | 409 |
| IR2 | acknowledged | responded | respond | Assigned Analyst | `info_request:respond` | `assigned_to == user.id` | `response_text` non-empty | No | Set responded_at | `ir_responded` → IR creator (compliance) | `ir_responded` | `ir.responded` | No-op | 409 |
| IR3 | responded | accepted | accept | IR Creator (Compliance) | `info_request:accept` | `created_by == user.id` | `acceptance_note` optional | No | Set accepted_at, accepted_by; trigger case C4 if case awaiting_information | none | `ir_accepted` | `ir.accepted` | No-op | 409 |
| IR4 | responded | returned | return | IR Creator (Compliance) | `info_request:return` | `created_by == user.id` | `return_reason` | No | Set returned_at, returned_by | `ir_returned` → analyst | `ir_returned` | `ir.returned` | No-op | 409 |
| IR5 | returned | acknowledged | re_acknowledge | Assigned Analyst | `info_request:respond` | `assigned_to == user.id` | none | No | none | none | `ir_re_acknowledged` | `ir.re_acknowledged` | No-op | 409 |
| IR6 | open | cancelled | cancel | IR Creator or Admin | `info_request:cancel` | `created_by == user.id` OR admin | `cancel_reason` | No | Set cancelled_at, cancelled_by | none | `ir_cancelled` | `ir.cancelled` | No-op | 409 |
| IR7 | acknowledged | cancelled | cancel | IR Creator or Admin | `info_request:cancel` | same | `cancel_reason` | No | same | none | `ir_cancelled` | `ir.cancelled` | No-op | 409 |

**Forbidden:**
- Analyst cannot accept/return own response: `created_by` is compliance; analyst has `info_request:respond` only
- Admin cannot respond to IR (not an analyst): forbidden by PROHIBITED list
- Transition from `accepted` or `cancelled`: 400 terminal states

---

## 5. ApprovalRequest State Machine

### States

```
pending → approved (when approval_count >= required_approvals)
pending → rejected (any approval_decision = rejected)
pending → expired (worker sets after expires_at)
pending → cancelled (requester cancels before any vote)
approved → executed (when gated action performed; not a DB state — executed_at set)
```

**States:** `pending`, `approved`, `rejected`, `expired`, `cancelled`

### Transition Table

| # | From | To | Action | Actor | Perm | OLP | Required Fields | Side Effects | Timeline | Audit |
|---|------|----|--------|-------|------|-----|-----------------|--------------|----------|-------|
| AP1 | (new) | pending | create | Any (per action type) | `approval:request` | Entity must be in state requiring approval | `action_type`, `entity_*`, `rationale` | Compute expires_at; notify eligible approvers | `approval_requested` | `approval.created` |
| AP2 | pending | pending→approved | approve_vote | Compliance (not requester) | `approval:approve` | `approver != requested_by`; not already voted | `decision=approved` | Insert approval_decision; increment approval_count; if count >= required → status=approved | `approval_vote` | `approval.vote` |
| AP3 | pending | rejected | reject_vote | Compliance (not requester) | `approval:approve` | `approver != requested_by`; not already voted | `decision=rejected`, `rationale` | Insert approval_decision; status=rejected | `approval_rejected` | `approval.rejected` |
| AP4 | pending | cancelled | cancel | Requester | `approval:request` | `requested_by == user.id`; no votes yet | none | none | `approval_cancelled` | `approval.cancelled` |
| AP5 | pending | expired | expire | Worker | (system) | `expires_at < NOW()` | none | Status=expired; notify requester | `approval_expired` | `approval.expired` |

**Execution:**
- When `status == approved`, the requesting service checks this before executing the gated action.
- `executed_at` is set in the same transaction as the gated action.
- If `executed_at` already set: idempotent — return 200 with existing outcome, do not re-execute.
- Approval cannot be reused: if `executed_at` set, any subsequent attempt to execute returns 409.

**Forbidden:**
- Requester approving own request: step 7 in `authorise()` — 403
- Analyst voting on any approval (PROHIBITED combo)
- Admin creating approvals for compliance actions (admin requests emergency override separately in Phase 2H)

---

## State Consistency Constraints

These are enforced at application level (not by DB constraints, to avoid complexity in 2B):

1. Only one active (non-cancelled, non-expired) ApprovalRequest per entity+action_type at a time.
2. `compliance_cases.current_disposition_id` must reference a decision where `decision.case_id == compliance_cases.case_id`.
3. Alert's investigation: at most one non-cancelled investigation per alert.
4. IR: at most one non-cancelled IR per (case_id, assigned_to) per status cycle (new IRs OK after prior accepted).
5. `approval_decisions` unique per (approval_request_id, approver_id) — enforced by DB constraint.
