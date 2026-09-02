"""
Step 12: Post-hardening hybrid policy (consensus).

Deterministic authority is GREATER than Step-10 because the deterministic system
is now stronger. Consensus per spec §12:

  AUTO_ACCEPT      → deterministic, no LLM call
  REJECT           → deterministic, no LLM call
  CLARIFY+INFORMATION_MISSING → deterministic clarification, no LLM call
  CLARIFY+SEMANTICALLY_RESOLVABLE → LLM may attempt resolution
      - LLM says clarification   → keep clarification
      - LLM valid intent HIGH    → candidate resolution
      - LLM disagrees & evidence insufficient → clarification wins

The LLM never converts genuinely-missing context into confident intent.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from post_hardening_eligibility import (
    EligibilityClass,
    SemanticFallbackDecision,
    make_fallback_decision_step12,
)
from semantic_resolver import ALLOWED_INTENTS, SemanticResolver


def step12_hybrid_resolve(question: str, intent_output: dict, resolver: SemanticResolver) -> dict:
    """Combine hardened deterministic + conditional semantic fallback."""
    decision = make_fallback_decision_step12(intent_output)

    result = dict(intent_output)
    result["_fallback_triggered"] = False
    result["_eligibility_class"] = decision.eligibility_class.value
    result["_reason_codes"] = decision.reason_codes
    result["_agreement"] = None
    result["_llm_latency_ms"] = 0

    if not decision.use_llm:
        return result

    t0 = time.perf_counter()
    interp = resolver.resolve(question)
    result["_llm_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    result["_fallback_triggered"] = True

    # Provider failure / malformed JSON → LLM returns primary_intent=="unknown"
    # → keep deterministic clarification. (spec §19, §31 test 15/16)
    if interp.primary_intent == "unknown":
        result["_agreement"] = "invalid"
        return result

    det_primary = intent_output.get("primary_category", "")
    det_conf = intent_output.get("intent_evidence_score", intent_output.get("confidence", 0))

    # 1. Agreement → keep deterministic.
    if interp.primary_intent == det_primary:
        result["_agreement"] = "agree"
        return result

    # 2. LLM wants clarification → preserve clarification (never guess).
    if interp.requires_clarification:
        result["requires_clarification"] = True
        result["_agreement"] = "clarification_preserved"
        return result

    # 3. LLM returns a valid allowed intent → it is a candidate resolution.
    #    Only accept if HIGH confidence. Otherwise clarification wins.
    if interp.primary_intent in ALLOWED_INTENTS:
        if interp.confidence_class == "high":
            # ACL: never invent constraints — carry only explicitly-validated ones.
            result["primary_category"] = interp.primary_intent
            result["secondary_categories"] = interp.secondary_intents
            result["_agreement"] = "resolved"
            result["requires_clarification"] = False
        else:
            # Insufficient evidence → clarification wins (spec §12).
            result["requires_clarification"] = True
            result["_agreement"] = "insufficient_evidence_kept_clarification"
        return result

    # 4. Fallback: any other disagreement → keep deterministic behavior.
    result["_agreement"] = "disagree_kept_deterministic"
    return result
