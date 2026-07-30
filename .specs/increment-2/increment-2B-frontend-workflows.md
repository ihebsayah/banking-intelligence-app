# Increment 2B — Frontend Workflows

Framework: existing React + existing design system (Chakra UI / Tailwind as used). No new UI library introduced.

All routes are permission-gated using `PermissionGate`. Backend is the enforcer; frontend gates prevent unnecessary round-trips only.

---

## Route Map

| Path | Component | Permission Required |
|------|-----------|-------------------|
| `/workbench/alerts` | AlertQueue | `alert:read_assigned` |
| `/workbench/alerts/:id` | AlertDetail | `alert:read_assigned` |
| `/workbench/investigations` | InvestigationQueue | `investigation:read_own` |
| `/workbench/investigations/:id` | InvestigationDetail | `investigation:read_own` |
| `/workbench/cases` | CaseQueue | `case:read_assigned` |
| `/workbench/cases/:id` | CaseDetail | `case:read_assigned` |
| `/workbench/cases/:id/decisions` | DecisionForm | `case:decision` |
| `/workbench/information-requests` | IRInbox | `info_request:read_assigned` OR `info_request:read` |
| `/workbench/approvals` | ApprovalQueue | `approval:read` |
| `/workbench/admin/outbox` | OutboxMonitor | `admin:outbox_monitor` |
| `/notifications` | NotificationsPanel | `notification:read` |

---

## 1. Analyst Surfaces

### 1.1 Alert Queue (`/workbench/alerts`)
- Filter bar: severity, status
- Table columns: severity badge, title, assigned_to (self), status, created_at
- Row click → AlertDetail
- Badge on row: `CRITICAL` / `HIGH` in distinct colours
- Empty state: "No alerts assigned to you"
- Permission gate: `alert:read_assigned`

### 1.2 Alert Detail (`/workbench/alerts/:id`)

Sections:
- Header: severity, status badge, title, alert_type, created_at
- Description panel
- Related entity (type + id, no hyperlink in 2B — linkable in 2C)
- Version display (small, for conflict awareness)
- Action bar (permission-gated per button):

| Button | Condition | Permission | Triggers |
|--------|-----------|------------|---------|
| Acknowledge | status=assigned, user=assignee | `alert:acknowledge` | PATCH /acknowledge → refresh |
| Create Investigation | status=acknowledged, no active investigation | `alert:investigate` | Opens InvestigationCreateModal |
| Dismiss | status IN (acknowledged, under_investigation), user=assignee | `alert:dismiss` | Opens DismissModal |
| Escalate | status=under_investigation, investigation exists | `alert:transition` | Opens EscalateModal |

**InvestigationCreateModal:**
- Fields: title (required), description (optional)
- Submit → POST /alerts/:id/investigate
- On 201: navigate to new investigation detail
- On 409: show "Alert was updated — refresh and try again" + Refresh button

**DismissModal:**
- Fields: dismissed_reason (required textarea)
- If severity IN (critical, high): show "Four-eyes approval required" notice
  - Require user to first create ApprovalRequest
  - Show approval status; Submit enabled only when approval_request_id provided and approval.status=approved
- Submit → PATCH /alerts/:id/dismiss
- On 428: show "Approval not yet granted — waiting for compliance officer"

**EscalateModal:**
- Fields: title (required), description (optional), priority (select)
- Submit → POST /alerts/:id/escalate
- On 201: show success toast; navigate to created case

**Conflict UI (409):**
- Toast: "Someone else updated this record. Refreshing..."
- Auto-refetch; re-render action bar with new version
- All pending form inputs preserved where possible

### 1.3 Investigation Queue (`/workbench/investigations`)
- Filter: status
- Columns: title, alert link (id), status, priority, updated_at
- Empty state: "No investigations assigned to you"

### 1.4 Investigation Detail (`/workbench/investigations/:id`)

Tabs: Overview | Findings | Comments | Timeline

**Overview tab:**
- Status badge, priority, assigned_to, started_at, submitted_at
- Associated alert (link to alert detail)
- Action bar:

| Button | Condition | Permission |
|--------|-----------|------------|
| Start | status=open | `investigation:transition` |
| Submit | status=active, findings non-empty | `investigation:transition` |
| Complete | status=active, findings + conclusion | `investigation:transition` |
| Mark Revision Started | status=returned | `investigation:transition` |

**Findings tab:**
- Rich text area for `findings_text` (markdown or plaintext)
- `findings_refs` list: add/remove references [{type, id, description}]
- Conclusion textarea
- Save button → PATCH /investigations/:id
- Auto-save with debounce (3 seconds) — saves locally, syncs on explicit Save
- Evidence section: disabled panel "File evidence upload available in Phase 2D"
- On 409: banner "Conflict detected — your changes may overlap. Refresh to see latest."

