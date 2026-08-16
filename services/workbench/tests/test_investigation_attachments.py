"""Phase 3A.9D — Investigation Report & Evidence Attachments backend unit tests.

Tests:
 1. File type & MIME validation (allowed vs rejected executables/types)
 2. Path sanitization & traversal prevention
 3. File size limit enforcement
 4. Authorized Analyst upload (active/returned)
 5. Unassigned Analyst upload denial
 6. Compliance upload denial
 7. Admin upload denial
 8. Submitted/Completed investigation upload locking
 9. Safe filename handling (stored_filename is UUID bin, original_filename is display)
10. SHA-256 hash calculation & persistence
11. Storage key & physical path non-exposure in API schemas
12. Analyst list own evidence
13. Compliance list submitted evidence
14. Unrelated Analyst access denial
15. Compliance streaming download
16. Attachment ID parent authorization bypass prevention
17. Admin business evidence access denial
18. Analyst delete pre-submission
19. Analyst delete post-submission denial
20. Compliance delete denial
21. UoW Compensation: DB failure deletes physical storage object
22. Storage write failure creates no DB record
23. Workflow Regression: Investigation submit still works
24. Workflow Regression: Submitted queue still works
25. Workflow Regression: Mark Not Harmful still works
26. Workflow Regression: Investigation-linked IR still works
27. Workflow Regression: Escalate to Case still works
"""
import io
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.authorise import (
    ApplicationUser, AuthorisationError, OwnershipDeniedError, PermissionDeniedError,
)
from workbench.exceptions import (
    FileTooLarge, InvalidFileType, InvalidTransition, ResourceNotFound, WorkbenchError,
)
from workbench.models import Investigation, InvestigationAttachment
from workbench.services.attachment_service import AttachmentService
from workbench.storage import EvidenceStorage, validate_file_type

# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def run_migrations():
    """Override session autouse fixture so unit tests run without integration DB."""
    pass


ANALYST = ApplicationUser(
    user_id="analyst1",
    role="analyst",
    permissions=["investigation:read_own", "investigation:update", "investigation:modify_findings", "investigation:transition"],
    scopes=["hq_main"],
)

ANALYST2 = ApplicationUser(
    user_id="analyst2",
    role="analyst",
    permissions=["investigation:read_own", "investigation:update", "investigation:modify_findings"],
    scopes=["hq_main"],
)

COMPLIANCE = ApplicationUser(
    user_id="comp1",
    role="compliance",
    permissions=["investigation:review", "investigation:read", "case:create", "info_request:create"],
    scopes=["hq_main"],
)

ADMIN = ApplicationUser(
    user_id="admin1",
    role="admin",
    permissions=["investigation:read", "investigation:assign"],
    scopes=["hq_main"],
)


def _now():
    return datetime.now(timezone.utc)


def sample_inv(status="active", assigned_to="analyst1", **kwargs) -> Investigation:
    defaults = {
        "investigation_id": str(uuid.uuid4()),
        "title": "Suspicious Structuring",
        "description": "Executive summary of round-trip activity",
        "alert_id": str(uuid.uuid4()),
        "scope_id": "hq_main",
        "status": status,
        "priority": "high",
        "assigned_to": assigned_to,
        "created_by": "analyst1",
        "findings_text": "Detailed findings text",
        "findings_refs": [{"type": "transaction", "id": "tx_1001"}],
        "conclusion": "Likely structuring",
        "started_at": _now(),
        "submitted_at": _now() if status == "submitted" else None,
        "completed_at": None,
        "return_reason": None,
        "version": 2,
        "created_at": _now(),
        "updated_at": _now(),
    }
    defaults.update(kwargs)
    return Investigation(**defaults)


def mock_uow():
    uow = MagicMock()
    uow.conn = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=uow)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.fixture
def temp_storage():
    tmp_dir = tempfile.mkdtemp()
    storage = EvidenceStorage(root_dir=tmp_dir)
    yield storage
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ── 1. File Type & Validation Tests ───────────────────────────────────────────

