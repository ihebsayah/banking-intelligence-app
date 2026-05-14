"""
services/shared/database.py
Async PostgreSQL connection pool abstraction.
All services use DatabaseConnector to run queries safely.

CRITICAL RULE: ONLY parameterized queries. No f-strings in SQL. Ever.
"""
import asyncio
from typing import Any, List, Optional, Dict
import asyncpg

from shared.logger import get_logger
from shared.errors import (
    DatabaseError,
    ConnectionPoolError,
    QueryTimeoutError,
)

logger = get_logger(__name__, "database")

# Default pool configuration
DEFAULT_MIN_SIZE = 5
DEFAULT_MAX_SIZE = 20
DEFAULT_QUERY_TIMEOUT = 30.0   # seconds
DEFAULT_POOL_TIMEOUT = 10.0    # seconds to wait for a connection from pool


class DatabaseConnector:
    """
    Async PostgreSQL connector with connection pooling (asyncpg).

    Usage:
        db = DatabaseConnector(database_url)
        await db.initialize()
        rows = await db.fetch_all("SELECT * FROM customers WHERE segment = $1", ["premium"])
        await db.close()

    Parameterized query convention: use $1, $2, ... placeholders (asyncpg style).
    """

    def __init__(
        self,
        database_url: str,
        min_size: int = DEFAULT_MIN_SIZE,
        max_size: int = DEFAULT_MAX_SIZE,
        query_timeout: float = DEFAULT_QUERY_TIMEOUT,
    ):
        self.database_url = database_url
        self.min_size = min_size
        self.max_size = max_size
        self.query_timeout = query_timeout
        self._pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        """Create the connection pool. Call once at service startup."""
        if self._pool is not None:
            return  # Already initialized

        try:
            logger.info("Initializing database connection pool", extra={
                "min_size": self.min_size,
                "max_size": self.max_size,
            })
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_size,
                max_size=self.max_size,
                command_timeout=self.query_timeout,
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as exc:
            logger.error("Failed to create connection pool", extra={"error": str(exc)})
            raise ConnectionPoolError(f"Cannot connect to database: {exc}") from exc

    async def close(self) -> None:
        """Gracefully close all connections in the pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Database connection pool closed")

    def _ensure_pool(self) -> asyncpg.Pool:
        """Raise if the pool hasn't been initialized yet."""
        if self._pool is None:
            raise ConnectionPoolError("Database pool not initialized. Call initialize() first.")
        return self._pool

    # ─── Core Query Methods ──────────────────────────────────────────────────

    async def fetch_all(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return ALL rows as dicts.

        Args:
            sql:    Parameterized SQL (use $1, $2, ... placeholders).
            params: List of values to bind to placeholders.

        Returns:
            List of row dicts. Empty list if no rows found.
        """
        pool = self._ensure_pool()
        params = params or []

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
                return [dict(row) for row in rows]

        except asyncpg.exceptions.QueryCanceledError as exc:
            raise QueryTimeoutError(int(self.query_timeout)) from exc
        except asyncpg.PostgresError as exc:
            logger.error("fetch_all failed", extra={"sql": sql[:200], "error": str(exc)})
            raise DatabaseError("Query execution failed", detail=str(exc)) from exc

    async def fetch_one(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a SELECT query and return ONE row (or None).

        Args:
            sql:    Parameterized SQL.
            params: Bound values.

        Returns:
            Single row dict or None.
        """
        pool = self._ensure_pool()
        params = params or []

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(sql, *params)
                return dict(row) if row else None

        except asyncpg.exceptions.QueryCanceledError as exc:
            raise QueryTimeoutError(int(self.query_timeout)) from exc
        except asyncpg.PostgresError as exc:
            logger.error("fetch_one failed", extra={"sql": sql[:200], "error": str(exc)})
            raise DatabaseError("Query execution failed", detail=str(exc)) from exc

    async def execute(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
    ) -> str:
        """
        Execute a DML statement (INSERT, UPDATE, DELETE) and return status string.

        Args:
            sql:    Parameterized SQL.
            params: Bound values.

        Returns:
            asyncpg status string (e.g. 'INSERT 0 1').
        """
        pool = self._ensure_pool()
        params = params or []

        try:
            async with pool.acquire() as conn:
                result = await conn.execute(sql, *params)
                return result

        except asyncpg.exceptions.QueryCanceledError as exc:
            raise QueryTimeoutError(int(self.query_timeout)) from exc
        except asyncpg.PostgresError as exc:
            logger.error("execute failed", extra={"sql": sql[:200], "error": str(exc)})
            raise DatabaseError("Statement execution failed", detail=str(exc)) from exc

    async def execute_many(
        self,
        sql: str,
        params_list: List[List[Any]],
    ) -> None:
        """
        Execute a parameterized statement for multiple rows in a single batch.

        Args:
            sql:         Parameterized SQL.
            params_list: List of parameter lists, one per row.
        """
        pool = self._ensure_pool()

        try:
            async with pool.acquire() as conn:
                await conn.executemany(sql, [tuple(p) for p in params_list])

        except asyncpg.PostgresError as exc:
            logger.error("execute_many failed", extra={"sql": sql[:200], "error": str(exc)})
            raise DatabaseError("Batch statement failed", detail=str(exc)) from exc

    async def health_check(self) -> bool:
        """
        Return True if the database is reachable, False otherwise.
        Used by /health endpoints.
        """
        try:
            await self.fetch_one("SELECT 1 AS alive")
            return True
        except Exception:
            return False


# ─── Factory / Singleton helpers ─────────────────────────────────────────────

_connectors: Dict[str, DatabaseConnector] = {}


async def get_connector(database_url: str, **kwargs: Any) -> DatabaseConnector:
    """
    Return an initialized DatabaseConnector for the given URL.
    Creates and caches a single connector per URL (module-level singleton).
    """
    if database_url not in _connectors:
        connector = DatabaseConnector(database_url, **kwargs)
        await connector.initialize()
        _connectors[database_url] = connector
    return _connectors[database_url]
