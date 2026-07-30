# Increment 2B — Authorisation Policies

---

## Model Choice

**Model B: One action permission + explicit scope grant.**

Each action maps to exactly one permission code. Scope is a separate check in `authorise()`. No permission variants like `read_own` vs `read` — ownership is evaluated as an object-level policy step, not a different permission code.

Rationale: avoids permission explosion with variants; scope grant is explicit and auditable; ownership check is deterministic from resource fields.

Exception: `investigation:read_own` and `case:read_assigned` are retained as they exist in the current schema seed and distinguish list-access scope for analysts vs compliance. They are treated as permission codes, not model variants.

---

## Permission Codes (Phase 2B)

```
# Workbench gate
workbench:access

# Alert
alert:read_assigned       # list/read alerts assigned to self
alert:read                # list/read all alerts (admin)
alert:assign              # assign alert to user (admin)
alert:acknowledge         # acknowledge own assigned alert
alert:dismiss             # dismiss own assigned alert
alert:investigate         # create investigation from alert
alert:transition          # resolve alert (system-facing)

# Investigation
investigation:read_own        # read investigations assigned to self
investigation:read            # read any investigation (compliance, admin)
investigation:update          # update findings_text, findings_refs, conclusion
investigation:modify_findings # SENSITIVE — same as update but explicit for audit; analyst only
investigation:transition      # start, submit, revise, complete transitions
investigation:assign          # assign investigation (admin) + cancel

# Compliance Case
case:create           # create case (compliance, system via escalation)
case:read_assigned    # read cases assigned to self
case:read             # read any case (admin)
case:transition       # begin_review, request_info, ready_for_decision, action_completed (compliance)
case:decision         # record decision (compliance ONLY — PROHIBITED for admin)
case:close            # close case (compliance ONLY — PROHIBITED for admin)
case:assign           # assign case (admin) + cancel
case:reopen           # reopen closed case (admin, with approval)

# Information Request
info_request:create           # create IR (compliance)
info_request:read_assigned    # read IRs assigned to self (analyst)
info_request:read             # read any IR on owned case (compliance)
info_request:respond          # acknowledge + respond (analyst)
info_request:accept           # accept response (compliance IR creator)
info_request:return           # return response (compliance IR creator)
info_request:cancel           # cancel IR (compliance creator or admin)

# Approval
approval:request      # request approval for gated action
approval:approve      # vote on approval (compliance only)
approval:read         # read approval requests (all roles, own scope)

# Comments
comment:create        # create comment on accessible entity
comment:read          # read public comments on accessible entity
comment:view_internal # read internal comments (compliance, admin)
comment:redact        # redact comment (admin only)

# Timeline
timeline:read         # read timeline of accessible entity

# Notifications
notification:read     # read own notifications
notification:update   # mark own notifications read

# Admin operational
admin:outbox_monitor  # read audit outbox status (admin only)
admin:outbox_retry    # trigger outbox retry (admin only)
```

---

## Role → Permission Matrix

| Permission | Analyst | Compliance | Admin |
|------------|---------|------------|-------|
| `workbench:access` | ✓ | ✓ | ✓ |
| `alert:read_assigned` | ✓ | ✓ | — |
| `alert:read` | — | — | ✓ |
| `alert:assign` | — | — | ✓ |
| `alert:acknowledge` | ✓ | — | — |
| `alert:dismiss` | ✓ | — | ✓ |
| `alert:investigate` | ✓ | — | — |
| `alert:transition` | ✓ | ✓ | — |
| `investigation:read_own` | ✓ | — | — |
| `investigation:read` | — | ✓ | ✓ |
| `investigation:update` | ✓ | — | — |
| `investigation:modify_findings` | ✓ | — | — |
| `investigation:transition` | ✓ | — | — |
| `investigation:assign` | — | — | ✓ |
| `case:create` | — | ✓ | — |
| `case:read_assigned` | ✓ | ✓ | — |
| `case:read` | — | — | ✓ |
| `case:transition` | — | ✓ | — |
| `case:decision` | — | ✓ | ✗ PROHIBITED |
| `case:close` | — | ✓ | ✗ PROHIBITED |
| `case:assign` | — | — | ✓ |
| `case:reopen` | — | — | ✓ |
| `info_request:create` | — | ✓ | — |
| `info_request:read_assigned` | ✓ | — | — |
| `info_request:read` | — | ✓ | ✓ |
| `info_request:respond` | ✓ | — | — |
| `info_request:accept` | — | ✓ | — |
| `info_request:return` | — | ✓ | — |
| `info_request:cancel` | — | ✓ | ✓ |
| `approval:request` | ✓ (for alert:dismiss gated action) | ✓ | — |
| `approval:approve` | ✗ PROHIBITED | ✓ | — |
| `approval:read` | ✓ | ✓ | ✓ |
| `comment:create` | ✓ | ✓ | ✓ |
| `comment:read` | ✓ | ✓ | ✓ |
| `comment:view_internal` | — | ✓ | ✓ |
| `comment:redact` | — | — | ✓ |
| `timeline:read` | ✓ | ✓ | ✓ |
| `notification:read` | ✓ | ✓ | ✓ |
| `notification:update` | ✓ | ✓ | ✓ |
| `admin:outbox_monitor` | — | — | ✓ |
| `admin:outbox_retry` | — | — | ✓ |

---

