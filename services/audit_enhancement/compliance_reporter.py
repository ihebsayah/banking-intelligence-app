import asyncpg
import json
import logging
from datetime import datetime, timedelta
from typing import Dict

from config import Settings
from models import ReportResponse

logger = logging.getLogger(__name__)


class ComplianceReporter:
    """Generate GDPR and SOX compliance reports and persist them to DB."""

    def __init__(self, config: Settings):
        self.config = config
        self.main_pool: asyncpg.Pool = None   # banking_dev — lineage + audit
        self.audit_pool: asyncpg.Pool = None  # audit_logs  — query history

    async def initialize(self):
        self.main_pool = await asyncpg.create_pool(
            self.config.DATABASE_URL, min_size=1, max_size=3
        )
        try:
            self.audit_pool = await asyncpg.create_pool(
                self.config.AUDIT_DATABASE_URL, min_size=1, max_size=3
            )
        except Exception as exc:
            logger.warning(f"Audit DB pool failed (non-fatal): {exc}")
        logger.info("ComplianceReporter pools initialised")

    # ─────────────────────────────────────────────────────────────────────
    # GDPR Right-to-Access report
    # ─────────────────────────────────────────────────────────────────────

    async def generate_gdpr_report(self, user_id: str, days: int = 90) -> ReportResponse:
        now = datetime.utcnow()
        period_start = now - timedelta(days=days)

        try:
            lineage_rows = await self.main_pool.fetch(
                """
                SELECT source_table, source_column, COUNT(*) AS access_count
                FROM data_lineage
                WHERE user_id = $1
                  AND accessed_at >= $2
                GROUP BY source_table, source_column
                ORDER BY access_count DESC
                """,
                user_id, period_start,
            )

            # Try audit log from main DB first (audit_log table if it exists there)
            query_rows = []
            if self.audit_pool:
                try:
                    query_rows = await self.audit_pool.fetch(
                        """
                        SELECT id, user_role, action, endpoint,
                               timestamp, execution_time_ms
                        FROM audit_log
                        WHERE user_id = $1
                          AND timestamp >= $2
                        ORDER BY timestamp DESC
                        LIMIT 200
                        """,
                        user_id, period_start,
                    )
                except Exception:
                    pass

            data = {
                "user_id": user_id,
                "period_days": days,
                "data_accessed": [dict(r) for r in lineage_rows],
                "queries_executed": [dict(r) for r in query_rows],
                "total_field_accesses": sum(r["access_count"] for r in lineage_rows),
                "total_queries": len(query_rows),
            }

            stored = await self._store_report(
                "GDPR_Right_to_Access", "GDPR", period_start, now, data
            )

            return ReportResponse(
                report_type="GDPR_Right_to_Access",
                regulation="GDPR",
                generated_at=now.isoformat(),
                period=f"Last {days} days",
                data=data,
                stored=stored,
            )

        except Exception as exc:
            logger.error(f"GDPR report failed: {exc}")
            return ReportResponse(
                report_type="GDPR_Right_to_Access",
                regulation="GDPR",
                generated_at=datetime.utcnow().isoformat(),
                period=f"Last {days} days",
                error=str(exc),
            )

    # ─────────────────────────────────────────────────────────────────────
    # SOX access-log report
    # ─────────────────────────────────────────────────────────────────────

    async def generate_sox_report(self, days: int = 90) -> ReportResponse:
        now = datetime.utcnow()
        period_start = now - timedelta(days=days)

        try:
            logs = []
            if self.audit_pool:
                logs = await self.audit_pool.fetch(
                    """
                    SELECT user_id, user_role, action, endpoint,
                           timestamp, execution_time_ms
                    FROM audit_log
                    WHERE timestamp >= $1
                    ORDER BY timestamp DESC
                    LIMIT 1000
                    """,
                    period_start,
                )

            by_role: Dict[str, list] = {}
            for row in logs:
                role = row["user_role"] or "unknown"
                by_role.setdefault(role, []).append(dict(row))

            data = {
                "period_days": days,
                "access_by_role": by_role,
                "total_accesses": len(logs),
                "unique_users": len({r["user_id"] for r in logs}),
            }

            stored = await self._store_report(
                "SOX_Access_Log", "SOX", period_start, now, data
            )

            return ReportResponse(
                report_type="SOX_Access_Log",
                regulation="SOX",
                generated_at=now.isoformat(),
                period=f"Last {days} days",
                data=data,
                stored=stored,
            )

        except Exception as exc:
            logger.error(f"SOX report failed: {exc}")
            return ReportResponse(
                report_type="SOX_Access_Log",
                regulation="SOX",
                generated_at=datetime.utcnow().isoformat(),
                period=f"Last {days} days",
                error=str(exc),
            )

    # ─────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────

    async def _store_report(
        self,
        report_type: str,
        regulation: str,
        period_start: datetime,
        period_end: datetime,
        data: dict,
    ) -> bool:
        try:
            await self.main_pool.execute(
                """
                INSERT INTO regulatory_reports
                    (report_type, regulation, report_period_start,
                     report_period_end, report_content, status)
                VALUES ($1, $2, $3, $4, $5, 'draft')
                """,
                report_type,
                regulation,
                period_start.date(),
                period_end.date(),
                json.dumps(data, default=str),
            )
            return True
        except Exception as exc:
            logger.warning(f"Report storage skipped: {exc}")
            return False
