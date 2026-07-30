"""Test fixtures for workbench repository and outbox tests."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.database import DatabaseConnector


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
