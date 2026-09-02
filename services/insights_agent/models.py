from pydantic import BaseModel
from typing import List, Dict, Optional, Any


# ─────────────────────────────────────────────────────────────────────────────
# Trend (backward-compatible)
# Defined before InsightsResponse (which references it) so the forward
# reference resolves under older pydantic v2.x runtimes (e.g. 2.5.0 in Docker).
# ─────────────────────────────────────────────────────────────────────────────

class Trend(BaseModel):
    metric: str
    value: float
    direction: str  # "up", "down", "stable"
    confidence: float


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response (backward-compatible)
# ─────────────────────────────────────────────────────────────────────────────

class InsightsRequest(BaseModel):
    query_intent: str
    query_text: str
    results: List[Dict[str, Any]]
    metadata: Dict[str, Any] = {}


class InsightsResponse(BaseModel):
    status: str
    summary: str
    key_metrics: Dict[str, Any] = {}
    trends: List["Trend"] = []
    anomalies: List[str] = []
    recommendations: List[str] = []
    confidence: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Provenance
# ─────────────────────────────────────────────────────────────────────────────

class Provenance(BaseModel):
    source: str  # "execution_result" | "deterministic_calculation" | "query_metadata"
    column: Optional[str] = None
    method: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Dataset Profile
# ─────────────────────────────────────────────────────────────────────────────

class DatasetProfile(BaseModel):
    row_count: int = 0
    columns: List[str] = []
    numeric_columns: List[str] = []
    categorical_columns: List[str] = []
    temporal_columns: List[str] = []
    identifier_columns: List[str] = []
    null_counts: Dict[str, int] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Per-Column Statistics
# ─────────────────────────────────────────────────────────────────────────────

class DescriptiveStats(BaseModel):
    column: str
    count: int = 0
    null_count: int = 0
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std_dev: Optional[float] = None
    p25: Optional[float] = None
    p75: Optional[float] = None
    p90: Optional[float] = None
    p99: Optional[float] = None
    sum: Optional[float] = None
    provenance: Provenance


class CategoricalDistribution(BaseModel):
    column: str
    unique_count: int = 0
    dominant_value: Optional[str] = None
    dominant_share: Optional[float] = None
    value_counts: Dict[str, int] = {}
    provenance: Provenance


# ─────────────────────────────────────────────────────────────────────────────
# Anomalies
# ─────────────────────────────────────────────────────────────────────────────

class AnomalyFact(BaseModel):
    column: str
    observed_value: float
    mean: float
    std_dev: float
    deviation: float
    severity: str  # "moderate" (>2σ) | "extreme" (>3σ)
    provenance: Provenance


# ─────────────────────────────────────────────────────────────────────────────
# Correlations
# ─────────────────────────────────────────────────────────────────────────────

class CorrelationFact(BaseModel):
    column_a: str
    column_b: str
    coefficient: float
    sample_size: int
    provenance: Provenance


# ─────────────────────────────────────────────────────────────────────────────
# Temporal Analysis
# ─────────────────────────────────────────────────────────────────────────────

class TemporalComparison(BaseModel):
    column: str
    earliest_period: Optional[str] = None
    latest_period: Optional[str] = None
    previous_value: Optional[float] = None
    current_value: Optional[float] = None
    absolute_change: Optional[float] = None
    percentage_change: Optional[float] = None
    provenance: Provenance


# ─────────────────────────────────────────────────────────────────────────────
# Recommendation Candidates
# ─────────────────────────────────────────────────────────────────────────────

class RecommendationCandidate(BaseModel):
    rule: str
    message: str
    evidence_column: Optional[str] = None
    evidence_value: Optional[float] = None
    severity: str = "info"  # "info" | "warning" | "critical"


# ─────────────────────────────────────────────────────────────────────────────
# Evidence Quality (replaces hardcoded confidence)
# ─────────────────────────────────────────────────────────────────────────────

