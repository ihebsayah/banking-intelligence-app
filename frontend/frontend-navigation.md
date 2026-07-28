# Frontend Navigation

## Layout Structure

```
┌──────────┬──────────────────────────────────┐
│          │  TopBar (search, notifications,   │
│ Sidebar  │       user menu)                  │
│          ├──────────────────────────────────┤
│  Nav     │                                  │
│  Items   │  Page Content                    │
│          │                                  │
│          │                                  │
│ User     │                                  │
│ Info     │                                  │
│          │                                  │
│ Sign Out │                                  │
│ Collapse │                                  │
└──────────┴──────────────────────────────────┘
```

## Sidebar

- **Width**: 220px expanded, 60px collapsed
- **Position**: fixed left, full height
- **Logo**: Banking Intel brand mark
- **Nav items**: role-filtered, active = blue-400 text + blue-600/15 bg
- **Bottom**: notifications, user info (name + role), dev monitor (admin), sign out, collapse

## TopBar

- **Height**: 48px (h-12)
- **Left**: search input (placeholder, no backend yet)
- **Right**: notification bell (unread dot), user avatar + name + dropdown

## User Menu (dropdown)

- User info: name, email, role badge
- Actions: Profile, Settings
- Sign Out (red, separated by border)

## Route Map

| Path | Component | Access |
|------|-----------|--------|
| `/` | BankingDashboard | all authenticated |
| `/dashboard` | BankingDashboard | all authenticated |
| `/branches` | Branches | all authenticated |
| `/assistant` | Assistant | all authenticated |
| `/kpi` | KpiPage | all authenticated |
| `/kpi-governance` | KpiGovernancePage | analyst+ |
| `/risk` | RiskPage | analyst+ |
| `/compliance` | CompliancePage | compliance+ |
| `/reports` | ReportsPage | manager+ |
| `/admin` | AdminPage | admin |
| `/profile` | ProfilePage | all authenticated |
| `/settings` | Settings | all authenticated |
| `/dev/*` | Dev tools | admin only |
| `/login` | LoginPage | public |
| `/unauthorized` | UnauthorizedPage | public |

## Responsive

- Sidebar collapses to 60px on toggle
- TopBar search hides on small screens
- User name hides on md- breakpoint
- Content area scrolls independently
