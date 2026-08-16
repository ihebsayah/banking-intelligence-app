# Phase 3A.8 — Access Control & Role Capability Discovery Report

**Document Date:** August 16, 2026  
**Status:** Complete (DISCOVERY ONLY — Zero code or database modifications executed)  
**Target Repository:** `/Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system`  

---

## 1. Executive Summary

This discovery audit establishes the **REAL current access control state** of the Banking Intelligence System across the full authorization chain—from database seed files and Keycloak role mappings to frontend navigation metadata, `ProtectedRoute` gates, action buttons, API Gateway route dependencies, and domain service-level policy evaluation (`authorise()`).

### Key Findings
1. **Critical Compliance Workflow Blockers (BACKEND PERMISSION MISMATCH / ROUTE MISMATCH / MISSING FEATURE):**
   - **Investigations Queue Access:** Compliance Officers currently **cannot access the Investigations queue**. The frontend sidebar item is visible (due to Phase 3A.7 metadata), but `ProtectedRoute` requires `investigation:read_own` (which Compliance lacks), and the backend endpoint `GET /api/v1/investigations/assigned` enforces `investigation:read_own` while filtering strictly by `assigned_to = user_id`. Compliance Officers only possess `investigation:read` (read any), but no endpoint exists to list submitted or all investigations for compliance review.
   - **Information Requests Inbox:** Compliance Officers are denied access to `/workbench/information-requests` by `ProtectedRoute` because `App.tsx` requires `info_request:read_assigned` (which Compliance lacks), even though Compliance Officers possess `info_request:read` to create, accept, return, and cancel Information Requests.

2. **Backend Gateway Role-Group Exclusions (BACKEND PERMISSION MISMATCH):**
   - The API Gateway uses a hardcoded `require_roles("business")` dependency for all KPI Analytics, KPI Catalog, KPI History, KPI Trends, and Branch Revenue endpoints. `ROLE_GROUPS["business"]` includes `analyst`, `manager`, `admin`, but **excludes `compliance`**. As a result, Compliance Officers attempting to view the Dashboard, KPI Analytics, or KPI Governance experience **403 Forbidden** errors on backend requests.
   - Conversely, the Risk Monitor backend endpoints (`/api/v1/risk/summary`, `/api/v1/risk/flags`) use `require_roles("compliance")`, which **excludes `analyst`**. Analysts have full access to the Risk Monitor page UI via `ProtectedRoute`, but experience 403 Forbidden errors when loading risk summary/flags data.

3. **Platform Administrator Over-Permissioning (OVER-PERMISSION):**
   - Administrators currently retain direct access to operational banking queues (`alert:read`, `alert:dismiss`, `alert:assign`, `investigation:read`, `investigation:assign`, `case:read`, `case:assign`, `case:reopen`, `info_request:read`, `info_request:cancel`).
   - Customer 360 access for Administrators was already hardened in Phase 3A.2a to a metadata-only view (`customer:read_operational_metadata`), demonstrating the proper pattern for separating technical administration from business data inspection.

4. **Approvals Ownership Clarified:**
   - Voting on gated operational actions (`approval:approve`) is owned **exclusively by the Compliance Officer** role. Analysts and Administrators possess `approval:request` and `approval:read`, but cannot cast votes on approval requests.

---

## 2. Roles Audited

Per explicit prompt instructions, the **Manager** role is **EXCLUDED** from this analysis (deprecated/legacy role).

The three primary target roles audited are:
1. **Analyst** (`analyst`) — Triage, investigate operational alerts, author investigation reports, respond to information requests.
2. **Compliance Officer** (`compliance`) — Review submitted investigations, manage compliance cases, issue information requests, decide regulatory escalations, vote on approval requests.
3. **Administrator** (`admin`) — Platform administration, user/role management, outbox & audit monitoring, technical configuration.

---

## 3. Authorization Architecture & Evaluation Chain

Every action in the system passes through an 8-layer authorization chain:

