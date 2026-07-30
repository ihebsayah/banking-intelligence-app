# Increment 2 — Frontend Information Architecture

## Navigation Structure

```
Sidebar (existing layout, extended)
├── Dashboard (existing — all roles)
├── Analytics (existing — KPI, Risk, Reports)
├── AI Assistant (existing — all roles)
│
├── ANALYST WORKBENCH (new — analyst, admin)
│   ├── Alerts Inbox
│   ├── My Investigations
│   └── Saved Analyses
│
├── COMPLIANCE WORKBENCH (new — compliance, admin)
│   ├── Cases
│   ├── Watchlists
│   └── Evidence
│
├── ADMIN (existing + new — admin only)
│   ├── Users (existing)
│   ├── Alert Rules (new)
│   ├── All Tasks (new)
│   └── System Config (existing)
│
└── Notifications (bell icon, header — all roles)
```

## Page Specifications

### 1. Alerts Inbox (route: `/workbench/alerts`)
**Role:** Analyst, Admin

| State | Behaviour |
|-------|-----------|
| Loading | Skeleton rows (6) |
| Empty | "No alerts. All clear." illustration |
| List | Table: severity icon, title, type, status badge, assigned_to, time ago |
| Error | "Failed to load alerts" + retry button |
| Detail | Full alert detail: related entity card, timeline, comments, action buttons |
| Acknowledge | Button → optimistic update → status badge changes |
| Dismiss | Modal with reason textarea → POST |
| Investigate | Opens create investigation panel (same page slide-over) |
| Escalate | Opens create case modal with pre-filled data |

### 2. My Investigations (route: `/workbench/investigations`)
**Role:** Analyst, Admin

| State | Behaviour |
|-------|-----------|
| Loading | Skeleton cards |
| Empty | "Start an investigation from an alert" + link to alerts |
| List | Card grid: title, priority, status, assigned_to, last updated |
| Detail | Tabs: Overview | Findings | Timeline | Comments |
| Create | Slide-over panel or modal: title, desc, link alert, priority |
| Update findings | Inline editor (textarea/json) on overview tab |
| Status change | Dropdown with allowed transitions based on current state |
| AI Suggestions | Button "Get AI suggestions" → calls insights agent → shows suggestions panel |
| Archive | Confirm dialog → POST |

### 3. Saved Analyses (route: `/workbench/analyses`)
**Role:** Analyst, Admin

| State | Behaviour |
|-------|-----------|
| Loading | Skeleton list |
| Empty | "Save your AI Assistant queries for later." |
| List | Table: name, last_run, schedule, shared status, actions |
| Detail | Query parameters display, run now button, schedule config, results |
| Create | "Save Current" button on AI Assistant page → modal with name/desc |
| Schedule | Cron picker UI (or simple "daily/weekly/monthly") |
| Share | Toggle → PATCH share endpoint |

### 4. Compliance Cases (route: `/workbench/cases`)
**Role:** Compliance, Admin

| State | Behaviour |
|-------|-----------|
| Loading | Skeleton table |
| Empty | "No cases assigned." |
| List | Table: priority, title, status, regulatory framework tags, target_date, assigned |
| Detail | Tabs: Overview | Evidence | Decisions | Remediations | Timeline | Comments |
| Create | Wizard: link alert/violation → fill details → add evidence → assign |
| Status change | Dropdown with confirmation for transitions |
| Decision | Form: decision type + rationale (required) textarea |
| Evidence upload | File input → POST with metadata form |
| Remediation | Form: type, description, assignee, target date; list with status badges |
| Escalate | Modal: reason + escalation level |

### 5. Watchlists (route: `/workbench/watchlists`)
**Role:** Compliance, Admin

| State | Behaviour |
|-------|-----------|
| Loading | Skeleton |
| Empty | "Create your first watchlist." + CTA |
| List | Cards: name, type badge, item count, active status |
| Detail | Table of items + add item form; filters by entity_type |
| Create | Modal: name, description, type, initial items (optional) |
| Add Item | Inline form: entity_type, identifier, reference, risk_score, notes |
| Delete | Confirm → DELETE with parent redirect |

