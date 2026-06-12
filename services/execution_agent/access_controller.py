"""
services/execution_agent/access_controller.py
Role-based access control: row filters + column visibility + PII masking rules.

Roles:
  analyst        — sees all rows, masked PII columns
  manager        — sees all rows (branch-scoped in real deployments), masked PII
  compliance     — sees all rows, ALL columns unmasked
  customer       — sees only their own rows, limited columns
"""
from typing import Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# ROW-LEVEL FILTERS
# These WHERE-clause fragments are appended to queries per role.
# In a real system these would use the actual user_id / branch_id from JWT.
# ──────────────────────────────────────────────────────────────────────────────

_ROW_FILTERS: Dict[str, Optional[str]] = {
    "analyst":    None,                       # no extra filter — see all
    "manager":    None,                       # simplified; prod: WHERE branch_id = :bid
    "compliance": None,                       # see everything
    "customer":   "WHERE customer_id = :uid", # only own data
}

# ──────────────────────────────────────────────────────────────────────────────
# VISIBLE COLUMNS PER ROLE
# None = all columns visible
# ──────────────────────────────────────────────────────────────────────────────

_VISIBLE_COLUMNS: Dict[str, Optional[List[str]]] = {
    "analyst": [
        # customers
        "customer_id", "name", "segment", "risk_score", "kyc_verified",
        # accounts
        "account_id", "account_type", "status", "balance", "available_balance", "currency", "branch_id",
        # transactions
        "transaction_id", "amount", "transaction_type", "transaction_date", "description",
        # branches
        "branch_id", "state", "city",
        # products
        "product_id", "category",
        # risk_flags
        "flag_type", "severity", "resolved",
        # generic
        "id", "created_at", "updated_at", "customer_id",
    ],
    "manager": [
        # customers
        "customer_id", "name", "segment", "risk_score", "kyc_verified",
        # accounts
        "account_id", "account_type", "status", "balance", "available_balance", "currency", "branch_id",
        # transactions
        "transaction_id", "amount", "transaction_type", "transaction_date",
        # branches
        "branch_id", "state", "city", "manager_id",
        # risk flags
        "flag_type", "severity", "resolved", "description",
        # generic
        "id", "created_at",
    ],
    "compliance": None,  # all columns, no masking
    "customer": [
        "customer_id", "name", "segment",
        "account_id", "account_type", "balance", "available_balance",
        "transaction_id", "amount", "transaction_type", "transaction_date",
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# PII COLUMNS — masked for all roles except compliance
# ──────────────────────────────────────────────────────────────────────────────

PII_COLUMNS = {
    "ssn", "social_security_number",
    "credit_card", "credit_card_number", "card_number",
    "email", "email_address",
    "credit_score",
    "password", "password_hash",
    "phone", "phone_number",
    "date_of_birth", "dob",
}


class AccessController:
    """Enforces role-based access rules."""

    def get_row_filter(self, user_role: str) -> Optional[str]:
        """Return a SQL fragment (or None) to restrict rows for this role."""
        return _ROW_FILTERS.get(user_role.lower(), None)

    def get_visible_columns(self, user_role: str) -> Optional[List[str]]:
        """Return the list of columns this role may see (None = all)."""
        return _VISIBLE_COLUMNS.get(user_role.lower(), _VISIBLE_COLUMNS["analyst"])

    def should_mask_pii(self, user_role: str) -> bool:
        """Compliance sees raw PII; everyone else gets masked values."""
        return user_role.lower() != "compliance"

    def filter_columns(self, row: Dict, user_role: str) -> Dict:
        """Remove columns the role cannot see from a result row, allowing dynamic/aggregate columns."""
        visible = self.get_visible_columns(user_role)
        if visible is None:
            return row
            
        all_db_cols = {
            # customers
            "id", "customer_id", "name", "email", "phone", "kyc_verified", "risk_score", "segment", "created_at", "updated_at",
            "credit_score", "ssn", "social_security_number", "credit_card", "credit_card_number", "card_number", 
            "email_address", "password", "password_hash", "phone_number", "date_of_birth", "dob",
            # accounts
            "account_id", "account_type", "status", "balance", "available_balance", "currency", "branch_id",
            # transactions
            "transaction_id", "amount", "transaction_type", "transaction_date", "description",
            # branches
            "branch_name", "state", "city", "country", "manager_id", "opened_at",
            # products
            "product_id", "category",
            # risk_flags
            "risk_id", "flag_type", "severity", "resolved", "flagged_at", "resolved_at",
            # loans
            "loan_id", "loan_type", "principal_amount", "interest_rate", "term_months", "disbursed_at", "due_date",
            # employees
            "employee_id", "first_name", "last_name", "role", "hired_at"
        }
        
        filtered = {}
        for k, v in row.items():
            k_lower = k.lower()
            if k_lower in visible or k_lower not in all_db_cols:
                filtered[k] = v
        return filtered
