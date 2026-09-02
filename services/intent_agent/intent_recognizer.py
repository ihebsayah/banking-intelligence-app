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

# ── Consolidated bilingual category registry (always on) ────────────────────
# English + French keywords for all 13 allowed intent categories, plus common
# banking abbreviations. Independent of SEMANTIC_LAYER_ENABLED: basic language
# support must NOT be coupled to the semantic metadata DB layer.
#
# ponytail: token-based matching below; abbreviations handled as multiword
# phrases pre-tokenisation, since spaCy lemmatises "npl" to "npl" but "NPL
# ratio" to tokens needing phrase awareness. Upgrade to a trie if phrase count grows.

BILINGUAL_CATEGORY_REGISTRY: Dict[str, Dict[str, List[str]]] = {
    "customer_analysis": {
        "en": ["customer", "client", "segment", "demographic", "profile", "balance",
               "account_holder", "retail", "holder", "member", "user", "tiers",
               "account", "compte"],
        "fr": ["client", "clientèle", "tiers", "particulier", "profil", "segment",
               "compte", "particulier", "entreprise"],
    },
    "risk_analysis": {
        "en": ["risk", "fraud", "default", "violation", "aml", "kyc", "suspicious",
               "flag", "compliance", "sanction", "exposure", "credit_risk",
               "delinquent", "watchlist", "alert", "npl", "provision", "default",
               "bad"],
        "fr": ["risque", "fraude", "défaut", "impayé", "impayés", "créances",
               "suspicious", "blanchiment", "sanction", "exposition", "alerte",
               "alertes", "provision", "provisions", "douteuse", "douteuses",
               "mauvais", "clients à risque"],
    },
    "revenue_analysis": {
        "en": ["revenue", "income", "profit", "fee", "commission", "earning",
               "sale", "performance", "margin", "gross", "yield", "return",
               "interest", "net", "pnb", "roe", "roa", "underperform", "performer"],
        "fr": ["revenu", "revenus", "commission", "commissions", "frais", "bénéfice",
               "bénéfices", "pnb", "rentabilité", "rendement", "produit", "rapporte",
               "performe", "performance", "marge"],
    },
    "operational_analysis": {
        "en": ["volume", "count", "speed", "efficiency", "throughput", "latency",
               "queue", "processing", "rate", "capacity", "load", "operations"],
        "fr": ["volume", "efficacité", "débit", "traitement", "file", "capacité",
               "charge", "opérations"],
    },
    "geographic_analysis": {
        "en": ["region", "branch", "location", "state", "city", "geographic",
               "area", "territory", "district", "zone", "country", "market"],
        "fr": ["agence", "agences", "succursale", "ville", "région", "régions",
               "gouvernorat", "zone", "territoire"],
    },
    "product_analysis": {
        "en": ["product", "account_type", "service", "loan", "deposit", "credit",
               "investment", "insurance", "checking", "saving", "mortgage",
               "card", "portfolio", "lcr", "nsfr", "loan_to_deposit"],
        "fr": ["produit", "produits", "prêt", "prêts", "crédit", "crédits", "dépôt",
               "dépôts", "épargne", "assurance", "carte", "portefeuille", "placement",
               "liquidité"],
    },
    "compliance_analysis": {
        "en": ["compliance", "regulatory", "audit", "requirement", "regulation",
               "control", "policy", "gdpr", "sox", "sec", "report", "filing", "kyc"],
        "fr": ["conformité", "réglementaire", "audit", "régulation", "contrôle",
               "politique", "rapport", "déclaration"],
    },
    "transaction_analysis": {
        "en": ["transaction", "payment", "transfer", "wire", "ach", "movement",
               "flow", "settlement", "posting", "clearing", "remittance", "volume"],
        "fr": ["transaction", "transactions", "paiement", "paiements", "virement",
               "virements", "transfert", "flux", "mouvement", "mouvements", "remise"],
    },
    "loan_analysis": {
        "en": ["loan", "loans", "credit", "mortgage", "principal", "outstanding",
               "installment", "npl", "credit_risk", "exposure"],
        "fr": ["prêt", "prêts", "crédit", "crédits", "encours", "mensualité",
               "remboursement", "impayé", "impayés", "créance", "créances",
               "échéance"],
    },
    "kyc_analysis": {
        "en": ["kyc", "know your customer", "diligence", "verified", "unverified",
               "pep", "politically exposed"],
        "fr": ["kyc", "connaissance client", "vérifié", "non vérifié", "pep",
               "personne politiquement exposée"],
    },
    "aml_analysis": {
        "en": ["aml", "anti-money laundering", "blanchiment", "sar", "suspicious",
               "ctaf", "lcb-ft", "money laundering"],
        "fr": ["aml", "lbc", "blanchiment", "déclaration de soupçon", "soupçon",
               "douteuse", "ctaf"],
    },
    "profitability_analysis": {
        "en": ["profitability", "profit", "margin", "roe", "roa", "revenue",
               "income", "net banking income", "pnb", "cost to income"],
        "fr": ["rentabilité", "bénéfice", "bénéfices", "marge", "prob bénéfice",
               "produit net bancaire", "pnb", "coefficient d'exploitation"],
    },
    "liquidity_analysis": {
        "en": ["liquidity", "liquid", "lcr", "nsfr", "deposit", "loan to deposit",
               "cash reserve", "ldr"],
        "fr": ["liquidité", "lcr", "nsfr", "dépôt", "dépôts", "trésorerie",
               "ratio crédits / dépôts", "avoirs", "placements"],
    },
}

