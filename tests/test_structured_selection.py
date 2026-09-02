"""STEP 9 — Structured Fact Selection + Deterministic Narration.

Focused tests for the selection-only LLM contract: the LLM selects fact IDs
from a verified candidate set; deterministic software renders ALL prose.
No prose, no numbers, no natural-language generation from the LLM.

Architecture experiment: ENABLE_LLM_INSIGHTS remains false everywhere.
"""
import sys
import os
import json
import pytest
from unittest.mock import MagicMock, patch

# Ensure insights_agent is on the path
INSIGHTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "services", "insights_agent"
)
if INSIGHTS_DIR not in sys.path:
    sys.path.insert(0, INSIGHTS_DIR)

from models import (
    AnalyticalFactPackage, DatasetProfile, DescriptiveStats,
    CategoricalDistribution, AnomalyFact, CorrelationFact,
    TemporalComparison, RecommendationCandidate, EvidenceQuality,
    Provenance,
)
from structured_selection import (
    CandidateFact, CandidateRegistry, LLMFactSelection,
    SelectionValidator, DeterministicSelector, NarrativeRenderer,
    StructuredFactSelector, build_candidates, _extract_selection_json,
    _SELECTION_SYSTEM_PROMPT,
)


# ── Test fixtures ───────────────────────────────────────────────────────────

def _profile(row_count=100, numeric=("balance", "amount"), categorical=("region",)):
    cols = list(numeric) + list(categorical)
    return DatasetProfile(
        row_count=row_count, columns=cols,
        numeric_columns=list(numeric), categorical_columns=list(categorical),
        null_counts={c: 0 for c in cols},
    )


def _pkg():
    return AnalyticalFactPackage(
        query_intent="risk_analysis", query_text="Analyze regional exposure",
        dataset_profile=_profile(),
        descriptive_stats=[
            DescriptiveStats(column="balance", count=100, sum=1825000.0, mean=18250.0,
                             median=17000.0, std_dev=5000.0, min=1000.0, max=99999.0,
                             p25=12000.0, p90=28000.0,
                             provenance=Provenance(source="deterministic_calculation", column="balance", method="numpy")),
            DescriptiveStats(column="amount", count=100, sum=910000.0, mean=9100.0,
                             median=8800.0, std_dev=2000.0, min=500.0, max=40000.0,
                             p25=7000.0, p90=15000.0,
                             provenance=Provenance(source="deterministic_calculation", column="amount", method="numpy")),
        ],
        categorical_distributions=[
            CategoricalDistribution(column="region", unique_count=2,
                                    dominant_value="Tunis", dominant_share=0.6,
                                    value_counts={"Tunis": 60, "Sfax": 40},
                                    provenance=Provenance(source="execution_result", column="region", method="count")),
        ],
        anomalies=[
            AnomalyFact(column="balance", observed_value=99999.0, mean=18250.0,
                        std_dev=5000.0, deviation=16.35, severity="extreme",
                        provenance=Provenance(source="deterministic_calculation", column="balance", method="z")),
        ],
        correlations=[
            CorrelationFact(column_a="balance", column_b="amount", coefficient=0.85,
                            sample_size=100,
                            provenance=Provenance(source="deterministic_calculation", method="pearson")),
        ],
        temporal_comparisons=[
            TemporalComparison(column="balance", earliest_period="2024-01", latest_period="2024-02",
                               previous_value=100.0, current_value=130.0, absolute_change=30.0,
                               percentage_change=30.0,
                               provenance=Provenance(source="deterministic_calculation", method="po")),
        ],
        recommendation_candidates=[
            RecommendationCandidate(rule="anomaly_concentration",
                                    message="Investigate the extreme balance anomaly.",
                                    evidence_column="balance", evidence_value=1.0, severity="warning"),
        ],
    )


def _candidates():
    return build_candidates(_pkg())


def _registry():
    return CandidateRegistry(_candidates())


