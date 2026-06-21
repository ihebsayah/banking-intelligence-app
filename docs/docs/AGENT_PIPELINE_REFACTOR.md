# AGENT PIPELINE REFACTOR DESIGN
**Phase 6 — NL-to-SQL Agent Accuracy Upgrade**
*Design for each of the 6 agents in the pipeline*

---

## PIPELINE OVERVIEW

```
User NL Query
     │
     ▼
┌──────────────────────────────────────────────────────┐
│  INTENT AGENT (port 8002)                            │
│  Query → intent_category + confidence + banking_kpis │
└─────────────────────┬────────────────────────────────┘
                      │ IntentResponse
                      ▼
┌──────────────────────────────────────────────────────┐
│  SCHEMA AGENT (port 8003)                            │
│  intent → semantic table discovery + join paths      │
└─────────────────────┬────────────────────────────────┘
                      │ SchemaResponse (tables + joins)
                      ▼
┌──────────────────────────────────────────────────────┐
│  ENTITY RESOLUTION AGENT (port 8005)                 │
│  NL terms → banking entities + synonym normalization │
└─────────────────────┬────────────────────────────────┘
                      │ EntityResponse (entities + join paths)
                      ▼
┌──────────────────────────────────────────────────────┐
│  COMPLIANCE AGENT (port 8011)                        │
│  Tables + user_role → PII masking + access control   │
└─────────────────────┬────────────────────────────────┘
                      │ ComplianceResponse (allowed/masked)
                      ▼
┌──────────────────────────────────────────────────────┐
│  SQL AGENT (port 8006)                               │
│  Entities + tables + metric formula → SQL query      │
└─────────────────────┬────────────────────────────────┘
                      │ SQLResponse
                      ▼
┌──────────────────────────────────────────────────────┐
│  VALIDATION AGENT (port 8007)                        │
│  SQL → 5-check security + 3-check banking validation │
└─────────────────────┬────────────────────────────────┘
                      │ Signed safe SQL
                      ▼
              Execution Agent (port 8008)
```

---

## AGENT 1: INTENT AGENT — Refactor Spec

### Current State
- 8 intent categories (English only)
- spaCy pattern matching
- No KPI recognition
- No French/Arabic support

### Target State

#### Extended Intent Categories (from 8 to 14)
```python
INTENT_CATEGORIES = {
    # Existing (kept)
    "customer_analysis":    "Analyse clients — segment, KYC, profil",
    "risk_analysis":        "Analyse risques — score, flags, exposition",
    "revenue_analysis":     "Analyse revenus — PNB, commissions, marges",
    "operational_analysis": "Analyse opérationnelle — transactions, volumes",
    "geographic_analysis":  "Analyse géographique — régions, agences",
    "product_analysis":     "Analyse produits — souscriptions, portefeuille",
    "compliance_analysis":  "Analyse conformité — KYC, AML, violations",
    "transaction_analysis": "Analyse transactions — flux, tendances",
    
    # NEW
    "loan_analysis":        "Analyse crédits — encours, NPL, remboursements",
    "kyc_analysis":         "Analyse KYC — dossiers, expirations, PEP",
    "aml_analysis":         "Analyse AML/LCB — alertes, déclarations, seuils",
    "liquidity_analysis":   "Analyse liquidité — LCR, NSFR, ratio transformation",
    "profitability_analysis": "Analyse rentabilité — ROE, ROA, coefficient exploitation",
    "executive_summary":    "Tableau de bord exécutif — KPIs synthèse",
}
```

#### Banking KPI Recognition (NEW)
```python
# Pattern → intent + metric_id mapping
BANKING_KPI_PATTERNS = {
    # NPL patterns (FR + EN)
    r"(npl|créances classées|créances douteuses|bad loans|sinistres|non[- ]performants?)": 
        ("loan_analysis", "npl_ratio"),
    
    # ROE/ROA
    r"(roe|return on equity|rentabilité des fonds propres|rendement des capitaux)":
        ("profitability_analysis", "roe"),
    r"(roa|return on assets|rentabilité des actifs)":
        ("profitability_analysis", "roa"),
    
    # LCR/NSFR
    r"(lcr|liquidity coverage|couverture des liquidités)":
        ("liquidity_analysis", "lcr"),
    r"(nsfr|net stable funding|financement stable)":
        ("liquidity_analysis", "nsfr"),
    
    # KYC
    r"(kyc|know your customer|connaissance client|vérification d'identité|diligence)":
        ("kyc_analysis", None),
    
    # AML
    r"(aml|lcb|blanchiment|money laundering|alerte aml|suspicious|soupçon)":
        ("aml_analysis", None),
    
    # Provisions/Provisions
    r"(provision|provisionnement|taux de couverture|coverage ratio)":
        ("loan_analysis", "provision_coverage"),
    
    # Cost-to-income
    r"(coefficient d.exploitation|cost.to.income|cir|charges.revenu)":
        ("profitability_analysis", "cost_income_ratio"),
    
    # LDR
    r"(ldr|loan.to.deposit|crédits.dépôts|taux de transformation)":
        ("liquidity_analysis", "loan_to_deposit"),
}
```

