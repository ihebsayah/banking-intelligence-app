"""
services/execution_agent/result_formatter.py
PII masking + multi-format output (JSON / CSV / ASCII table).

Masking rules (applied to all roles except 'compliance'):
  SSN / social_security_number  → "***-**-{last4}"
  credit_card / card_number     → "****-****-****-{last4}"
  email / email_address         → "{first_letter}***@{domain}"
  credit_score                  → "MASKED"
  password / password_hash      → "HIDDEN"
  phone / phone_number          → "***-***-{last4}"
  date_of_birth / dob           → "****-**-**"
"""
import csv
import io
import re
from typing import Any, Dict, List, Optional, Tuple

from access_controller import AccessController, PII_COLUMNS

_ac = AccessController()


# ──────────────────────────────────────────────────────────────────────────────
# PII Masking helpers
# ──────────────────────────────────────────────────────────────────────────────

def _mask_ssn(value: str) -> str:
    """Show only last 4 digits: ***-**-1234"""
    digits = re.sub(r"\D", "", str(value))
    return f"***-**-{digits[-4:]}" if len(digits) >= 4 else "***-**-****"


def _mask_card(value: str) -> str:
    """Show only last 4 digits: ****-****-****-4532"""
    digits = re.sub(r"\D", "", str(value))
    return f"****-****-****-{digits[-4:]}" if len(digits) >= 4 else "****-****-****-****"


def _mask_email(value: str) -> str:
    """u***@example.com"""
    try:
        local, domain = str(value).split("@", 1)
        return f"{local[0]}***@{domain}"
    except Exception:
        return "***@***.***"


def _mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", str(value))
    return f"***-***-{digits[-4:]}" if len(digits) >= 4 else "***-***-****"


def _mask_value(column: str, value: Any) -> Tuple[Any, bool]:
    """
    Returns (masked_value, was_masked).
    Returns (value, False) if column not PII.
    """
    col = column.lower()
    if value is None:
        return value, False

    if col in ("ssn", "social_security_number"):
        return _mask_ssn(str(value)), True
    if col in ("credit_card", "credit_card_number", "card_number"):
        return _mask_card(str(value)), True
    if col in ("email", "email_address"):
        return _mask_email(str(value)), True
    if col in ("credit_score",):
        return "MASKED", True
    if col in ("password", "password_hash"):
        return "HIDDEN", True
    if col in ("phone", "phone_number"):
        return _mask_phone(str(value)), True
    if col in ("date_of_birth", "dob"):
        return "****-**-**", True
    return value, False


# ──────────────────────────────────────────────────────────────────────────────
# Format renderers
# ──────────────────────────────────────────────────────────────────────────────

def _to_csv(rows: List[Dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _to_table(rows: List[Dict]) -> str:
    """ASCII box table."""
    if not rows:
        return "(empty result set)"
    cols = list(rows[0].keys())
    widths = {c: max(len(str(c)), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}

    def _sep():
        return "+-" + "-+-".join("-" * widths[c] for c in cols) + "-+"

    def _row(r: Dict):
        cells = (str(r.get(c, "")).ljust(widths[c]) for c in cols)
        return "| " + " | ".join(cells) + " |"

    lines = [_sep()]
    lines.append("| " + " | ".join(str(c).ljust(widths[c]) for c in cols) + " |")
    lines.append(_sep())
    for r in rows:
        lines.append(_row(r))
    lines.append(_sep())
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# ResultFormatter
# ──────────────────────────────────────────────────────────────────────────────

class ResultFormatter:
    """
    Apply column filtering, PII masking, then format results.
    """

    def format(
        self,
        raw_rows: List[Dict],
        format_type: str,
        user_role: str,
    ) -> Tuple[Any, List[str]]:
        """
        Returns (formatted_data, columns_masked_list).

        formatted_data:
          - json   → list[dict]
          - csv    → str
          - table  → str (ASCII)
        """
        columns_masked: List[str] = []
        should_mask = _ac.should_mask_pii(user_role)

        processed = []
        for row in raw_rows:
            # 1. Column visibility filter
            filtered = _ac.filter_columns(row, user_role)

            # 2. PII masking
            masked_row = {}
            for col, val in filtered.items():
                if should_mask and col.lower() in PII_COLUMNS:
                    new_val, was_masked = _mask_value(col, val)
                    masked_row[col] = new_val
                    if was_masked and col not in columns_masked:
                        columns_masked.append(col)
                else:
                    masked_row[col] = val
            processed.append(masked_row)

        fmt = format_type.lower()
        if fmt == "csv":
            return _to_csv(processed), columns_masked
        if fmt == "table":
            return _to_table(processed), columns_masked
        # default: json (list of dicts)
        return processed, columns_masked
