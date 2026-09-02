"""Symbolic grounding & deterministic value rendering (STEP 8 — experiment).

Architecture principle set by STEP 7's failure mode: small local LLMs invent
exact numeric values even at temperature 0.0. STEP 8 changes the LLM contract
so the model reasons and writes ONLY using symbolic fact tokens (``{{F1}}``,
``{{A1}}``, ``{{C1}}``, ``{{T1}}``, ``{{R1}}`` ...). A deterministic software
layer (``FactRenderer``) injects verified presentation values AFTER generation.

- Deterministic software OWNS values. The LLM OWNS language.
- The LLM is never shown exact numeric literals when avoidable.
- ``symbolic_renderer`` is the single source of truth for token schema,
  token->payload building, zero-numeric + token validation, and rendering.

This is an ARCHITECTURE EXPERIMENT. It does not enable production LLM usage;
``ENABLE_LLM_INSIGHTS`` remains false. Nothing here weakens the deterministic
fact layer, SQL safety, or any governance agent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from models import (  # noqa: F401  (re-exported for convenience / introspection)
    AnalyticalFactPackage,
    LLMInsightOutput,
)

logger = __import__("logging").getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Token & boundary constants
# ─────────────────────────────────────────────────────────────────────────────
_MAX_METRIC_COLUMNS = 8
_MAX_ANOMALIES = 10
_MAX_CORRELATIONS = 5
_MAX_TEMPORAL = 5
_MAX_CATEGORICAL = 6

# Fact type letters -> symbolic ID prefixes. Token == "{{" + fact_id + "}}".
_TOKEN_RE = re.compile(r"\{\{\s*([A-Z][A-Z0-9]*)\s*\}\}")
# A numeric literal of any kind: digits, decimal thousands separators, %, sigmas.
_NUMERIC_LITERAL_RE = re.compile(r"-?\d[\d,\.]*\s*%?")
# A parenthetical numeric clause like "(62%)" or "(0.71)" — stripped from
# LLM-facing labels so the model never sees a value it could echo.
_PAREN_NUMERIC_RE = re.compile(r"\([^)]*\d[^)]*\)")

# User-visible bound on generated items (mirrors the old prompt caps).
_MAX_SUMMARY_SENTENCES = 3
_MAX_OBSERVATIONS = 4
_MAX_RECOMMENDATIONS = 3
_MAX_LIMITATIONS = 3

# ── Magnitude classes (deterministic, centralized, documented) ──────────────
# Correlation |r| buckets.
_CORR_THRESH_WEAK = 0.3
_CORR_THRESH_MODERATE = 0.7
# Trend magnitude used ONLY for qualitative language (exact value stays in the
# token; this class never replaces the authoritative rendered value).
_TREND_THRESH = 20.0
# Concentration (dominant categorical share) buckets — NEW centralized default.
# Existing code did not define share classes; documented here as low<0.4,
# moderate 0.4-0.6, high>0.6.
_CONC_THRESH_LOW = 0.4
_CONC_THRESH_MODERATE = 0.6


# ─────────────────────────────────────────────────────────────────────────────
# Value formatting (centralized; NEVER the LLM's job)
# ─────────────────────────────────────────────────────────────────────────────
def format_currency(v: Optional[float], currency: Optional[str] = None) -> str:
    """Format a monetary value with thousands separators; currency suffix when known."""
    if v is None or (isinstance(v, float) and v != v):  # NaN guard
        return "N/A"
    s = f"{v:,.0f}".replace(",", " ")
    if currency:
        return f"{s} {currency}"
    return s


def format_percent(v: Optional[float], decimals: int = 1) -> str:
    """Format a percentage point (0-100 scale already)."""
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    sign = "+" if v > 0 else ""
    return f"{sign}{round(v, decimals):g}%"


def format_count(v: Optional[float]) -> str:
    """Format an integer/count value."""
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    return f"{int(round(v)):,}".replace(",", " ")


def format_decimal(v: Optional[float], decimals: int = 2) -> str:
    """Format a generic decimal conservatively."""
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    return f"{v:,.{decimals}f}".replace(",", " ")


def format_correlation(v: Optional[float]) -> str:
    """Format a Pearson correlation coefficient."""
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    sign = "+" if v > 0 else ""
    return f"{sign}{round(v, 2):.2f}"


def format_score(v: Optional[float], decimals: int = 1) -> str:
    """Generic score formatting (dominant share x100 etc.)."""
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    return f"{round(v, decimals):g}"


def format_value_raw(v: Any) -> str:
    """Render a raw verified value conservatively (no unit metadata)."""
    if v is None:
        return "N/A"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        if v != v:
            return "N/A"
        return f"{v:,.2f}".replace(",", " ")
    return str(v)


# ─────────────────────────────────────────────────────────────────────────────
# Symbolic fact model (internal; raw values never exposed to the LLM payload)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class SymbolicFact:
    fact_id: str
    fact_type: str          # metric | distribution | anomaly | correlation | temporal | recommendation
    token: str              # "{{F1}}"
    label: str              # short human label e.g. "mean loan amount"
    meaning: str            # qualitative description shown to the LLM (no exact number)
    raw_value: Optional[Any] = None          # authoritative value for rendering only
    unit: Optional[str] = None               # e.g. "TND", "€", "%"
    value_kind: str = "raw"                  # currency | percent | count | decimal | correlation | score | raw | text
    recommendation_message: Optional[str] = None  # deterministic message for {{R#}} rendering
    magnitude_class: Optional[str] = None    # qualitative class for the LLM (no number)
    direction: Optional[str] = None          # trend direction: positive/negative/stable


# ─────────────────────────────────────────────────────────────────────────────
# Qualitative metadata helpers (NO numeric literals in LLM-facing text)
# ─────────────────────────────────────────────────────────────────────────────
def _rel_class(r: float) -> str:
    a = abs(r)
    if a < _CORR_THRESH_WEAK:
        return "weak"
    if a < _CORR_THRESH_MODERATE:
        return "moderate"
    return "strong"


def _magnitude_for_pct(pct: Optional[float]) -> str:
    """Qualitative change magnitude (0-100% corpus threshold)."""
    if pct is None:
        return "stable"
    if abs(pct) < 1:
        return "stable"
    if abs(pct) < _TREND_THRESH:
        return "moderate"
    return "large"


def _share_class(share: Optional[float]) -> str:
    if share is None:
        return "moderate"
    if share < _CONC_THRESH_LOW:
        return "low"
    if share < _CONC_THRESH_MODERATE:
        return "moderate"
    return "high"


def _sanitize_label(text: str) -> str:
    """Strip numeric literals (parenthetical or bare, with optional '%') so
    LLM-facing labels carry zero numbers while preserving natural language."""
    stripped = _PAREN_NUMERIC_RE.sub("", text)
    stripped = _NUMERIC_LITERAL_RE.sub("", stripped)
    return re.sub(r"\s+", " ", stripped).strip(" -–")


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic fact builder: verified facts -> symbolic registry
# ─────────────────────────────────────────────────────────────────────────────
def build_symbolic_facts(fact_package: AnalyticalFactPackage) -> List[SymbolicFact]:
    facts: List[SymbolicFact] = []
    ds = fact_package.dataset_profile
    currency = None  # no currency metadata in the package today; leave unset (conservative)

    # Metrics (F) — bounded to top-N numeric columns
    for i, s in enumerate(fact_package.descriptive_stats[:_MAX_METRIC_COLUMNS]):
        col_label = s.column.replace("_", " ")
        facts.append(SymbolicFact(
            fact_id=f"F{i + 1}", fact_type="metric", token=f"{{{{F{i + 1}}}}}",
            label=f"mean {col_label}",
            meaning=f"mean value of {s.column}",
            raw_value=s.mean, unit=currency, value_kind="currency",
        ))

    # Categorical dominant share (D)
    for i, d in enumerate(fact_package.categorical_distributions[:_MAX_CATEGORICAL]):
        facts.append(SymbolicFact(
            fact_id=f"D{i + 1}", fact_type="distribution", token=f"{{{{D{i + 1}}}}}",
            label=f"dominant value of {d.column}",
            meaning=f"the most frequent value of {d.column} is {d.dominant_value!r} "
                    f"({_share_class(d.dominant_share)} concentration)",
            raw_value=d.dominant_value, value_kind="text",
            magnitude_class=_share_class(d.dominant_share),
        ))

    # Anomalies (A) — meaning carries NO numeric literals (no sigma value)
    anomalies = sorted(fact_package.anomalies, key=lambda a: -a.deviation)[:_MAX_ANOMALIES]
    for i, a in enumerate(anomalies):
        facts.append(SymbolicFact(
            fact_id=f"A{i + 1}", fact_type="anomaly", token=f"{{{{A{i + 1}}}}}",
            label=f"{a.severity} anomaly in {a.column}",
            meaning=f"a {a.severity} statistical anomaly in {a.column}",
            raw_value=a.observed_value, unit=currency, value_kind="currency",
            magnitude_class=a.severity,
        ))

    # Correlations (C)
    corrs = sorted(fact_package.correlations, key=lambda c: -abs(c.coefficient))[:_MAX_CORRELATIONS]
    for i, c in enumerate(corrs):
        strength = _rel_class(c.coefficient)
        polarity = "positive" if c.coefficient > 0 else "negative"
        facts.append(SymbolicFact(
            fact_id=f"C{i + 1}", fact_type="correlation", token=f"{{{{C{i + 1}}}}}",
            label=f"correlation between {c.column_a} and {c.column_b}",
            meaning=f"{strength} {polarity} association between {c.column_a} and {c.column_b}",
            raw_value=c.coefficient, value_kind="correlation",
            magnitude_class=strength, direction=polarity,
        ))

    # Temporal (T) — meaning carries NO period literals (dates are numeric-like)
    for i, t in enumerate(fact_package.temporal_comparisons[:_MAX_TEMPORAL]):
        direction = "positive" if (t.percentage_change or 0) > 0 else (
            "negative" if (t.percentage_change or 0) < 0 else "stable")
        facts.append(SymbolicFact(
            fact_id=f"T{i + 1}", fact_type="temporal", token=f"{{{{T{i + 1}}}}}",
            label=f"period change of {t.column}",
            meaning=f"{direction} ({_magnitude_for_pct(t.percentage_change)} magnitude) "
                    f"change in {t.column} between the earlier and the later period",
            raw_value=t.percentage_change, value_kind="percent",
            magnitude_class=_magnitude_for_pct(t.percentage_change), direction=direction,
        ))

    # Recommendation candidates (R) — deterministic messages ONLY
    # LLM-facing label is sanitized to carry NO numeric literals; the rich
    # deterministic message (which may contain verified values) stays internal
    # for the renderer to inject at {{R#}}.
    for i, r in enumerate(fact_package.recommendation_candidates):
        sanitized_label = _sanitize_label(r.message)
        facts.append(SymbolicFact(
            fact_id=f"R{i + 1}", fact_type="recommendation", token=f"{{{{R{i + 1}}}}}",
            label=f"recommendation: {sanitized_label}",
            meaning=f"an approved recommendation candidate ({r.severity} severity) "
                    f"related to {r.evidence_column}",
            raw_value=r.evidence_value, value_kind="raw",
            recommendation_message=r.message, magnitude_class=r.severity,
        ))

    return facts


class FactRegistry:
    """Token <-> SymbolicFact registry with lookups and validation helpers."""

    def __init__(self, facts: List[SymbolicFact]):
        self.facts = facts
        self._by_id = {f.fact_id: f for f in facts}
        self._by_token = {f.token: f for f in facts}

    @property
    def fact_ids(self) -> Set[str]:
        return set(self._by_id.keys())

    def get(self, fact_id: str) -> Optional[SymbolicFact]:
        return self._by_id.get(fact_id)

    def get_by_token(self, token: str) -> Optional[SymbolicFact]:
        return self._by_token.get(token)

    def token(self, fact_id: str) -> Optional[str]:
        f = self._by_id.get(fact_id)
        return f.token if f else None

    def fact_type(self, fact_id: str) -> Optional[str]:
        f = self._by_id.get(fact_id)
        return f.fact_type if f else None


# ─────────────────────────────────────────────────────────────────────────────
# LLM-facing symbolic payload builder (NO exact numeric literals)
# ─────────────────────────────────────────────────────────────────────────────
class SymbolicPayloadBuilder:
    """Builds the JSON payload sent to the LLM using value tokens in place of
    numeric literals. The model sees qualitative metadata + tokens only."""

    def __init__(self, registry: FactRegistry):
        self.registry = registry

    def build(self) -> List[dict]:
        payload = []
        for f in self.registry.facts:
            entry: Dict[str, Any] = {
                "id": f.fact_id,
                "type": f.fact_type,
                "label": f.label,
                "meaning": f.meaning,
                "value_token": f.token,
            }
            if f.fact_type == "metric":
                entry["value"] = f.token
            elif f.fact_type == "distribution":
                payload.append(entry)  # dominant value stays a token/text, no number
                continue
            elif f.fact_type == "anomaly":
                entry["severity"] = f.magnitude_class
                entry["value"] = f.token
            elif f.fact_type == "correlation":
                entry["relationship"] = (
                    f"{f.magnitude_class} {'positive' if (f.direction == 'positive') else 'negative'} association"
                )
                entry["value_token"] = f.token
            elif f.fact_type == "temporal":
                entry["direction"] = f.direction
                entry["magnitude_class"] = f.magnitude_class
                entry["value_token"] = f.token
            elif f.fact_type == "recommendation":
                entry["value_token"] = f.token
            payload.append(entry)
        return payload

    def to_json(self) -> str:
        import json
        return json.dumps({"facts": self.build()}, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# Zero-numeric validation + token validation
# ─────────────────────────────────────────────────────────────────────────────
class SymbolicValidator:
    """Deterministic validation of the symbolic LLM structured output.

    Rules enforced:
      1. No numeric literal anywhere in semantic prose (summary, observations,
         recommendations, limitations).
      2. Every token is well-formed and references an existing fact_id.
      3. Every referenced fact_id (in fact_ids) is known.
      4. Token/fact consistency: the set of tokens inline in an item's text
         must agree exactly with its declared fact_ids. No mismatch, no
         undeclared token, no unreferenced fact_id.
      5. Every observation/recommendation references >= 1 fact.
      6. Forbidden/Causality claims still rejected (unchanged policy).
      7. Recommendations referenced only from fact_ids of type recommendation.
      8. Item count and summary length caps.
    """

    def __init__(self, registry: FactRegistry):
        self.registry = registry

    def validate(self, out: LLMInsightOutput) -> Tuple[bool, str]:
        if not out.summary.strip():
            return False, "EMPTY_SUMMARY"

        # Zero numeric literal check across ALL prose.
        for claim in [out.summary, *out.limitations]:
            if self._first_numeric(claim) is not None:
                return False, f"NUMERIC_LITERAL_IN_TEXT"
        for o in out.key_observations:
            n = self._first_numeric(o.text)
            if n is not None:
                return False, f"NUMERIC_LITERAL_IN_OBSERVATION"
        for r in out.recommendations:
            n = self._first_numeric(r.text)
            if n is not None:
                return False, f"NUMERIC_LITERAL_IN_RECOMMENDATION"

        known = self.registry.fact_ids

        # Structural: every item references >= 1 fact.
        for i, o in enumerate(out.key_observations):
            if not o.fact_ids:
                return False, f"OBSERVATION_NO_FACT:{i}"
        for i, r in enumerate(out.recommendations):
            if not r.fact_ids:
                return False, f"RECOMMENDATION_NO_FACT:{i}"

        # Token format + existence + fact consistency for each item text.
        for i, o in enumerate(out.key_observations):
            ok, reason = self._validate_item(o.text, o.fact_ids, "OBSERVATION", i)
            if not ok:
                return False, reason
        for i, r in enumerate(out.recommendations):
            ok, reason = self._validate_item(r.text, r.fact_ids, "RECOMMENDATION", i)
            if not ok:
                return False, reason

        # Summary-level token validation (no fact_ids container; just validate
        # format + existence, no cross-consistency requirement for prose).
        for fid in _TOKEN_RE.findall(out.summary):
            if fid not in known:
                return False, f"UNKNOWN_TOKEN_IN_SUMMARY:{fid}"
            if self.registry.get(fid).fact_type == "recommendation":
                return False, f"REC_TOKEN_IN_SUMMARY"

        # Recommendation items may only reference recommendation facts (R#).
        for i, r in enumerate(out.recommendations):
            for fid in r.fact_ids:
                if self.registry.get(fid).fact_type != "recommendation":
                    return False, f"RECOMMENDATION_REF_NON_REC:{fid}"
            # every recommendation must correspond to an approved candidate
            if not any(self.registry.get(fid).fact_type == "recommendation" for fid in r.fact_ids):
                return False, f"RECOMMENDATION_NO_R_FACT:{i}"

        # Forbidden / causality claims (unchanged policy).
        prose = [
            out.summary, *[o.text for o in out.key_observations],
            *[r.text for r in out.recommendations], *out.limitations,
        ]
        from mistral_integrator import _assertive_match, _FORBIDDEN_CLAIMS, _CAUSATION_WORDS
        for claim in prose:
            if _assertive_match(_FORBIDDEN_CLAIMS, claim):
                return False, "FORBIDDEN_CLAIM"
            if _assertive_match(_CAUSATION_WORDS, claim):
                return False, "CAUSALITY_CLAIM"

        # Bounds.
        if len(out.key_observations) > _MAX_OBSERVATIONS:
            return False, f"TOO_MANY_OBSERVATIONS"
        if len(out.recommendations) > _MAX_RECOMMENDATIONS:
            return False, f"TOO_MANY_RECOMMENDATIONS"
        if len(out.limitations) > _MAX_LIMITATIONS:
            return False, f"TOO_MANY_LIMITATIONS"
        if len(out.summary.split(".")) - 1 > _MAX_SUMMARY_SENTENCES:
            return False, f"SUMMARY_TOO_LONG"

        return True, "OK"

    def _validate_item(self, text: str, fact_ids: List[str], kind: str, idx: int) -> Tuple[bool, str]:
        """Token <-> fact_ids consistency for one observation/recommendation."""
        known = self.registry.fact_ids

        # 1. every declared fact_id exists
        for fid in fact_ids:
            if fid not in known:
                return False, f"UNKNOWN_FACT_ID:{fid}"

        # 2. every token inline must be exact format + exist
        inline_ids = set()
        for fid in _TOKEN_RE.findall(text):
            if fid not in known:
                return False, f"UNKNOWN_TOKEN:{fid}"
            inline_ids.add(fid)

        # 3. token set == declared fact_id set (both directions)
        declared = set(fact_ids)
        if inline_ids != declared:
            missing = declared - inline_ids
            extra = inline_ids - declared
            return False, f"TOKEN_FACT_MISMATCH:{kind}{idx}:extra={sorted(extra)}:missing={sorted(missing)}"

        return True, "OK"

    def _first_numeric(self, text: str) -> Optional[str]:
        # Strip symbolic tokens first so digits inside "{{F1}}" never count.
        stripped = _TOKEN_RE.sub("", text)
        m = _NUMERIC_LITERAL_RE.search(stripped)
        if not m:
            return None
        return m.group(0)


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic FactRenderer
# ─────────────────────────────────────────────────────────────────────────────
class FactRenderer:
    """Injects authoritative presentation values for approved tokens only.

    - String substitution over an allowlist map (token -> verified value).
    - Replaces exact known tokens only; uses the registry, never arbitrary
      user placeholders and never evaluates token content as code.
    - Any unresolved/unknown token -> error (caller falls back deterministically).
    """

    def __init__(self, registry: FactRegistry):
        self.registry = registry

    def render(self, text: str) -> Tuple[bool, str]:
        """Render text; returns (success, rendered_or_error_reason)."""
        tokens = _TOKEN_RE.findall(text)
        for fid in tokens:
            fact = self.registry.get(fid)
            if fact is None:
                return False, f"UNRESOLVED_TOKEN:{fid}"
            value_str = self._present(fact)
            text = text.replace(f"{{{{{fid}}}}}", value_str)
        # Any leftover {{...}} => unresolved token (unknown/malformed type).
        left = _TOKEN_RE.search(text)
        if left:
            return False, f"UNRESOLVED_TOKEN:{left.group(1)}"
        return True, text

    def _present(self, fact: SymbolicFact) -> str:
        if fact.value_kind == "currency":
            return format_currency(fact.raw_value, fact.unit)
        if fact.value_kind == "percent":
            return format_percent(fact.raw_value)
        if fact.value_kind == "count":
            return format_count(fact.raw_value)
        if fact.value_kind == "correlation":
            return format_correlation(fact.raw_value)
        if fact.value_kind == "score":
            return format_score(fact.raw_value)
        if fact.value_kind == "text":
            return format_value_raw(fact.raw_value)
        if fact.fact_type == "recommendation" and fact.recommendation_message:
            return fact.recommendation_message
        return format_value_raw(fact.raw_value)


def render_result(out: LLMInsightOutput, registry: FactRegistry) -> Tuple[bool, Optional[LLMInsightOutput]]:
    """Render every token in a validated symbolic output. On any unresolved
    token returns (False, None) so the caller falls back deterministically."""
    renderer = FactRenderer(registry)
    try:
        summary_ok, summary = renderer.render(out.summary)
        if not summary_ok:
            return False, None
        observations = []
        for o in out.key_observations:
            ok, t = renderer.render(o.text)
            if not ok:
                return False, None
            observations.append(LLMObservation(text=t, fact_ids=list(o.fact_ids)))
        recommendations = []
        for r in out.recommendations:
            ok, t = renderer.render(r.text)
            if not ok:
                return False, None
            recommendations.append(LLMRecommendation(text=t, fact_ids=list(r.fact_ids)))
        limitations = []
        for lim in out.limitations:
            ok, t = renderer.render(lim)
            if not ok:
                return False, None
            limitations.append(t)
        return True, LLMInsightOutput(
            summary=summary,
            key_observations=observations,
            recommendations=recommendations,
            limitations=limitations,
        )
    except Exception:
        return False, None


# Re-exported for testing convenience
from models import LLMObservation, LLMRecommendation  # noqa: E402