# Multiword phrase keywords that must be matched against the raw lowercased
# query (before/after tokenisation) — handles abbreviations and compound terms.
BILINGUAL_PHRASES: Dict[str, List[str]] = {
    "npl_ratio": ["npl ratio", "non-performing loan ratio", "taux de créances classées",
                  "créances classées", "taux de créances douteuses", "npl"],
    "kyc_compliance_rate": ["kyc compliance rate", "taux de conformité kyc"],
    "aml_alert_rate": ["aml alert rate", "taux d'alertes aml", "alertes aml"],
    "roe": ["roe", "return on equity", "rentabilité des fonds propres", "rentabilité des capitaux propres"],
    "roa": ["roa", "return on assets", "rentabilité des actifs"],
    "pnb": ["pnb", "produit net bancaire", "net banking income", "nbi"],
    "loan_to_deposit": ["loan to deposit", "ldr", "ratio crédits / dépôts", "loan to deposit ratio"],
    "lcr": ["lcr", "liquidity coverage ratio"],
}

# Map abbreviation/phrase keys to their owning intent category.
_PHRASE_TO_CATEGORY = {
    "npl_ratio": "risk_analysis",
    "kyc_compliance_rate": "compliance_analysis",
    "aml_alert_rate": "aml_analysis",
    "roe": "profitability_analysis",
    "roa": "profitability_analysis",
    "pnb": "profitability_analysis",
    "loan_to_deposit": "liquidity_analysis",
    "lcr": "liquidity_analysis",
}


def _phrase_to_category(phrase_key: str) -> str:
    return _PHRASE_TO_CATEGORY.get(phrase_key, "unknown")


# Domain families — categories whose keywords co-occur naturally as a single
# intent (synonyms describing the same subject). Used to avoid false COMPOUND.
_CATEGORY_FAMILY = {
    "customer_analysis": "customer",
    "risk_analysis": "risk_compliance",
    "compliance_analysis": "risk_compliance",
    "kyc_analysis": "risk_compliance",
    "aml_analysis": "risk_compliance",
    "revenue_analysis": "performance",
    "profitability_analysis": "performance",
    "operational_analysis": "performance",
    "product_analysis": "products",
    "loan_analysis": "credit",
    "transaction_analysis": "funds",
    "liquidity_analysis": "funds",
    "geographic_analysis": "geo",
}


def _cat_family(cat: str) -> str:
    return _CATEGORY_FAMILY.get(cat, cat)


# Categories that act as dimensions/breakdowns rather than competing intents
# (e.g. "revenue BY branch" → branch is a dimension, not a second intent).
DIMENSION_CATEGORIES = {"geographic_analysis", "operational_analysis"}


