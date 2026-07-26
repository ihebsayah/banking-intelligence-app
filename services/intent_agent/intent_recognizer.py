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
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# ── Original Category keyword tables (Fallback mode) ───────────────────────

ORIGINAL_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
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

# ── Semantic Category keyword tables (French + English) ───────────────────────

SEMANTIC_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "customer_analysis": [
        "customer", "client", "segment", "demographic", "profile",
        "balance", "account_holder", "retail", "holder", "member", "user",
        "tiers", "particulier", "entreprise", "profil", "clientèle"
    ],
    "loan_analysis": [
        "loan", "loans", "credit", "prêt", "crédit", "mensualité", "outstanding",
        "amortissement", "échéancier", "remboursement", "contrat", "prêts", "crédits"
    ],
    "kyc_analysis": [
        "kyc", "know your customer", "connaissance client", "diligence", "verified",
        "unverified", "vérification", "pièce d'identité", "pep", "politically exposed"
    ],
    "aml_analysis": [
        "aml", "anti-money laundering", "blanchiment", "lbc", "declaration de soupcon",
        "sar", "ctaf", "suspicious", "fraude", "blanchiment d'argent"
    ],
    "risk_analysis": [
        "risk", "fraud", "default", "violation", "aml", "kyc", "suspicious",
        "flag", "compliance", "sanction", "exposure", "credit_risk",
        "delinquent", "watchlist", "alert", "risque", "défaut", "npl", "provision",
        "sinistre", "créances douteuses", "créance", "compromise", "défaillance"
    ],
    "profitability_analysis": [
        "revenue", "income", "profit", "fee", "commission", "earning",
        "sale", "performance", "margin", "gross", "yield", "return",
        "interest", "net", "pnb", "net banking income", "roe", "roa",
        "rentabilité", "rendement", "bénéfice", "produit net bancaire",
        "coefficient d'exploitation", "cir", "charges d'exploitation"
    ],
    "liquidity_analysis": [
        "liquidity", "liquidité", "lcr", "nsfr", "deposit", "dépôt", "epargne",
        "solde", "ldr", "loan to deposit", "avoirs", "placements", "tresorerie"
    ],
    "transaction_analysis": [
        "transaction", "payment", "transfer", "wire", "ach", "movement",
        "flow", "settlement", "posting", "clearing", "remittance",
        "virement", "paiement", "flux", "transfert", "mouvement"
    ],
    "operational_analysis": [
        "volume", "count", "speed", "efficiency", "throughput",
        "latency", "queue", "processing", "rate", "capacity", "load",
    ],
    "geographic_analysis": [
        "region", "branch", "location", "state", "city", "geographic",
        "area", "territory", "district", "zone", "country", "market",
        "agence", "succursale", "ville", "région"
    ],
    "product_analysis": [
        "product", "account_type", "service", "loan", "deposit", "credit",
        "investment", "insurance", "checking", "saving", "mortgage",
        "card", "portfolio", "produit", "type de compte"
    ],
    "compliance_analysis": [
        "compliance", "regulatory", "audit", "requirement",
        "regulation", "control", "policy", "gdpr", "sox", "sec",
        "report", "filing", "conformité", "réglementaire"
    ]
}

