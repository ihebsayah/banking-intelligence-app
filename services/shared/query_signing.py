import hmac
import hashlib
import json
import time
import unicodedata
import logging
from datetime import datetime, date
import uuid

logger = logging.getLogger(__name__)

def canonicalize_value(val):
    """
    Recursively canonicalize dictionary keys, lists/tuples, None, datetimes, and strings.
    :ponytail: Simple recursive dictionary & list formatting to handle all JSON-serializable inputs.
    """
    if val is None:
        return None
    if isinstance(val, dict):
        return {str(k): canonicalize_value(v) for k, v in sorted(val.items())}
    if isinstance(val, (list, tuple)):
        return [canonicalize_value(v) for v in val]
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, str):
        # Normalize line endings and Unicode NFC
        val = val.replace('\r\n', '\n').replace('\r', '\n')
        return unicodedata.normalize('NFC', val)
    return val

def canonicalize_query_payload(request_id: str, sql: str, parameters: list, timestamp: int, nonce: str) -> str:
    """
    Normalize query fields into a deterministic, canonical JSON string.
    :ponytail: Simple normalization rules for SQL whitespace, parameter typing, and sorting.
    """
    import re
    # Normalize SQL whitespace (collapse all consecutive whitespace characters including newlines)
    normalized_sql = re.sub(r'\s+', ' ', sql or '').strip()
    normalized_sql = unicodedata.normalize('NFC', normalized_sql)

    # Build canonical payload
    payload = {
        "request_id": str(request_id) if request_id else "",
        "sql": normalized_sql,
        "parameters": canonicalize_value(parameters or []),
        "timestamp": int(timestamp),
        "nonce": str(nonce) if nonce else ""
    }

    # Deterministic JSON serialization
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

def sign_query_payload(request_id: str, sql: str, parameters: list, timestamp: int, nonce: str, key: str) -> str:
    """
    Sign a query payload using HMAC-SHA256. Returns the formatted signature token.
    """
    serialized = canonicalize_query_payload(request_id, sql, parameters, timestamp, nonce)
    sig = hmac.new(
        key.encode("utf-8"),
        serialized.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    # Carry metadata fields inside the signature token
    return f"sha256:{sig}:{timestamp}:{nonce}:{request_id}"

def verify_query_signature(sql: str, parameters: list, signature: str, key: str, max_age_seconds: int = 60) -> bool:
    """
    Verify the query signature token. Raises specific ValueErrors for distinct failure reasons.
    """
    if not signature:
        raise ValueError("SIGNATURE_MISSING: Query signature is missing")

    parts = signature.split(":", 4)
    if len(parts) < 5 or parts[0] != "sha256":
        raise ValueError("SIGNATURE_INVALID: Query signature format is invalid")

    expected_sig = parts[1]
    try:
        timestamp = int(parts[2])
    except ValueError:
        raise ValueError("SIGNATURE_INVALID: Query signature timestamp is invalid")
    nonce = parts[3]
    request_id = parts[4]

    # Verify timestamp age/skew
    now = int(time.time())
    age = now - timestamp
    if abs(age) > max_age_seconds:
        raise ValueError(f"SIGNATURE_EXPIRED: Query signature has expired (age: {age}s, max age: {max_age_seconds}s)")

    # Reconstruct payload and verify signature
    serialized = canonicalize_query_payload(request_id, sql, parameters, timestamp, nonce)
    actual_sig = hmac.new(
        key.encode("utf-8"),
        serialized.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # Safe debug logging (limit to SHA256 digest, request_id, timestamp, nonce, and 8 chars of signature prefix)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    logger.debug(
        f"[SIGNING_DEBUG] digest={digest} request_id={request_id} timestamp={timestamp} nonce={nonce} "
        f"sig_prefix={expected_sig[:8]} computed_prefix={actual_sig[:8]}"
    )

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("SIGNATURE_PAYLOAD_MISMATCH: Query signature payload mismatch or wrong key")

    return True
