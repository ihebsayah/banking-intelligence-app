# Phase 3A.9D — Investigation Report & Evidence Attachments: Discovery & Architecture Report

**Status:** STOP & REPORT (Awaiting Architecture & Migration Approval)  
**Date:** 2026-08-16  
**Phase:** 3A.9D — Investigation Report & Evidence Attachments  

---

## 1. Executive Summary & Discovery Findings

Following the mandatory **Discovery First** requirement for Phase 3A.9D, a complete audit of the repository's database schema, domain models, backend services, and frontend components was conducted.

### 1.1 Existing Investigation Report Capabilities
The existing `Investigation` model and database table (`investigations`) contain all structured report fields required for an Analyst's submission package. **No new report table or Investigation schema redesign is required.**

| Report Requirement | Existing `Investigation` Field | Type / Constraints |
|--------------------|--------------------------------|-------------------|
| Executive Summary | `description` | `TEXT` |
| Detailed Findings | `findings_text` | `TEXT` |
| Analyst Conclusion | `conclusion` | `TEXT` |
| Evidence References | `findings_refs` | `JSONB` array |
| Originating Alert | `alert_id` | `UUID REFERENCES alerts` |
| Scope / Branch | `scope_id` | `VARCHAR(100)` |
| Submission Timestamp | `submitted_at` | `TIMESTAMPTZ` |
| Analyst Identity | `assigned_to` / `created_by` | `VARCHAR(100)` |

### 1.2 Identified Architectural & Persistence Gaps (Stop Trigger)
Per Section 26 of the Phase 3A.9D Specification, implementation is paused to report the following structural gaps:

1. **No Attachment Persistence Table**: The current database schema (migrations `0001` through `0011`) has no table for tracking uploaded files, MIME types, file sizes, or storage keys.
2. **No File Storage Subsystem**: There is no existing file upload, storage, streaming download, or sanitized filesystem manager anywhere in the application code.

---

## 2. Minimal Proposed Attachment Schema & Database Migration

To safely persist banking evidence without bloating application JSON payloads or audit logs, we propose Alembic migration `0012_add_investigation_attachments.py`.

### 2.1 Proposed DDL (`0012_add_investigation_attachments.py`)

```sql
CREATE TABLE IF NOT EXISTS investigation_attachments (
    attachment_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id    UUID        NOT NULL REFERENCES investigations(investigation_id) ON DELETE RESTRICT,
    original_filename   VARCHAR(255) NOT NULL,
    stored_filename     VARCHAR(255) NOT NULL UNIQUE,
    content_type        VARCHAR(100) NOT NULL,
    size_bytes          BIGINT      NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 10485760),
    sha256_hash         VARCHAR(64) NOT NULL,
    description         TEXT,
    uploaded_by         VARCHAR(100) NOT NULL REFERENCES users(user_id),
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attachments_investigation 
    ON investigation_attachments(investigation_id);
CREATE INDEX IF NOT EXISTS idx_attachments_uploaded_by 
    ON investigation_attachments(uploaded_by);
```

### 2.2 Pydantic Entity Model (`services/workbench/models.py`)

