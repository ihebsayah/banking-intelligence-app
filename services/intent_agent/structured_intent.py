"""
services/intent_agent/structured_intent.py
Structured intent extraction logic for French and English queries.
"""
import re
import sys
import os
from typing import Dict, List, Optional, Any

# Ensure services/shared is accessible
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../shared")))

from shared.provenance import Provenance

FRENCH_STOPWORDS = {"le", "la", "les", "de", "des", "en", "par", "pour", "dans", "sur", "avec", "sans", "est", "sont", "un", "une", "ce", "cette", "ces"}
FRENCH_KEYWORDS = {
    "créances", "douteuses", "impayés", "encours", "dépôts", "agence", "gouvernorat",
    "client", "clientèle", "conformité", "alertes", "rentabilité", "liquidité",
    "provisions", "garanties", "taux", "prêt", "prêts", "crédit", "crédits", "virement", "virements",
    "bénéficiaire", "bénéficiaires", "tous", "chaque", "par", "selon", "mouvement", "mouvements"
}

# Domain vocabulary (English & French)
DOMAINS = {
    "customer": [
        "customer", "client", "segment", "demographic", "profile", "tiers",
        "particulier", "entreprise", "clientèle", "relationship manager", "rm", "conseiller", "commercial"
    ],
    "accounts": [
        "account", "compte", "current account", "compte courant", "compte de dépôt",
        "checking", "savings", "solde", "available balance", "disponible"
    ],
    "deposits": [
        "deposit", "dépôt", "épargne", "term deposit", "placements", "avoirs"
    ],
    "transactions": [
        "transaction", "payment", "transfer", "wire", "virement", "transfert",
        "flux", "mouvement", "paiement", "channel", "canal"
    ],
    "loans": [
        "loan", "loans", "credit", "prêt", "crédit", "mensualité", "outstanding",
        "remboursement", "outstanding_balance", "outstanding balance", "principal", "échéancier",
        "loan_contracts", "installment", "disbursement", "maturity"
    ],
    "credit risk": [
        "npl", "provision", "default", "défaut", "créances douteuses", "sinistre",
        "risques", "risk", "credit risk", "delinquent", "classées", "souffrance",
        "non_performing", "npl_amount", "provision_amount"
    ],
    "liquidity": [
        "liquidity", "liquidité", "lcr", "nsfr", "tresorerie", "trésorerie", "ldr"
    ],
    "profitability": [
        "revenue", "income", "profit", "fee", "commission", "margin", "yield",
        "pnb", "net banking income", "roe", "roa", "rentabilité", "bénéfice", "produit net bancaire",
        "fee_income", "interest_income"
    ],
    "kyc": [
        "kyc", "know your customer", "connaissance client", "diligence", "verified",
        "pep", "politically exposed", "connaissance du client"
    ],
    "aml": [
        "aml", "anti-money laundering", "blanchiment", "ctaf", "suspicious",
        "fraude", "lbc", "lcb-ft", "soupçon", "suspicious_activity_reports"
    ],
    "compliance": [
        "compliance", "regulatory", "audit", "requirement", "control", "policy",
        "conformité", "réglementaire", "sox", "gdpr", "constats",
        "compliance_violations", "compliance_cases", "audit_findings",
        "sanctions", "screening", "sanctions screening", "ofac", "lists"
    ],
    "branch and regional performance": [
        "branch", "region", "state", "city", "location", "succursale",
        "gouvernorat", "agence", "ville", "région", "agences", "performance"
    ]
}

