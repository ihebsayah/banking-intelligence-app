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
    "bénéficiaire", "bénéficiaires", "tous", "chaque", "par", "selon", "mouvement", "mouvements",
    "revenu", "revenus", "commissions", "frais", "bénéfice", "bénéfices", "pnb",
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
    "accounts.status": ["account status", "statut de compte", "statut des comptes"],
    "accounts.currency": ["currency", "devise"],
    "customers.kyc_verified": ["kyc status", "statut kyc", "kyc_verified", "vérifié kyc"],
    "customers.risk_score": ["risk level", "niveau de risque", "risk_score"],
    "loan_contracts.loan_type": ["loan type", "type de prêt", "loan_type"],
    "loan_contracts.status": ["loan status", "statut prêt", "loan_status"],
    "loan_contracts.disbursement_date": ["disbursement date", "mois de décaissement", "disbursement_date"],
    "transactions.transaction_type": ["transaction type", "type de transaction", "transaction_type"],
    "transactions.status": ["transaction status", "statut de transaction"],
    "transactions.transaction_date": ["transaction date", "date de transaction", "transaction_date"],
    "risk_flags.severity": ["severity", "sévérité"],
    "fee_income.fee_type": ["fee type", "type de frais", "fee_type"],
    "non_performing_loans.classification": ["classification"],
    "suspicious_activity_reports.status": ["sar status", "statut sar"],
    "kyc_cases.risk_level": ["risk level kyc", "niveau de risque kyc"],
}

