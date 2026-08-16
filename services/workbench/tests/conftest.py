"""Test fixtures for workbench repository and integration tests."""
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from shared.database import DatabaseConnector


@pytest.fixture(scope="session", autouse=True)
def run_migrations():
    """Run Alembic migrations before test session."""
    alembic_cfg = Config("alembic.ini")
    db_url = os.getenv("INTEGRATION_DATABASE_URL")
    if not db_url:
        pytest.skip("INTEGRATION_DATABASE_URL not set")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture
def mock_db():
    db = MagicMock(spec=DatabaseConnector)
    db.initialize = AsyncMock()
    db.close = AsyncMock()
    db._pool = MagicMock()
    db._ensure_pool = MagicMock()
    return db


@pytest.fixture
def new_id():
    return str(uuid.uuid4())


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def integration_db():
    """Fixture for the integration database connection."""
    db_url = os.getenv("INTEGRATION_DATABASE_URL")
    if not db_url:
        pytest.skip("INTEGRATION_DATABASE_URL not set")
    
    connector = DatabaseConnector(db_url)
    await connector.initialize()
    yield connector
    await connector.close()


@pytest.fixture(scope="session", autouse=True)
def audit_mock_server():
    """Start the audit mock server for the test session."""
    from workbench.tests.test_audit_mock import start_audit_mock, reset_audit_mock
    server, thread = start_audit_mock(port=18008)
    reset_audit_mock()
    yield
    if server:
        server.shutdown()


@pytest.fixture
def mock_audit_agent():
    """Mock fixture for the Audit Agent."""
    from workbench.tests.test_audit_mock import reset_audit_mock, get_received_events
    reset_audit_mock()
    return get_received_events


# --- Auth Fixtures ---
@pytest.fixture
def test_token():
    """Fixture for generating a test token."""
    return "test-token"


@pytest.fixture
def auth_headers(test_token):
    """Fixture for injecting authentication headers."""
    return {"Authorization": f"Bearer {test_token}"}


# --- Workflow Object Fixtures ---
@pytest.fixture
def test_alert():
    """Fixture for a test alert."""
    return {
        "alert_id": str(uuid.uuid4()),
        "status": "open",
        "severity": "high",
        "title": "Test Alert",
        "description": "Test Description",
    }


@pytest.fixture
def test_investigation():
    """Fixture for a test investigation."""
    return {
        "investigation_id": str(uuid.uuid4()),
        "status": "open",
        "title": "Test Investigation",
        "findings": "Test Findings",
    }


@pytest.fixture
def test_case():
    """Fixture for a test case."""
    return {
        "case_id": str(uuid.uuid4()),
        "status": "open",
        "title": "Test Case",
        "risk_level": "high",
    }


# --- Seed Fixtures ---
@pytest_asyncio.fixture
async def seed_users(integration_db):
    """Fixture to seed test users."""
    async with integration_db._pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, email, name, role, bank_id, password_hash, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) "
            "ON CONFLICT (user_id) DO NOTHING",
            "test-analyst", "analyst@test.com", "Test Analyst", "analyst", "hq_main", "dummy-hash", "active",
        )
        await conn.execute(
            "INSERT INTO users (user_id, email, name, role, bank_id, password_hash, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) "
            "ON CONFLICT (user_id) DO NOTHING",
            "test-compliance", "compliance@test.com", "Test Compliance", "compliance", "hq_main", "dummy-hash", "active",
        )