class EvidenceQuality(BaseModel):
    """Measurable signals about analytical evidence quality.

    This is NOT an LLM-confidence score and NOT a probability of correctness.
    It measures how complete, parseable, and adequate the result data is for
    deterministic analysis. It deliberately does NOT reward the presence of
    interesting patterns (anomalies, correlations, temporal changes), because
    the absence of patterns does not mean poor data quality.

    Interpret this as: "analytical evidence quality".
    """
    row_count_adequate: bool = False  # >= 5 rows
    has_numeric_data: bool = False
    completeness_ratio: float = 0.0  # non-null values / total cells
    numeric_column_count: int = 0
    categorical_column_count: int = 0
    temporal_column_count: int = 0
    parseability_ratio: float = 0.0  # usable (numeric+categorical) cells / non-null cells
    consistency_ratio: float = 0.0  # columns typed identically across rows
    score: float = 0.0  # 0.0-1.0, computed from the quality dimensions above


# ─────────────────────────────────────────────────────────────────────────────
# Necessity Gate
# ─────────────────────────────────────────────────────────────────────────────

class InsightsDecision(BaseModel):
    """Deterministic decision about whether LLM interpretation is useful."""
    use_llm: bool = False
    reason_codes: List[str] = []
    complexity_score: float = 0.0  # 0.0-1.0, interpretable evidence-weighted
    formatter_mode: str = "deterministic"  # "deterministic" | "llm"
    classification: str = "DIRECT_LOOKUP"  # stable class for audit
    provenance: Provenance


# ─────────────────────────────────────────────────────────────────────────────
# Grounded LLM Output Contract (STEP 4)
# ─────────────────────────────────────────────────────────────────────────────

class LLMObservation(BaseModel):
    text: str
    fact_ids: List[str] = []


class LLMRecommendation(BaseModel):
    text: str
    fact_ids: List[str] = []


class LLMInsightOutput(BaseModel):
    summary: str
    key_observations: List[LLMObservation] = []
    recommendations: List[LLMRecommendation] = []
    limitations: List[str] = []


class GenerationMetadata(BaseModel):
    generation_mode: str = "deterministic"  # deterministic | llm | llm_fallback
    model_name: Optional[str] = None
    latency_ms: Optional[int] = None
    fallback_reason: Optional[str] = None
    gate_reason_codes: List[str] = []


class InterpretationResult(BaseModel):
    """Internal result of the grounded interpretation step."""
    summary: str
    key_observations: List[LLMObservation] = []
    recommendations: List[LLMRecommendation] = []
    limitations: List[str] = []
    metadata: GenerationMetadata = GenerationMetadata()


# ─────────────────────────────────────────────────────────────────────────────
# Verified Analytical Fact Package (root internal representation)
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticalFactPackage(BaseModel):
    """Complete deterministic fact package for a query result set.

    Every value is computed from actual execution results or query metadata.
    No synthetic or hardcoded values are permitted.
    """
    query_intent: str = ""
    query_text: str = ""
    dataset_profile: DatasetProfile
    descriptive_stats: List[DescriptiveStats] = []
    categorical_distributions: List[CategoricalDistribution] = []
    anomalies: List[AnomalyFact] = []
    correlations: List[CorrelationFact] = []
    temporal_comparisons: List[TemporalComparison] = []
    recommendation_candidates: List[RecommendationCandidate] = []
    evidence_quality: EvidenceQuality = EvidenceQuality()


# ─────────────────────────────────────────────────────────────────────────────
# Legacy models (kept for backward compatibility)
# ─────────────────────────────────────────────────────────────────────────────

class StatisticalAnalysis(BaseModel):
    total_sum: Optional[float] = None
    average: Optional[float] = None
    median: Optional[float] = None
    std_dev: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    percentiles: Dict[str, float] = {}
    outliers: List[str] = []


class ContextData(BaseModel):
    historical_data: Dict[str, Any] = {}
    system_totals: Dict[str, Any] = {}
    regional_breakdown: Dict[str, Any] = {}
    segment_breakdown: Dict[str, Any] = {}
