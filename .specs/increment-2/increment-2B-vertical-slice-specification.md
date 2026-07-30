# Increment 2B — Vertical Slice Specification

The first complete operational workflow. No placeholders. Every step from alert creation to case closure is specified, implementable without later phases.

---

## Workflow

```
Alert created/assigned (system or admin)
  → Analyst acknowledges
  → Analyst creates Investigation
  → Analyst records findings and comments
  → Analyst escalates → Compliance Case created
  → Compliance assigns (or auto-assigned)
  → Compliance creates InformationRequest
  → Analyst acknowledges IR
  → Analyst responds to IR
  → Compliance accepts or returns response
  → Compliance records Decision
  → Decision triggers ApprovalRequest (if required)
  → Authorised Compliance Officer approves
  → Approved action executed exactly once
  → Compliance resolves case
  → Compliance closes case
  → Full immutable timeline + audit outbox flushed
```

---

## Included Entities

| Entity | Status |
|--------|--------|
| Alert | Included |
| Investigation | Included |
| ComplianceCase | Included |
| InformationRequest | Included — explicit model, not via Task |
| Decision | Included |
| ApprovalRequest | Included |
| ApprovalDecision | Included |
| Comment | Included |
| ActivityTimelineEntry | Included |
| Notification | Included (in-DB, no email/push) |
| AuditOutboxEvent | Included |
| AssignmentHistory | Included |

## Postponed Entities

| Entity | Postponed to |
|--------|-------------|
| Evidence | Phase 2D — no file upload in 2B; findings/text references allowed |
| RemediationAction | Phase 2D |
| Watchlist / WatchlistItem | Phase 2D |
| SavedAnalysis | Phase 2C |
| Task (generic) | Phase 2G |
| AiAssistance | Phase 2F |
| EmergencyOverride | Phase 2H |

**Evidence impact:** Analyst findings field accepts text and JSON references to external documents. No file upload API or UI in 2B. Evidence upload button is disabled with "Available in Phase 2D" label. No chain-of-custody claims in 2B docs.

**AI impact:** Existing NL-to-SQL agent pipeline is unchanged. No operational AI assistance endpoints in 2B. AI governance boundaries enforced structurally (audit outbox, prohibited combos) but AI suggestion buttons are Phase 2F.

---

## Endpoint Count

**Total Phase 2B endpoints: 44**

Breakdown by domain:

| Domain | Count |
|--------|-------|
| Alerts | 7 |
| Investigations | 5 |
| Cases | 7 |
| Information Requests | 8 |
| Decisions | 2 |
| Approvals | 4 |
| Comments | 3 |
| Timeline | 2 |
| Notifications | 3 |
| Admin (operational) | 3 |
| **Total** | **44** |

Full per-endpoint specification in increment-2B-api-contracts.md.

---

## Transaction Boundary (all mutations)

```python
async with db.transaction():
    # 1. Version check (SELECT FOR UPDATE or WHERE version = expected → 409 if 0 rows)
    # 2. Business mutation (UPDATE/INSERT)
    # 3. INSERT INTO activity_timeline (...)
    # 4. INSERT INTO notifications (...) — if applicable
    # 5. INSERT INTO audit_outbox (...) — idempotency_key computed before tx
    # commit

# After commit — audit worker picks up outbox record asynchronously
```

Audit delivery is NOT in the HTTP response path. The mutation returns 200/201 when the transaction commits. The outbox worker delivers asynchronously. No fire-and-forget HTTP to audit agent from mutation code paths.

---

## AI — Postponed

Operational AI assistance (investigation suggestions, case risk classification, RFI drafts) is postponed to Phase 2F. This decision is final for 2B.

The existing NL-to-SQL agent pipeline (`/query`, `/insights`, etc.) is NOT modified by Phase 2B.

AI governance boundaries enforced in 2B:
- `PROHIBITED` combos in `authorise()` prevent any programmatic bypass
- Audit outbox records every mutation with actor identity
- No string-matching on AI output in 2B (no AI output to match)

---

## Organisational Scope in 2B

- All 2B resources default to `hq_main` scope (single-scope first deployment)
- Scope field exists in schema; multi-scope support activates in 2E
- Policy engine checks scope at step 4; with single scope all users in same scope pass

---

## Four-Eyes Approval in 2B

ApprovalRequest and ApprovalDecision are fully implemented in 2B.

Actions requiring approval in 2B:

| Action | Risk Level | Required Approvers |
|--------|-----------|-------------------|
| Alert dismissal | critical or high | 1 additional compliance officer |
| Case closure | critical or high risk_level | 1 additional compliance officer |
| Decision: report_to_authority_recommended | any | 1 compliance officer (not the recorder) |
| Case reopening | any | 1 compliance officer (admin requests reopening via `approval:request` with `action_type=case_reopen`, does not vote) |

Rules:
- Requester cannot approve own request (step 7 in authorise())
- Approver must have `approval:approve` permission (compliance only in 2B)
- `required_approvals` is stored on ApprovalRequest at creation (configurable per action via DB config table — default values seeded in 0005)
- Approval expires after 72 hours (configurable)
- Rejection requires `rejection_rationale`
- Approved action executed exactly once — idempotency_key on ApprovalDecision
- ApprovalRequest.status transitions to `approved` only when `approval_count >= required_approvals`
- Execution: caller checks ApprovalRequest.status == 'approved' before executing gated action; `authorise()` enforces this at step 8

---

## Notification Delivery in 2B

In-database only. `notifications` table. Frontend polls `GET /api/v1/notifications` on page focus. No WebSocket, no email, no push (Phase 2G+).

Each mutation that triggers a notification inserts a row atomically in the same transaction.

---

## Remarks on Previous Architecture Corrections

| Previous issue | 2B correction |
|----------------|---------------|
| Fire-and-forget HTTP audit | Transactional audit outbox; worker delivers after commit |
| Task used as InformationRequest | Explicit `information_requests` table with full state machine |
| No ApprovalRequest model | ApprovalRequest + ApprovalDecision fully designed |
| `escalated` used inconsistently | `escalated` removed from ComplianceCase status list; see state machines |
| Admin had broad bypass | PROHIBITED combos hardcoded; no admin:* |
| Compliance Manager as 4th role | Approval by other Compliance officer; no new role |
| ON DELETE CASCADE on decisions | RESTRICT; lifecycle via status transitions only |
| ComplianceCase.current_disposition_id FK | Application-level validation: decision must belong to same case |
| No-action decision had no closure path | Explicit transition: decision_pending → resolved (no_action path) |
| Warning/EDD recommendations — no next state | Explicit: decision_pending → awaiting_compliance_action → resolved |
| Reopened as both transient and long-lived | Reopened is a timeline/audit event only, NOT a stored DB state; canonical transition is closed → open |
