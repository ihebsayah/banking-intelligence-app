"""
services/intent_agent/intent_recognizer.py

Pattern-matching intent recogniser (no LLM).
Uses spaCy for tokenisation / lemmatisation, then keyword scoring.
Redis caches results for 24 h.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Category keyword tables ──────────────────────────────────────────────────

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "customer_analysis": [
        "customer", "client", "segment", "demographic", "profile",
        "balance", "account_holder", "retail", "holder", "member", "user",
    ],
    "risk_analysis": [
        "risk", "fraud", "default", "violation", "aml", "kyc", "suspicious",
        "flag", "compliance", "sanction", "exposure", "credit_risk",
        "delinquent", "watchlist", "alert",
    ],
    "revenue_analysis": [
        "revenue", "income", "profit", "fee", "commission", "earning",
        "sale", "performance", "margin", "gross", "yield", "return",
        "interest", "net",
    ],
    "operational_analysis": [
        "volume", "count", "speed", "efficiency", "throughput",
        "latency", "queue", "processing", "rate", "capacity", "load",
    ],
    "geographic_analysis": [
        "region", "branch", "location", "state", "city", "geographic",
        "area", "territory", "district", "zone", "country", "market",
    ],
    "product_analysis": [
        "product", "account_type", "service", "loan", "deposit", "credit",
        "investment", "insurance", "checking", "saving", "mortgage",
        "card", "portfolio",
    ],
    "compliance_analysis": [
        "compliance", "regulatory", "audit", "requirement",
        "regulation", "control", "policy", "gdpr", "sox", "sec",
        "report", "filing",
    ],
    "transaction_analysis": [
        "transaction", "payment", "transfer", "wire", "ach", "movement",
        "flow", "settlement", "posting", "clearing", "remittance",
    ],
}

# Shared / ambiguous words that belong to multiple categories
AMBIGUOUS_WORDS = {
    "balance": ["customer_analysis", "revenue_analysis"],
    "performance": ["revenue_analysis", "operational_analysis"],
    "product": ["product_analysis", "revenue_analysis"],
    "compliance": ["compliance_analysis", "risk_analysis"],
}

# ── Constraint extraction patterns ───────────────────────────────────────────

_TOP_N_RE    = re.compile(r"\btop\s+(\d+)\b", re.IGNORECASE)
_LAST_N_DAYS = re.compile(r"\blast\s+(\d+)\s+days?\b", re.IGNORECASE)
_QUARTER_RE  = re.compile(r"\b(this|last)\s+quarter\b", re.IGNORECASE)
_MONTH_RE    = re.compile(r"\b(this|last)\s+month\b", re.IGNORECASE)
_YEAR_RE     = re.compile(r"\b(this|last)\s+year\b|\byear\s+to\s+date\b|\bytd\b", re.IGNORECASE)

_GEO_MAP = {
    "new york": "NY", "ny": "NY", "northeast": "Northeast",
    "california": "CA", "ca": "CA", "texas": "TX", "tx": "TX",
    "florida": "FL", "fl": "FL", "midwest": "Midwest", "southeast": "Southeast",
}

_SEGMENT_KEYWORDS = ["premium", "gold", "platinum", "standard", "vip",
                     "retail", "corporate", "sme", "private banking"]


def _extract_constraints(query: str) -> Dict:
    q = query.lower()
    constraints: Dict = {"threshold": None, "time_period": None,
                         "geography": None, "segment": None}

    # threshold
    m = _TOP_N_RE.search(query)
    if m:
        constraints["threshold"] = f"top_{m.group(1)}"

    # time period
    if _LAST_N_DAYS.search(q):
        n = _LAST_N_DAYS.search(q).group(1)
        constraints["time_period"] = f"last_{n}_days"
    elif _QUARTER_RE.search(q):
        constraints["time_period"] = "last_quarter"
    elif _MONTH_RE.search(q):
        constraints["time_period"] = "last_30_days"
    elif _YEAR_RE.search(q):
        constraints["time_period"] = "last_year"

    # geography
    for phrase, code in _GEO_MAP.items():
        if phrase in q:
            constraints["geography"] = code
            break

    # segment
    for seg in _SEGMENT_KEYWORDS:
        if seg in q:
            constraints["segment"] = seg
            break

    return constraints


# ── Main recogniser ───────────────────────────────────────────────────────────

class IntentRecognizer:
    """
    Keyword + lemma based intent classifier.
    spaCy is used for lemmatisation so 'customers' → 'customer' etc.
    Redis is used for result caching (TTL 24 h).
    """

    def __init__(self, redis_client=None):
        self._nlp = None          # loaded lazily or passed in
        self._redis = redis_client
        self._CACHE_TTL = 86_400  # 24 h

    # ── spaCy bootstrap ──────────────────────────────────────────────────────

    def _get_nlp(self):
        if self._nlp is None:
            try:
                import spacy
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                import subprocess, sys
                subprocess.run(
                    [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
                    check=True,
                )
                import spacy
                self._nlp = spacy.load("en_core_web_sm")
        return self._nlp

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _cache_key(self, query: str) -> str:
        return "intent:" + hashlib.sha256(query.lower().encode()).hexdigest()

    async def _from_cache(self, query: str):
        if not self._redis:
            return None
        try:
            raw = await self._redis.get(self._cache_key(query))
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def _to_cache(self, query: str, result: dict):
        if not self._redis:
            return
        try:
            await self._redis.setex(
                self._cache_key(query), self._CACHE_TTL, json.dumps(result)
            )
        except Exception:
            pass

    # ── Core recognition ──────────────────────────────────────────────────────

    def _tokenise(self, query: str) -> List[str]:
        """Return list of lowercase lemmas using spaCy."""
        nlp = self._get_nlp()
        doc = nlp(query.lower())
        return [
            token.lemma_.lower()
            for token in doc
            if not token.is_stop and not token.is_punct and token.is_alpha
        ]

    def _score_categories(self, tokens: List[str]) -> Dict[str, int]:
        scores: Dict[str, int] = {cat: 0 for cat in CATEGORY_KEYWORDS}
        for token in tokens:
            for cat, kws in CATEGORY_KEYWORDS.items():
                if token in kws:
                    scores[cat] += 1
        return scores

    def _detect_ambiguities(
        self, query: str, scores: Dict[str, int], primary: str
    ) -> List[str]:
        ambiguities: List[str] = []
        q = query.lower()

        # Near-tie between top-2 categories → ambiguous intent
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[0] > 0:
            if sorted_scores[1] / sorted_scores[0] >= 0.75:
                ambiguities.append("Multiple categories equally matched — please clarify focus")

        # Specific word ambiguities
        if "balance" in q:
            ambiguities.append("'balance' could mean account balance or revenue balance")
        if "customer" in q and "branch" in q:
            ambiguities.append("Unclear primary entity: customer or branch?")
        if primary == "risk_analysis" and "high risk" in q:
            ambiguities.append("What is 'high risk'? Define threshold (e.g. risk_score > 0.7)")
        if primary == "risk_analysis" and not any(
            w in q for w in ["today", "this week", "this month", "this quarter",
                              "this year", "last", "since", "ytd"]
        ):
            ambiguities.append("What time period?")
            ambiguities.append("All products or specific product type?")

        # No matches at all → totally ambiguous
        if scores[primary] == 0:
            ambiguities.append("Query too vague — no clear category detected")

        return list(dict.fromkeys(ambiguities))  # dedupe, preserve order

    def recognize_sync(self, query: str) -> dict:
        """
        Synchronous recognition (used internally and by tests).
        Returns a plain dict matching IntentResponse schema.
        """
        tokens = self._tokenise(query)
        total_tokens = max(len(tokens), 1)

        scores = self._score_categories(tokens)

        # Primary = max score category
        primary_cat = max(scores, key=lambda c: (scores[c], c))
        primary_score = scores[primary_cat]

        # Secondary = categories with ≥30 % of primary's score (excluding primary)
        secondary_cats = [
            cat for cat, sc in scores.items()
            if cat != primary_cat and sc > 0 and (primary_score == 0 or sc / primary_score >= 0.30)
        ]
        # Sort secondaries by score desc
        secondary_cats.sort(key=lambda c: -scores[c])

        # Confidence
        if primary_score == 0:
            confidence = 0.05
        else:
            raw_conf = (primary_score / total_tokens) * 0.90 + 0.05
            confidence = round(min(raw_conf, 0.99), 4)

        constraints = _extract_constraints(query)
        ambiguities = self._detect_ambiguities(query, scores, primary_cat)

        # Force clarification when confidence low OR ambiguities present
        requires_clarification = confidence < 0.85 or len(ambiguities) > 0

        return {
            "primary_category": primary_cat,
            "secondary_categories": secondary_cats,
            "confidence": confidence,
            "explicit_constraints": constraints,
            "ambiguities": ambiguities,
            "requires_clarification": requires_clarification,
        }

    async def recognize(self, query: str) -> dict:
        """Async wrapper with Redis cache."""
        cached = await self._from_cache(query)
        if cached:
            logger.debug("Intent cache hit: %s", query[:40])
            return cached

        result = self.recognize_sync(query)
        await self._to_cache(query, result)
        return result
