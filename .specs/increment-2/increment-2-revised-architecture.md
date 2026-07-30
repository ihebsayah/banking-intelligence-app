# Increment 2 — Revised Architecture

Complete revision addressing all 15 blocking issues.

---

## Blocking Issues Corrected

| # | Issue | Resolution |
|---|-------|-----------|
| 1 | `manager` as silent fourth role | Deprecated: retained in enum/DB as legacy value, zero Inc 2 permissions, migration documented |
| 2 | Admin had compliance authority | Full SoD: `sensitive:*` permissions gated away from admin; emergency override designed |
| 3 | Role-only frontend guards | Central `authorize()` policy engine; frontend uses permission checks, not `requiredRole` arrays |
| 4 | Hard-delete CRUD endpoints | Replaced with archive/cancel/withdraw lifecycle; no `DELETE` for regulated objects |
| 5 | Unsafe evidence design | Full chain-of-custody model; backend-only extraction; protected storage; malware scan |
| 6 | Domain model contradictions | Fixed cardinalities, FK ambiguity, polymorphic constraints, version columns |
| 7 | Incomplete state machines | Explicit transition tables with preconditions, side-effects, forbidden transitions |
| 8 | No AI governance | Operational AI records; advisory-only; no autonomous decisions; `account_freeze`→`recommend` |
| 9 | Audit/timeline/notification inconsistency | Three-layer split; same-transaction writes; no outbox until justified |
| 10 | Unsafe alert engine | Distributed lock, watermark, fingerprint, uniqueness, idempotency |
| 11 | No migration strategy | Alembic plan; versioned; backup/staging/production rollout documented |
| 12 | Narrow workbenches | Expanded to 16+ views per role; postponed items labelled clearly |
| 13 | 42-endpoint first delivery | Scoped to single vertical slice (~12 endpoints); postponed 30 endpoints |
| 14 | Generic API quality | Per-endpoint: policies, schemas, status codes, lock, audit, notification, transaction boundary |
| 15 | Optimistic 26-day estimate | Replaced with 8-phase, 40-60 day estimate; team size, testing, security, hardening |

---

## 1. Revised Active Roles

### Decision: Deprecate `manager`, retain as inactive legacy value

**What changes:**
- `UserRole.MANAGER` stays in the enum — removing it breaks existing tokens in the wild
- `manager` role in the `roles` table stays — already referenced by existing users
- `manager` gets **zero new Inc 2 permissions** in `role_permissions` junction
- `manager` existing permissions (`read:branch_data`, `read:risk_summary`) remain for backward compatibility
- New `user_migrations` table tracks legacy-to-active role migration

**Migration SQL:**
```sql
-- Mark manager as legacy in roles table
UPDATE roles SET description = 'DEPRECATED — Legacy role. No new capabilities.' WHERE role_id = 'manager';

-- Optionally flag existing manager users
ALTER TABLE users ADD COLUMN IF NOTANCE NOT EXISTS legacy_role boolean DEFAULT FALSE;
UPDATE users SET legacy_role = TRUE WHERE role = 'manager';

-- Admin can reassign manager users to analyst or compliance via existing admin UI
```

**Compatibility impact:**
- Existing `manager_001` mock user stays and logs in — sees only old dashboard/report pages
- New Inc 2 routes require active-role permissions; manager has none → 403 on any workbench page
- No token invalidation needed — `manager` role is still in the JWT, it just has no Inc 2 permission grants
- Keycloak mapping `executive_manager` → `manager` continues; admin can reassign users

**Frontend impact:**
- `ProtectedRoute` updated: Inc 2 routes check `hasPermission('workbench:access')` not just role
- `manager` sees no sidebar links to workbenches (permission-gated menu items)
- Old dashboard/report pages remain accessible (unchanged)

---

## 2. Segregation-of-Duties Model

### Admin scope (strictly limited)
```
Admin can:
├── Users, identities, roles, permissions
├── System configuration, feature flags, retention
├── Technical monitoring (services, agents, queues)
├── Audit access (read-only immutable audit)
├── Workflow dictionaries (status lists, transition configs)
├── Assignment recovery (emergency reassign)
├── Agent monitoring and restart
└── Maintenance mode toggle

Admin must NOT:
├── Record a compliance decision
├── Close a compliance case
├── Verify a remediation action
├── Modify investigation findings
├── Destroy evidence
├── Approve regulatory reporting
├── Modify AI governance records
└── Override a compliance officer's decision
```

### Sensitive permission codes (admin-excluded)
```python
SENSITIVE_PERMISSIONS = {
    "case:decision",        # Record compliance decision
    "case:close",           # Close compliance case
    "remediation:verify",   # Verify remediation
    "evidence:destroy",     # Destroy evidence records
    "investigation:modify_findings",  # Change investigation conclusions
    "regulatory:approve",   # Approve regulatory reports
}
```

### Emergency override design

```python
class EmergencyOverride(BaseModel):
    """Time-limited elevation for admin to perform sensitive actions."""
    override_id: UUID
    admin_user_id: str
    sensitive_permission: str       # e.g. "case:close"
    reason: str                     # Required: compliance incident, system emergency, etc.
    second_approver: str            # Must be different compliance officer  
    expires_at: datetime            # Max 24 hours
    is_active: bool
    created_at: datetime
    exercised_at: Optional[datetime]  # When actually used
    audit_event: str                # Full audit trail
```

**Rules:**
1. Admin requests override via `POST /admin/emergency-override` with reason
2. Compliance officer (different person) approves via `PATCH /admin/emergency-override/{id}/approve`
3. Override expires after 24 hours or single use (whichever is sooner)
4. Every override exercise is **immutable-audited** with: actor, override ID, reason, action, timestamp
5. Notification sent to compliance governance group on creation and exercise

---

## 3. Object-Level Authorisation Model

### Central policy function

```python
async def authorise(
    user: User,
    action: str,           # e.g. "case:read", "alert:transition"
    resource: dict,        # The domain object with all context fields
) -> bool:
```

**Policy evaluates in order:**
1. Does user have `admin:*` or `admin:sensitive_override`? → may bypass (with audit)
2. Does user have the granular permission code? → continue, else deny
3. Is user the owner/assignee of the resource? → allow (for owner-scoped actions)
4. Does user's organisational scope match resource's scope? → allow
5. Is resource in a workflow state that permits this action? → continue, else deny
6. Is this a conflict-of-interest (user assigned to entity, trying to approve own work)? → deny
7. Is there an active emergency override for this action? → allow (with audit)
8. Default: deny

### Per-entity rules