```
ROLE (Keycloak JWT claim / DB users.role)
 ↓
assigned permissions (role_permissions join table)
 ↓
frontend effective permissions (usePermissions hook / AuthProvider)
 ↓
navigation visibility (lib/navigation.ts NAV_GROUPS filter)
 ↓
ProtectedRoute (App.tsx route wrapper check)
 ↓
frontend actions/buttons (conditional render in component)
 ↓
backend endpoint permission (FastAPI Depends: require_roles / require_any_permission_audited)
 ↓
service-level authorization (shared.authorise() 10-step policy engine)
 ↓
actual capability (Domain Service execution + UnitOfWork commit)
```

### Critical Authorization Chain Insights
- **Navigation Visibility vs Route Protection:** In Phase 3A.7, `lib/navigation.ts` was updated with arrays of acceptable permissions (e.g. `[PERMISSIONS.INVESTIGATION_READ_OWN, PERMISSIONS.INVESTIGATION_READ]`). However, `App.tsx` routes were left using single strict permissions (e.g. `requiredPermission="investigation:read_own"`). This creates a direct discrepancy where sidebar links are visible to a role, but clicking them causes `ProtectedRoute` to redirect to `/unauthorized`.
- **Route Protection vs Backend API Gate:** `ProtectedRoute` only checks frontend JWT/session claims. If `ProtectedRoute` passes (or is bypassed via direct URL), the backend API enforces its own dependencies (`require_roles`, `require_any_permission_audited`). If the backend dependency uses a different role group or permission name, the request fails with 403 Forbidden.
- **Backend Route Gate vs Service `authorise()`:** API Gateway endpoints pass requests to domain services. Workbench domain services invoke `shared.authorise(user, action, resource, db, ctx)`. `authorise()` evaluates action validity, role prohibitions, granted permissions, organizational scope (`scope_id`), ownership/assignment (`assigned_to`), entity status lifecycle, conflict of interest, and approval prerequisites.

---

## 4. Effective Permissions Currently Assigned

Loaded from `init/10-phase2b-permission-seeds.sql` and `init/11-phase3a2-customer-permission-seeds.sql`:

### 4.1 Analyst (`analyst`)
- `workbench:access`
- **Alerts:** `alert:read_assigned`, `alert:acknowledge`, `alert:dismiss`, `alert:investigate`, `alert:transition`
- **Investigations:** `investigation:read_own`, `investigation:update`, `investigation:modify_findings`, `investigation:transition`
- **Cases:** `case:read_assigned`
- **Information Requests:** `info_request:read_assigned`, `info_request:respond`
- **Approvals:** `approval:request`, `approval:read`
- **Comments/Timeline:** `comment:create`, `comment:read`, `timeline:read`
- **Notifications:** `notification:read`, `notification:update`
- **Customer 360:** `customer:read`, `customer:read_basic`, `customer:read_financial`, `customer:read_transactions`, `customer:read_kyc`, `customer:read_risk` (PII masked by service)

### 4.2 Compliance Officer (`compliance`)
- `workbench:access`
- **Alerts:** `alert:read_assigned`, `alert:transition`
- **Investigations:** `investigation:read`, `investigation:review` *(Lacks `investigation:read_own`)*
- **Cases:** `case:create`, `case:read_assigned`, `case:transition`, `case:decision`, `case:close`
- **Information Requests:** `info_request:create`, `info_request:read`, `info_request:accept`, `info_request:return`, `info_request:cancel` *(Lacks `info_request:read_assigned`)*
- **Approvals:** `approval:request`, `approval:approve`, `approval:read`
- **Comments/Timeline:** `comment:create`, `comment:read`, `comment:view_internal_content`, `timeline:read`
- **Notifications:** `notification:read`, `notification:update`
- **Customer 360:** `customer:read`, `customer:read_basic`, `customer:read_financial`, `customer:read_transactions`, `customer:read_kyc`, `customer:read_risk`, `customer:read_compliance_history`, `customer:read_pii` (Full unmasked PII + compliance history)

