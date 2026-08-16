# Phase 3A.9C Part 2 — Compliance Review Decision Actions Completion Report

**Executive Summary:**
Successfully implemented the final compliance dispositions for submitted analyst investigations: **Mark Not Harmful** and **Escalate to Compliance Case**. The generic "Approve" button has been completely replaced with dedicated, permission-gated Compliance review actions requiring rationale. All atomicity, idempotency, duplicate escalation, and authorization invariants are fully satisfied.

---

## 1. Domain Implementation Summary

### Backend Services & Routers
- **`InvestigationService.review_not_harmful`**:
  - Requires `investigation:review` permission.
  - Validates `status == "submitted"`.
  - Atomically inside a single `UnitOfWork`:
    - Transitions status: `submitted` → `completed`.
    - Sets `completed_at` timestamp.
    - Inserts internal `Comment` with reviewer's rationale.
    - Inserts `ActivityTimelineEntry` (`investigation.review_not_harmful`).
    - Inserts `AuditOutboxEvent` (`investigation.review_not_harmful`).
  - Route: `POST /api/v1/investigations/{id}/review/not-harmful`

- **`InvestigationService.escalate_to_case`**:
  - Requires `investigation:review` + `case:create` permissions.
  - Validates `status == "submitted"`.
  - App-level duplicate escalation check via `CaseRepo.fetch_active_for_investigation`: returns HTTP 409 `DUPLICATE_ESCALATION` if active case already linked.
  - Atomically inside a single `UnitOfWork`:
    - Creates `ComplianceCase` (status=`open`, unassigned, linked `investigation_id` & originating `alert_id`, inherited `scope_id`).
    - Transitions investigation: `submitted` → `completed` (sets `completed_at`).
    - Inserts internal `Comment` with reviewer's rationale and created `case_id`.
    - Inserts `ActivityTimelineEntry` on investigation (`investigation.escalated_to_case`) and on case (`case.created`).
    - Inserts `AuditOutboxEvent` on investigation (`investigation.escalated_to_case`) and on case (`case.created`).
  - Route: `POST /api/v1/investigations/{id}/review/escalate`

### Repository & Authorization Extensions
- **`CaseRepo.fetch_active_for_investigation`**: Queries `compliance_cases` for non-cancelled case matching `investigation_id`.
- **`shared.authorise`**: Extended `INVESTIGATION_TRANSITIONS["submitted"]` and `CASE_TRANSITIONS["new"]` / `["open"]` to map `case:create` permission cleanly for case escalation.

---

## 2. Frontend User Experience

- **`MarkNotHarmfulDialog`**:
  - Modal with required rationale text input and read-only context (Investigation ID, Alert ID).
  - Calls `investigationsApi.reviewNotHarmful` and refreshes parent investigation view.
- **`EscalateToCaseDialog`**:
  - Modal with pre-filled title, priority selection (`low`/`medium`/`high`/`critical`), and required rationale.
  - Shows read-only originating context (Investigation ID, Alert ID, Scope ID).
  - On success, presents created `case_id` with a direct navigation link ("Go to Case") to `/workbench/cases/{caseId}`.
- **`InvestigationDetailPage`**:
  - Replaced generic placeholder "Approve" button with "Mark Not Harmful" (`var(--accent-green)`) and "Escalate to Case" (`var(--accent-red)`).
  - Preserved "Return for Revision" (`var(--accent-amber)`) and "Request Additional Information" (`var(--accent-blue)`).
  - Enforced permission visibility (`investigation:review` for Not Harmful / Return / Request Info, plus `case:create` for Escalate).
  - Analyst and Admin roles without `investigation:review` see no review action buttons.

---

## 3. Verification & Test Results

### Backend Unit Tests (`test_investigation_review_actions.py`)
- **23/23 tests passed** (0.65s):
  - Mark Not Harmful authorization, state validation, status transition, comment insertion, timeline & outbox events.
  - Escalate to Case authorization, link integrity (`investigation_id`, `alert_id`, `scope_id`), atomic finalization, duplicate escalation rejection (409), outbox events.
  - Information Request regression suite.

### Frontend Unit Tests (`InvestigationDetailPage.test.tsx`)
- **25/25 tests passed** (0.91s):
  - Rendering fields, badges, version, linked alert, and customer context.
  - Analyst flow (start, save findings, submit for review).
  - Compliance review actions (Mark Not Harmful modal & execution, Escalate to Case modal & navigation link, Return for Revision).
  - Strict role/permission button visibility checks.

### Code Quality & Static Analysis
- **TypeScript**: `npx tsc --noEmit` — 0 errors.
- **ESLint**: `npx eslint` — 0 errors, 0 warnings.