def _is_dimension_composition(q: str, top: List[tuple]) -> bool:
    """True when the top-1 is a subject and the near-tied runner-up is a
    dimension category joined by "by/per/par" — composition, not competition."""
    if len(top) < 2:
        return False
    tie_cats = {top[0][0], top[1][0]}
    if not (tie_cats & DIMENSION_CATEGORIES) or tie_cats <= DIMENSION_CATEGORIES:
        return False
    return bool("by " in q or " per " in q or " par " in q)


def _is_same_family_tie(top: List[tuple]) -> bool:
    """True when the top-1 and runner-up are near-tied categories in the SAME
    domain family (synonyms like revenue/profitability, compliance/risk) — a
    single intent pair, not competing intents."""
    if len(top) < 2:
        return False
    return _cat_family(top[0][0]) == _cat_family(top[1][0])


def _is_benign_tie(q: str, top: List[tuple]) -> bool:
    """A near-tie is benign (composition or same-family synonym) when it does NOT
    reflect competing analytical intents."""
    return _is_dimension_composition(q, top) or _is_same_family_tie(top)


# Hard (content) ambiguity codes — never cleared by structured enrichment.
HARD_AMBIGUITY_CODES = {
    "NO_INTENT_MATCH", "UNRESOLVED_REFERENCE", "COMPOUND_UNSUPPORTED",
    "AMBIGUOUS_METRIC", "AMBIGUOUS_ENTITY", "DOMAIN_UNCLEAR",
    "NO_ANALYTICAL_SUBSTANCE",
}


def _evidence_score(primary_score: int, top2_score: int, total_tokens: int,
                    ambiguity_codes: List[str]) -> float:
    """Deterministic certainty score combining signal strength and class separation.

    Components:
      - penalise total absence of evidence; reward absolute margin (top1-top2)
      - reward token coverage (how much of the query anchored the category)
      - apply a hard floor for NO_INTENT_MATCH / DOMAIN_UNCLEAR so these never
        look 'certain'.
    """
    if primary_score == 0:
        return 0.0

    margin_component = (primary_score - top2_score) / primary_score
    coverage_component = min(primary_score / max(total_tokens, 1), 1.0)
    base = 0.15 + 0.40 * margin_component + 0.35 * coverage_component

    # Hard uncertainty codes cap the score so the gating threshold can reject.
    # INTENT_CONFIDENCE_THRESHOLD = 0.31 in shared/config; a hard ambiguity must
    # land BELOW that so the orchestrator's clarification path triggers.
    if "NO_INTENT_MATCH" in ambiguity_codes or "DOMAIN_UNCLEAR" in ambiguity_codes:
        base = min(base, 0.10)
    if "UNRESOLVED_REFERENCE" in ambiguity_codes or "COMPOUND_UNSUPPORTED" in ambiguity_codes \
            or "NO_ANALYTICAL_SUBSTANCE" in ambiguity_codes:
        base = min(base, 0.28)
    if "AMBIGUOUS_METRIC" in ambiguity_codes or "AMBIGUOUS_ENTITY" in ambiguity_codes:
        base = min(base, 0.28)
    if "INTENT_TIE" in ambiguity_codes:
        base = min(base, 0.55)
    if "MISSING_TIME_CONTEXT" in ambiguity_codes:
        base = min(base, 0.70)

    return round(min(max(base, 0.0), 1.0), 4)


# Human-readable text for each machine ambiguity code.
COD_TO_TEXT = {
    "NO_INTENT_MATCH": "Query too vague — no clear category detected",
    "INTENT_TIE": "Multiple categories equally matched — please clarify focus",
    "AMBIGUOUS_METRIC": "Ambiguous metric — please clarify which measure to use",
    "AMBIGUOUS_ENTITY": "Unclear primary entity — please specify customer, branch or account",
    "MISSING_TIME_CONTEXT": "Missing time period — please specify the period to analyze",
    "UNRESOLVED_REFERENCE": "Reference to prior context is unresolved — please rephrase",
    "COMPOUND_UNSUPPORTED": "Compound request combines multiple analytical intents — please separate them",
    "TOO_SHORT": "Query too short — please provide more detail",
    "DOMAIN_UNCLEAR": "This does not appear to be a banking analytics question",
    "NO_ANALYTICAL_SUBSTANCE": "Query names a data area but specifies no metric, dimension or period",
}