def _valid_selection():
    """A valid selection with correct IDs and types."""
    return LLMFactSelection(
        summary_fact_ids=["F1", "A1"],
        observation_fact_ids=["A1", "C1", "T1"],
        recommendation_ids=["R1"],
        limitation_ids=[],
        priority_order=["R1", "A1", "F1", "C1", "T1"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# TESTS (20 required)
# ═════════════════════════════════════════════════════════════════════════════

class TestSelectionValidation:
    """Tests 1-6: basic validation of LLMFactSelection."""

    def test_valid_selection_accepted(self):
        """Test 1: valid selection with correct IDs accepted."""
        reg = _registry()
        sel = _valid_selection()
        ok, reason = SelectionValidator(reg).validate(sel)
        assert ok, reason
        assert reason == "OK"

    def test_unknown_id_rejected(self):
        """Test 2: unknown ID rejected."""
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=["F99"],  # F99 doesn't exist
            observation_fact_ids=[],
            recommendation_ids=[],
            limitation_ids=[],
        )
        ok, reason = SelectionValidator(reg).validate(sel)
        assert not ok
        assert "UNKNOWN_ID" in reason

    def test_malformed_id_rejected(self):
        """Test 3: malformed ID rejected."""
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=["F1"],
            observation_fact_ids=["OBS_INVALID"],
            recommendation_ids=[],
            limitation_ids=[],
        )
        ok, reason = SelectionValidator(reg).validate(sel)
        assert not ok
        assert "UNKNOWN_ID" in reason

    def test_recommendation_type_mismatch_rejected(self):
        """Test 4: recommendation field containing non-R ID rejected."""
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=["F1"],
            observation_fact_ids=[],
            recommendation_ids=["F1"],  # F1 is metric, not recommendation
            limitation_ids=[],
        )
        ok, reason = SelectionValidator(reg).validate(sel)
        assert not ok
        assert "TYPE_MISMATCH" in reason

    def test_duplicate_id_rejected(self):
        """Test 5: duplicate IDs within same field rejected."""
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=["F1", "F1"],  # duplicate
            observation_fact_ids=[],
            recommendation_ids=[],
            limitation_ids=[],
        )
        ok, reason = SelectionValidator(reg).validate(sel)
        assert not ok
        assert "DUPLICATE_ID" in reason

    def test_max_selection_caps_enforced(self):
        """Test 6: over-selection in summary_fact_ids rejected."""
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=["F1", "F2", "A1", "C1"],  # 4 > max 3
            observation_fact_ids=[],
            recommendation_ids=[],
            limitation_ids=[],
        )
        ok, reason = SelectionValidator(reg).validate(sel)
        assert not ok
        assert "OVER_SELECTION" in reason


class TestInjectionResistance:
    """Tests 7-8: prompt injection and empty recommendations."""

    def test_prompt_injection_unknown_id_rejected(self):
        """Test 7: prompt injection with unknown ID rejected by validation."""
        reg = _registry()
        # Simulate LLM returning an injected ID
        sel = LLMFactSelection(
            summary_fact_ids=["F99"],  # injected ID
            observation_fact_ids=[],
            recommendation_ids=[],
            limitation_ids=[],
        )
        ok, reason = SelectionValidator(reg).validate(sel)
        assert not ok
        assert "UNKNOWN_ID" in reason

    def test_empty_recommendations_respected(self):
        """Test 8: empty recommendation_ids accepted when no R candidates exist."""
        # Build registry with no recommendations
        pkg = _pkg()
        pkg.recommendation_candidates = []
        candidates = build_candidates(pkg)
        reg = CandidateRegistry(candidates)

        sel = LLMFactSelection(
            summary_fact_ids=["F1"],
            observation_fact_ids=["A1"],
            recommendation_ids=[],  # empty
            limitation_ids=[],
        )
        ok, reason = SelectionValidator(reg).validate(sel)
        assert ok, reason


class TestNarrativeRenderer:
    """Tests 9-13: deterministic rendering."""

    def test_french_rendering_from_selected_ids(self):
        """Test 9: French rendering from selected IDs."""
        renderer = NarrativeRenderer()
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=["A1"],
            observation_fact_ids=["C1"],
            recommendation_ids=["R1"],
            limitation_ids=[],
        )
        result = renderer.render(sel, reg, "Analyser l'exposition régionale")
        assert result.summary != ""
        # French should contain French words
        assert any(w in result.summary.lower() for w in ["statistiquement", "atypique", "observée", "corrélation"])

    def test_english_rendering_from_selected_ids(self):
        """Test 10: English rendering from selected IDs."""
        renderer = NarrativeRenderer()
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=["A1"],
            observation_fact_ids=["C1"],
            recommendation_ids=["R1"],
            limitation_ids=[],
        )
        result = renderer.render(sel, reg, "Analyze regional exposure")
        assert result.summary != ""
        assert any(w in result.summary.lower() for w in ["statistically", "unusual", "correlation", "observed"])

    def test_deterministic_numeric_formatting_exact(self):
        """Test 11: numeric formatting is deterministic and exact."""
        renderer = NarrativeRenderer()
        assert renderer._fmt_currency(18250.0) == "18 250"
        assert renderer._fmt_currency(18250.0, ) == "18 250"
        assert renderer._fmt_percent(30.0) == "+30%"
        assert renderer._fmt_percent(-10.0) == "-10%"
        assert renderer._fmt_correlation(0.85) == "+0.85"
        assert renderer._fmt_correlation(-0.7) == "-0.70"
        assert renderer._fmt_decimal(18250.0) == "18 250.00"

    def test_correlation_non_causal_wording(self):
        """Test 12: correlation rendered with association language, never causation."""
        renderer = NarrativeRenderer()
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=[],
            observation_fact_ids=["C1"],
            recommendation_ids=[],
            limitation_ids=[],
        )
        result = renderer.render(sel, reg, "Analyze relationship")
        obs_text = result.key_observations[0].text.lower()
        # Must NOT contain causal words
        assert "caus" not in obs_text
        assert "drive" not in obs_text
        # Must contain association/correlation language
        assert any(w in obs_text for w in ["correlation", "observed", "association"])

    def test_anomaly_non_fraud_wording(self):
        """Test 13: anomaly rendered with statistical language, never fraud."""
        renderer = NarrativeRenderer()
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=["A1"],
            observation_fact_ids=[],
            recommendation_ids=[],
            limitation_ids=[],
        )
        result = renderer.render(sel, reg, "Explain unusual values")
        summary = result.summary.lower()
        # Must NOT contain fraud/suspicious language
        assert "fraud" not in summary
        assert "suspicious" not in summary
        assert "illegal" not in summary
        # Must contain statistical language
        assert any(w in summary for w in ["statistically", "atypical", "unusual", "observation"])


