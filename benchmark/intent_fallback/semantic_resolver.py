"""
Step 10: Semantic Intent Fallback.
Local LLM (qwen2.5:3b) as OPTIONAL fallback for ambiguous deterministic intents.

The LLM only CLASSIFIES language into an existing intent category. It never:
- generates SQL
- selects tables
- accesses data
- makes auth/compliance decisions
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Structured schema ───────────────────────────────────────────────────────

class SemanticInterpretation(BaseModel):
    """LLM output. Strictly classification, never SQL/data."""
    primary_intent: str
    secondary_intents: List[str] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    requires_clarification: bool = False
    clarification_reason: Optional[str] = None
    missing_context: List[str] = Field(default_factory=list)
    confidence_class: str = "low"   # low | medium | high
    is_banking_query: bool = True   # False = off-domain, never map to an intent


# The platform's existing allowed intent categories (matches INTENT_TO_DOMAINS)
ALLOWED_INTENTS: List[str] = [
    "customer_analysis",
    "risk_analysis",
    "revenue_analysis",
    "operational_analysis",
    "geographic_analysis",
    "product_analysis",
    "compliance_analysis",
    "transaction_analysis",
    "loan_analysis",
    "kyc_analysis",
    "aml_analysis",
    "profitability_analysis",
    "liquidity_analysis",
]

INTENT_DEFINITIONS = {
    "customer_analysis": "questions about customer demographics, segments, profiles, balances, account holders, customer behavior",
    "risk_analysis": "questions about credit risk, fraud, defaults, NPL, exposure, delinquent accounts, suspicious/delinquent customers, high-risk customers, non-performing loans",
    "revenue_analysis": "questions about revenue, income, profit, fees, commissions, PNB, ROE, ROA, performance of branches in terms of income, earnings",
    "operational_analysis": "questions about transaction volume, counts, throughput, efficiency, processing speed, operational metrics",
    "geographic_analysis": "questions about branches, regions, locations, cities, state-level or territory-level breakdowns, branch comparison by region",
    "product_analysis": "questions about products, account types, loans, deposits, credit, investments, insurance, mortgages, cards, loan-to-deposit ratio",
    "compliance_analysis": "questions about regulatory compliance, KYC compliance, AML alerts, audit, filing, reporting obligations, compliance status",
    "transaction_analysis": "questions about transactions, payments, transfers, wires, money movements, transaction volumes, remittances, settlement",
    "loan_analysis": "questions specifically about loans, prêts, crédits, outstanding loans, loan portfolios",
    "kyc_analysis": "questions specifically about Know Your Customer verification status, unverified customers, PEP status",
    "aml_analysis": "questions specifically about anti-money-laundering, blanchiment, SARs, suspicious activity reports",
    "profitability_analysis": "questions about profitability, net banking income, ROE, ROA, rentabilité, margins, cost-to-income ratio",
    "liquidity_analysis": "questions about liquidity, liquidity coverage ratio, loan-to-deposit ratio, deposits, cash reserves",
}


CLARIFICATION_TEXTS = {
    "importance_criterion": "Which criterion defines 'important'? (e.g. balance, revenue, risk)",
    "risk_threshold": "What risk threshold should define 'risky'? (e.g. risk_score > 0.7)",
    "time_period": "What time period should we analyze?",
    "entity_type": "Which entity type? (customers, transactions, accounts, or branches)",
    "metric": "Which metric should we use?",
    "comparison_basis": "Compared against what baseline?",
    "segment": "Which customer segment?",
    "product_type": "Which product type?",
}


# ── Fallback trigger (deterministic) ────────────────────────────────────────

class SemanticFallbackDecision(BaseModel):
    use_llm: bool
    reason_codes: List[str] = Field(default_factory=list)
    deterministic_confidence: float
    ambiguity_type: Optional[str] = None


def make_fallback_decision(intent_output: dict) -> SemanticFallbackDecision:
    """Decide whether the LLM fallback is worth invoking for this intent.

    Uses only existing deterministic signals from the Intent Agent.
    NEVER calls LLM for: adversarial, unsupported, or high-confidence clear queries.
    """
    conf = intent_output.get("confidence", 0) or intent_output.get("intent_confidence", 0)
    reason_codes: List[str] = []
    risk = intent_output.get("risk_level", "safe")
    supported = intent_output.get("supported_capability", True)

    # Never fall back on security-relevant states — the LLM must not re-interpret
    # requests already gated as adversarial/unsupported.
    if risk in ("adversarial", "suspicious") or not supported:
        return SemanticFallbackDecision(
            use_llm=False,
            reason_codes=["SECURITY_GATE"],
            deterministic_confidence=conf,
        )

    requires_clarification = intent_output.get("requires_clarification", False)
    ambiguities = intent_output.get("ambiguities", [])
    secondary = intent_output.get("secondary_categories", [])
    primary = intent_output.get("primary_category", "")

    # The keyword classifier fell to the 0.05 floor → zero keyword matches →
    # primary_category is effectively a garbage default. This is the strongest
    # possible uncertainty signal; the LLM can help.
    hard_vague = any(
        "vague" in a.lower() or "too short" in a.lower() for a in ambiguities
    )
    if conf <= 0.05:
        return SemanticFallbackDecision(
            use_llm=True,
            reason_codes=["UNKNOWN_INTENT"],
            deterministic_confidence=conf,
            ambiguity_type="unknown",
        )

    # Hard vagueness (no category detected / too short) + clarification flagged
    if requires_clarification and hard_vague:
        return SemanticFallbackDecision(
            use_llm=True,
            reason_codes=["AMBIGUOUS_TERM"],
            deterministic_confidence=conf,
            ambiguity_type="ambiguous",
        )

    # Everything else: deterministic wins. This keeps the fallback rate low
    # (only genuinely-unclassified queries reach the LLM).
    return SemanticFallbackDecision(
        use_llm=False,
        reason_codes=[],
        deterministic_confidence=conf,
    )


# ── Semantic resolver (LLM) ─────────────────────────────────────────────────

PROMPT_TEMPLATE = """You are a banking query classifier. Classify the user's question into EXACTLY ONE intent from the allowed list below. You do NOT generate SQL, choose tables, or access data.

