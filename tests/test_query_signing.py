import sys
import os
import time
import pytest

# Add services/shared path
shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "shared"))
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from query_signing import sign_query_payload, verify_query_signature

KEY = "my-secret-signing-key"
WRONG_KEY = "wrong-secret-signing-key"

def test_valid_signature_accepted():
    # 1. Valid signature accepted
    sql = "SELECT * FROM customers LIMIT 10"
    params = [1, "premium"]
    timestamp = int(time.time())
    nonce = "abc123nonce"
    request_id = "req-id-uuid"
    
    sig = sign_query_payload(request_id, sql, params, timestamp, nonce, KEY)
    assert verify_query_signature(sql, params, sig, KEY) is True

def test_wrong_key_rejected():
    # 2. Wrong key rejected
    sql = "SELECT * FROM customers LIMIT 10"
    params = [1, "premium"]
    timestamp = int(time.time())
    nonce = "abc123nonce"
    request_id = "req-id-uuid"
    
    sig = sign_query_payload(request_id, sql, params, timestamp, nonce, KEY)
    with pytest.raises(ValueError, match="SIGNATURE_PAYLOAD_MISMATCH"):
        verify_query_signature(sql, params, sig, WRONG_KEY)

def test_modified_sql_rejected():
    # 3. Modified SQL rejected
    sql = "SELECT * FROM customers LIMIT 10"
    params = [1, "premium"]
    timestamp = int(time.time())
    nonce = "abc123nonce"
    request_id = "req-id-uuid"
    
    sig = sign_query_payload(request_id, sql, params, timestamp, nonce, KEY)
    modified_sql = "SELECT * FROM customers LIMIT 11"
    with pytest.raises(ValueError, match="SIGNATURE_PAYLOAD_MISMATCH"):
        verify_query_signature(modified_sql, params, sig, KEY)

def test_modified_parameter_rejected():
    # 4. Modified parameter rejected
    sql = "SELECT * FROM customers LIMIT 10"
    params = [1, "premium"]
    timestamp = int(time.time())
    nonce = "abc123nonce"
    request_id = "req-id-uuid"
    
    sig = sign_query_payload(request_id, sql, params, timestamp, nonce, KEY)
    modified_params = [1, "standard"]
    with pytest.raises(ValueError, match="SIGNATURE_PAYLOAD_MISMATCH"):
        verify_query_signature(sql, modified_params, sig, KEY)

def test_modified_request_id_rejected():
    # 5. Modified request_id rejected
    sql = "SELECT * FROM customers LIMIT 10"
    params = [1, "premium"]
    timestamp = int(time.time())
    nonce = "abc123nonce"
    request_id = "req-id-uuid"
    
    sig = sign_query_payload(request_id, sql, params, timestamp, nonce, KEY)
    
    # Signature token has the request_id packed inside.
    # If we modify the request_id in the token, the computed signature won't match.
    parts = sig.split(":")
    parts[4] = "different-req-id"
    tampered_sig = ":".join(parts)
    
    with pytest.raises(ValueError, match="SIGNATURE_PAYLOAD_MISMATCH"):
        verify_query_signature(sql, params, tampered_sig, KEY)

def test_expired_timestamp_rejected():
    # 6. Expired timestamp rejected
    sql = "SELECT * FROM customers LIMIT 10"
    params = [1, "premium"]
    timestamp = int(time.time()) - 100  # 100 seconds ago
    nonce = "abc123nonce"
    request_id = "req-id-uuid"
    
    sig = sign_query_payload(request_id, sql, params, timestamp, nonce, KEY)
    with pytest.raises(ValueError, match="SIGNATURE_EXPIRED"):
        verify_query_signature(sql, params, sig, KEY, max_age_seconds=60)

def test_timestamp_within_tolerance_accepted():
    # 7. Timestamp within tolerance accepted
    sql = "SELECT * FROM customers LIMIT 10"
    params = [1, "premium"]
    timestamp = int(time.time()) - 30  # 30 seconds ago
    nonce = "abc123nonce"
    request_id = "req-id-uuid"
    
    sig = sign_query_payload(request_id, sql, params, timestamp, nonce, KEY)
    assert verify_query_signature(sql, params, sig, KEY, max_age_seconds=60) is True

def test_parameter_dictionary_order_consistent():
    # 8. Different parameter dictionary order produces the same signature
    sql = "SELECT * FROM customers LIMIT 10"
    params_a = [{"a": 1, "b": 2}]
    params_b = [{"b": 2, "a": 1}]
    timestamp = int(time.time())
    nonce = "abc123nonce"
    request_id = "req-id-uuid"
    
    sig_a = sign_query_payload(request_id, sql, params_a, timestamp, nonce, KEY)
    sig_b = sign_query_payload(request_id, sql, params_b, timestamp, nonce, KEY)
    assert sig_a == sig_b

def test_sql_whitespace_normalization():
    # 9. SQL whitespace normalization produces the same signature if intended
    sql_a = "SELECT * FROM customers LIMIT 10"
    sql_b = "  SELECT * \n FROM customers \n LIMIT 10  \n"
    params = []
    timestamp = int(time.time())
    nonce = "abc123nonce"
    request_id = "req-id-uuid"
    
    sig_a = sign_query_payload(request_id, sql_a, params, timestamp, nonce, KEY)
    sig_b = sign_query_payload(request_id, sql_b, params, timestamp, nonce, KEY)
    assert sig_a == sig_b

def test_unicode_french_metadata():
    # 10. Unicode French query metadata signs consistently
    sql = "SELECT * FROM customers WHERE segment = ?"
    params = ["Dépôts"]
    timestamp = int(time.time())
    nonce = "abc123nonce"
    request_id = "req-id-uuid"
    
    # Use pre-composed vs de-composed unicode character to check NFC normalization
    param_decomposed = "De\u0301po\u0302ts" # decomposed e-acute and o-circumflex
    param_precomposed = "Dépôts" # pre-composed
    
    sig_decomp = sign_query_payload(request_id, sql, [param_decomposed], timestamp, nonce, KEY)
    assert verify_query_signature(sql, [param_precomposed], sig_decomp, KEY) is True
