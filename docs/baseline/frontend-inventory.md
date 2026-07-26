# Frontend Inventory

## Tech Stack
- React 18 + TypeScript
- Vite
- TailwindCSS
- shadcn/ui
- React Router v6
- Axios (client.ts)

## Pages (17 files physically exist in frontend/src/pages/)

### Business Portal Routes (BankingSidebar layout)

| Route | Component | File | Auth | Role Protection |
|-------|-----------|------|------|----------------|
| / | BankingDashboard | pages/BankingDashboard.tsx | Yes | None (any auth) |
| /dashboard | BankingDashboard | pages/BankingDashboard.tsx | Yes | None (any auth) |
| /branches | Branches | pages/Branches.tsx | Yes | None (any auth) |
| /assistant | Assistant | pages/Assistant.tsx | Yes | None (any auth) |
| /kpi | KpiPage | pages/KpiPage.tsx | Yes | None (any auth) |
| /kpi-governance | KpiGovernancePage | pages/KpiGovernancePage.tsx | Yes | analyst, manager, compliance, admin |
| /risk | RiskPage | pages/RiskPage.tsx | Yes | analyst, manager, compliance, admin |
| /compliance | CompliancePage | pages/CompliancePage.tsx | Yes | compliance, manager, admin |
| /reports | ReportsPage | pages/ReportsPage.tsx | Yes | manager, admin |
| /admin | AdminPage | pages/AdminPage.tsx | Yes | admin |
| /profile | ProfilePage | pages/ProfilePage.tsx | Yes | None (any auth) |
| /settings | Settings | pages/Settings.tsx | Yes | None (any auth) |

### Dev Routes (Sidebar layout, admin-only)

| Route | Component | File | Auth | Role Protection |
|-------|-----------|------|------|----------------|
| /dev | Dashboard | pages/Dashboard.tsx | Yes | admin |
| /dev/query | QueryTester | pages/QueryTester.tsx | Yes | admin |
| /dev/agents | AgentMonitorPage | pages/AgentMonitorPage.tsx | Yes | admin |
| /dev/performance | PerformanceMonitor | pages/PerformanceMonitor.tsx | Yes | admin |
| /dev/settings | Settings | pages/Settings.tsx | Yes | admin |
| /dev/debug | DebugPage | pages/DebugPage.tsx | Yes | admin |

### No-Auth Routes

| Route | Component | File |
|-------|-----------|------|
| /login | LoginPage | components/auth/LoginPage.tsx |
| /unauthorized | UnauthorizedPage | pages/UnauthorizedPage.tsx |

**Total: 17 page files, 18 routes**

## API Client Modules (14 files in frontend/src/api/)

| Module | File | Endpoints Called | Backend Match |
|--------|------|-----------------|---------------|
| client | client.ts | (axios instance) | N/A |
| auth | auth.ts | POST /auth/login | MATCHED |
| dashboard | dashboard.ts | GET /dashboard/overview, /dashboard/kpis, /dashboard/recent-activity, /dashboard/charts/{id} | MATCHED |
| kpiApi | kpiApi.ts | GET /kpi/catalog, /kpi/dashboard, /kpi/values, /kpi/metrics, /kpi/trends, /kpi/{id}/insights, /kpi/{id} | MATCHED |
| riskApi | riskApi.ts | GET /risk/overview, /risk/flags, /risk/segments, /risk/summary | MATCHED |
| complianceApi | complianceApi.ts | GET /compliance/overview, /compliance/rules, /compliance/violations, /compliance/report | MATCHED |
| reportsApi | reportsApi.ts | GET /reports, POST /reports/generate | MATCHED |
| adminApi | adminApi.ts | GET /admin/users, POST /admin/users, PATCH /admin/users/{id}, PATCH /admin/users/{id}/status, PATCH /admin/users/{id}/roles, GET /admin/roles, POST /admin/roles, PATCH /admin/roles/{id}, PATCH /admin/roles/{id}/permissions, GET /admin/permissions, GET /admin/activity | MATCHED |
| profileApi | profileApi.ts | GET /auth/me | MATCHED |
| queryApi | queryApi.ts | POST /query | MATCHED |
| agents | agents.ts | (WebSocket/monitoring) | INTERNAL |
| banking | banking.ts | (banking-specific calls) | CHECK |
| branches | branches.ts | (branch data) | CHECK |
| queries | queries.ts | (query history) | CHECK |

## Frontend/Backend Contract Gaps

### Missing Backend Endpoints (frontend calls but no backend)

1. Settings page exists but NO `/settings/*` backend endpoints
2. Branches page exists but NO `/branches/*` backend endpoints (Branches page likely queries `banking.ts` or `dashboard`)
3. Documents page does NOT exist (contrary to previous baseline)
4. Notifications page does NOT exist (contrary to previous baseline)
5. Analytics page does NOT exist (contrary to previous baseline)

### Dead Frontend Modules

1. `queries.ts` - may be unused if `queryApi.ts` is the active module

## Navigation Reachability

- All business portal routes are reachable from BankingSidebar.
- All dev routes are reachable from Sidebar (admin-only layout).
