"""Test PostgreSQL reachability without conftest."""
import os
import psycopg2
import pytest


def test_postgresql_reachable():
    """Test that PostgreSQL is reachable."""
    db_url = os.getenv("INTEGRATION_DATABASE_URL")
    if not db_url:
        pytest.skip("INTEGRATION_DATABASE_URL not set")
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
        cursor.close()
        conn.close()
    except Exception as e:
        pytest.fail(f"PostgreSQL connection failed: {e}")