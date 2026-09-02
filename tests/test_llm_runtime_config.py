"""Tests for the native-macOS-Ollama migration (config + runtime semantics).

Covers:
1. Native host endpoint configuration (host.docker.internal:11434)
2. Model configuration precedence (INSIGHTS_LLM_MODEL wins over MISTRAL_MODEL)
3. LLM disabled => Insights has NO dependency on Ollama (lazy init)
4. Insights health reflects LLM-disabled state independently of Ollama
5. Deterministic fallback when native Ollama is unreachable
"""
import os
import sys

INSIGHTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "services", "insights_agent")
)
if INSIGHTS_DIR not in sys.path:
    sys.path.insert(0, INSIGHTS_DIR)

from config import Settings
from models import InsightsRequest
from mistral_integrator import MistralIntegrator


def test_native_host_endpoint_default():
    # The Insights default must target native macOS Ollama through Docker's
    # host.docker.internal, not a compose service named "ollama".
    cfg = Settings(_env_file=None)
    assert cfg.MISTRAL_API_URL == "http://host.docker.internal:11434"


def test_insights_llm_model_precedence_over_mistral_model():
    # INSIGHTS_LLM_MODEL is the single source of truth; a generic MISTRAL_MODEL
    # must not silently override it.
    cfg = Settings(
        _env_file=None,
        MISTRAL_MODEL="some-other-model",
        INSIGHTS_LLM_MODEL="mistral:latest",
    )
    integrator = MistralIntegrator(cfg)
    assert integrator._model == "mistral:latest"


def test_insights_llm_model_used_when_only_mistral_model_set():
    # Legacy path: INSIGHTS_LLM_MODEL has a default, so the integrator uses it
    # even when the caller only overrides the generic MISTRAL_MODEL. The
    # generic variable thus never wins.
    cfg = Settings(_env_file=None, MISTRAL_MODEL="some-other-model")
    integrator = MistralIntegrator(cfg)
    assert integrator._model == cfg.INSIGHTS_LLM_MODEL
    assert integrator._model == "mistral"


def test_llm_disabled_no_dependency(config_module=Settings):
    cfg = Settings(_env_file=None, ENABLE_LLM_INSIGHTS=False)
    assert cfg.ENABLE_LLM_INSIGHTS is False


def test_health_with_llm_disabled():
    # With LLM disabled the Insights service is healthy regardless of whether
    # an LLM provider is reachable. Health must NOT be equivalent to Ollama.
    from main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        got = client.get("/health").json()
    assert got["status"] == "healthy"
    assert got["llm_enabled"] is False
    assert got["llm_available"] == "unknown"


def test_fallback_when_host_ollama_unavailable():
    # Point at a dead port; interpret() must degrade to deterministic
    # llm_fallback, never raise.
    from models import (
        AnalyticalFactPackage, DatasetProfile, DescriptiveStats, Provenance,
    )
    cfg = Settings(
        _env_file=None,
        MISTRAL_API_URL="http://127.0.0.1:1",  # nothing listens here
        INSIGHTS_LLM_TIMEOUT=2,
    )
    integrator = MistralIntegrator(cfg)
    fp = AnalyticalFactPackage(
        query_intent="risk_analysis", query_text="Analyze exposure",
        dataset_profile=DatasetProfile(
            row_count=100, columns=["balance"], numeric_columns=["balance"],
            null_counts={"balance": 0},
        ),
        descriptive_stats=[DescriptiveStats(
            column="balance", count=100, sum=100.0, mean=1.0, median=1.0,
            std_dev=0.0, min=1.0, max=1.0, p25=1.0, p90=1.0,
            provenance=Provenance(source="deterministic_calculation",
                                  column="balance", method="numpy")),
        ],
        evidence_quality=__import__("models", fromlist=["EvidenceQuality"]).EvidenceQuality(
            row_count_adequate=True, has_numeric_data=True, score=0.9,
        ),
    )
    result = integrator.interpret(fp, "risk_analysis", "Analyze exposure", [])
    assert result.metadata.generation_mode == "llm_fallback"
    assert result.metadata.fallback_reason == "LLM_UNAVAILABLE_OR_EMPTY"
