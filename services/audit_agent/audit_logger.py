"""services/audit_agent/audit_logger.py
Core audit logging logic — inserts records into the immutable audit_log table.

Supports idempotency key: if the same key is used twice, returns the existing
record without error (idempotent POST /log_access).

CRITICAL: This table is append-only. No UPDATE or DELETE ever.
          The PostgreSQL RULE enforces this at the DB level.
"""
import json
import uuid
from datetime import datetime
from typing import Optional

from shared.database import DatabaseConnector
from shared.errors import AuditLoggingError, DatabaseError
from shared.logger import get_logger
from shared.models import AuditLogEntry, AuditLogResponse

logger = get_logger(__name__, "audit-agent")


class AuditLogger:
    """
    Writes immutable audit log entries to the audit_log table.

    Supports idempotency via idempotency_key column with UNIQUE constraint.
    Every public method uses a parameterized INSERT — no string interpolation.
    The DB-level RULE prevents any UPDATE or DELETE from taking effect.
    """

    def __init__(self, db: DatabaseConnector):
        self._db = db

    async def log_access(
        self,
        entry: AuditLogEntry,
        idempotency_key: Optional[str] = None,
    ) -> AuditLogResponse:
        """
        Insert one audit log record.

        If idempotency_key is provided and a row with that key already exists,
        returns the existing audit_id (200, not 409). No duplicate row is created.

        Args:
            entry: Fully populated AuditLogEntry model.
            idempotency_key: Optional X-Idempotency-Key for deduplication.

        Returns:
            AuditLogResponse with logged=True and the audit_id.

        Raises:
            AuditLoggingError: If the INSERT fails (caller decides how to handle).
        """
        tables_json: Optional[str] = None
        if entry.tables_accessed:
            tables_json = json.dumps(entry.tables_accessed)

        metadata_json: Optional[str] = None
        if entry.metadata:
            metadata_json = json.dumps(entry.metadata, default=str)

        if idempotency_key:
            return await self._log_access_idempotent(
                entry, idempotency_key, tables_json, metadata_json,
            )

        return await self._log_access_simple(entry, tables_json, metadata_json)

    async def _log_access_simple(
        self,
        entry: AuditLogEntry,
        tables_json: Optional[str],
        metadata_json: Optional[str],
    ) -> AuditLogResponse:
        sql = """
            INSERT INTO audit_log (
                audit_id, timestamp, user_id, user_role, action,
                query_intent, tables_accessed, rows_accessed,
                execution_time_ms, status, ip_address, endpoint,
                http_method, query_signature, data_freshness,
                error_message, metadata
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15,
                $16, $17::jsonb
            )
        """
        params = self._build_params(entry, tables_json, metadata_json)

        try:
            await self._db.execute(sql, params)
            logger.info("Audit log entry written", extra={
                "audit_id": entry.audit_id, "user_id": entry.user_id,
                "action": entry.action, "status": entry.status,
            })
            return AuditLogResponse(logged=True, audit_id=entry.audit_id)
        except DatabaseError as exc:
            logger.error("Failed to write audit log", extra={
                "audit_id": entry.audit_id, "error": str(exc),
            })
            raise AuditLoggingError(str(exc)) from exc

    async def _log_access_idempotent(
        self,
        entry: AuditLogEntry,
        idempotency_key: str,
        tables_json: Optional[str],
        metadata_json: Optional[str],
    ) -> AuditLogResponse:
        sql = """
            INSERT INTO audit_log (
                audit_id, timestamp, user_id, user_role, action,
                query_intent, tables_accessed, rows_accessed,
                execution_time_ms, status, ip_address, endpoint,
                http_method, query_signature, data_freshness,
                error_message, metadata, idempotency_key
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15,
                $16, $17::jsonb, $18
            )
            ON CONFLICT (idempotency_key) DO NOTHING
        """
        params = self._build_params(entry, tables_json, metadata_json) + [idempotency_key]

        try:
            result = await self._db.execute(sql, params)
            if result and result.strip() == "INSERT 0 0":
                existing = await self._db.fetch_one(
                    "SELECT audit_id FROM audit_log WHERE idempotency_key = $1",
                    [idempotency_key],
                )
                if existing:
                    return AuditLogResponse(logged=True, audit_id=existing["audit_id"])
            return AuditLogResponse(logged=True, audit_id=entry.audit_id)
        except DatabaseError as exc:
            logger.error("Failed to write audit log", extra={
                "audit_id": entry.audit_id, "error": str(exc),
            })
            raise AuditLoggingError(str(exc)) from exc

    def _build_params(
        self,
        entry: AuditLogEntry,
        tables_json: Optional[str],
        metadata_json: Optional[str],
    ) -> list:
        return [
            entry.audit_id,
            entry.timestamp,
            entry.user_id,
            entry.user_role,
            entry.action,
            entry.query_intent,
            tables_json,
            entry.rows_accessed,
            entry.execution_time_ms,
            entry.status if isinstance(entry.status, str) else entry.status.value,
            entry.ip_address,
            entry.endpoint,
            entry.http_method,
            entry.query_signature,
            entry.data_freshness,
            entry.error_message,
            metadata_json,
        ]

    async def get_recent_logs(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """Fetch recent audit log entries (read-only, for compliance review)."""
        limit = min(limit, 1000)
        if user_id:
            return await self._db.fetch_all(
                "SELECT * FROM audit_log WHERE user_id = $1 ORDER BY timestamp DESC LIMIT $2",
                [user_id, limit],
            )
        return await self._db.fetch_all(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT $1",
            [limit],
        )
