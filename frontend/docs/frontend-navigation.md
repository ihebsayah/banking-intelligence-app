# Frontend Navigation

## Route Structure

| Path | Component | Access | Description |
|------|-----------|--------|-------------|
| `/` | `BankingDashboard` | `banking.*` | Executive dashboard (via ProtectedRoute) |
| `/login` | `LoginPage` | Public | Legacy mode login form only |
| `/auth/callback` | — | Public | Keycloak callback (handled by keycloak-js) |
| `/unauthorized` | `UnauthorizedPage` | Public | Access denied screen |
| `/banking` | `BankingDashboard` | `banking.*` | Redirect target |
| `/banking/branches` | `Branches` | `banking.view` | Branch list |
| `/banking/kpi` | `KpiPage` | `banking.view` | Financial KPIs |
| `/banking/risk` | `RiskPage` | `banking.risk` | Risk scoring |
| `/banking/compliance` | `CompliancePage` | `banking.compliance` | Compliance audit |
| `/banking/reports` | `ReportsPage` | `banking.reports` | Query engine |
| `/banking/admin` | `AdminPage` | `banking.admin` | System admin |
| `/banking/profile` | `ProfilePage` | `banking.*` | User profile |
| `/banking/settings` | `SettingsPage` | `banking.*` | User preferences |

Note: There is no LandingPage in production mode. The app automatically redirects to Keycloak for authentication.

## Sidebar Navigation

Items filtered by RBAC role via `menuItems` with `roles` arrays:

| Item | Icon | Required Role | Route |
|------|------|---------------|-------|
| Dashboard | LayoutDashboard | `banking.*` | `/banking` |
| Branches | Building2 | `banking.view` | `/banking/branches` |
| Risk Management | Shield | `banking.risk` | `/banking/risk` |
| Compliance | FileCheck | `banking.compliance` | `/banking/compliance` |
| Reports | FileText | `banking.reports` | `/banking/reports` |
| Admin | Settings | `banking.admin` | `/banking/admin` |

## Global Features

### Command Palette (Ctrl+K)
- Opens from any page
- Searches all routes AND actions by name
- Keyboard navigation: ↑↓ to move, Enter to select, Esc to close
- Navigates via `react-router-dom` `useNavigate()`

### AI Assistant Panel
- Opens from TopBar or command palette
- Slides in from right, 400px width
- Workspace interface for natural language queries, insights, and actions
- Integrates with `queryApi.submitQuery()`

## Auth Flow

### Production (Keycloak)
1. App boot → `kc.init({ onLoad: 'login-required' })` → auto-redirects to Keycloak if no session
2. Keycloak callback → `/auth/callback` (handled by keycloak-js internally) → token exchange
3. `/auth/me` fetch → user profile + role assignment
4. Role-based redirect to appropriate `/banking/*` route
5. Session expiry → auto-redirect to Keycloak login

### Demo (Legacy)
1. App boot → redirect to `/login`
2. User submits email/password → `/auth/login` → token in localStorage
3. Redirect to `/dashboard`