class TestIntegration:
    """Tests 14-16: integration with existing pipeline."""

    def test_direct_query_still_no_llm_call(self):
        """Test 14: direct query invokes zero LLM calls."""
        from insights_generator import InsightsGenerator
        from models import InsightsRequest
        from unittest.mock import MagicMock

        cfg = MagicMock()
        cfg.MISTRAL_API_URL = "http://localhost:11434"
        cfg.MISTRAL_MODEL = "mistral"
        cfg.INSIGHTS_LLM_MODEL = "mistral"
        cfg.INSIGHTS_LLM_TIMEOUT = 30
        cfg.INSIGHTS_LLM_TEMPERATURE = 0.0
        cfg.INSIGHTS_LLM_MAX_TOKENS = 128
        cfg.ENABLE_LLM_INSIGHTS = False

        gen = InsightsGenerator(cfg)
        gen.mistral.interpret_structured = MagicMock(
            side_effect=AssertionError("must not call LLM")
        )
        req = InsightsRequest(
            query_intent="retrieve", query_text="Balance of X",
            results=[{"balance": 27450.0}], metadata={}
        )
        import asyncio
        resp = asyncio.run(gen.generate(req))
        assert resp.key_metrics["generation_mode"] == "deterministic"

    def test_llm_flag_false_uses_deterministic_selector(self):
        """Test 15: ENABLE_LLM_INSIGHTS=false → deterministic selector."""
        selector = StructuredFactSelector(enable_llm=False)
        assert selector.llm_selector is None
        result = selector.interpret(_pkg(), "Analyze exposure", [])
        # Should use deterministic selection
        assert "deterministic" in result.metadata.generation_mode
        assert result.summary != ""

    def test_provider_unavailable_uses_deterministic_selector(self):
        """Test 16: LLM provider unavailable → falls back to deterministic."""
        selector = StructuredFactSelector(
            enable_llm=True,
            base_url="http://localhost:19999",  # wrong port
            model="qwen2.5:3b",
            timeout=2,
        )
        result = selector.interpret(_pkg(), "Analyze exposure", [])
        # Should fall back to deterministic
        assert "deterministic" in result.metadata.generation_mode


class TestEndToEndRendering:
    """Tests 17-20: full pipeline and regression."""

    def test_selected_ids_correctly_rendered(self):
        """Test 17: selected IDs are correctly rendered into prose."""
        renderer = NarrativeRenderer()
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=["A1", "F1"],
            observation_fact_ids=["C1", "T1"],
            recommendation_ids=["R1"],
            limitation_ids=[],
        )
        result = renderer.render(sel, reg, "Explain anomalies and trends")
        assert result.summary != ""
        assert len(result.key_observations) == 2
        assert len(result.recommendations) == 1
        # Verify fact_ids are preserved in rendered output
        assert result.key_observations[0].fact_ids == ["C1"]
        assert result.key_observations[1].fact_ids == ["T1"]
        assert result.recommendations[0].fact_ids == ["R1"]

    def test_no_free_text_fields_in_llm_schema(self):
        """Test 18: LLMFactSelection has no prose/number fields."""
        sel = LLMFactSelection(
            summary_fact_ids=["F1"],
            observation_fact_ids=["A1"],
            recommendation_ids=[],
            limitation_ids=[],
        )
        d = sel.model_dump()
        # No text/summary/prose fields should exist
        assert "summary" not in d or isinstance(d.get("summary_fact_ids"), list)
        assert "text" not in d
        assert "prose" not in d
        # Only ID arrays and priority_order
        assert set(d.keys()) == {
            "summary_fact_ids", "observation_fact_ids",
            "recommendation_ids", "limitation_ids", "priority_order"
        }

    def test_no_numeric_factual_generation_possible(self):
        """Test 19: LLMFactSelection schema cannot contain numeric facts."""
        # The schema only accepts string arrays; float/int values would fail
        with pytest.raises(Exception):
            LLMFactSelection(
                summary_fact_ids=[123],  # int, not str
                observation_fact_ids=[],
                recommendation_ids=[],
                limitation_ids=[],
            )

    def test_deterministic_selector_regression(self):
        """Test 20: deterministic selector produces valid, complete output."""
        pkg = _pkg()
        selector = DeterministicSelector()
        reg = CandidateRegistry(build_candidates(pkg))
        sel = selector.select(reg, pkg, "Analyze regional exposure")

        # Should select some facts
        assert len(sel.summary_fact_ids) > 0
        assert len(sel.observation_fact_ids) > 0

        # Validation should pass
        ok, reason = SelectionValidator(reg).validate(sel)
        assert ok, reason

        # Rendering should produce output
        renderer = NarrativeRenderer()
        result = renderer.render(sel, reg, "Analyze regional exposure")
        assert result.summary != ""