**Comments tab:**
- Comment list (paginated)
- Internal comments shown with grey badge (compliance/admin only)
- New comment form: textarea + is_internal toggle (hidden for analyst)
- Submit → POST /investigations/:id/comments

**Timeline tab:**
- Chronological event list: event_type, actor, occurred_at, delta summary
- Paginated

**Returned Investigation handling:**
- When status=returned: prominent yellow banner "Investigation returned — reason: {return_reason}"
- Findings tab enabled for editing
- "Mark as Revised" button in Overview → transition returned → active

### 1.5 IR Inbox (`/workbench/information-requests`)
Analyst view — shows IRs assigned to self.

- Filter: status (open, acknowledged, responded, returned)
- Columns: case link (id), question (truncated), due_date, status badge
- Overdue IRs (due_date < today, status != accepted): red due_date badge
- Empty state: "No information requests assigned to you"

### 1.6 IR Response Form (modal or page from IR Inbox row)

- IR question (read-only)
- Linked case (read-only link)
- Due date (read-only)
- Status badge
- Acknowledge button (if status=open or returned) → PATCH /information-requests/:id/acknowledge
- Response textarea (enabled when status=acknowledged or returned)
- Submit Response → PATCH /information-requests/:id/respond
- If status=returned: "Returned — reason: {return_reason}" banner above response field
- On 409: refresh notice

---

## 2. Compliance Surfaces

### 2.1 Case Queue (`/workbench/cases`)

- Filter: status, risk_level, priority
- Columns: title, status, risk_level, priority, assigned_to (self), target_date, updated_at
- Overdue: target_date < today + status NOT IN (resolved, closed) → row highlight
- Unassigned cases: shown in separate sub-section "Unassigned" (Phase 2E full queue; in 2B admin assigns)
- Permission gate: `case:read_assigned`

### 2.2 Case Detail (`/workbench/cases/:id`)

Tabs: Overview | Investigation | Information Requests | Decisions | Comments | Timeline

**Overview tab:**
- Status badge, risk_level, priority, regulatory_frameworks, target_date
- Assigned analyst (from investigation link)
- Resolution text (editable when status=resolved, before close)
- Action bar:

| Button | Condition | Permission |
|--------|-----------|------------|
| Begin Review | status=assigned | `case:transition` |
| Request Information | status=under_review | `case:transition` → opens IRCreateModal |
| Mark Decision Pending | status=under_review | `case:transition` |
| Mark Action Completed | status=awaiting_compliance_action | `case:transition` |
| Record Decision | status=decision_pending | `case:decision` → navigate to DecisionForm |
| Resolve Case | status=awaiting_compliance_action | `case:transition` |
| Close Case | status=resolved | `case:close` → opens CloseModal |

**IRCreateModal:**
- Fields: assigned analyst (select from users with `info_request:respond`), question (required textarea), due_date (optional)
- Submit → POST /cases/:id/information-requests
- On 201: IR Inbox tab refreshed

**CloseModal (case:close):**
- Resolution text (required if not already set)
- If risk_level IN (critical, high): show "Four-eyes approval required"
  - Show ApprovalRequest status
  - Submit enabled only when approval approved
- Submit → POST /cases/:id/close

**Investigation tab:**
- Linked investigation summary (read-only for compliance)
- Findings text (read-only)
- References list (read-only)
- Conclusion (read-only)
- Button: Return Investigation (if investigation.status=submitted) → PATCH /investigations/:id/transition (target=returned)
- Button: Approve Investigation (if investigation.status=submitted) → PATCH /investigations/:id/transition (target=completed)

**Information Requests tab:**
- List of all IRs for this case
- Status badge per IR
- Row: question (truncated), assigned analyst, due_date, status
- Expand row → IR detail inline
- Accept / Return response buttons per IR (when IR status=responded):
  - Accept → PATCH /information-requests/:id/accept
  - Return → opens ReturnModal (requires return_reason)

**Decisions tab:**
- List of all decisions, newest first
- Decision_type, rationale (read-only), decided_by, decided_at, is_final badge

**Comments tab:**
- Same as investigation comments but entity_type=compliance_case
- Internal comment toggle available to compliance users

### 2.3 Decision Form (`/workbench/cases/:id/decisions`)

- Decision type selector (radio):
  - No Action
  - Warning
  - Enhanced Due Diligence Recommended
  - Report to Authority Recommended ← requires approval badge shown
  - Account Action Recommended
  - Close Case (no_action path)
