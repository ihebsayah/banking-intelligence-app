# Frontend API Gap Analysis

This report lists the expected backend endpoints that are currently missing, but required by the upgraded role-based Banking Portal Shell. For each missing endpoint, we define the HTTP Method, Route, Expected JSON Response structure, and the frontend page consuming it.

---

## 1. Dashboard Services

### 1.1 `GET /dashboard/kpis`
- **Frontend Consumer**: `/dashboard` ([BankingDashboard.tsx](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/pages/BankingDashboard.tsx))
- **Description**: Returns key financial KPIs (deposits, revenue, active customer count, risk metrics).
- **Expected Payload**:
  ```json
  [
    {
      "kpi_id": "total_deposits",
      "name": "Total Deposits",
      "value": 2347650000.0,
      "metric_type": "currency",
      "trend": 2.3,
      "trend_direction": "up",
      "last_updated": "2026-06-12T15:00:00Z",
      "data_freshness": "real-time"
    }
  ]
  ```

### 1.2 `GET /dashboard/charts/{chartId}`
- **Frontend Consumer**: `/dashboard` ([BankingDashboard.tsx](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/pages/BankingDashboard.tsx))
- **Description**: Returns chart data by chart name/id (e.g. `revenue_trend`, `risk_levels`, `concentration`, `growth_rate`).
- **Expected Payload**:
  ```json
  {
    "chart_id": "revenue_trend",
    "chart_type": "line",
    "title": "Revenue Trend",
    "data": [
      { "label": "Jun", "value": 10200000.0 }
    ],
    "last_updated": "2026-06-12T15:00:00Z"
  }
  ```

---

## 2. KPI Intelligence

### 2.1 `GET /kpi/metrics`
- **Frontend Consumer**: `/kpi` ([KpiPage.tsx](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/pages/KpiPage.tsx))
- **Description**: Returns operational and core performance metrics.
- **Expected Payload**:
  ```json
  [
    {
      "kpi_id": "monthly_recurring_rev",
      "name": "Monthly Recurring Revenue",
      "value": 12500000.0,
      "metric_type": "currency",
      "trend": 4.1,
      "trend_direction": "up",
      "last_updated": "2026-06-12T15:00:00Z",
      "data_freshness": "6-hour"
    }
  ]
  ```

---

## 3. Portfolio Risk

### 3.1 `GET /risk/summary`
- **Frontend Consumer**: `/risk` ([RiskPage.tsx](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/pages/RiskPage.tsx))
- **Description**: Returns consolidated portfolio credit risk levels and counts of alerts.
- **Expected Payload**:
  ```json
  {
    "risk_level_distribution": {
      "low": 62,
      "medium": 28,
      "high": 8,
      "critical": 2
    },
    "total_high_risk_customers": 140,
    "critical_alerts_count": 5,
    "average_risk_score": 0.45,
    "last_updated": "2026-06-12T15:00:00Z"
  }
  ```

---

## 4. Compliance & Audit

### 4.1 `GET /compliance/report`
- **Frontend Consumer**: `/compliance` ([CompliancePage.tsx](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/pages/CompliancePage.tsx))
- **Description**: Returns status indicators for GDPR, PCI compliance, and number of active KYC violations or AML flags.
- **Expected Payload**:
  ```json
  {
    "gdpr_status": "compliant",
    "pci_status": "compliant",
    "aml_alerts_count": 12,
    "kyc_status": "warning",
    "active_violations_count": 2,
    "last_updated": "2026-06-12T15:00:00Z"
  }
  ```

### 4.2 `GET /audit/logs`
- **Frontend Consumer**: `/reports` ([ReportsPage.tsx](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/pages/ReportsPage.tsx))
- **Description**: List of security audit log records stored in the `audit_logs` DB.
- **Expected Payload**:
  ```json
  [
    {
      "id": "audit_8279",
      "timestamp": "2026-06-12T14:45:00Z",
      "user_id": "analyst_001",
      "user_role": "analyst",
      "action": "query_database",
      "status": "success",
      "details": "Submitted NL query: Show me top customers",
      "ip_address": "127.0.0.1"
    }
  ]
  ```

---

## 5. Administration

### 5.1 `GET /admin/users`
- **Frontend Consumer**: `/admin` ([AdminPage.tsx](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/pages/AdminPage.tsx))
- **Description**: Retrieves a list of user profiles from backend to review active intelligence roles.
- **Expected Payload**:
  ```json
  [
    {
      "user_id": "analyst_001",
      "email": "analyst_001@bankintel.hq",
      "role": "analyst",
      "bank_id": "hq_main",
      "created_at": "2026-05-01T00:00:00Z",
      "last_login": "2026-06-12T15:10:00Z",
      "status": "active"
    }
  ]
  ```

---

## 6. Profile Services

### 6.1 `GET /auth/me`
- **Frontend Consumer**: `/profile` ([ProfilePage.tsx](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/pages/ProfilePage.tsx))
- **Description**: Returns detailed identity and role attributes for the current session.
- **Expected Payload**: Same structure as a user record inside user management list.
