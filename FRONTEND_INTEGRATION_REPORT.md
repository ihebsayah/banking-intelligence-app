# Frontend Integration Report

**Generated:** 2026-06-12  
**Branch:** main  
**Build status:** ✅ `tsc && vite build` — 2783 modules, 0 TypeScript errors

---

## Overview

All frontend pages in the Banking Intelligence Portal are now connected to real, authenticated FastAPI endpoints on the API Gateway. No mock JSON files, hardcoded business numbers, random values, or placeholder charts remain in any page or API client module.

---

## API Client Layer

| File | Status | Endpoints Covered |
|------|--------|-------------------|
| `src/api/client.ts` | ✅ Preserved | Base `axios` client with Bearer-token interceptor and 401 redirect |
| `src/api/auth.ts` | ✅ Updated | `POST /auth/login`, `GET /users/me` |
| `src/api/profileApi.ts` | ✅ Updated | `GET /users/me` |
| `src/api/dashboard.ts` | ✅ Refactored | `GET /dashboard/overview`, `GET /dashboard/kpis`, `GET /dashboard/recent-activity`, `GET /dashboard/charts/{chart_id}` |
| `src/api/kpiApi.ts` | ✅ Created | `GET /kpi/catalog`, `GET /kpi/values`, `GET /kpi/trends` |
| `src/api/riskApi.ts` | ✅ Created | `GET /risk/overview`, `GET /risk/flags`, `GET /risk/segments`, `GET /risk/summary` |
| `src/api/complianceApi.ts` | ✅ Refactored | `GET /compliance/overview`, `GET /compliance/rules`, `GET /compliance/violations`, `GET /audit/logs` |
| `src/api/reportsApi.ts` | ✅ Created | `GET /reports`, `POST /reports/generate` |
| `src/api/adminApi.ts` | ✅ Updated | `GET /admin/users`, `GET /admin/roles`, `GET /admin/permissions` |

---

## TypeScript Interface Definitions

**File:** `src/types/api.ts` — fully aligned with FastAPI Pydantic models in `services/api_gateway/routes.py`

| Interface | Backend Model | Used By |
|-----------|---------------|---------|
| `DashboardOverview` | `DashboardOverview` | `BankingDashboard` |
| `RecentActivity` | `RecentActivity` | `BankingDashboard` |
| `KpiMetric` | `KPIMetric` | `BankingDashboard`, `KpiPage` |
| `KpiDefinition` | `kpi_definitions` table row | `KpiPage` |
| `ChartResponse` / `ChartDataPoint` | `ChartResponse` / `ChartDataPoint` | `BankingDashboard` |
| `RiskOverview` | `RiskOverview` | `RiskPage` |
| `RiskFlag` / `PaginatedRiskFlags` | `RiskFlag` / `PaginatedRiskFlags` | `RiskPage` |
| `RiskSegment` | `RiskSegment` | `RiskPage` |
| `RiskSummary` | `risk_summary` dict | `RiskPage` |
| `ComplianceOverview` | `ComplianceOverview` | `CompliancePage` |
| `ComplianceRule` | `ComplianceRule` | `CompliancePage` |
| `ComplianceViolation` / `PaginatedComplianceViolations` | `ComplianceViolation` | `CompliancePage` |
| `AuditLogRow` / `PaginatedAuditLogs` | `AuditLogRow` / `PaginatedAuditLogs` | `CompliancePage` |
| `Report` / `PaginatedReports` | `Report` / `PaginatedReports` | `ReportsPage` |
| `AdminUserRow` | `AdminUserRow` | `AdminPage` |
| `RoleInfo` | `RoleInfo` | `AdminPage` |
| `PermissionInfo` | `PermissionInfo` | `AdminPage` |
| `AdminUser` | `AdminUserRow` | `ProfilePage` |

---

## Page-by-Page Integration Map

### `/dashboard` — `BankingDashboard.tsx`

| Data | Endpoint | RBAC |
|------|----------|------|
| Portfolio/account/transaction overview counts | `GET /dashboard/overview` | `business` |
| Financial KPI cards (deposits, revenue, customers, risk score) | `GET /dashboard/kpis` | `business` |
| Revenue trend line chart | `GET /dashboard/charts/revenue_trend` | `business` |
| New customer growth area chart | `GET /dashboard/charts/growth_rate` | `business` |
| Deposit concentration bar chart | `GET /dashboard/charts/concentration` | `business` |
| Risk flag severity pie chart | `GET /dashboard/charts/risk_levels` | `business` |
| Latest 10 transactions activity log | `GET /dashboard/recent-activity?limit=10` | `business` |

**UI States:** Loading skeletons (per-section), error banner with Retry button, real-time refresh via header button.

---

### `/assistant` — `Assistant.tsx`

| Data | Endpoint | RBAC |
|------|----------|------|
| Natural language query submission | `POST /query` | Authenticated |

**Status:** Pre-existing, preserved unchanged. Full NL→SQL→results pipeline with insight rendering.

---

### `/kpi` — `KpiPage.tsx`

