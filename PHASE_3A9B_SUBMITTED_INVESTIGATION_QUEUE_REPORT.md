# Phase 3A.9B — Submitted Investigation Review Queue Report

## 1. Existing Investigation State Model
The `investigations` domain state model comprises seven discrete states:
- `open`: Newly instantiated investigation created from an alert or manual trigger.
- `active`: Analyst is actively working on the investigation and recording findings.
- `awaiting_information`: Suspended while awaiting response from an Information Request.
- `submitted`: Operational findings and conclusion are complete; submitted by Analyst for Compliance review.
- `returned`: Compliance reviewer returned the investigation to the Analyst for rework.
- `completed`: Compliance review complete; investigation finalized.
- `cancelled`: Terminated prior to completion.

---

## 2. Existing Analyst Queue Architecture
- Endpoint: `GET /api/v1/investigations/assigned`
- Required Permission: `investigation:read_own`
- Scope & Assignment: Filters investigations where `assigned_to = user.user_id` and `scope_id = caller_scope`.
- Purpose: Serves as the operational work queue for Analysts managing active investigations.

---

## 3. Submission Boundary Discovered
- Transition `active` -> `submitted`:
  - Required Permission: `investigation:transition`
  - Validation: Requires `findings_text` or `findings_refs` to be present.
  - Side Effects: Records `submitted_at = timestamp`, logs timeline entry (`investigation.submitted`), and emits audit outbox event (`investigation.submitted`).
- Transition `submitted` -> `completed` / `returned`:
  - Required Permission: `investigation:review` (held exclusively by Compliance Officers).

---

## 4. Compliance Queue Design
- Separation: Compliance Officers do NOT consume the Analyst `/assigned` queue.
- Dedicated Surface: Compliance Officers are presented with a server-filtered queue containing only investigations that have crossed the Analyst submission boundary (`status = 'submitted'`).
- Display & Triage Context: Identifiers, originating alert ID, status, priority/severity, assigned Analyst, submission timestamp, and update timestamp.

---

## 5. Backend Endpoint
- **URL**: `GET /api/v1/investigations/submitted`
- **Router File**: [investigations.py](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/workbench/routers/investigations.py)
- **Service Method**: `InvestigationService.list_submitted(user, scope, priority, page, per_page)`
- **Response Schema**: `InvestigationListResponse`

---

## 6. Permission Enforcement
- **Required Permission**: `investigation:review` evaluated against `Resource(id="submitted", status="active", entity_type="collection")`.
- **Role Permissions**:
  - `compliance`: Holds `investigation:review` -> Granted access.
  - `analyst`: Holds `investigation:read_own` (lacks `investigation:review`) -> Denied with HTTP 403 `PermissionDeniedError`.
  - `admin`: Has `("admin", "investigation:review")` registered in `PROHIBITED` -> Denied with HTTP 403 `ProhibitedComboError`.

---

## 7. Server-Side Filtering Rules
- Backend performs strict database filtering:
  ```sql
  SELECT * FROM investigations 
  WHERE scope_id = $1 AND status = 'submitted'
  ORDER BY created_at DESC LIMIT $2 OFFSET $3
  ```
- Client-side filtering is eliminated. Only submitted investigations in the caller's scope are returned.

---

## 8. Frontend Queue Behavior
- **Component**: [InvestigationQueuePage.tsx](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/components/investigations/InvestigationQueuePage.tsx)
- **API Dispatch**: [investigationsApi.ts](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/api/investigationsApi.ts) (`listSubmitted`)
- **Permission Detection**: Uses `useAuth()` hook to check `hasPermission(PERMISSIONS.INVESTIGATION_REVIEW)` vs `hasPermission(PERMISSIONS.INVESTIGATION_READ_OWN)`.

---

## 9. Analyst vs. Compliance Behavior
- **Analyst**:
  - Primary View: "My Assigned Investigations" (`/api/v1/investigations/assigned`).
  - Cannot view Compliance review queue.
- **Compliance Officer**:
  - Primary View: "Submitted for Review" (`/api/v1/investigations/submitted`).
  - Table displays assigned Analyst column and submission timestamp.
- **Dual-Role Users**:
  - Tab selector permits switching between "Submitted for Review" and "My Assigned Investigations".

---

## 10. Investigation Detail Integration
- Selecting a row in the Compliance queue opens [InvestigationDetailPage.tsx](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/frontend/src/components/investigations/InvestigationDetailPage.tsx).
- Preserves:
  - Linked alert context and resolution metadata.
  - Authorized `CustomerContextPanel` and Customer 360 bridge.
  - Internal/external comments and activity timeline.
- **Decision Boundaries**: Final Compliance decision actions (Approve/Complete, Return, Escalate) are deliberately deferred to Phase 3A.9C.

---

## 11. Assignment / Ownership Semantics
- Submitted investigations retain their original Analyst assignment (`assigned_to`).
- Queue listing is shared across all authorized Compliance Officers within the given organizational scope (`scope_id`).
- No database migration was required; persistence schema supports status-based queue isolation natively.

---

## 12. Files Changed
1. `services/shared/authorise.py`: Added `"investigation:review"` to `COLLECTION_TRANSITIONS["active"]`.
2. `services/workbench/services/investigation_service.py`: Added `list_submitted` service method.
3. `services/workbench/routers/investigations.py`: Added `GET /api/v1/investigations/submitted` router endpoint.
4. `services/workbench/tests/test_submitted_queue_authorization.py`: Added backend unit test suite.
5. `frontend/src/api/investigationsApi.ts`: Added `listSubmitted` method.
6. `frontend/src/components/investigations/InvestigationQueuePage.tsx`: Updated with permission-aware queue mode selection.
7. `frontend/src/api/__tests__/investigationsApi.test.ts`: Added unit tests for `listSubmitted`.
8. `frontend/src/components/investigations/__tests__/InvestigationQueuePage.test.tsx`: Added frontend component unit tests.

---

## 13. Security Invariants
- Backend authorization is authoritative; no client-side decision on queue access.
- Deny by default enforced across all roles.
- Admin role Segregation of Duties (SoD) enforced via `PROHIBITED` combo check.
- Customer 360 authorization and PII masking remain untouched and server-controlled.

---

## 14. Test Results
- **Backend Pytest**:
  - `test_submitted_queue_authorization.py`: 4 passed
  - `test_assigned_list_authorization.py`: 9 passed
  - Total backend tests: 13 passed in 1.65s
- **Frontend Vitest**:
  - `investigationsApi.test.ts`: 11 passed
  - `InvestigationQueuePage.test.tsx`: 5 passed
  - Total frontend test suite: 68 passed across 12 files
- **TypeScript Typecheck**: `npx tsc --noEmit` passed with 0 errors.
- **ESLint**: Passed with 0 errors/warnings on changed files.

---

## 15. Remaining Workflow Gaps
- Decision Forms & Actions: Phase 3A.9B allows Compliance to receive and inspect submitted investigations. Final review dispositions (Mark Not Harmful, Request Additional Information, Escalate to Compliance Case) will be implemented in Phase 3A.9C.

---

## 16. Readiness for Phase 3A.9C
The dedicated backend endpoint, permission model, and frontend queue boundary for submitted investigation reviews are fully verified and operational. The system is ready for Phase 3A.9C (Compliance Review Decision Actions).