### 6. All Tasks (route: `/admin/tasks`)
**Role:** Admin only
- Table: all tasks, filterable by status/assignee/entity_type
- Admin can reassign, verify, delete any task
- Create task for any entity

### 7. Alert Rules (route: `/admin/alert-rules`)
**Role:** Admin only
- Future: UI for configuring KPI threshold alerts
- For Inc 2: simple list of active rules with enable/disable toggle

### 8. Notification Center (header bell icon, dropdown + `/notifications`)
**Role:** All
- Bell icon with unread count badge
- Dropdown: last 10 notifications with "Mark all read" link
- Full page: filterable list, mark individual read
- Click → navigate to linked entity

## Shared UI Patterns

### Entity Detail Page Layout
```
[Header] Title + Status badge + Priority badge + Actions menu
[Section 1] Overview / Key info (metadata cards)
[Section 2] Related entities (linked alerts, cases, investigations)
[Tab bar]    | Overview | Evidence | Decisions | Remediations | Timeline | Comments |
```

### Action Buttons (per entity)
- Each entity detail page has a floating action bar or inline buttons for available transitions
- Buttons disabled if user lacks permission; tooltip explains why

### Comment Component
```
[Comment list] Avatar + name + timestamp + content
[Comment input] Textarea + Submit button (with is_internal toggle for compliance)
```

### Timeline Component
```
[Filter bar] All | Status changes | Assignments | Comments | Evidence
[Timeline] Chronological feed: icon + action text + actor + timestamp
           Clickable entries expand to show old/new values
```

## State Management
- New Zustand stores:
  - `alertStore` — alerts list, current alert, filters
  - `investigationStore` — investigations, current, findings
  - `caseStore` — cases, current, evidence, decisions
  - `watchlistStore` — watchlists, items
  - `taskStore` — tasks list, current
  - `notificationStore` — notifications, unread count
  - `timelineStore` — timeline entries per entity (ephemeral)
- Pattern: same as existing stores (create with devtools, async actions)
- Auth store extended to include new permissions for UI gating

## Route Configuration
```typescript
// New routes added to App.tsx
{
  path: '/workbench/alerts',
  element: <ProtectedRoute roles={['analyst','admin']}><AlertsPage /></ProtectedRoute>
},
{
  path: '/workbench/alerts/:id',
  element: <ProtectedRoute roles={['analyst','admin']}><AlertDetail /></ProtectedRoute>
},
{
  path: '/workbench/investigations',
  element: <ProtectedRoute roles={['analyst','admin']}><InvestigationsPage /></ProtectedRoute>
},
{
  path: '/workbench/investigations/:id',
  element: <ProtectedRoute roles={['analyst','admin']}><InvestigationDetail /></ProtectedRoute>
},
{
  path: '/workbench/analyses',
  element: <ProtectedRoute roles={['analyst','admin']}><SavedAnalysesPage /></ProtectedRoute>
},
{
  path: '/workbench/cases',
  element: <ProtectedRoute roles={['compliance','admin']}><CasesPage /></ProtectedRoute>
},
{
  path: '/workbench/cases/:id',
  element: <ProtectedRoute roles={['compliance','admin']}><CaseDetail /></ProtectedRoute>
},
{
  path: '/workbench/watchlists',
  element: <ProtectedRoute roles={['compliance','admin']}><WatchlistsPage /></ProtectedRoute>
},
{
  path: '/workbench/watchlists/:id',
  element: <ProtectedRoute roles={['compliance','admin']}><WatchlistDetail /></ProtectedRoute>
},
{
  path: '/admin/alert-rules',
  element: <ProtectedRoute roles={['admin']}><AlertRulesPage /></ProtectedRoute>
},
{
  path: '/admin/tasks',
  element: <ProtectedRoute roles={['admin']}><AllTasksPage /></ProtectedRoute>
},
{
  path: '/notifications',
  element: <ProtectedRoute roles={['analyst','compliance','admin']}><NotificationsPage /></ProtectedRoute>
}
```

## Existing Pages Unchanged
- Dashboard, KPI, Risk, Compliance (read-only dashboards), Reports, Admin (Users + Config), AI Assistant, Profile