### 4.3 Administrator (`admin`)
- `workbench:access`
- **Alerts:** `alert:read`, `alert:assign`, `alert:dismiss`
- **Investigations:** `investigation:read`, `investigation:assign`
- **Cases:** `case:read`, `case:assign`, `case:reopen`
- **Information Requests:** `info_request:read`, `info_request:cancel`
- **Approvals:** `approval:request`, `approval:read`
- **Comments/Timeline:** `comment:create`, `comment:read`, `comment:view_metadata`, `comment:redact`, `timeline:read`
- **Notifications:** `notification:read`, `notification:update`
- **Admin System:** `admin:outbox_monitor`, `admin:outbox_retry`, `read:audit_logs`, `admin:users`, `admin:roles`
- **Customer 360:** `customer:read`, `customer:read_basic`, `customer:read_operational_metadata` (Metadata-only: counts, risk classification, active flags; no financials/PII)

---

## 5. Current Frontend Visibility Matrix

| Area | Nav Group | Analyst | Compliance Officer | Administrator |
|------|-----------|---------|--------------------|---------------|
| **Dashboard** | General | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **Branches** | General | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **Customer 360** | Operational Workbench | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **Alert Queue** | Operational Workbench | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **Investigations** | Operational Workbench | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **Cases** | Operational Workbench | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **Information Requests** | Operational Workbench | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **Approvals** | Operational Workbench | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **AI Assistant** | Intelligence & Analytics | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **KPI Analytics** | Intelligence & Analytics | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **KPI Governance** | Intelligence & Analytics | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **Risk Monitor** | Intelligence & Analytics | **VISIBLE** | **VISIBLE** | **VISIBLE** |
| **Compliance Workspace**| Intelligence & Analytics | **HIDDEN** | **VISIBLE** | **VISIBLE** |
| **Reports** | Intelligence & Analytics | **HIDDEN** | **HIDDEN** | **VISIBLE** |
| **Outbox Monitor** | Administration | **HIDDEN** | **HIDDEN** | **VISIBLE** |
| **Admin** | Administration | **HIDDEN** | **HIDDEN** | **VISIBLE** |

---

## 6. Current Backend Capability Matrix

*Legend: NONE (Denies / 403), READ, READ ASSIGNED, CREATE, UPDATE, SUBMIT, REVIEW, REQUEST INFO, ESCALATE, CLOSE, APPROVE, ADMIN*