#### French Keyword Patterns (NEW)
```python
FRENCH_INTENT_PATTERNS = {
    "customer_analysis": [
        "clients", "client", "clientèle", "tiers", "segment",
        "particuliers", "entreprises", "PME"
    ],
    "loan_analysis": [
        "crédit", "prêt", "crédits", "prêts", "emprunt",
        "mensualité", "échéance", "remboursement", "encours",
        "immobilier", "consommation", "automobile"
    ],
    "aml_analysis": [
        "alerte", "alertes", "blanchiment", "soupçon", "LCB",
        "déclaration", "CTAF", "transaction suspecte"
    ],
    "kyc_analysis": [
        "KYC", "vérification", "dossier", "identification",
        "PEP", "diligence", "conformité client"
    ],
}
```

### New Method: `recognize_with_glossary()`
```python
async def recognize_with_glossary(self, query: str) -> IntentResponse:
    # 1. Standard pattern matching (existing)
    base_result = await self.recognize(query)
    
    # 2. KPI pattern scan (new)
    kpi_matches = self._scan_kpi_patterns(query)
    
    # 3. Business glossary lookup (new — async DB call)
    glossary_terms = await self._lookup_glossary(query)
    
    # 4. Merge: KPI match overrides base if higher confidence
    final_intent = self._merge_intents(base_result, kpi_matches, glossary_terms)
    
    return IntentResponse(
        intent=final_intent.intent,
        confidence=final_intent.confidence,
        detected_kpis=kpi_matches,         # NEW field
        resolved_terms=glossary_terms,       # NEW field
        detected_entities=final_intent.entities,
    )
```

---

## AGENT 2: SCHEMA AGENT — Refactor Spec

### Current State
- Hardcoded `DOMAIN_TO_TABLES` dict (8 entries)
- Static 1-hop join graph (16 edges)
- No vector similarity usage
- No business glossary integration

### Target State

#### Dynamic Table Discovery via Semantic Layer
```python
class SchemaMatcher:
    
    async def match_tables_semantic(
        self, 
        intent: str, 
        resolved_terms: List[str],
        metric_ids: List[str]
    ) -> List[str]:
        """
        1. Start with domain tables from table_metadata
        2. Add tables from metric_registry.source_tables for detected KPIs
        3. Add tables implied by glossary terms
        4. Rank by relevance score
        5. Return top N tables
        """
        tables: Set[str] = set()
        
        # Step 1: Domain tables
        domain_tables = await self.db.fetch("""
            SELECT table_name FROM table_metadata 
            WHERE domain = $1 OR domain IN (
                SELECT DISTINCT domain FROM column_metadata 
                WHERE $2 ILIKE ANY(synonyms)
            )
        """, intent_to_domain(intent), resolved_terms)
        tables.update(r['table_name'] for r in domain_tables)
        
        # Step 2: Metric source tables
        for metric_id in metric_ids:
            metric = await self.db.fetchrow("""
                SELECT source_tables FROM metric_registry WHERE metric_id = $1
            """, metric_id)
            if metric:
                tables.update(metric['source_tables'])
        
        # Step 3: Glossary-implied tables
        for term in resolved_terms:
            glossary = await self.db.fetchrow("""
                SELECT source_tables FROM business_glossary
                WHERE term = $1 OR $1 = ANY(synonyms)
            """, term)
            if glossary:
                tables.update(glossary['source_tables'])
        
        return sorted(tables)
    
    async def get_join_paths_from_registry(
        self,
        tables: List[str],
        primary_table: str
    ) -> List[JoinPath]:
        """
        Never guess joins. Always read from join_registry.
        BFS traversal from primary_table through join_registry.
        """
        visited = {primary_table}
        paths = []
        queue = [primary_table]
        
        while queue:
            current = queue.pop(0)
            # Find all join paths FROM current table TO any table in our list
            edges = await self.db.fetch("""
                SELECT source_table, source_column, target_table, target_column,
                       relationship_type, join_type
                FROM join_registry
                WHERE (source_table = $1 AND target_table = ANY($2))
                   OR (target_table = $1 AND source_table = ANY($2))
                ORDER BY confidence DESC
            """, current, list(set(tables) - visited))
            
            for edge in edges:
                to_table = (edge['target_table'] 
                           if edge['source_table'] == current 
                           else edge['source_table'])
                if to_table not in visited:
                    visited.add(to_table)
                    queue.append(to_table)
                    paths.append(JoinPath(
                        from_table=current,
                        to_table=to_table,
                        join_key=edge['source_column'],
                        join_type=edge['join_type'],
                        condition=f"{current}.{edge['source_column']} = {to_table}.{edge['target_column']}"
                    ))
        
        return paths
```