# Task vocabulary
TASKS = {
    "detail_listing": [
        "list", "show", "details", "retrieve", "find", "get", "afficher", "lister",
        "détails", "trouver", "sélectionner", "donner"
    ],
    "aggregation": [
        "total", "sum", "average", "avg", "count", "somme", "moyenne", "nombre",
        "totaliser", "calculer", "montant total", "compter", "quantité", "how many",
        "combien"
    ],
    "comparison": [
        "compare", "versus", "vs", "comparer", "comparaison", "différence", "comparé"
    ],
    "ranking": [
        "top", "bottom", "best", "worst", "highest", "lowest", "max", "min",
        "most", "fewest",
        "plus grand", "plus petit", "meilleur", "pire", "maximum", "minimum"
    ],
    "trend": [
        "trend", "growth", "rate", "evolution", "croissance", "évolution", "tendance", "évoluer"
    ],
    "distribution": [
        "distribution", "spread", "histogram", "segmentation", "répartition", "distribuer"
    ],
    "anomaly investigation": [
        "anomaly", "alert", "flag", "suspicious", "anomalie", "alerte", "drapeau",
        "fraude", "suspect", "anormal"
    ],
    "ratio calculation": [
        "ratio", "percentage", "pourcentage", "lcr", "nsfr", "roe", "roa", "ldr", "ratio"
    ],
    "portfolio analysis": [
        "portfolio", "portefeuille", "encours total", "portefeuilles"
    ],
    "time-series analysis": [
        "daily", "monthly", "yearly", "over time", "par mois", "par an", "historique",
        "temps", "série", "évolution mensuelle"
    ]
}

# Dimension names mapping to canonical tables/columns
DIMENSION_KEYWORDS = {
    "customers.segment": ["segment", "segment clientèle", "client segment"],
    "branches.region_id": ["region", "région", "region_id"],
    "branches.name": ["branch", "agence", "branch name", "nom d'agence"],
    "branches.state": ["state", "état"],
    "branches.city": ["city", "ville"],
    "accounts.account_type": ["account type", "type de compte", "account_type"],
    "customers.kyc_verified": ["kyc status", "statut kyc", "kyc_verified", "vérifié kyc"],
    "customers.risk_score": ["risk level", "niveau de risque", "risk_score"],
    "loan_contracts.loan_type": ["loan type", "type de prêt", "loan_type"],
    "loan_contracts.status": ["loan status", "statut prêt", "loan_status"],
    "fee_income.fee_type": ["fee type", "type de frais", "fee_type"],
}

# Authoritative KPIs (metric_id -> Synonyms)
# Exclude bare keywords to separate entities from metrics
GLOSSARY_KPIS = {
    "npl_ratio": ["npl ratio", "taux de créances classées", "non-performing loan ratio", "taux de sinistralité", "taux de défaut", "npl rate", "taux de créances douteuses"],
    "roe": ["roe", "return on equity", "rentabilité des fonds propres", "rentabilité des capitaux propres"],
    "roa": ["roa", "return on assets", "rentabilité des actifs"],
    "kyc_compliance_rate": ["kyc compliance rate", "taux de conformité kyc", "taux de conformité"],
    "aml_alert_rate": ["aml alert rate", "taux d'alertes aml", "taux alertes aml"],
    "loan_to_deposit": ["loan to deposit", "ldr", "ratio crédits / dépôts", "ratio crédits/dépôts", "loan to deposit ratio"],
    "pnb": ["pnb", "produit net bancaire", "net banking income", "nbi"]
}

# Explicit analytical triggers required for ratio/rate metrics
ANALYTICAL_TRIGGERS = {
    "rate", "ratio", "total", "average", "avg", "count", "exposure", "balance", 
    "taux", "total", "moyenne", "nombre", "exposition", "solde", "somme", 
    "percentage", "pourcentage", "growth", "croissance", "evolution", "évolution"
}