| Entity | List | Read | Mutate | Assign | Transition | Internal Comments | Evidence |
|--------|------|------|--------|--------|------------|------------------|----------|
| Alert | `alert:read` (all) / `alert:read_assigned` (own) | Same as list | Owner/assignee + `alert:update` | Admin + `alert:assign` | Owner + transition permission | N/A | N/A |
| Investigation | `investigation:read` / `investigation:read_own` | Same as list | Owner + `investigation:update` / admin no-findings-modify | Admin + `investigation:assign` | Owner + transition permission | Owner + admin (read-only) | Attached to case only |
| Compliance Case | `case:read` / `case:read_assigned` | Same as list | Assignee + `case:update` / admin read-only | Admin + `case:assign` | Assignee + transition permission | Assignee + compliance + admin (read-only) | Case assignee + compliance |
| Decision | N/A (child of case) | Case read permission | Creator only before case close | N/A | N/A | N/A | N/A |
| Remediation | `remediation:read` | Case assignee + compliance | Assignee + `remediation:update` | Admin + `remediation:assign` | Assignee + transition permission | N/A | N/A |
| Evidence | `evidence:read` | Case participants | Creator only (metadata); no replace | N/A | N/A | N/A | Case participants |
| Task | `task:read` / `task:read_assigned` | Same as list | Assignee + `task:update` | Admin + `task:assign` | Assignee + transition permission | N/A | N/A |
| Watchlist | `watchlist:read` | All | Creator + `watchlist:update` | N/A | N/A | N/A | N/A |

### Frontend enforcement

**Replace `ProtectedRoute` role arrays with permission checks:**
```tsx
// OLD (role-based):
<Route path="/cases" element={<ProtectedRoute requiredRole={['compliance', 'admin']}><Cases /></ProtectedRoute>} />

// NEW (permission-based):
<Route path="/cases" element={<PermissionGate requiredPermissions={['case:read_assigned', 'case:read']}><Cases /></ProtectedRoute>} />
```

**`PermissionGate` component:**
```tsx
function PermissionGate({ requiredPermissions, requireAll = false, children }) {
  const { hasPermission, applicationUser } = useAuth();
  const hasAccess = requireAll
    ? requiredPermissions.every(hasPermission)
    : requiredPermissions.some(hasPermission);
  if (!hasAccess) return <Navigate to="/unauthorized" />;
  return <>{children}</>;
}
```

**Sidebar menu gating:**
```tsx
// Conditionally render menu items based on permissions
{hasPermission('case:read_assigned') && (
  <NavItem to="/workbench/cases" label="Compliance Cases" icon={Scale} />
)}
```

---

## 4. Domain Model (Revised)

### Version column on all operational entities
```sql
version INTEGER NOT NULL DEFAULT 1
updated_at TIMESTAMP NOT NULL DEFAULT NOW()
```

**Optimistic concurrency:**
```python
async def update_entity(entity_id, data, expected_version):
    result = await db.execute("""
        UPDATE entity SET ..., version = version + 1, updated_at = NOW()
        WHERE id = $1 AND version = $2
    """, [entity_id, expected_version])
    if result.rowcount == 0:
        raise HTTPException(409, detail="Conflict: entity was modified by another user")
```