#### Backward Compatibility
- Existing hardcoded `INTENT_TO_DOMAINS` and `JOIN_GRAPH` kept as **fallback**
- Dynamic discovery tried first; fallback if DB unavailable

---

## AGENT 3: ENTITY RESOLUTION AGENT — Refactor Spec

### Current State
- 8 entity types (hardcoded Python dicts)
- No synonym resolution
- References non-existent `loans` and `employees` tables
- 1-hop joins only

### Target State

#### Banking Terminology Normalization
```python
class EntityResolver:
    
    async def resolve_with_glossary(self, request: EntityResolutionRequest) -> EntityResolutionResponse:
        # Step 1: Normalize entities via business_glossary
        normalized_entities = []
        for entity in request.entities:
            norm = await self._normalize_entity(entity)
            normalized_entities.append(norm)
        
        # Step 2: Standard resolution (existing logic)
        response = self.resolve(request._replace(entities=normalized_entities))
        
        return response
    
    async def _normalize_entity(self, term: str) -> str:
        """
        Examples:
            "bad loans" → "non_performing_loans"
            "créances douteuses" → "non_performing_loans"  
            "dépôts" → "accounts" (with filter account_type IN ('savings','checking'))
            "agence" → "branches"
            "chargé de clientèle" → "employees"
        """
        result = await self.db.fetchrow("""
            SELECT term, source_tables[1] as primary_table
            FROM business_glossary
            WHERE LOWER($1) = LOWER(term)
               OR LOWER($1) = ANY(SELECT LOWER(s) FROM unnest(synonyms) s)
            LIMIT 1
        """, term.lower())
        
        return result['primary_table'] if result else term
    
    async def _recognize_banking_kpi(self, term: str) -> Optional[dict]:
        """Detect if term is a KPI and return its formula + tables."""
        return await self.db.fetchrow("""
            SELECT metric_id, formula, source_tables
            FROM metric_registry
            WHERE LOWER($1) = LOWER(metric_name_fr)
               OR LOWER($1) = LOWER(metric_name_en)
               OR LOWER($1) = LOWER(metric_id)
        """, term)
```

#### Expanded Entity Types (from 8 to 20+)
```python
ENTITY_TO_PRIMARY_KEY = {
    # Existing (corrected)
    "customer":             "customer_id",
    "account":              "account_id",
    "transaction":          "transaction_id",
    "branch":               "branch_id",
    "product":              "product_id",
    
    # NEW - Loan domain
    "loan":                 "loan_id",
    "loan_contract":        "loan_id",
    "installment":          "installment_id",
    "repayment":            "repayment_id",
    "collateral":           "collateral_id",
    "guarantee":            "guarantee_id",
    "provision":            "provision_id",
    "npl":                  "npl_id",
    
    # NEW - Compliance/KYC
    "kyc_case":             "kyc_case_id",
    "aml_alert":            "alert_id",
    "sar":                  "sar_id",
    "compliance_case":      "case_id",
    
    # NEW - Organization
    "employee":             "employee_id",
    "region":               "region_id",
    "department":           "department_id",
    
    # NEW - Finance
    "ledger_entry":         "entry_id",
}
```

---

## AGENT 4: SQL AGENT — Refactor Spec

### Current State
- Parameterized queries ✅ (keep)
- Column whitelist (broken for branches/risk_flags, fix required)
- No metric registry usage
- No join registry usage
- No banking formula generation

### Target State

