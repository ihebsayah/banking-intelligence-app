"""Test harness for the expiry worker."""
import pytest
import uuid
from datetime import datetime, timedelta, timezone

from workbench.expiry_worker import expire_due
from workbench.repos import ApprovalRepo
from workbench.models import ApprovalRequest


@pytest.mark.asyncio
async def _seed_user(integration_db):
    await integration_db.execute(
        "INSERT INTO users (user_id, email, name, role, bank_id, password_hash, status) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7) "
        "ON CONFLICT (user_id) DO NOTHING",
        ["expiry-harness-user", "expiry-h@test.com", "Expiry Harness", "analyst",
         "hq_main", "dummy-hash", "active"],
    )


def _make_request(expires_at):
    return ApprovalRequest(
        approval_request_id=str(uuid.uuid4()),
        action_type="alert_dismissal_critical_high",
        entity_type="alert",
        entity_id=str(uuid.uuid4()),
        requested_by="expiry-harness-user",
        rationale="Test rationale",
        required_approvals=1,
        status="pending",
        expires_at=expires_at,
    )


@pytest.mark.asyncio
async def test_expiry_worker_expires_overdue_approvals(integration_db):
    """Test that the expiry worker expires overdue approvals."""
    await _seed_user(integration_db)
    repo = ApprovalRepo(integration_db)

    ar = _make_request(datetime.now(timezone.utc) - timedelta(minutes=10))
    await repo.create(ar)

    expired = await expire_due(integration_db, batch_size=10)
    assert any(a.approval_request_id == ar.approval_request_id for a in expired)

    approval = await repo.fetch_by_id(ar.approval_request_id)
    assert approval is not None
    assert approval.status == "expired"


@pytest.mark.asyncio
async def test_expiry_worker_skips_future_approvals(integration_db):
    """Test that the expiry worker skips future approvals."""
    await _seed_user(integration_db)
    repo = ApprovalRepo(integration_db)

    ar = _make_request(datetime.now(timezone.utc) + timedelta(minutes=10))
    await repo.create(ar)

    expired = await expire_due(integration_db, batch_size=10)
    assert not any(a.approval_request_id == ar.approval_request_id for a in expired)

    approval = await repo.fetch_by_id(ar.approval_request_id)
    assert approval is not None
    assert approval.status == "pending"