# Explicit output fields vocabulary
REQUESTED_FIELDS_VOCAB = {
    "customer_id": ["customer id", "id client", "customer_id"],
    "name": ["name", "nom"],
    "email": ["email", "courriel"],
    "phone": ["phone", "téléphone", "tel"],
    "segment": ["segment", "segment clientèle"],
    "risk_score": ["risk score", "score de risque", "risk_score", "note de risque"],
    "kyc_verified": ["kyc verified", "kyc status", "statut kyc", "vérifié", "kyc_verified"],
    "status": ["status", "statut", "état", "active status"],
    "balance": ["balance", "solde", "avoirs"],
    "amount": ["amount", "montant"],
    "transaction_date": ["date", "transaction date", "date de transaction"],
    "branch_id": ["branch", "agence", "branch id", "nom d'agence"],
    "governorate": ["governorate", "gouvernorat"],
    "region": ["region", "région"],
    "days_past_due": ["days past due", "dpd", "jours de retard", "retard", "days_past_due"],
    "outstanding_balance": ["outstanding balance", "encours", "capital restant dû", "outstanding_balance"],
    "principal_amount": ["principal", "principal amount", "montant du prêt"],
    "pnb": ["pnb", "produit net bancaire", "net banking income"],
    "roe": ["roe", "return on equity", "rentabilité des fonds propres"],
    "roa": ["roa", "return on assets", "rentabilité des actifs"]
}

# Clarification templates for domain ambiguity
CLARIFICATION_TEMPLATES = {
    "risk": "Par risque, souhaitez-vous analyser le score de risque client, les créances classées (NPL) ou les alertes AML ?",
    "revenue": "Par revenu, souhaitez-vous analyser les commissions, les intérêts ou le produit net bancaire (PNB) ?",
    "account": "Par compte, souhaitez-vous lister les comptes courants, les comptes épargne ou le solde global ?",
    "general": "Votre question est trop générale. Souhaitez-vous lister les détails ou calculer une agrégation ?"
}

def detect_language(query: str) -> str:
    """Detect language based on stop words and character frequencies."""
    q_lower = query.lower()
    words = set(re.findall(r"\b\w+\b", q_lower))
    
    fr_score = len(words.intersection(FRENCH_STOPWORDS)) + len(words.intersection(FRENCH_KEYWORDS))
    return "fr" if fr_score > 0 else "en"

def extract_domain(query: str) -> tuple:
    """Detect business domain and calculate domain confidence."""
    q_lower = query.lower()
    scores = {dom: 0 for dom in DOMAINS}
    for dom, kws in DOMAINS.items():
        for kw in kws:
            if re.search(rf'\b{re.escape(kw)}', q_lower):
                scores[dom] += 2 if len(kw.split()) > 1 else 1
    
    if max(scores.values()) == 0:
        return "customer", 0.1  # low confidence — no domain keywords matched
    
    sorted_doms = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary_domain = sorted_doms[0][0]
    score_val = sorted_doms[0][1]
    
    confidence = min(0.2 + 0.1 * score_val, 0.99)
    return primary_domain, confidence

def extract_metrics(query: str) -> tuple:
    """Match KPIs against glossary registry, requiring analytical triggers for ratio/rate metrics."""
    q_lower = query.lower()
    detected = []
    reasons = []
    
    has_trigger = any(t in q_lower for t in ANALYTICAL_TRIGGERS)
    self_triggering = {"roe", "roa", "pnb", "ldr", "loan_to_deposit"}
    
    for metric_id, synonyms in GLOSSARY_KPIS.items():
        needs_trigger = metric_id not in self_triggering
        
        for syn in synonyms:
            if syn in q_lower:
                # Synonym itself might have the trigger (e.g., "npl ratio" contains "ratio")
                syn_has_trigger = any(t in syn for t in ANALYTICAL_TRIGGERS)
                if not needs_trigger or syn_has_trigger or has_trigger:
                    detected.append(metric_id)
                    reasons.append(f"Synonym match: '{syn}' -> '{metric_id}'")
                    break
                
    confidence = 0.95 if detected else 0.5
    return list(set(detected)), reasons, confidence

