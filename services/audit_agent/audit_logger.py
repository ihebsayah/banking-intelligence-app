"""
services/audit_agent/audit_logger.py
Core audit logging logic — inserts records into the immutable audit_log table.

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

    Every public method uses a parameterized INSERT — no string interpolation.
    The DB-level RULE prevents any UPDATE or DELETE from taking effect.
    """

    def __init__(self, db: DatabaseConnector):
        self._db = db

    async def log_access(self, entry: AuditLogEntry) -> AuditLogResponse:
        """
        Insert one audit log record.

        Args:
            entry: Fully populated AuditLogEntry model.

        Returns:
            AuditLogResponse with logged=True and the audit_id.

        Raises:
            AuditLoggingError: If the INSERT fails (caller decides how to handle).
        """
        # Serialize tables_accessed list to JSON string for TEXT column
        tables_json: Optional[str] = None
        if entry.tables_accessed:
            tables_json = json.dumps(entry.tables_accessed)

        # Serialize metadata dict to JSONB-compatible string
        metadata_json: Optional[str] = None
        if entry.metadata:
            metadata_json = json.dumps(entry.metadata, default=str)

        # ─── Parameterized INSERT — no f-strings, no concatenation ───────────
        sql = """
            INSERT INTO audit_log (
                audit_id,
                timestamp,
                user_id,
                user_role,
                action,
                query_intent,
                tables_accessed,
                rows_accessed,
                execution_time_ms,
                status,
                ip_address,
                endpoint,
                http_method,
                query_signature,
                data_freshness,
                error_message,
                metadata
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15,
                $16, $17::jsonb
            )
        """

        params = [
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

        try:
            await self._db.execute(sql, params)
            logger.info(
                "Audit log entry written",
                extra={
                    "audit_id": entry.audit_id,
                    "user_id": entry.user_id,
                    "action": entry.action,
                    "status": entry.status,
                },
            )
            return AuditLogResponse(logged=True, audit_id=entry.audit_id)

        except DatabaseError as exc:
            logger.error(
                "Failed to write audit log",
                extra={"audit_id": entry.audit_id, "error": str(exc)},
            )
            raise AuditLoggingError(str(exc)) from exc

    async def get_recent_logs(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """
        Fetch recent audit log entries (read-only, for compliance review).

        Args:
            user_id: Filter by specific user (optional).
            limit:   Maximum rows to return (max 1000).

        Returns:
            List of audit_log row dicts ordered by timestamp DESC.
        """
        limit = min(limit, 1000)  # safety cap

        if user_id:
            sql = """
                SELECT * FROM audit_log
                WHERE user_id = $1
                ORDER BY timestamp DESC
                LIMIT $2
            """
            return await self._db.fetch_all(sql, [user_id, limit])
        else:
            sql = """
                SELECT * FROM audit_log
                ORDER BY timestamp DESC
                LIMIT $1
            """
            return await self._db.fetch_all(sql, [limit])
