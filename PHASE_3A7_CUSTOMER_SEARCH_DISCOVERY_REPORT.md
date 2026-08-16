# Phase 3A.7 — Customer Search Discovery Report

**Status: DISCOVERY COMPLETE — AWAITING BACKEND ENDPOINT APPROVAL.**
**Produced: 2026-08-16**

---

## 1. Executive Summary & Existing Capabilities Inspected

A thorough discovery audit was conducted across the backend services (`services/api_gateway`, `services/workbench`) and frontend code (`frontend/src`).

### Inspected Backend Surfaces:
- `services/api_gateway/routes.py`:
  - `GET /api/v1/customers/{customer_id}/overview` — Customer 360 overview for a specific customer ID.
  - `GET /api/v1/customers/{customer_id}/transactions` — Paginated transactions for a specific customer ID.
- `services/api_gateway/customer360/repos.py` & `service.py`:
  - `Customer360Repository`: Contains `fetch_customer_core`, `fetch_profile`, `fetch_accounts`, `fetch_loans`, etc., all taking a specific `customer_id`.
  - `Customer360Service`: Contains `get_overview` and `get_transactions`, requiring a known `customer_id`.

### Inspected Frontend Surfaces:
- [`frontend/src/api/customer360Api.ts`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/api/customer360Api.ts): Only contains `getOverview(customerId)` and `getTransactions(customerId, params)`.
- Navigation components (`BankingSidebar.tsx`, `CommandPalette.tsx`, `App.tsx`): Feature routes for `/workbench/alerts`, `/workbench/investigations`, `/workbench/cases`, `/workbench/admin/outbox`, etc., but no Customer 360 global navigation item or search landing page.

---

## 2. Why Existing APIs Cannot Safely Support Customer Search

1. **Exact Customer ID Path Dependency**: Both existing Customer 360 endpoints (`/overview` and `/transactions`) require an exact, known `customer_id` as a path parameter.
2. **No List/Search Endpoint**: No backend endpoint currently exists to query, list, or search authorized customers by ID or name.
3. **Security & Privacy Boundaries**:
   - The frontend cannot guess or brute-force customer IDs.
   - Client-side filtering of all database customers is impossible (no list endpoint exists and downloading the customer database would violate org-scope, PII, and performance constraints).
   - Hardcoding demo customer IDs (such as `CUST_00001`) in navigation is strictly prohibited.

---

## 3. Minimal Proposed Backend Endpoint Proposal

To enable Customer 360 discoverability without compromising security, we propose adding a minimal, secure customer search endpoint to the Customer 360 read bridge.

### 3.1 Proposed Endpoint Definition
- **HTTP Method & Path**: `GET /api/v1/customers`
- **Description**: Search and list authorized customers accessible to the caller's organizational scope.

### 3.2 Request Query Parameters
| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | `Optional[str]` | `None` | Optional search string matching `customer_id` (prefix) or `name` (ILIKE substring). |
| `limit` | `int` | `20` | Pagination limit ($1 \le \text{limit} \le 50$). |
| `offset` | `int` | `0` | Pagination offset ($\ge 0$). |

### 3.3 Response Schema (`CustomerSearchResponse`)

```json
{
  "items": [
    {
      "customer_id": "CUST_00001",
      "name": "Fouad Ben Salah",
      "segment": "PART_PREM",
      "kyc_verified": true,
      "risk_score": "0.85"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### 3.4 Required Permission & Authorization
- **Required Permission**: `customer:read_basic`
- **Audited Decorator**: `@require_any_permission_audited(["customer:read_basic"])`
- **PII Masking**:
  - If the caller possesses `customer:read_pii`, the unmasked `name` is returned.
  - If the caller lacks `customer:read_pii`, the `name` is masked (e.g. `F*** B** S****`) using the existing `mask_pii()` utility in `Customer360Service`.

### 3.5 Organizational Scope Enforcement
- Searches join `customers` with `customer_branches` / `accounts`.
- The user's active org-scopes (fetched via `fetch_user_scopes(user.user_id)`) filter query results so callers **only see customers in their authorized branches/regions**.

---

## 4. Exact Files Likely to Change

1. **Backend**:
   - `services/api_gateway/customer360/repos.py`: Add `search_customers(query, limit, offset, allowed_branches)` method.
   - `services/api_gateway/customer360/service.py`: Add `search_customers(user, query, limit, offset)` method with org-scope resolution, PII masking, and audit payload.
   - `services/api_gateway/routes.py`: Expose `GET /api/v1/customers` route.
   - `services/api_gateway/customer360/tests/test_customer360_service.py` & `test_customer360_routes.py`: Add unit tests for search, org-scope filtering, and PII masking.
2. **Frontend**:
   - `frontend/src/api/customer360Api.ts`: Add `searchCustomers(params)` client function.
   - `frontend/src/components/customers/CustomerSearchPage.tsx`: Lightweight Customer 360 search landing page at `/workbench/customers`.
   - `frontend/src/components/navigation/BankingSidebar.tsx`: Add permission-aware `Customer 360` sidebar link.
   - `frontend/src/components/navigation/CommandPalette.tsx`: Add `Customer 360` entry.
   - `frontend/src/App.tsx`: Register `/workbench/customers` route under `customer:read_basic` protection.

---

## 5. Focused Test Strategy

1. **Backend Unit Tests**:
   - Verify `GET /api/v1/customers` requires `customer:read_basic` (403 for unauthorized users).
   - Verify org-scope restricts returned customers to user's assigned branches.
   - Verify `customer:read_pii` masking behavior on search result names.
   - Verify search term filtering (`q=CUST_00921` or `q=Fouad`).
2. **Frontend Unit Tests**:
   - Verify `Customer 360` sidebar item is visible for users with `customer:read_basic`.
   - Verify sidebar item is hidden for users lacking `customer:read_basic`.
   - Verify `/workbench/customers` renders search page and navigates to `/workbench/customers/:customerId` upon customer selection.

---

## 6. GO / NO-GO Recommendation

**RECOMMENDATION: GO (Approve Backend Surface Extension)**.

Creating the minimal `GET /api/v1/customers` endpoint strictly adheres to existing security patterns (`customer:read_basic`, org-scope filtering, PII masking, and audit logging) and provides the exact server-side capability required for secure, discoverable Customer 360 search.

> **Status**: Implementation is paused per Phase 3A.7 instructions pending user approval of this backend proposal.
