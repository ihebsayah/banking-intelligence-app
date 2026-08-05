"""Customer 360 typed DTO contract (Phase 3A.2).

Authoritative data comes from the main banking DB (banking_dev); workbench
links come from the integration DB (banking_integration). Monetary values are
serialised as exact strings (Decimal -> str) so no precision is lost across
the JSON boundary.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CustomerIdentity(BaseModel):
    customer_id: str
    name: Optional[str] = None
    customer_type: Optional[str] = None
    segment: Optional[str] = None
    status: Optional[str] = None
    onboarding_date: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    employment_status: Optional[str] = None
    employer_name: Optional[str] = None
    # Sensitive — masked unless the caller holds customer:read_pii
    national_id: Optional[str] = None
    passport_number: Optional[str] = None
    tax_id: Optional[str] = None
    annual_income: Optional[str] = None
    net_worth_band: Optional[str] = None
    pep: Optional[bool] = None


class Relationship(BaseModel):
    primary_branch: Optional[str] = None
    region: Optional[str] = None
    relationship_managers: List[Dict[str, Any]] = Field(default_factory=list)
    relationship_duration_days: Optional[int] = None
    products_held: int = 0


class AccountSummary(BaseModel):
    account_id: str
    account_type: Optional[str] = None
    status: Optional[str] = None
    balance: Optional[str] = None
    available_balance: Optional[str] = None
    currency: Optional[str] = None
    branch: Optional[str] = None
    opened_at: Optional[str] = None


class LoanSummary(BaseModel):
    loan_id: str
    loan_type: Optional[str] = None
    product: Optional[str] = None
    principal: Optional[str] = None
    outstanding_balance: Optional[str] = None
    currency: Optional[str] = None
    interest_rate: Optional[str] = None
    maturity_date: Optional[str] = None
    status: Optional[str] = None
    days_past_due: Optional[int] = None


class FinancialSummary(BaseModel):
    account_count: int = 0
    active_account_count: int = 0
    total_balance_by_currency: Dict[str, str] = Field(default_factory=dict)
    available_balance_by_currency: Dict[str, str] = Field(default_factory=dict)
    loan_count: int = 0
    total_outstanding_loans_by_currency: Dict[str, str] = Field(default_factory=dict)
    maximum_days_past_due: Optional[int] = None
    recent_transaction_count: int = 0
    recent_transaction_volume_by_currency: Dict[str, str] = Field(default_factory=dict)


class TransactionSummary(BaseModel):
    d30_inbound_count: int = 0
    d30_inbound_amount: Dict[str, str] = Field(default_factory=dict)
    d30_outbound_count: int = 0
    d30_outbound_amount: Dict[str, str] = Field(default_factory=dict)
    d30_total_count: int = 0
    d30_total_amount: Dict[str, str] = Field(default_factory=dict)
    d90_total_count: int = 0
    d90_total_amount: Dict[str, str] = Field(default_factory=dict)
    latest_transaction_date: Optional[str] = None
    top_transaction_types: List[Dict[str, Any]] = Field(default_factory=list)
    currencies: List[str] = Field(default_factory=list)


class TransactionRow(BaseModel):
    transaction_id: str
    account_id: Optional[str] = None
    amount: Optional[str] = None
    currency: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    transaction_date: Optional[str] = None


class KycCaseSummary(BaseModel):
    # Internal case id is suppressed for users without customer:read_pii
    # (status-level KYC only); see customer360/service.py.
    kyc_case_id: Optional[str] = None
    case_type: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[str] = None
    opened_at: Optional[str] = None


class ScreeningSummary(BaseModel):
    status: Optional[str] = None
    risk_level: Optional[str] = None
    match_score: Optional[str] = None
    list_name: Optional[str] = None
    matched_name: Optional[str] = None
    checked_at: Optional[str] = None


class AmlAlertSummary(BaseModel):
    alert_id: str
    alert_type: Optional[str] = None
    label: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    score: Optional[str] = None
    triggered_at: Optional[str] = None


class KycAml(BaseModel):
    kyc_verified: Optional[bool] = None
    latest_kyc_case: Optional[KycCaseSummary] = None
    kyc_status: Optional[str] = None
    next_review_date: Optional[str] = None
    pep_screening: Optional[ScreeningSummary] = None
    sanctions_screening: Optional[ScreeningSummary] = None
    aml_alert_counts_by_status: Dict[str, int] = Field(default_factory=dict)
    aml_alert_counts_by_severity: Dict[str, int] = Field(default_factory=dict)
    sar_count: int = 0


class RiskFlagSummary(BaseModel):
    flag_id: str
    flag_type: Optional[str] = None
    severity: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None


class AdminCustomerMetadata(BaseModel):
    """Metadata-only Customer 360 view for admin (customer:read_operational_metadata).

    Explicitly excludes balances, transaction rows, loan amounts, KYC/PEP
    content, and any raw PII. Populated only when the section is granted.
    """
    account_count: int = 0
    active_account_count: int = 0
    product_count: int = 0
    loan_count: int = 0
    risk_score: Optional[float] = None
    risk_classification: Optional[str] = None
    active_flag_count: int = 0
    highest_active_severity: Optional[str] = None
    kyc_status: Optional[str] = None


class RiskSection(BaseModel):
    risk_score: Optional[float] = None
    active_flags: List[RiskFlagSummary] = Field(default_factory=list)
    highest_active_severity: Optional[str] = None
    risk_factors: List[str] = Field(default_factory=list)
    unresolved_flag_count: int = 0


class WorkbenchLink(BaseModel):
    entity_type: str
    entity_id: str
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    updated_at: Optional[str] = None
    scope_id: Optional[str] = None
    source: str = "workbench"


class DataQuality(BaseModel):
    missing_profile: bool = False
    missing_branch: bool = False
    missing_relationship_manager: bool = False
    stale_kyc: bool = False
    unresolved_workbench_reference: bool = False
    unavailable_sections: List[str] = Field(default_factory=list)


class Customer360Overview(BaseModel):
    customer: Optional[CustomerIdentity] = None
    relationship: Optional[Relationship] = None
    financial_summary: Optional[FinancialSummary] = None
    accounts: List[AccountSummary] = Field(default_factory=list)
    loans: List[LoanSummary] = Field(default_factory=list)
    transaction_summary: Optional[TransactionSummary] = None
    recent_transactions: List[TransactionRow] = Field(default_factory=list)
    kyc_aml: Optional[KycAml] = None
    risk: Optional[RiskSection] = None
    analytics_alerts: List[AmlAlertSummary] = Field(default_factory=list)
    workbench_links: List[WorkbenchLink] = Field(default_factory=list)
    admin_metadata: Optional[AdminCustomerMetadata] = None
    data_quality: DataQuality = Field(default_factory=DataQuality)
    generated_at: str = ""
