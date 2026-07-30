# Increment 2 — Workflow & Process Specification

## 1. Alert-to-Investigation Flow (Analyst)

```
[System] Alert triggered (rule/KPI/ML)
    → Email/notification sent to assigned analyst
    → Alert appears in Analyst workbench inbox

[Analyst] Views alert detail
    → Sees context: related customer/account/transaction/KPI
    → Reviews source query or rule that triggered

[Analyst] Acknowledges alert → status=acknowledged
    → Optional: dismisses with note → status=dismissed [end]

[Analyst] Creates investigation from alert
    → Investigation created with status=draft, linked to alert
    → Alert status → investigating

[Analyst] Conducts investigation
    → Runs queries (existing AI assistant)
    → Attaches findings (jsonb)
    → Adds evidence if compliance-relevant
    → Adds comments/notes
    → Timeline auto-populated

[Analyst] Completes investigation
    → Writes conclusion
    → Status → completed

  [Branch: compliance concern identified]
    → Analyst escalates → creates ComplianceCase
    → Links evidence, investigation, alert
    → Case appears in Compliance Officer workbench

[System] Alert → resolved (if investigation completed without escalation)
```

## 2. Compliance Case Flow (Compliance Officer)

```
[Trigger] New case (from alert escalation, violation detection, or manual)

[Compliance Officer] Reviews case
    → Views linked alert, investigation, evidence, violation
    → Reviews regulatory framework applicability

[Compliance Officer] Assigns priority, target date
    → Cases status → under_review

[Compliance Officer] Conducts review
    → Requests additional evidence from analyst (creates task)
    → Records decisions
    → Checks against watchlists

[Branch: needs escalation]
    → Status → escalated
    → Notifies admin
    → Admin reassigns or escalates further

[Compliance Officer] Makes decision
    → Decision recorded: no_action, warning, enhanced_due_diligence, report_to_authority, account_freeze, case_closed
    → Rationale required

[Compliance Officer] Creates remediation actions (if needed)
    → One or more RemediationAction entities
    → Assigns owners, sets target dates

[Compliance Officer] Closes case
    → Status → closed
    → Case resolution documented
```

## 3. Task Assignment & Tracking (All Roles)

```
[Any role] Creates task
    → Linked to entity (alert, investigation, case, remediation)
    → Assigns to user, sets priority/due date

[Assignee] Views task in workbench
    → Task appears in "My Tasks" section

[Assignee] Updates status
    → pending → in_progress → completed

[Verifier] (Compliance/Admin) Verifies completion
    → completed → verified [or] → in_progress (rejected)

[System] Notification on each transition
```

## 4. Watchlist Screening (Compliance)

```
[Compliance Officer] Creates watchlist
    → Selects type (sanctions/PEP/adverse_media/internal_risk/custom)
    → Adds items (entity_identifier, external_reference)

[System - future] Automated screening
    → Future: matching against customers/transactions
    → For Inc 2: manual lookup only

[Compliance Officer] Reviews match
    → During case investigation, checks entity against watchlists
    → Records finding in case
```

## 5. Saved Analysis & Scheduling (Analyst)

```
[Analyst] Runs query via AI Assistant
    → Optionally saves as SavedAnalysis

[Analyst] Configures schedule (cron)
    → System runs query on schedule
    → Results stored as snapshot

[Analyst] Reviews scheduled results
    → Shares with team (is_shared=true)
    → Creates alert threshold from saved analysis (future)
```

## 6. Notification Delivery

```
[Trigger] Entity state change, assignment, mention, deadline
    → Notification created for target user(s)
    → Listed in notification center (bell icon)
    → Email/push (future)

[User] Views notifications
    → Sees unread count in header
    → Opens notification center dropdown
    → Clicks → navigates to entity detail
    → Marks as read
```

## 7. Activity Timeline (System)

```
[Automated] Any state change on operational entities
    → ActivityTimelineEntry created
    → logged: who, what, when, old/new values

[User] Views timeline on any entity detail page
    → Chronological list of all actions
    → Filters by action type
```

## State Machine Summary

### Alert States
```
triggered → acknowledged → investigating → resolved
                                      → dismissed
```

### Investigation States
```
draft → active → completed → archived
           → paused
```

### ComplianceCase States
```
open → under_review → escalated → resolved → closed
                                  → resolved
```

### Task States
```
pending → in_progress → completed → verified
                                    → in_progress (rejected)
```
