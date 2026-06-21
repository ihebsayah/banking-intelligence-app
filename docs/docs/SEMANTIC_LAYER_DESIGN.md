# SEMANTIC LAYER DESIGN
**Phase 6 — Business Understanding Layer for Banking Intelligence**
*The semantic layer is what transforms SQL generation from guessing to understanding.*

---

## ARCHITECTURE OVERVIEW

```
User Query (French/Arabic/English)
        │
        ▼
┌─────────────────┐
│  Business       │  ◄── synonyms: "créances douteuses" → non_performing_loans
│  Glossary       │  ◄── "NPL" → non_performing_loans
│  (DB table)     │  ◄── "taux de sinistralité" → npl_ratio metric
└────────┬────────┘
         │ resolved term
         ▼
┌─────────────────┐
│  Metric         │  ◄── "ROE" → formula: net_income / equity * 100
│  Registry       │  ◄── source_tables: [income_statement_snapshots, balance_sheet_snapshots]
│  (DB table)     │
└────────┬────────┘
         │ source tables + formula
         ▼
┌─────────────────┐
│  Table          │  ◄── business_description: "Contrats de crédit accordés..."
│  Metadata       │  ◄── domain: "loan", is_pii_bearing: false
│  (DB table)     │
└────────┬────────┘
         │ table context
         ▼
┌─────────────────┐
│  Column         │  ◄── synonyms: ["capital restant dû", "encours", "outstanding"]
│  Metadata       │  ◄── business_description: "Montant restant à rembourser"
│  (DB table)     │
└────────┬────────┘
         │ column context
         ▼
┌─────────────────┐
│  Join           │  ◄── source: loan_contracts.customer_id → customers.customer_id
│  Registry       │  ◄── relationship: many_to_one
│  (DB table)     │
└────────┬────────┘
         │ join paths
         ▼
    SQL Agent (safe, accurate SQL generation)
```

---

## TABLE 1: `business_glossary` — Seed Data (50 Terms)