| Area / Operation | Analyst | Compliance Officer | Administrator |
|------------------|---------|--------------------|---------------|
| **Dashboard (KPI Summary)** | READ | **NONE (403)** | READ |
| **AI Assistant (Query)** | QUERY | QUERY | QUERY |
| **Alerts — List Assigned** | READ ASSIGNED | READ ASSIGNED | **NONE (403)** |
| **Alerts — Acknowledge / Dismiss** | ACKNOWLEDGE / DISMISS | NONE | DISMISS (Admin only) |
| **Alerts — Investigate (Create Inv)** | INVESTIGATE | NONE | NONE |
| **Alerts — Assign** | NONE | NONE | ASSIGN |
| **Investigations — List Assigned** | READ ASSIGNED | **NONE (403)** | **NONE (403)** |
| **Investigations — List Submitted**| **MISSING (No API)**| **MISSING (No API)**| **MISSING (No API)**|
| **Investigations — Read Detail** | READ OWN | READ ANY | READ ANY |
| **Investigations — Edit Findings**| UPDATE | NONE | NONE |
| **Investigations — Submit Report**| SUBMIT | NONE | NONE |
| **Investigations — Review Report**| NONE | REVIEW (completed/returned) | NONE |
| **Customer 360 — Search / Basic** | READ BASIC | READ BASIC | READ BASIC |
| **Customer 360 — Financials / Tx**| READ (Masked PII) | READ (Full PII) | **NONE (403)** |
| **Customer 360 — Metadata Only** | READ FULL | READ FULL | READ METADATA ONLY |
| **Compliance Workspace** | **NONE (403)** | READ | READ |
| **Cases — List Assigned** | READ ASSIGNED | READ ASSIGNED | **NONE (403)** |
| **Cases — Create / Decision / Close**| NONE | CREATE / DECISION / CLOSE | NONE |
| **Cases — Reopen / Assign** | NONE | NONE | REOPEN / ASSIGN |
| **Information Requests — Create** | NONE | CREATE | NONE |
| **Information Requests — Inbox** | READ ASSIGNED | **NONE (403)** | **NONE (403)** |
| **Information Requests — Respond**| RESPOND | NONE | NONE |
| **Information Requests — Accept / Return**| NONE | ACCEPT / RETURN | NONE |
| **Approvals — Create Request** | REQUEST (Alert) | REQUEST (Case) | REQUEST (Reopen) |
| **Approvals — List / Read** | READ | READ | READ |
| **Approvals — Vote Approve/Reject**| NONE | **APPROVE** | NONE |
| **Risk Monitor — Summary / Flags**| **NONE (403)** | READ | READ |
| **KPI Analytics — Metrics / Trends**| READ | **NONE (403)** | READ |
| **KPI Governance — Catalog Read** | READ | **NONE (403)** | READ |
| **KPI Governance — Edit KPIs** | NONE | NONE | ADMIN (Write API) |
| **Administration — User / Role Admin**| NONE | NONE | ADMIN |
| **Audit / Outbox Monitor** | NONE | NONE | MONITOR / RETRY |

---

## 7. Detailed Area-by-Area Analysis

### 7.1 Dashboard (`/dashboard`)
- **Implementation Purpose:** Summary overview of bank KPIs (deposits, revenue, active customers) and branch metrics.
- **Frontend Route:** `/dashboard` wrapped in `<ProtectedRoute><BankingDashboard /></ProtectedRoute>`.
- **Authorization Gaps:**
  - `navigation.ts` and `App.tsx` allow all authenticated roles.
  - Backend `GET /api/v1/kpi/summary` and `GET /api/v1/branches/revenue` enforce `require_roles("business")`.
  - `ROLE_GROUPS["business"]` includes `analyst`, `manager`, `admin`, but excludes `compliance`.
  - **Result:** Compliance Officer sees the Dashboard page, but API calls fail with 403 Forbidden.

### 7.2 Assistant (`/assistant`)
- **Implementation Purpose:** Natural language intelligence query interface (`POST /api/v1/query`).
- **Authorization Gaps:** None. All authenticated users can access the endpoint.

### 7.3 Alerts (`/workbench/alerts`)
- **Implementation Purpose:** Real-time ingestion queue of operational fraud, AML, and credit risk detection events requiring analyst triage.
- **Authorization Gaps:**
  - `App.tsx` requires `requiredPermission="alert:read_assigned"`.
  - Admin possesses `alert:read` (read all), but lacks `alert:read_assigned`.
  - **Result:** Admin clicking on Alert Queue in the sidebar gets redirected to `/unauthorized` by `ProtectedRoute`.

### 7.4 Investigations (`/workbench/investigations`)
- **Implementation Purpose:** Multi-stage investigation of suspicious alert findings by Analysts, culminating in a structured investigation report submitted to Compliance Officers for formal review.
- **Authorization Gaps (CONFIRMED CRITICAL WORKFLOW BLOCKER):**
  - **Navigation vs Route Mismatch:** `lib/navigation.ts` grants visibility to `[INVESTIGATION_READ_OWN, INVESTIGATION_READ]`. Compliance Officer has `investigation:read`. Thus, "Investigations" is visible in the sidebar. However, `App.tsx` specifies `requiredPermission="investigation:read_own"`. Compliance Officer lacks `investigation:read_own`, so clicking the sidebar link causes `ProtectedRoute` to reject them (`/unauthorized`).
  - **Backend List Gate Mismatch:** `GET /api/v1/investigations/assigned` invokes `InvestigationService.list_assigned()`, which explicitly checks `authorise(user, "investigation:read_own", ...)` and queries `WHERE assigned_to = user.user_id`. Even if Compliance bypasses `ProtectedRoute`, the backend returns 403 Forbidden.
  - **Missing Endpoint Feature:** There is no `GET /api/v1/investigations` (list all / list submitted) endpoint for Compliance Officers to inspect investigations submitted for review.
  - **Workflow Gaps:** Investigation reports currently rely solely on text/JSON fields (`findings_text`, `conclusion`, `findings_refs`). File upload attachment mechanisms and direct automated escalation buttons from Investigation to Case do not currently exist.