_NON_BANKING_HINTS = [
    "joke", "weather", "time is it", "heure", "password", "reset", "quantum",
    "recipe", "movie", "song", "email", "write", "send", "print", "sms",
    "what is your name", "who are you", "hello", "bonjour", "merci", "thanks",
]


def _is_off_domain(q: str) -> bool:
    """Heuristic: query has non-banking content cues and little/no banking intent."""
    banking_cues = 0
    for cat, langs in BILINGUAL_CATEGORY_REGISTRY.items():
        for kw in list(langs["en"]) + list(langs["fr"]):
            if kw in q:
                banking_cues += 1
    for hint in _NON_BANKING_HINTS:
        if hint in q:
            return banking_cues == 0
    return False


# Word/phrase hints that signal an analytical action on the data — a query carrying
# any of these is actionable even without parsed metric/dimension/time fields.
_ANALYTICAL_HINT_WORDS = [
    # measure verbs / quantifiers
    "show", "display", "list", "count", "compute", "calculate", "calc",
    "how many", "how much", "combien", "nombre", "total", "sum", "average", "moyenne",
    "top", "meilleur", "meilleur", "worst", "pire", "rank", "rang",
    # concrete measures / measure noun
    "status", "etat", "state", "répartition", "distribution", "reparti",
    "balance", "volume", "taux", "ratio", "rate", "number of", "solde", "montant",
    # analytical verbs
    "compare", "comparer", "perform", "performent", "performe", "underperform",
    "expose", "exposed", "exposé", "analyse", "analyze", "measur", "measure",
    "répartition", "classement",
    # interrogative measures
    "quel est", "quelle est", "what is", "which", "qui sont", "où", "where",
]
# Time phrases (bilingual) that resolve when/period.
_ANALYTICAL_HINT_TIME = [
    "this year", "this quarter", "this month", "this week", "today", "yesterday",
    "last year", "last quarter", "last month", "last week", "last 7 days",
    "last 30 days", "last 90 days", "year-to-date", "ytd", "since", "by year",
    "cette année", "ce trimestre", "ce mois", "cette semaine", "aujourd",
    "hier", "l'an dernier", "l'annee derniere", "dernier mois", "mois dernier",
    "derniers 7 jours", "derniers 30 jours", "depuis", "année dernière",
    "cet exercice", "2024", "2025", "2026",
]
# Dimension words that scope the breakdown.
_ANALYTICAL_HINT_DIM = [
    "by branch", "per branch", "par agence", "per region", "by region", "par région",
    "per segment", "by segment", "par segment", "by product", "par produit",
    "par gouvernorat", "by governorate", "geographique", "géographique", "geographic",
    "per city", "par ville", "by state", "par type", "by type",
]