| term | definition | synonyms | domain | source_tables | formula |
|------|-----------|----------|--------|---------------|---------|
| NPL | Créance classée non performante. Prêt en retard de paiement supérieur à 90 jours. | ["créances classées","bad loans","prêts non performants","sinistres"] | loan | ["non_performing_loans","loan_contracts"] | COUNT(*) FROM non_performing_loans WHERE status = 'contentieux' |
| ROE | Rendement des capitaux propres. Mesure la rentabilité des actionnaires. | ["return on equity","rentabilité des fonds propres","RCP"] | finance | ["income_statement_snapshots","balance_sheet_snapshots"] | net_income / equity * 100 |
| ROA | Rendement des actifs. Profit généré pour chaque dinar d'actif. | ["return on assets","rentabilité des actifs"] | finance | ["income_statement_snapshots","balance_sheet_snapshots"] | net_income / total_assets * 100 |
| LCR | Ratio de couverture des liquidités. Actifs liquides / sorties nettes sur 30 jours. | ["liquidity coverage ratio","ratio de liquidité"] | liquidity | ["balance_sheet_snapshots"] | hqla / net_outflows_30d * 100 |
| NSFR | Ratio structurel de liquidité à long terme. | ["net stable funding ratio"] | liquidity | ["balance_sheet_snapshots"] | available_stable_funding / required_stable_funding * 100 |
| KYC | Connaissance du client. Processus de vérification d'identité réglementaire. | ["know your customer","connaissance client","identification client"] | kyc | ["kyc_cases","customers","customer_documents"] | NULL |
| AML | Lutte contre le blanchiment de capitaux. | ["anti-money laundering","LBC","LCB-FT","lutte contre blanchiment"] | compliance | ["aml_alerts","suspicious_activity_reports"] | NULL |
| Dépôt | Fonds déposés par un client sur un compte bancaire. | ["épargne","solde","balance","avoirs","dépôts","placements"] | account | ["accounts","account_balances"] | SUM(balance) FROM accounts WHERE account_type IN ('savings','checking') |
| Encours | Montant total des crédits accordés non encore remboursés. | ["outstanding balance","capital restant dû","exposition crédit"] | loan | ["loan_contracts"] | SUM(outstanding_balance) FROM loan_contracts WHERE status = 'actif' |
| Provision | Montant mis de côté pour couvrir des pertes potentielles sur créances. | ["provisions","provisionnement","réserve pour créances"] | loan | ["provisions","loan_contracts"] | SUM(provision_amount) FROM provisions |
| Taux NPL | Ratio créances non performantes / total encours crédits. | ["NPL ratio","taux de sinistralité","taux créances douteuses"] | loan | ["non_performing_loans","loan_contracts"] | COUNT(npl) / COUNT(loans) * 100 |
| PEP | Personne Politiquement Exposée. Client à risque AML élevé. | ["politically exposed person","personne politique"] | kyc | ["pep_screening","customer_profiles"] | NULL |
| Tiers | Client individuel ou entreprise. | ["client","customer","bénéficiaire","tiers payant"] | customer | ["customers"] | NULL |
| Virement | Transfert de fonds entre comptes bancaires. | ["transfer","transfert","virement bancaire","virement SWIFT"] | payment | ["transfers","transactions"] | NULL |
| Découvert | Solde négatif autorisé sur un compte courant. | ["overdraft","débit","autorisation de découvert"] | account | ["accounts","loan_contracts"] | NULL |
| Collatéral | Actif mis en garantie pour un prêt. | ["garantie réelle","hypothèque","nantissement","sûreté"] | loan | ["collateral"] | NULL |
| Caution | Garantie personnelle d'un tiers pour un prêt. | ["garantie personnelle","garant","aval"] | loan | ["guarantees"] | NULL |
| Chargé de clientèle | Gestionnaire de relation client en agence. | ["RM","relationship manager","commercial","conseiller"] | organization | ["employees","relationship_managers"] | NULL |
| Taux d'intérêt | Coût du crédit exprimé en pourcentage annuel. | ["taux","interest rate","TEG","TAEG"] | loan | ["loan_contracts","loan_products"] | NULL |
| Mensualité | Montant de remboursement mensuel d'un crédit. | ["installment","échéance mensuelle","remboursement mensuel"] | loan | ["loan_installments"] | NULL |
| Sinistre | Incident de paiement sur un crédit (retard, défaut). | ["défaut","impayé","incident de paiement","delinquency"] | loan | ["loan_delinquency_events"] | NULL |
| Score crédit | Note de risque attribuée à un client pour l'octroi de crédit. | ["credit score","note de risque","scoring"] | risk | ["customer_risk_scores","risk_assessments"] | NULL |
| Compte courant | Compte bancaire principal pour les transactions quotidiennes. | ["current account","compte chèque","CC"] | account | ["accounts"] | NULL |
| Compte épargne | Compte rémunéré pour l'épargne. | ["savings account","DAT","dépôt à terme"] | account | ["accounts"] | NULL |
| Résultat net | Bénéfice ou perte nette après impôts. | ["net income","profit","bénéfice net","résultat"] | finance | ["income_statement_snapshots"] | NULL |
| Total actif | Somme de tous les actifs de la banque. | ["total assets","bilan total","total du bilan"] | finance | ["balance_sheet_snapshots"] | SUM(total_assets) FROM balance_sheet_snapshots WHERE period = latest |
| Ratio coût/revenu | Charges d'exploitation / Produit Net Bancaire. | ["cost to income","CIR","coefficient d'exploitation"] | finance | ["income_statement_snapshots"] | operating_expenses / pnb * 100 |
| PNB | Produit Net Bancaire. Différence entre produits et charges bancaires. | ["produit net bancaire","net banking income","NBI"] | finance | ["income_statement_snapshots"] | interest_income + fee_income - interest_expense |
| Agence | Succursale bancaire physique. | ["branch","succursale","point de vente","PDV"] | organization | ["branches"] | NULL |
| Région | Zone géographique regroupant plusieurs agences. | ["region","zone","territoire"] | organization | ["regions","branches"] | NULL |
| Actif client | Ensemble des produits détenus par un client. | ["customer assets","patrimoine client","AUM"] | customer | ["accounts","loan_contracts"] | NULL |
| Dépôt à terme | Placement bloqué à taux fixe pour une durée déterminée. | ["DAT","term deposit","fixed deposit","certificat de dépôt"] | account | ["accounts"] | NULL |
| LTV | Ratio crédit/valeur du collatéral. | ["loan to value","ratio hypothécaire"] | loan | ["loan_contracts","collateral"] | outstanding_balance / collateral_value * 100 |
| LDR | Ratio crédits/dépôts. Mesure la liquidité structurelle. | ["loan to deposit ratio","taux transformation"] | liquidity | ["loan_contracts","accounts"] | SUM(loans) / SUM(deposits) * 100 |
| CTAF | Commission Tunisienne des Analyses Financières. Régulateur AML en Tunisie. | ["financial intelligence unit","FIU Tunisia"] | compliance | ["suspicious_activity_reports"] | NULL |
| DSFR | Déclaration de Soupçon de Financement du Terrorisme. | ["suspicious activity report","SAR","déclaration de soupçon"] | compliance | ["suspicious_activity_reports"] | NULL |
| BCT | Banque Centrale de Tunisie. | ["central bank","banque centrale"] | compliance | [] | NULL |

