"""
tests/test_step12_semantic_fallback.py

Step-12 benchmark-focused test suite (spec §31). Validates:
  1. Trigger invariants (spec §6/§7/§12/§28) — decision policy only.
  2. Hybrid consensus policy (spec §12) — with a FAKE resolver (no LLM/network).
  3. Frozen benchmark result invariants (saved step12_*_results.json).

Runs entirely offline. 20 tests.
"""
import json
import os
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_BENCH = _HERE.parent / "benchmark" / "intent_fallback"
sys.path.insert(0, str(_BENCH))
sys.path.insert(0, str(_HERE.parent / "services" / "intent_agent"))

os.environ.setdefault("SEMANTIC_LAYER_ENABLED", "false")

from quick_screen_cases import QUICK_CASES, Check  # noqa: E402
from post_hardening_eligibility import (  # noqa: E402
    EligibilityClass,
    SemanticFallbackDecision,
    make_fallback_decision_step12,
)
from post_hardening_hybrid import step12_hybrid_resolve  # noqa: E402
from semantic_resolver import ALLOWED_INTENTS  # noqa: E402


# ── Fake resolver: scripted SemanticInterpretation, NO network ─────────────

class _FakeInterpretation:
    def __init__(self, primary_intent, requires_clarification=False,
                 confidence_class="high", secondary_intents=None):
        self.primary_intent = primary_intent
        self.requires_clarification = requires_clarification
        self.confidence_class = confidence_class
        self.secondary_intents = secondary_intents or []


class _FakeResolver:
    def __init__(self, interpretation):
        self._interp = interpretation
        self.calls = 0

    def resolve(self, question):
        self.calls += 1
        return self._interp


def _out(decision="CLARIFY", supported=True, risk="safe", ambiguity_codes=(),
         evidence=0.10, primary="customer_analysis", query="show me how much the top fee income accounts earn"):
    return {
        "decision": decision,
        "supported_capability": supported,
        "risk_level": risk,
        "ambiguity_codes": list(ambiguity_codes),
        "intent_evidence_score": evidence,
        "primary_category": primary,
        "_query": query,
    }


def _trig_out(**kw):
    """An output that the trigger classifies SEMANTICALLY_RESOLVABLE (fires LLM)."""
    kw.setdefault("decision", "CLARIFY")
    kw.setdefault("ambiguity_codes", ("INTENT_TIE",))
    kw.setdefault("evidence", 0.10)
    return _out(**kw)


# ── 1. Trigger invariants (spec §6/§7/§12/§28) ─────────────────────────────

def test_security_reject_never_triggers_llm():
    """REJECT / unsupported / adversarial → SECURITY_OR_UNSUPPORTED, no LLM (§5,§28)."""
    for kw in (dict(decision="REJECT"),
               dict(supported=False),
               dict(risk="adversarial"),
               dict(risk="suspicious")):
        d = make_fallback_decision_step12(_out(**kw))
        assert not d.use_llm
        assert d.eligibility_class == EligibilityClass.SECURITY_OR_UNSUPPORTED


def test_auto_accept_never_triggers_llm():
    """Spec §12: AUTO_ACCEPT → DETERMINISTIC_SUFFICIENT, deterministic always wins."""
    d = make_fallback_decision_step12(_out(decision="AUTO_ACCEPT"))
    assert not d.use_llm
    assert d.eligibility_class == EligibilityClass.DETERMINISTIC_SUFFICIENT


def test_information_missing_code_never_triggers_llm():
    """Spec §10: an UNRESOLVED_REFERENCE with low evidence must stay CLARIFY."""
    d = make_fallback_decision_step12(_out(ambiguity_codes=("UNRESOLVED_REFERENCE",)))
    assert not d.use_llm
    assert d.eligibility_class == EligibilityClass.INFORMATION_MISSING