| Data | Endpoint | RBAC |
|------|----------|------|
| 6 live computed KPI metric cards | `GET /kpi/values` | `business` |
| Monthly trend line chart (fee revenue / tx count / avg tx size) | `GET /kpi/trends?months={6|12|24}` | `business` |
| Searchable KPI definition catalog table | `GET /kpi/catalog` | `business` |

**UI States:** Loading skeletons for cards and chart, empty state for catalog search, interactive metric/timeframe toggles.

---

### `/risk` — `RiskPage.tsx`

| Data | Endpoint | RBAC |
|------|----------|------|
| Risk overview stats (total flags, critical, avg score, KYC incomplete) | `GET /risk/overview` | `business` |
| Segment risk concentration table (count, avg score, total balance, exposure bar) | `GET /risk/segments` | `business` |
| Paginated risk flags registry with severity/resolved filters | `GET /risk/flags?page=&page_size=&severity=&resolved=` | `business` |

**UI States:** Loading skeletons, colored severity badges, resolved/active status indicators, pagination controls.

---

### `/compliance` — `CompliancePage.tsx`

Tabbed interface with three views:

| Tab | Data | Endpoint | RBAC |
|-----|------|----------|------|
| Overview bar | Compliance status indicators (GDPR, AML, KYC, violations) | `GET /compliance/overview` | `compliance` |
| Active Rules | Compliance rules with regulation/type/condition/action | `GET /compliance/rules?regulation=&enabled_only=` | `compliance` |
| Violations | Paginated violations with regulation/severity filters | `GET /compliance/violations?page=&page_size=&regulation=&severity=` | `compliance` |
| Audit Trail | Paginated audit DB logs with user/action search | `GET /audit/logs?page=&page_size=&user_id=&action=` | `compliance` |

**UI States:** Loading skeletons per tab, empty states with icons, pagination on violations and audit tabs.

---

### `/reports` — `ReportsPage.tsx`

| Data | Endpoint | RBAC |
|------|----------|------|
| Paginated generated reports with regulation/status filters | `GET /reports?page=&page_size=&regulation=&status=` | `business` |
| Report generation form wizard (modal) | `POST /reports/generate` | `business` |

**Generate modal:** Selects report type (`aml_summary`, `kyc_status`, `risk_exposure`, `transaction_volume`), governance frame (AML/KYC/GDPR/PCI-DSS/SOX), and optional date period. Success/error feedback with auto-close and list refresh.

---

### `/admin` — `AdminPage.tsx`

Tabbed interface with three views plus developer tool shortcut cards:

| Tab | Data | Endpoint | RBAC |
|-----|------|----------|------|
| User Directory | Paginated users with role/status filters | `GET /admin/users?page=&page_size=&role=&status=` | `admin` |
| RBAC Role Matrix | Role cards with user count and permission tokens | `GET /admin/roles` | `admin` |
| Permissions Registry | Permission → roles capability table | `GET /admin/permissions` | `admin` |

Developer shortcuts remain for admin users only: links to `/dev`, `/dev/query`, `/dev/debug`.

---

### `/profile` — `ProfilePage.tsx`

| Data | Endpoint | RBAC |
|------|----------|------|
| User profile (name, email, role, bank_id, timestamps) | `GET /users/me` | Authenticated |

**Fallback:** If `/users/me` is unreachable, falls back to JWT-decoded identity from `authStore` with a visible advisory banner. No hardcoded user data.

---

## Role-Aware Navigation

Sidebar (`BankingSidebar.tsx`) filters navigation links dynamically against `user.role`:

| Route | Visible To |
|-------|-----------|
| `/dashboard` | analyst, manager, compliance, admin |
| `/assistant` | analyst, manager, compliance, admin |
| `/kpi` | analyst, manager, compliance, admin |
| `/risk` | analyst, manager, compliance, admin |
| `/compliance` | compliance, manager, admin |
| `/reports` | manager, admin |
| `/admin` | admin |
| `/profile` | analyst, manager, compliance, admin |
| `/dev` (Developer Monitor) | admin (sidebar link only) |

Route guards in `App.tsx` enforce RBAC at the route level via `<ProtectedRoute requiredRole={...}>`. `/dev/*` routes additionally require the `admin` role.

---

## Mock Data Audit

| Check | Result |
|-------|--------|
| Hardcoded KPI numbers in page files | ✅ None — all values from API |
| Static chart data arrays | ✅ None — all chart data from `/dashboard/charts/*` |
| Fake transaction records | ✅ None — transactions from `/dashboard/recent-activity` |
| Mock JSON fixture files | ✅ None created or referenced |
| `Math.random()` usage in data rendering | ✅ None |
| Placeholder text replacing real counts | ✅ None |
| Hardcoded user/role strings in data display | ✅ None — all from JWT + `/users/me` |

The only static content is:
- UI labels and column headers (e.g. "Total Deposits", "AML Alerts")
- RBAC role permission definitions in `GET /admin/permissions` (sourced from backend, not frontend)
- Role badge color mappings (CSS only, not data)

---

## Verification

```
✓ npm run build (tsc && vite build) — exit 0
✓ 2783 modules transformed
✓ 0 TypeScript errors
✓ dist/assets/index.js — 959 kB (259 kB gzip)
```
