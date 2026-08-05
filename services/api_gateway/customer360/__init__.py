"""Customer 360 read bridge (Phase 3A.2).

Composes authoritative customer data from banking_dev with explicit workbench
links from banking_integration behind a single permission-scoped API surface.
"""

from .models import (
    AccountSummary,
    AdminCustomerMetadata,
    AmlAlertSummary,
    Customer360Overview,
    CustomerIdentity,
    DataQuality,
    FinancialSummary,
    KycAml,
    KycCaseSummary,
    LoanSummary,
    Relationship,
    RiskFlagSummary,
    RiskSection,
    ScreeningSummary,
    TransactionRow,
    TransactionSummary,
    WorkbenchLink,
)
from .repos import Customer360Repository, WorkbenchLinkRepository
from .service import Customer360Service, Customer360SourceUnavailable

__all__ = [
    "Customer360Service",
    "Customer360SourceUnavailable",
    "Customer360Repository",
    "WorkbenchLinkRepository",
    "AccountSummary",
    "AdminCustomerMetadata",
    "AmlAlertSummary",
    "Customer360Overview",
    "CustomerIdentity",
    "DataQuality",
    "FinancialSummary",
    "KycAml",
    "KycCaseSummary",
    "LoanSummary",
    "Relationship",
    "RiskFlagSummary",
    "RiskSection",
    "ScreeningSummary",
    "TransactionRow",
    "TransactionSummary",
    "WorkbenchLink",
]