---

## TABLE 2: `metric_registry` — Seed Data (25 Metrics)

| metric_id | metric_name_fr | formula | source_tables |
|-----------|---------------|---------|---------------|
| npl_ratio | Taux de créances classées | `SUM(CASE WHEN l.days_past_due > 90 THEN l.outstanding_balance ELSE 0 END) / SUM(l.outstanding_balance) * 100` | loan_contracts |
| provision_coverage | Taux de couverture des provisions | `SUM(p.provision_amount) / SUM(n.npl_amount) * 100` | provisions, non_performing_loans |
| loan_to_deposit | Ratio crédits / dépôts (LDR) | `SUM(l.outstanding_balance) / SUM(a.balance) * 100` | loan_contracts, accounts |
| roe | Rentabilité des fonds propres (ROE) | `i.net_income / b.total_equity * 100` | income_statement_snapshots, balance_sheet_snapshots |
| roa | Rentabilité des actifs (ROA) | `i.net_income / b.total_assets * 100` | income_statement_snapshots, balance_sheet_snapshots |
| cost_income_ratio | Coefficient d'exploitation | `i.operating_expenses / i.pnb * 100` | income_statement_snapshots |
| kyc_compliance_rate | Taux de conformité KYC | `COUNT(CASE WHEN kyc_verified THEN 1 END) / COUNT(*) * 100` | customers |
| aml_alert_rate | Taux d'alertes AML | `COUNT(aml_alerts) / COUNT(DISTINCT customer_id) * 1000` | aml_alerts, customers |
| customer_growth_rate | Taux de croissance clientèle MoM | `(current_month - prior_month) / prior_month * 100` | customers |
| deposit_growth_rate | Taux de croissance des dépôts | `(current_balance - prior_balance) / prior_balance * 100` | account_balances |
| avg_loan_size | Taille moyenne des crédits | `AVG(principal_amount)` | loan_contracts |
| default_rate | Taux de défaut | `COUNT(CASE WHEN status = 'contentieux' THEN 1 END) / COUNT(*) * 100` | loan_contracts |
| avg_days_past_due | Retard moyen de paiement | `AVG(days_past_due) WHERE days_past_due > 0` | loan_contracts |
| total_risk_exposure | Exposition totale aux risques | `SUM(exposure_amount)` | risk_exposure |
| branch_profitability | Rentabilité par agence | `SUM(fee_income + interest_income) - SUM(operating_expenses) GROUP BY branch_id` | fee_income, interest_income, operating_expenses |
| active_loan_portfolio | Portefeuille crédits actif | `SUM(outstanding_balance) WHERE status = 'actif'` | loan_contracts |
| overdue_loans | Crédits en retard | `COUNT(*) WHERE days_past_due BETWEEN 1 AND 90` | loan_contracts |
| pep_customer_rate | % Clients PEP | `COUNT(CASE WHEN politically_exposed THEN 1 END) / COUNT(*) * 100` | customer_profiles |
| pending_kyc_cases | Dossiers KYC en attente | `COUNT(*) WHERE status IN ('ouvert','en_cours')` | kyc_cases |
| open_aml_alerts | Alertes AML ouvertes | `COUNT(*) WHERE status = 'ouvert'` | aml_alerts |
| transaction_volume_30d | Volume de transactions 30j | `COUNT(*) WHERE transaction_date >= NOW() - INTERVAL '30 days'` | transactions |
| avg_transaction_value | Montant moyen transaction | `AVG(ABS(amount))` | transactions |
| income_per_customer | PNB par client | `SUM(fee_income + interest_income) / COUNT(DISTINCT customer_id)` | fee_income, interest_income, customers |
| collateral_coverage | Couverture collatérale | `SUM(collateral_value) / SUM(outstanding_balance) * 100` | collateral, loan_contracts |
| restructured_loan_rate | Taux de prêts restructurés | `COUNT(DISTINCT loan_id) / COUNT(*) * 100` | loan_restructuring, loan_contracts |

