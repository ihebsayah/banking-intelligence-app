from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime


class LineageRequest(BaseModel):
    query_id: str
    user_id: str
    source_tables: List[str]
    accessed_columns: List[str]


class LineageResponse(BaseModel):
    logged: bool
    records: int = 0
    error: Optional[str] = None


class GDPRReportRequest(BaseModel):
    user_id: str
    days: int = 90


class SOXReportRequest(BaseModel):
    days: int = 90


class ReportResponse(BaseModel):
    report_type: str
    regulation: str
    generated_at: str
    period: str
    data: Dict[str, Any] = {}
    stored: bool = False
    error: Optional[str] = None