### 7.5 Customer 360 (`/workbench/customers`)
- **Implementation Purpose:** Consolidated 360-degree customer view (identity, accounts, financial summary, transactions, KYC/AML screening, risk score, compliance history).
- **Authorization Gaps:**
  - **Implementation Status:** Fully hardened in Phase 3A.2a.
  - Analyst gets operational view with masked PII. Compliance Officer gets full view with unmasked PII. Administrator gets `admin_metadata` section only (counts and risk classification; no financials or PII).
  - Admin attempting to access `GET /api/v1/customers/{id}/transactions` is denied 403 (lacks `customer:read_transactions`).

### 7.6 Compliance Workspace (`/compliance`)
- **Implementation Purpose:** Dedicated high-level workspace for Compliance Officers to monitor system-wide compliance risk, review active cases, and handle regulatory escalations.
- **Authorization Gaps:**
  - Hidden from Analyst. Accessible to Compliance Officer and Admin.
  - Risk summary data backend APIs (`/api/v1/risk/summary`) require `require_roles("compliance")` (`compliance`, `admin`), which correctly aligns with frontend access.

### 7.7 Compliance Cases (`/workbench/cases`)
- **Implementation Purpose:** Legal and regulatory case handling following escalation of suspicious activity. Supports formal case decisions (`report_to_authority_recommended`, `internal_monitoring_only`, `no_action_required`) and closure.
- **Authorization Gaps:**
  - `App.tsx` specifies `requiredPermission="case:read_assigned"`.
  - Admin possesses `case:read` (read all), but lacks `case:read_assigned`.
  - **Result:** Admin clicking Cases in the sidebar is redirected to `/unauthorized` by `ProtectedRoute`.

### 7.8 Information Requests (`/workbench/information-requests`)
- **Implementation Purpose:** Formal query channel where Compliance Officers issue Information Requests (IRs) on cases to Analysts, who provide additional evidence/responses.
- **Authorization Gaps:**
  - `App.tsx` specifies `requiredPermission="info_request:read_assigned"`.
  - Compliance Officer possesses `info_request:read` (create/manage IRs on cases), but lacks `info_request:read_assigned` (which is assigned to Analysts for their inbox).
  - **Result:** Compliance Officer clicking Information Requests in the sidebar is redirected to `/unauthorized` by `ProtectedRoute`.

### 7.9 Approvals (`/workbench/approvals`)
- **Implementation Purpose:** Multi-person operational governance queue for high-risk actions.
- **Action Types Implemented:**
  1. `alert_dismissal_critical_high` (Analyst requests, Compliance approves)
  2. `case_closure_critical_high` (Compliance requests, Compliance approves)
  3. `decision_report_to_authority` (Compliance requests, Compliance approves)
  4. `case_reopen` (Admin requests, Compliance approves)
- **Ownership & Self-Approval Analysis:**
  - Voting (`approval:approve`) is granted **ONLY to Compliance Officer**.
  - `_fetch_eligible_approvers()` filters `WHERE u.role = 'compliance' AND u.user_id != requester_id`.
  - Double voting is prevented (`ApprovalDecisionRepo.list_for_request`).