---

## TABLE 3: `table_metadata` — All 96 Tables

Excerpt of key entries:

| table_name | business_description | domain | is_pii_bearing | is_analytical |
|-----------|---------------------|--------|----------------|---------------|
| customers | Registre principal des clients de la banque | customer | TRUE | FALSE |
| loan_contracts | Contrats de crédit accordés aux clients | loan | FALSE | FALSE |
| non_performing_loans | Créances classées — prêts en défaut de paiement > 90 jours | loan | FALSE | TRUE |
| aml_alerts | Alertes de lutte contre le blanchiment de capitaux | compliance | FALSE | FALSE |
| balance_sheet_snapshots | Bilans mensuels agrégés de la banque | finance | FALSE | TRUE |
| income_statement_snapshots | Comptes de résultat mensuels | finance | FALSE | TRUE |
| kyc_cases | Dossiers de vérification d'identité et diligence raisonnable | kyc | TRUE | FALSE |
| risk_score_history | Historique des scores de risque par client et par modèle | risk | FALSE | TRUE |
| general_ledger | Plan comptable général de la banque | finance | FALSE | FALSE |
| customer_profiles | Profils démographiques et financiers étendus des clients | customer | TRUE | FALSE |

---

## TABLE 4: `column_metadata` — Key Columns

Excerpt (banking-critical columns):

| table_name | column_name | business_description | synonyms | is_pii |
|-----------|------------|---------------------|----------|--------|
| loan_contracts | outstanding_balance | Montant restant dû sur le crédit | ["encours","capital restant dû","solde crédit"] | FALSE |
| loan_contracts | days_past_due | Nombre de jours de retard de paiement | ["DPD","retard","impayé jours"] | FALSE |
| loan_contracts | status | Statut du crédit (actif/en_retard/contentieux) | ["état crédit","loan status"] | FALSE |
| customers | risk_score | Score de risque global du client (0-1) | ["score","note de risque","rating"] | FALSE |
| customers | kyc_verified | Statut de vérification KYC du client | ["vérifié","KYC status"] | FALSE |
| aml_alerts | severity | Niveau de sévérité de l'alerte | ["criticité","niveau alerte"] | FALSE |
| accounts | balance | Solde actuel du compte | ["solde","balance","avoirs"] | FALSE |
| customer_profiles | politically_exposed | Indicateur PEP (personne politiquement exposée) | ["PEP flag","pep_status"] | FALSE |
| transactions | amount | Montant de la transaction | ["montant","valeur","somme"] | FALSE |
| non_performing_loans | classification | Classe de risque BCT (1-5) | ["classe","classification BCT"] | FALSE |

---

## TABLE 5: `join_registry` — Critical Join Paths

| source_table | source_column | target_table | target_column | relationship_type |
|-------------|--------------|-------------|--------------|-------------------|
| customers | customer_id | accounts | customer_id | one_to_many |
| customers | customer_id | loan_contracts | customer_id | one_to_many |
| customers | customer_id | transactions | customer_id | one_to_many |
| customers | customer_id | risk_flags | customer_id | one_to_many |
| customers | customer_id | kyc_cases | customer_id | one_to_many |
| customers | customer_id | aml_alerts | customer_id | one_to_many |
| customers | customer_id | customer_profiles | customer_id | one_to_one |
| accounts | account_id | transactions | account_id | one_to_many |
| accounts | account_id | loan_contracts | account_id | one_to_many |
| accounts | branch_id | branches | branch_id | many_to_one |
| loan_contracts | loan_id | loan_installments | loan_id | one_to_many |
| loan_contracts | loan_id | loan_repayments | loan_id | one_to_many |
| loan_contracts | loan_id | loan_delinquency_events | loan_id | one_to_many |
| loan_contracts | loan_id | collateral | loan_id | one_to_many |
| loan_contracts | loan_id | provisions | loan_id | one_to_many |
| loan_contracts | loan_id | non_performing_loans | loan_id | one_to_one |
| transactions | transaction_id | aml_alerts | transaction_id | one_to_many |
| branches | branch_id | employees | branch_id | one_to_many |
| branches | region_id | regions | region_id | many_to_one |
| kyc_cases | kyc_case_id | kyc_reviews | kyc_case_id | one_to_many |
| kyc_cases | kyc_case_id | kyc_documents | kyc_case_id | one_to_many |
| kyc_cases | kyc_case_id | kyc_verifications | kyc_case_id | one_to_many |
| aml_alerts | alert_id | suspicious_activity_reports | alert_id | one_to_one |
| general_ledger | account_code | ledger_entries | account_code | one_to_many |

