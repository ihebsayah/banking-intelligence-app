# Phase 3A.9C Workflow Blocker Report

## 1. Executive Summary

Discovery for Phase 3A.9C revealed a structural schema blocker in the `information_requests` domain entity. Per Phase 3A.9C Stop Condition A, implementation has been halted before modifying code or applying database migrations.

---

## 2. Exact Blocker

`InformationRequest` currently requires a mandatory non-null `case_id` at the database schema, Pydantic model, repository SQL query, and service validation layers.

An `InformationRequest` cannot be created directly against a submitted `Investigation` (without an existing `ComplianceCase`). Attempting to insert an `InformationRequest` with `case_id = NULL` violates database foreign key / NOT NULL constraints and breaks repository SQL joins.

---

## 3. Current Schema & Implementation Analysis

### A. Database Schema (`migrations/versions/0004_add_operational_entities.py`)
```sql
CREATE TABLE IF NOT EXISTS information_requests (
    ir_id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             UUID        NOT NULL
                        REFERENCES compliance_cases(case_id) ON DELETE RESTRICT,
    investigation_id    UUID        REFERENCES investigations(investigation_id) ON DELETE RESTRICT,
    created_by          VARCHAR(100) NOT NULL REFERENCES users(user_id),
    assigned_to         VARCHAR(100) NOT NULL REFERENCES users(user_id),
    ...
);
```
- `case_id` is defined as `UUID NOT NULL`.
- `investigation_id` exists as `UUID` (nullable), but `case_id` remains mandatory.

### B. Pydantic Model (`services/workbench/models.py`)
```python
class InformationRequest(BaseModel):
    ir_id: str
    case_id: str
    investigation_id: Optional[str] = None
    ...
```

### C. Repository Layer (`services/workbench/repos.py`)
Queries join directly on `compliance_cases.case_id`:
```sql
SELECT ir.* FROM information_requests ir
JOIN compliance_cases c ON c.case_id = ir.case_id
WHERE ir.assigned_to = $1 AND c.scope_id = ANY($2::text[])
```
- If `case_id` is `NULL`, INNER JOIN on `compliance_cases` drops the record from query results.

### D. Service Layer (`services/workbench/services/information_request_service.py`)
- `InformationRequestService.create(self, user, case_id: str, req)` strictly requires `case_id` and validates that `ComplianceCase.status == "under_review"`.

---

## 4. Secondary Structural Considerations

### A. Compliance Review Outcome Representation (Stop Condition B)
- `Investigation` model (`models.py`) has fields: `status`, `return_reason`, `findings_text`, `findings_refs`, `conclusion`, `started_at`, `submitted_at`, `completed_at`.
- There is no persisted `review_outcome` column (e.g. `'not_harmful'` vs `'escalated_to_case'`) or explicit `reviewed_by` / `reviewed_at` field on `Investigation`. While `Comment` and `ActivityTimelineEntry` can record the rationale, storing structured outcome metadata cleanly requires a convention (e.g. `Comment` with specific event metadata or a small column addition).

### B. Transactional Escalation Orchestration (Stop Condition C)
- Creating a `ComplianceCase` and transitioning an `Investigation` currently exist as separate service operations (`CaseService.create` and `InvestigationService.transition_status`).
- An atomic backend orchestration method (e.g. `escalate_investigation_to_case` in `InvestigationService` running inside a `UnitOfWork` transaction) is needed so case creation and investigation completion succeed or fail together.

---

## 5. Smallest Proposed Schema Change

To support direct Information Requests on Investigations (Outcome B) without hacky workarounds:

### Migration `0005_allow_investigation_information_requests.py`

1. **Alter Column Constraint**:
   ```sql
   ALTER TABLE information_requests ALTER COLUMN case_id DROP NOT NULL;
   ```
2. **Add Table Check Constraint**:
   ```sql
   ALTER TABLE information_requests ADD CONSTRAINT chk_ir_target_entity
   CHECK (case_id IS NOT NULL OR investigation_id IS NOT NULL);
   ```
3. **Update Scope Resolution Query**:
   Update `InfoRequestRepo.list_assigned` and `count_assigned` to LEFT JOIN both `compliance_cases` and `investigations` for scope resolution:
   ```sql
   SELECT ir.* FROM information_requests ir
   LEFT JOIN compliance_cases c ON c.case_id = ir.case_id
   LEFT JOIN investigations i ON i.investigation_id = ir.investigation_id
   WHERE ir.assigned_to = $1 
     AND COALESCE(c.scope_id, i.scope_id) = ANY($2::text[])
   ```

---

## 6. Affected Services & Components

1. **Backend Schema & Models**:
   - `workbench/models.py`: `InformationRequest.case_id` -> `Optional[str] = None`
   - `workbench/schemas/information_requests.py`: `CreateInformationRequest` to accept `investigation_id` (or `case_id`)
2. **Repositories**:
   - `workbench/repos.py`: `InfoRequestRepo` updated for optional `case_id` and dual-scope fallback (`COALESCE(c.scope_id, i.scope_id)`).
3. **Services**:
   - `workbench/services/information_request_service.py`: Add `create_for_investigation` or extend `create` to handle `investigation_id` target and transition `Investigation` to `awaiting_information`.
   - `workbench/services/investigation_service.py`: Add `escalate_to_case` orchestration method for Outcome C.
4. **Frontend**:
   - `InvestigationDetailPage.tsx`: Add Compliance Review action panel and dialogs for Outcomes A, B, and C.
   - `informationRequestsApi.ts` & `investigationsApi.ts`: Add client endpoints for investigation IR creation and escalation.

---

## 7. Security & Authorization Implications

- **Permission Boundary**: `info_request:create` will be checked against the target `Investigation` (or `ComplianceCase`) resource.
- **Scope Enforcement**: Information requests for investigations remain strictly isolated within the org scope (`scope_id`) of the parent `Investigation`.
- **Role Control**: Only users with `investigation:review` (Compliance Officers) can trigger IR creation or escalation on a submitted investigation. Analysts cannot trigger Compliance review actions.

---

## 8. Test Strategy

1. **Backend Tests**:
   - Test creating IR on `Investigation` without `case_id`.
   - Test `Investigation` status transitions: `submitted` -> `awaiting_information`.
   - Test IR response transitioning `Investigation` from `awaiting_information` -> `submitted`.
   - Test atomic escalation: `submitted` -> `completed` (outcome: `escalated_to_case`) with linked `ComplianceCase`.
   - Test permission isolation (`investigation:review`, scope isolation).
2. **Frontend Tests**:
   - Test button rendering (visible to Compliance with `investigation:review`, hidden from Analyst and Admin).
   - Test modal dialog workflows for Not Harmful, Request Information, and Escalate.

---

## 9. GO / NO-GO Recommendation

**Recommendation**: **NO-GO for inline code modification until Migration 0005 approval**.

**Next Steps**:
1. Review and approve proposed Migration `0005_allow_investigation_information_requests.py`.
2. Once approved, apply migration, update Pydantic models/services/repos, and execute Phase 3A.9C implementation.