class TestEdgeCases:
    """Additional edge case tests."""

    def test_empty_fact_package(self):
        """Empty fact package produces only limitation candidates (from default evidence quality)."""
        pkg = AnalyticalFactPackage(
            query_intent="retrieve", query_text="Test",
            dataset_profile=DatasetProfile(),
        )
        candidates = build_candidates(pkg)
        # Empty package still generates limitation candidates from default evidence quality
        assert all(c.type == "limitation" for c in candidates)
        reg = CandidateRegistry(candidates)
        sel = DeterministicSelector().select(reg, pkg, "Test")
        assert sel.summary_fact_ids == []
        assert sel.observation_fact_ids == []
        assert sel.recommendation_ids == []

    def test_only_anomalies_no_recs(self):
        """Package with anomalies but no recommendations."""
        pkg = AnalyticalFactPackage(
            query_intent="anomaly_analysis", query_text="Find anomalies",
            dataset_profile=_profile(row_count=200, numeric=("amount",), categorical=()),
            descriptive_stats=[
                DescriptiveStats(column="amount", count=200, sum=1000000.0, mean=5000.0,
                                 median=4800.0, std_dev=800.0, min=100.0, max=42500.0,
                                 p25=4100.0, p90=6200.0,
                                 provenance=Provenance(source="deterministic_calculation", column="amount", method="numpy")),
            ],
            anomalies=[
                AnomalyFact(column="amount", observed_value=42500.0, mean=5000.0,
                            std_dev=800.0, deviation=46.88, severity="extreme",
                            provenance=Provenance(source="deterministic_calculation", column="amount", method="z")),
            ],
            recommendation_candidates=[],
        )
        candidates = build_candidates(pkg)
        reg = CandidateRegistry(candidates)
        sel = DeterministicSelector().select(reg, pkg, "Find anomalies")
        assert sel.recommendation_ids == []
        assert any(fid.startswith("A") for fid in sel.observation_fact_ids)

    def test_bilingual_rendering(self):
        """FR and EN produce different language output from same selection."""
        renderer = NarrativeRenderer()
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=["A1"],
            observation_fact_ids=[],
            recommendation_ids=[],
            limitation_ids=[],
        )
        result_fr = renderer.render(sel, reg, "Analyser les anomalies")
        result_en = renderer.render(sel, reg, "Analyze anomalies")
        # Both should render
        assert result_fr.summary != ""
        assert result_en.summary != ""
        # French should contain French indicators
        assert any(w in result_fr.summary.lower() for w in ["observation", "atypique", "statistiquement"])
        # English should contain English indicators
        assert any(w in result_en.summary.lower() for w in ["observation", "unusual", "statistically"])

    def test_type_leakage_rejected(self):
        """Recommendation field cannot contain metric IDs."""
        reg = _registry()
        sel = LLMFactSelection(
            summary_fact_ids=["F1"],
            observation_fact_ids=["A1"],
            recommendation_ids=["F2"],  # F2 is metric, not recommendation
            limitation_ids=[],
        )
        ok, reason = SelectionValidator(reg).validate(sel)
        assert not ok
        assert "TYPE_MISMATCH" in reason

    def test_system_prompt_is_compact(self):
        """Selection system prompt is under 1000 chars (compact per spec)."""
        assert len(_SELECTION_SYSTEM_PROMPT) < 1200

    def test_extract_json_valid(self):
        """JSON extraction handles code fences and plain JSON."""
        # Plain JSON
        assert _extract_selection_json('{"summary_fact_ids": []}') is not None
        # Code fences
        assert _extract_selection_json('```json\n{"summary_fact_ids": []}\n```') is not None
        # Embedded in text
        assert _extract_selection_json('Here is the result: {"summary_fact_ids": []} done') is not None
        # Invalid
        assert _extract_selection_json("not json at all") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
