"""
services/api_gateway/auth.py
JWT token generation and verification.
Authentication now queries the real `users` table.
Falls back to the mock store if the database is unavailable (dev safety).

WARNING: JWT_SECRET_KEY must be rotated in production.
         The default key is for DEMO PURPOSES ONLY.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt  # PyJWT
from passlib.context import CryptContext

from shared.config import get_settings
from shared.errors import AuthenticationError, TokenExpiredError, InvalidTokenError
from shared.logger import get_logger
from shared.models import User, UserRole

logger = get_logger(__name__, "api-gateway")
settings = get_settings()

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    """Generate a bcrypt hash from a plaintext password."""
    return pwd_context.hash(plain)


# ─── Fallback Mock User Store ─────────────────────────────────────────────────
# Used ONLY when the database is unreachable (e.g., during cold start).
# Production: every login goes through the real `users` table.

MOCK_USERS: dict = {
    "analyst_001": {
        "password_hash": "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y",
        "role": UserRole.ANALYST,
        "permissions": [
            "read:customers",
            "read:accounts",
            "read:transactions",
            "read:risk_flags",
        ],
    },
    "analyst_002": {
        "password_hash": "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y",
        "role": UserRole.ANALYST,
        "permissions": [
            "read:customers",
            "read:accounts",
            "read:transactions",
        ],
    },
    "compliance_001": {
        "password_hash": "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y",
        "role": UserRole.COMPLIANCE,
        "permissions": [
            "read:customers",
            "read:accounts",
            "read:transactions",
            "read:risk_flags",
            "read:audit_logs",
            "read:pii",
        ],
    },
    "manager_001": {
        "password_hash": "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y",
        "role": UserRole.MANAGER,
        "permissions": [
            "read:customers",
            "read:accounts",
            "read:transactions",
            "read:branch_data",
            "read:risk_summary",
        ],
    },
    "admin_001": {
        "password_hash": "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y",
        "role": UserRole.ADMIN,
        "permissions": [
            "read:customers",
            "read:accounts",
            "read:transactions",
            "read:risk_flags",
            "read:audit_logs",
            "read:pii",
            "admin:users",
            "admin:roles",
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

async def authenticate_user_db(
    username: str,
    password: str,
    db,  # DatabaseConnector | None
) -> Optional[User]:
    """
    Validate credentials against the real `users` table.
    Falls back to MOCK_USERS if db is None and DEV_MODE is True.

    Args:
        username: Submitted username.
        password: Submitted password (plaintext; verified using bcrypt).
        db:       DatabaseConnector instance, or None to use mock store.

    Returns:
        User object if credentials are valid, None otherwise.
    """
    if db is None:
        if settings.DEV_MODE:
            logger.warning("DB unavailable — using mock user store fallback")
            return _authenticate_mock(username, password)
        else:
            logger.error("DB unavailable and DEV_MODE is False")
            return None

    try:
        row = await db.fetch_one(
            """
            SELECT user_id, role, password_hash, permissions, status, must_change_password
              FROM users
             WHERE user_id = $1
            """,
            [username],
        )

        if not row:
            logger.warning("Login attempt failed (DB - user not found)", extra={"username": username})
            # To avoid timing attacks, verify a dummy hash
            pwd_context.verify(password, "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y")
            return None

        # Verify bcrypt password hash
        if not pwd_context.verify(password, row["password_hash"]):
            logger.warning("Login attempt failed (DB - invalid password)", extra={"username": username})
            return None

        # Check status
        if row["status"] != "active":
            logger.warning("Login attempt failed (DB - user status not active)", extra={"username": username})
            return None

        # Update last_login (non-fatal)
        try:
            await db.execute(
                "UPDATE users SET last_login = NOW() WHERE user_id = $1",
                [username],
            )
        except Exception:
            pass

        # Load role's dynamic permissions from the junction table
        try:
            role_permissions_rows = await db.fetch_all(
                """
                SELECT permission_key
                  FROM role_permissions
                 WHERE role_id = $1
                """,
                [row["role"]]
            )
            role_perms = [r["permission_key"] for r in role_permissions_rows]
        except Exception as err:
            logger.error("Failed to load role permissions from DB", extra={"error": str(err)})
            role_perms = []

        custom_perms = row.get("permissions") or []
        if isinstance(custom_perms, str):
            import json
            try:
                custom_perms = json.loads(custom_perms)
            except Exception:
                custom_perms = [custom_perms]

        # Combine role-based permissions with custom permission overrides
        all_perms = list(set(role_perms) | set(custom_perms))

        return User(
            user_id=row["user_id"],
            user_role=row["role"],
            permissions=all_perms,
        )

    except Exception as exc:
        logger.error(
            "DB authentication query failed",
            extra={"error": str(exc)},
        )
        if settings.DEV_MODE:
            logger.warning("Falling back to mock store due to DB error")
            return _authenticate_mock(username, password)
        return None


def _authenticate_mock(username: str, password: str) -> Optional[User]:
    """Fallback: validate against in-memory mock user store."""
    if not settings.DEV_MODE:
        logger.warning("Mock auth attempted, but DEV_MODE is disabled.")
        return None
    user_data = MOCK_USERS.get(username)
    if not user_data:
        logger.warning("Login attempt for unknown user", extra={"username": username})
        return None
    if not pwd_context.verify(password, user_data["password_hash"]):
        logger.warning("Invalid password for user", extra={"username": username})
        return None
    return User(
        user_id=username,
        user_role=user_data["role"],
        permissions=user_data["permissions"],
    )


# ─── Sync wrapper kept for backward compatibility ─────────────────────────────

def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Synchronous fallback used only in tests / non-async contexts.
    Real login path uses `authenticate_user_db` (async).
    """
    return _authenticate_mock(username, password)

