from pydantic import BaseModel
from typing import List, Dict, Optional, Any


class InsightsRequest(BaseModel):
    query_intent: str          # "customer_analysis", "risk_analysis", etc.
    query_text: str            # "Top 10 customers by balance"
    results: List[Dict[str, Any]]  # Raw query results
    metadata: Dict[str, Any] = {}  # rows_returned, execution_time, tables, etc.


class StatisticalAnalysis(BaseModel):
    total_sum: Optional[float] = None
    average: Optional[float] = None
    median: Optional[float] = None
    std_dev: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    percentiles: Dict[str, float] = {}   # p25, p50, p75, p90, p99
    outliers: List[str] = []


class ContextData(BaseModel):
    historical_data: Dict[str, Any] = {}
    system_totals: Dict[str, Any] = {}
    regional_breakdown: Dict[str, Any] = {}
    segment_breakdown: Dict[str, Any] = {}


class Trend(BaseModel):
    metric: str          # "balance_growth", "customer_concentration"
    value: float         # 12.5 (for 12.5%)
    direction: str       # "up", "down", "stable"
    confidence: float    # 0.0-1.0


class InsightsResponse(BaseModel):
    status: str                          # "success", "error"
    summary: str                         # 2-3 sentence executive summary
    key_metrics: Dict[str, Any] = {}     # Important numbers
    trends: List[Trend] = []             # Identified trends
    anomalies: List[str] = []            # Notable outliers
    recommendations: List[str] = []      # Business recommendations
    confidence: float = 0.0             # 0.0-1.0 overall confidence