### 7.10 Risk Monitor (`/risk`)
- **Implementation Purpose:** Interactive portfolio risk monitoring dashboard and risk flag tracking.
- **Authorization Gaps:**
  - Frontend (`navigation.ts` and `App.tsx`) allows Analyst, Compliance, Admin.
  - Backend endpoints (`GET /api/v1/risk/summary`, `GET /api/v1/risk/flags`) enforce `require_roles("compliance")`.
  - **Result:** Analyst can open Risk Monitor UI, but API requests return 403 Forbidden.

### 7.11 KPI Analytics (`/kpi`)
- **Implementation Purpose:** In-depth KPI metrics and trend visualization.
- **Authorization Gaps:** Backend endpoints (`/api/v1/kpi/summary`, `/api/v1/kpi/metrics`, `/api/v1/kpi/trends`) use `require_roles("business")`, which excludes `compliance` (403 Forbidden).

### 7.12 KPI Governance (`/kpi-governance`)
- **Implementation Purpose:** Maintenance and governance of KPI definitions, calculation formulas, thresholds, and assigned owners.
- **Authorization Gaps:**
  - Viewing catalog: Backend uses `require_roles("business")`, excluding `compliance` (403 Forbidden).
  - Modifying KPI definitions/thresholds: Backend uses `require_roles("admin")`, which correctly restricts mutations to Admin.

### 7.13 Administration (`/admin`)
- **Implementation Purpose:** Platform user management, role assignment, system setting configuration.
- **Authorization Gaps:** Hidden from Analyst and Compliance. Accessible to Admin.

### 7.14 Audit / System Operations (`/workbench/admin/outbox`)
- **Implementation Purpose:** Audit outbox health monitoring and failed event retry processing.
- **Authorization Gaps:** Hidden from Analyst and Compliance. Accessible to Admin (`admin:outbox_monitor`).

---

## 8. Current vs Intended Access Matrix

| Area | Role | Current Access | Intended Access | Status | Reason |
|------|------|----------------|-----------------|--------|--------|
| **Dashboard** | Compliance | NONE (403) | READ | BACKEND PERMISSION MISMATCH | Gateway `business` role group excludes `compliance`. |
| **Investigations** | Compliance | NONE (403) | READ / REVIEW SUBMITTED | BACKEND PERMISSION MISMATCH & ROUTE MISMATCH | `ProtectedRoute` requires `read_own`; backend lists `assigned_to` only. |
| **Investigations** | Compliance | MISSING | LIST SUBMITTED QUEUE | MISSING FEATURE | No `GET /api/v1/investigations` list endpoint exists. |
| **Information Requests**| Compliance | NONE (403) | CREATE / READ / ACCEPT / RETURN | ROUTE MISMATCH | `ProtectedRoute` requires `info_request:read_assigned`. |
| **Alert Queue** | Admin | NONE (403) | READ (or NONE if restricted) | ROUTE MISMATCH | `ProtectedRoute` requires `alert:read_assigned`, missing `alert:read`. |
| **Cases** | Admin | NONE (403) | READ (or NONE if restricted) | ROUTE MISMATCH | `ProtectedRoute` requires `case:read_assigned`, missing `case:read`. |
| **Risk Monitor** | Analyst | NONE (403) | READ OPERATIONAL RISK | BACKEND PERMISSION MISMATCH | Gateway `/risk/summary` requires `compliance` role group. |
| **KPI Analytics** | Compliance | NONE (403) | READ | BACKEND PERMISSION MISMATCH | Gateway `business` role group excludes `compliance`. |
| **KPI Governance** | Compliance | NONE (403) | READ CATALOG | BACKEND PERMISSION MISMATCH | Gateway `kpi/catalog` requires `business` role group. |
| **Approvals** | Analyst | REQUEST / READ | REQUEST / READ OWN | CORRECT | Analyst can request dismissal & read approval status. |
| **Approvals** | Compliance | REQUEST / VOTE / READ | REQUEST / VOTE / READ | CORRECT | Compliance officer owns approval decision voting. |

---