- Rationale textarea (required)
- If "Report to Authority": show four-eyes approval flow inline
  - "Create Approval Request" button → POST /approval-requests
  - Approval status poll (every 10s or on focus)
  - Submit enabled only when approval approved
- Submit → POST /cases/:id/decisions
- On 201: navigate back to case detail; show success toast "Decision recorded"

### 2.4 Approval Queue (`/workbench/approvals`)
Compliance view — pending approvals where user is eligible approver.

- Filter: action_type, status
- Columns: action_type, entity (type + id), requested_by, rationale, expires_at, approval_count/required
- Row click → Approval Detail modal
- Approval Detail modal:
  - Rationale (read-only)
  - Entity link
  - Existing votes
  - "Approve" / "Reject" buttons
  - Rejection requires rationale field
  - Submit → POST /approval-requests/:id/vote
  - On 409 (already voted): "You have already voted on this request"
  - Cannot vote if `requested_by == user.id` (frontend guard + backend 403)

### 2.5 Case Closure Requiring Approval

Embedded in Close Case modal:
1. If risk_level IN (critical, high): show approval section
2. User clicks "Request Approval" → POST /approval-requests (action_type=case_closure_critical_high)
3. Modal shows live approval status (poll every 10s)
4. When approval.status=approved → "Close Case" button activates
5. Submit → POST /cases/:id/close (with approval_request_id)

---

## 3. Admin Surfaces

### 3.1 Audit Outbox Monitor (`/workbench/admin/outbox`)

- Table: outbox_id (truncated), event_type, entity_type, entity_id, status badge, attempt_count, last_error (truncated), created_at, delivered_at
- Filters: status
- Status badges: pending (blue), delivering (yellow), delivered (green), failed (orange), poison (red)
- Row actions:
  - Poison/Failed rows: "Retry" button → POST /admin/outbox/:id/retry
  - Deliver column: time since created (lag indicator)
- Stats summary bar: pending count, failed count, poison count, avg delivery lag
- Permission gate: `admin:outbox_monitor`

### 3.2 Assignment Recovery

Handled via existing Admin user management page (extend in 2B):
- "Reassign" button on any analyst/compliance user listing
- Opens ReassignModal:
  - From user (pre-filled)
  - Entity type (alerts / investigations / cases)
  - Target user
  - Confirm → PATCH /alerts/:id/assign or /cases/:id/assign
- Used when: user suspended, user deleted, user on leave

---

## 4. Cross-Cutting UI Patterns

### 4.1 Conflict / 409 Handling

All mutation forms:
- Store `expected_version` from last fetch
- On 409: display banner "This record was updated by someone else while you were working. Your changes have not been saved. Refreshing..."
- Auto-refetch entity
- Re-populate form with current data
- User must re-apply changes and resubmit

### 4.2 Notification Bell

Global header:
- Bell icon with unread count badge
- Click → dropdown showing last 10 notifications
- Each notification: title, body (truncated), entity link, time ago
- "Mark all read" button → PATCH /notifications/read-all
- "View all" → /notifications page
- Poll on window focus + 30s interval

### 4.3 Version Display

All detail pages show entity version in small text below title:
`v{version} · updated {relative time}` (e.g., `v4 · 2 minutes ago`)

Helps users identify stale views before submitting.

### 4.4 Permission-Aware Rendering

Buttons/actions not rendered if user lacks permission:
```tsx
<PermissionGate requires="case:decision">
  <Button onClick={openDecisionForm}>Record Decision</Button>
</PermissionGate>
```

Status-gated rendering: even if user has permission, action buttons only render when entity status permits. Both permission AND status conditions required.

### 4.5 Loading States

All list and detail pages:
- Skeleton loaders during initial fetch
- Spinner overlay during mutation (prevents double-submit)
- Disabled action buttons while mutation in flight

### 4.6 Empty States

Every list has:
- Custom empty state message per context (e.g., "No alerts assigned to you", "No information requests pending your response")
- No generic "Nothing here" messages

---

## 5. Postponed UI

| Feature | Phase |
|---------|-------|
| Evidence upload tab | 2D |
| AI suggestion buttons | 2F |
| Email notification settings | 2G |
| Real-time WebSocket updates | 2G |
| Bulk assign | 2E |
| Watchlists | 2D |
| Saved analyses | 2C |
| Remediation tracking | 2D |
| Emergency override request UI | 2H |
| Regulatory reporting integration | 2C |

All postponed features: either hidden or shown as disabled panel with "Available in Phase X" label. No placeholder forms that submit to non-existent endpoints.
