# Increment 2 — Role & Capability Matrix

## Roles

| Role | Short Name | Description |
|------|-----------|-------------|
| `analyst` | Analyst | Investigates alerts, runs analyses, manages own work |
| `compliance` | Compliance Officer | Manages compliance cases, evidence, decisions, watchlists |
| `admin` | Administrator | System config, user management, oversees all entities, escalations |

Note: Existing `manager` role is retained in the enum but has no Inc 2 specific capabilities. It maps to a read-only view across all workbenches. If needed, promote to a full role in a later increment.

## Capability Matrix

| Capability | Analyst | Compliance | Admin |
|-----------|---------|-----------|-------|
| **Alerts** | | | |
| View assigned alerts | ✓ | ✓ | ✓ |
| View all alerts | — | — | ✓ |
| Acknowledge alert | ✓ | ✓ | ✓ |
| Investigate alert | ✓ | — | ✓ |
| Dismiss alert | ✓ | — | ✓ |
| Escalate alert to case | ✓ | ✓ | ✓ |
| Configure alert rules | — | — | ✓ |
| **Investigations** | | | |
| Create investigation | ✓ | — | ✓ |
| View own investigations | ✓ | ✓ | ✓ |
| View all investigations | — | — | ✓ |
| Edit investigation | ✓ | — | ✓ |
| Add findings/conclusion | ✓ | — | ✓ |
| Reassign investigation | — | — | ✓ |
| Archive investigation | ✓ | — | ✓ |
| **Compliance Cases** | | | |
| Create case | — | ✓ | ✓ |
| View assigned cases | ✓ | ✓ | ✓ |
| View all cases | — | — | ✓ |
| Add evidence | ✓ | ✓ | ✓ |
| Record decision | — | ✓ | ✓ |
| Create remediation action | — | ✓ | ✓ |
| Track remediation status | — | ✓ | ✓ |
| Close case | — | ✓ | ✓ |
| Escalate case | ✓ | ✓ | ✓ |
| Reassign case | — | — | ✓ |
| **Watchlists** | | | |
| View watchlists | ✓ | ✓ | ✓ |
| Create watchlists | — | ✓ | ✓ |
| Add/edit watchlist items | — | ✓ | ✓ |
| Delete watchlist | — | — | ✓ |
| **Saved Analysis** | | | |
| Create saved analysis | ✓ | — | ✓ |
| View own saved analyses | ✓ | — | ✓ |
| View all saved analyses | — | — | ✓ |
| Schedule recurring analysis | ✓ | — | ✓ |
| Share analysis | ✓ | — | ✓ |
| **Tasks** | | | |
| View assigned tasks | ✓ | ✓ | ✓ |
| Create task | ✓ | ✓ | ✓ |
| Update task status | ✓ | ✓ | ✓ |
| Verify completed task | — | ✓ | ✓ |
| Reassign task | — | — | ✓ |
| View all tasks | — | — | ✓ |
| **Notifications** | | | |
| View own notifications | ✓ | ✓ | ✓ |
| Mark read | ✓ | ✓ | ✓ |
| **Comments** | | | |
| Add comment to any entity | ✓ | ✓ | ✓ |
| Delete any comment | — | — | ✓ |
| **Timeline** | | | |
| View timeline of any entity | ✓ | ✓ | ✓ |
| **Admin** | | | |
| Manage users | — | — | ✓ |
| Manage roles | — | — | ✓ |
| System configuration | — | — | ✓ |
| View all entities (system-wide) | — | — | ✓ |
| Delete entities | — | — | ✓ |
| **Dashboard / Reports** (existing) | | | |
| View dashboards | ✓ | ✓ | ✓ |
| Create reports | ✓ | ✓ | ✓ |
| Schedule reports | ✓ | ✓ | ✓ |

## Summary by Volume

| Role | Read Capabilities | Write Capabilities | Admin Capabilities |
|------|------------------|-------------------|-------------------|
| Analyst | Own entities + shared | Own entities CRUD | None |
| Compliance | Own + assigned cases | Case, evidence, watchlist, remediation | None (except case escalation) |
| Admin | Everything | Everything | Full system control |
