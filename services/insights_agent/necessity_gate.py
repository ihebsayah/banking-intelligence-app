"""Deterministic Insigs Necessity Gate — decides whether LLM interpretation adds value.

No LLM is used here. The gate answers: given intent + query text + verified
fact package, is generative natural-language synthesis genuinely useful?

- DIRECT/SIMPLE results -> deterministic response (NO LLM).
- COMPLEX/ANALYTICAL/explicitly requested -> LLM useful.
- The LLM (when enabled) still receives ONLY verified facts.
"""

import logging
import re
from typing import List

from models import (
    AnalyticalFactPackage,
    InsightsDecision,
    Provenance,
)

logger = logging.getLogger(__name__)

# ── Thresholds ───────────────────────────────────────────────────────────────
_LLM_THRESHOLD = 0.5

# Direct / simple intent categories -> deterministic
_SIMPLE_INTENTS = {"retrieve", "lookup", "count", "retrieval"}

# ── Explicit explanation signals (EN + FR) → user override ──────────────────
_EXPLICIT_SIGNALS = re.compile(
    r"\b("
    r"analy[sz]e|analysis|explain|interpret|interpretation|why|summar[yi]|summary"
    r"|insight|anomal|unusual|trend|compare|comparison|relationship|correlation"
    r"|what stands out|recommendation|risk|concentration|exposure"
    r"|[ée]carter|dynamique"
    r"|analyser|analyse|expliquer|interpr[ée]ter|pourquoi|r[ée]sumer|synth[èe]se"
    r"|tendance|anomalie|comparer|relation|corr[ée]lation|recommander|risque"
    r"|que faut-il retenir|attention"
    r")\b",
    re.IGNORECASE,
)


class NecessityGate:
    """Deterministic LLM-necessity decision."""

    def evaluate(
        self,
        query_intent: str,
        query_text: str,
        fact_package: AnalyticalFactPackage,
    ) -> InsightsDecision:
        intent = (query_intent or "").strip().lower()
        text = query_text or ""

        reason_codes: List[str] = []
        score = 0.0
        classification = self._classify(intent, text)

        explicit = bool(_EXPLICIT_SIGNALS.search(text))
        lower = text.lower()
        wants_trend = "trend" in lower or "tendance" in lower or classification == "TREND_ANALYSIS"
        wants_anomaly = (
            "anomal" in lower or "unusual" in lower
            or classification == "ANOMALY_ANALYSIS"
        )

        # 1. Classification baseline
        if classification in ("DIRECT_LOOKUP", "SIMPLE_AGGREGATION", "RANKING_TOP_N"):
            reason_codes.append(classification)

        # 2. Explicit user override — strongest signal
        if explicit:
            reason_codes.append("USER_REQUESTED_EXPLANATION")
            score += 0.6

        # 3. Fact-complexity signals (only strengthen; never reward emptiness)
        profile = fact_package.dataset_profile
        if len(profile.numeric_columns) >= 2:
            reason_codes.append("MULTI_DIMENSION_ANALYSIS")
            score += 0.2
        if fact_package.anomalies:
            reason_codes.append("ANOMALIES_REQUIRE_SYNTHESIS")
            score += 0.2
        if fact_package.correlations:
            reason_codes.append("CORRELATIONS_REQUIRE_INTERPRETATION")
            score += 0.2
        if fact_package.temporal_comparisons:
            reason_codes.append("TEMPORAL_ANALYSIS")
            score += 0.2
        if len(fact_package.recommendation_candidates) >= 2:
            reason_codes.append("MULTIPLE_RECOMMENDATION_CANDIDATES")
            score += 0.1

        # 4. Temporal/anomaly request without supporting facts → deterministic
        if wants_trend and not fact_package.temporal_comparisons:
            reason_codes.append("TREND_UNAVAILABLE")
            score -= 0.4
        if wants_anomaly and not fact_package.anomalies:
            reason_codes.append("NO_ANOMALIES")
            score -= 0.4

        # 5. Low evidence quality → safe deterministic response
        eq_score = fact_package.evidence_quality.score
        if eq_score < 0.4:
            reason_codes.append("LOW_EVIDENCE_QUALITY")
            score -= 0.3

        score = round(max(0.0, min(score, 1.0)), 2)
        use_llm = score >= _LLM_THRESHOLD and eq_score >= 0.3

        return InsightsDecision(
            use_llm=use_llm,
            reason_codes=list(dict.fromkeys(reason_codes)),
            complexity_score=score,
            formatter_mode="llm" if use_llm else "deterministic",
            classification=classification,
            provenance=Provenance(
                source="deterministic_calculation",
                method="necessity_gate",
            ),
        )

    @staticmethod
    def _classify(intent: str, text: str) -> str:
        """Map to a stable classification using existing intent categories.

        Reuses the orchestrator's intent categories; does NOT introduce a
        competing taxonomy. Falls back to text-scanning for intent families.
        """
        lower = text.lower()
        if intent in _SIMPLE_INTENTS:
            return "DIRECT_LOOKUP"
        if "trend" in intent or "tendance" in lower:
            return "TREND_ANALYSIS"
        if "anomal" in intent or "anomal" in lower or "unusual" in lower:
            return "ANOMALY_ANALYSIS"
        if "compare" in intent or "compar" in intent or "compar" in lower:
            return "COMPARATIVE_ANALYSIS"
        if "top " in lower or "top-" in lower or "ranking" in lower:
            return "RANKING_TOP_N"
        if intent.endswith("_analysis"):
            return "ANALYTICAL"
        return "DIRECT_LOOKUP"


class DeterministicFormatter:
    """Concise, factual, traceable responses for the deterministic path."""

    def format(
        self,
        fact_package: AnalyticalFactPackage,
        decision: InsightsDecision,
        metadata: dict,
    ) -> str:
        profile = fact_package.dataset_profile
        stats = fact_package.descriptive_stats
        n = profile.row_count

        if n == 0:
            return "No results matched the query."

        # Single-metric response (primary numeric column)
        if stats:
            s = stats[0]
            label = s.column.replace("_", " ").title()
            if decision.classification == "DIRECT_LOOKUP":
                return f"{label}: {self._num(s.sum)}."
            if decision.classification in ("SIMPLE_AGGREGATION", "ANALYTICAL"):
                return (
                    f"Total {label.lower()}: {self._num(s.sum)} across {s.count} "
                    f"records (mean {self._num(s.mean)})."
                )
            if decision.classification == "RANKING_TOP_N":
                top = fact_package.categorical_distributions[0] if fact_package.categorical_distributions else None
                if top and top.dominant_value:
                    return (
                        f"Top {label.lower()}: {top.dominant_value} "
                        f"({self._num(top.dominant_share * 100.0)}% share)."
                    )
                return f"Highest {label.lower()}: {self._num(s.max)}."

        # Count response
        if profile.categorical_columns and not stats:
            return f"{n} records matched the query."

        return f"{n} records matched the query."

    @staticmethod
    def _num(v) -> str:
        if v is None:
            return "N/A"
        if abs(v) >= 1000:
            return f"{v:,.0f}"
        return f"{v:,.2f}"