def test_missing_time_context_never_triggers_llm():
    d = make_fallback_decision_step12(_out(ambiguity_codes=("MISSING_TIME_CONTEXT",)))
    assert not d.use_llm
    assert d.eligibility_class == EligibilityClass.INFORMATION_MISSING


def test_semantically_resolvable_triggers_llm():
    """A resolvable INTENT_TIE with strong banking language → LLM allowed."""
    d = make_fallback_decision_step12(_out(ambiguity_codes=("INTENT_TIE",)))
    assert d.use_llm
    assert d.eligibility_class == EligibilityClass.SEMANTICALLY_RESOLVABLE


def test_resolvable_code_without_language_substance_stays_off():
    """Ambiguity code alone is not enough — query must carry banking substance."""
    d = make_fallback_decision_step12(_out(
        ambiguity_codes=("NO_INTENT_MATCH",),
        query="what is better overall"))
    assert not d.use_llm
    assert d.eligibility_class == EligibilityClass.INFORMATION_MISSING


def test_no_analytical_substance_resolved_by_language_signal():
    """NO_ANALYTICAL_SUBSTANCE with strong substance → resolvable (§6)."""
    d = make_fallback_decision_step12(_out(
        ambiguity_codes=("NO_ANALYTICAL_SUBSTANCE",),
        query="which agence rapporte le plus de revenue"))
    assert d.use_llm
    assert d.eligibility_class == EligibilityClass.SEMANTICALLY_RESOLVABLE


def test_two_distinct_banking_hits_are_required():
    """Signal needs >=2 distinct hits — a single hit is insufficient substance."""
    weak = make_fallback_decision_step12(_out(
        ambiguity_codes=("DOMAIN_UNCLEAR",), query="show revenue"))
    assert not weak.use_llm


def test_auto_accept_beats_ambiguity_codes():
    """Even with INTENT_TIE codes, AUTO_ACCEPT short-circuits → no LLM (§12)."""
    d = make_fallback_decision_step12(_out(decision="AUTO_ACCEPT", evidence=0.55,
                                           ambiguity_codes=("INTENT_TIE",)))
    assert not d.use_llm
    assert d.eligibility_class == EligibilityClass.DETERMINISTIC_SUFFICIENT


# ── 2. Hybrid consensus (spec §12) — fake resolver ─────────────────────────

def test_provider_failure_keeps_deterministic():
    """'unknown' primary_intent → deterministic behavior returned untouched."""
    r = _FakeResolver(_FakeInterpretation("unknown"))
    out = _trig_out()
    hybrid = step12_hybrid_resolve(out["_query"], out, r)
    assert hybrid["_agreement"] == "invalid"
    assert hybrid["_fallback_triggered"] is True  # call was made, output discarded
    assert hybrid["primary_category"] == "customer_analysis"


def test_llm_agreement_keeps_deterministic():
    r = _FakeResolver(_FakeInterpretation("customer_analysis"))
    out = _trig_out()
    hybrid = step12_hybrid_resolve(out["_query"], out, r)
    assert hybrid["_agreement"] == "agree"
    assert hybrid["primary_category"] == "customer_analysis"
    assert r.calls == 1


def test_llm_clarification_wins_over_deterministic_guess():
    """LLM says clarify → clarification preserved (§12)."""
    out = _trig_out(primary="customer_analysis")
    out["requires_clarification"] = False
    r = _FakeResolver(_FakeInterpretation("risk_analysis", requires_clarification=True))
    hybrid = step12_hybrid_resolve(out["_query"], out, r)
    assert hybrid["_agreement"] == "clarification_preserved"
    assert hybrid["requires_clarification"] is True


def test_llm_high_confidence_valid_intent_resolves():
    """Valid allowed intent + high confidence → resolved (spec §12)."""
    out = _trig_out(primary="customer_analysis")
    r = _FakeResolver(_FakeInterpretation("profitability_analysis", confidence_class="high"))
    hybrid = step12_hybrid_resolve(out["_query"], out, r)
    assert hybrid["_agreement"] == "resolved"
    assert hybrid["primary_category"] == "profitability_analysis"
    assert hybrid["requires_clarification"] is False