# Authoritative KPIs (metric_id -> Synonyms)
# Exclude bare keywords to separate entities from metrics
GLOSSARY_KPIS = {
    "npl_ratio": ["npl ratio", "taux de créances classées", "non-performing loan ratio", "taux de sinistralité", "taux de défaut", "npl rate", "taux de créances douteuses", "ratio de prêts improductifs"],
    "roe": ["roe", "return on equity", "rentabilité des fonds propres", "rentabilité des capitaux propres"],
    "roa": ["roa", "return on assets", "rentabilité des actifs"],
    "kyc_compliance_rate": ["kyc compliance rate", "taux de conformité kyc", "taux de conformité"],
    "aml_alert_rate": ["aml alert rate", "taux d'alertes aml", "taux alertes aml"],
    "loan_to_deposit": ["loan to deposit", "ldr", "ratio crédits / dépôts", "ratio crédits/dépôts", "loan to deposit ratio"],
    "pnb": ["pnb", "produit net bancaire", "net banking income", "nbi"],
    "net_income": ["net income", "revenu net", "résultat net", "resultat net", "net profits"],
    "cost_income_ratio": ["cost-income ratio", "cost to income ratio", "cost income ratio", "ratio de coût sur revenu", "ratio coût / revenu", "ratio coûts / produits", "ratio couts / produits"],
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
    "kyc_verified": ["kyc verified", "kyc status", "statut kyc", "kyc_verified"],
    "status": ["status", "statut", "état", "active status"],
    "balance": ["balance", "solde", "avoirs"],
    "amount": ["amount", "montant"],
    "transaction_date": ["date", "transaction date", "date de transaction"],
    "branch_id": ["branch id", "id agence", "branch_id"],
    "branch_name": ["branch name", "nom de l'agence", "branch_name"],
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
    q_lower = re.sub(r"[-\s]+", " ", query.lower())
    detected = []
    reasons = []
    
    has_trigger = any(t in q_lower for t in ANALYTICAL_TRIGGERS)
    self_triggering = {"roe", "roa", "pnb", "net_income", "ldr", "loan_to_deposit"}
    
    for metric_id, synonyms in GLOSSARY_KPIS.items():
        needs_trigger = metric_id not in self_triggering
        
        for syn in synonyms:
            syn_n = re.sub(r"[-\s]+", " ", syn)
            if syn_n in q_lower:
                # Synonym itself might have the trigger (e.g., "npl ratio" contains "ratio")
                syn_has_trigger = any(t in syn_n for t in ANALYTICAL_TRIGGERS)
                if not needs_trigger or syn_has_trigger or has_trigger:
                    detected.append(metric_id)
                    reasons.append(f"Synonym match: '{syn}' -> '{metric_id}'")
                    break
                
    confidence = 0.95 if detected else 0.5
    return list(set(detected)), reasons, confidence

def extract_task(query: str, detected_metrics: List[str] = []) -> tuple:
    """Detect analytical task, separating listing requests with 'by/par' grouping from aggregations."""
    q_lower = query.lower()
    
    # Check for explicit ranking keywords first
    if any(re.search(r"\b" + w + r"\b", q_lower) for w in ["top", "bottom", "best", "worst", "highest", "lowest"]) or any(w in q_lower for w in ["plus grand", "plus petit", "meilleur", "pire"]):
        return "ranking", 0.95
        
    has_listing_verb = any(w in q_lower for w in ["list", "show", "details", "retrieve", "find", "get", "history", "alerts", "report history", "lister", "afficher", "détails", "trouver", "sélectionner", "donner"])
    has_agg_verb = any(w in q_lower for w in ["total", "totaux", "totale", "sum", "average", "avg", "count", "somme", "moyen", "moyenne", "nombre", "totaliser", "calculer", "montant total", "compter", "quantité", "how many", "combien", "rate", "ratio", "taux", "pnb", "roe", "roa", "ldr", "volume", "deposit", "deposits", "dépôt", "dépôts", "commission", "commissions", "répartition", "évolution", "distribution"])
    has_grouping = any(w in q_lower for w in ["by ", "par ", "selon ", "per "])
    has_metric = len(detected_metrics) > 0
    
    if has_grouping:
        if has_listing_verb and not (has_metric or has_agg_verb):
            return "detail_listing", 0.7
        return "aggregation", 0.95
            
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
    """Detect dimensions for GROUP BY using token-boundary matching.

    Substring matching lets 'branch' leak into 'branches'/'branche', and misses
    "par statut"/"par mois" forms. Dimensions are matched word-boundary and
    generic subjects collapse to canonical placeholders (STATUS / TIME_MONTH /
    TIME_DAY / RISK_LEVEL) that the planner resolves against selected tables.
    When a geo dimension (state/city/region) is present, a pure 'branches.name'
    split is suppressed: location grouping wins over branch-name grouping.
    """
    q_lower = query.lower()
    detected: List[str] = []

    for canonical, synonyms in DIMENSION_KEYWORDS.items():
        for syn in synonyms:
            if re.search(r"\b" + re.escape(syn) + r"(?:es|s)?\b", q_lower):
                detected.append(canonical)
                break

    # Generic subject placeholders (table/column resolved by the planner)
    if re.search(r"\bstatus\b|\bstatut\b|\bétat\b", q_lower):
        detected.append("STATUS")
    if re.search(r"\bmonth\b|\bmonthly\b|\bmois\b|\bmensuel|\bmensuelle\b", q_lower):
        if "TIME_MONTH" not in detected:
            detected.append("TIME_MONTH")
    if re.search(r"\bday\b|\bdaily\b|\bjour\b|\bpar jour\b", q_lower):
        if "TIME_DAY" not in detected:
            detected.append("TIME_DAY")
    if re.search(r"\bniveau de risque\b|\brisk level\b", q_lower):
        detected.append("RISK_LEVEL")
    if re.search(r"\btype de\b|\bpar type\b|\btype\b|\btypes?\b", q_lower):
        if "TYPE" not in detected:
            detected.append("TYPE")

    # Scalar-total counts ask for one number, not a per-branch split
    # ("How many branches exist in total?"): a bare branch noun only groups
    # when the query anchors a grouping/ranking connector.
    if set(detected) == {"branches.name"} and re.search(
        r"\bhow\s+many\b|\bcombien\b|\bnumber\s+of\b|\bnombre\s+d\w*\b"
        r"|\bin\s+total\b|\bau\s+total\b|\ben\s+tout\b|\btotal(?:s)?\b", q_lower
    ) and not re.search(
        r"\bby\b|\bper\b|\bpar\b|\bselon\b|r[ée]partition|distribution"
        r"|le\s+plus\s+de\b|avec\s+le\s+plus\b|\btop\b|\bplus\s+de\s+\d+\b"
        r"|\beach\b|\bchaque\b", q_lower
    ):
        detected.remove("branches.name")

    # Location grouping beats a bare branch-name grouping: keep branches.name
    # unless a distinct geographic split (state/city/region) is also requested.
    if "branches.name" in detected and {
        "branches.state", "branches.city", "branches.region_id",
    } & set(detected):
        detected.remove("branches.name")

    # Risk-level grouping beats a customer-level risk-score split
    if "RISK_LEVEL" in detected and "customers.risk_score" in detected:
        detected.remove("customers.risk_score")

    return list(dict.fromkeys(detected))

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

# Words that end a branch-name phrase (connectors between branch scope and rest of query)
_BRANCH_CONNECTOR_WORDS = (
    "par by pour with in at for de en dans sur selon of across from under to "
    "and et or ou around within the"
).split()


def _capture_branch_name(text: str) -> str:
    """Capture a short branch-name token run, stopping at connector words."""
    tokens = []
    for tok in re.findall(r"[A-Za-zÀ-ÿ0-9'.-]+", text):
        if tok.lower() in _BRANCH_CONNECTOR_WORDS:
            break
        tokens.append(tok)
        if len(tokens) >= 4:
            break
    return " ".join(tokens)


def extract_time_range(query: str) -> Dict[str, Any]:
    """Extract relative time ranges."""
    q_lower = query.lower()
    
    # English matches
    m_days_en = re.search(r"\blast\s+(\d+)\s+days?\b", q_lower)
    m_months_en = re.search(r"\blast\s+(\d+)\s+months?\b", q_lower)
    m_y_en = re.search(r"\blast\s+year\b", q_lower)
    m_q_en = re.search(r"\blast\s+quarter\b", q_lower)
    m_ytd_en = re.search(r"\bytd\b|\byear\s+to\s+date\b", q_lower)
    m_this_year_en = re.search(r"\bthis\s+year\b", q_lower)
    m_this_year_fr = re.search(r"\bcette\s+ann[ée]e\b|\bcet\s+exercice\b", q_lower)
    
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
        
    if m_y_en or m_y_fr or m_year_word_fr or m_this_year_en or m_this_year_fr:
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
    # 'le plus de / the most' → fixed business top-5 (golden-frozen).
    if re.search(r"\ble\s+plus\s+de\b|\bthe\s+most\b|\bavec\s+le\s+plus\b", q_lower):
        return 5
    # 'latest / last period / dernière période' → most recent reporting period.
    if re.search(r"\blatest\b|\blast\s+period\b|\bderni[eè]re\s+p[eé]riode\b|\bdernier\s+(?:pnb|r[eé]sultat)\b", q_lower):
        return 1
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

# ────────────────────────────────────────────────────────────────────────────
# Constraint extraction (Step 17). Deterministic, no LLM, no value invention.
# Every filter value derives from explicit query text or from the documented
# golden-frozen business thresholds below. An adjective ("active", "pending",
# "dormant") NEVER becomes a filter unless its owning business object is named
# in the query — ambiguous filter sources resolve by business context, never by
# a global schema guess.
#
# Business-context anchors that OWN a status column.
#   ponytail: pattern-based extraction; if new product/domain filters appear,
#   extend these context anchors rather than adding per-query special cases.
_ACCOUNT_NOUN = r"accounts?|comptes?(?:\s+(?:courants?|épargne))?"
_LOAN_NOUN = r"loans?|prêts?|crédits?|credits?|financing"
_TRANSACTION_NOUN = r"transactions?|mouvements?|paiements?"  # transaction status/type context
_AML_ALERT_NOUN = r"\baml\b"  # always paired with "alert" word check


def _context_adj_filter(query: str, noun_re: str, value_map: Dict[str, str]) -> Optional[str]:
    """Map a bare status/type adjective to its canonical value, but only when
    an owning noun appears within a short window (deterministic bilingual).
    Returns the canonical value or None."""
    q = query.lower()
    for raw, canon in value_map.items():
        pat = re.compile(
            r"(?:" + noun_re + r").{0,40}?\b" + re.escape(raw) + r"\b"
            r"|\b" + re.escape(raw) + r".{0,24}?(?:" + noun_re + r")",
            re.IGNORECASE,
        )
        if pat.search(q):
            return canon
    return None


def _extract_risk_explicit(query: str) -> Optional[Dict[str, Any]]:
    """Numeric risk-score comparison: EN/FR operator phrases + decimal numbers
    (both comma and dot decimals). Numeric threshold must come from the query."""
    q = query.lower()
    # Longest/boundary-safe operator phrases, longest first per family.
    ops = (
        (">=", re.compile(r">=|au\s+moins|at\s+least", re.I)),
        ("<=", re.compile(r"<=|au\s+plus|at\s+most", re.I)),
        (">", re.compile(r">|above|greater\s+than|more\s+than|plus\s+que|plus\s+de|sup[ée]rieur\w*|au[- ]?dessus", re.I)),
        ("<", re.compile(r"<|below|under|less\s+than|moins\s+de|inf[ée]rieur\w*", re.I)),
        ("=", re.compile(r"==?|equal\s+to|[ée]gal\w*\s+[aà]|egal\w*\s+a", re.I)),
    )
    risk_phrase = re.compile(
        r"\b(?:risk\s*score|risk_score|risk|score\s+de\s+risque|note\s+de\s+risque)\b", re.I)
    win = 36
    for op, pat in ops:
        for m in pat.finditer(q):
            op_end = m.end()
            tail = q[op_end: op_end + 18]
            num = re.match(r"[^.\d]*(\d[\d.,]*)\b", tail)
            if not num:
                continue
            value = float(num.group(1).replace(",", "."))
            head = q[max(0, op_end - win): op_end]
            if risk_phrase.search(head):
                return {"column": "customers.risk_score", "operator": op, "value": value}
    return None


# Golden-frozen business risk bands (documented thresholds). A categorical
# band names only map here; the threshold is NOT invented per query.
_RISK_BANDS = (
    (re.compile(r"haut\s+risque|high[- ]?risk", re.I), ">", 0.7),
    (re.compile(r"risque\s+[ée]lev[ée]|elevated\s+risk", re.I), ">", 0.5),
)


def _extract_risk_filter(query: str) -> Optional[Dict[str, Any]]:
    explicit = _extract_risk_explicit(query)
    if explicit:
        return explicit
    q = query.lower()
    for pat, op, threshold in _RISK_BANDS:
        if pat.search(q):
            return {"column": "customers.risk_score", "operator": op, "value": threshold}
    return None


def _extract_segment_filter(query: str) -> Optional[Dict[str, Any]]:
    """Segment code must be present verbatim (no fabrication)."""
    q = query
    m = re.search(r"\bsegment\w*\s+(?:de\s+)?(?P<v>[A-Z][A-Z0-9_]{1,})\b", q) or \
        re.search(r"\b(?P<v>[A-Z][A-Z0-9_]{1,})\s+segment\b", q)
    if m:
        return {"column": "customers.segment", "operator": "=", "value": m.group("v").upper()}
    return None


def _extract_boolean_kyc(query: str) -> Optional[Dict[str, Any]]:
    q = query.lower()
    false_pat = re.compile(r"kyc(?:\s*_?\s*verified)?\s*=\s*false|kyc\s+non\s+(?:v[ée]rifi[ée]|vérifiés)|non\s+v[ée]rifi[ée]s?\s*(?:kyc)?|kyc\s+non\s+verif|not\s+kyc\s+verified", re.I)
    if false_pat.search(q):
        return {"column": "customers.kyc_verified", "operator": "=", "value": False}
    true_pat = re.compile(r"kyc(?:\s*_?\s*verified)|\s*_?\s*=\s*true|kyc\s+est\s+v[ée]rifi[ée]|v[ée]rifi[ée]\s+(?:leur\s+)?kyc|verified\s+their\s+kyc|kyc\s+ok|kyc\s+valid[ée]", re.I)
    if true_pat.search(q):
        return {"column": "customers.kyc_verified", "operator": "=", "value": True}
    return None


def _extract_account_filters(query: str) -> List[Dict[str, Any]]:
    out = []
    st = _context_adj_filter(query, _ACCOUNT_NOUN, {
        "actifs": "active", "actif": "active", "active": "active", "ouvert": "active",
        "dormants": "dormant", "dormant": "dormant",
        "clos": "closed", "closed": "closed",
    })
    if st:
        out.append({"column": "accounts.status", "operator": "=", "value": st})
    at = _context_adj_filter(query, _ACCOUNT_NOUN, {
        "épargne": "savings", "epargne": "savings", "savings": "savings",
        "courant": "current", "courants": "current", "current": "current", "checking": "checking",
    })
    if at:
        out.append({"column": "accounts.account_type", "operator": "=", "value": at})
    return out


def _extract_loan_filters(query: str) -> List[Dict[str, Any]]:
    """Loan status + loan type + days_past_due. 'en retard' maps to
    days_past_due > 0 (loan outcomes live in days_past_due, not status)."""
    out = []
    q = query.lower()
    st = _context_adj_filter(query, _LOAN_NOUN, {
        "actifs": "active", "actif": "active", "active": "active",
        "clos": "closed", "closed": "closed", "clotur": "closed", "ferm": "closed",
    })
    if st:
        out.append({"column": "loan_contracts.status", "operator": "=", "value": st})

    loan_type_pat = re.compile(
        r"\b(?P<t>auto|immo|immobilier|pro|conso|personal|mortgage|hypoth[ée]caire)\b.{0,28}?(?:" + _LOAN_NOUN + r")"
        r"|\b(?:" + _LOAN_NOUN + r").{0,28}?\b(?P<u>auto|immo|conso|pro)\b",
        re.I,
    )
    m = loan_type_pat.search(q)
    if m:
        raw = (m.group("t") or m.group("u")).lower()
        canon = {"immo": "immo", "immobilier": "immo", "mortgage": "immo",
                 "hypoth[ée]caire": "immo", "auto": "auto", "pro": "pro",
                 "personal": "conso", "conso": "conso"}.get(raw, raw)
        out.append({"column": "loan_contracts.loan_type", "operator": "=", "value": canon})

    due = _extract_days_past_due(query)
    if due:
        out.append(due)
    return out


def _extract_days_past_due(query: str) -> Optional[Dict[str, Any]]:
    """days_past_due > N. The numeric N always comes from the query; a bare
    overdue phrase (EN/FR) means > 0."""
    q = query.lower()
    if not re.search(_LOAN_NOUN, q):
        return None
    m_num = re.search(
        r"retard\s+(?:de\s+)?plus\s+de\s+(\d+)\s+jours?"
        r"|(\d+)\s+jours?\s+de\s+retard"
        r"|(\d+)\s+days?\s+(?:overdue|past\s+due|delinquen\w*)"
        r"|overdue\s+by\s+(\d+)\s+days?"
        r"|more\s+than\s+(\d+)\s+days?\s+overdue",
        q,
    )
    if m_num:
        for grp in m_num.groups():
            if grp:
                return {"column": "loan_contracts.days_past_due", "operator": ">", "value": int(grp)}
    if re.search(r"\ben\s+retard\b|overdue|past\s+due|delinquen\w+|douteu(?:x|se)|impay[ée]s?", q):
        return {"column": "loan_contracts.days_past_due", "operator": ">", "value": 0}
    return None


def _extract_transaction_filters(query: str) -> List[Dict[str, Any]]:
    out = []
    q = query.lower()

    def _txn_context(q: str) -> bool:
        return bool(re.search(_TRANSACTION_NOUN, q))

    if _txn_context(q):
        completed = _context_adj_filter(query, _TRANSACTION_NOUN, {
            "completed": "complété", "compl[ée]t[ée]": "complété", "r[ée]ussi": "complété",
            "failed": "failed", "[ée]chou[ée]": "failed",
            "pending": "pending", "en attente": "pending",
        })
        if completed:
            out.append({"column": "transactions.status", "operator": "=", "value": completed})

        ttype_pat = re.compile(
            r"(?:transfer|transfert|virement\w*|wire|paiement\w*|payment\w*|deposit|d[ée]p[ôo]t\w*|retrait\w*|withdrawal\w*|purchase|achat\w*)\b",
            re.I,
        )
        if ttype_pat.search(q):
            m = ttype_pat.search(q)
            raw = m.group(0).lower()
            mapping = {
                "transfer": "transfer", "transfert": "transfer", "virement": "transfer",
                "virements": "transfer", "wire": "transfer",
                "deposit": "deposit", "d[ée]p[ôo]t": "deposit", "dépôt": "deposit",
                "withdrawal": "withdrawal", "withdrawals": "withdrawal", "retrait": "withdrawal",
                "retraits": "withdrawal",
                "payment": "payment", "payments": "payment", "paiement": "payment", "paiements": "payment",
                "purchase": "purchase", "achat": "purchase",
            }
            out.append({"column": "transactions.transaction_type", "operator": "=",
                        "value": mapping.get(raw, raw)})
    return out


def _extract_kyc_case_filter(query: str) -> Optional[Dict[str, Any]]:
    q = query.lower()
    if re.search(r"kyc\s+cases?", q) or re.search(r"en\s+attente\s+kyc|kyc\s+en\s+attente|attente\s+kyc|dossiers?\s+kyc", q):
        if re.search(r"\bpending\b|en\s+attente|en_attente|\battend\b|\brejet|rejected|approuv|approved", q):
            if re.search(r"\bpending\b|en\s+attente|en_attente|\battend\b", q):
                return {"column": "kyc_cases.status", "operator": "=", "value": "pending"}
            if re.search(r"approuv|approved", q):
                return {"column": "kyc_cases.status", "operator": "=", "value": "approved"}
            return {"column": "kyc_cases.status", "operator": "=", "value": "rejected"}
    return None


def _extract_aml_filters(query: str) -> List[Dict[str, Any]]:
    out = []
    q = query.lower()
    if not (re.search(r"\baml\b", q) and re.search(r"alert", q)):
        return out
    if re.search(r"high[- ]?severity|high\s+severity|s[ée]v[ée]rit[ée]\s+[ée]lev[ée]|haute\s+s[ée]v[ée]rit[ée]", q):
        out.append({"column": "aml_alerts.severity", "operator": "=", "value": "high"})
    if re.search(r"\bopen\b|ouvert\w*", q):
        out.append({"column": "aml_alerts.status", "operator": "=", "value": "open"})
    return out


def _extract_risk_flag_filter(query: str) -> Optional[Dict[str, Any]]:
    q = query.lower()
    if re.search(r"flags?\s+de\s+risque|risk\s+flags?", q) and \
       re.search(r"non\s+r[ée]solu\w*|non\s+resolu\w*|unresolved", q):
        return {"column": "risk_flags.resolved_at", "operator": "IS NULL", "value": None}
    return None


def extract_branch_filter(query: str) -> Optional[Dict[str, Any]]:
    """Extract an explicit branch-scope filter (branches.name).

    Recognises branch codes (BR_016), English 'in|at|for|within <name> Branch',
    French '<prep> l'agence <name>' and 'dans la branche / (dans) les branches
    de <name>'. Named branches are canonicalised to '<Name> Branch' unless the
    captured name is already a branch code.
    """
    m_code = re.search(r"\b(BR[_-]?\d+)\b", query, re.IGNORECASE)
    if m_code:
        return {"column": "branches.name", "operator": "=", "value": m_code.group(1).upper()}

    m_en = re.search(r"\b(?:in|at|for|within)\s+(.+?)\s+[Bb]ranch\b", query)
    if m_en:
        name = _capture_branch_name(m_en.group(1))
        if name:
            value = f"{name} Branch" if not name.upper().startswith("BR_") else name
            return {"column": "branches.name", "operator": "=", "value": value}

    # French: à l'agence <name> (kept plain, legacy contract); dans la branche
    # <name> / (dans) les branches de <name> canonicalise to '<Name> Branch'.
    m_fr = re.search(
        r"\b(?:à|a|dans|de|en)\s+l['’]?\s*agence\s+(.+)"
        r"|\bdans\s+la\s+branche\w*\s+([A-Za-zÀ-ÿ]+)"
        r"|\bdans\s+(?:les|des)\s+branches\w*\s+(?:de\s+)?([A-Za-zÀ-ÿ]+)",
        query, re.IGNORECASE,
    )
    if m_fr:
        name = None
        needs_suffix = False
        if m_fr.group(1):
            name = _capture_branch_name(m_fr.group(1))
        elif m_fr.group(2):
            name = _capture_branch_name(m_fr.group(2))
            needs_suffix = True
        elif m_fr.group(3):
            name = _capture_branch_name(m_fr.group(3))
            needs_suffix = True
        if name:
            value = f"{name} Branch" if (needs_suffix and not name.upper().startswith("BR_")) else name
            return {"column": "branches.name", "operator": "=", "value": value}
    return None


def _extract_filters(query: str) -> List[Dict[str, Any]]:
    """Deterministic, context-gated constraint extraction. Constraints that are
    detected but cannot be represented are surfaced to the caller via the
    'detected_unsupported' list so the pipeline FAILS CLOSED instead of running
    a broader query. (No such case currently exists; kept as a registry.)"""
    filters = []

    kyc = _extract_boolean_kyc(query)
    if kyc:
        filters.append(kyc)

    risk = _extract_risk_filter(query)
    if risk:
        filters.append(risk)

    seg = _extract_segment_filter(query)
    if seg:
        filters.append(seg)

    filters.extend(_extract_account_filters(query))
    filters.extend(_extract_loan_filters(query))
    filters.extend(_extract_transaction_filters(query))

    kyc_case = _extract_kyc_case_filter(query)
    if kyc_case:
        filters.append(kyc_case)

    filters.extend(_extract_aml_filters(query))

    flag = _extract_risk_flag_filter(query)
    if flag:
        filters.append(flag)

    branch = extract_branch_filter(query)
    if branch:
        filters.append(branch)

    return filters


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

    # Deterministic, context-gated constraint extraction (Step 17).
    filters = _extract_filters(query)
    branch_filter = extract_branch_filter(query)
    q_lower = query.lower()

    ambiguities = detect_ambiguities_structured(query, domain)
    # Exempt queries with explicit task verbs, domain keywords, or explicit branch
    # scope from requiring clarification
    has_explicit_intent = (
        branch_filter is not None
        or "kyc_verified = false" in q_lower
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
            
    sort_structured = []
    if task == "ranking" or limit is not None or any(w in q_lower for w in ["top", "bottom", "best", "worst", "highest", "lowest", "plus grand", "plus petit", "largest", "biggest", "latest"]):
        direction = "DESC"
        if any(w in q_lower for w in ["bottom", "worst", "lowest", "plus petit", "moins", "smallest", "plus faible"]):
            direction = "ASC"

        sort_col = ""
        if "risk_score" in q_lower or "score de risque" in q_lower:
            sort_col = "customers.risk_score"
        elif "balance" in q_lower or "solde" in q_lower or "deposits" in q_lower or "dépôts" in q_lower:
            sort_col = "accounts.balance"
        elif "amount" in q_lower or "montant" in q_lower or (re.search(r"largest|biggest", q_lower) and re.search(r"transaction|transfer", q_lower)):
            sort_col = "transactions.amount"
        elif "principal" in q_lower or "capital" in q_lower:
            sort_col = "loan_contracts.principal_amount"
        elif re.search(r"latest|period|période|périod|net income|pnb|revenu net|résultat", q_lower):
            sort_col = "income_statement_snapshots.period"
        elif re.search(r"number\s+of|nombre\s+de|par\s+nombre|le\s+plus\s+de|the\s+most|avec\s+le\s+plus", q_lower):
            sort_col = "count_all"
        elif metrics:
            sort_col = metrics[0]

        if sort_col:
            sort_structured = [{"column": sort_col, "direction": direction}]
            
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
        "sort_structured": sort_structured,
        "limit_requested": limit,
        "ambiguities": ambiguities,
        "requires_clarification": requires_clarification,
        "clarification_question": clarification_question,
        "intent_confidence": dom_conf,
        "entity_confidence": 0.8,
        "metric_confidence": met_conf,
        "confidence": confidence
    }
