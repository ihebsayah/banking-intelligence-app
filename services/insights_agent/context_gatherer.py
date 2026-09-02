import logging
from typing import List

from config import Settings
from models import ContextData

logger = logging.getLogger(__name__)


class ContextGatherer:
    """Gathers query-scoped context from metadata only.

    v2.0: No longer executes arbitrary SQL against the database.
    System-wide totals were misleading alongside query-specific results.
    Context now comes exclusively from query metadata passed by the caller.
    """

    def __init__(self, config: Settings):
        self.config = config

    async def initialize(self):
        logger.info("ContextGatherer v2.0 ready (no DB pool)")

    async def gather_context(
        self, intent: str, metadata: dict
    ) -> ContextData:
        """Build context from query metadata — no DB queries."""
        context = ContextData()
        context.system_totals = {
            "rows_returned": metadata.get("rows_returned", 0),
            "execution_time_ms": metadata.get("execution_time_ms", 0),
            "tables_used": metadata.get("tables", []),
        }
        return context