## 9. Problem Classification

### A. Correct Matches
- Analyst alert triage, investigation creation, findings editing, report submission.
- Compliance case creation, formal decision recording, case closure, IR creation.
- Compliance approval voting ownership.
- Admin user and role administration, outbox retry.
- Section-level Customer 360 data gating (Analyst masked, Compliance full, Admin metadata-only).

### B. Navigation Mismatches
- `lib/navigation.ts` allows Compliance Officer to see Investigations and Information Requests in sidebar, but frontend routes fail.

### C. Route Mismatches (`ProtectedRoute`)
- `App.tsx` lines 103, 105, 107, 109 restrict `/workbench/alerts`, `/workbench/investigations`, `/workbench/cases`, and `/workbench/information-requests` using single `requiredPermission` strings (`alert:read_assigned`, `investigation:read_own`, `case:read_assigned`, `info_request:read_assigned`) instead of accepting `requiredPermission` arrays or checking `canAccess()`.

### D. Backend Permission Mismatches
- Gateway `ROLE_GROUPS["business"]` excludes `compliance`, breaking Dashboard, KPI Analytics, and KPI Governance for Compliance Officers.
- Gateway `/risk/summary` requires `compliance` role group, breaking Risk Monitor for Analysts.
- `InvestigationService.list_assigned()` enforces `investigation:read_own`, returning 403 for Compliance Officers.

### E. Over-Permission Findings
- Administrator possesses direct business queue read/write permissions (`alert:read`, `alert:dismiss`, `investigation:read`, `case:read`, `info_request:read`). Admin should be restricted to platform management, audit, and system operations.

### F. Missing Features
- Missing `GET /api/v1/investigations` list endpoint (for Compliance to view all/submitted investigations).
- Missing file attachment upload capability for investigation reports.
- Missing direct "Escalate to Compliance Case" workflow button on completed/submitted investigations.

---

## 10. Approvals Ownership Analysis

- **Who creates approval requests?**
  - Analyst: `alert_dismissal_critical_high`
  - Compliance: `case_closure_critical_high`, `decision_report_to_authority`
  - Admin: `case_reopen`
- **Who approves them?**
  - **Compliance Officer ONLY** (holds `approval:approve`).
- **What actions require approval?**
  - Dismissing a Critical or High severity Alert.
  - Closing a Critical or High risk Compliance Case.
  - Reopening a closed Compliance Case.
  - Recommending a formal report to external regulatory authority.
- **Is self-approval prevented?**
  - Yes. Notification assignment excludes the requester (`WHERE u.user_id != requester_id`), and `ApprovalDecisionRepo` rejects duplicate votes.

---

## 11. Recommended Target Access Matrix & Intended Capability

| Area | Analyst | Compliance Officer | Administrator |
|------|---------|--------------------|---------------|
| **Dashboard** | READ summary metrics | READ summary metrics | READ platform stats |
| **Assistant** | QUERY banking data | QUERY compliance data | QUERY system data |
| **Alerts** | READ ASSIGNED / ACK / DISMISS / INVESTIGATE | READ ASSIGNED / VIEW CONTEXT | NONE (or READ ALL if operational lead) |
| **Investigations** | CREATE / WORK / SUBMIT OWN | READ / REVIEW SUBMITTED / ACCEPT / RETURN | NONE |
| **Customer 360** | READ OPERATIONAL (Masked PII) | READ FULL (Unmasked PII + History) | READ METADATA ONLY (Counts & Risk Class) |
| **Compliance** | NONE | READ / DECIDE / ESCALATE | READ (Audit mode) |
| **Cases** | READ ASSIGNED | CREATE / TRANSITION / DECIDE / CLOSE | REOPEN / ASSIGN |
| **Information Requests** | READ ASSIGNED / RESPOND | CREATE / READ CASE IRs / ACCEPT / RETURN / CANCEL | CANCEL (Admin override) |
| **Approvals** | REQUEST DISMISSAL / READ OWN | VOTE (APPROVE/REJECT) / REQUEST / READ | REQUEST REOPEN / READ |
| **Risk Monitor** | READ OPERATIONAL RISK | READ FULL RISK / FLAGS | READ FULL RISK |
| **KPI Analytics** | READ ANALYTICS | READ ANALYTICS | READ ANALYTICS |
| **KPI Governance** | READ CATALOG | READ CATALOG | CREATE / EDIT / DELETE KPIS |
| **Administration** | NONE | NONE | FULL ADMIN (Users, Roles, Config) |
| **Audit / System** | NONE | READ AUDIT LOGS | MONITOR OUTBOX / RETRY / AUDIT LOGS |

