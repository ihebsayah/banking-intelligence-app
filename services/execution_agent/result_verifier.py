"""
services/execution_agent/result_verifier.py
Validates returned datasets against ExpectedAnswer rather than inspecting SQL.

Increment 3.1: Expanded verification with severity levels and empty-result
semantics. Checks now carry a severity (critical/warning/informational) so
the caller can decide whether to block, warn, or log.

Checks performed:
  1. row_count — matches answer type expectations
  2. column_presence — expected columns present
  3. metric_numeric — metric columns contain numeric values
  4. dimension_presence — dimension columns present
  5. no_all_null_metrics — metric columns not all NULL
  6. empty_result — respects empty_result_semantics from ExpectedAnswer
  7. grain_consistency — output grain columns exist
  8. metric_value_range — values within min/max if MetricValidationRules set
  9. ratio_sanity — ratio metrics between 0 and 100 (or 0 and 1)
 10. duplicate_rows — no unexpected duplicate rows
 11. null_ratio — null percentage per metric column
 12. ordering — result ordering matches expected ordering
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResultVerifier:
    """Verify query results against ExpectedAnswer metadata from the QueryPlan."""

    def verify(
        self,
        data: List[Dict[str, Any]],
        expected_answer: Optional[Dict[str, Any]] = None,
        plan_metrics: Optional[List[str]] = None,
        plan_dimensions: Optional[List[str]] = None,
        plan_grain: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Verify dataset against expected answer shape.

        Returns:
          {
            "verified": bool,
            "checks": [{"check_name": str, "passed": bool, "severity": str, "message": str}],
            "row_count": int,
            "column_count": int,
            "repair_suggestions": [str],
            "critical_failures": [str],
            "warnings": [str],
            "informational": [str],
          }
        """
        if not expected_answer:
            return {
                "verified": True,
                "checks": [],
                "row_count": len(data),
                "column_count": len(data[0]) if data else 0,
                "repair_suggestions": [],
                "critical_failures": [],
                "warnings": [],
                "informational": [],
            }

        checks = []
        suggestions = []

        # 1. Row count sanity
        checks.append(self._check_row_count(data, expected_answer))

        # 2. Column presence
        col_check = self._check_columns(data, expected_answer)
        checks.append(col_check)
        if not col_check["passed"]:
            suggestions.append(col_check.get("repair", ""))

        # 3. Metric columns numeric
        checks.append(self._check_metric_columns(
            data, plan_metrics or expected_answer.get("expected_metrics", []),
        ))

        # 4. Dimension columns present
        checks.append(self._check_dimension_columns(
            data, plan_dimensions or expected_answer.get("expected_dimensions", []),
        ))

        # 5. No all-NULL metrics
        null_check = self._check_no_all_null_metrics(
            data, plan_metrics or expected_answer.get("expected_metrics", []),
        )
        checks.append(null_check)
        if not null_check["passed"] and expected_answer.get("empty_result_semantics") != "expect_scalar_null":
            suggestions.append(null_check.get("repair", ""))

        # 6. Empty result semantics (Increment 3.1)
        empty_check = self._check_empty_result_semantics(data, expected_answer)
        checks.append(empty_check)

        # 7. Grain consistency
        if plan_grain:
            checks.append(self._check_grain_consistency(data, plan_grain))

        # 8. Metric value range (Increment 3.1)
        checks.append(self._check_metric_value_range(
            data,
            plan_metrics or expected_answer.get("expected_metrics", []),
            expected_answer.get("metric_validation_rules", {}),
        ))

        # 9. Ratio sanity (Increment 3.1)
        checks.append(self._check_ratio_sanity(
            data, plan_metrics or expected_answer.get("expected_metrics", []),
        ))

        # 10. Duplicate rows (Increment 3.1)
        checks.append(self._check_duplicate_rows(data))

        # 11. Null ratio (Increment 3.1)
        checks.append(self._check_null_ratio(
            data, plan_metrics or expected_answer.get("expected_metrics", []),
        ))

        # 12. Ordering (Increment 3.1)
        checks.append(self._check_ordering(data, expected_answer))

        # Aggregate severity buckets
        critical = [c["check_name"] for c in checks if not c["passed"] and c.get("severity") == "critical"]
        warnings = [c["check_name"] for c in checks if not c["passed"] and c.get("severity") == "warning"]
        info = [c["check_name"] for c in checks if not c["passed"] and c.get("severity") == "informational"]

        verified = not critical  # verified unless critical failures
        suggestions = [s for s in suggestions if s]

        return {
            "verified": verified,
            "checks": checks,
            "row_count": len(data),
            "column_count": len(data[0]) if data else 0,
            "repair_suggestions": suggestions,
            "critical_failures": critical,
            "warnings": warnings,
            "informational": info,
        }

    # ── Individual checks ─────────────────────────────────────────────────

    def _check_row_count(
        self, data: List[Dict], expected: Dict,
    ) -> Dict[str, Any]:
        answer_type = expected.get("answer_type", "")
        n_rows = len(data)

        if answer_type == "scalar" and n_rows != 1:
            empty_sem = expected.get("empty_result_semantics", "invalid")
            if n_rows == 0 and empty_sem in ("expect_scalar_zero", "expect_scalar_null", "valid_no_match"):
                return {
                    "check_name": "row_count_scalar",
                    "passed": True,
                    "severity": "informational",
                    "expected": "1 row for scalar",
                    "actual": f"{n_rows} rows",
                    "message": f"0 rows for scalar acceptable per empty_result_semantics={empty_sem}",
                }
            return {
                "check_name": "row_count_scalar",
                "passed": False,
                "severity": "critical",
                "expected": "1 row for scalar",
                "actual": f"{n_rows} rows",
                "message": f"Scalar answer expects exactly 1 row, got {n_rows}",
                "repair": "add_group_by" if n_rows > 1 else "",
            }
        if answer_type in ("grouped_rows", "ranked_list", "time_series") and n_rows == 0:
            empty_sem = expected.get("empty_result_semantics", "invalid")
            if empty_sem == "invalid":
                return {
                    "check_name": "row_count_nonempty",
                    "passed": False,
                    "severity": "critical",
                    "expected": ">=1 row",
                    "actual": "0 rows",
                    "message": f"{answer_type} answer should have rows",
                    "repair": "fix_null_filter",
                }
            else:
                return {
                    "check_name": "row_count_nonempty",
                    "passed": True,
                    "severity": "informational",
                    "message": f"0 rows acceptable per empty_result_semantics={empty_sem}",
                }
        return {
            "check_name": "row_count",
            "passed": True,
            "severity": "informational",
            "expected": answer_type,
            "actual": f"{n_rows} rows",
            "message": "Row count OK",
        }

    def _check_columns(
        self, data: List[Dict], expected: Dict,
    ) -> Dict[str, Any]:
        if not data:
            return {
                "check_name": "column_presence",
                "passed": True,
                "severity": "informational",
                "message": "Empty result — column check skipped",
            }

        exp_cols = expected.get("expected_columns", [])
        if not exp_cols:
            return {
                "check_name": "column_presence",
                "passed": True,
                "severity": "informational",
                "message": "No expected columns specified",
            }

        actual_cols = set(data[0].keys())
        actual_lower = {c.lower() for c in actual_cols}

        missing = []
        for ec in exp_cols:
            ec_base = ec.split(".")[-1] if "." in ec else ec
            if ec not in actual_cols and ec_base.lower() not in actual_lower:
                missing.append(ec)

        if missing:
            return {
                "check_name": "column_presence",
                "passed": False,
                "severity": "critical",
                "expected": str(exp_cols),
                "actual": str(list(actual_cols)),
                "message": f"Missing columns: {missing}",
                "repair": "add_group_by",
            }
        return {
            "check_name": "column_presence",
            "passed": True,
            "severity": "informational",
            "message": "All expected columns present",
        }

    def _check_metric_columns(
        self, data: List[Dict], metrics: List[str],
    ) -> Dict[str, Any]:
        if not data or not metrics:
            return {
                "check_name": "metric_numeric",
                "passed": True,
                "severity": "informational",
                "message": "No data or no metrics to check",
            }

        first_row = data[0]
        non_numeric = []
        for m in metrics:
            if m in first_row:
                val = first_row[m]
                if val is not None and not isinstance(val, (int, float, Decimal)):
                    non_numeric.append(m)

        if non_numeric:
            return {
                "check_name": "metric_numeric",
                "passed": False,
                "severity": "critical",
                "expected": "numeric values",
                "actual": f"non-numeric: {non_numeric}",
                "message": f"Metric columns non-numeric: {non_numeric}",
            }
        return {
            "check_name": "metric_numeric",
            "passed": True,
            "severity": "informational",
            "message": "Metric columns are numeric",
        }

    def _check_dimension_columns(
        self, data: List[Dict], dimensions: List[str],
    ) -> Dict[str, Any]:
        if not data or not dimensions:
            return {
                "check_name": "dimension_presence",
                "passed": True,
                "severity": "informational",
                "message": "No data or no dimensions to check",
            }

        actual_cols = set(data[0].keys())
        missing = []
        for d in dimensions:
            d_base = d.split(".")[-1] if "." in d else d
            if d not in actual_cols and d_base not in actual_cols:
                missing.append(d)

        if missing:
            return {
                "check_name": "dimension_presence",
                "passed": False,
                "severity": "warning",
                "expected": str(dimensions),
                "actual": str(list(actual_cols)),
                "message": f"Missing dimension columns: {missing}",
            }
        return {
            "check_name": "dimension_presence",
            "passed": True,
            "severity": "informational",
            "message": "Dimension columns present",
        }

    def _check_no_all_null_metrics(
        self, data: List[Dict], metrics: List[str],
    ) -> Dict[str, Any]:
        if not data or not metrics:
            return {
                "check_name": "no_all_null_metrics",
                "passed": True,
                "severity": "informational",
                "message": "No data or no metrics to check",
            }

        all_null = []
        for m in metrics:
            values = [row.get(m) for row in data]
            if all(v is None for v in values):
                all_null.append(m)

        if all_null:
            return {
                "check_name": "no_all_null_metrics",
                "passed": False,
                "severity": "warning",
                "expected": "at least one non-NULL value",
                "actual": f"all NULL: {all_null}",
                "message": f"Metric columns all NULL: {all_null}",
                "repair": "fix_null_filter",
            }
        return {
            "check_name": "no_all_null_metrics",
            "passed": True,
            "severity": "informational",
            "message": "Metrics have non-NULL values",
        }

    def _check_empty_result_semantics(
        self, data: List[Dict], expected: Dict,
    ) -> Dict[str, Any]:
        """Increment 3.1: Respect empty_result_semantics from ExpectedAnswer."""
        answer_type = expected.get("answer_type", "")
        empty_sem = expected.get("empty_result_semantics", "invalid")

        if len(data) > 0:
            return {
                "check_name": "empty_result_check",
                "passed": True,
                "severity": "informational",
                "message": "Non-empty result — empty semantics not applicable",
            }

        if empty_sem == "valid_no_match":
            return {
                "check_name": "empty_result_valid_no_match",
                "passed": True,
                "severity": "informational",
                "message": "Empty result is valid per empty_result_semantics",
            }
        if empty_sem == "expect_scalar_zero":
            return {
                "check_name": "empty_result_expect_scalar_zero",
                "passed": True,
                "severity": "informational",
                "message": "Empty result acceptable — scalar should be interpreted as 0",
            }
        if empty_sem == "expect_scalar_null":
            return {
                "check_name": "empty_result_expect_scalar_null",
                "passed": True,
                "severity": "informational",
                "message": "Empty result acceptable — scalar should be interpreted as NULL",
            }
        # invalid
        if answer_type != "detail_rows":
            return {
                "check_name": "empty_result_invalid",
                "passed": False,
                "severity": "critical",
                "expected": "non-empty for " + answer_type,
                "actual": "0 rows",
                "message": f"Empty result invalid for {answer_type}",
                "repair": "fix_null_filter",
            }
        return {
            "check_name": "empty_result_check",
            "passed": True,
            "severity": "informational",
            "message": "Detail queries may legitimately return 0 rows",
        }

    def _check_grain_consistency(
        self, data: List[Dict], grain: Dict,
    ) -> Dict[str, Any]:
        output_grain = grain.get("output_grain", "scalar")
        if output_grain == "scalar":
            return {
                "check_name": "grain_consistency",
                "passed": True,
                "severity": "informational",
                "message": "Scalar grain — no dimension check needed",
            }

        grain_cols = [g.strip() for g in output_grain.split(",")]
        if not data:
            return {
                "check_name": "grain_consistency",
                "passed": True,
                "severity": "informational",
                "message": "Empty data — grain check skipped",
            }

        actual_cols = set(data[0].keys())
        missing = [g for g in grain_cols if g not in actual_cols and g.lower() not in {c.lower() for c in actual_cols}]

        if missing:
            return {
                "check_name": "grain_consistency",
                "passed": False,
                "severity": "warning",
                "expected": f"grain columns: {grain_cols}",
                "actual": str(list(actual_cols)),
                "message": f"Grain columns missing: {missing}",
            }
        return {
            "check_name": "grain_consistency",
            "passed": True,
            "severity": "informational",
            "message": "Grain columns present",
        }

    def _check_metric_value_range(
        self, data: List[Dict], metrics: List[str], rules: Dict,
    ) -> Dict[str, Any]:
        """Increment 3.1: Check metric values against MetricValidationRules."""
        if not data or not metrics or not rules:
            return {
                "check_name": "metric_value_range",
                "passed": True,
                "severity": "informational",
                "message": "No validation rules to check",
            }

        violations = []
        for m in metrics:
            rule = rules.get(m)
            if not rule:
                continue
            for row in data:
                val = row.get(m)
                if val is None:
                    if not rule.get("nullable", True):
                        violations.append(f"{m}: NULL not allowed")
                    continue
                if not isinstance(val, (int, float, Decimal)):
                    continue
                if rule.get("minimum") is not None and val < rule["minimum"]:
                    violations.append(f"{m}: {val} < minimum {rule['minimum']}")
                if rule.get("maximum") is not None and val > rule["maximum"]:
                    violations.append(f"{m}: {val} > maximum {rule['maximum']}")
                if rule.get("finite_only") and not (-1e18 < val < 1e18):
                    violations.append(f"{m}: {val} not finite")

        if violations:
            return {
                "check_name": "metric_value_range",
                "passed": False,
                "severity": "warning",
                "message": f"Value range violations: {violations[:5]}",
            }
        return {
            "check_name": "metric_value_range",
            "passed": True,
            "severity": "informational",
            "message": "All metric values within range",
        }

    def _check_ratio_sanity(
        self, data: List[Dict], metrics: List[str],
    ) -> Dict[str, Any]:
        """Increment 3.1: Check ratio metrics are between 0 and 100."""
        ratio_keywords = {"ratio", "rate", "percentage", "pct", "deposit"}
        ratio_metrics = [m for m in metrics if any(k in m.lower() for k in ratio_keywords)]

        if not data or not ratio_metrics:
            return {
                "check_name": "ratio_sanity",
                "passed": True,
                "severity": "informational",
                "message": "No ratio metrics to check",
            }

        bad = []
        for m in ratio_metrics:
            for row in data:
                val = row.get(m)
                if val is not None and isinstance(val, (int, float)):
                    if val < 0 or val > 100:
                        bad.append(f"{m}={val}")

        if bad:
            return {
                "check_name": "ratio_sanity",
                "passed": False,
                "severity": "warning",
                "message": f"Ratio values out of [0, 100]: {bad[:5]}",
            }
        return {
            "check_name": "ratio_sanity",
            "passed": True,
            "severity": "informational",
            "message": "Ratio values within [0, 100]",
        }

    def _check_duplicate_rows(self, data: List[Dict]) -> Dict[str, Any]:
        """Increment 3.1: Detect unexpected duplicate rows."""
        if len(data) <= 1:
            return {
                "check_name": "duplicate_rows",
                "passed": True,
                "severity": "informational",
                "message": "Too few rows for duplicate check",
            }

        seen = set()
        dupes = 0
        for row in data:
            key = tuple(sorted(row.items()))
            if key in seen:
                dupes += 1
            seen.add(key)

        if dupes > 0:
            return {
                "check_name": "duplicate_rows",
                "passed": False,
                "severity": "warning",
                "message": f"{dupes} duplicate rows detected",
            }
        return {
            "check_name": "duplicate_rows",
            "passed": True,
            "severity": "informational",
            "message": "No duplicate rows",
        }

    def _check_null_ratio(
        self, data: List[Dict], metrics: List[str],
    ) -> Dict[str, Any]:
        """Increment 3.1: Report null percentage per metric."""
        if not data or not metrics:
            return {
                "check_name": "null_ratio",
                "passed": True,
                "severity": "informational",
                "message": "No data or metrics for null ratio check",
            }

        high_null = []
        n_rows = len(data)
        for m in metrics:
            null_count = sum(1 for row in data if row.get(m) is None)
            null_pct = (null_count / n_rows) * 100 if n_rows > 0 else 0
            if null_pct >= 80:
                high_null.append(f"{m}: {null_pct:.0f}%")

        if high_null:
            return {
                "check_name": "null_ratio",
                "passed": False,
                "severity": "warning",
                "message": f"High null ratio: {high_null}",
            }
        return {
            "check_name": "null_ratio",
            "passed": True,
            "severity": "informational",
            "message": "Null ratios acceptable",
        }

    def _check_ordering(
        self, data: List[Dict], expected: Dict,
    ) -> Dict[str, Any]:
        """Increment 3.1: Check result ordering matches expected."""
        ordering = expected.get("ordering")
        if not ordering or len(data) <= 1:
            return {
                "check_name": "ordering",
                "passed": True,
                "severity": "informational",
                "message": "No ordering expected or too few rows",
            }

        # Parse ordering like "risk_score DESC"
        parts = ordering.strip().split()
        col = parts[0]
        direction = parts[1].upper() if len(parts) > 1 else "ASC"

        values = [row.get(col) for row in data if row.get(col) is not None]
        if len(values) <= 1:
            return {
                "check_name": "ordering",
                "passed": True,
                "severity": "informational",
                "message": "Not enough non-null values to check ordering",
            }

        is_sorted = all(
            values[i] <= values[i + 1] if direction == "ASC" else values[i] >= values[i + 1]
            for i in range(len(values) - 1)
        )

        if not is_sorted:
            return {
                "check_name": "ordering",
                "passed": False,
                "severity": "warning",
                "message": f"Result not sorted by {col} {direction}",
            }
        return {
            "check_name": "ordering",
            "passed": True,
            "severity": "informational",
            "message": f"Result sorted by {col} {direction}",
        }
