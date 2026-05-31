import asyncpg
import logging
from typing import List, Dict, Any

from config import Settings
from models import ContextData

logger = logging.getLogger(__name__)


class ContextGatherer:
    """Gather business context to enrich insights (totals, regions, segments)."""

    def __init__(self, config: Settings):
        self.config = config
        self.pool: asyncpg.Pool = None

    async def initialize(self):
        self.pool = await asyncpg.create_pool(
            self.config.DATABASE_URL, min_size=1, max_size=5
        )
        logger.info("ContextGatherer pool initialized")

    async def gather_context(
        self, intent: str, tables: List[str]
    ) -> ContextData:
        """
        Pull totals, regional and segment breakdowns for percentage context.
        Degrades gracefully if any query fails.
        """
        context = ContextData()

        if not self.pool:
            return context

        try:
            # ── System totals ──────────────────────────────────────────────
            total_balance = await self.pool.fetchval(
                "SELECT COALESCE(SUM(balance), 0) FROM accounts"
            )
            context.system_totals["total_deposits"] = float(total_balance or 0)

            total_customers = await self.pool.fetchval(
                "SELECT COUNT(*) FROM customers"
            )
            context.system_totals["total_customers"] = int(total_customers or 0)

            total_transactions = await self.pool.fetchval(
                "SELECT COUNT(*) FROM transactions"
            )
            context.system_totals["total_transactions"] = int(
                total_transactions or 0
            )

            # ── Regional breakdown ────────────────────────────────────────
            regional_rows = await self.pool.fetch(
                "SELECT state, COUNT(*) AS cnt FROM branches GROUP BY state ORDER BY cnt DESC"
            )
            context.regional_breakdown = {
                row["state"]: int(row["cnt"]) for row in regional_rows
            }

            # ── Segment breakdown ──────────────────────────────────────────
            segment_rows = await self.pool.fetch(
                "SELECT segment, COUNT(*) AS cnt FROM customers "
                "WHERE segment IS NOT NULL GROUP BY segment ORDER BY cnt DESC"
            )
            context.segment_breakdown = {
                row["segment"]: int(row["cnt"]) for row in segment_rows
            }

        except Exception as exc:
            logger.error(f"Context gathering failed: {exc}")

        return context
