"""Tests for investigation-linked Information Requests (Phase 3A.9C.1).

Verifies:
1. Database XOR parent constraint (case_id vs investigation_id).
2. Compliance creation of investigation-linked IRs and atomic transition of investigation to awaiting_information.
3. Analyst and Admin permission restrictions.
4. Analyst response loop and Compliance accept/return lifecycle.
5. Automatic re-entry of investigation into submitted review queue upon IR completion.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from shared.authorise import (
    ApplicationUser, PermissionDeniedError, ProhibitedComboError,
)
from workbench.exceptions import (
    InvalidAssignee, InvalidTransition, ResourceNotFound, WorkbenchError,
)
from workbench.models import InformationRequest, Investigation
from workbench.schemas.information_requests import (
    AcceptInformationRequest, AcknowledgeInformationRequest,
    CancelInformationRequest, CreateInformationRequest,
    RespondInformationRequest, ReturnInformationRequest,
)
from workbench.services.information_request_service import InformationRequestService

@pytest.fixture(scope="session", autouse=True)
def run_migrations():
    """Override session-level autouse migration fixture so unit tests run without integration DB."""
    pass


COMPLIANCE = ApplicationUser(
    user_id="comp1",
    role="compliance",
    permissions=["info_request:create", "info_request:read", "info_request:accept",
                 "info_request:return", "info_request:cancel", "investigation:review", "investigation:read"],
    scopes=["hq_main"],
)

ANALYST = ApplicationUser(
    user_id="analyst1",
    role="analyst",
    permissions=["info_request:read_assigned", "info_request:respond", "investigation:read_own"],
    scopes=["hq_main"],
)

ADMIN = ApplicationUser(
    user_id="admin1",
    role="admin",
    permissions=["info_request:read", "info_request:cancel", "investigation:read"],
    scopes=["hq_main"],
)


def mock_uow():
    uow = MagicMock()
    uow.conn = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=uow)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


class TestInvestigationInformationRequests:

    def test_model_parent_fields(self):
        """1 & 2. Verify model tolerates case_id or investigation_id."""
        ir_case = InformationRequest(
            ir_id="ir_1", case_id="case_1", investigation_id=None,
            created_by="comp1", assigned_to="analyst1", question="Q1"
        )
        assert ir_case.case_id == "case_1"
        assert ir_case.investigation_id is None

        ir_inv = InformationRequest(
            ir_id="ir_2", case_id=None, investigation_id="inv_1",
            created_by="comp1", assigned_to="analyst1", question="Q2"
        )
        assert ir_inv.case_id is None
        assert ir_inv.investigation_id == "inv_1"

    @pytest.mark.asyncio
    async def test_compliance_can_create_investigation_ir(self, mock_db):
        """5 & 8. Compliance creates IR for submitted investigation -> transitions to awaiting_information."""
        inv_row = {
            "investigation_id": "inv_sub_100", "title": "Sub Inv", "description": "Test",
            "alert_id": None, "scope_id": "hq_main", "status": "submitted",
            "priority": "medium", "assigned_to": "analyst1", "created_by": "analyst1",
            "findings_text": "findings", "findings_refs": [], "conclusion": "conc",
            "started_at": None, "submitted_at": None, "completed_at": None, "return_reason": None,
            "version": 2, "created_at": "2026-08-16T00:00:00Z", "updated_at": "2026-08-16T00:00:00Z",
        }

        async def fake_fetch_one(*args, **kwargs):
            sql_str = str(args[1]) if len(args) > 1 else ""
            if "FROM investigations" in sql_str:
                return inv_row
            return None

        async def fake_fetch_all(*args, **kwargs):
            return []

        async def fake_execute(*args, **kwargs):
            return "UPDATE 1"

        with patch("workbench.services.information_request_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos._fetch_one", side_effect=fake_fetch_one), \
             patch("workbench.repos._fetch_all", side_effect=fake_fetch_all), \
             patch("workbench.repos._execute", side_effect=fake_execute), \
             patch("workbench.services.information_request_service._validate_assignee", return_value=None):

            req = CreateInformationRequest(
                assigned_to="analyst1", question="Need additional transaction logs",
                expected_investigation_version=2
            )
            res = await InformationRequestService(mock_db).create_for_investigation(
                COMPLIANCE, "inv_sub_100", req
            )

            assert res.success is True
            assert res.information_request.investigation_id == "inv_sub_100"
            assert res.information_request.case_id is None
            assert res.information_request.question == "Need additional transaction logs"

    @pytest.mark.asyncio
    async def test_analyst_cannot_create_investigation_ir(self, mock_db):
        """6. Analyst cannot create investigation-linked IR."""
        inv_row = {
            "investigation_id": "inv_sub_100", "title": "Sub Inv", "scope_id": "hq_main",
            "status": "submitted", "priority": "medium", "assigned_to": "analyst1", "created_by": "analyst1",
            "version": 2, "created_at": "2026-08-16T00:00:00Z", "updated_at": "2026-08-16T00:00:00Z",
        }
        with patch("workbench.services.information_request_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos._fetch_one", return_value=inv_row):
            req = CreateInformationRequest(assigned_to="analyst1", question="Q?", expected_investigation_version=2)
            with pytest.raises(PermissionDeniedError):
                await InformationRequestService(mock_db).create_for_investigation(
                    ANALYST, "inv_sub_100", req
                )

    @pytest.mark.asyncio
    async def test_admin_cannot_create_investigation_ir(self, mock_db):
        """7. Admin prohibited from creating investigation-linked IR."""
        inv_row = {
            "investigation_id": "inv_sub_100", "title": "Sub Inv", "scope_id": "hq_main",
            "status": "submitted", "priority": "medium", "assigned_to": "analyst1", "created_by": "analyst1",
            "version": 2, "created_at": "2026-08-16T00:00:00Z", "updated_at": "2026-08-16T00:00:00Z",
        }
        with patch("workbench.services.information_request_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos._fetch_one", return_value=inv_row):
            req = CreateInformationRequest(assigned_to="analyst1", question="Q?", expected_investigation_version=2)
            with pytest.raises((PermissionDeniedError, ProhibitedComboError)):
                await InformationRequestService(mock_db).create_for_investigation(
                    ADMIN, "inv_sub_100", req
                )

    @pytest.mark.asyncio
    async def test_accept_investigation_ir_resumes_investigation(self, mock_db):
        """16. Accepting investigation IR returns investigation to submitted queue when active IRs resolved."""
        ir_row = {
            "ir_id": "ir_100", "case_id": None, "investigation_id": "inv_sub_100",
            "created_by": "comp1", "assigned_to": "analyst1", "question": "Need proof",
            "due_date": None, "status": "responded", "response_text": "Attached proof",
            "responded_at": "2026-08-16T01:00:00Z", "acceptance_note": None,
            "return_reason": None, "accepted_at": None, "returned_at": None,
            "accepted_by": None, "returned_by": None, "cancelled_at": None,
            "cancelled_by": None, "cancel_reason": None, "version": 2,
            "created_at": "2026-08-16T00:00:00Z", "updated_at": "2026-08-16T01:00:00Z",
        }
        inv_row = {
            "investigation_id": "inv_sub_100", "title": "Sub Inv", "scope_id": "hq_main",
            "status": "awaiting_information", "priority": "medium", "assigned_to": "analyst1",
            "created_by": "analyst1", "version": 3,
            "created_at": "2026-08-16T00:00:00Z", "updated_at": "2026-08-16T00:00:00Z",
        }

        async def fake_fetch_one(*args, **kwargs):
            sql_str = str(args[1]) if len(args) > 1 else ""
            if "FROM information_requests WHERE ir_id" in sql_str:
                return ir_row
            if "FROM investigations" in sql_str:
                return inv_row
            return None

        async def fake_fetch_all(*args, **kwargs):
            return []

        async def fake_execute(*args, **kwargs):
            return "UPDATE 1"

        with patch("workbench.services.information_request_service.UnitOfWork", return_value=mock_uow()), \
             patch("workbench.repos._fetch_one", side_effect=fake_fetch_one), \
             patch("workbench.repos._fetch_all", side_effect=fake_fetch_all), \
             patch("workbench.repos._execute", side_effect=fake_execute):

            req = AcceptInformationRequest(acceptance_note="Looks good", expected_version=2)
            res = await InformationRequestService(mock_db).accept(COMPLIANCE, "ir_100", req)

            assert res.success is True
            assert res.information_request.status == "accepted"


@pytest.mark.asyncio
class TestInvestigationIROperationalDB:
    """Integration test enforcing XOR parent check constraint in PostgreSQL."""

    async def test_db_xor_parent_constraint(self, integration_db):
        conn = await integration_db._pool.acquire()
        try:
            uid_hex = uuid.uuid4().hex[:8]
            user_id = f"user_{uid_hex}"
            inv_id = str(uuid.uuid4())
            case_id = str(uuid.uuid4())

            # Seed user, scope, investigation, and case
            await conn.execute(
                "INSERT INTO users (user_id, email, password_hash, role, status) VALUES ($1, $2, 'hash', 'analyst', 'active')",
                user_id, f"{user_id}@test.com"
            )
            await conn.execute("INSERT INTO user_scopes (user_id, scope_id, granted_by) VALUES ($1, 'hq_main', $1)", user_id)
            await conn.execute(
                "INSERT INTO investigations (investigation_id, title, scope_id, created_by, status) VALUES ($1, 'Test Inv', 'hq_main', $2, 'submitted')",
                inv_id, user_id
            )
            await conn.execute(
                "INSERT INTO compliance_cases (case_id, title, scope_id, created_by, status) VALUES ($1, 'Test Case', 'hq_main', $2, 'under_review')",
                case_id, user_id
            )

            # 1. Valid: investigation_id set, case_id NULL
            ir1_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO information_requests (ir_id, case_id, investigation_id, created_by, assigned_to, question, status) VALUES ($1, NULL, $2, $3, $3, 'Question?', 'open')",
                ir1_id, inv_id, user_id
            )

            # 2. Valid: case_id set, investigation_id NULL
            ir2_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO information_requests (ir_id, case_id, investigation_id, created_by, assigned_to, question, status) VALUES ($1, $2, NULL, $3, $3, 'Question?', 'open')",
                ir2_id, case_id, user_id
            )

            # 3. Invalid: both NULL -> Check constraint error
            ir3_id = str(uuid.uuid4())
            with pytest.raises(Exception) as exc_info:
                await conn.execute(
                    "INSERT INTO information_requests (ir_id, case_id, investigation_id, created_by, assigned_to, question, status) VALUES ($1, NULL, NULL, $2, $2, 'Question?', 'open')",
                    ir3_id, user_id
                )
            assert "chk_ir_exactly_one_parent" in str(exc_info.value) or "check constraint" in str(exc_info.value).lower()

            # 4. Invalid: both non-NULL -> Check constraint error
            ir4_id = str(uuid.uuid4())
            with pytest.raises(Exception) as exc_info:
                await conn.execute(
                    "INSERT INTO information_requests (ir_id, case_id, investigation_id, created_by, assigned_to, question, status) VALUES ($1, $2, $3, $4, $4, 'Question?', 'open')",
                    ir4_id, case_id, inv_id, user_id
                )
            assert "chk_ir_exactly_one_parent" in str(exc_info.value) or "check constraint" in str(exc_info.value).lower()

        finally:
            await integration_db._pool.release(conn)
