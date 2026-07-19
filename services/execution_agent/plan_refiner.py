"""
services/execution_agent/plan_refiner.py
Advisory plan refinement based on verification failures or execution errors.

Increment 3.1: Refiner is advisory-only — produces proposals that the caller
must explicitly accept. Never auto-applies changes to dimensions, filters,
or limits.

Refinement strategies:
  - scalar_result_with_multiple_rows: propose removing dimensions or limiting
  - empty_result_for_nonempty: propose reviewing filters
  - missing_columns: suggest alternative column names
  - all_null_metrics: suggest reviewing filters
  - timeout: suggest reducing scope
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PlanRefiner:
    """Advisory-only plan refinement — proposals only, never auto-applies."""

    def refine(
        self,
        plan_summary: Dict[str, Any],
        verification_result: Optional[Dict[str, Any]] = None,
        execution_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Produce advisory proposals based on failure signals.

        Args:
            plan_summary: Simplified plan info (task, tables, metrics, dims, filters)
            verification_result: Output from ResultVerifier.verify()
            execution_error: Error message from query execution

        Returns:
          {
            "refined": bool,
            "reason": str,
            "changes": [],          # always empty in 3.1 (no auto-apply)
            "proposals": [{"field": str, "action": str, "reason": str}],
            "retry_recommended": bool,
          }
        """
        proposals: List[Dict[str, str]] = []
        reason_parts: List[str] = []

        if verification_result and not verification_result.get("verified", True):
            p, r = self._propose_from_verification(plan_summary, verification_result)
            proposals.extend(p)
            if r:
                reason_parts.append(r)

        if execution_error and not proposals:
            p, r = self._propose_from_error(plan_summary, execution_error)
            proposals.extend(p)
            if r:
                reason_parts.append(r)

        if not proposals:
            return {
                "refined": False,
                "reason": "No refinements applicable",
                "changes": [],
                "proposals": [],
                "retry_recommended": False,
            }

        return {
            "refined": True,
            "reason": "; ".join(reason_parts),
            "changes": [],  # Increment 3.1: never auto-apply
            "proposals": proposals,
            "retry_recommended": True,
        }

    def _propose_from_verification(
        self, plan: Dict, verification: Dict,
    ) -> Tuple[List[Dict[str, str]], str]:
        """Generate advisory proposals from verification failure."""
        checks = verification.get("checks", [])
        proposals: List[Dict[str, str]] = []
        reason_parts: List[str] = []

        for check in checks:
            if check.get("passed"):
                continue

            check_name = check.get("check_name", "")
            severity = check.get("severity", "warning")

            if check_name == "row_count_scalar":
                task = plan.get("task", "")
                if task == "aggregation" and plan.get("dimensions"):
                    proposals.append({
                        "field": "dimensions",
                        "action": "remove",
                        "reason": "Scalar answer got multiple rows — consider removing dimensions",
                    })
                    reason_parts.append("scalar got multiple rows → proposed dimension removal")
                else:
                    proposals.append({
                        "field": "limit",
                        "action": "set_to_1",
                        "reason": "Scalar answer got multiple rows — consider LIMIT 1",
                    })
                    reason_parts.append("scalar got multiple rows → proposed LIMIT 1")

            if check_name == "column_presence":
                proposals.append({
                    "field": "columns",
                    "action": "review",
                    "reason": "Missing columns detected — review selected_columns",
                })
                reason_parts.append("missing columns → proposed review")

            if check_name == "no_all_null_metrics":
                proposals.append({
                    "field": "filters",
                    "action": "review",
                    "reason": "Metrics all NULL — review filters or time range",
                })
                reason_parts.append("all-null metrics → proposed filter review")

            if check_name == "nonempty_result":
                if plan.get("filters"):
                    proposals.append({
                        "field": "filters",
                        "action": "relax",
                        "reason": "Empty result with filters — consider relaxing constraints",
                    })
                    reason_parts.append("empty result → proposed filter relaxation")

            if check_name == "empty_result_valid_no_match":
                # Empty is valid per empty_result_semantics — no proposal
                pass

        reason = "; ".join(reason_parts) if reason_parts else ""
        return proposals, reason

    def _propose_from_error(
        self, plan: Dict, error: str,
    ) -> Tuple[List[Dict[str, str]], str]:
        """Generate advisory proposals from execution error."""
        proposals: List[Dict[str, str]] = []
        reason = ""

        error_lower = error.lower()

        if "timeout" in error_lower:
            proposals.append({
                "field": "limit",
                "action": "reduce",
                "reason": "Query timed out — consider reducing scope",
            })
            reason = "timeout → proposed LIMIT reduction"
        elif "permission denied" in error_lower:
            reason = "Permission denied — cannot auto-repair, needs role change"
        elif "does not exist" in error_lower:
            proposals.append({
                "field": "tables",
                "action": "review",
                "reason": "Schema object missing — review table/column mapping",
            })
            reason = "schema object missing → proposed review"

        return proposals, reason

    def apply_refinement(
        self, plan_summary: Dict[str, Any], refinement: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply accepted proposals to a plan summary.

        Increment 3.1: Only applies changes that are explicitly in the
        'changes' list (always empty from refine()). Proposals require
        caller acceptance before passing here.
        """
        if not refinement.get("refined"):
            return plan_summary

        new_plan = dict(plan_summary)
        for change in refinement.get("changes", []):
            field = change["field"]
            new_value = change["to"]
            new_plan[field] = new_value

        logger.info(
            "[PlanRefiner] Applied %d changes: %s",
            len(refinement.get("changes", [])), refinement.get("reason", ""),
        )
        return new_plan