def extract_task(query: str, detected_metrics: List[str] = []) -> tuple:
    """Detect analytical task, separating listing requests with 'by/par' grouping from aggregations."""
    q_lower = query.lower()
    
    has_listing_verb = any(w in q_lower for w in ["list", "show", "details", "retrieve", "find", "get", "history", "alerts", "report history", "lister", "afficher", "détails", "trouver", "sélectionner", "donner"])
    has_agg_verb = any(w in q_lower for w in ["total", "sum", "average", "avg", "count", "somme", "moyenne", "nombre", "totaliser", "calculer", "montant total", "compter", "quantité", "rate", "ratio", "taux", "pnb", "roe", "roa", "ldr"])
    has_grouping = any(w in q_lower for w in ["by ", "par ", "selon "])
    has_metric = len(detected_metrics) > 0
    
    # Grouping ONLY produces aggregation if we have an explicit metric or an aggregate trigger verb
    if has_grouping:
        if has_metric or has_agg_verb:
            return "aggregation", 0.95
        else:
            return "detail_listing", 0.95
            
    # Listing verbs without aggregation keywords -> detail_listing
    if has_listing_verb and not has_agg_verb and not has_metric:
        return "detail_listing", 0.7
        
    # Fallback to standard keyword matching
    scores = {task: 0 for task in TASKS}
    for task, kws in TASKS.items():
        for kw in kws:
            if kw in q_lower:
                scores[task] += 2 if len(kw.split()) > 1 else 1
                
    if not scores or max(scores.values()) == 0:
        if has_listing_verb:
            return "detail_listing", 0.7
        return "aggregation", 0.6
        
    sorted_tasks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_tasks[0][0], min(0.6 + 0.1 * sorted_tasks[0][1], 0.99)

def extract_dimensions(query: str) -> List[str]:
    """Detect dimensions for GROUP BY clause."""
    q_lower = query.lower()
    detected = []
    
    by_patterns = [r"\bby\s+(\w+(?:\s+\w+)?)", r"\bpar\s+(\w+(?:\s+\w+)?)", r"\bselon\s+(\w+(?:\s+\w+)?)"]
    potential_dims = []
    for pattern in by_patterns:
        matches = re.findall(pattern, q_lower)
        potential_dims.extend(matches)
        
    for canonical, synonyms in DIMENSION_KEYWORDS.items():
        for syn in synonyms:
            if syn in q_lower:
                detected.append(canonical)
                break
                
    return list(set(detected))

def extract_requested_fields(query: str) -> List[str]:
    """Extract explicitly requested fields to display."""
    q_lower = query.lower()
    fields = []
    for canonical, synonyms in REQUESTED_FIELDS_VOCAB.items():
        for syn in synonyms:
            # Simple substring match for prompt constraints
            if syn in q_lower:
                fields.append(canonical)
                break
    return list(set(fields))

def extract_time_range(query: str) -> Dict[str, Any]:
    """Extract relative time ranges."""
    q_lower = query.lower()
    
    # English matches
    m_days_en = re.search(r"\blast\s+(\d+)\s+days?\b", q_lower)
    m_months_en = re.search(r"\blast\s+(\d+)\s+months?\b", q_lower)
    m_y_en = re.search(r"\blast\s+year\b", q_lower)
    m_q_en = re.search(r"\blast\s+quarter\b", q_lower)
    m_ytd_en = re.search(r"\bytd\b|\byear\s+to\s+date\b", q_lower)
    
    # French matches
    m_days_fr = re.search(r"\b(\d+)\s+derniers\s+jours\b", q_lower)
    m_months_fr = re.search(r"\b(\d+)\s+derniers\s+mois\b", q_lower)
    m_y_fr = re.search(r"\bdernière\s+année\b|\bl'année\s+dernière\b", q_lower)
    m_q_fr = re.search(r"\bdernier\s+trimestre\b", q_lower)
    m_ytd_fr = re.search(r"\bdepuis\s+le\s+début\s+de\s+l'année\b", q_lower)
    
    # Month/Year without digits
    m_month_word_en = re.search(r"\blast\s+month\b", q_lower)
    m_month_word_fr = re.search(r"\bdernier\s+mois\b|\bmois\s+dernier\b", q_lower)
    m_year_word_fr = re.search(r"\bdernière\s+année\b|\bl'année\s+dernière\b", q_lower)
    
    if m_days_en:
        return {"type": "relative", "value": f"last_{m_days_en.group(1)}_days"}
    if m_days_fr:
        return {"type": "relative", "value": f"last_{m_days_fr.group(1)}_days"}
        
    if m_months_en:
        return {"type": "relative", "value": f"last_{m_months_en.group(1)}_months"}
    if m_months_fr:
        return {"type": "relative", "value": f"last_{m_months_fr.group(1)}_months"}
        
    if m_month_word_en or m_month_word_fr:
        return {"type": "relative", "value": "last_30_days"}
        
    if m_y_en or m_y_fr or m_year_word_fr:
        return {"type": "relative", "value": "last_year"}
    if m_q_en or m_q_fr:
        return {"type": "relative", "value": "last_quarter"}
    if m_ytd_en or m_ytd_fr:
        return {"type": "relative", "value": "ytd"}

    m_year_fr_en = re.search(r"\ben\s+(20\d{2})\b", q_lower)
    if m_year_fr_en:
        return {"type": "absolute", "value": m_year_fr_en.group(1)}
    m_year_en = re.search(r"\bin\s+(20\d{2})\b", q_lower)
    if m_year_en:
        return {"type": "absolute", "value": m_year_en.group(1)}

    return {"type": "none", "value": None}

