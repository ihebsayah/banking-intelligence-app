import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    DATABASE_URL: str = Field(
        default="postgresql://banking_user:securepass123@localhost:5432/banking_dev"
    )
    # Native macOS Ollama is the development default (outside Docker). Inside
    # Docker, host.docker.internal resolves to the macOS host where Ollama runs.
    MISTRAL_API_URL: str = Field(default="http://host.docker.internal:11434")
    # Model source of truth for the Insights Agent: INSIGHTS_LLM_MODEL wins.
    # MISTRAL_MODEL is kept only as a legacy fallback when INSIGHTS_LLM_MODEL is
    # unset — it never overrides an explicitly set INSIGHTS_LLM_MODEL.
    MISTRAL_MODEL: str = Field(default="mistral")
    INSIGHTS_LLM_MODEL: str = Field(default="mistral")
    INSIGHTS_LLM_TIMEOUT: int = Field(default=30)  # seconds; STEP 5 will tune
    INSIGHTS_LLM_TEMPERATURE: float = Field(default=0.1)
    INSIGHTS_LLM_MAX_TOKENS: int = Field(default=512)
    LOG_LEVEL: str = Field(default="INFO")
    ENABLE_LLM_INSIGHTS: bool = Field(default=False)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
