import logging
from typing import List, Dict, Any, Optional

from statistical_analyzer import StatisticalAnalyzer
from context_gatherer import ContextGatherer
from mistral_integrator import MistralIntegrator
from necessity_gate import NecessityGate, DeterministicFormatter
from models import (
    InsightsRequest,
    InsightsResponse,
    AnalyticalFactPackage,
    DatasetProfile,
    DescriptiveStats,
    CategoricalDistribution,
    AnomalyFact,
    CorrelationFact,
    TemporalComparison,
    RecommendationCandidate,
    EvidenceQuality,
    InterpretationResult,
    Provenance,
)
from config import Settings

logger = logging.getLogger(__name__)


class InsightsGenerator:
    """Orchestrates deterministic fact package → optional LLM summary.

    v2.0: Every number shown to users comes from actual query results
    or documented deterministic calculations. No synthetic/hardcoded values.
    LLM (Mistral) may explain facts; LLM must NOT create facts.
    """

    def __init__(self, config: Settings):
        self.config = config
        self.analyzer = StatisticalAnalyzer()
        self.context_gatherer = ContextGatherer(config)
        self.mistral = MistralIntegrator(config)
        self.gate = NecessityGate()
        self.formatter = DeterministicFormatter()

    # ─────────────────────────────────────────────────────────────────────
    # Public
    # ─────────────────────────────────────────────────────────────────────

    async def generate(self, request: InsightsRequest) -> InsightsResponse:
        try:
            logger.info(f"Generating insights for intent={request.query_intent}")

            # No-data guard: never fabricate insights from empty results
            if not request.results:
                return InsightsResponse(
                    status="no_data",
                    summary=(
                        "Aucun résultat n'a été retourné pour cette requête. "
                        "Vérifiez les filtres (nom d'agence, période, type de transaction) "
                        "et réessayez."
                    ),
                    key_metrics={"total_count": 0},
                    trends=[],
                    anomalies=[],
                    recommendations=[],
                    confidence=0.0,
                )

            # Step 1 — Build verified analytical fact package
            fact_package = self._build_fact_package(request)

            # Step 2 — Context from metadata (no DB queries)
            context = await self.context_gatherer.gather_context(
                request.query_intent,
                request.metadata,
            )

            # Step 3 — Necessity gate: decide deterministically whether the
            # result benefits from LLM interpretation. NO LLM decides this.
            decision = self.gate.evaluate(
                request.query_intent,
                request.query_text,
                fact_package,
            )
            logger.info(
                f"Gate: use_llm={decision.use_llm} "
                f"mode={decision.formatter_mode} "
                f"scope={decision.complexity_score} "
                f"reasons={decision.reason_codes}"
            )

            # Step 4 — Build deterministic response components (always used)
            evidence_quality = fact_package.evidence_quality
            deterministic_recs = [
                rc.message for rc in fact_package.recommendation_candidates
            ]
            anomaly_strings = [
                f"{a.column}={a.observed_value:.2f} "
                f"({a.severity}, {a.deviation}σ from mean {a.mean:.2f})"
                for a in fact_package.anomalies
            ]
            key_metrics = self._build_key_metrics(fact_package)
            trends = self._build_trends(fact_package)

            # Step 5 — Deterministic summary from verified facts (fast path)
            summary = self.formatter.format(
                fact_package, decision, request.metadata
            )
            recommendations = list(deterministic_recs)
            generation_mode = "deterministic"

            # Step 6 — Grounded LLM interpretation ONLY when the gate says useful
            # AND the feature flag is enabled. Any failure falls back to the
            # deterministic summary; the LLM is optional for correctness.
            if decision.use_llm and self.config.ENABLE_LLM_INSIGHTS:
                result = self.mistral.interpret(
                    fact_package,
                    request.query_intent,
                    request.query_text,
                    decision.reason_codes,
                )
                if result.metadata.generation_mode == "llm":
                    summary = result.summary
                    generation_mode = "llm"
                    if result.recommendations:
                        recommendations = [r.text for r in result.recommendations]
                    elif not deterministic_recs:
                        recommendations = []

            return InsightsResponse(
                status="success",
                summary=summary,
                key_metrics={**key_metrics, "generation_mode": generation_mode},
                trends=trends,
                anomalies=anomaly_strings,
                recommendations=recommendations,
                confidence=evidence_quality.score,
            )

        except Exception as exc:
            logger.error(f"InsightsGenerator.generate failed: {exc}")
            return InsightsResponse(
                status="error",
                summary=f"Insights generation error: {exc}",
                confidence=0.0,
            )

    # ─────────────────────────────────────────────────────────────────────
    # Fact Package Builder
    # ─────────────────────────────────────────────────────────────────────

    def _build_fact_package(
        self, request: InsightsRequest
    ) -> AnalyticalFactPackage:
        """Build the complete verified analytical fact package."""
        results = request.results

        # 1. Column classification
        dataset_profile = self.analyzer.classify_columns(results)

        # 2. Per-column descriptive statistics
        descriptive_stats = self.analyzer.compute_descriptive_stats(
            results, dataset_profile.numeric_columns
        )

        # 3. Categorical distributions
        categorical_distributions = self.analyzer.compute_categorical_distributions(
            results, dataset_profile.categorical_columns
        )

        # 4. Anomaly detection
        anomalies = self.analyzer.detect_anomalies(
            results, dataset_profile.numeric_columns
        )

        # 5. Correlations
        correlations = self.analyzer.compute_correlations(
            results, dataset_profile.numeric_columns
        )

        # 6. Temporal comparisons
        temporal_comparisons = self.analyzer.compute_temporal_comparisons(
            results,
            dataset_profile.temporal_columns,
            dataset_profile.numeric_columns,
        )

        # 7. Recommendation candidates (evidence-backed)
        recommendation_candidates = self._generate_recommendation_candidates(
            dataset_profile, descriptive_stats, anomalies,
            correlations, temporal_comparisons,
        )

        # 8. Evidence quality score (data-quality dimensions only)
        evidence_quality = self._compute_evidence_quality(
            dataset_profile, results,
        )

        return AnalyticalFactPackage(
            query_intent=request.query_intent,
            query_text=request.query_text,
            dataset_profile=dataset_profile,
            descriptive_stats=descriptive_stats,
            categorical_distributions=categorical_distributions,
            anomalies=anomalies,
            correlations=correlations,
            temporal_comparisons=temporal_comparisons,
            recommendation_candidates=recommendation_candidates,
            evidence_quality=evidence_quality,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Key Metrics
    # ─────────────────────────────────────────────────────────────────────

    def _build_key_metrics(
        self, fact: AnalyticalFactPackage
    ) -> Dict[str, Any]:
        """Build key_metrics dict entirely from the fact package."""
        metrics: Dict[str, Any] = {
            "total_count": fact.dataset_profile.row_count,
            "numeric_columns": len(fact.dataset_profile.numeric_columns),
            "categorical_columns": len(fact.dataset_profile.categorical_columns),
            "anomaly_count": len(fact.anomalies),
            "correlation_pairs": len(fact.correlations),
        }

        # Add primary column stats (highest-priority numeric)
        if fact.descriptive_stats:
            primary = fact.descriptive_stats[0]
            metrics["primary_column"] = primary.column
            metrics["total_sum"] = primary.sum
            metrics["average"] = primary.mean
            metrics["median"] = primary.median
            metrics["std_dev"] = primary.std_dev

        # Add top categorical dominant value
        if fact.categorical_distributions:
            top_cat = fact.categorical_distributions[0]
            metrics[f"top_{top_cat.column}"] = top_cat.dominant_value
            metrics[f"top_{top_cat.column}_share"] = top_cat.dominant_share

        # Add strongest correlation
        if fact.correlations:
            strongest = max(fact.correlations, key=lambda c: abs(c.coefficient))
            metrics["strongest_correlation"] = {
                "columns": f"{strongest.column_a} ↔ {strongest.column_b}",
                "coefficient": strongest.coefficient,
            }

        # Add temporal change
        if fact.temporal_comparisons:
            for tc in fact.temporal_comparisons:
                if tc.percentage_change is not None:
                    metrics[f"{tc.column}_period_change_pct"] = tc.percentage_change

        return metrics

    # ─────────────────────────────────────────────────────────────────────
    # Trends
    # ─────────────────────────────────────────────────────────────────────

    def _build_trends(
        self, fact: AnalyticalFactPackage
    ) -> List[Dict[str, Any]]:
        """Convert temporal comparisons and correlations into trend objects."""
        trends = []

        for tc in fact.temporal_comparisons:
            if tc.percentage_change is None:
                continue
            pct = tc.percentage_change
            direction = "up" if pct > 1 else ("down" if pct < -1 else "stable")
            # Evidence quality score = data completeness ratio
            conf = fact.evidence_quality.score
            trends.append({
                "metric": f"{tc.column}_period_change",
                "value": pct,
                "direction": direction,
                "confidence": conf,
            })

        for corr in fact.correlations:
            if abs(corr.coefficient) >= 0.7:
                direction = "up" if corr.coefficient > 0 else "down"
                trends.append({
                    "metric": f"{corr.column_a}_vs_{corr.column_b}",
                    "value": corr.coefficient,
                    "direction": direction,
                    "confidence": fact.evidence_quality.score,
                })

        return trends

    # ─────────────────────────────────────────────────────────────────────
    # Evidence Quality
    # ─────────────────────────────────────────────────────────────────────

    def _compute_evidence_quality(
        self,
        profile: DatasetProfile,
        results: List[Dict],
    ) -> EvidenceQuality:
        """Compute analytical evidence quality (0.0-1.0).

        Measures data QUALITY only. It deliberately does NOT reward the
        presence of anomalies, correlations, or temporal changes.

        Formula (documented weights):
        - non-empty result set                             +0.15
        - sample size adequate (>= 5 rows)                 +0.15
        - completeness ratio (non-null / total cells)      x0.30
        - has usable data (numeric or categorical)         +0.10
        - parseability (typed cells / non-null cells)      x0.15
        - consistency (columns with a stable single type)  x0.15
        Score is clamped to 0.0-1.0. It is NOT a probability of correctness.
        """
        if profile.row_count == 0 or not profile.columns:
            return EvidenceQuality()

        total_cells = profile.row_count * len(profile.columns)
        non_null = sum(
            profile.row_count - v
            for v in profile.null_counts.values()
        )
        completeness = round(non_null / total_cells, 4) if total_cells else 0.0

        # Parseability: fraction of non-null cells that classify as usable
        usable_cells = sum(
            (profile.row_count - v)
            for c, v in profile.null_counts.items()
            if c in profile.numeric_columns or c in profile.categorical_columns
        )
        parseability = round(usable_cells / non_null, 4) if non_null else 0.0

        # Consistency: columns where every non-null row shares its expected type
        typed_cols = sum(
            1 for c in profile.columns
            if c in profile.numeric_columns or c in profile.categorical_columns
            or c in profile.temporal_columns
        )
        consistency = round(typed_cols / len(profile.columns), 4)

        score = 0.0
        score += 0.15  # non-empty
        if profile.row_count >= 5:
            score += 0.15
        score += completeness * 0.30
        if profile.numeric_columns or profile.categorical_columns:
            score += 0.10
        score += parseability * 0.15
        score += consistency * 0.15

        return EvidenceQuality(
            row_count_adequate=profile.row_count >= 5,
            has_numeric_data=bool(profile.numeric_columns),
            completeness_ratio=completeness,
            numeric_column_count=len(profile.numeric_columns),
            categorical_column_count=len(profile.categorical_columns),
            temporal_column_count=len(profile.temporal_columns),
            parseability_ratio=parseability,
            consistency_ratio=consistency,
            score=round(min(score, 1.0), 2),
        )

    # ─────────────────────────────────────────────────────────────────────
    # Recommendation Candidates (evidence-backed only)
    # ─────────────────────────────────────────────────────────────────────

    def _generate_recommendation_candidates(
        self,
        profile: DatasetProfile,
        stats: List[DescriptiveStats],
        anomalies: List[AnomalyFact],
        correlations: List[CorrelationFact],
        temporal: List[TemporalComparison],
    ) -> List[RecommendationCandidate]:
        """Generate recommendation candidates grounded in actual evidence.

        Only produces recommendations when there is measurable evidence
        to support them. No generic/static recommendations.
        """
        candidates = []

        # Rule 1: Anomaly concentration
        if anomalies:
            extreme = [a for a in anomalies if a.severity == "extreme"]
            cols = list({a.column for a in anomalies})
            if extreme:
                candidates.append(RecommendationCandidate(
                    rule="anomaly_concentration",
                    message=(
                        f"{len(extreme)} extreme anomalies detected in "
                        f"{', '.join(cols)} — investigate data quality or "
                        f"underlying business conditions."
                    ),
                    evidence_column=cols[0] if cols else None,
                    evidence_value=float(len(extreme)),
                    severity="warning",
                ))
            else:
                candidates.append(RecommendationCandidate(
                    rule="moderate_anomalies",
                    message=(
                        f"{len(anomalies)} moderate anomalies in "
                        f"{', '.join(cols)} — review for potential issues."
                    ),
                    evidence_column=cols[0] if cols else None,
                    evidence_value=float(len(anomalies)),
                    severity="info",
                ))

        # Rule 2: Strong correlation
        for corr in correlations:
            if abs(corr.coefficient) >= 0.7:
                direction = "positive" if corr.coefficient > 0 else "negative"
                candidates.append(RecommendationCandidate(
                    rule="strong_correlation",
                    message=(
                        f"Strong {direction} correlation ({corr.coefficient:.2f}) "
                        f"between {corr.column_a} and {corr.column_b} — "
                        f"consider joint analysis or causal investigation."
                    ),
                    evidence_column=f"{corr.column_a},{corr.column_b}",
                    evidence_value=corr.coefficient,
                    severity="info",
                ))

        # Rule 3: Large temporal change
        for tc in temporal:
            if tc.percentage_change is not None and abs(tc.percentage_change) > 20:
                direction = "increase" if tc.percentage_change > 0 else "decrease"
                candidates.append(RecommendationCandidate(
                    rule="large_temporal_change",
                    message=(
                        f"{tc.column} shows {abs(tc.percentage_change):.1f}% "
                        f"{direction} between periods — "
                        f"investigate drivers of change."
                    ),
                    evidence_column=tc.column,
                    evidence_value=tc.percentage_change,
                    severity="warning" if abs(tc.percentage_change) > 50 else "info",
                ))

        # Rule 4: Skewed distribution (mean vs median divergence)
        for s in stats:
            if s.mean and s.median:
                skew = abs(s.mean - s.median) / s.std_dev if s.std_dev else 0
                if skew > 0.5:
                    candidates.append(RecommendationCandidate(
                        rule="skewed_distribution",
                        message=(
                            f"{s.column} shows skewed distribution "
                            f"(mean={s.mean:.2f}, median={s.median:.2f}) — "
                            f"consider using median for reporting."
                        ),
                        evidence_column=s.column,
                        evidence_value=skew,
                        severity="info",
                    ))

        return candidates