def extract_limit(query: str) -> Optional[int]:
    """Extract query limits like Top N."""
    q_lower = query.lower()
    m_top = re.search(r"\btop\s+(\d+)\b|\bles\s+(\d+)\s+premiers\b", q_lower)
    if m_top:
        limit_val = m_top.group(1) or m_top.group(2)
        return int(limit_val)
    m_limit = re.search(r"\blimit\s+(\d+)\b|\blimite\s+de\s+(\d+)\b", q_lower)
    if m_limit:
        limit_val = m_limit.group(1) or m_limit.group(2)
        return int(limit_val)
    _WORD_NUMS = {
        "ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
    }
    m_word_top = re.search(r"\btop\s+(\w+)\b", q_lower)
    if m_word_top and m_word_top.group(1) in _WORD_NUMS:
        return _WORD_NUMS[m_word_top.group(1)]
    m_word_limit = re.search(r"\b(\w+)\s+(?:customers?|clients?|accounts?|comptes?|branches?|loans?|prêts?)\b", q_lower)
    if m_word_limit and m_word_limit.group(1) in _WORD_NUMS:
        return _WORD_NUMS[m_word_limit.group(1)]
    return None

def detect_ambiguities_structured(query: str, domain: str) -> List[str]:
    """Identify ambiguities based on keywords and domain."""
    q_lower = query.lower()
    amb = []
    if "risk" in q_lower or "risque" in q_lower:
        if not any(w in q_lower for w in ["npl", "classées", "douteuses", "aml", "alertes", "score", "kyc", "scoring"]):
            amb.append("ambiguous_risk_metric")
    if "revenue" in q_lower or "revenu" in q_lower or "pnb" in q_lower:
        if not any(w in q_lower for w in ["commission", "intérêt", "pnb", "produit net bancaire", "bénéfice", "fee", "frais"]):
            amb.append("ambiguous_revenue_metric")
    if "compte" in q_lower or "account" in q_lower:
        if not any(w in q_lower for w in ["courant", "épargne", "checking", "savings", "type", "solde", "balance"]):
            amb.append("ambiguous_account_type")
            
    # Generic short query check
    # Exempt queries with explicit aggregation verbs or ranking verbs
    has_explicit_task = any(w in q_lower for w in [
        "total", "sum", "average", "count", "how many", "combien",
        "top", "bottom", "rank", "classez", "plus", "moins",
        "by", "par", "selon", "per", "pour", "les", "the", "which", "quel",
        "list", "show", "afficher", "lister", "donner",
        "customers", "clients", "branches", "accounts", "comptes",
        "transactions", "loans", "prêts", "kyc", "aml", "compliance",
    ])
    if len(q_lower.split()) < 4 and not has_explicit_task:
        amb.append("too_short_query")
    elif len(q_lower.split()) < 6 and not has_explicit_task:
        amb.append("too_short_query")
        
    return amb

