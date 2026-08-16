# Phase 3A.9C.1 — Investigation-Linked Information Requests Report

## 1. Executive Summary

Phase 3A.9C.1 successfully extends the `InformationRequest` domain so Compliance Officers can issue Information Requests directly against a submitted `Investigation` before a `ComplianceCase` exists.

This resolves the schema blocker identified in Phase 3A.9C and enforces the database-level XOR parent constraint: `((case_id IS NOT NULL)::integer + (investigation_id IS NOT NULL)::integer = 1)`.

---

## 2. Key Changes Implemented

### Database Migration (0011_allow_investigation_irs)
- Migration revision `0011_allow_investigation_irs` dropped `NOT NULL` constraint from `information_requests.case_id`.
- Added check constraint `chk_ir_exactly_one_parent` to enforce exact-parent XOR semantics.

### Backend Data Models & Repositories
- Updated `models.py` to make `InformationRequest.case_id` optional.
- Updated `schemas/information_requests.py` (`CreateInformationRequest`, `InformationRequestResponse`, `InformationRequestAdminView`) to support optional `case_id` and optional `investigation_id`.
- Updated `repos.py` (`InfoRequestRepo`):
  - Added `list_by_investigation`, `fetch_active_by_investigation_assignee`, `fetch_active_by_investigation`.
  - Updated `list_assigned` and `count_assigned` with `LEFT JOIN compliance_cases` and `LEFT JOIN investigations` using `COALESCE(c.scope_id, inv.scope_id)` for Analyst inbox visibility.

### Authorization Policy (`services/shared/authorise.py`)
- Added `"info_request:create"` to `INVESTIGATION_TRANSITIONS["submitted"]`.
- Updated Step 5 ownership check to permit Compliance Officers with `info_request:create` and `investigation:review` to issue IRs on submitted investigations assigned to Analysts.

### Service Layer (`services/workbench/services/information_request_service.py`)
- Implemented `_resolve_ir_parent` helper to dynamically resolve case or investigation parentage.
- Implemented `create_for_investigation`:
  - Atomically creates `InformationRequest` and transitions `Investigation.status` from `submitted` to `awaiting_information` within a single `UnitOfWork` transaction.
- Implemented `list_for_investigation`.
- Updated `accept` lifecycle method:
  - Checks for active IRs via `fetch_active_by_investigation`.
  - When no active IRs remain, automatically transitions investigation from `awaiting_information` back to `submitted` state, returning it to the Compliance review queue.

### API Router (`services/workbench/routers/information_requests.py`)
- Registered `POST /investigations/{investigation_id}/information-requests` (`create_investigation_information_request`).
- Registered `GET /investigations/{investigation_id}/information-requests` (`list_investigation_information_requests`).

### Frontend UI & Client (`frontend/src/`)
- Updated `cases.ts` TypeScript interface (`case_id?: string | null`, `investigation_id?: string | null`).
- Updated `informationRequestsApi.ts` client (`createForInvestigation`, `listForInvestigation`, `accept`, `return`).
- Created `RequestInfoDialog.tsx` modal dialog.
- Updated `InvestigationDetailPage.tsx` to display "Request Additional Information" button for Compliance Officers on `submitted` investigations.

---

## 3. Automated Verification

- Added `services/workbench/tests/test_investigation_information_requests.py` covering:
  1. XOR parent check constraint in PostgreSQL integration database (`chk_ir_exactly_one_parent`).
  2. Compliance IR creation and atomic `submitted` -> `awaiting_information` status transition.
  3. Analyst and Admin permission restrictions.
  4. Analyst response loop and Compliance acceptance returning the investigation to `submitted` state when all active IRs are resolved.

---

## 4. Operational & Baseline Verification Status

- Database migration revision `0011_allow_investigation_irs` upgraded cleanly against PostgreSQL.
- Frontend TypeScript compilation (`npx tsc --noEmit`) succeeded with 0 errors.
- Pytest suite (`test_investigation_information_requests.py`) passed 100%.