#### Fix 1: ALLOWED_COLUMNS Mismatch (Critical Bug Fix)
```python
ALLOWED_COLUMNS = {
    # FIX: branches schema uses 'name', not 'branch_name'
    "branches": [
        "branch_id", "name",         # was: "branch_name"
        "state",                       # keep state for backward compat
        "city", "manager_id",
        "region_id",                   # NEW field
        "created_at",
    ],
    # FIX: risk_flags uses 'id' not 'risk_id', no account_id, no flagged_at
    "risk_flags": [
        "id", "customer_id",          # was: "risk_id"
        "flag_type", "severity",
        "description", "resolved",
        "created_at",
    ],
    # FIX: loans now exist — update from ghost to real
    "loan_contracts": [
        "loan_id", "customer_id", "account_id", "branch_id",
        "loan_type", "principal_amount", "outstanding_balance",
        "interest_rate", "term_months", "installment_amount",
        "disbursement_date", "maturity_date", "status",
        "days_past_due", "created_at",
    ],
    # NEW tables
    "non_performing_loans": [
        "npl_id", "loan_id", "customer_id", "classification",
        "npl_amount", "provision_amount", "classified_at",
    ],
    "aml_alerts": [
        "alert_id", "customer_id", "account_id", "transaction_id",
        "alert_type", "alert_label_fr", "severity", "status",
        "score", "triggered_at", "closed_at",
    ],
    "kyc_cases": [
        "kyc_case_id", "customer_id", "case_type", "status",
        "risk_level", "opened_at", "closed_at", "due_date",
    ],
    # ... 90+ more tables
}
```

#### Feature 2: Metric Registry Integration
```python
class SQLBuilder:
    
    async def build_with_metric(self, request: SQLGenerationRequest) -> SQLGenerationResponse:
        # If a metric_id was detected by intent agent
        if request.detected_metric_id:
            metric = await self.db.fetchrow("""
                SELECT formula, source_tables FROM metric_registry 
                WHERE metric_id = $1
            """, request.detected_metric_id)
            
            if metric:
                # Use the pre-defined formula instead of generating one
                return self._build_metric_query(
                    metric_formula=metric['formula'],
                    source_tables=metric['source_tables'],
                    additional_filters=request.filters,
                    group_by=request.group_by,
                    limit=request.limit,
                )
        
        # Fallback: standard build
        return self.build(request)
    
    def _build_metric_query(self, metric_formula, source_tables, ...) -> SQLGenerationResponse:
        """
        Generate SQL directly from metric formula.
        Example input: 
            formula = "SUM(CASE WHEN days_past_due > 90 THEN outstanding_balance ELSE 0 END) / SUM(outstanding_balance) * 100"
            source_tables = ["loan_contracts"]
        Output:
            SELECT SUM(CASE WHEN days_past_due > 90 THEN outstanding_balance ELSE 0 END) 
                   / SUM(outstanding_balance) * 100 AS npl_ratio
            FROM loan_contracts
            WHERE status = 'actif'
            LIMIT 1
        """
```

#### Feature 3: Join Registry Integration
```python
    def _build_joins_from_registry(self, join_paths: List[JoinPath]) -> str:
        """
        EXISTING: builds joins from EntityResolver output
        ENHANCEMENT: validate each join against join_registry before using
        """
        validated_paths = []
        for jp in join_paths:
            # Check join_registry for this exact pair
            registered = join_registry_cache.get((jp.from_table, jp.to_table))
            if registered:
                # Use registry-confirmed join
                validated_paths.append(jp._replace(
                    join_key=registered['source_column'],
                    condition=f"{jp.from_table}.{registered['source_column']} = {jp.to_table}.{registered['target_column']}"
                ))
            else:
                # Log warning but proceed (backward compat)
                logger.warning("Join not in registry: %s → %s", jp.from_table, jp.to_table)
                validated_paths.append(jp)
        
        return self._build_joins(validated_paths)
```

---

## AGENT 5: VALIDATION AGENT — Refactor Spec

### Current State
- 5 security checks ✅ (keep all)
- No banking rule validation
- No join correctness validation
- No table existence validation

### Target State

#### Add 3 Banking-Specific Checks (Checks 6-8)

**Check 6: Table Existence Validation**
```python
async def _check_table_existence(self, sql: str) -> Tuple[bool, List[str]]:
    """Extract table names from SQL and verify they exist in DB."""
    # Parse table names from FROM and JOIN clauses
    table_pattern = re.compile(
        r'\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE
    )
    tables_in_query = set(table_pattern.findall(sql))
    
    # Check against schema
    existing_tables = await self.db.fetch("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND table_name = ANY($1)
    """, list(tables_in_query))
    
    existing_set = {r['table_name'] for r in existing_tables}
    missing = tables_in_query - existing_set
    
    if missing:
        return False, [f"Tables do not exist: {', '.join(missing)}"]
    return True, []
```