## Prohibited Combos (Hardcoded in `authorise()`)

These are rejected at step 2, before any permission check, regardless of DB grants.

```python
PROHIBITED: frozenset[tuple[str, str]] = frozenset({
    # Admin SoD
    ('admin', 'case:decision'),
    ('admin', 'case:close'),
    ('admin', 'investigation:modify_findings'),
    ('admin', 'remediation:verify'),       # Phase 2D; blocked in advance
    ('admin', 'evidence:destroy'),         # Phase 2D; blocked in advance
    # Analyst SoD
    ('analyst', 'case:decision'),
    ('analyst', 'case:close'),
    ('analyst', 'case:assign'),
    ('analyst', 'approval:approve'),
    # Legacy role
    ('manager', 'workbench:access'),
    ('manager', 'alert:acknowledge'),
    ('manager', 'investigation:transition'),
    ('manager', 'case:transition'),
    ('manager', 'case:decision'),
    ('manager', 'case:close'),
})
```

---

## Authorise() Evaluation Order (Full Detail)

```
Input: user, action, resource{id, status, assigned_to, scope_id, version}, db, ctx{request_id, ip}

Step 1 — Action known?
  action not in ALL_PERMISSION_CODES → raise 400 "Unknown action"

Step 2 — Prohibited combo?
  (user.role, action) in PROHIBITED → raise 403 "Action forbidden for role"

Step 3 — Permission granted?
  action not in user.effective_permissions → raise 403 "Permission not granted"
  (effective_permissions = role permissions ∪ user.permissions overrides)

Step 4 — Scope check?
  user_scopes = await db.fetch_user_scopes(user.user_id)
  resource_scope = resource['scope_id']
  if resource_scope not in user_scopes AND 'global' not in user_scopes:
    → raise 404 (leakage prevention — resource appears nonexistent)
  if 'global' in user_scopes AND resource_scope not in user_scopes:
    → only allow metadata-only actions (alert:read, case:read without content)
    → for content actions: raise 404

Step 5 — Ownership/assignment?
  if permission is _own or _assigned variant (alert:acknowledge, investigation:transition, etc.):
    if resource['assigned_to'] != user.user_id → raise 404

Step 6 — Workflow state permits action?
  valid = VALID_TRANSITIONS[entity_type][resource['status']][action]
  if not valid → raise 409 "Action not permitted in current state"
  (See state machine tables for valid transitions per status)

Step 7 — Conflict of interest?
  if action in APPROVAL_VOTE_ACTIONS:
    if resource['requested_by'] == user.user_id → raise 403 "Cannot approve own request"
  if action in DECISION_ACTIONS:
    # Analyst cannot be both investigator and compliance decision-maker (different roles; PROHIBITED covers this)

Step 8 — Approval prerequisite?
  if action in APPROVAL_GATED_ACTIONS:
    approval = await db.fetch_active_approval(entity_id=resource['id'], action_type=...)
    if approval is None or approval.status != 'approved' → raise 428 "Approval required"
    if approval.executed_at is not None → raise 409 "Approval already consumed"

Step 9 — Emergency override?
  (Phase 2H — not implemented in 2B)
  if action in OVERRIDEABLE_ACTIONS:
    override = await db.fetch_active_override(user.user_id, action)
    if override and not override.exercised_at:
      → mark exercised, emit outbox event, proceed
      → RETURN (allow)

Step 10 — Default deny
  raise 403 "Access denied"
```

---

## Object-Level Leakage Policy

Resources inaccessible to a user due to scope or assignment return **404**, not 403. This prevents confirming existence of cases/alerts the user should not know about.

Exceptions:
- Admin with `global` scope: receives 403 on content actions (confirms existence for operational purposes, but denies content)
- Auth failures (no token, invalid token): 401 always

---

## Approval-Gated Actions

```python
APPROVAL_GATED_ACTIONS: dict[str, str] = {
    # action: approval_request.action_type
    'alert:dismiss':         'alert_dismissal_critical_high',   # only if severity IN (critical, high)
    'case:close':            'case_closure_critical_high',       # only if risk_level IN (critical, high)
    'case:decision[report]': 'decision_report_to_authority',    # decision_type = report_to_authority_recommended
    'case:reopen':           'case_reopen',                     # always
}
```

Condition check: severity/risk_level evaluated before requiring approval. Low/medium actions are not gated.

---

## Sensitive Permissions (NEVER granted to Admin by default)

```python
SENSITIVE_PERMISSIONS: frozenset[str] = frozenset({
    'case:decision',
    'case:close',
    'investigation:modify_findings',
    'remediation:verify',
    'evidence:destroy',
})
```

These are inserted into `permissions` table but NOT into `role_permissions` for `admin`. No DB path to grant them to admin without changing PROHIBITED hardcode.

---

## Scope Metadata Access for Admin

Admin with `global` scope may read (GET only):
- Alert: `alert_id`, `title`, `severity`, `status`, `assigned_to`, `created_at` — NOT `description`, `dismissed_reason`
- Investigation: `investigation_id`, `title`, `status`, `assigned_to` — NOT `findings_text`, `findings_refs`, `conclusion`
- Case: `case_id`, `title`, `status`, `risk_level`, `assigned_to` — NOT `resolution`, `current_disposition_id`

This is enforced by serialiser field filtering based on `user.role == 'admin' AND resource_scope not in user_scopes`.