Allowed intents and their meanings:
{intent_defs}

Rules:
- First determine if this is a BANKING ANALYTICS question (asking to analyze customers, accounts, transactions, branches, risk, revenue, compliance, loans, etc. as data in a banking context). If it is not (e.g. a joke, weather, time, general knowledge, IT support, unrelated topic), set "is_banking_query": false, "requires_clarification": true, and "primary_intent" to an empty string.
- Choose the single most appropriate intent ONLY if the question is clearly a banking analytics query.
- Prefer CLARIFICATION over guessing. Set requires_clarification to true and list missing_context when:
  - the referenced entity is unresolved ("the bad ones", "compare them", "ceux qui posent problème", "les gros clients", "those")
  - an ambiguous business word needs a definition before answering ("important", "risky", "better", "performance", "galèrent", "bizarrement", "cloche")
  - a compound question needs decomposition into a single primary intent
  - there is a follow-up/reference to prior context that is not given ("and last month?", "compare them", "same for...")
- When you clarify, still set primary_intent to your best-guess intent IF there is one, otherwise empty string.
- Never invent an intent outside the allowed list.
- Never invent constraint values the user did not state.
- Secondary intents: only if the question clearly combines multiple analytical topics.
- Missing context options: importance_criterion, risk_threshold, time_period, entity_type, metric, comparison_basis, segment, product_type.

User question: {question}