def _has_analytical_hint(query: str) -> bool:
    """True if the raw query carries an explicit analytical action/measure/dimension.

    Single words are matched at word boundaries to avoid substring false positives
    (e.g. "count" must NOT match inside "accounts").
    """
    import re as _re
    q_lower = query.lower()
    for w in _ANALYTICAL_HINT_WORDS:
        pattern = _re.escape(w) + r"\b" if w.isalpha() and " " not in w else _re.escape(w)
        if _re.search(pattern, q_lower):
            return True
    for t in _ANALYTICAL_HINT_TIME:
        if t in q_lower:
            return True
    for d in _ANALYTICAL_HINT_DIM:
        if d in q_lower:
            return True
    return False

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

    def _score_categories(self, query: str, tokens: List[str]) -> Dict[str, int]:
        """Score all 13 categories from the bilingual registry (EN+FR always on).

        Phrase/abbreviation keywords are matched against the raw query; single
        tokens are matched against spaCy lemmas.
        """
        q_lower = query.lower()
        scores: Dict[str, int] = {cat: 0 for cat in BILINGUAL_CATEGORY_REGISTRY}

        # Phrase + abbreviation matching (multiword, raw query)
        for phrase_key, phrases in BILINGUAL_PHRASES.items():
            for phrase in phrases:
                if phrase in q_lower:
                    scores[_phrase_to_category(phrase_key)] += 2
                    break

        # Token-level keyword matching
        for token in tokens:
            for cat, langs in BILINGUAL_CATEGORY_REGISTRY.items():
                if token in langs["en"] or token in langs["fr"]:
                    scores[cat] += 1
        return scores

    def _detect_ambiguities(
        self, query: str, scores: Dict[str, int], primary: str
    ) -> List[str]:
        """Detect ambiguity and return human-readable reasons (backward compat).

        Machine-readable reason codes are returned separately via
        `_ambiguity_codes` (or exposed on the response).
        """
        codes = self._ambiguity_codes(query, scores, primary)
        return [COD_TO_TEXT[c] for c in codes if c in COD_TO_TEXT]

    def _ambiguity_codes(self, query: str, scores: Dict[str, int], primary: str) -> List[str]:
        """Produce a deduplicated, machine-readable set of ambiguity reason codes."""
        codes: List[str] = []
        q = query.lower()

        top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top1_score = top[0][1] if top else 0
        top2_score = top[1][1] if len(top) > 1 else 0

        # Zero-match → strongest signal
        if top1_score == 0:
            codes.append("NO_INTENT_MATCH")
            return codes

        # Top-2 closeness (margin, not just ratio). A near-tie between a subject
        # category and a dimension category joined by "by/per/par" is COMPOSITION
        # (e.g. "revenue by branch"), not competition → no INTENT_TIE.
        if top2_score > 0:
            relative_margin = (top1_score - top2_score) / top1_score if top1_score else 0
            if not _is_benign_tie(q, top):
                if relative_margin < 0.25:
                    codes.append("INTENT_TIE")

        # Ambiguous metric terms — fire ONLY when the query genuinely pairs two
        # competing measures/entities, not on a bare keyword mention.
        balance_owner = "customer_analysis" if "balance" in q else None
        rev_cat = "revenue_analysis"
        if "balance" in q and scores.get("customer_analysis", 0) > 0 and scores.get("revenue_analysis", 0) > 0:
            # customer balance vs revenue balance both plausible → ambiguous metric
            codes.append("AMBIGUOUS_METRIC")
        if ("performance" in q or "performe" in q or "performent" in q) and len(q.split()) < 6:
            # 'performe' could be revenue OR operational → ambiguous metric
            if scores.get("revenue_analysis", 0) > 0 and scores.get("operational_analysis", 0) > 0:
                codes.append("AMBIGUOUS_METRIC")
        # Comparison of preference without specifying the measure.
        if ("better" in q or "meilleur" in q or "mieux" in q or "best" in q) and (
            "than" in q or "versus" in q or "que" in q or "que les" in q or "et" in q
        ):
            codes.append("AMBIGUOUS_METRIC")

        # Entity ambiguity
        if ("customer" in q or "client" in q) and ("branch" in q or "agence" in q):
            codes.append("AMBIGUOUS_ENTITY")

        # Risk without threshold/time context
        if primary == "risk_analysis" and "high risk" in q:
            codes.append("AMBIGUOUS_METRIC")
        if primary == "risk_analysis" and not any(
            w in q for w in ["today", "this week", "this month", "this quarter",
                              "this year", "last", "since", "ytd", "récemment",
                              "dernier", "dernière", "trimestre", "mois"]
        ):
            codes.append("MISSING_TIME_CONTEXT")

        # Unresolved references / pronouns (no conversation memory)
        if any(w in q for w in [" and last month", "compare them", "and them",
                                "et eux", "them", "those", "those ones", "et pour",
                                "same for", "same"]):
            if len(q.split()) <= 6:
                codes.append("UNRESOLVED_REFERENCE")
                # Do NOT also flag as vague; UNRESOLVED_REFERENCE is more specific

        # Compound / multi-intent requests. Fire ONLY when two DIFFERENT domain
        # families score AND an explicit conjunction/join is present. Co-occurring
        # synonyms within one family (e.g. "KYC compliance rate") are NOT compound.
        scored_cats = [cat for cat, sc in scores.items() if sc > 0]
        family_sel = {_cat_family(c) for c in scored_cats}
        has_join = any(
            w in q for w in [" and ", " et ", "compare", "comparer",
                             "together", "ensemble", "both", "autant", "ainsi que"]
        )
        if len(family_sel) >= 2 and has_join:
            codes.append("COMPOUND_UNSUPPORTED")

        # Off-domain heuristic (additive; no banking keywords)
        if top1_score <= 1 and _is_off_domain(q):
            codes.append("DOMAIN_UNCLEAR")

        # Too short with no clear intent
        if len(q.split()) <= 2 and top1_score <= 1:
            codes.append("TOO_SHORT")

        return list(dict.fromkeys(codes))

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
        Returns a plain dict matching IntentResponse schema (additive fields).
        """
        tokens = self._tokenise(query)
        total_tokens = max(len(tokens), 1)

        scores = self._score_categories(query, tokens)

        # Primary = max score category. NO arbitrary default on zero match.
        top = sorted(scores.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
        primary_cat = top[0][0]
        primary_score = top[0][1]
        top2_score = top[1][1] if len(top) > 1 else 0

        # Zero-match → explicit unknown (never a fabricated intent)
        if primary_score == 0:
            primary_cat = "unknown"

        # Secondary = categories with ≥30 % of primary's score (excluding primary)
        secondary_cats = (
            [cat for cat, sc in scores.items()
             if cat != primary_cat and sc > 0 and (primary_score == 0 or sc / primary_score >= 0.30)]
            if primary_score > 0 else []
        )
        secondary_cats.sort(key=lambda c: -scores[c])

        # Evidence score (classification certainty, not density). Raw density was
        # (primary_score/total_tokens)*0.90+0.05 — disconnected from class separation.
        is_dim_composition = (primary_score > 0 and _is_benign_tie(query, top))
        ambiguity_codes = self._ambiguity_codes(query, scores, primary_cat)
        # A subject+dimension composition (e.g. "revenue by branch") is a single
        # intent; the dimension contributes to confidence, not a competing margin.
        effective_top2 = 0 if is_dim_composition else top2_score
        absolute_margin = primary_score - effective_top2
        relative_margin = (
            (primary_score - effective_top2) / primary_score if primary_score > 0 else 0.0
        )

        intent_evidence_score = _evidence_score(
            primary_score=primary_score,
            top2_score=effective_top2,
            total_tokens=total_tokens,
            ambiguity_codes=ambiguity_codes,
        )

        # Keep `confidence` for API compatibility: map evidence score into the old
        # 0.0–1.0 range. Meaning is now documented as evidence/certainty, not density.
        confidence = round(intent_evidence_score, 4)

        constraints = _extract_constraints(query)
        ambiguities = self._detect_ambiguities(query, scores, primary_cat)

        # Hard ambiguities always force clarification (never overridden later).
        has_hard_ambiguity = any(c in HARD_AMBIGUITY_CODES for c in ambiguity_codes)

        res: Dict[str, Any] = {
            "primary_category": primary_cat,
            "secondary_categories": secondary_cats,
            "confidence": confidence,
            "intent_evidence_score": round(intent_evidence_score, 4),
            "top1_score": primary_score,
            "top2_score": top2_score,
            "absolute_margin": absolute_margin,
            "relative_margin": round(relative_margin, 4) if primary_score > 0 else None,
            "ambiguity_codes": ambiguity_codes,
            "explicit_constraints": constraints,
            "ambiguities": ambiguities,
            "requires_clarification": has_hard_ambiguity,
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
                    res[k] = list(dict.fromkeys(res.get(k, []) + v))
                elif k == "requires_clarification":
                    # Fixed (Step 11): structured enrichment may ADD evidence but may
                    # NOT erase a HARD ambiguity. Only SOFT ambiguities (minor keyword
                    # overlap / secondary presence) may be cleared by strong structure.
                    if not v:
                        if has_hard_ambiguity:
                            res[k] = True  # never clear a hard ambiguity
                        else:
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
            # Use structured intent confidence; fall back to evidence score
            intent_conf = res.get("intent_confidence") or res.get("confidence", 1.0)
            if intent_conf < 0.2:
                res["requires_clarification"] = True
                if not res.get("clarification_question"):
                    res["clarification_question"] = (
                        "Votre question est trop générale. Souhaitez-vous lister les détails ou calculer une agrégation ?"
                    )
        except Exception:
            pass

        # Phase 6E: analytical-substance gate (Step 11). A category keyword match is
        # NOT sufficient for a legible intent: the query must carry at least one
        # analytical signal (metric, dimension, time range, limit, filter, or an
        # explicit measure verb/quantifier in the raw text). A bare descriptive
        # statement ("I need info about customers", "Tell me about accounts") matches
        # a category but has nothing to compute/list → genuinely vague, must clarify.
        if res.get("primary_category") != "unknown" and not res.get("requires_clarification"):
            substance_fields = res
            has_substance = bool(
                substance_fields.get("metrics")
                or substance_fields.get("dimensions")
                or substance_fields.get("filters_structured")
                or substance_fields.get("limit_requested")
                or (substance_fields.get("time_range") or {}).get("value")
                or substance_fields.get("detected_kpis")
                or _has_analytical_hint(query)
            )
            if not has_substance:
                codes = res.setdefault("ambiguity_codes", [])
                if "NO_ANALYTICAL_SUBSTANCE" not in codes:
                    codes.append("NO_ANALYTICAL_SUBSTANCE")
                res["requires_clarification"] = True
                # Force certainty below the orchestrator gate (0.31) so the
                # clarification path triggers rather than silently auto-accepting.
                res["intent_evidence_score"] = round(min(res.get("intent_evidence_score", 1.0), 0.28), 4)
                res["confidence"] = res["intent_evidence_score"]
                res["ambiguities"] = list(dict.fromkeys(
                    res.get("ambiguities", [])
                    + ["Query names a data area but specifies no metric, dimension or period — please clarify"]
                ))
                if not res.get("clarification_question"):
                    res["clarification_question"] = (
                        "Vous citez un domaine de données sans mesure précise. "
                        "Quelle métrique et quelle période souhaitez-vous analyser ?"
                    )

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
        # Step 11: this override must not run when a HARD ambiguity was detected.
        if res.get("requires_clarification") is False and risk_level == "suspicious":
            if rejection_reason and "ambiguities" in rejection_reason.lower():
                if not has_hard_ambiguity:
                    risk_level = "safe"
                    rejection_reason = None

        # Off-domain routing: zero/weak banking evidence → unsupported capability so
        # the orchestrator gate rejects BEFORE classification (no fabricated intent).
        if primary_cat == "unknown" or "DOMAIN_UNCLEAR" in ambiguity_codes:
            supported_capability = False
            if risk_level == "safe":
                rejection_reason = "Query is outside the supported banking analytics scope" \
                    if "DOMAIN_UNCLEAR" in ambiguity_codes else "No recognizable intent detected"
            if not res.get("clarification_question"):
                res["clarification_question"] = (
                    "Cette demande semble hors du périmètre bancaire. Veuillez poser une "
                    "question d'analyse de données bancaires."
                )

        res["supported_capability"] = supported_capability
        res["risk_level"] = risk_level
        res["rejection_reason"] = rejection_reason

        # Deterministic decision: AUTO_ACCEPT / CLARIFY / REJECT.
        evidence = res.get("intent_evidence_score", 0.0)
        if not supported_capability or risk_level in ("adversarial", "suspicious"):
            res["decision"] = "REJECT"
        elif res.get("requires_clarification") or evidence < 0.20:
            res["decision"] = "CLARIFY"
        else:
            res["decision"] = "AUTO_ACCEPT"

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

