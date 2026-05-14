"""
services/shared/redis_client.py
Redis cache client used by all services.
Handles query result caching, session tokens, and schema caching.
"""
import json
import hashlib
import os
from typing import Any, Optional
import redis.asyncio as aioredis

from shared.logger import get_logger

logger = get_logger(__name__, "redis-client")

# Default TTLs
TTL_QUERY_RESULTS = 3600       # 1 hour for query results
TTL_SCHEMA_INFO = 86400        # 24 hours for schema metadata
TTL_EMBEDDINGS = 86400 * 7    # 7 days for embedding vectors
TTL_SESSION = 28800            # 8 hours for session data


class RedisCache:
    """
    Async Redis cache wrapper.

    Keys are namespaced: `namespace:key`
    e.g. `query:sha256hash`, `schema:table_name`, `session:user_id`
    """

    def __init__(self, redis_url: str):
        self._url = redis_url
        self._client: Optional[aioredis.Redis] = None

    async def initialize(self) -> None:
        """Connect to Redis. Call once at service startup."""
        try:
            self._client = aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self._client.ping()
            logger.info("Redis connection established", extra={"url": self._url})
        except Exception as exc:
            logger.warning(
                "Redis unavailable — caching disabled",
                extra={"error": str(exc)},
            )
            self._client = None  # Non-fatal: service runs without cache

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ─── Generic Get / Set / Delete ─────────────────────────────────────────

    async def get(self, key: str) -> Optional[Any]:
        """Return deserialized value for key, or None if missing/unavailable."""
        if not self._client:
            return None
        try:
            raw = await self._client.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Redis GET failed", extra={"key": key, "error": str(exc)})
            return None

    async def set(self, key: str, value: Any, ttl: int = TTL_QUERY_RESULTS) -> bool:
        """Serialize and store value with TTL. Returns True on success."""
        if not self._client:
            return False
        try:
            serialized = json.dumps(value, default=str)
            await self._client.setex(key, ttl, serialized)
            return True
        except Exception as exc:
            logger.warning("Redis SET failed", extra={"key": key, "error": str(exc)})
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key. Returns True if it existed."""
        if not self._client:
            return False
        try:
            result = await self._client.delete(key)
            return result > 0
        except Exception as exc:
            logger.warning("Redis DEL failed", extra={"key": key, "error": str(exc)})
            return False

    # ─── Named helpers ───────────────────────────────────────────────────────

    @staticmethod
    def query_hash(sql: str, params: list) -> str:
        """Generate a stable SHA-256 hash key for a (sql, params) pair."""
        message = f"{sql.strip()}:{json.dumps(params, sort_keys=True, default=str)}"
        return hashlib.sha256(message.encode()).hexdigest()

    async def get_cached_query(self, sql: str, params: list) -> Optional[Any]:
        """Look up a cached query result."""
        key = f"query:{self.query_hash(sql, params)}"
        return await self.get(key)

    async def cache_query_result(self, sql: str, params: list, result: Any) -> bool:
        """Cache a query result for TTL_QUERY_RESULTS seconds."""
        key = f"query:{self.query_hash(sql, params)}"
        return await self.set(key, result, ttl=TTL_QUERY_RESULTS)

    async def get_schema(self, table_name: str) -> Optional[Any]:
        """Look up cached schema for a table."""
        return await self.get(f"schema:{table_name}")

    async def cache_schema(self, table_name: str, schema: Any) -> bool:
        """Cache schema info for 24 hours."""
        return await self.set(f"schema:{table_name}", schema, ttl=TTL_SCHEMA_INFO)

    async def get_session(self, user_id: str) -> Optional[Any]:
        """Retrieve session data for a user."""
        return await self.get(f"session:{user_id}")

    async def set_session(self, user_id: str, data: Any) -> bool:
        """Store session data (8 hours TTL)."""
        return await self.set(f"session:{user_id}", data, ttl=TTL_SESSION)

    async def health_check(self) -> bool:
        """Return True if Redis is reachable."""
        if not self._client:
            return False
        try:
            return await self._client.ping()
        except Exception:
            return False
