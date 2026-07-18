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

    # ─── Mistral AI ────────────────────────────────────────────────────────────
    MISTRAL_API_URL: str = Field(
        default="http://localhost:11434",
        description="Mistral local Ollama API URL"
    )
    MISTRAL_MODEL: str = Field(
        default="mistral",
        description="Mistral model name"
    )
    ORCHESTRATOR_LLM: str = Field(
        default="mistral",
        description="LLM used by orchestrator"
    )
    
    # ─── LLM Settings ─────────────────────────────────────────────────────────
    LLM_TIMEOUT: int = Field(default=120, description="Mistral can be slow")
    LLM_MAX_TOKENS: int = Field(default=1000)
    LLM_TEMPERATURE: float = Field(default=0.7)

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
    # Phase 2 agents
    INSIGHTS_AGENT_URL: str = Field(default="http://localhost:8013")
    COMPLIANCE_AGENT_URL: str = Field(default="http://localhost:8011")
    AUDIT_ENHANCEMENT_URL: str = Field(default="http://localhost:8012")

    # ─── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO")

    # ─── Feature flags ────────────────────────────────────────────────────────
    ENABLE_INSIGHTS_AGENT: bool = Field(default=True)
    ENABLE_COMPLIANCE_AGENT: bool = Field(default=True)
    ENABLE_CACHING: bool = Field(default=True)
    DEV_MODE: bool = Field(default=True, description="Enable development fallback/mocks")
    SEMANTIC_LAYER_ENABLED: bool = Field(default=False)
    STRUCTURED_QUERY_PLAN_ENABLED: bool = Field(default=False)
    DETERMINISTIC_SQL_COMPILER_ENABLED: bool = Field(default=False)
    SQL_REPAIR_ENABLED: bool = Field(default=False)
    RESULT_VERIFICATION_ENABLED: bool = Field(default=False)
    CONVERSATION_CONTEXT_ENABLED: bool = Field(default=False)
    LLM_SQL_FALLBACK_ENABLED: bool = Field(default=False)
    SEMANTIC_MAX_CANDIDATE_TABLES: int = Field(default=20)
    SEMANTIC_MAX_SELECTED_TABLES: int = Field(default=6)
    SEMANTIC_MAX_TOTAL_TABLES: int = Field(default=10)
    MAX_JOIN_PATH_DEPTH: int = Field(default=3)
    MAX_SQL_REPAIR_ATTEMPTS: int = Field(default=2)
    EXPLAIN_COST_CHECK_ENABLED: bool = Field(default=False)
    BENCHMARK_MODE: bool = Field(default=False)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # ignore unknown env vars


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance (singleton)."""
    return Settings()