### Alert (revised)
```sql
CREATE TABLE alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL,  -- transaction_anomaly, kpi_breach, risk_threshold, pattern_match, system_rule
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical','high','medium','low')),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    source_query_id UUID,
    source_rule_type VARCHAR(50),  -- 'kpi_threshold' | 'compliance_rule' | 'risk_rule'
    source_rule_id VARCHAR(100),   -- generic ref, FK enforced at app level
    related_entity_type VARCHAR(50),
    related_entity_id VARCHAR(100), -- generic; app-level integrity
    status VARCHAR(30) NOT NULL DEFAULT 'new' CHECK (status IN ('new','assigned','acknowledged','under_investigation','escalated','resolved','dismissed','reopened')),
    assigned_to VARCHAR(100) REFERENCES users(user_id),
    resolution_notes TEXT,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100) REFERENCES users(user_id),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Investigation (revised)
```sql
CREATE TABLE investigations (
    investigation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    alert_id UUID REFERENCES alerts(alert_id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','assigned','active','awaiting_information','submitted','returned','escalated','completed','archived','reopened','cancelled')),
    priority VARCHAR(10) NOT NULL CHECK (priority IN ('critical','high','medium','low')),
    assigned_to VARCHAR(100) REFERENCES users(user_id),
    findings JSONB,
    conclusion TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    completed_by VARCHAR(100) REFERENCES users(user_id),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### ComplianceCase (revised)
```sql
CREATE TABLE compliance_cases (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    alert_id UUID REFERENCES alerts(alert_id) ON DELETE SET NULL,
    investigation_id UUID REFERENCES investigations(investigation_id) ON DELETE SET NULL,
    violation_id UUID,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','triage','assigned','under_review','awaiting_information','decision_pending','remediation_required','remediation_in_progress','resolved','closed','reopened','cancelled')),
    priority VARCHAR(10) NOT NULL CHECK (priority IN ('critical','high','medium','low')),
    risk_level VARCHAR(10) CHECK (risk_level IN ('high','medium','low')),
    regulatory_frameworks TEXT[],  -- GDPR, PCI, SOX, AML, KYC
    assigned_to VARCHAR(100) REFERENCES users(user_id),
    current_disposition_id UUID,  -- FK to decisions (the active/final decision)
    target_date DATE,
    resolution TEXT,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100) REFERENCES users(user_id),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Decision (revised: 1:N to ComplianceCase)
```sql
CREATE TABLE decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES compliance_cases(case_id) ON DELETE CASCADE,
    decision_type VARCHAR(30) NOT NULL CHECK (decision_type IN (
        'no_action', 'warning', 'enhanced_due_diligence_recommended',
        'report_to_authority_recommended', 'account_action_recommended', 'case_closed'
    )),
    rationale TEXT NOT NULL,
    decided_by VARCHAR(100) NOT NULL REFERENCES users(user_id),
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_final BOOLEAN NOT NULL DEFAULT FALSE,
    supersedes_decision_id UUID REFERENCES decisions(decision_id),
    version INTEGER NOT NULL DEFAULT 1
);
```

**Note:** `account_freeze` is renamed to `account_action_recommended`.
Actual account freeze is an **external execution** governed by a separate integration.

### Evidence (revised — chain of custody)
```sql
CREATE TABLE evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES compliance_cases(case_id) ON DELETE CASCADE,
    investigation_id UUID REFERENCES investigations(investigation_id) ON DELETE SET NULL,
    original_filename VARCHAR(500) NOT NULL,
    detected_mime_type VARCHAR(100),
    file_size_bytes BIGINT,
    sha256_hash VARCHAR(64) NOT NULL,
    storage_key VARCHAR(500) NOT NULL,  -- internal object store key
    encryption_status VARCHAR(20) DEFAULT 'aes256' CHECK (encryption_status IN ('aes256', 'none', 'pending')),
    uploaded_by VARCHAR(100) NOT NULL REFERENCES users(user_id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source VARCHAR(50) DEFAULT 'upload' CHECK (source IN ('upload', 'system_generated', 'external_import', 'ai_extracted')),
    classification VARCHAR(50) DEFAULT 'unclassified' CHECK (classification IN ('unclassified','internal','confidential','regulated','legal_hold')),
    supersedes_evidence_id UUID REFERENCES evidence(evidence_id),
    retention_policy VARCHAR(50) DEFAULT 'standard' CHECK (retention_policy IN ('standard','extended','permanent')),
    legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    malware_scan_status VARCHAR(20) DEFAULT 'pending' CHECK (malware_scan_status IN ('pending','clean','infected','skipped')),
    extraction_status VARCHAR(20) DEFAULT 'pending' CHECK (extraction_status IN ('pending','extracted','failed','confirmed')),
    extraction_text_hash VARCHAR(64),  -- hash of extracted text for integrity
    is_redacted BOOLEAN NOT NULL DEFAULT FALSE,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### AiAssistance (new — operational AI record)
```sql
CREATE TABLE ai_assistance (
    assistance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL,  -- alert, investigation, case, evidence, report
    entity_id VARCHAR(100) NOT NULL,
    agent_name VARCHAR(100) NOT NULL,  -- e.g. insights_agent, compliance_agent
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    prompt_reference TEXT,              -- summary of what was asked (not raw prompt)
    source_context JSONB,               -- what data was sent to the agent
    generated_result TEXT,
    confidence DECIMAL(5,4),            -- 0.0000 to 1.0000
    requesting_user VARCHAR(100) NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latency_ms INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'success' CHECK (status IN ('success','failure','partial')),
    human_status VARCHAR(20) DEFAULT 'pending' CHECK (human_status IN ('pending','accepted','rejected','partially_used','not_reviewed')),
    human_reviewer VARCHAR(100) REFERENCES users(user_id),
    human_reviewer_note TEXT,
    reviewed_at TIMESTAMPTZ
);
```

### RemediationAction (revised)
```sql
CREATE TABLE remediation_actions (
    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES compliance_cases(case_id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL CHECK (action_type IN (
        'enhanced_monitoring', 'training', 'process_change',
        'system_update', 'policy_update', 'account_action_recommended'
    )),
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','verified','superseded')),
    assigned_to VARCHAR(100) REFERENCES users(user_id),
    verified_by VARCHAR(100) REFERENCES users(user_id),
    target_date DATE,
    completed_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Task (revised — no hard delete)
```sql
CREATE TABLE tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN ('alert','investigation','compliance_case','remediation','evidence','other')),
    entity_id VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','verified','cancelled','superseded')),
    priority VARCHAR(10) NOT NULL CHECK (priority IN ('critical','high','medium','low')),
    assigned_to VARCHAR(100) REFERENCES users(user_id),
    assigned_by VARCHAR(100) NOT NULL REFERENCES users(user_id),
    is_request_for_information BOOLEAN NOT NULL DEFAULT FALSE,
    target_date DATE,
    completed_at TIMESTAMPTZ,
    completed_by VARCHAR(100) REFERENCES users(user_id),
    sort_order INTEGER DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Comment (revised)
```sql
CREATE TABLE comments (
    comment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN ('alert','investigation','compliance_case','task','evidence','remediation')),
    entity_id VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    author_id VARCHAR(100) NOT NULL REFERENCES users(user_id),
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    is_redacted BOOLEAN NOT NULL DEFAULT FALSE,
    redacted_at TIMESTAMPTZ,
    redacted_by VARCHAR(100) REFERENCES users(user_id),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Watchlist, WatchlistItem, SavedAnalysis, Notification, ActivityTimelineEntry
(Minor additions: `version` column, `cancelled`/`superseded` status values, `deactivated_at` on watchlist. Full DDL in migration scripts.)

### AI governance rules (application-enforced)
```python
AI_PROHIBITED_ACTIONS = [
    "case:close",
    "case:decision",
    "remediation:verify",
    "evidence:destroy",
    "account:freeze",        # account_action_recommended is advisory
    "user:suspend",
    "permission:modify",
    "record:delete",
]
```

Every AI agent response that matches an action in `AI_PROHIBITED_ACTIONS` is **rejected by the gateway** with `{"error": "AI_CANNOT_PERFORM", "message": "This action requires human authorisation."}`.

---

## 5. Revised State Machines

### Alert State Machine

```
[new] ──assign──→ [assigned] ──acknowledge──→ [acknowledged]
  │                                              │
  │                                              ├──investigate──→ [under_investigation]
  │                                              │                    │
  │                                              │                    ├──escalate──→ [escalated]
  │                                              │                    │                │
  │                                              │                    │                └──resolve──→ [resolved]
  │                                              │                    │
  │                                              │                    └──resolve──→ [resolved]
  │                                              │
  │                                              └──dismiss──→ [dismissed]
  │
  [any] ──reopen──→ [reopened] ──assign──→ [assigned]
```

| From | To | Actor | Permission | Preconditions | Side Effects |
|------|----|-------|-----------|---------------|-------------|
| new | assigned | System/Admin | `alert:assign` | alert exists | Notification to assignee, timeline entry |
| assigned | acknowledged | Assignee | `alert:acknowledge` | user == assigned_to | Timeline entry |
| acknowledged | under_investigation | Assignee | `alert:investigate` | user == assigned_to | Investigation created, timeline entry |
| acknowledged | dismissed | Assignee/Admin | `alert:dismiss` | user == assigned_to OR admin | Resolution notes required, timeline entry |
| under_investigation | escalated | Assignee | `alert:escalate` | Investigation exists | Compliance case created, notification to compliance |
| under_investigation | resolved | Assignee | `alert:transition` | Investigation completed | Alert closed, notification |
| escalated | resolved | Compliance | `case:close` | Case closed | Notification |
| dismissed | reopened | Admin | `alert:transition` | Four-eyes if regulatory | Notification |
| resolved | reopened | Admin | `alert:transition` | Four-eyes if regulatory | Notification |

**Four-eyes requirement:** Dismissing a `critical` or `high` severity alert requires approval from a second analyst or compliance officer.

### Investigation State Machine

```
[draft] ──assign──→ [assigned] ──start──→ [active]
  │                    │                      │
  │                    │                      ├──request_info──→ [awaiting_information] ──respond──→ [active]
  │                    │                      │
  │                    │                      ├──submit──→ [submitted] ──return──→ [returned] ──revise──→ [active]
  │                    │                      │                       │
  │                    │                      │                       └──approve──→ [completed]
  │                    │                      │
  │                    │                      ├──escalate──→ [escalated] ──resolve──→ [completed]
  │                    │                      │
  │                    │                      └──complete──→ [completed] ──archive──→ [archived]
  │                    │                                      │
  │                    │                                      └──reopen──→ [active]
  │                    │
  │                    └──cancel──→ [cancelled]
  │
  [any] ──reopen──→ [reopened] ──assign──→ [assigned]
```

| From | To | Actor | Permission | Required Fields | Side Effects |
|------|----|-------|-----------|----------------|-------------|
| draft | assigned | Admin | `investigation:assign` | assigned_to | Notification |
| assigned | active | Assignee | `investigation:transition` | — | started_at set, timeline |
| active | awaiting_information | Assignee | `investigation:transition` | description of request | Task created (is_request_for_information=true), notification |
| awaiting_information | active | Assignee | `investigation:transition` | response in comments | Timeline entry |
| active | submitted | Assignee | `investigation:transition` | findings (any) | Notification to reviewer |
| active | completed | Assignee | `investigation:transition` | findings, conclusion | Timeline, notifications |
| active | escalated | Assignee | `investigation:transition` | escalation reason | Compliance case created |
| submitted | completed | Compliance/Admin | `investigation:transition` | — | Verification, timeline |
| submitted | returned | Compliance/Admin | `investigation:transition` | return reason | Notification to assignee |
| returned | active | Assignee | `investigation:transition` | — | Timeline |
| completed | archived | Assignee | `investigation:archive` | — | Read-only after archive |
| completed | active | Admin | `investigation:transition` | — | Four-eyes if regulatory |
| active | cancelled | Admin | `investigation:transition` | reason | Notification |

### Compliance Case State Machine

```
[draft] ──submit──→ [triage] ──assign──→ [assigned]
  │                    │                    │
  │                    │                    ├──review──→ [under_review] ──request_info──→ [awaiting_information] ──info_received──→ [under_review]
  │                    │                    │                       │
  │                    │                    │                       ├──decision_pending──→ [decision_pending] ──decision_recorded──→ [remediation_required]
  │                    │                    │                       │                                                    │
  │                    │                    │                       │                                                    ↓
  │                    │                    │                       │                                          [remediation_in_progress]
  │                    │                    │                       │                                                    │
  │                    │                    │                       │                                          all_remediated──→ [resolved] ──close──→ [closed]
  │                    │                    │                       │
  │                    │                    │                       └──escalate──→ [escalated] ──resolve──→ [resolved] ──close──→ [closed]
  │                    │                    │
  │                    │                    └──cancel──→ [cancelled]
  │                    │
  │                    └──(auto-escalate on SLA breach)
  │
  [closed] ──reopen──→ [reopened] ──assign──→ [assigned]
  [cancelled] ──reopen──→ [reopened]
```

| From | To | Actor | Permission | Preconditions | Side Effects |
|------|----|-------|-----------|---------------|-------------|
| draft | triage | Creator | `case:create` | — | Timeline entry |
| triage | assigned | Admin | `case:assign` | Risk level set | Notification |
| assigned | under_review | Assignee | `case:transition` | — | Timeline |
| under_review | awaiting_information | Assignee | `case:transition` | — | Task created (RFI), notification |
| awaiting_information | under_review | Assignee | `case:transition` | Response received | Timeline |
| under_review | decision_pending | Assignee | `case:transition` | All evidence reviewed, recommendation ready | Notification |
| decision_pending | remediation_required | Compliance | `case:decision` | Decision recorded, decision_type != case_closed | Remediation actions created, notifications |
| decision_pending | resolved | Compliance | `case:decision` | Decision recorded, decision_type = case_closed | Case resolves, notifications |
| remediation_required | remediation_in_progress | Compliance | `case:transition` | Remediation actions assigned | Notifications |
| remediation_in_progress | resolved | Compliance | `case:transition` | All remediations verified | Timeline |
| resolved | closed | Compliance | `case:close` | Resolution documented | Immutable after close |
| escalated | resolved | Compliance/Admin | `case:transition` | Escalation reason addressed | Timeline |
| closed | reopened | Admin | `case:transition` | Four-eyes, reason documented | Notification to compliance |
| under_review | escalated | Assignee | `case:escalate` | Escalation reason | Notification to admin |

**Four-eyes requirements:**
- Closing a `critical` or `high` risk case requires two compliance officer approvals
- Recording a decision with `report_to_authority_recommended` requires compliance manager approval
- Reopening a `closed` or `cancelled` case requires admin + compliance officer

---

## 6. Revised Permissions

### New permission codes (operational)

```
# Workbench access (gate)
workbench:access                        # Can see workbenches at all

# Alert
alert:read
alert:read_assigned
alert:acknowledge
alert:dismiss
alert:investigate
alert:escalate
alert:configure
alert:reopen

# Investigation
investigation:create
investigation:read
investigation:read_own
investigation:update
investigation:modify_findings          # SENSITIVE — admin excluded
investigation:delete_or_archive        # archive only (no hard delete)
investigation:assign
investigation:transition
investigation:reopen

# Case
case:create
case:read
case:read_assigned
case:update
case:transition
case:escalate
case:close                             # SENSITIVE — admin excluded
case:decision                          # SENSITIVE — admin excluded
case:assign
case:delete_or_archive                 # archive only
case:reopen

# Evidence
evidence:create
evidence:read
evidence:update_metadata               # no replace, no hard delete
evidence:destroy                       # SENSITIVE — admin excluded, requires legal hold check
evidence:classify                      # Set classification level

# Remediation
remediation:create
remediation:read
remediation:update
remediation:verify                     # SENSITIVE — admin excluded
remediation:delete_or_supersede        # supersede only

# Decision
decision:create                        # alias for case:decision
decision:read
decision:supersede

# Watchlist
watchlist:create
watchlist:read
watchlist:update
watchlist:deactivate                   # no delete
watchlist:add_item
watchlist:remove_item

# Saved Analysis
saved_analysis:create
saved_analysis:read_own
saved_analysis:read
saved_analysis:update
saved_analysis:delete_or_archive
saved_analysis:share
saved_analysis:schedule

# Task
task:create
task:read
task:read_assigned
task:update
task:transition
task:assign
task:verify
task:cancel
task:reopen

# Notification
notification:read
notification:update

# Comment
comment:create
comment:read
comment:delete_or_redact
comment:view_internal

# Timeline
timeline:read

# Admin (sensitive overrides)
admin:sensitive_override               # Emergency override — audited separately
admin:override_approve                 # Approve someone else's override

# AI
ai:request_suggestion
ai:request_classification
ai:accept_result
ai:reject_result
```

### Role → Permission mapping (revised)

| Permission | Analyst | Compliance | Admin |
|-----------|---------|-----------|-------|
| `workbench:access` | ✓ | ✓ | ✓ |
| `alert:read_assigned` | ✓ | ✓ | — |
| `alert:read` | — | — | ✓ |
| `alert:acknowledge` | ✓ | ✓ | ✓ |
| `alert:dismiss` | ✓ | — | ✓ (via override if four-eyes) |
| `alert:escalate` | ✓ | ✓ | ✓ |
| `alert:investigate` | ✓ | ✓ | ✓ |
| `alert:configure` | — | — | ✓ |
| `alert:reopen` | — | — | ✓ |
| `investigation:create` | ✓ | — | ✓ |
| `investigation:read_own` | ✓ | — | — |
| `investigation:read` | — | ✓ (linked to case) | ✓ (read-only) |
| `investigation:update` | ✓ | — | — |
| `investigation:modify_findings` | ✓ | — | — |
| `investigation:delete_or_archive` | — | — | ✓ |
| `investigation:assign` | — | — | ✓ |
| `investigation:transition` | ✓ | — | — |
| `investigation:reopen` | — | — | ✓ |
| `case:create` | — | ✓ | — |
| `case:read_assigned` | ✓ | ✓ | — |
| `case:read` | — | — | ✓ |
| `case:update` | — | ✓ | — |
| `case:transition` | — | ✓ | — |
| `case:escalate` | ✓ | ✓ | ✓ |
| `case:close` | — | ✓ | — |
| `case:decision` | — | ✓ | — |
| `case:assign` | — | — | ✓ |
| `case:delete_or_archive` | — | — | ✓ |
| `case:reopen` | — | — | ✓ |
| `evidence:create` | ✓ | ✓ | ✓ |
| `evidence:read` | ✓ | ✓ | ✓ |
| `evidence:update_metadata` | — | ✓ | — |
| `evidence:destroy` | — | — | — (requires override + legal hold check) |
| `evidence:classify` | — | ✓ | — |
| `remediation:create` | — | ✓ | — |
| `remediation:read` | — | ✓ | ✓ |
| `remediation:update` | — | ✓ | — |
| `remediation:verify` | — | ✓ | — |
| `remediation:delete_or_supersede` | — | ✓ | — |
| `watchlist:create` | — | ✓ | ✓ |
| `watchlist:read` | ✓ | ✓ | ✓ |
| `watchlist:update` | — | ✓ | — |
| `watchlist:deactivate` | — | ✓ | ✓ |
| `watchlist:add_item` | — | ✓ | ✓ |
| `watchlist:remove_item` | — | ✓ | ✓ |
| `saved_analysis:create` | ✓ | — | ✓ |
| `saved_analysis:read_own` | ✓ | — | — |
| `saved_analysis:read` | — | — | ✓ |
| `saved_analysis:update` | ✓ | — | ✓ |
| `saved_analysis:delete_or_archive` | ✓ | — | ✓ |
| `saved_analysis:share` | ✓ | — | ✓ |
| `saved_analysis:schedule` | ✓ | — | ✓ |
| `task:create` | ✓ | ✓ | ✓ |
| `task:read_assigned` | ✓ | ✓ | — |
| `task:read` | — | — | ✓ |
| `task:update` | ✓ | ✓ | ✓ |
| `task:transition` | ✓ | ✓ | ✓ |
| `task:assign` | — | — | ✓ |
| `task:verify` | — | ✓ | — |
| `task:cancel` | — | — | ✓ |
| `notification:read` | ✓ | ✓ | ✓ |
| `notification:update` | ✓ | ✓ | ✓ |
| `comment:create` | ✓ | ✓ | ✓ |
| `comment:read` | ✓ | ✓ | ✓ |
| `comment:delete_or_redact` | — | — | ✓ (redact only, no hard delete) |
| `comment:view_internal` | — | ✓ | ✓ |
| `timeline:read` | ✓ | ✓ | ✓ |
| `ai:request_suggestion` | ✓ | ✓ | ✓ |
| `ai:request_classification` | ✓ | ✓ | ✓ |
| `ai:accept_result` | ✓ | ✓ | ✓ |
| `ai:reject_result` | ✓ | ✓ | ✓ |

---

## 7. Revised APIs for First Vertical Slice

### Scope: The complete alert→case→decision workflow

**12 endpoints** — everything needed for the first slice.

#### Alerts

| Method | Path | Permission | Object Policy | Request | Response | Status Codes |
|--------|------|-----------|---------------|---------|----------|-------------|
| GET | `/api/v1/alerts/assigned` | `alert:read_assigned` | Own only | `?status=&severity=&page=&per_page=` | `{data: [...], pagination}` | 200, 403 |
| GET | `/api/v1/alerts/{id}` | `alert:read_assigned` | Own or admin | — | `{data: Alert}` | 200, 403, 404 |
| PATCH | `/api/v1/alerts/{id}/acknowledge` | `alert:acknowledge` | Must be assignee | `{expected_version}` | `{data: Alert}` | 200, 400, 403, 404, 409 |
| PATCH | `/api/v1/alerts/{id}/dismiss` | `alert:dismiss` | Assignee (or admin via override) | `{reason, expected_version}` | `{data: Alert}` | 200, 400, 403, 404, 409 |
| POST | `/api/v1/alerts/{id}/investigate` | `alert:investigate` | Assignee | `{title, description, expected_version}` | `{data: Investigation}` | 201, 400, 403, 404, 409 |

#### Investigations

| Method | Path | Permission | Object Policy | Request | Response | Status Codes |
|--------|------|-----------|---------------|---------|----------|-------------|
| GET | `/api/v1/investigations/assigned` | `investigation:read_own` | Own only | `?status=&page=&per_page=` | `{data: [...], pagination}` | 200, 403 |
| GET | `/api/v1/investigations/{id}` | `investigation:read` | Own, linked case participant, or admin | — | `{data: Investigation}` | 200, 403, 404 |
| PATCH | `/api/v1/investigations/{id}/status` | `investigation:transition` | Must be assignee | `{status, expected_version, ...}` | `{data: Investigation}` | 200, 400, 403, 404, 409 |
| PATCH | `/api/v1/investigations/{id}` | `investigation:update` | Must be assignee (findings) | `{findings, conclusion, expected_version}` | `{data: Investigation}` | 200, 400, 403, 404, 409 |

#### Cases

| Method | Path | Permission | Object Policy | Request | Response | Status Codes |
|--------|------|-----------|---------------|---------|----------|-------------|
| POST | `/api/v1/alerts/{id}/escalate` | `alert:escalate` | Must be alert assignee | `{title, description, expected_version}` | `{data: ComplianceCase}` | 201, 400, 403, 404, 409 |
| GET | `/api/v1/cases/assigned` | `case:read_assigned` | Own only | `?status=&page=&per_page=` | `{data: [...], pagination}` | 200, 403 |
| GET | `/api/v1/cases/{id}` | `case:read_assigned` | Own, or admin | — | `{data: Case}` | 200, 403, 404 |
| PATCH | `/api/v1/cases/{id}/status` | `case:transition` | Must be assignee | `{status, expected_version, ...}` | `{data: Case}` | 200, 400, 403, 404, 409 |

#### Decisions

| Method | Path | Permission | Object Policy | Request | Response | Status Codes |
|--------|------|-----------|---------------|---------|----------|-------------|
| POST | `/api/v1/cases/{id}/decisions` | `case:decision` | Must be case assignee, compliance only | `{decision_type, rationale, expected_version}` | `{data: Decision}` | 201, 400, 403, 404, 409 |

#### Comments

| Method | Path | Permission | Object Policy | Request | Response | Status Codes |
|--------|------|-----------|---------------|---------|----------|-------------|
| GET | `/{entity_type}/{entity_id}/comments` | `comment:read` | Entity read permission | `?page=&per_page=` | `{data: [...], pagination}` | 200, 403, 404 |
| POST | `/{entity_type}/{entity_id}/comments` | `comment:create` | Entity read permission | `{content, is_internal}` | `{data: Comment}` | 201, 400, 403, 404 |

**entity_type:** alerts, investigations, cases, tasks, evidence

#### Timeline

| Method | Path | Permission | Object Policy | Response | Status Codes |
|--------|------|-----------|---------------|----------|-------------|
| GET | `/{entity_type}/{entity_id}/timeline` | `timeline:read` | Entity read permission | `{data: [...]}` | 200, 403, 404 |

### Response envelope (unchanged — matches existing conventions)
```json
{
    "status": "success",
    "data": { ... },
    "pagination": { "page": 1, "per_page": 20, "total": 100, "total_pages": 5 }
}
```

### Transaction boundaries (per mutation)
```python
async with db.transaction():
    # 1. Update entity (with version check → 409 if stale)
    # 2. Create BusinessTimelineEntry
    # 3. Create Notification (if applicable)
    # 4. Append to ImmutableAuditLog (via HTTP to audit-agent — fire-and-forget, non-fatal)
```

### Postponed endpoints (30+ endpoints for later phases)
- Evidence upload/download (Phase 2D)
- Remediation CRUD (Phase 2D)
- Watchlists CRUD (Phase 2D)
- Saved Analysis CRUD (Phase 2C)
- All admin CRUD endpoints (Phase 2E)
- Notifications list/mark-read (Phase 2G)
- AI assistance history (Phase 2F)
- Full-text search on all entities

---

## 8. Revised Workbenches

### Analyst Workbench
| View | First Slice | Postponed |
|------|-------------|-----------|
| Alerts Inbox (assigned) | ✓ | — |
| Alert Detail | ✓ | — |
| My Investigations | ✓ | — |
| Investigation Detail | ✓ | — |
| Investigation Create | ✓ (from alert) | — |
| Findings & Hypotheses | ✓ (basic JSON) | Structured template |
| AI Assistance History | — | Phase 2F |
| Morning Work Queue | — | Phase 2C |
| Returned Investigations | ✓ | — |
| My Tasks | — | Phase 2G |
| Requests for Information | ✓ (via tasks) | Dedicated view |
| Customer Investigation View | — | Phase 2C |
| Transaction Investigation View | — | Phase 2C |
| Portfolio Analysis | — | Phase 2C |
| Comparison Workspace | — | Phase 2C |
| Evidence (read-only, case-linked) | — | Phase 2D |
| Saved Analyses | — | Phase 2C |
| Draft Reports | — | Phase 2C |
| Follow-ups | — | Phase 2G |

### Compliance Workbench
| View | First Slice | Postponed |
|------|-------------|-----------|
| My Queue (assigned cases) | ✓ | — |
| Case Detail | ✓ | — |
| Decision Record | ✓ | — |
| Unassigned Queue | — | Phase 2D |
| Awaiting Information | ✓ | — |
| Decision Pending | ✓ | — |
| Approval Queue (four-eyes) | — | Phase 2H |
| Regulatory Deadlines | — | Phase 2D |
| Overdue Cases | — | Phase 2D |
| Remediation Monitoring | — | Phase 2D |
| Escalations | ✓ | — |
| Returned Cases | ✓ | — |
| Watchlists | — | Phase 2D |
| Regulatory Reporting | — | Phase 2C (existing reports tab) |
| Workload & SLA View | — | Phase 2G |
| AI Assistance History | — | Phase 2F |
| Evidence Upload & Review | — | Phase 2D |

### Admin Workbench
| View | First Slice | Postponed |
|------|-------------|-----------|
| Users (existing) | ✓ | — |
| Roles and Permissions (existing) | ✓ | — |
| Audit Explorer (existing) | ✓ | — |
| Identity Links | — | Phase 2E |
| Organisational Scope | — | Phase 2E |
| Keycloak Health | — | Phase 2E |
| API and Service Health (exists partially) | ✓ | — |
| Agent Monitor (exists) | ✓ | — |
| Job and Queue Monitor | — | Phase 2E |
| Access Anomalies | — | Phase 2H |
| Workflow Dictionaries | — | Phase 2E |
| Alert Rules | — | Phase 2E |
| Notification Rules | — | Phase 2E |
| Feature Flags | — | Phase 2E |
| Retention & Legal Hold Config | — | Phase 2H |
| Model Configuration & Limits | — | Phase 2F |
| Maintenance Mode | — | Phase 2E |
| Emergency Override Requests | — | Phase 2H |

---

## 9. Evidence and Chain-of-Custody Design

### Upload flow
```
[User] Uploads file via frontend
    → POST /api/v1/cases/{id}/evidence (multipart)
    → Backend:
        1. Validate file type, size (< 50MB for now)
        2. Generate SHA-256 hash of file bytes
        3. Store file in protected local storage (/data/evidence/{case_id}/{evidence_id}/{filename})
           - Not publicly served. Nginx location blocked.
           - Served via X-Accel-Redirect or signed URL only
        4. Record metadata in evidence table
        5. Initiate async malware scan (ClamAV via subprocess or API)
           - While scanning: status = malware_scan_status='pending'
           - Result: clean | infected | skipped (if scanner unavailable)
        6. If clean: trigger async extraction (text/OCR for documents)
           - extraction_status = 'pending' → 'extracted' | 'failed'
        7. If infected: mark evidence, notify admin, block download
        8. Return { evidence_id, sha256_hash, status: 'stored' }
```

### Storage (first deployment)
- Location: `docker volume evidence_data:/data/evidence/{case_id}/{evidence_id}/{filename}`
- Access: Only through API endpoint with proper authz
- Encryption: AES-256 at rest (application-level encrypt before write, decrypt on read)
- No public directory, no Nginx static serving

### Access audit
Every evidence read/write creates an `ActivityTimelineEntry` AND immutable audit log entry with:
- `evidence_id`, `user_id`, `action` (viewed, downloaded, uploaded, classified), `timestamp`, `ip_address`

### Legal hold
- `legal_hold = TRUE` prevents any lifecycle transition (including redaction and destruction)
- Setting legal hold requires `evidence:classify` permission
- Legal hold is cleared by compliance officer via explicit action with reason

---

## 10. AI Governance Design

### Operational AI records
Every AI interaction from a workbench creates an `ai_assistance` record.

### Flow
```
[User action] (e.g. "get suggestions" button on investigation page)
    → Frontend calls POST /api/v1/ai/investigation-suggestions
    → Backend:
        1. Creates ai_assistance record with status='pending'
        2. Forwards to insights_agent
        3. Records result, latency, confidence
        4. Returns to frontend
        5. User accepts/rejects/partially_uses
        6. Frontend calls PATCH /api/v1/ai/assistance/{id}
        7. Backend updates human_status
```

### Advisory-only enforcement
```python
# In API gateway, before forwarding any AI response to a mutation endpoint:
for action in AI_PROHIBITED_ACTIONS:
    if response_body.get("action") == action:
        logger.warning("AI attempted prohibited action", extra={"agent": agent_name, "action": action})
        return {"error": "AI_CANNOT_PERFORM", "message": "This action requires human authorisation."}
```

### Renamed operational concepts
| Old (in docs) | New (in code) | Rationale |
|---------------|---------------|-----------|
| `account_freeze` | `account_action_recommended` | AI and compliance can recommend; execution is a separate governed process |
| `report_to_authority` | `report_to_authority_recommended` | Same — recommendation vs execution |
| "AI decides" | "AI suggests" | Consistent language across UI and docs |
| "Auto-close" | "Auto-suggest closure" | AI never closes autonomously |

---

## 11. Audit and Timeline Design

### Three-layer observability

| Layer | Name | Stores | Retention | Who sees it | Consistency |
|-------|------|--------|-----------|-------------|-------------|
| 1 | Business Timeline | `activity_timeline` (main DB) | Life of entity | All users with entity access | Same transaction |
| 2 | Immutable Audit | `audit_logs` (audit DB) | Regulatory (7+ years) | Admin, compliance | Fire-and-forget HTTP |
| 3 | Application Logs | stdout / ELK | 30 days | Operations | Best effort |

### Business Timeline
```sql
CREATE TABLE activity_timeline (
    timeline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,         -- e.g. 'status_changed', 'assigned', 'comment_added'
    actor_id VARCHAR(100) NOT NULL REFERENCES users(user_id),
    old_value TEXT,                        -- JSON string of old state
    new_value TEXT,                        -- JSON string of new state
    metadata JSONB,                        -- Additional context
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_timeline_entity ON activity_timeline(entity_type, entity_id);
CREATE INDEX idx_timeline_created ON activity_timeline(created_at DESC);
```

### Immutable Audit (extend existing `audit_logs`)
Add columns:
```sql
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entity_type VARCHAR(50);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entity_id VARCHAR(100);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS operation VARCHAR(50);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS old_values_hash VARCHAR(64);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS new_values_hash VARCHAR(64);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS request_id VARCHAR(100);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS source_ip VARCHAR(45);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS override_context JSONB;  -- emergency override info
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS reason TEXT;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS version_at_mutation INTEGER;
```

### Transactional consistency
```python
async def mutate_with_audit(entity_type, entity_id, mutation_fn, user, request):
    """Execute mutation, timeline, notification in a single DB transaction.
    Audit log is sent via HTTP (non-fatal, fire-and-forget)."""
    async with db.transaction():
        # 1. Execute the mutation (with version check)
        result = await mutation_fn()
        
        # 2. Create business timeline entry
        await db.execute("""
            INSERT INTO activity_timeline (entity_type, entity_id, action, actor_id, old_value, new_value, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, [entity_type, entity_id, action, user.user_id, old_val, new_val, metadata])
        
        # 3. Create notification if needed
        if should_notify:
            await db.execute("""
                INSERT INTO notifications (user_id, type, title, body, entity_type, entity_id)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, [target_user, notif_type, title, body, entity_type, entity_id])
    
    # 4. Immutable audit — outside transaction, non-fatal
    try:
        await send_audit_log(AuditLogEntry(
            user_id=user.user_id,
            user_role=user.user_role,
            action=f"{entity_type}:{operation}",
            entity_type=entity_type,
            entity_id=entity_id,
            operation=operation,
            status=AuditStatus.SUCCESS,
            ip_address=request.client.host,
            request_id=getattr(request.state, 'request_id', None),
            metadata={"override": override_context} if override_context else None,
        ))
    except Exception:
        logger.error("Audit log delivery failed", extra={"entity_type": entity_type, "entity_id": entity_id})
```

### Why not a transactional outbox?
- Current scale: single PostgreSQL instance, low throughput
- An outbox pattern (separate table, polling publisher) adds complexity with no justified benefit
- The audit DB is a separate PostgreSQL; cross-DB transactions aren't supported
- Fire-and-forget with non-fatal failure is acceptable for audit (system remains operational if audit agent is down)
- **ponytail:** Outbox only if audit delivery reliability < 99.9% in production

---

## 12. Migration Strategy

### Decision: Alembic (preferred)

Alembic is the standard migration tool for SQLAlchemy-based projects. The project currently uses init-scripts that run at container start (`apply_migrations` in `main.py`), which is fragile — they re-execute on every restart and have no version tracking.

### Plan

#### Phase M1: Install and configure Alembic
```bash
pip install alembic
alembic init migrations/
```

`alembic.ini`:
```ini
[alembic]
script_location = migrations
sqlalchemy.url = postgresql://user:pass@db:5432/banking_dev
```

#### Phase M2: Create initial migration (baseline)
```bash
alembic revision --autogenerate -m "baseline_existing_schema"
```
This captures the existing schema (all 23 tables) as the first migration.

**Note:** Autogenerate requires SQLAlchemy models. The project uses raw SQL via `DatabaseConnector`, not ORM models. Alternative: create a set of `declarative_base` models for migration purposes only.

**Simpler alternative (recommended for this project):** Hand-write the initial migration to match existing schema, then use `--autogenerate` for future changes.

#### Phase M3: Add operational entities migration
```bash
alembic revision -m "add_operational_entities"
```

This migration contains:
- All new tables (alerts, investigations, compliance_cases, decisions, evidence, remediation_actions, tasks, watchlists, watchlist_items, saved_analyses, notifications, activity_timeline, ai_assistance, comments)
- New columns on existing tables (version, updated_at, etc.)
- New permissions in permissions table
- New role_permissions mappings
- Indexes for entity_type+entity_id lookups

#### Phase M4: Migration process

| Step | Action | Safety |
|------|--------|--------|
| 1 | Backup production database | Required |
| 2 | Run migration on staging | Validate no data loss |
| 3 | Run migration on production | `alembic upgrade head` |
| 4 | Verify schema | `alembic check` |
| 5 | Deploy new application code | No downtime if additive |

**Downgrade:** Supported for additive changes. Not supported if migration includes destructive operations (the first vertical slice is purely additive).

**Key principle:** Every Inc 2 migration is **additive only** — new tables, new columns, new indexes. No dropped columns, no renamed tables, no destructive ALTERs. This ensures zero-downtime deployment and simple rollback by reverting the application code.

#### Phase M5: Retire init-script approach
- Keep existing init SQL files for local development / fresh installs (they use `IF NOT EXISTS`)
- Production: Alembic only
- Future: Remove `apply_migrations()` from `main.py` after all environments migrate to Alembic

---

## 13. Realistic Implementation Sequence

### Phase 2A: Foundations and Migrations (5-7 days)
- Alembic setup + baseline migration
- Operational entities DDL (additive migration)
- Version column migration on all new tables
- Permission seed data migration
- Extend audit_logs table (additive)
- New shared models in Python (Pydantic + SQLAlchemy)
- `authorise()` policy engine implementation
- `PermissionGate` frontend component

### Phase 2B: First Vertical Workflow (8-10 days)
- Alert CRUD + state machine (status transitions, permissions, version checks)
- Alert → Investigation creation
- Investigation CRUD + state machine
- Alert escalation → Case creation
- Case CRUD + state machine
- Decision recording
- Comments (polymorphic) + Timeline (transactional)
- Backend tests for workflow states and transitions
- Frontend: Alert inbox, Investigation detail, Case detail
- Frontend: Comment component, Timeline component

### Phase 2C: Analyst Workbench Expansion (5-7 days)
- Investigation advanced UI (findings, hypotheses, conclusion)
- Saved Analyses CRUD (reuse existing saved analysis concept)
- Draft reports placeholder
- AI Investigation Suggestions (frontend button + backend endpoint)
- Morning Work Queue view
- Customer/Transaction investigation views

### Phase 2D: Compliance Workbench Expansion (6-8 days)
- Evidence upload + chain of custody (storage, hash, malware scan)
- Remediation actions CRUD + state machine
- Watchlists CRUD
- Case advanced UI (evidence tab, remediation tracking)
- Regulatory reporting integration (reuse existing report generator)
- SLA/deadline tracking on cases

### Phase 2E: Administrator Workbench (4-5 days)
- Emergency override CRUD
- Workflow dictionaries (status codes, transition configs)
- Feature flags UI
- Retention policy configuration
- Maintenance mode toggle
- Organisational scope config
- Identity link management (Keycloak ↔ application user)

### Phase 2F: AI Operational Integration (3-4 days)
- `ai_assistance` table + CRUD
- Wrap existing insights_agent + compliance_agent calls in ai_assistance record
- AI suggestion accept/reject UI
- Prohibited-action enforcement in gateway
- AI governance dashboard (read-only: usage, latency, human status)

### Phase 2G: Notifications, Collaboration and SLA (4-5 days)
- Notification CRUD + bell UI
- Task CRUD (is_request_for_information flag)
- In-app notification delivery for: assignment, status change, mention, deadline
- SLA breach detection (cron job)
- Escalation triggers on SLA breach
- Follow-up reminder system

### Phase 2H: Security, Audit and Production Validation (5-7 days)
- Emergency override end-to-end testing
- Four-eyes approval workflow (critical alerts, case closure, decisions)
- Permission boundary penetration tests
- Optimistic locking conflict tests
- Evidence chain-of-custody audit verification
- AI governance boundary tests (AI cannot perform prohibited actions)
- Load test: concurrent alert processing
- Production hardening: rate limits, timeouts, circuit breakers
- Runbook creation for operational workflows

---

## 14. Revised Estimates

| Phase | Days | Team | Dependencies |
|-------|------|------|-------------|
| 2A Foundations + Migrations | 5-7 | 2 devs | None |
| 2B First Vertical Workflow | 8-10 | 2 devs | 2A |
| 2C Analyst Workbench | 5-7 | 1 dev | 2B |
| 2D Compliance Workbench | 6-8 | 1 dev | 2B |
| 2E Admin Workbench | 4-5 | 1 dev | 2B |
| 2F AI Operational Integration | 3-4 | 1 dev | 2B, 2C, 2D |
| 2G Notifications + Collaboration | 4-5 | 1 dev | 2B, 2C, 2D |
| 2H Security + Production Validation | 5-7 | 2 devs | 2C, 2D, 2E, 2F, 2G |
| **Total** | **40-53** | **1-2 devs** | |

### Assumptions
- 1-2 senior full-stack developers (backend + frontend capable)
- Existing infrastructure (Docker, PostgreSQL, Redis) reused
- No Kubernetes, no Kafka, no new infrastructure dependencies
- Frontend uses existing Chakra UI + Tailwind design system
- Backend uses existing FastAPI + asyncpg patterns
- Tests are written alongside code (not post-facto)
- Security review is part of Phase 2H, not a separate external audit
- Pilot feedback: 1 iteration after Phase 2B

### Testing Effort
| Layer | Coverage | Effort (days) |
|-------|----------|---------------|
| Unit tests (state machines, permissions, validators) | 90%+ | 3-4 |
| Integration tests (API endpoints, DB, auth) | 80%+ | 4-5 |
| E2E workflow test (alert→case→decision) | 1 full path | 2 |
| Security tests (permission boundaries, override) | Critical paths | 2 |
| Load test (alert engine, concurrent mutations) | 1 test | 1 |
| **Total testing** | | **12-14** |

### Security Effort
| Area | Effort (days) |
|------|---------------|
| AuthZ policy engine unit tests | 1 |
| Permission boundary pen test | 1 |
| AI governance boundary test | 0.5 |
| Evidence chain-of-custody audit | 1 |
| Emergency override test | 0.5 |
| **Total security** | **4** |

### MVP vertical slice (Phase 2B only)
- **Estimate: 8-10 days with 2 devs**
- Deliverable: end-to-end alert→investigation→case→decision→close workflow
- Working frontend for 6 pages (Alert inbox, Alert detail, Investigation detail, Case detail, Decision form, Comment/Timeline)
- Working backend with all state machines, permissions, version checks, audit
- Deployed in staging for pilot feedback

### Full Increment 2
- **Estimate: 40-53 days calendar time**
- **Team: 1-2 senior devs (can parallelize 2C+2D+2E)**
- With 2 devs working in parallel: ~7-8 weeks calendar time

---

## 15. Postponed Capabilities

| Capability | Reason | Expected Phase |
|-----------|--------|---------------|
| Email/push notification delivery | In-app is sufficient for MVP | Increment 3 |
| Real-time websockets for alerts | Polling works at current volume | Increment 3 |
| Bulk operations (select-all, batch assign) | YAGNI | Increment 4 |
| ML model for alert severity | Rule-based + optional LLM is sufficient | Increment 4 |
| File storage service (S3/MinIO) | Local protected storage is fine for MVP | Increment 3 |
| Transactional outbox | Not justified until audit reliability < 99.9% | Increment 4 |
| KPI/alert rule builder UI | Config in DB directly | Increment 3 |
| Credit risk / market risk modules | Out of scope | Increment 4 |
| Customer 360 view | Requires customer service integration | Increment 3 |
| Regulatory filing automation | Requires regulator API integration | Increment 4 |

---

## 16. Remaining Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Dependency on existing agents for AI features | Medium | Low | New endpoints are additive; agents have no changes |
| Evidence storage on container volume | Medium | Medium | Backup volume; document in runbook to add S3/MinIO before production |
| Malware scanner may not be available in all environments | Medium | Low | `malware_scan_status='skipped'` with warning; evidence stored with note |
| Existing `manager` users may see 403 on new pages | Low | Low | Documented in migration; admin can reassign |
| Four-eyes approval may slow compliance workflow | Low | Medium | Only applies to critical/regulatory actions; configurable threshold |
| Optimistic locking conflicts under concurrent access | Low | Low | Client retry with refresh; 409 UI guidance |
| Audit log delivery failure (async HTTP) | Low | Medium | Non-fatal; logged; periodic reconciliation job (future) |
| Alembic autogenerate may not capture existing schema perfectly | Medium | Low | Hand-write initial migration; test on staging first |

---

## Increment 2 Architecture Verdict

**READY FOR FIRST VERTICAL SLICE**

The architecture is internally consistent. All 15 blocking issues are resolved. The first vertical slice (Phase 2B) is scoped to 12 endpoints, 6 frontend pages, complete state machines, SoD, object-level auth, chain-of-custody evidence, AI governance, and transactional audit.

Remaining risks are documented and mitigated. Postponed capabilities are clearly labelled. Start with Phase 2A (Alembic, foundations, policy engine), then Phase 2B (the working workflow).
