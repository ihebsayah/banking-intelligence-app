"""
tests/conftest.py
Stub/patch setup for running api_gateway tests outside Docker.

Without this file, pytest cannot import main.py because:
  1. `slowapi` package is not installed locally (it's in the container image).
  2. `main.py` tries to write `/app/startup_error.log` (container-only path).
  3. Shared library imports assume /app/shared is mounted.

This conftest:
  a) Installs stub modules for slowapi and asyncpg.
  b) Patches builtins.open to redirect /app/* log writes to /tmp/.
  c) Ensures PYTHONPATH includes api_gateway/ and services/shared/.
"""
import sys
import os
import types
import asyncio
from unittest.mock import MagicMock, AsyncMock

# ─── PYTHONPATH ───────────────────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GATEWAY = os.path.join(ROOT, "services/api_gateway")
SERVICES = os.path.join(ROOT, "services")

for p in [GATEWAY, SERVICES]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ─── Stub: slowapi ────────────────────────────────────────────────────────────

def _build_slowapi_stub():
    slowapi = types.ModuleType("slowapi")
    errors = types.ModuleType("slowapi.errors")
    util = types.ModuleType("slowapi.util")

    class RateLimitExceeded(Exception):
        pass

    class Limiter:
        def __init__(self, *a, **kw):
            pass
        def limit(self, *a, **kw):
            def decorator(fn):
                return fn
            return decorator

    def _rate_limit_exceeded_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=429, content={"error": "RATE_LIMIT_EXCEEDED"})

    def get_remote_address(request):
        return "127.0.0.1"

    slowapi.Limiter = Limiter
    slowapi._rate_limit_exceeded_handler = _rate_limit_exceeded_handler
    errors.RateLimitExceeded = RateLimitExceeded
    util.get_remote_address = get_remote_address

    slowapi.errors = errors
    slowapi.util = util
    return slowapi, errors, util


_slowapi, _slowapi_errors, _slowapi_util = _build_slowapi_stub()
sys.modules.setdefault("slowapi", _slowapi)
sys.modules.setdefault("slowapi.errors", _slowapi_errors)
sys.modules.setdefault("slowapi.util", _slowapi_util)


if "asyncpg" not in sys.modules:
    asyncpg = types.ModuleType("asyncpg")
    asyncpg.create_pool = AsyncMock()
    asyncpg.Record = dict
    class MockPool:
        pass
    class MockConnection:
        pass
    asyncpg.Pool = MockPool
    asyncpg.Connection = MockConnection
    sys.modules["asyncpg"] = asyncpg


# ─── Patch: redirect /app/*.log writes to /tmp/ ───────────────────────────────
import builtins as _builtins

_real_open = _builtins.open


def _safe_open(file, mode="r", *args, **kwargs):
    if isinstance(file, str) and file.startswith("/app/") and file.endswith(".log"):
        file = "/tmp/" + os.path.basename(file)
    return _real_open(file, mode, *args, **kwargs)


_builtins.open = _safe_open


# ─── Ensure shared/ stubs are loaded before main.py import ───────────────────
# The shared package has its own imports; this seeds them so import doesn't fail.

def _ensure_shared_importable():
    """Make sure `from shared.X import Y` resolves to our local shared/ dir."""
    if "shared" not in sys.modules:
        import importlib
        try:
            importlib.import_module("shared.config")
        except Exception:
            pass

_ensure_shared_importable()


# ─── Stub: PyJWT ──────────────────────────────────────────────────────────────
# Try loading real PyJWT first; only stub if unavailable.
_jwt_real = False
try:
    import jwt as _real_jwt
    if hasattr(_real_jwt, "decode") and hasattr(_real_jwt, "encode"):
        _jwt_real = True
except ImportError:
    pass

if not _jwt_real and "jwt" not in sys.modules:
    import json
    import base64

    class ExpiredSignatureError(Exception):
        pass

    class InvalidTokenError(Exception):
        pass

    def encode(payload, key, algorithm=None):
        payload_json = json.dumps(payload)
        return base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")

    def decode(token, key, algorithms=None):
        try:
            padded = token + "=" * (4 - len(token) % 4)
            payload_json = base64.urlsafe_b64decode(padded.encode()).decode()
            payload = json.loads(payload_json)
            if "exp" in payload:
                import time
                if payload["exp"] < time.time():
                    raise ExpiredSignatureError()
            return payload
        except ExpiredSignatureError:
            raise
        except Exception:
            raise InvalidTokenError()

    jwt_stub = types.ModuleType("jwt")
    jwt_stub.ExpiredSignatureError = ExpiredSignatureError
    jwt_stub.InvalidTokenError = InvalidTokenError
    jwt_stub.encode = encode
    jwt_stub.decode = decode
    sys.modules["jwt"] = jwt_stub

