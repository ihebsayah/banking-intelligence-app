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


@pytest_asyncio.fixture
async def seed_workflow_objects(integration_db):
    """Fixture to seed workflow objects (alerts, investigations, cases)."""
    async with integration_db._pool.acquire() as conn:
        # Seed an alert
        await conn.execute(
            "INSERT INTO alerts (alert_id, alert_type, severity, title, description, scope_id, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            str(uuid.uuid4()), "suspicious_activity", "high", "Test Alert", "Test Description", "hq_main", "open",
        )
        # Seed an investigation
        await conn.execute(
            "INSERT INTO investigations (investigation_id, alert_id, title, status, assigned_to) "
            "VALUES ($1, $2, $3, $4, $5)",
            str(uuid.uuid4()), str(uuid.uuid4()), "Test Investigation", "open", "test-analyst",
        )
        # Seed a case
        await conn.execute(
            "INSERT INTO compliance_cases (case_id, title, status, risk_level, assigned_to) "
            "VALUES ($1, $2, $3, $4, $5)",
            str(uuid.uuid4()), "Test Case", "open", "high", "test-compliance",
        )