def build_structured_intent(query: str) -> Dict[str, Any]:
    """Generate structured query analysis."""
    lang = detect_language(query)
    domain, dom_conf = extract_domain(query)
    metrics, met_reasons, met_conf = extract_metrics(query)
    task, task_conf = extract_task(query, metrics)
    dimensions = extract_dimensions(query)
    requested_fields = extract_requested_fields(query)
    time_range = extract_time_range(query)
    limit = extract_limit(query)
    
    # Filter extraction helper using flexible regex
    filters = []
    q_lower = query.lower()
    
    # Check boolean kyc_verified filter
    if "kyc_verified = false" in q_lower or "non vérifiés" in q_lower or "kyc non vérifié" in q_lower or "kyc_verified=false" in q_lower:
        filters.append({"column": "customers.kyc_verified", "operator": "=", "value": False})
    
    # Check risk_score filter with regex
    risk_match = re.search(r"risk\s*score\s*(>|>=|<|<=|=)\s*([0-9.]+)", q_lower)
    if risk_match:
        op = risk_match.group(1)
        val = float(risk_match.group(2))
        filters.append({"column": "customers.risk_score", "operator": op, "value": val})
    elif "risk_score" in q_lower:
        risk_match_alt = re.search(r"risk_score\s*(>|>=|<|<=|=)\s*([0-9.]+)", q_lower)
        if risk_match_alt:
            op = risk_match_alt.group(1)
            val = float(risk_match_alt.group(2))
            filters.append({"column": "customers.risk_score", "operator": op, "value": val})
    elif "haut risque" in q_lower or "high-risk" in q_lower:
        filters.append({"column": "customers.risk_score", "operator": ">=", "value": 0.7})

    if any(w in q_lower for w in ["overdue", "past due", "en retard", "impayés"]):
        filters.append({"column": "loan_contracts.status", "operator": "=", "value": "overdue"})
    if any(w in q_lower for w in ["clôturés", "cloturés", "closed", "fermés"]):
        filters.append({"column": "accounts.status", "operator": "=", "value": "closed"})
        
    ambiguities = detect_ambiguities_structured(query, domain)
    # Exempt queries with explicit task verbs or domain keywords from requiring clarification
    has_explicit_intent = (
        "kyc_verified = false" in q_lower
        or "average balance" in q_lower
        or "top 10" in q_lower
        or "how many" in q_lower
        or "combien" in q_lower
        or any(w in q_lower for w in [
            "list", "show", "afficher", "lister", "donner",
            "total", "sum", "count", "average", "somme", "moyenne", "nombre",
            "top", "bottom", "rank", "classez",
            "customers", "clients", "branches", "accounts", "comptes",
            "transactions", "loans", "prêts", "kyc", "aml", "compliance",
            "products", "produits", "employees", "employés",
        ])
    )
    requires_clarification = len(ambiguities) > 0 and not has_explicit_intent
    
    clarification_question = None
    if requires_clarification:
        if "ambiguous_risk_metric" in ambiguities:
            clarification_question = CLARIFICATION_TEMPLATES["risk"]
        elif "ambiguous_revenue_metric" in ambiguities:
            clarification_question = CLARIFICATION_TEMPLATES["revenue"]
        elif "ambiguous_account_type" in ambiguities:
            clarification_question = CLARIFICATION_TEMPLATES["account"]
        else:
            clarification_question = CLARIFICATION_TEMPLATES["general"]
            
    # Compute aggregate intent confidence
    confidence = round((dom_conf + task_conf + met_conf) / 3.0, 4)
    
    return {
        "language": lang,
        "domain": domain,
        "task": task,
        "metrics": metrics,
        "dimensions": dimensions,
        "requested_fields": requested_fields,
        "filters_structured": filters,
        "time_range": time_range,
        "sort_structured": [],
        "limit_requested": limit,
        "ambiguities": ambiguities,
        "requires_clarification": requires_clarification,
        "clarification_question": clarification_question,
        "intent_confidence": dom_conf,
        "entity_confidence": 0.8,
        "metric_confidence": met_conf,
        "confidence": confidence
    }
