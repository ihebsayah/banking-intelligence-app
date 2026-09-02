import re
import math
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

from models import (
    DatasetProfile,
    DescriptiveStats,
    CategoricalDistribution,
    AnomalyFact,
    CorrelationFact,
    TemporalComparison,
    Provenance,
)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_TEMPORAL_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),                    # 2024-01-15
    re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"),    # 2024-01-15T10:30
    re.compile(r"^\d{4}/\d{2}/\d{2}$"),                    # 2024/01/15
    re.compile(r"^\d{2}/\d{2}/\d{4}$"),                    # 01/15/2024
    re.compile(r"^\d{4}-\d{2}$"),                          # 2024-01
]

_ID_PATTERNS = [
    re.compile(r"^[A-Za-z]+_?\d+$"),       # abc_123
    re.compile(r"^\d+$"),                    # pure numeric id
    re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}"),  # uuid prefix
]

_ANOMALY_THRESHOLD_MODERATE = 2.0
_ANOMALY_THRESHOLD_EXTREME = 3.0
_MIN_ROWS_FOR_STATS = 1  # a lone value is still a valid lookup; std guards at n>=2
_MIN_ROWS_FOR_CORRELATION = 5


class StatisticalAnalyzer:
    """Deterministic analysis engine — no LLM calls, no hardcoded values.

    Produces per-column descriptive stats, categorical distributions,
    pairwise correlations, anomaly detection, and temporal comparisons.
    Every output includes a Provenance record.
    """

    # ─────────────────────────────────────────────────────────────────────
    # Column classification
    # ─────────────────────────────────────────────────────────────────────

    def classify_columns(
        self, results: List[Dict[str, Any]]
    ) -> DatasetProfile:
        """Classify every column as numeric, categorical, temporal, or identifier."""
        if not results:
            return DatasetProfile()

        all_columns = list(results[0].keys())
        numeric_cols, categorical_cols, temporal_cols, id_cols = [], [], [], []

        for col in all_columns:
            values = [r.get(col) for r in results if r.get(col) is not None]
            if not values:
                categorical_cols.append(col)
                continue

            if self._is_temporal(values):
                temporal_cols.append(col)
            elif self._is_identifier(values):
                id_cols.append(col)
            elif self._is_numeric(values):
                numeric_cols.append(col)
            else:
                categorical_cols.append(col)

        # Null counts per column
        null_counts = {}
        for col in all_columns:
            null_counts[col] = sum(1 for r in results if r.get(col) is None)

        return DatasetProfile(
            row_count=len(results),
            columns=all_columns,
            numeric_columns=numeric_cols,
            categorical_columns=categorical_cols,
            temporal_columns=temporal_cols,
            identifier_columns=id_cols,
            null_counts=null_counts,
        )

    def _is_temporal(self, values: List[Any]) -> bool:
        if not values:
            return False
        sample = [str(v) for v in values[:20] if v is not None]
        if not sample:
            return False
        matches = sum(
            1 for s in sample
            if any(p.match(s.strip()) for p in _TEMPORAL_PATTERNS)
        )
        return matches / len(sample) >= 0.6

    def _is_identifier(self, values: List[Any]) -> bool:
        if not values:
            return False
        sample = [str(v) for v in values[:20] if v is not None]
        if not sample:
            return False
        # Identifiers: high cardinality + matches ID patterns
        unique_ratio = len(set(sample)) / len(sample)
        if unique_ratio < 0.8:
            return False
        matches = sum(
            1 for s in sample
            if any(p.match(s.strip()) for p in _ID_PATTERNS)
        )
        return matches / len(sample) >= 0.6

    def _is_numeric(self, values: List[Any]) -> bool:
        if not values:
            return False
        sample = [v for v in values[:20] if v is not None]
        if not sample:
            return False
        numeric_count = 0
        for v in sample:
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                numeric_count += 1
            elif isinstance(v, str) and v.strip():
                try:
                    float(v)
                    # Exclude dates/times that happen to parse
                    if "-" in v and ":" not in v:
                        parts = v.split("-")
                        if len(parts) == 3 and all(p.isdigit() for p in parts):
                            continue
                    numeric_count += 1
                except ValueError:
                    pass
        return numeric_count / len(sample) >= 0.8

    # ─────────────────────────────────────────────────────────────────────
    # Descriptive statistics per numeric column
    # ─────────────────────────────────────────────────────────────────────

    def compute_descriptive_stats(
        self,
        results: List[Dict[str, Any]],
        numeric_columns: List[str],
    ) -> List[DescriptiveStats]:
        """Compute per-column descriptive statistics with provenance."""
        stats = []
        for col in numeric_columns:
            values = self._extract_floats(results, col)
            if not values or len(values) < _MIN_ROWS_FOR_STATS:
                continue
            arr = np.array(values, dtype=float)
            stats.append(DescriptiveStats(
                column=col,
                count=len(values),
                null_count=sum(1 for r in results if r.get(col) is None),
                min=float(np.min(arr)),
                max=float(np.max(arr)),
                mean=float(np.mean(arr)),
                median=float(np.median(arr)),
                std_dev=float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
                p25=float(np.percentile(arr, 25)),
                p75=float(np.percentile(arr, 75)),
                p90=float(np.percentile(arr, 90)),
                p99=float(np.percentile(arr, 99)),
                sum=float(np.sum(arr)),
                provenance=Provenance(
                    source="deterministic_calculation",
                    column=col,
                    method="numpy_descriptive_statistics",
                ),
            ))
        return stats

    # ─────────────────────────────────────────────────────────────────────
    # Categorical distributions
    # ─────────────────────────────────────────────────────────────────────

    def compute_categorical_distributions(
        self,
        results: List[Dict[str, Any]],
        categorical_columns: List[str],
    ) -> List[CategoricalDistribution]:
        """Count distinct values per categorical column."""
        dists = []
        for col in categorical_columns:
            counts: Dict[str, int] = {}
            for r in results:
                val = r.get(col)
                if val is not None:
                    key = str(val)
                    counts[key] = counts.get(key, 0) + 1
            if not counts:
                continue
            total = sum(counts.values())
            dominant = max(counts, key=counts.get)
            dists.append(CategoricalDistribution(
                column=col,
                unique_count=len(counts),
                dominant_value=dominant,
                dominant_share=round(counts[dominant] / total, 4) if total else None,
                value_counts=dict(sorted(counts.items(), key=lambda x: -x[1])),
                provenance=Provenance(
                    source="execution_result",
                    column=col,
                    method="count_distinct",
                ),
            ))
        return dists

    # ─────────────────────────────────────────────────────────────────────
    # Anomaly detection (z-score, no LLM)
    # ─────────────────────────────────────────────────────────────────────

    def detect_anomalies(
        self,
        results: List[Dict[str, Any]],
        numeric_columns: List[str],
    ) -> List[AnomalyFact]:
        """Flag values exceeding 2σ from column mean."""
        anomalies = []
        for col in numeric_columns:
            values = self._extract_floats(results, col)
            if len(values) < _MIN_ROWS_FOR_STATS:
                continue
            arr = np.array(values, dtype=float)
            mean = float(np.mean(arr))
            std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
            if std == 0:
                continue
            for v in values:
                dev = abs(v - mean) / std
                if dev > _ANOMALY_THRESHOLD_MODERATE:
                    anomalies.append(AnomalyFact(
                        column=col,
                        observed_value=v,
                        mean=mean,
                        std_dev=std,
                        deviation=round(dev, 2),
                        severity="extreme" if dev > _ANOMALY_THRESHOLD_EXTREME else "moderate",
                        provenance=Provenance(
                            source="deterministic_calculation",
                            column=col,
                            method="z_score_anomaly_detection",
                        ),
                    ))
        return anomalies

    # ─────────────────────────────────────────────────────────────────────
    # Pairwise correlations (Pearson)
    # ─────────────────────────────────────────────────────────────────────

    def compute_correlations(
        self,
        results: List[Dict[str, Any]],
        numeric_columns: List[str],
    ) -> List[CorrelationFact]:
        """Compute Pearson r for all numeric column pairs with enough data."""
        if len(numeric_columns) < 2:
            return []
        # Pre-extract aligned value lists
        column_values: Dict[str, List[float]] = {}
        for col in numeric_columns:
            column_values[col] = self._extract_floats(results, col)

        correlations = []
        for i, a in enumerate(numeric_columns):
            for b in numeric_columns[i + 1:]:
                a_vals = column_values[a]
                b_vals = column_values[b]
                # Align on non-null pairs
                pairs = [(x, y) for x, y in zip(a_vals, b_vals)]
                if len(pairs) < _MIN_ROWS_FOR_CORRELATION:
                    continue
                arr_a = np.array([p[0] for p in pairs], dtype=float)
                arr_b = np.array([p[1] for p in pairs], dtype=float)
                # Skip if zero variance
                if np.std(arr_a) == 0 or np.std(arr_b) == 0:
                    continue
                r = float(np.corrcoef(arr_a, arr_b)[0, 1])
                if math.isnan(r):
                    continue
                correlations.append(CorrelationFact(
                    column_a=a,
                    column_b=b,
                    coefficient=round(r, 4),
                    sample_size=len(pairs),
                    provenance=Provenance(
                        source="deterministic_calculation",
                        column=f"{a},{b}",
                        method="pearson_correlation",
                    ),
                ))
        return correlations

    # ─────────────────────────────────────────────────────────────────────
    # Temporal comparison (first vs last period)
    # ─────────────────────────────────────────────────────────────────────

    def compute_temporal_comparisons(
        self,
        results: List[Dict[str, Any]],
        temporal_columns: List[str],
        numeric_columns: List[str],
    ) -> List[TemporalComparison]:
        """Compare the latest complete period vs its preceding period.

        Granularity is inferred from actual data span: weekly/daily within a
        month's span, monthly within ~a year, otherwise yearly. A comparison is
        only produced when both periods have sufficient observations and dates
        parse reliably. A row-half split is never treated as period-over-period.
        """
        if not temporal_columns or not numeric_columns:
            return []

        time_col = temporal_columns[0]
        dated = []
        for r in results:
            raw = r.get(time_col)
            parsed = self._parse_date(raw)
            if parsed is not None:
                dated.append((parsed, r))
        if len(dated) < 2:
            return []

        # Bucket rows into chronologically ordered periods with inferred granularity
        period_key = self._infer_period_key(dated)
        buckets: Dict[str, List[dict]] = {}
        for parsed, row in sorted(dated, key=lambda t: t[0]):
            key = period_key(parsed)
            buckets.setdefault(key, []).append(row)
        keys = sorted(buckets.keys())
        if len(keys) < 2:
            return []

        # Latest complete period vs the immediately preceding one
        latest, prev = keys[-1], keys[-2]
        min_obs = 1

        comparisons = []
        for col in numeric_columns:
            prev_vals = self._extract_floats(buckets[prev], col)
            curr_vals = self._extract_floats(buckets[latest], col)
            if len(prev_vals) < min_obs or len(curr_vals) < min_obs:
                continue
            before = float(np.mean(prev_vals))
            now = float(np.mean(curr_vals))
            abs_change = now - before
            pct_change = (abs_change / before * 100) if before != 0 else None
            comparisons.append(TemporalComparison(
                column=col,
                earliest_period=prev,
                latest_period=latest,
                previous_value=round(before, 4),
                current_value=round(now, 4),
                absolute_change=round(abs_change, 4),
                percentage_change=round(pct_change, 2) if pct_change is not None else None,
                provenance=Provenance(
                    source="deterministic_calculation",
                    column=col,
                    method="period_over_period_grouped",
                ),
            ))
        return comparisons

    @staticmethod
    def _parse_date(value) -> Optional[Any]:
        """Parse a value into a datetime, or None if not a reliable date."""
        if value is None:
            return None
        import datetime as _dt
        s = str(value).strip()
        fmts = [
            "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M",
        ]
        for fmt in fmts:
            try:
                return _dt.datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _infer_period_key(dated):
        """Choose daily/monthly/yearly bucketing from data distribution.

        - crosses multiple years  -> yearly
        - multiple months with multiple days within them -> monthly
        - otherwise               -> daily
        """
        dates = [d[0] for d in dated]
        days = {d.date() for d in dates}
        months = {(d.year, d.month) for d in dates}
        years = {d.year for d in dates}
        if len(years) > 1:
            return lambda dt: dt.strftime("%Y")
        if len(months) >= 2 and len(days) > len(months):
            return lambda dt: dt.strftime("%Y-%m")
        return lambda dt: dt.strftime("%Y-%m-%d")

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    def _extract_floats(
        self, results: List[Dict], col: str
    ) -> List[float]:
        """Extract float values from a column, skipping nulls/non-numeric."""
        values = []
        for r in results:
            val = r.get(col)
            if val is None:
                continue
            if isinstance(val, bool):
                continue
            try:
                values.append(float(val))
            except (ValueError, TypeError):
                continue
        return values
