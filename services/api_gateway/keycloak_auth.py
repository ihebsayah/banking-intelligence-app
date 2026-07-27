"""
services/api_gateway/keycloak_auth.py
Keycloak RS256 token validation via JWKS.

Validates Keycloak-issued access tokens locally after fetching signing keys
from the realm JWKS endpoint. No Keycloak Admin SDK required.
"""
import json
import time
from typing import Optional, Tuple

import jwt
import httpx
from jwt import PyJWKSet, PyJWK

from shared.config import get_settings
from shared.errors import AuthenticationError, InvalidTokenError, TokenExpiredError
from shared.logger import get_logger

logger = get_logger(__name__, "api-gateway")
settings = get_settings()

# ─── JWKS Cache ──────────────────────────────────────────────────────────────

_jwks_cache: dict = {
    "keys_by_kid": {},
    "fetched_at": 0.0,
    "raw_keys": None,  # Store raw PyJWKSet for fallback
}


def _jwks_url() -> str:
    base = settings.KEYCLOAK_INTERNAL_URL.rstrip("/")
    realm = settings.KEYCLOAK_REALM
    return f"{base}/realms/{realm}/protocol/openid-connect/certs"


def _load_jwks(force_refresh: bool = False) -> PyJWKSet:
    """
    Fetch and cache JWKS keys from Keycloak.

    Uses a simple time-based cache. On unknown kid, forces a refresh.
    """
    now = time.time()
    ttl = settings.KEYCLOAK_JWKS_CACHE_TTL_SECONDS

    if (
        not force_refresh
        and _jwks_cache["raw_keys"] is not None
        and (now - _jwks_cache["fetched_at"]) < ttl
    ):
        return _jwks_cache["raw_keys"]

    url = _jwks_url()
    try:
        resp = httpx.get(url, timeout=settings.KEYCLOAK_HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
        resp_data = resp.json()
        keys_list = resp_data.get("keys", [])
        if not keys_list:
            logger.warning("JWKS response contained no keys", extra={"url": url})
            if _jwks_cache["raw_keys"] is not None:
                return _jwks_cache["raw_keys"]
            raise AuthenticationError("JWKS endpoint returned no signing keys")
        jwks = PyJWKSet.from_dict(resp_data)
        _jwks_cache["raw_keys"] = jwks
        _jwks_cache["fetched_at"] = now
        # Rebuild kid index
        _jwks_cache["keys_by_kid"] = {key.key_id: key for key in jwks.keys if key.key_id}
        logger.info("JWKS keys fetched", extra={"url": url, "key_count": len(jwks.keys)})
        return jwks
    except httpx.HTTPError as exc:
        logger.error("JWKS fetch failed", extra={"url": url, "error": str(exc)})
        if _jwks_cache["raw_keys"] is not None:
            logger.warning("Using stale JWKS cache")
            return _jwks_cache["raw_keys"]
        raise AuthenticationError("Unable to fetch signing keys from identity provider")


def _find_signing_key(kid: str, jwks: PyJWKSet) -> Optional[PyJWK]:
    """Find a specific key by kid from the JWKS key set."""
    # Fast path: check kid index first
    key = _jwks_cache.get("keys_by_kid", {}).get(kid)
    if key is not None:
        return key
    # Fallback: linear scan (shouldn't happen if cache is populated)
    for key in jwks.keys:
        if key.key_id == kid:
            return key
    return None


# ─── Token Validation ────────────────────────────────────────────────────────

class KeycloakTokenValidationError(AuthenticationError):
    """Raised when Keycloak token validation fails."""
    pass


def validate_keycloak_token(token: str) -> Tuple[str, dict]:
    """
    Validate a Keycloak RS256 access token.

    Args:
        token: Raw JWT string (without 'Bearer ' prefix).

    Returns:
        Tuple of (subject, full_claims_dict).

    Raises:
        TokenExpiredError: Token has expired.
        KeycloakTokenValidationError: Token is invalid for any reason.
    """
    # 1. Read the unverified header to get kid and alg
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.DecodeError:
        raise KeycloakTokenValidationError("Malformed token")

    alg = unverified_header.get("alg", "")
    kid = unverified_header.get("kid", "")

    # 2. Reject alg=none
    if alg.lower() == "none":
        raise KeycloakTokenValidationError("Token algorithm 'none' is not allowed")

    # 3. Allow only RS256
    if alg != "RS256":
        raise KeycloakTokenValidationError(
            f"Unexpected algorithm '{alg}'. Only RS256 is accepted for Keycloak tokens"
        )

    if not kid:
        raise KeycloakTokenValidationError("Token missing key ID (kid)")

    # 4. Resolve signing key from JWKS
    jwks = _load_jwks()
    signing_key = _find_signing_key(kid, jwks)

    if signing_key is None:
        # Unknown kid — refresh JWKS once
        logger.warning("Unknown kid, refreshing JWKS", extra={"kid": kid})
        jwks = _load_jwks(force_refresh=True)
        signing_key = _find_signing_key(kid, jwks)

    if signing_key is None:
        raise KeycloakTokenValidationError(f"Signing key not found for kid '{kid}'")

    # 5. Decode and validate
    clock_skew = settings.KEYCLOAK_CLOCK_SKEW_SECONDS
    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_EXPECTED_AUDIENCE,
            issuer=f"{settings.KEYCLOAK_INTERNAL_URL.rstrip('/')}/realms/{settings.KEYCLOAK_REALM}",
            options={
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iss": True,
                "verify_aud": True,
                "require": ["exp", "sub", "iss", "aud"],
            },
            leeway=clock_skew,
        )
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except jwt.InvalidAudienceError:
        raise KeycloakTokenValidationError("Token audience does not match expected audience")
    except jwt.InvalidIssuerError:
        raise KeycloakTokenValidationError("Token issuer does not match expected issuer")
    except jwt.InvalidTokenError as exc:
        raise KeycloakTokenValidationError(f"Invalid token: {exc}")

    subject = claims.get("sub")
    if not subject:
        raise KeycloakTokenValidationError("Token missing subject claim")

    return subject, claims


def invalidate_jwks_cache() -> None:
    """Clear the JWKS cache. Useful for testing."""
    _jwks_cache["keys_by_kid"] = {}
    _jwks_cache["fetched_at"] = 0.0
    _jwks_cache["raw_keys"] = None