```python
class InvestigationAttachment(BaseModel):
    attachment_id: str
    investigation_id: str
    original_filename: str
    stored_filename: str
    content_type: str
    size_bytes: int
    sha256_hash: str
    description: Optional[str] = None
    uploaded_by: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## 3. Secure File Storage & Streaming Architecture

### 3.1 Physical Storage Layout
- Files are stored in a private directory outside the web server root: `var/evidence_store/{scope_id}/{investigation_id}/{stored_filename}.bin`.
- Direct web access is prohibited (no public static URL routes).
- Storage filenames use randomly generated server-controlled UUIDs (`{attachment_id}.bin`) to eliminate path traversal, overwrites, or untrusted filename execution.

### 3.2 Security Controls & File Validation
- **Allowed Extensions & MIME Whitelist**:
  - `PDF`: `application/pdf` (`.pdf`)
  - `PNG`: `image/png` (`.png`)
  - `JPEG`: `image/jpeg` (`.jpg`, `.jpeg`)
  - `CSV`: `text/csv`, `text/plain` (`.csv`)
  - `XLSX`: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (`.xlsx`)
  - `TXT`: `text/plain` (`.txt`)
- **Prohibited Executables**: Strictly reject `.exe`, `.sh`, `.bat`, `.js`, `.py`, `.bin`, `.dll`, `.cmd`, `.msi`, etc.
- **Maximum File Size**: 10 MB per file (enforced at FastAPI request stream & DB check constraint).
- **Integrity**: SHA-256 hash calculated during upload stream and stored in DB.
- **Content-Disposition**: Downloads stream with `Content-Disposition: attachment; filename="<sanitized_original>"`.

### 3.3 Authorization Matrix (`shared.authorise`)

| Action | Allowed Roles | Investigation Lifecycle State | Permission Code |
|--------|---------------|-------------------------------|-----------------|
| Upload Evidence | Analyst (Assignee) | `open`, `active`, `returned` | `investigation:update` / `investigation:modify_findings` |
| List Attachments | Analyst (Assignee), Compliance | `open`, `active`, `submitted`, `returned`, `completed`, `awaiting_information` | `investigation:read_own` / `investigation:read` / `investigation:review` |
| Download Attachment | Analyst (Assignee), Compliance | `open`, `active`, `submitted`, `returned`, `completed`, `awaiting_information` | `investigation:read_own` / `investigation:read` / `investigation:review` |
| Delete Attachment | Analyst (Assignee) | `open`, `active`, `returned` (before submission) | `investigation:modify_findings` |

*Note: All attachment authorization checks pass through parent `Investigation` access validation. Knowledge of an `attachment_id` alone confers no access.*

---

## 4. API Specification

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/investigations/{id}/attachments` | Upload multipart file + description metadata |
| `GET` | `/api/v1/investigations/{id}/attachments` | List all evidence attachments for an investigation |
| `GET` | `/api/v1/investigations/{id}/attachments/{att_id}/download` | Stream attachment binary file safely |
| `DELETE` | `/api/v1/investigations/{id}/attachments/{att_id}` | Remove attachment metadata & physical storage file |

---

## 5. Audit Logging Policy

Audit events emit through the existing `UnitOfWork` outbox and activity timeline:
- **`investigation.attachment_uploaded`**: `{attachment_id, original_filename, size_bytes, content_type, sha256_hash}`
- **`investigation.attachment_deleted`**: `{attachment_id, original_filename}`
- **`investigation.attachment_downloaded`**: `{attachment_id, downloaded_by}`

*Raw file contents are strictly excluded from logs.*

---

## 6. Proposed Implementation Plan & Affected Files

### Backend
1. `migrations/versions/0012_add_investigation_attachments.py` — Schema migration.
2. `services/workbench/models.py` — Add `InvestigationAttachment`.
3. `services/workbench/repos.py` — Add `AttachmentRepo`.
4. `services/workbench/schemas/attachments.py` — Upload/List response models.
5. `services/workbench/services/attachment_service.py` — File validation, storage cleanup, atomic UoW.
6. `services/workbench/routers/investigations.py` — Upload/List/Download/Delete routes.
7. `services/shared/authorise.py` — Register attachment permission rules.
8. `services/workbench/tests/test_investigation_attachments.py` — 25 backend unit & integration tests.

### Frontend
1. `frontend/src/api/attachmentsApi.ts` — API client helper for multipart upload & blob download.
2. `frontend/src/components/investigations/EvidenceUploadPanel.tsx` — Upload UI with size/type validation & list viewer.
3. `frontend/src/components/investigations/InvestigationDetailPage.tsx` — Integrate report section & evidence panel.
4. `frontend/src/components/investigations/__tests__/InvestigationDetailPage.test.tsx` — Vitest tests for upload/download UI.

---

## 7. Recommendation

**Verdict: GO**  
The proposed migration (`0012_add_investigation_attachments.py`) and filesystem abstraction leverage all existing infrastructure (UnitOfWork, Audit Outbox, Timeline, Keycloak permissions) with zero breaking changes to existing alerts, cases, or compliance review workflows.

Upon user approval of this design, implementation will begin immediately.
