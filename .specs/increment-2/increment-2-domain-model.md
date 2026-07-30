# Increment 2 — Domain Model

New entities organized by bounded context. All entities get `created_at`, `updated_at`, `created_by` inherited from a shared `TimestampMixin`.

## Analyst Workbench

### Alert
```
alert_id: UUID PK
type: enum(transaction_anomaly, kpi_breach, risk_threshold, pattern_match, system_rule)
severity: enum(critical, high, medium, low)
title: str
description: text
source_query_id: UUID FK → query_log (nullable)
source_rule_id: UUID FK → kpi_thresholds | compliance_rules (nullable)
related_entity_type: enum(customer, account, transaction, kpi)
related_entity_id: UUID
status: enum(triggered, acknowledged, investigating, resolved, dismissed)
assigned_to: UUID FK → users (nullable)
resolution_notes: text (nullable)
resolved_at: timestamp (nullable)
resolved_by: UUID FK → users (nullable)
```

### Investigation
```
investigation_id: UUID PK
title: str
description: text
alert_id: UUID FK → alerts (nullable)
status: enum(draft, active, paused, completed, archived)
priority: enum(critical, high, medium, low)
assigned_to: UUID FK → users
findings: jsonb (nullable)
conclusion: text (nullable)
started_at: timestamp
completed_at: timestamp (nullable)
completed_by: UUID FK → users (nullable)
```

### SavedAnalysis
```
saved_analysis_id: UUID PK
name: str
description: text (nullable)
query_parameters: jsonb
result_snapshot: jsonb (nullable)
schedule_cron: str (nullable — for recurring)
last_run_at: timestamp (nullable)
owner_id: UUID FK → users
is_shared: bool default false
```

## Compliance Workbench

### ComplianceCase
```
case_id: UUID PK
title: str
description: text
alert_id: UUID FK → alerts (nullable)
investigation_id: UUID FK → investigations (nullable)
violation_id: UUID FK → compliance_violations (nullable)
status: enum(open, under_review, escalated, resolved, closed)
priority: enum(critical, high, medium, low)
risk_level: enum(high, medium, low)
regulatory_frameworks: text[] (GDPR, PCI, SOX, AML, KYC)
assigned_to: UUID FK → users
target_date: date (nullable)
resolution: text (nullable)
resolved_at: timestamp (nullable)
resolved_by: UUID FK → users (nullable)
```

### Evidence
```
evidence_id: UUID PK
case_id: UUID FK → compliance_cases
investigation_id: UUID FK → investigations (nullable)
type: enum(document, screenshot, query_result, log_extract, report, other)
title: str
description: text (nullable)
file_path: str (nullable)
metadata: jsonb (nullable)
uploaded_by: UUID FK → users
```

### Decision
```
decision_id: UUID PK
case_id: UUID FK → compliance_cases
decision: enum(no_action, warning, enhanced_due_diligence, report_to_authority, account_freeze, case_closed)
rationale: text
decided_by: UUID FK → users
decided_at: timestamp
```

### RemediationAction
```
remediation_action_id: UUID PK
case_id: UUID FK → compliance_cases
type: enum(enhanced_monitoring, training, process_change, system_update, policy_update, account_action)
description: text
status: enum(pending, in_progress, completed, verified)
assigned_to: UUID FK → users (nullable)
target_date: date (nullable)
completed_at: timestamp (nullable)
verified_by: UUID FK → users (nullable)
```

### Watchlist
```
watchlist_id: UUID PK
name: str
description: text (nullable)
type: enum(sanctions, pep, adverse_media, internal_risk, custom)
is_active: bool default true
owner_id: UUID FK → users
```

### WatchlistItem
```
watchlist_item_id: UUID PK
watchlist_id: UUID FK → watchlists
entity_type: enum(customer, account, transaction, individual, entity)
entity_identifier: str (name, ID, account number)
external_reference: str (nullable — UN/OFAC ref)
risk_score: decimal (nullable)
notes: text (nullable)
added_by: UUID FK → users
```

## Shared / Cross-cutting

### Task
```
task_id: UUID PK
title: str
description: text (nullable)
entity_type: enum(alert, investigation, compliance_case, remediation)
entity_id: UUID
status: enum(pending, in_progress, completed, verified, cancelled)
priority: enum(critical, high, medium, low)
assigned_to: UUID FK → users (nullable)
assigned_by: UUID FK → users
target_date: date (nullable)
completed_at: timestamp (nullable)
completed_by: UUID FK → users (nullable)
order: int (for manual sorting)
```

### Assignment
```
assignment_id: UUID PK
entity_type: enum(alert, investigation, compliance_case, task, remediation)
entity_id: UUID
assigned_to: UUID FK → users
assigned_by: UUID FK → users
assigned_at: timestamp
note: text (nullable)
```

### Comment
```
comment_id: UUID PK
entity_type: enum(alert, investigation, compliance_case, task, evidence, remediation)
entity_id: UUID
content: text
author_id: UUID FK → users
is_internal: bool default false
```

### Notification
```
notification_id: UUID PK
user_id: UUID FK → users
type: enum(alert_assigned, case_assigned, task_assigned, status_change, mention, deadline, system)
title: str
body: text (nullable)
entity_type: enum(alert, investigation, compliance_case, task) (nullable)
entity_id: UUID (nullable)
is_read: bool default false
read_at: timestamp (nullable)
```

### ActivityTimelineEntry
```
timeline_id: UUID PK
entity_type: enum(alert, investigation, compliance_case, task, evidence, remediation, decision)
entity_id: UUID
action: str (e.g., "status_changed", "assigned", "comment_added", "evidence_uploaded")
actor_id: UUID FK → users
metadata: jsonb (nullable — old/new values, etc.)
```

### AuditLog (extend existing)
Add columns for operational entities:
```
entity_type: str (nullable — which entity type)
entity_id: UUID (nullable — which entity instance)
action: str (nullable — what operation)
```
To correlate audit_logs entries to operational workflows.

## Entity Relationship Summary

```
Alert → Investigation (optional 1:1)
Alert → ComplianceCase (optional 1:1 via violation)
Investigation → ComplianceCase (optional 1:N)
ComplianceCase → Evidence (1:N)
ComplianceCase → Decision (1:1)
ComplianceCase → RemediationAction (1:N)
Watchlist → WatchlistItem (1:N)
Alert, Investigation, ComplianceCase, Task → Comment (polymorphic 1:N)
Alert, Investigation, ComplianceCase, Task → ActivityTimelineEntry (polymorphic 1:N)
Alert, Investigation, ComplianceCase, Task → Notification (polymorphic 1:N)
Alert, Investigation, ComplianceCase, Remediation → Task (polymorphic 1:N)
```

## Notes
- All IDs are UUID v4 generated at application level
- All timestamps are UTC
- `jsonb` columns for flexibility (findings, metadata, query_parameters)
- Polymorphic associations use `entity_type` + `entity_id` pattern (no shared PK)
- Foreign keys are enforced for direct relations; polymorphic FKs are NOT enforced at DB level (app-level integrity)
