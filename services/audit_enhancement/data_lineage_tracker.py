import asyncpg
import logging
from typing import List

from config import Settings
from models import LineageResponse

logger = logging.getLogger(__name__)


class DataLineageTracker:
    """Record per-field data access for GDPR right-to-access audits."""

    def __init__(self, config: Settings):
        self.config = config
        self.pool: asyncpg.Pool = None

    async def initialize(self):
        self.pool = await asyncpg.create_pool(
            self.config.DATABASE_URL, min_size=1, max_size=3
        )
        logger.info("DataLineageTracker pool initialised")

    async def track(
        self,
        query_id: str,
        user_id: str,
        source_tables: List[str],
        accessed_columns: List[str],
    ) -> LineageResponse:
        if not self.pool:
            return LineageResponse(logged=False, error="No DB pool")

        try:
            records = 0
            async with self.pool.acquire() as conn:
                for table in source_tables:
                    for col in accessed_columns:
                        await conn.execute(
                            """
                            INSERT INTO data_lineage
                                (query_id, source_table, source_column,
                                 destination_column, user_id)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            query_id, table, col, col, user_id,
                        )
                        records += 1

            logger.info(
                f"Lineage tracked: query={query_id} user={user_id} "
                f"tables={source_tables} cols={accessed_columns} → {records} rows"
            )
            return LineageResponse(logged=True, records=records)

        except Exception as exc:
            logger.error(f"DataLineageTracker.track failed: {exc}")
            return LineageResponse(logged=False, error=str(exc))