---

## 12. Proposed Remediation Plan (EXACT CHANGES REQUIRED — DO NOT APPLY YET)

### Step 1: Database Seed Updates (`init/10-phase2b-permission-seeds.sql`)
1. Grant `investigation:read_own` (or broaden `list_assigned` permission check) to `compliance` role so Compliance Officers can view assigned items.
2. Grant `info_request:read_assigned` to `compliance` role (or adjust frontend route gate to accept `info_request:read`).
3. Strip business permissions (`alert:read`, `investigation:read`, `case:read`, `info_request:read`) from `admin` role to enforce least-privilege platform administration.

### Step 2: API Gateway Gateway Role Groups (`services/api_gateway/routes.py`)
1. Update `ROLE_GROUPS["business"]` to include `compliance`:
   ```python
   "business": {UserRole.ANALYST, UserRole.MANAGER, UserRole.COMPLIANCE, UserRole.ADMIN, "analyst", "manager", "compliance", "admin"}
   ```
2. Update `/risk/summary` dependency from `require_roles("compliance")` to a new `require_roles("risk_readers")` group that includes `analyst`, `compliance`, `admin`.

### Step 3: Workbench Investigation Service & Router (`services/workbench`)
1. Add `GET /api/v1/investigations` (list all / list submitted) endpoint in `routers/investigations.py`.
2. Update `InvestigationService.list()` to support filtering by `status="submitted"` and allow users with `investigation:read` permission to view the submitted queue.

### Step 4: Frontend Route Protection (`frontend/src/App.tsx` & `ProtectedRoute.tsx`)
1. Update `ProtectedRoute` to support `requiredPermission: string | string[]`.
2. Update `App.tsx` routes to pass array permissions matching `lib/navigation.ts`:
   - `/workbench/investigations`: `requiredPermission={[PERMISSIONS.INVESTIGATION_READ_OWN, PERMISSIONS.INVESTIGATION_READ]}`
   - `/workbench/information-requests`: `requiredPermission={[PERMISSIONS.INFO_REQUEST_READ_ASSIGNED, PERMISSIONS.INFO_REQUEST_READ]}`
   - `/workbench/alerts`: `requiredPermission={[PERMISSIONS.ALERT_READ_ASSIGNED, PERMISSIONS.ALERT_READ]}`
   - `/workbench/cases`: `requiredPermission={[PERMISSIONS.CASE_READ_ASSIGNED, PERMISSIONS.CASE_READ]}`

---

## 13. Security Implications

- **Data Leakage Risk:** Currently low for PII due to Phase 3A.2a Customer 360 section gating.
- **Workflow Integrity Risk:** High. Compliance Officers cannot review submitted investigations via the standard UI due to authorization blockages, forcing manual workarounds or stalled compliance workflows.
- **Principle of Least Privilege:** Currently violated by Admin role having broad read access to alert and investigation queues.

---

## 14. GO / NO-GO Recommendation

**Verdict: GO FOR REMEDIATION (PHASE 3A.9)**

The discovery phase has pinpointed exact permission key mismatches, frontend route misconfigurations, backend role-group gaps, and missing endpoints. Remediation can be performed cleanly with zero breaking database schema changes.

---

*Report compiled autonomously by Antigravity Agent. Zero files modified during discovery.*
