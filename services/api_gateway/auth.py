"""
services/api_gateway/auth.py
JWT token generation and verification.
Mock user database for MVP — replace with real DB lookup in production.

WARNING: JWT_SECRET_KEY must be rotated in production.
         The default key is for DEMO PURPOSES ONLY.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt  # PyJWT

from shared.config import get_settings
from shared.errors import AuthenticationError, TokenExpiredError, InvalidTokenError
from shared.logger import get_logger
from shared.models import User, UserRole

logger = get_logger(__name__, "api-gateway")
settings = get_settings()

# ─── Mock User Store ──────────────────────────────────────────────────────────
# In production: replace with async DB lookup + bcrypt password hashing.
# For MVP: plaintext passwords acceptable ONLY in demo environments.

MOCK_USERS: dict = {
    "analyst_001": {
        "password": "password",
        "role": UserRole.ANALYST,
        "permissions": [
            "read:customers",
            "read:accounts",
            "read:transactions",
            "read:risk_flags",
        ],
    },
    "analyst_002": {
        "password": "password",
        "role": UserRole.ANALYST,
        "permissions": [
            "read:customers",
            "read:accounts",
            "read:transactions",
        ],
    },
    "compliance_001": {
        "password": "password",
        "role": UserRole.COMPLIANCE,
        "permissions": [
            "read:customers",
            "read:accounts",
            "read:transactions",
            "read:risk_flags",
            "read:audit_logs",
            "read:pii",  # compliance can see unmasked PII
        ],
    },
    "manager_001": {
        "password": "password",
        "role": UserRole.MANAGER,
        "permissions": [
            "read:customers",
            "read:accounts",
            "read:transactions",
            "read:branch_data",
            "read:risk_summary",
        ],
    },
}


# ─── Token Creation ───────────────────────────────────────────────────────────

def create_access_token(user_id: str, user_role: str) -> Tuple[str, int]:
    """
    Generate a signed JWT access token.

    Args:
        user_id:   Unique user identifier.
        user_role: User's role string.

    Returns:
        Tuple of (token_string, expires_in_seconds).
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    expire_ts = int(expire.timestamp())

    payload = {
        "sub": user_id,
        "role": user_role,
        "iat": int(now.timestamp()),
        "exp": expire_ts,
        "jti": str(uuid.uuid4()),  # unique token ID (for revocation in future)
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    expires_in = settings.JWT_EXPIRE_MINUTES * 60
    logger.info("Access token created", extra={"user_id": user_id, "role": user_role})
    return token, expires_in


# ─── Token Verification ───────────────────────────────────────────────────────

def verify_token(token: str) -> Tuple[str, str]:
    """
    Decode and validate a JWT token.

    Args:
        token: Raw JWT string (without 'Bearer ' prefix).

    Returns:
        Tuple of (user_id, user_role).

    Raises:
        TokenExpiredError:  Token has expired.
        InvalidTokenError:  Token is malformed or signature invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str = payload.get("sub", "")
        user_role: str = payload.get("role", "")

        if not user_id or not user_role:
            raise InvalidTokenError()

        return user_id, user_role

    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except jwt.InvalidTokenError:
        raise InvalidTokenError()


# ─── User Authentication ──────────────────────────────────────────────────────

def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Validate credentials against the mock user store.

    Args:
        username: Submitted username.
        password: Submitted password (plaintext — MVP only).

    Returns:
        User object if credentials are valid, None otherwise.
    """
    user_data = MOCK_USERS.get(username)

    if not user_data:
        logger.warning("Login attempt for unknown user", extra={"username": username})
        return None

    # MVP: direct string comparison. Production: bcrypt.checkpw()
    if user_data["password"] != password:
        logger.warning("Invalid password for user", extra={"username": username})
        return None

    return User(
        user_id=username,
        user_role=user_data["role"],
        permissions=user_data["permissions"],
    )