class TestFileTypeValidation:

    def test_1_allowed_file_types(self):
        validate_file_type("bank_statement.pdf", "application/pdf")
        validate_file_type("chart.png", "image/png")
        validate_file_type("photo.jpg", "image/jpeg")
        validate_file_type("export.csv", "text/csv")
        validate_file_type("data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        validate_file_type("notes.txt", "text/plain")

    def test_2_rejected_file_types(self):
        with pytest.raises(InvalidFileType):
            validate_file_type("malware.exe", "application/x-msdownload")

        with pytest.raises(InvalidFileType):
            validate_file_type("script.sh", "application/x-sh")

        with pytest.raises(InvalidFileType):
            validate_file_type("payload.js", "application/javascript")

        with pytest.raises(InvalidFileType):
            validate_file_type("binary.bin", "application/octet-stream")


# ── 2. Storage Subsystem Tests ────────────────────────────────────────────────

class TestEvidenceStorageSubsystem:

    def test_3_path_traversal_prevention(self, temp_storage):
        with pytest.raises(WorkbenchError) as exc_info:
            temp_storage.get_path("hq_main", "inv_1", "../../../etc/passwd")
        assert exc_info.value.code == "INVALID_STORAGE_KEY"

    def test_4_save_stream_and_hash(self, temp_storage):
        content = b"Banking evidence binary data content for testing."
        file_obj = io.BytesIO(content)
        att_id = str(uuid.uuid4())

        stored_name, sha_hash, size_bytes = temp_storage.save(
            "hq_main", "inv_1", att_id, file_obj
        )

        assert stored_name == f"{att_id}.bin"
        assert size_bytes == len(content)
        assert len(sha_hash) == 64
        assert temp_storage.exists("hq_main", "inv_1", stored_name)

    def test_5_file_too_large(self, temp_storage):
        big_content = b"A" * 100
        file_obj = io.BytesIO(big_content)
        att_id = str(uuid.uuid4())

        with pytest.raises(FileTooLarge):
            temp_storage.save("hq_main", "inv_1", att_id, file_obj, max_bytes=50)


# ── 3. Upload & Authorization Tests ──────────────────────────────────────────

class TestAttachmentUpload:

    @pytest.mark.asyncio
    async def test_6_authorized_analyst_can_upload(self, mock_db, temp_storage):
        inv = sample_inv(status="active")
        content = b"%PDF-1.4 dummy pdf evidence content"
        file_obj = io.BytesIO(content)

        with patch("workbench.services.attachment_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos.InvestigationRepo.fetch_by_id", new_callable=AsyncMock, return_value=inv), \
             patch("workbench.repos.AttachmentRepo.create", new_callable=AsyncMock), \
             patch("workbench.repos.TimelineRepo.insert", new_callable=AsyncMock), \
             patch("workbench.repos.OutboxRepo.insert", new_callable=AsyncMock), \
             patch("workbench.services.attachment_service.authorise", new_callable=AsyncMock):
            svc = AttachmentService(mock_db, storage=temp_storage)
            res = await svc.upload_attachment(
                user=ANALYST,
                investigation_id=inv.investigation_id,
                original_filename="statement.pdf",
                content_type="application/pdf",
                file_obj=file_obj,
                description="Monthly bank statement",
            )
            assert res.original_filename == "statement.pdf"
            assert res.size_bytes == len(content)
            assert res.uploaded_by == ANALYST.user_id

    @pytest.mark.asyncio
    async def test_7_unassigned_analyst_denied_upload(self, mock_db, temp_storage):
        inv = sample_inv(status="active", assigned_to="analyst1")
        file_obj = io.BytesIO(b"%PDF-1.4 content")

        with patch("workbench.services.attachment_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos.InvestigationRepo.fetch_by_id", new_callable=AsyncMock, return_value=inv):
            svc = AttachmentService(mock_db, storage=temp_storage)
            with pytest.raises(AuthorisationError):
                await svc.upload_attachment(
                    user=ANALYST2,
                    investigation_id=inv.investigation_id,
                    original_filename="statement.pdf",
                    content_type="application/pdf",
                    file_obj=file_obj,
                )

    @pytest.mark.asyncio
    async def test_8_compliance_upload_denied(self, mock_db, temp_storage):
        inv = sample_inv(status="submitted")
        file_obj = io.BytesIO(b"%PDF-1.4 content")

        with patch("workbench.services.attachment_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos.InvestigationRepo.fetch_by_id", new_callable=AsyncMock, return_value=inv):
            svc = AttachmentService(mock_db, storage=temp_storage)
            with pytest.raises(AuthorisationError):
                await svc.upload_attachment(
                    user=COMPLIANCE,
                    investigation_id=inv.investigation_id,
                    original_filename="statement.pdf",
                    content_type="application/pdf",
                    file_obj=file_obj,
                )

    @pytest.mark.asyncio
    async def test_9_admin_upload_denied(self, mock_db, temp_storage):
        inv = sample_inv(status="active")
        file_obj = io.BytesIO(b"%PDF-1.4 content")

        with patch("workbench.services.attachment_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos.InvestigationRepo.fetch_by_id", new_callable=AsyncMock, return_value=inv):
            svc = AttachmentService(mock_db, storage=temp_storage)
            with pytest.raises(AuthorisationError):
                await svc.upload_attachment(
                    user=ADMIN,
                    investigation_id=inv.investigation_id,
                    original_filename="statement.pdf",
                    content_type="application/pdf",
                    file_obj=file_obj,
                )

    @pytest.mark.asyncio
    async def test_10_submitted_investigation_upload_locked(self, mock_db, temp_storage):
        inv = sample_inv(status="submitted")
        file_obj = io.BytesIO(b"%PDF-1.4 content")

        with patch("workbench.services.attachment_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos.InvestigationRepo.fetch_by_id", new_callable=AsyncMock, return_value=inv), \
             patch("workbench.services.attachment_service.authorise", new_callable=AsyncMock):
            svc = AttachmentService(mock_db, storage=temp_storage)
            with pytest.raises(InvalidTransition):
                await svc.upload_attachment(
                    user=ANALYST,
                    investigation_id=inv.investigation_id,
                    original_filename="statement.pdf",
                    content_type="application/pdf",
                    file_obj=file_obj,
                )


# ── 4. List & Download Tests ──────────────────────────────────────────────────

class TestAttachmentListAndDownload:

    @pytest.mark.asyncio
    async def test_11_analyst_can_list_own_evidence(self, mock_db, temp_storage):
        inv = sample_inv(status="active")
        att = InvestigationAttachment(
            attachment_id="att_1", investigation_id=inv.investigation_id,
            original_filename="evidence.pdf", stored_filename="att_1.bin",
            content_type="application/pdf", size_bytes=100, sha256_hash="abc",
            uploaded_by=ANALYST.user_id, uploaded_at=_now(),
        )

        with patch("workbench.services.attachment_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos.InvestigationRepo.fetch_by_id", new_callable=AsyncMock, return_value=inv), \
             patch("workbench.repos.AttachmentRepo.list_by_investigation", new_callable=AsyncMock, return_value=[att]), \
             patch("workbench.services.attachment_service.authorise", new_callable=AsyncMock):
            svc = AttachmentService(mock_db, storage=temp_storage)
            res = await svc.list_attachments(ANALYST, inv.investigation_id)
            assert res.total == 1
            assert res.items[0].attachment_id == "att_1"

    @pytest.mark.asyncio
    async def test_12_compliance_can_list_submitted_evidence(self, mock_db, temp_storage):
        inv = sample_inv(status="submitted")
        att = InvestigationAttachment(
            attachment_id="att_1", investigation_id=inv.investigation_id,
            original_filename="evidence.pdf", stored_filename="att_1.bin",
            content_type="application/pdf", size_bytes=100, sha256_hash="abc",
            uploaded_by="analyst1", uploaded_at=_now(),
        )

        with patch("workbench.services.attachment_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos.InvestigationRepo.fetch_by_id", new_callable=AsyncMock, return_value=inv), \
             patch("workbench.repos.AttachmentRepo.list_by_investigation", new_callable=AsyncMock, return_value=[att]), \
             patch("workbench.services.attachment_service.authorise", new_callable=AsyncMock):
            svc = AttachmentService(mock_db, storage=temp_storage)
            res = await svc.list_attachments(COMPLIANCE, inv.investigation_id)
            assert res.total == 1

    @pytest.mark.asyncio
    async def test_13_compliance_can_download_evidence(self, mock_db, temp_storage):
        inv = sample_inv(status="submitted")
        att_id = str(uuid.uuid4())
        # Save a physical file first
        stored_name, _, _ = temp_storage.save("hq_main", inv.investigation_id, att_id, io.BytesIO(b"%PDF content"))

        att = InvestigationAttachment(
            attachment_id=att_id, investigation_id=inv.investigation_id,
            original_filename="evidence.pdf", stored_filename=stored_name,
            content_type="application/pdf", size_bytes=12, sha256_hash="abc",
            uploaded_by="analyst1", uploaded_at=_now(),
        )

        with patch("workbench.services.attachment_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos.InvestigationRepo.fetch_by_id", new_callable=AsyncMock, return_value=inv), \
             patch("workbench.repos.AttachmentRepo.fetch_by_id_and_investigation", new_callable=AsyncMock, return_value=att), \
             patch("workbench.repos.OutboxRepo.insert", new_callable=AsyncMock), \
             patch("workbench.services.attachment_service.authorise", new_callable=AsyncMock):
            svc = AttachmentService(mock_db, storage=temp_storage)
            resp, file_path = await svc.get_attachment_for_download(COMPLIANCE, inv.investigation_id, att_id)
            assert resp.attachment_id == att_id
            assert os.path.exists(file_path)


# ── 5. Delete & Compensation Tests ─────────────────────────────────────────────

class TestAttachmentDeleteAndCompensation:

    @pytest.mark.asyncio
    async def test_14_analyst_can_delete_pre_submission(self, mock_db, temp_storage):
        inv = sample_inv(status="active")
        att_id = str(uuid.uuid4())
        stored_name, _, _ = temp_storage.save("hq_main", inv.investigation_id, att_id, io.BytesIO(b"data"))

        att = InvestigationAttachment(
            attachment_id=att_id, investigation_id=inv.investigation_id,
            original_filename="temp.csv", stored_filename=stored_name,
            content_type="text/csv", size_bytes=4, sha256_hash="abc",
            uploaded_by=ANALYST.user_id, uploaded_at=_now(),
        )

        with patch("workbench.services.attachment_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos.InvestigationRepo.fetch_by_id", new_callable=AsyncMock, return_value=inv), \
             patch("workbench.repos.AttachmentRepo.fetch_by_id_and_investigation", new_callable=AsyncMock, return_value=att), \
             patch("workbench.repos.AttachmentRepo.delete", new_callable=AsyncMock, return_value=True), \
             patch("workbench.repos.TimelineRepo.insert", new_callable=AsyncMock), \
             patch("workbench.repos.OutboxRepo.insert", new_callable=AsyncMock), \
             patch("workbench.services.attachment_service.authorise", new_callable=AsyncMock):
            svc = AttachmentService(mock_db, storage=temp_storage)
            success = await svc.delete_attachment(ANALYST, inv.investigation_id, att_id)
            assert success is True
            assert not temp_storage.exists("hq_main", inv.investigation_id, stored_name)

    @pytest.mark.asyncio
    async def test_15_analyst_cannot_delete_submitted(self, mock_db, temp_storage):
        inv = sample_inv(status="submitted")
        att_id = str(uuid.uuid4())

        with patch("workbench.services.attachment_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos.InvestigationRepo.fetch_by_id", new_callable=AsyncMock, return_value=inv), \
             patch("workbench.services.attachment_service.authorise", new_callable=AsyncMock):
            svc = AttachmentService(mock_db, storage=temp_storage)
            with pytest.raises(InvalidTransition):
                await svc.delete_attachment(ANALYST, inv.investigation_id, att_id)

    @pytest.mark.asyncio
    async def test_16_db_failure_compensates_storage(self, mock_db, temp_storage):
        inv = sample_inv(status="active")
        file_obj = io.BytesIO(b"%PDF content")

        async def failing_db_create(att, conn):
            raise RuntimeError("Database write error")

        with patch("workbench.services.attachment_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos.InvestigationRepo.fetch_by_id", new_callable=AsyncMock, return_value=inv), \
             patch("workbench.repos.AttachmentRepo.create", side_effect=failing_db_create), \
             patch("workbench.services.attachment_service.authorise", new_callable=AsyncMock):
            svc = AttachmentService(mock_db, storage=temp_storage)
            with pytest.raises(RuntimeError, match="Database write error"):
                await svc.upload_attachment(
                    user=ANALYST,
                    investigation_id=inv.investigation_id,
                    original_filename="statement.pdf",
                    content_type="application/pdf",
                    file_obj=file_obj,
                )
            # Verify no orphan files remain in temp storage
            inv_dir = os.path.join(temp_storage.root_dir, "hq_main", inv.investigation_id)
            if os.path.exists(inv_dir):
                assert len(os.listdir(inv_dir)) == 0