**Check 7: Join Correctness Validation**
```python
async def _check_join_validity(self, sql: str) -> Tuple[bool, List[str]]:
    """Extract JOIN conditions and verify foreign keys exist in join_registry."""
    join_pattern = re.compile(
        r'(?:LEFT|INNER|RIGHT)?\s*JOIN\s+(\w+)\s+ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)',
        re.IGNORECASE
    )
    issues = []
    for match in join_pattern.finditer(sql):
        _, t1, c1, t2, c2 = match.groups()
        
        registered = await self.db.fetchrow("""
            SELECT * FROM join_registry
            WHERE (source_table = $1 AND source_column = $2 
                   AND target_table = $3 AND target_column = $4)
               OR (source_table = $3 AND source_column = $4 
                   AND target_table = $1 AND target_column = $2)
        """, t1, c1, t2, c2)
        
        if not registered:
            issues.append(f"Unregistered join: {t1}.{c1} = {t2}.{c2}")
    
    return len(issues) == 0, issues
```

**Check 8: KPI Formula Validation**
```python
async def _check_kpi_validity(self, sql: str, expected_metric: str = None) -> Tuple[bool, List[str]]:
    """If query should compute a KPI, verify the formula pattern matches metric_registry."""
    if not expected_metric:
        return True, []  # No KPI expected, skip
    
    metric = await self.db.fetchrow("""
        SELECT formula, source_tables FROM metric_registry WHERE metric_id = $1
    """, expected_metric)
    
    if not metric:
        return True, []  # Metric not in registry, skip
    
    # Check that required source tables are present in the query
    sql_upper = sql.upper()
    issues = []
    for table in metric['source_tables']:
        if table.upper() not in sql_upper:
            issues.append(f"KPI '{expected_metric}' requires table '{table}' not found in query")
    
    return len(issues) == 0, issues
```

---

## AGENT 6: COMPLIANCE AGENT — Post-Expansion Safety

### Current State
- Rules hardcoded for 6 tables
- Works correctly for existing tables

### Required Changes

#### PII Column Registry Extension
```python
# Current (hardcoded)
PII_COLUMNS = {"email", "phone", "national_id", "ssn"}

# Target: derive from column_metadata
async def get_pii_columns(self) -> Set[str]:
    """Load PII columns from column_metadata table."""
    result = await self.db.fetch("""
        SELECT table_name || '.' || column_name as full_col
        FROM column_metadata
        WHERE is_pii = TRUE
    """)
    return {r['full_col'] for r in result}
```

#### Table Whitelist Extension
```python
# Current: hardcoded 6-table whitelist for masking rules
SENSITIVE_TABLES = {"customers", "accounts", "transactions", "risk_flags"}

# Target: derive from table_metadata
async def get_sensitive_tables(self) -> Set[str]:
    return {r['table_name'] for r in await self.db.fetch("""
        SELECT table_name FROM table_metadata WHERE is_pii_bearing = TRUE
    """)}
```

---

## ACCURACY IMPACT PROJECTION

| Agent Upgrade | Expected Accuracy Gain |
|--------------|----------------------|
| Intent: French pattern + KPI recognition | +15-20% on French queries |
| Intent: 6 new intent categories | +10% on loan/KYC/AML queries |
| Schema: Dynamic table discovery via DB | +20% on multi-domain queries |
| Schema: join_registry BFS traversal | +15% on join-heavy queries |
| Entity: Banking glossary normalization | +25% on banking terminology queries |
| Entity: 20+ entity types | +10% on new domain queries |
| SQL: ALLOWED_COLUMNS bug fix | +5-8% on branches/risk_flags queries |
| SQL: Metric registry formula injection | +30% on KPI computation queries |
| SQL: Join registry validation | +10% on join correctness |
| Validation: Table existence check | -5% false positives (rejects ghost queries) |

**Projected overall accuracy**: from ~45% → **75-80%** (single domain queries)
**KPI computation accuracy**: from ~30% → **85%+** (with metric registry)

---

## BACKWARD COMPATIBILITY GUARANTEE

All refactors follow these rules:
1. Existing API contracts unchanged (same HTTP endpoints, same request/response models)
2. Hardcoded dicts kept as fallback when DB unavailable
3. New DB calls are `async` and fail gracefully (log + use fallback)
4. All new fields in response models are Optional with defaults
5. No breaking changes to KPI Governance, Risk Center, Compliance Center