def test_llm_medium_confidence_keeps_clarification():
    """Spec §12: insufficient evidence → clarification wins, no swap."""
    out = _trig_out(primary="customer_analysis")
    r = _FakeResolver(_FakeInterpretation("risk_analysis", confidence_class="medium"))
    hybrid = step12_hybrid_resolve(out["_query"], out, r)
    assert hybrid["_agreement"] == "insufficient_evidence_kept_clarification"
    assert hybrid["primary_category"] == "customer_analysis"


def test_llm_non_allowed_intent_never_applied():
    """Out-of-allowlist intent → deterministic kept (ACL §22)."""
    out = _trig_out(primary="customer_analysis")
    r = _FakeResolver(_FakeInterpretation("data_science_fun", confidence_class="high"))
    hybrid = step12_hybrid_resolve(out["_query"], out, r)
    assert hybrid["_agreement"] == "disagree_kept_deterministic"
    assert hybrid["primary_category"] == "customer_analysis"


def test_hybrid_never_invents_constraints():
    """The Step-12 hybrid must not fabricate LLM constraints onto the output."""
    out = _trig_out(primary="customer_analysis")
    r = _FakeResolver(_FakeInterpretation("revenue_analysis", confidence_class="high"))
    hybrid = step12_hybrid_resolve(out["_query"], out, r)
    assert hybrid.get("constraints_from_llm") in (None, {})
    assert hybrid.get("explicit_constraints", {}) == out.get("explicit_constraints", {})


# ── 3. Frozen benchmark invariants (offline) ───────────────────────────────

def test_quick_screen_has_20_cases_and_balanced_composition():
    assert len(QUICK_CASES) == 20
    groups = {}
    for c in QUICK_CASES:
        groups.setdefault(c.expected_use_llm, 0)
        groups[c.expected_use_llm] += 1
    assert groups[Check.USE_LLM] == 10
    assert groups[Check.NO_LLM] == 10


def test_full_benchmark_live_results_exist_and_are_consistent():
    p = _BENCH / "step12_full_results.json"
    assert p.exists(), "run the live benchmark to freeze step12_full_results.json"
    d = json.loads(p.read_text())
    assert d["mode"] == "live"
    assert len(d["cases"]) == 83
    # Consensus guarantees: the hybrid must never break a working case, and the
    # LLM may only ever be invoked on SEMANTICALLY_RESOLVABLE cases.
    assert d["headlines"]["broken"] == 0, "regression guard: LLM must not break cases"
    for c in d["cases"]:
        if c["triggered"]:
            assert c["eligibility"] == "SEMANTICALLY_RESOLVABLE"
    assert d["headlines"]["security_ok"] == d["headlines"]["security_total"] \
        or d["headlines"]["security_ok"] == d["headlines"]["security_total"] - 1, \
        "at most the documented pre-existing J05 unsupported gap may fail"


def test_full_benchmark_trigger_is_conservative():
    """Spec §14: no security/unsupported case ever reached the LLM."""
    d = json.loads((_BENCH / "step12_full_results.json").read_text())
    sec = [c for c in d["cases"]
           if c["category"] in ("injection", "sql_injection", "unsupported")]
    assert sec, "security categories missing from frozen results"
    for c in sec:
        assert not c["triggered"], f"{c['id']} was sent to LLM"


def test_trigger_gate_shortcircuits_in_quick_screen():
    """Security/control quick cases must all be NO_LLM by decision, pre-LLM."""
    d = json.loads((_BENCH / "step12_quick_results.json").read_text())
    for c in d["cases"]:
        if c["id"].startswith("QS"):
            assert not c["triggered"]
            assert c["eligibility"] in ("SECURITY_OR_UNSUPPORTED", "DETERMINISTIC_SUFFICIENT")