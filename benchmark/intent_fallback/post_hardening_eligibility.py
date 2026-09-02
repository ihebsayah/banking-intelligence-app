"""
Step 12: Post-hardening semantic fallback eligibility.

Rebuilds the Step-10 fallback trigger around Step-11 semantics (decision,
ambiguity_codes, evidence score) instead of the obsolete conf<=0.05 heuristic.

The LLM may ONLY attempt genuine SEMANTICALLY_RESOLVABLE ambiguity. It never
recovers information the user did not supply (INFORMATION_MISSING), and never
overrides security/unsupported state.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EligibilityClass(str, Enum):
    SEMANTICALLY_RESOLVABLE = "SEMANTICALLY_RESOLVABLE"
    INFORMATION_MISSING = "INFORMATION_MISSING"
    SECURITY_OR_UNSUPPORTED = "SECURITY_OR_UNSUPPORTED"
    DETERMINISTIC_SUFFICIENT = "DETERMINISTIC_SUFFICIENT"


class SemanticFallbackDecision(BaseModel):
    use_llm: bool
    eligibility_class: EligibilityClass
    reason_codes: List[str] = Field(default_factory=list)
    intent_evidence_score: float = 0.0
    ambiguity_codes: List[str] = Field(default_factory=list)


# ── Ambiguity-code → eligibility mapping ────────────────────────────────────
#
# Derived conservatively from the actual Step-11 cases (spec §7/§6). The rule:
# only fire the LLM when the query LANGUAGE carries enough semantic signal to
# disambiguate. When the required information simply does not exist in the
# query (unresolved pronoun, missing metric/entity/comparison basis), no model
# can recover it — clarifying is the only correct answer.

# Information the user never supplied → NEVER send to LLM; deterministic
# clarification wins. LLM guessing here would be counted as failure, not success.
_INFORMATION_MISSING_CODES = {
    "UNRESOLVED_REFERENCE",   # "compare them", "the bad ones", "and last month?"
    "AMBIGUOUS_ENTITY",       # customer vs branch — entity not given
    "MISSING_TIME_CONTEXT",   # period not given
    "COMPOUND_UNSUPPORTED",   # downstream capability issue, not language
    "TOO_SHORT",              # nothing to disambiguate on
}

# These CODES alone never justify an LLM call. But a code like NO_INTENT_MATCH
# or INTENT_TIE may be LLM-eligible IF the raw query contains enough banking
# language to be semantically resolvable (checked by _has_semantic_signal).
_POTENTIALLY_RESOLVABLE_CODES = {
    "NO_INTENT_MATCH",        # registry missed a paraphrase → language-resolvable
    "INTENT_TIE",             # near-tie structuring did not settle → language-resolvable
    "DOMAIN_UNCLEAR",         # only if query still carries banking substance
    "AMBIGUOUS_METRIC",       # "better/meilleur/performe" — often language-resolvable
    # NO_ANALYTICAL_SUBSTANCE is disputed. It may mean the deterministic hint
    # vocabulary missed a resolvable measure OR the query genuinely lacks one.
    # Resolved per-case by _banking_language_signal: strong language substance
    # (=2+ banking word hits) means the metric/entity IS in the words and the
    # gate fired on a vocabulary gap (spec §6 "lexical synonym not captured by
    # registry") → SEMANTICALLY_RESOLVABLE. Weak substance → INFORMATION_MISSING.
    "NO_ANALYTICAL_SUBSTANCE",
}


def _banking_language_signal(query: str) -> int:
    """Count distinct banking-word hits in the raw query — the amount of
    resolvable language substance the LLM would have to work with.

    Total DISTINCT hits across all categories (not per-category presence):
    a query like "fee income" scores 2 (fee + income) even though both are
    revenue words.
    """
    signals = {
        "customer": ["client", "clientèle", "customer", "compte", "comptes",
                     "account", "accounts", "segment", "clients", "tiers",
                     "profil", "profile"],
        "risk": ["risque", "risk", "npl", "créance", "fraud", "default",
                 "impayé", "douteuse", "douteuses", "exposure", "exposition",
                 "bad", "delinquent", "solvable", "solvables", "découvert",
                 "overdrawn", "risky"],
        "revenue": ["revenu", "revenus", "revenue", "commission", "commissions",
                    "pnb", "profit", "roe", "roa", "performance", "rapporte",
                    "performe", "performent", "marge", "margin", "income",
                    "earning", "earnings", "earn", "génère", "génèrent", "vendent",
                    "vend", "fee", "fees", "bénéfice", "bénéfices", "profitable",
                    "profitability", "returns", "sales", "intérêt", "intérêts",
                    "interest"],
        "ops": ["volume", "count", "transaction", "transactions", "mouvement",
                "mouvements", "flux", "virement", "virements", "transfer",
                "transfers", "paiement", "paiements", "remise", "remises"],
        "geo": ["agence", "agences", "branch", "branches", "region", "ville",
                "gouvernorat", "location", "city", "succursale", "province"],
        "product": ["produit", "produits", "product", "products", "prêt",
                    "prêts", "loan", "loans", "crédit", "crédits", "credit",
                    "dépôt", "dépôts", "deposit", "deposits", "assurance",
                    "carte", "cards", "borrower", "borrowers"],
        "compliance": ["conformité", "compliance", "audit", "réglementaire",
                       "regulatory", "kyc", "aml", "blanchiment", "screening"],
        "liquidity": ["liquidité", "liquidity", "lcr", "nsfr", "ldr"],
    }
    q = query.lower()
    seen = set()
    for word_list in signals.values():
        for w in word_list:
            if re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", q):
                seen.add(w)
    return len(seen)


def _semantically_resolvable_codes(query: str, ambiguity_codes: List[str]) -> bool:
    """True if the ambiguity codes are candidates AND the raw query carries
    enough banking language for the LLM to potentially disambiguate."""
    codes = set(ambiguity_codes)
    regular_missing = _INFORMATION_MISSING_CODES & codes
    # NO_ANALYTICAL_SUBSTANCE is the only information-missing-adjacent code that
    # may actually carry resolvable substance — resolve it per-case below.
    if regular_missing:
        return False
    candidates = codes & _POTENTIALLY_RESOLVABLE_CODES
    if not candidates:
        return False
    # Need at least 2 distinct banking word hits to give the LLM substance.
    return _banking_language_signal(query) >= 2


def make_fallback_decision_step12(intent_output: Dict[str, Any]) -> SemanticFallbackDecision:
    """Step-12 trigger. Decides LLM eligibility from Step-11 semantics only."""
    decision = intent_output.get("decision")
    risk = intent_output.get("risk_level", "safe")
    supported = intent_output.get("supported_capability", True)
    ambiguity_codes = list(intent_output.get("ambiguity_codes", []) or [])
    evidence = intent_output.get("intent_evidence_score", 0.0)
    query = intent_output.get("_query", "") or ""

    # 1. Security / rejection — NEVER call LLM (spec §5, §12, §28).
    if not supported or risk in ("adversarial", "suspicious") or decision == "REJECT":
        return SemanticFallbackDecision(
            use_llm=False,
            eligibility_class=EligibilityClass.SECURITY_OR_UNSUPPORTED,
            reason_codes=["SECURITY_GATE"],
            intent_evidence_score=evidence,
            ambiguity_codes=ambiguity_codes,
        )

    # 2. AUTO_ACCEPT — deterministic always wins, no LLM (spec §12).
    if decision == "AUTO_ACCEPT":
        return SemanticFallbackDecision(
            use_llm=False,
            eligibility_class=EligibilityClass.DETERMINISTIC_SUFFICIENT,
            reason_codes=["DETERMINISTIC_SUFFICIENT"],
            intent_evidence_score=evidence,
            ambiguity_codes=ambiguity_codes,
        )

    # 3. CLARIFY / low-evidence — evaluate whether ambiguity is resolvable from
    #    the language. If it is information-missing, deterministic clarification wins.
    if decision == "CLARIFY" or evidence < 0.20:
        if _semantically_resolvable_codes(query, ambiguity_codes):
            return SemanticFallbackDecision(
                use_llm=True,
                eligibility_class=EligibilityClass.SEMANTICALLY_RESOLVABLE,
                reason_codes=_POTENTIALLY_RESOLVABLE_CODES & set(ambiguity_codes) or ["SEMANTIC_RESOLVABLE"],
                intent_evidence_score=evidence,
                ambiguity_codes=ambiguity_codes,
            )
        if set(ambiguity_codes) & _INFORMATION_MISSING_CODES:
            return SemanticFallbackDecision(
                use_llm=False,
                eligibility_class=EligibilityClass.INFORMATION_MISSING,
                reason_codes=list(set(ambiguity_codes) & _INFORMATION_MISSING_CODES),
                intent_evidence_score=evidence,
                ambiguity_codes=ambiguity_codes,
            )
        # CLARIFY with codes not resolvable → no LLM.
        return SemanticFallbackDecision(
            use_llm=False,
            eligibility_class=EligibilityClass.INFORMATION_MISSING,
            reason_codes=ambiguity_codes or ["CLARIFY_NOT_RESOLVABLE"],
            intent_evidence_score=evidence,
            ambiguity_codes=ambiguity_codes,
        )

    # 4. Anything else (CLARIFY no codes, defensive default) → no LLM.
    return SemanticFallbackDecision(
        use_llm=False,
        eligibility_class=EligibilityClass.DETERMINISTIC_SUFFICIENT,
        reason_codes=["DETERMINISTIC_SUFFICIENT"],
        intent_evidence_score=evidence,
        ambiguity_codes=ambiguity_codes,
    )
