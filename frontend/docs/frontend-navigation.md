# Frontend Navigation

## Route Structure

| Path | Component | Access | Description |
|------|-----------|--------|-------------|
| `/` | `LandingPage` | Public | Marketing landing, SSO redirect |
| `/auth/callback` | `AuthCallback` | Public | Keycloak callback handler |
| `/unauthorized` | `UnauthorizedPage` | Public | Access denied screen |
| `/banking` | `BankingDashboard` | `banking.*` | Executive dashboard |
| `/banking/branches` | `Branches` | `banking.view` | Branch list |
| `/banking/kpi` | `KpiPage` | `banking.view` | Financial KPIs |
| `/banking/risk` | `RiskPage` | `banking.risk` | Risk scoring |
| `/banking/compliance` | `CompliancePage` | `banking.compliance` | Compliance audit |
| `/banking/reports` | `ReportsPage` | `banking.reports` | Query engine |
| `/banking/admin` | `AdminPage` | `banking.admin` | System admin |
| `/banking/profile` | `ProfilePage` | `banking.*` | User profile |
| `/banking/settings` | `SettingsPage` | `banking.*` | User preferences |

## Sidebar Navigation

Items are filtered by RBAC role via `menuItems` with `roles` arrays:

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
- Searches all routes by name
- Keyboard navigation: ↑↓ to move, Enter to select, Esc to close
- Navigates via `react-router-dom` `useNavigate()`

### AI Assistant Panel
- Opens from TopBar or keyboard shortcut
- Slides in from right, 400px width
- Chat interface for natural language queries
- Integrates with `queryApi.submitQuery()`

## Auth Flow

1. User visits `/` → redirected to Keycloak if not authenticated
2. Keycloak callback → `/auth/callback` → token exchange
3. `/auth/me` fetch → user profile + role assignment
4. Role-based redirect to appropriate `/banking/*` route
5. Session expiry → automatic re-authentication prompt