@pytest_asyncio.fixture(autouse=True)
async def isolate_test_data():
    """Autouse fixture that snapshots operational database IDs before each test
    and deterministically deletes only newly created test rows on teardown.
    """
    db_url = os.getenv("INTEGRATION_DATABASE_URL")
    if not db_url:
        yield
        return

    import asyncpg
    try:
        conn = await asyncpg.connect(db_url)
    except Exception:
        yield
        return

    try:
        pre_alerts = set(str(r["alert_id"]) for r in await conn.fetch("SELECT alert_id FROM alerts"))
        pre_invs = set(str(r["investigation_id"]) for r in await conn.fetch("SELECT investigation_id FROM investigations"))
        pre_cases = set(str(r["case_id"]) for r in await conn.fetch("SELECT case_id FROM compliance_cases"))
        pre_irs = set(str(r["ir_id"]) for r in await conn.fetch("SELECT ir_id FROM information_requests"))
        pre_comments = set(str(r["comment_id"]) for r in await conn.fetch("SELECT comment_id FROM comments"))
        pre_approvals = set(str(r["approval_request_id"]) for r in await conn.fetch("SELECT approval_request_id FROM approval_requests"))
        pre_decisions = set(str(r["decision_id"]) for r in await conn.fetch("SELECT decision_id FROM decisions"))

        yield

        post_alerts = list(set(str(r["alert_id"]) for r in await conn.fetch("SELECT alert_id FROM alerts")) - pre_alerts)
        post_invs = list(set(str(r["investigation_id"]) for r in await conn.fetch("SELECT investigation_id FROM investigations")) - pre_invs)
        post_cases = list(set(str(r["case_id"]) for r in await conn.fetch("SELECT case_id FROM compliance_cases")) - pre_cases)
        post_irs = list(set(str(r["ir_id"]) for r in await conn.fetch("SELECT ir_id FROM information_requests")) - pre_irs)
        post_comments = list(set(str(r["comment_id"]) for r in await conn.fetch("SELECT comment_id FROM comments")) - pre_comments)
        post_approvals = list(set(str(r["approval_request_id"]) for r in await conn.fetch("SELECT approval_request_id FROM approval_requests")) - pre_approvals)
        post_decisions = list(set(str(r["decision_id"]) for r in await conn.fetch("SELECT decision_id FROM decisions")) - pre_decisions)

        new_entity_ids = list(set(post_alerts + post_invs + post_cases + post_irs + post_comments + post_approvals))

        if post_decisions:
            await conn.execute("DELETE FROM decisions WHERE decision_id::text = ANY($1::text[])", post_decisions)
        if post_approvals:
            await conn.execute("DELETE FROM approval_decisions WHERE approval_request_id::text = ANY($1::text[])", post_approvals)
        if new_entity_ids:
            await conn.execute("DELETE FROM activity_timeline WHERE entity_id::text = ANY($1::text[])", new_entity_ids)
            await conn.execute("DELETE FROM assignment_history WHERE entity_id::text = ANY($1::text[])", new_entity_ids)
            await conn.execute("DELETE FROM notifications WHERE entity_id::text = ANY($1::text[])", new_entity_ids)
            await conn.execute("DELETE FROM audit_outbox WHERE entity_id::text = ANY($1::text[])", new_entity_ids)
        if post_irs:
            await conn.execute("DELETE FROM information_requests WHERE ir_id::text = ANY($1::text[])", post_irs)
        if post_comments:
            await conn.execute("DELETE FROM comments WHERE comment_id::text = ANY($1::text[])", post_comments)
        if post_cases:
            await conn.execute("UPDATE compliance_cases SET closure_approval_id = NULL WHERE case_id::text = ANY($1::text[])", post_cases)
        if post_approvals:
            await conn.execute("DELETE FROM approval_requests WHERE approval_request_id::text = ANY($1::text[])", post_approvals)
        if post_cases:
            await conn.execute("DELETE FROM compliance_cases WHERE case_id::text = ANY($1::text[])", post_cases)
        if post_invs:
            await conn.execute("DELETE FROM investigations WHERE investigation_id::text = ANY($1::text[])", post_invs)
        if post_alerts:
            await conn.execute("DELETE FROM alerts WHERE alert_id::text = ANY($1::text[])", post_alerts)
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def seed_workflow_objects(integration_db):
    """Fixture to seed workflow objects (alerts, investigations, cases)."""
    aid = str(uuid.uuid4())
    iid = str(uuid.uuid4())
    cid = str(uuid.uuid4())
    async with integration_db._pool.acquire() as conn:
        # Seed an alert
        await conn.execute(
            "INSERT INTO alerts (alert_id, alert_type, severity, title, description, scope_id, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            aid, "suspicious_activity", "high", "Test Alert", "Test Description", "hq_main", "open",
        )
        # Seed an investigation
        await conn.execute(
            "INSERT INTO investigations (investigation_id, alert_id, title, status, assigned_to) "
            "VALUES ($1, $2, $3, $4, $5)",
            iid, aid, "Test Investigation", "open", "test-analyst",
        )
        # Seed a case
        await conn.execute(
            "INSERT INTO compliance_cases (case_id, title, status, risk_level, assigned_to) "
            "VALUES ($1, $2, $3, $4, $5)",
            cid, "Test Case", "open", "high", "test-compliance",
        )
    yield {"alert_id": aid, "investigation_id": iid, "case_id": cid}
    async with integration_db._pool.acquire() as conn:
        await conn.execute("DELETE FROM compliance_cases WHERE case_id = $1", cid)
        await conn.execute("DELETE FROM investigations WHERE investigation_id = $1", iid)
        await conn.execute("DELETE FROM alerts WHERE alert_id = $1", aid)