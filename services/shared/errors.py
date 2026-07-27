"""
services/shared/errors.py
Custom exception hierarchy for the Banking Intelligence System.
All errors include a human-readable message and an error_code for clients.
"""
from typing import Optional


class BankingBaseError(Exception):
    """Root exception for all banking system errors."""

    def __init__(self, message: str, error_code: str = "INTERNAL_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error": self.error_code,
            "message": self.message,
        }


# ─── Authentication & Authorization ──────────────────────────────────────────

class AuthenticationError(BankingBaseError):
    """Raised when credentials are invalid or token is missing/expired."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, error_code="AUTH_FAILED")


class AuthorizationError(BankingBaseError):
    """Raised when a user lacks permission to perform an action."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, error_code="PERMISSION_DENIED")


class TokenExpiredError(AuthenticationError):
    """Raised when a JWT token has expired."""

    def __init__(self):
        super().__init__("Token has expired. Please log in again.")
        self.error_code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    """Raised when a JWT token is malformed or invalid."""

    def __init__(self):
        super().__init__("Invalid authentication token.")
        self.error_code = "TOKEN_INVALID"


class AmbiguousRoleMappingError(AuthenticationError):
    """Raised when Keycloak roles map to multiple distinct application roles."""

    def __init__(self, mapped_roles: set):
        super().__init__(
            f"Token maps to conflicting application roles: {sorted(mapped_roles)}. "
            "Each token must resolve to exactly one application role."
        )
        self.error_code = "AMBIGUOUS_ROLE_MAPPING"
        self.mapped_roles = mapped_roles


# ─── Database ─────────────────────────────────────────────────────────────────

class DatabaseError(BankingBaseError):
    """Raised when a database operation fails."""

    def __init__(self, message: str = "Database operation failed", detail: Optional[str] = None):
        full_msg = f"{message}: {detail}" if detail else message
        super().__init__(full_msg, error_code="DB_ERROR")


class ConnectionPoolError(DatabaseError):
    """Raised when the connection pool is exhausted or unreachable."""

    def __init__(self, message: str = "Database connection pool unavailable"):
        super().__init__(message)
        self.error_code = "DB_POOL_ERROR"


class QueryTimeoutError(DatabaseError):
    """Raised when a query exceeds the maximum execution time."""

    def __init__(self, timeout_seconds: int = 30):
        super().__init__(f"Query exceeded timeout of {timeout_seconds}s")
        self.error_code = "QUERY_TIMEOUT"


# ─── Validation ───────────────────────────────────────────────────────────────

class ValidationError(BankingBaseError):
    """Raised when input fails validation checks."""

    def __init__(self, message: str = "Validation failed", field: Optional[str] = None):
        full_msg = f"Validation error on '{field}': {message}" if field else message
        super().__init__(full_msg, error_code="VALIDATION_ERROR")


class SQLInjectionError(ValidationError):
    """Raised when a SQL injection attempt is detected."""

    def __init__(self, detail: str = ""):
        super().__init__(f"SQL injection detected{': ' + detail if detail else ''}")
        self.error_code = "SQL_INJECTION"


class QuerySignatureError(ValidationError):
    """Raised when query HMAC signature verification fails."""

    def __init__(self):
        super().__init__("Query signature verification failed. Query may have been tampered with.")
        self.error_code = "SIGNATURE_INVALID"


# ─── Query Execution ──────────────────────────────────────────────────────────

class QueryExecutionError(BankingBaseError):
    """Raised when a validated query fails during execution."""

    def __init__(self, message: str = "Query execution failed", detail: Optional[str] = None):
        full_msg = f"{message}: {detail}" if detail else message
        super().__init__(full_msg, error_code="QUERY_EXEC_ERROR")


# ─── Service Communication ────────────────────────────────────────────────────

class ServiceUnavailableError(BankingBaseError):
    """Raised when a downstream microservice cannot be reached."""

    def __init__(self, service_name: str):
        super().__init__(
            f"Service '{service_name}' is unavailable. Please try again later.",
            error_code="SERVICE_UNAVAILABLE",
        )


class AuditLoggingError(BankingBaseError):
    """Raised when audit logging fails (non-fatal but should be tracked)."""

    def __init__(self, detail: str = ""):
        super().__init__(
            f"Audit logging failed{': ' + detail if detail else ''}",
            error_code="AUDIT_ERROR",
        )


# ─── Rate Limiting ────────────────────────────────────────────────────────────

class RateLimitError(BankingBaseError):
    """Raised when rate limit is exceeded."""

    def __init__(self, limit: str = "100/minute"):
        super().__init__(
            f"Rate limit exceeded ({limit}). Please slow down.",
            error_code="RATE_LIMIT_EXCEEDED",
        )