# Static fallback KPIs for offline/disabled mode
STATIC_KPIS: Dict[str, List[str]] = {
    "npl_ratio": ["npl ratio", "taux de créances classées", "créances classées", "non-performing loan ratio", "npl"],
    "roe": ["roe", "return on equity", "rentabilité des fonds propres", "rentabilité des capitaux propres"],
    "roa": ["roa", "return on assets", "rentabilité des actifs"],
    "kyc_compliance_rate": ["kyc compliance rate", "taux de conformité kyc", "conformité kyc"],
    "aml_alert_rate": ["aml alert rate", "taux d'alertes aml", "alertes aml"],
    "loan_to_deposit": ["loan to deposit", "ldr", "ratio crédits / dépôts", "ratio crédits/dépôts"]
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
        if re.search(rf"\b{phrase}\b", q):
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

    def __init__(self, redis_client=None, db=None, semantic_layer_enabled=False):
        self._nlp = None          # loaded lazily or passed in
        self._redis = redis_client
        self._db = db
        self._semantic_layer_enabled = semantic_layer_enabled
        self._CACHE_TTL = 86_400  # 24 h
        self._kpi_cache = None    # Cache for registered KPIs

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
        kws_map = SEMANTIC_CATEGORY_KEYWORDS if self._semantic_layer_enabled else ORIGINAL_CATEGORY_KEYWORDS
        scores: Dict[str, int] = {cat: 0 for cat in kws_map}
        for token in tokens:
            for cat, kws in kws_map.items():
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

    async def _fetch_kpi_registry(self) -> List[Dict[str, Any]]:
        """Fetch active KPIs from metric_registry database table with in-memory lazy caching."""
        if not self._semantic_layer_enabled or not self._db:
            return []
        if self._kpi_cache is None:
            try:
                rows = await self._db.fetch_all(
                    "SELECT metric_id, metric_name_fr, metric_name_en FROM metric_registry"
                )
                self._kpi_cache = [dict(r) for r in rows]
                logger.info("Loaded %d KPIs from metric_registry into memory cache", len(self._kpi_cache))
            except Exception as exc:
                logger.warning("Failed to fetch metric_registry from database: %s. Using static fallback.", exc)
                self._kpi_cache = []
        return self._kpi_cache

    def recognize_sync(self, query: str, detected_kpis: Optional[List[str]] = None) -> dict:
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

        res: Dict[str, Any] = {
            "primary_category": primary_cat,
            "secondary_categories": secondary_cats,
            "confidence": confidence,
            "explicit_constraints": constraints,
            "ambiguities": ambiguities,
            "requires_clarification": requires_clarification,
        }
        if self._semantic_layer_enabled:
            res["detected_kpis"] = detected_kpis or []

        # Phase 6C: upgrade with structured intent fields (backward-compatible)
        try:
            import importlib, sys as _sys
            _dir = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
            if _dir not in _sys.path:
                _sys.path.insert(0, _dir)
            from structured_intent import build_structured_intent
            struct = build_structured_intent(query)
            # Add or override structured intent fields
            for k, v in struct.items():
                if k == "ambiguities":
                    # Merge ambiguities
                    res[k] = list(set(res.get(k, []) + v))
                elif k == "requires_clarification":
                    # Structured intent can override keyword recognizer's
                    # requires_clarification=True ONLY when:
                    # 1. Structured intent says no clarification needed
                    # 2. Structured intent detected no ambiguities
                    # 3. Keyword recognizer's ambiguities are all "soft" (confidence-
                    #    related, not content-related like "too vague")
                    # This prevents overriding real ambiguity signals.
                    if not v:
                        kw_ambiguities = res.get("ambiguities", [])
                        has_hard_ambiguity = any(
                            "too short" in a.lower()
                            for a in kw_ambiguities
                        )
                        if not has_hard_ambiguity:
                            has_structure = (
                                struct.get("domain")
                                and struct.get("intent_confidence", 0) >= 0.3
                                and struct.get("task")
                                and (
                                    struct.get("metrics")
                                    or struct.get("filters_structured")
                                    or (struct.get("time_range") or {}).get("value")
                                    or struct.get("limit_requested")
                                    or struct.get("dimensions")
                                )
                            )
                            if has_structure:
                                res[k] = False
                    else:
                        res[k] = res.get(k, False) or v
                else:
                    res[k] = res.get(k, False) or v
        except Exception as exc:
            logger.warning("Failed to parse structured intent fields: %s", exc)

        # Phase 6D: general vagueness check — if structured intent confidence
        # is very low, the query is too vague to process regardless of keyword
        # matching. This catches queries like "Show me data", "I need info",
        # "Summarize everything" that the keyword matcher misclassifies.
        try:
            # Use structured intent confidence; fall back to keyword confidence
            intent_conf = res.get("intent_confidence") or res.get("confidence", 1.0)
            if intent_conf < 0.2:
                res["requires_clarification"] = True
                if not res.get("clarification_question"):
                    res["clarification_question"] = (
                        "Votre question est trop générale. Souhaitez-vous lister les détails ou calculer une agrégation ?"
                    )
        except Exception:
            pass

        # ── Request-gating assessment ──────────────────────────────────────────
        supported_capability = True
        risk_level = "safe"
        rejection_reason = None
        q_lower = query.lower()

        # Adversarial: SQL injection / prompt injection / social engineering
        adversarial_patterns = [
            r"\b(drop|truncate|delete)\s+(table|database)\b",
            r"\bdrop\s+(all\s+)?(tables?|data|database)\b",
            r"\bunion\s+select\b",
            r";\s*(select|insert|update|delete)\b",
            r"ignore\s+(all\s+)?(previous|prior|above|any)\s+(instructions|rules)",
            r"ignore\s+\w+\s+(previous|prior)\s+(instructions|rules)",
            r"ignorez\s+(les\s+)?(instructions|r[èe]gles|consignes)",
            r"act[\s_]+as[\s_]+(admin|root|superuser)",
            r"(vous\s+)?[êe]tes?\s+ maintenant\s+en\s+mode\s+admin",
            r"mode\s+administrateur",
            r"\bpretend\b.*\b(you\s+are|to\s+be)\b",
            r"\bpretend\b.*\b(no\s+restrictions|unrestricted)\b",
            r"bypass\s+(all\s+)?(auth|compliance|validation|safety|security)",
            r"bypass\s+toutes\s+les",
            r"bypassez\s+(toutes?\s+les?\s+)?(v[ée]rifications?|s[ée]curit[ée]|contr[ôo]les?)",
            r"reveal\s+(all|every|the)\s+(data|rows|records|table)",
            r"password|secret|token|credential",
            r"identifiants?\s+(de\s+)?(la\s+)?(base|donn[ée]es)",
            r"\b(exfiltrate|dump|export\s+all)\b",
        ]
        for pat in adversarial_patterns:
            if __import__("re").search(pat, q_lower):
                risk_level = "adversarial"
                supported_capability = False
                rejection_reason = "Query contains potentially adversarial patterns"
                break

        # Unsupported capabilities (English + French)
        unsupported_keywords = [
            "predict", "forecast", "what will", "future value",
            "prévoyez", "prédis", "prédire", "prévision",
            "real-time", "real time", "live feed", "streaming",
            "modify", "update", "insert", "delete",
            "modifier", "mettre à jour", "insérer", "supprimer",
            "send", "email", "sms", "create", "print", "schedule",
            "envoyer", "envoyez", "créer", "créez", "supprimez", "modifiez",
            "transfer", "initiate payment", "execute transaction",
            "transférer", "initier paiement", "exécuter transaction",
            "deploy", "restart", "shutdown",
            "déployer", "redémarrer", "arrêter",
        ]
        if risk_level == "safe":
            for kw in unsupported_keywords:
                if kw in q_lower:
                    supported_capability = False
                    risk_level = "suspicious"
                    rejection_reason = f"Query requests unsupported capability: '{kw}'"
                    break

        # Strong ambiguity escalation (already flagged by ambiguity detection)
        if risk_level == "safe" and len(ambiguities) >= 4:
            risk_level = "suspicious"
            rejection_reason = "Too many ambiguities to proceed safely"

        # Phase 6C override: if structured intent found no ambiguities and cleared
        # requires_clarification, also clear the risk_level escalation — the keyword
        # recognizer's ambiguity detector often false-positives on well-specified queries
        # that happen to mention multiple entities (e.g. "KYC status + risk score + balance").
        if res.get("requires_clarification") is False and risk_level == "suspicious":
            if rejection_reason and "ambiguities" in rejection_reason.lower():
                risk_level = "safe"
                rejection_reason = None

        res["supported_capability"] = supported_capability
        res["risk_level"] = risk_level
        res["rejection_reason"] = rejection_reason

        return res

    async def recognize(self, query: str) -> dict:
        """Async wrapper with Redis cache."""
        cached = await self._from_cache(query)
        if cached:
            logger.debug("Intent cache hit: %s", query[:40])
            # Ensure cached response contains structured intent defaults if needed
            return cached

        # Detect KPIs dynamically or statically under semantic mode
        detected_kpis: List[str] = []
        if self._semantic_layer_enabled:
            q_lower = query.lower()
            db_kpis = await self._fetch_kpi_registry()
            
            if db_kpis:
                for kpi in db_kpis:
                    metric_id = kpi["metric_id"]
                    name_fr = kpi.get("metric_name_fr") or ""
                    name_en = kpi.get("metric_name_en") or ""
                    if (metric_id.lower() in q_lower or 
                        (name_fr and name_fr.lower() in q_lower) or 
                        (name_en and name_en.lower() in q_lower)):
                        detected_kpis.append(metric_id)
            else:
                # Static patterns fallback
                for metric_id, synonyms in STATIC_KPIS.items():
                    if any(syn in q_lower for syn in synonyms):
                        detected_kpis.append(metric_id)

        result = self.recognize_sync(query, detected_kpis=detected_kpis)
        await self._to_cache(query, result)
        return result

