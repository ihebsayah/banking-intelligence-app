"""
services/shared/logger.py
Structured JSON logging for all banking microservices.
Produces JSON log lines compatible with log aggregators (ELK, CloudWatch, etc.)
"""
import logging
import json
import sys
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.
    Adds service_name, timestamp (ISO-8601 UTC), and level to every record.
    """

    def __init__(self, service_name: str = "banking-service"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include any extra fields passed via `extra=` kwarg
        extra_keys = {
            k: v
            for k, v in record.__dict__.items()
            if k not in logging.LogRecord.__init__.__code__.co_varnames
            and not k.startswith("_")
            and k
            not in (
                "args",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "message",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "taskName",
                "thread",
                "threadName",
            )
        }
        if extra_keys:
            log_entry["extra"] = extra_keys

        return json.dumps(log_entry, default=str)


def get_logger(name: str, service_name: Optional[str] = None) -> logging.Logger:
    """
    Return a configured logger instance.

    Args:
        name:         Logger name (usually __name__ of the calling module).
        service_name: Human-readable service label (e.g. 'api-gateway').
                      Falls back to SERVICE_NAME env var or the logger name.

    Returns:
        A logging.Logger instance that writes JSON to stdout.
    """
    service = service_name or os.getenv("SERVICE_NAME", name)
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    logger.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(JSONFormatter(service_name=service))
    logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    return logger