---

## HOW AGENTS CONSUME THE SEMANTIC LAYER

### Schema Agent — Enhanced Flow
```python
# BEFORE (hardcoded dict)
DOMAIN_TO_TABLES = {"loan_analysis": ["loans"]}  # broken

# AFTER (semantic layer query)
async def get_tables_for_intent(intent: str, query: str) -> List[str]:
    # Step 1: Resolve terms via business_glossary
    terms = await resolve_query_terms(query)  # "NPL" → "non_performing_loans"
    
    # Step 2: Get table_metadata for these terms
    tables = await db.fetch("""
        SELECT DISTINCT tm.table_name 
        FROM table_metadata tm
        JOIN column_metadata cm ON cm.table_name = tm.table_name
        WHERE tm.domain = $1 
           OR $2 = ANY(cm.synonyms)
           OR tm.business_description ILIKE $3
        ORDER BY tm.table_name
    """, domain, term, f'%{query}%')
    
    # Step 3: Get join paths from join_registry
    joins = await get_join_paths_from_registry(tables)
    return tables, joins
```

### Entity Resolution Agent — Banking Terminology
```python
# BEFORE: "bad loans" → not recognized
# AFTER: "bad loans" → synonyms match → "non_performing_loans" table

async def resolve_banking_term(user_term: str) -> dict:
    result = await db.fetchrow("""
        SELECT term, source_tables, formula, domain
        FROM business_glossary
        WHERE $1 ILIKE ANY(synonyms)
           OR term ILIKE $1
        LIMIT 1
    """, user_term)
    return result  # {term: "NPL", source_tables: ["non_performing_loans", ...]}
```

### SQL Agent — Metric Registry Usage
```python
# BEFORE: agent guesses NPL ratio formula
# AFTER: agent reads it from metric_registry

async def get_metric_formula(metric_name: str) -> dict:
    return await db.fetchrow("""
        SELECT metric_id, formula, source_tables, dependencies
        FROM metric_registry
        WHERE metric_id ILIKE $1
           OR metric_name_fr ILIKE $1
           OR metric_name_en ILIKE $1
    """, metric_name)
    # Returns: {formula: "SUM(CASE WHEN days_past_due > 90...) / SUM(outstanding_balance) * 100",
    #           source_tables: ["loan_contracts"]}
```

---

## SYNONYM RESOLUTION EXAMPLES

| User says | After glossary lookup | Tables resolved | Formula |
|-----------|----------------------|-----------------|---------|
| "show me bad loans" | NPL → non_performing_loans | non_performing_loans, loan_contracts | COUNT(*) / total_loans * 100 |
| "taux de sinistralité" | Taux NPL → non_performing_loans | loan_contracts | SUM(DPD>90) / SUM(all) * 100 |
| "créances douteuses" | NPL → same | non_performing_loans | same |
| "ROE par agence" | ROE + Agence → GL + branches | income_statement_snapshots, balance_sheet_snapshots, branches | net_income/equity GROUP BY branch |
| "clients à risque élevé" | risk_score > 0.7 | customers, customer_risk_scores | WHERE score_band = 'élevé' |
| "dépôts Grand Tunis" | Dépôt + region | accounts, branches, regions | SUM(balance) WHERE region = 'Grand Tunis' |
| "encours crédits immobiliers" | Encours + type | loan_contracts | SUM(outstanding_balance) WHERE loan_type = 'immobilier' |
| "alertes AML ouvertes" | AML + ouverts | aml_alerts | COUNT WHERE status = 'ouvert' |
| "dossiers KYC en attente" | KYC + en_cours | kyc_cases | COUNT WHERE status IN ('ouvert','en_cours') |
| "coefficient d'exploitation" | CIR → cost_income_ratio | income_statement_snapshots | expenses/PNB * 100 |
