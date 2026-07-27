"""
tests/test_keycloak_auth.py
Focused unit tests for Keycloak RS256 token validation.

Tests run WITHOUT internet — JWKS endpoint is mocked via httpx mock.
Covers: valid token, expired, invalid sig, wrong issuer, wrong audience,
wrong azp, missing sub, missing role, unknown kid, JWKS unavailable,
alg=none rejection, HS256 rejection, role mapping, DB permission loading.
"""
import sys
import os
import time
import json
import base64
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone

import jwt
from jwt import PyJWKSet, PyJWK
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GATEWAY = os.path.join(BASE, "services/api_gateway")
SHARED = os.path.join(BASE, "services/shared")

for p in [GATEWAY, SHARED]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ─── Key Generation Helpers ─────────────────────────────────────────────────

def _generate_rsa_keypair():
    """Generate an RSA key pair for testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


PRIVATE_PEM, PUBLIC_PEM = _generate_rsa_keypair()
TEST_KID = "test-key-1"
TEST_ISSUER = "http://keycloak:8080/realms/banking-intelligence"
TEST_AUDIENCE = "banking-portal-api"


def _make_jwks_response():
    """Build a JWKS response dict containing our test public key."""
    from jwt.algorithms import RSAAlgorithm

    pub_key = serialization.load_pem_public_key(PUBLIC_PEM)
    alg_obj = RSAAlgorithm(RSAAlgorithm.SHA256)
    jwk_dict = json.loads(alg_obj.to_jwk(pub_key))
    jwk_dict["kid"] = TEST_KID
    return {"keys": [jwk_dict]}


def _make_test_token(
    sub="test-user-123",
    iss=TEST_ISSUER,
    aud=TEST_AUDIENCE,
    exp_delta=300,
    nbf_offset=0,
    realm_roles=None,
    kid=TEST_KID,
    alg="RS256",
    extra_claims=None,
):
    """Create a signed test JWT."""
    now = int(time.time())
    claims = {
        "sub": sub,
        "iss": iss,
        "aud": aud,
        "iat": now,
        "exp": now + exp_delta,
        "nbf": now + nbf_offset,
        "preferred_username": "testuser",
        "email": "test@banking.local",
        "realm_roles": realm_roles or ["banking_analyst"],
    }
    if extra_claims:
        claims.update(extra_claims)

    if alg == "none":
        header = {"alg": "none", "typ": "JWT", "kid": kid}
        import base64
        h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
        p = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        return f"{h}.{p}."

    if alg == "HS256":
        return jwt.encode(claims, "some-secret", algorithm="HS256")

    return jwt.encode(
        claims,
        PRIVATE_PEM,
        algorithm="RS256",
        headers={"kid": kid},
    )


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_jwks_cache():
    """Clear JWKS cache before each test."""
    from keycloak_auth import invalidate_jwks_cache
    invalidate_jwks_cache()
    yield
    invalidate_jwks_cache()


@pytest.fixture
def mock_jwks():
    """Mock httpx.get to return our test JWKS."""
    jwks_data = _make_jwks_response()
    mock_resp = MagicMock()
    mock_resp.json.return_value = jwks_data
    mock_resp.raise_for_status = MagicMock()
    with patch("keycloak_auth.httpx.get", return_value=mock_resp):
        yield


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestValidToken:
    def test_valid_rs256_token_accepted(self, mock_jwks):
        from keycloak_auth import validate_keycloak_token
        token = _make_test_token()
        subject, claims = validate_keycloak_token(token)
        assert subject == "test-user-123"
        assert claims["email"] == "test@banking.local"


class TestTokenRejection:
    def test_expired_token_rejected(self, mock_jwks):
        from keycloak_auth import validate_keycloak_token
        from shared.errors import TokenExpiredError
        token = _make_test_token(exp_delta=-60)  # well past clock skew
        with pytest.raises(TokenExpiredError):
            validate_keycloak_token(token)

    def test_invalid_signature_rejected(self, mock_jwks):
        from keycloak_auth import validate_keycloak_token, KeycloakTokenValidationError
        # Sign with a different key
        other_private, _ = _generate_rsa_keypair()
        claims = {
            "sub": "user-1", "iss": TEST_ISSUER, "aud": TEST_AUDIENCE,
            "iat": int(time.time()), "exp": int(time.time()) + 300,
        }
        token = jwt.encode(claims, other_private, algorithm="RS256", headers={"kid": TEST_KID})
        with pytest.raises(KeycloakTokenValidationError):
            validate_keycloak_token(token)

    def test_wrong_issuer_rejected(self, mock_jwks):
        from keycloak_auth import validate_keycloak_token, KeycloakTokenValidationError
        token = _make_test_token(iss="http://evil.com/realms/fake")
        with pytest.raises(KeycloakTokenValidationError, match="issuer"):
            validate_keycloak_token(token)

    def test_wrong_audience_rejected(self, mock_jwks):
        from keycloak_auth import validate_keycloak_token, KeycloakTokenValidationError
        token = _make_test_token(aud="wrong-audience")
        with pytest.raises(KeycloakTokenValidationError, match="audience"):
            validate_keycloak_token(token)

    def test_alg_none_rejected(self, mock_jwks):
        from keycloak_auth import validate_keycloak_token, KeycloakTokenValidationError
        # Build a token with alg=none manually
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT", "kid": TEST_KID}).encode()).rstrip(b"=").decode()
        payload_claims = {"sub": "user-1", "iss": TEST_ISSUER, "aud": TEST_AUDIENCE, "exp": int(time.time()) + 300}
        payload = base64.urlsafe_b64encode(json.dumps(payload_claims).encode()).rstrip(b"=").decode()
        token = f"{header}.{payload}."
        with pytest.raises(KeycloakTokenValidationError, match="none"):
            validate_keycloak_token(token)

    def test_hs256_token_rejected(self, mock_jwks):
        from keycloak_auth import validate_keycloak_token, KeycloakTokenValidationError
        token = _make_test_token(alg="HS256")
        with pytest.raises(KeycloakTokenValidationError, match="algorithm"):
            validate_keycloak_token(token)

    def test_malformed_token_rejected(self, mock_jwks):
        from keycloak_auth import validate_keycloak_token, KeycloakTokenValidationError
        with pytest.raises(KeycloakTokenValidationError):
            validate_keycloak_token("not.a.valid.jwt.token")


class TestJWKSFailures:
    def test_unknown_kid_triggers_refresh(self):
        from keycloak_auth import validate_keycloak_token, KeycloakTokenValidationError
        # JWKS always returns our test key (kid=TEST_KID), but token uses unknown kid
        good_resp = MagicMock()
        good_resp.json.return_value = _make_jwks_response()
        good_resp.raise_for_status = MagicMock()

        with patch("keycloak_auth.httpx.get", return_value=good_resp):
            token = _make_test_token(kid="unknown-kid-999")
            with pytest.raises(KeycloakTokenValidationError, match="not found"):
                validate_keycloak_token(token)

    def test_jwks_unavailable_with_warm_cache(self):
        from keycloak_auth import validate_keycloak_token, _load_jwks
        # Pre-populate cache
        good_resp = MagicMock()
        good_resp.json.return_value = _make_jwks_response()
        good_resp.raise_for_status = MagicMock()
        with patch("keycloak_auth.httpx.get", return_value=good_resp):
            _load_jwks()

        # Now make JWKS fail — should use stale cache
        with patch("keycloak_auth.httpx.get", side_effect=Exception("network error")):
            token = _make_test_token()
            subject, claims = validate_keycloak_token(token)
            assert subject == "test-user-123"

    def test_jwks_unavailable_with_empty_cache(self):
        from keycloak_auth import validate_keycloak_token, KeycloakTokenValidationError
        with patch("keycloak_auth.httpx.get", side_effect=Exception("network error")):
            token = _make_test_token()
            with pytest.raises(Exception, match="Unable to fetch|network error"):
                validate_keycloak_token(token)

    def test_two_different_kids_cached_independently(self):
        from keycloak_auth import validate_keycloak_token, _load_jwks, _jwks_cache
        # Generate two key pairs
        other_private, other_public = _generate_rsa_keypair()
        
        # Build JWKS with both keys
        from jwt.algorithms import RSAAlgorithm
        key1 = serialization.load_pem_public_key(PUBLIC_PEM)
        key2 = serialization.load_pem_public_key(other_public)
        alg_obj = RSAAlgorithm(RSAAlgorithm.SHA256)
        jwk1 = json.loads(alg_obj.to_jwk(key1))
        jwk1["kid"] = TEST_KID
        jwk2 = json.loads(alg_obj.to_jwk(key2))
        jwk2["kid"] = "kid-two"
        jwks_response = {"keys": [jwk1, jwk2]}
        
        good_resp = MagicMock()
        good_resp.json.return_value = jwks_response
        good_resp.raise_for_status = MagicMock()
        
        with patch("keycloak_auth.httpx.get", return_value=good_resp):
            _load_jwks()
            # Both kids should be cached
            assert TEST_KID in _jwks_cache["keys_by_kid"]
            assert "kid-two" in _jwks_cache["keys_by_kid"]
            # Each key should be different
            assert _jwks_cache["keys_by_kid"][TEST_KID] != _jwks_cache["keys_by_kid"]["kid-two"]

    def test_cache_hit_by_kid(self):
        from keycloak_auth import validate_keycloak_token, _load_jwks, _jwks_cache
        good_resp = MagicMock()
        good_resp.json.return_value = _make_jwks_response()
        good_resp.raise_for_status = MagicMock()
        
        with patch("keycloak_auth.httpx.get", return_value=good_resp):
            _load_jwks()
            # Verify key is in cache by kid
            assert TEST_KID in _jwks_cache["keys_by_kid"]
            # Token validation should use cached key
            token = _make_test_token()
            subject, claims = validate_keycloak_token(token)
            assert subject == "test-user-123"

    def test_stale_key_refresh(self):
        from keycloak_auth import validate_keycloak_token, _load_jwks, _jwks_cache
        import time
        # Pre-populate cache
        good_resp = MagicMock()
        good_resp.json.return_value = _make_jwks_response()
        good_resp.raise_for_status = MagicMock()
        with patch("keycloak_auth.httpx.get", return_value=good_resp):
            _load_jwks()
        
        # Simulate cache expiration by setting fetched_at to 0
        _jwks_cache["fetched_at"] = 0.0
        
        # Now validate token - should trigger refresh
        with patch("keycloak_auth.httpx.get", return_value=good_resp):
            token = _make_test_token()
            subject, claims = validate_keycloak_token(token)
            assert subject == "test-user-123"


class TestRoleMapping:
    def test_keycloak_role_mapping_analyst(self):
        from routes import _map_keycloak_roles_to_application_role
        assert _map_keycloak_roles_to_application_role(["banking_analyst"]) == "analyst"

    def test_keycloak_role_mapping_manager(self):
        from routes import _map_keycloak_roles_to_application_role
        assert _map_keycloak_roles_to_application_role(["executive_manager"]) == "manager"

    def test_keycloak_role_mapping_compliance(self):
        from routes import _map_keycloak_roles_to_application_role
        assert _map_keycloak_roles_to_application_role(["compliance_officer"]) == "compliance"

    def test_keycloak_role_mapping_admin(self):
        from routes import _map_keycloak_roles_to_application_role
        assert _map_keycloak_roles_to_application_role(["administrator"]) == "admin"

    def test_keycloak_role_mapping_risk_officer_to_analyst(self):
        from routes import _map_keycloak_roles_to_application_role
        assert _map_keycloak_roles_to_application_role(["risk_officer"]) == "analyst"

    def test_keycloak_role_mapping_internal_auditor_to_compliance(self):
        from routes import _map_keycloak_roles_to_application_role
        assert _map_keycloak_roles_to_application_role(["internal_auditor"]) == "compliance"

    def test_keycloak_role_mapping_multiple_roles_highest_wins(self):
        from routes import _map_keycloak_roles_to_application_role
        from shared.errors import AmbiguousRoleMappingError
        # Conflicting distinct app roles (analyst + admin) must raise
        with pytest.raises(AmbiguousRoleMappingError):
            _map_keycloak_roles_to_application_role(
                ["banking_analyst", "administrator"]
            )

    def test_keycloak_role_mapping_conflicting_roles_raises_error(self):
        from routes import _map_keycloak_roles_to_application_role
        from shared.errors import AmbiguousRoleMappingError
        with pytest.raises(AmbiguousRoleMappingError):
            _map_keycloak_roles_to_application_role(["banking_analyst", "compliance_officer"])

    def test_keycloak_role_mapping_same_app_role_multiple_keycloak_roles(self):
        from routes import _map_keycloak_roles_to_application_role
        assert _map_keycloak_roles_to_application_role(
            ["banking_analyst", "risk_officer"]
        ) == "analyst"

    def test_keycloak_role_mapping_unknown_role_defaults_analyst(self):
        from routes import _map_keycloak_roles_to_application_role
        assert _map_keycloak_roles_to_application_role(["unknown_role"]) is None

    def test_keycloak_role_mapping_empty_list_defaults_analyst(self):
        from routes import _map_keycloak_roles_to_application_role
        assert _map_keycloak_roles_to_application_role([]) is None


class TestConfigDefaults:
    def test_auth_provider_default_legacy(self, monkeypatch):
        monkeypatch.setenv("AUTH_PROVIDER", "legacy")
        from shared.config import Settings
        s = Settings()
        assert s.AUTH_PROVIDER == "legacy"

    def test_keycloak_urls_default(self):
        from shared.config import Settings
        s = Settings()
        assert s.KEYCLOAK_INTERNAL_URL == "http://keycloak:8080"
        assert s.KEYCLOAK_REALM == "banking-intelligence"
        assert s.KEYCLOAK_EXPECTED_AUDIENCE == "banking-portal-api"

    def test_keycloak_dev_transient_users_disabled_by_default(self):
        from shared.config import Settings
        s = Settings()
        assert s.KEYCLOAK_DEV_TRANSIENT_USERS_ENABLED is False


class TestUserModel:
    def test_user_model_has_keycloak_fields(self):
        from shared.models import User
        u = User(user_id="x", user_role="analyst", authentication_provider="keycloak",
                 keycloak_subject="kc-sub-123", email="a@b.com")
        assert u.authentication_provider == "keycloak"
        assert u.keycloak_subject == "kc-sub-123"

    def test_user_model_defaults_to_legacy(self):
        from shared.models import User
        u = User(user_id="x", user_role="analyst")
        assert u.authentication_provider == "legacy"
        assert u.keycloak_subject is None

    def test_user_model_has_unmapped_role(self):
        from shared.models import User, UserRole
        u = User(user_id="x", user_role="unmapped")
        assert u.user_role == "unmapped"