Respond with JSON exactly in this shape:
{{"primary_intent": "intent_or_empty", "secondary_intents": [], "constraints": {{}}, "requires_clarification": false, "clarification_reason": null, "missing_context": [], "confidence_class": "low|medium|high", "is_banking_query": true}}"""


class SemanticResolver:
    """Calls Ollama for structured intent interpretation. Optional/fallback only."""

    def __init__(self, model: str = "qwen2.5:3b", base_url: str = "http://localhost:11434",
                 enabled: bool = False, timeout: float = 30.0, max_tokens: int = 128):
        self.model = model
        self.base_url = base_url
        self.enabled = enabled
        self.timeout = timeout
        self.max_tokens = max_tokens

    def available(self) -> bool:
        if not self.enabled:
            return False
        try:
            import requests
            r = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def resolve(self, question: str, candidate_scores: Optional[dict] = None) -> SemanticInterpretation:
        """Return parsed interpretation. On ANY failure returns requires_clarification=True."""
        if not self.enabled:
            return SemanticInterpretation(
                primary_intent="unknown", requires_clarification=True,
                clarification_reason="resolver_disabled",
            )
        try:
            import requests
            intent_defs = "\n".join(f"- {k}: {v}" for k, v in INTENT_DEFINITIONS.items())
            prompt = PROMPT_TEMPLATE.format(intent_defs=intent_defs, question=question)

            t0 = time.perf_counter()
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.0, "num_predict": self.max_tokens},
            }
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            raw = resp.json().get("response", "")
            latent = (time.perf_counter() - t0) * 1000

            parsed = json.loads(raw)
            interp = SemanticInterpretation(**parsed)

            # Allowlist enforcement + validation
            if not interp.is_banking_query:
                # Off-domain: never map to an intent, force clarification
                return SemanticInterpretation(
                    primary_intent="", requires_clarification=True,
                    clarification_reason="not_a_banking_analytics_query",
                    missing_context=["entity_type"],
                )
            if interp.primary_intent and interp.primary_intent not in ALLOWED_INTENTS:
                return SemanticInterpretation(
                    primary_intent="unknown", requires_clarification=True,
                    clarification_reason="invalid_intent",
                )
            interp.secondary_intents = [i for i in interp.secondary_intents if i in ALLOWED_INTENTS]
            if interp.requires_clarification and interp.primary_intent in ("", "unknown"):
                interp.primary_intent = ""
            return interp
        except Exception as exc:
            logger.warning("Semantic resolver failed: %s", exc)
            return SemanticInterpretation(
                primary_intent="unknown", requires_clarification=True,
                clarification_reason="resolver_failed",
            )


# ── Hybrid policy ───────────────────────────────────────────────────────────

def hybrid_resolve(question: str, intent_output: dict, resolver: SemanticResolver) -> dict:
    """Combine deterministic + optional semantic fallback into a final intent dict.

    Returns a dict with the same contract shape plus hybrid metadata.
    """
    decision = make_fallback_decision(intent_output)

    result = dict(intent_output)  # clone
    result["fallback_triggered"] = False
    result["agreement"] = None
    result["latency_ms_extra"] = 0

    if not decision.use_llm:
        return result

    t0 = time.perf_counter()
    interp = resolver.resolve(question)
    latency_ms = (time.perf_counter() - t0) * 1000
    result["latency_ms_extra"] = round(latency_ms, 2)

    if interp.primary_intent == "unknown":
        # LLM failed to produce valid output → keep deterministic/clarification behavior
        result["fallback_triggered"] = True
        result["agreement"] = "invalid"
        return result

    det_primary = intent_output.get("primary_category", "")
    det_conf = intent_output.get("confidence", 0)

    # Agreement → keep deterministic but note improved confidence
    if interp.primary_intent == det_primary:
        result["agreement"] = "agree"
        return result

    # LLM wants clarification → prefer clarification (do not guess)
    if interp.requires_clarification:
        result["requires_clarification"] = True
        result["clarification_reason"] = interp.clarification_reason
        result["missing_context"] = interp.missing_context
        result["fallback_triggered"] = True
        result["agreement"] = "clarification"
        result["primary_category"] = det_primary if det_primary in ALLOWED_INTENTS else interp.primary_intent
        return result

    # Disagreement on a case the deterministic path already flagged as requiring
    # clarification (unresolved reference / ambiguous entity) → prefer keeping
    # clarification over a confident guess unless the deterministic signal was
    # purely a keyword miss (det_conf < 0.3) AND the LLM is high confidence.
    # This enforces §9/§11: do not override a clarification signal with a guess.
    if intent_output.get("requires_clarification", False):
        if det_conf < 0.3 and interp.confidence_class == "high":
            result["primary_category"] = interp.primary_intent
            result["secondary_categories"] = interp.secondary_intents
            result["constraints_from_llm"] = interp.constraints
            result["fallback_triggered"] = True
            result["agreement"] = "disagree"
            result["requires_clarification"] = False
        else:
            # Keep clarification signal, note the LLM's alternative
            result["requires_clarification"] = True
            result["clarification_reason"] = "ambiguity_resolved_to_guess_but_not_confident"
            result["missing_context"] = ["entity_type"]
            result["fallback_triggered"] = True
            result["agreement"] = "disagree_kept_clarification"
        return result

    # Disagreement on low-confidence deterministic case → use LLM classification
    if det_conf < 0.5:
        result["primary_category"] = interp.primary_intent
        result["secondary_categories"] = interp.secondary_intents
        result["constraints_from_llm"] = interp.constraints
        result["fallback_triggered"] = True
        result["agreement"] = "disagree"
        result["requires_clarification"] = False
        return result

    # High-confidence deterministic case: do NOT override
    result["agreement"] = "disagree_kept_deterministic"
    return result
