# Banking Intelligence Portal API Endpoints

This document provides a comprehensive reference of all endpoints exposed by the FastAPI API Gateway for the Banking Intelligence Portal, including authentication, RBAC, query pipelines, and features across all page modules.

---

## Authentication & Session

### 1. Authenticate / Login
*   **Endpoint:** `POST /auth/login`
*   **Description:** Authenticate using system credentials. Real DB lookup is performed against the `users` table. Returns a JWT access token.
*   **Request Type:** `Form-data`
*   **Parameters:**
    *   `username` (string, required)
    *   `password` (string, required)
*   **Response:**
    ```json
    {
      "access_token": "eyJhbGciOi...",
      "user_id": "analyst_001",
      "user_role": "analyst",
      "expires_in": 1800
    }
    ```

### 2. Current User Profile
*   **Endpoint:** `GET /users/me` (Alias: `GET /auth/me`)
*   **Description:** Fetch the logged-in user's profile information from the database.
*   **Auth Required:** Bearer JWT (Any Role)
*   **Response:**
    ```json
    {
      "user_id": "analyst_001",
      "email": "analyst_001@bankintel.hq",
      "name": "Analyst One",
      "role": "analyst",
      "bank_id": "hq_main",
      "created_at": "2026-06-12T12:00:00Z",
      "last_login": "2026-06-12T15:30:00Z",
      "status": "active"
    }
    ```

---

## Natural Language Query

### 1. Execute Query Pipeline
*   **Endpoint:** `POST /query`
*   **Description:** Submits a natural language banking query to the orchestration service, which executes intent classification, schema validation, entity resolution, SQL translation, validation, compliance checks, DB execution, and insight generation.
*   **Auth Required:** Bearer JWT (Any Role)
*   **Request Body:**
    ```json
    {
      "query": "Show total deposits by customer segment",
      "format": "json"
    }
    ```
*   **Response:** Includes status, final dataset, structural metadata, trace steps from each agent, and LLM-generated insights.

---

## Dashboard Module
*Access restricted to Roles: `analyst`, `manager`, `admin`*

### 1. Financial Overview
*   **Endpoint:** `GET /dashboard/overview`
*   **Description:** Aggregates metrics (customers, accounts, deposit sums, transaction count, risk counts) from real main database tables.
*   **Response:**
    ```json
    {
      "total_customers": 210,
      "total_accounts": 415,
      "active_accounts": 385,
      "total_deposits": 12345678.50,
      "monthly_transactions": 1234,
      "high_risk_customers": 18,
      "last_updated": "2026-06-12T15:00:00Z"
    }
    ```

### 2. Main KPI Metrics
*   **Endpoint:** `GET /dashboard/kpis`
*   **Description:** Key metrics (total deposits, monthly revenue, active customers, average risk score) with calculated trend direction compared to historical windows.
*   **Response:** Array of KPI objects (see schema below).

### 3. Recent Activity Feed
*   **Endpoint:** `GET /dashboard/recent-activity`
*   **Description:** Returns the most recent transactions across all banking accounts.
*   **Query Parameters:** `limit` (default: 10, max: 50)

### 4. Dynamic Chart Data
*   **Endpoint:** `GET /dashboard/charts/{chart_id}`
*   **Description:** Generates time-series, distribution, or concentration datasets for charts.
*   **Path Parameter:**
    *   `revenue_trend`: 12-month transaction fee revenue timeline.
    *   `risk_levels`: Distribution of active risk flags by severity.
    *   `concentration`: Deposits concentration sorted by customer segment.
    *   `growth_rate`: New customer acquisitions by month.

---

## KPI Center
*Access restricted to Roles: `analyst`, `manager`, `admin`*

### 1. KPI Catalog Definitions
*   **Endpoint:** `GET /kpi/catalog`
*   **Description:** Retrieves static metadata definitions for registered KPIs (formula descriptions, categories, refresh intervals).

### 2. Current KPI Values
*   **Endpoint:** `GET /kpi/values` (Alias: `GET /kpi/metrics`)
*   **Description:** Calculates live KPI values (adds KYC compliance rate and open risk flags to the core stats).
*   **Response:**
    ```json
    [
      {
        "kpi_id": "total_deposits",
        "name": "Total Deposits",
        "value": 12345678.50,
        "metric_type": "currency",
        "trend": 2.3,
        "trend_direction": "up",
        "last_updated": "2026-06-12T15:00:00Z",
        "data_freshness": "real-time"
      }
    ]
    ```

