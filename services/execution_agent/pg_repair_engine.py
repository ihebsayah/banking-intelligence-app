"""
services/execution_agent/pg_repair_engine.py
Post-execution repair engine for PostgreSQL query failures.

Increment 3.1: Split into three recovery components:
  1. ExecutionRetryPolicy — deadlocks, transients → retry once
  2. SQLMechanicalRepair — semantics-preserving fixes only (GROUP BY, syntax)
  3. PlanRepairRequest — structural issues (missing table/column) → replan

Destructive repairs (removing JOINs, columns, filters) are NEVER applied
directly to SQL. They produce a PlanRepairRequest that the caller routes
back to the planner.
"""
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ExecutionRetryPolicy:
    """Determines whether a transient error should trigger a retry."""

    RETRYABLE = {"deadlock", "timeout", "serialization_failure"}

    def __init__(self, max_retries: int = 1):
        self.max_retries = max_retries

    def should_retry(self, error_type: str, attempt: int) -> bool:
        return attempt < self.max_retries and error_type in self.RETRYABLE


class SQLMechanicalRepair:
    """Semantics-preserving SQL fixes that do not alter query intent.

    Allowed repairs:
      - Add missing GROUP BY column
      - Fix unbalanced parentheses
      - Remove trailing semicolons
    """

    def diagnose(self, error_message: str) -> Dict[str, Any]:
        """Diagnose error and classify as repairable (mechanical) or replan."""
        for pattern, error_type, description in _ERROR_PATTERNS:
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                return {
                    "error_type": error_type,
                    "error_detail": description,
                    "matched_value": match.group(1) if match.lastindex else "",
                }
        return {
            "error_type": "unknown",
            "error_detail": error_message[:200],
            "matched_value": "",
        }

    def repair(self, sql: str, error_type: str, matched_value: str = "") -> Optional[str]:
        """Attempt semantics-preserving repair. Returns repaired SQL or None."""
        if error_type == "group_by_error":
            return self._repair_group_by(sql, matched_value)
        if error_type == "syntax_error":
            return self._repair_syntax(sql)
        return None

    def _repair_group_by(self, sql: str, column_name: str) -> Optional[str]:
        match = re.search(r'(GROUP\s+BY\s+)([^\n]+)', sql, re.IGNORECASE)
        if match:
            existing = match.group(2).strip()
            if column_name not in existing:
                repaired = sql[:match.start(2)] + f"{existing}, {column_name}" + sql[match.end(2):]
                return repaired.strip()
        return None

    def _repair_syntax(self, sql: str) -> Optional[str]:
        repaired = sql.rstrip().rstrip(';')
        open_count = repaired.count('(')
        close_count = repaired.count(')')
        if open_count > close_count:
            repaired += ')' * (open_count - close_count)
        if repaired != sql:
            return repaired.strip()
        return None


class PGRepairEngine:
    """Orchestrates diagnosis → retry / mechanical repair / replan request."""

    def __init__(self):
        self.retry_policy = ExecutionRetryPolicy()
        self.mechanical = SQLMechanicalRepair()

    def diagnose(self, error_message: str) -> Dict[str, Any]:
        """Diagnose a PostgreSQL error."""
        return self.mechanical.diagnose(error_message)

    def attempt_recovery(
        self,
        sql: str,
        error_message: str,
        attempt: int = 0,
    ) -> Dict[str, Any]:
        """
        Three-way recovery split.

        Returns:
          {
            "recovered": bool,
            "retry": bool,            # transient → retry original SQL
            "mechanical_sql": str|None, # semantics-preserving fix
            "plan_repair": dict|None,  # structural → request replan
            "error_type": str,
          }
        """
        diagnosis = self.mechanical.diagnose(error_message)
        error_type = diagnosis["error_type"]
        matched_value = diagnosis.get("matched_value", "")

        # 1. Transient errors → retry
        if self.retry_policy.should_retry(error_type, attempt):
            logger.info("[PGRepairEngine] Transient error %s, retry attempt %d", error_type, attempt + 1)
            return {
                "recovered": True,
                "retry": True,
                "mechanical_sql": None,
                "plan_repair": None,
                "error_type": error_type,
            }

        # 2. Semantics-preserving mechanical repair
        repaired = self.mechanical.repair(sql, error_type, matched_value)
        if repaired:
            repair_id = f"mr-{uuid.uuid4().hex[:8]}"
            logger.info("[PGRepairEngine] Mechanical repair %s: %s", repair_id, error_type)
            return {
                "recovered": True,
                "retry": False,
                "mechanical_sql": repaired,
                "plan_repair": None,
                "error_type": error_type,
                "repair_id": repair_id,
            }

        # 3. Structural issues → plan repair request
        if error_type in ("table_missing", "column_missing", "permission_denied"):
            plan_repair = {
                "reason": diagnosis["error_detail"],
                "error_type": error_type,
                "requested_change": f"{error_type}: {matched_value}",
                "original_sql": sql,
                "original_error": error_message,
            }
            logger.info("[PGRepairEngine] Plan repair request: %s", error_type)
            return {
                "recovered": False,
                "retry": False,
                "mechanical_sql": None,
                "plan_repair": plan_repair,
                "error_type": error_type,
            }

        # 4. Unknown / unrecoverable
        return {
            "recovered": False,
            "retry": False,
            "mechanical_sql": None,
            "plan_repair": None,
            "error_type": error_type,
        }

    # Legacy compatibility
    def repair_sql(self, sql: str, error_type: str, matched_value: str = "") -> Optional[str]:
        return self.mechanical.repair(sql, error_type, matched_value)


# ─── Error patterns (shared between components) ─────────────────────────────

_ERROR_PATTERNS: List[Tuple[str, str, str]] = [
    (r'relation "(\w+)" does not exist', "table_missing", "Table not found in schema"),
    (r'column "(\w+)" does not exist', "column_missing", "Column not found in table"),
    (r'syntax error at or near', "syntax_error", "SQL syntax error"),
    (r'permission denied for (?:table|relation) (\w+)', "permission_denied", "Access denied to table"),
    (r'canceling statement due to statement timeout', "timeout", "Query exceeded timeout"),
    (r'deadlock detected', "deadlock", "Transaction deadlock"),
    (r'column "(\w+)" must appear in the GROUP BY clause', "group_by_error", "Column not in GROUP BY"),
    (r'CASE WHEN.*aggregate.*not allowed', "aggregate_in_case", "Aggregate inside CASE"),
    (r'could not create unique index', "unique_violation", "Unique constraint violation"),
    (r'invalid input syntax for (?:type|integer|numeric|date)', "type_error", "Type conversion error"),
    (r'Out of memory', "oom", "Insufficient memory"),
    (r'invalid authorization', "authorization_error", "Authorization failure"),
]
