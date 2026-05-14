"""
services/shared/config.py
Centralized configuration loaded from environment variables.
All services import Settings from here.
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses pydantic-settings for validation and type coercion.
    """

    # ─── Database URLs ────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql://banking_user:securepass123@localhost:5432/banking_dev",
        description="Main banking PostgreSQL connection string",
    )
    AUDIT_DATABASE_URL: str = Field(
        default="postgresql://audit_user:securepass123@localhost:5433/audit_logs",
        description="Audit-only PostgreSQL connection string",
    )
    EMBEDDINGS_DATABASE_URL: str = Field(
        default="postgresql://embedding_user:securepass123@localhost:5434/embeddings",
        description="pgvector PostgreSQL connection string",
    )

    # ─── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string",
    )

    # ─── Claude AI ────────────────────────────────────────────────────────────
    CLAUDE_API_KEY: str = Field(
        default="",
        description="Anthropic Claude API key",
    )

    # ─── JWT Auth ─────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(
        default="change-this-in-production-do-not-use-in-prod",
        description="JWT signing secret. MUST be overridden in production.",
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRE_MINUTES: int = Field(default=480, description="Token TTL in minutes (8 hours)")

    # ─── Service URLs ─────────────────────────────────────────────────────────
    AUDIT_AGENT_URL: str = Field(default="http://localhost:8008")
    ORCHESTRATOR_URL: str = Field(default="http://localhost:8001")
    INTENT_AGENT_URL: str = Field(default="http://localhost:8002")
    SCHEMA_AGENT_URL: str = Field(default="http://localhost:8003")
    ENTITY_RESOLUTION_AGENT_URL: str = Field(default="http://localhost:8004")
    SQL_AGENT_URL: str = Field(default="http://localhost:8005")
    VALIDATION_AGENT_URL: str = Field(default="http://localhost:8006")
    EXECUTION_AGENT_URL: str = Field(default="http://localhost:8007")
    EMBEDDING_SERVICE_URL: str = Field(default="http://localhost:8009")

    # ─── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO")

    # ─── Feature flags ────────────────────────────────────────────────────────
    ENABLE_INSIGHTS_AGENT: bool = Field(default=False)
    ENABLE_CACHING: bool = Field(default=True)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # ignore unknown env vars


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance (singleton)."""
    return Settings()
