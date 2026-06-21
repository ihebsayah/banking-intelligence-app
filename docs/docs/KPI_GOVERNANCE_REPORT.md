# Banking KPI Governance & Intelligence Center Report

This report documents the implementation of the **KPI Governance & Intelligence Center** within the Banking Intelligence Platform. This new dashboard and service layer transitions the platform from basic metrics reporting to a robust, audited governance framework for business metrics.

---

## 1. Database Schema Extensions

The schema was extended using safe, migration-friendly scripts (`init/02-users-kpis.sql`).

```sql
-- 1. KPI Categories
CREATE TABLE IF NOT EXISTS kpi_categories (
    category_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

-- 2. KPI Owners
CREATE TABLE IF NOT EXISTS kpi_owners (
    owner_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(100)
);

-- 3. Update Definitions Catalog
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS formula TEXT;
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active';
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS unavailable_reason TEXT;
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS owner_id VARCHAR(50) REFERENCES kpi_owners(owner_id);
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS source_tables VARCHAR(100)[];
ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS refresh_frequency VARCHAR(50) DEFAULT 'real-time';

-- 4. KPI Thresholds
CREATE TABLE IF NOT EXISTS kpi_thresholds (
    kpi_id VARCHAR(50) PRIMARY KEY REFERENCES kpi_definitions(kpi_id) ON DELETE CASCADE,
    healthy_min NUMERIC,
    healthy_max NUMERIC,
    warning_min NUMERIC,
    warning_max NUMERIC,
    critical_min NUMERIC,
    critical_max NUMERIC,
    healthy_label VARCHAR(100),
    warning_label VARCHAR(100),
    critical_label VARCHAR(100)
);

-- 5. KPI Change History (Audit Log)
CREATE TABLE IF NOT EXISTS kpi_history (
    history_id SERIAL PRIMARY KEY,
    kpi_id VARCHAR(50) NOT NULL,
    changed_by VARCHAR(100) NOT NULL,
    change_type VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 2. KPI Governance Catalog

The catalog consists of **18 registered KPIs** categorized under major banking sectors:

| KPI ID | Name | Category | Metric Type | Status | Formula / Definition | Owner |
|---|---|---|---|---|---|---|
| `total_deposits` | Total Deposits | Liquidity | Currency | `active` | `SUM(balance) FROM accounts WHERE status = 'active'` | Sarah Jenkins |
| `monthly_revenue` | Monthly Fee Income | Profitability | Currency | `active` | `SUM(ABS(amount)) * 0.002 FROM transactions WHERE date >= NOW() - 30 days` | Sarah Jenkins |
| `active_customers` | Active Customers | Customer | Count | `active` | `COUNT(DISTINCT customer_id) FROM accounts WHERE status = 'active'` | Sophia Chen |
| `avg_risk_score` | Avg Risk Score | Compliance | Ratio | `active` | `AVG(risk_score) FROM customers` | David Kross |
| `kyc_compliance_rate` | KYC Compliance Rate | Compliance | Percentage | `active` | `100 * COUNT(kyc_verified) / COUNT(customer_id)` | David Kross |
| `total_risk_flags` | Total Risk Flags | Compliance | Count | `active` | `COUNT(*) FROM risk_flags WHERE resolved = FALSE` | David Kross |
| `net_interest_margin` | Net Interest Margin | Profitability | Percentage | `unavailable` | *(Unavailable: Requires ledger interest statements)* | CFO Office |
| `cost_to_income_ratio` | Cost to Income | Profitability | Percentage | `unavailable` | *(Unavailable: Requires operational cost data)* | CFO Office |
| `return_on_assets` | Return on Assets (ROA) | Profitability | Percentage | `unavailable` | *(Unavailable: Requires balance sheet data)* | CFO Office |
| `loan_to_deposit_ratio` | Loan-to-Deposit (LDR) | Liquidity | Percentage | `unavailable` | *(Unavailable: Requires active loan contract accounts)* | CFO Office |
| `liquidity_coverage_ratio` | Liquidity Coverage (LCR) | Liquidity | Percentage | `unavailable` | *(Unavailable: Requires high-quality liquid assets)* | CFO Office |
| `npl_ratio` | Non-Performing Loans (NPL) | Credit Quality | Percentage | `unavailable` | *(Unavailable: Requires loan delinquency fields)* | Risk Committee |
| `provision_coverage_ratio` | Provision Coverage | Credit Quality | Percentage | `unavailable` | *(Unavailable: Requires credit provisions ledger)* | Risk Committee |
| `cet1_ratio` | CET1 Ratio | Capital | Percentage | `unavailable` | *(Unavailable: Requires Tier 1 capital definitions)* | CFO Office |
| `capital_adequacy_ratio` | Capital Adequacy (CAR) | Capital | Percentage | `unavailable` | *(Unavailable: Requires risk-weighted assets estimation)* | CFO Office |
| `customer_growth_rate` | Customer Growth Rate | Customer | Percentage | `active` | `((curr - prev) / prev) * 100` | Sophia Chen |
| `customer_retention_rate` | Customer Retention Rate | Customer | Percentage | `active` | `(active_customers / total_customers) * 100` | Sophia Chen |
| `compliance_score` | Compliance Score | Compliance | Count | `active` | `MAX(0, 100 - (open_violations * 10))` | David Kross |

---

## 3. Computation Engine & Mathematical Formulas

The computation engine is implemented in `services/api_gateway/kpi_service.py` via the `KPIService` class. It manages:

1. **Active KPIs**: Dynamically runs PostgreSQL aggregate queries using `asyncpg` to calculate values in real-time.
2. **Unavailable KPIs**: Safely returns `status="unavailable"` along with the specific metadata, ownership info, and `unavailable_reason`.
3. **Threshold Evaluation**: Checks calculated metrics against nested target bands (Healthy → Warning → Critical).
4. **Trend Calculation**: Compares current value against a 30-day lookback window.
5. **AI Insights**: Generates structured, qualitative intelligence summaries using SQL-based contextual segments.

---

## 4. REST API Integration Points

The API Gateway (`services/api_gateway/routes.py`) exposes the following endpoints:

- `GET /kpi/catalog`: Returns the complete governance metadata definitions. Supporting filters: `category`, `status`.
- `GET /kpi/values`: Current calculated metric values with governance status.
- `GET /kpi/dashboard`: High-level aggregated statistics (total counts of active, warning, critical, unavailable).
- `GET /kpi/trends`: Time-series trends (returns 12-month series). Supports targeting by `kpi_id`.
- `GET /kpi/{id}`: Detailed dashboard card data for one metric, containing thresholds and change history.
- `GET /kpi/{id}/insights`: Returns an AI-powered quantitative explanation/recommendation for the target metric.

---

## 5. Frontend UI Implementation

The new page `KpiGovernancePage.tsx` was added in `frontend/src/pages/` and connected as `/kpi-governance`.

- **KPI Cards Overview**: Displays overall system metrics (total, active, unavailable, warning, and critical KPIs).
- **KPI Catalog Grid Table**: Details individual metric definitions, owners, live values, and category style pills. Supporting filters for categories, status, and thresholds.
- **Detail Drawer Panel**: Instantly slides out from the right to expose:
  - KPI Formula presentation.
  - Active sparkline chart (12-month timeline).
  - Target thresholds (Healthy, Warning, Critical) ranges.
  - KPI Owner information (name, role, email contact).
  - **AI-powered Insight card**: Dynamic recommendations and actions generated for that KPI.
  - Change history logs tracking the KPI's history.

---

## 6. Verification & Test Suite

All tests executed locally outside of Docker and passed successfully:

- `test_kpi_governance.py`: Validates calculation methods (`compute_kpi`), threshold evaluation bands, fallback scenarios, and trend queries. (15/15 Passed)
- `test_portal_endpoints.py`: Validates backwards compatibility of old values/trends endpoints and verifies response models. (52/52 Passed)
- React frontend compiled successfully for production with zero bundle errors.
