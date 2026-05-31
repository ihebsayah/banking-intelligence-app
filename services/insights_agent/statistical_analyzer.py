import numpy as np
from typing import List, Dict, Any, Optional
from models import StatisticalAnalysis


class StatisticalAnalyzer:
    """Analyze query results for statistical patterns."""

    def analyze(
        self,
        results: List[Dict[str, Any]],
        numeric_columns: Optional[List[str]] = None,
    ) -> StatisticalAnalysis:
        """
        Calculate descriptive statistics over result set.
        Auto-detects numeric columns when none provided.
        """
        if not results:
            return StatisticalAnalysis()

        if numeric_columns is None:
            numeric_columns = self._detect_numeric_columns(results)

        if not numeric_columns:
            return StatisticalAnalysis()

        # Use the first numeric column found for primary statistics
        primary_col = numeric_columns[0]
        values = [
            float(r[primary_col])
            for r in results
            if r.get(primary_col) is not None
            and isinstance(r[primary_col], (int, float))
        ]

        if not values:
            return StatisticalAnalysis()

        arr = np.array(values, dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr))

        outlier_labels = [
            f"{primary_col}={v:.2f} (deviation={abs(v - mean):.2f})"
            for v in values
            if abs(v - mean) > 2 * std
        ]

        return StatisticalAnalysis(
            total_sum=float(np.sum(arr)),
            average=mean,
            median=float(np.median(arr)),
            std_dev=std,
            min_value=float(np.min(arr)),
            max_value=float(np.max(arr)),
            percentiles={
                "p25": float(np.percentile(arr, 25)),
                "p50": float(np.percentile(arr, 50)),
                "p75": float(np.percentile(arr, 75)),
                "p90": float(np.percentile(arr, 90)),
                "p99": float(np.percentile(arr, 99)),
            },
            outliers=outlier_labels,
        )

    def _detect_numeric_columns(self, results: List[Dict]) -> List[str]:
        """Return columns whose first non-None value is a real number."""
        if not results:
            return []
        numeric_cols = []
        for key, val in results[0].items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                numeric_cols.append(key)
        return numeric_cols
