"""
services/sql_agent/branch_resolver.py
Resolve a raw branch name (from intent extraction) to a canonical branch.

Resolution policy (fail closed):
  1. Exact match, case-insensitive   -> resolved
  2. Exactly one contains-match      -> resolved (partial)
  3. Zero or multiple matches        -> not resolved, candidate list returned

The branches table is the single source of truth — no hardcoded branch names.
"""
import logging
import os
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = (
    "postgresql://banking_user:securepass123@postgres-main:5432/banking_dev"
)

_EXACT_SQL = "SELECT branch_id, name FROM branches WHERE LOWER(name) = LOWER(%s)"
_PARTIAL_SQL = (
    "SELECT branch_id, name FROM branches "
    "WHERE LOWER(name) LIKE '%%' || LOWER(%s) || '%%' "
    "ORDER BY name LIMIT 20"
)


def _default_conn():
    import psycopg2
    return psycopg2.connect(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))


class BranchResolver:
    def __init__(self, get_conn: Optional[Callable[[], Any]] = None):
        self._get_conn = get_conn or _default_conn

    def resolve(self, raw_name: str) -> Dict[str, Any]:
        """Resolve a branch name; see module docstring for the policy."""
        if not raw_name or not raw_name.strip():
            return {"resolved": False, "reason": "empty_name", "matches": []}
        name = raw_name.strip()
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(_EXACT_SQL, (name,))
                    exact = cur.fetchall()
                    if len(exact) == 1:
                        return {
                            "resolved": True,
                            "branch_id": exact[0][0],
                            "name": exact[0][1],
                            "match_type": "exact",
                            "matches": [],
                        }
                    cur.execute(_PARTIAL_SQL, (name,))
                    partials = cur.fetchall()
        except Exception as exc:
            logger.warning("[BranchResolver] database lookup failed: %s", exc)
            return {"resolved": False, "reason": "database_error", "matches": []}

        if len(partials) == 1:
            return {
                "resolved": True,
                "branch_id": partials[0][0],
                "name": partials[0][1],
                "match_type": "partial",
                "matches": [],
            }
        matches = [{"branch_id": r[0], "name": r[1]} for r in partials[:10]]
        if not partials:
            return {"resolved": False, "reason": "not_found", "name": name, "matches": []}
        return {"resolved": False, "reason": "ambiguous", "name": name, "matches": matches}