### 3. Historical Trends
*   **Endpoint:** `GET /kpi/trends`
*   **Description:** Aggregates monthly KPIs (revenue, transaction count, average size) for a configurable history.
*   **Query Parameters:** `months` (default: 12, max: 24)

---

## Risk Center
*Access restricted to Roles: `analyst`, `manager`, `admin`*

### 1. Risk Overview
*   **Endpoint:** `GET /risk/overview`
*   **Description:** Live counts of active risk flags by severity, plus overall portfolio risk averages.

### 2. Risk Flags List
*   **Endpoint:** `GET /risk/flags`
*   **Description:** Paginated registry of all risk flags flagged by system heuristics or AI.
*   **Query Parameters:**
    *   `page` (default: 1)
    *   `page_size` (default: 20)
    *   `severity` (optional: `low`, `medium`, `high`, `critical`)
    *   `resolved` (optional: boolean)

### 3. Risk Segments
*   **Endpoint:** `GET /risk/segments`
*   **Description:** Aggregates risk levels and total deposits exposure grouped by customer segments.

### 4. Portfolio Summary
*   **Endpoint:** `GET /risk/summary` (Alias/Detail)
*   **Description:** Simple severity distributions and high-risk client volumes.

---

## Compliance & Audit
*Access restricted to Roles: `compliance`, `admin`*

### 1. Compliance Dashboard Overview
*   **Endpoint:** `GET /compliance/overview` (Alias: `GET /compliance/report`)
*   **Description:** Health status indicators across regulations (GDPR, PCI-DSS, AML, KYC) based on active violations and verification completeness.

### 2. Compliance Rules Registry
*   **Endpoint:** `GET /compliance/rules`
*   **Description:** Catalog of data protection rules, compliance thresholds, and automated guardrails.
*   **Query Parameters:**
    *   `regulation` (optional: GDPR, AML, KYC, PCI-DSS)
    *   `enabled_only` (default: true)

### 3. Violations Tracker
*   **Endpoint:** `GET /compliance/violations`
*   **Description:** Detailed logs of query compliance rejections or database security rules infractions.
*   **Query Parameters:** `page`, `page_size`, `regulation`, `severity`, `date_from`, `date_to`.

### 4. Immutable Audit Logs
*   **Endpoint:** `GET /audit/logs`
*   **Description:** Queries the dedicated read-only audit database (`postgres-audit`).
*   **Query Parameters:**
    *   `page` (default: 1)
    *   `page_size` (default: 25)
    *   `user_id` (optional: filter by actor)
    *   `action` (optional: filter by type, e.g. `login`, `nl_query`, `api_call`)
    *   `date_from` / `date_to` (optional: filter by timestamp)

---

## Reports Center
*Access restricted to Roles: `analyst`, `manager`, `admin`*

### 1. List Generated Reports
*   **Endpoint:** `GET /reports`
*   **Description:** Retrieve history of generated formal compliance and activity documents.
*   **Query Parameters:** `page`, `page_size`, `regulation`, `status` (`draft`, `submitted`).

### 2. Generate Report
*   **Endpoint:** `POST /reports/generate`
*   **Description:** Compiles real aggregated transactions, KYC, or risk databases into a report document and inserts a new draft entry.
*   **Request Body:**
    ```json
    {
      "report_type": "aml_summary",
      "regulation": "AML",
      "period_start": "2026-05-01",
      "period_end": "2026-05-31"
    }
    ```

---

## System Administration
*Access restricted to Role: `admin` only*

### 1. Users Management
*   **Endpoint:** `GET /admin/users`
*   **Description:** Paginated system user accounts list from `users` table.

### 2. Roles Catalog
*   **Endpoint:** `GET /admin/roles`
*   **Description:** Defined roles, active user counts under each role, and associated permission claims.

### 3. Permissions Registry
*   **Endpoint:** `GET /admin/permissions`
*   **Description:** System permission strings, descriptive mappings, and role-mapping grids.
