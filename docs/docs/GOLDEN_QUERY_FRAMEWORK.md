# GOLDEN QUERY EVALUATION FRAMEWORK
**Phase 6 — 100 Banking NL-to-SQL Benchmark Questions**
*Tunisian Banking Context — French & English Queries*

---

## FRAMEWORK STRUCTURE

Each golden query defines:
- `id`: unique identifier
- `category`: analytics domain  
- `difficulty`: simple / medium / complex / expert
- `question_fr`: French query (primary)
- `question_en`: English equivalent
- `expected_tables`: tables that MUST appear in generated SQL
- `expected_entities`: banking entities that MUST be resolved
- `expected_kpi_ids`: metric_registry IDs if KPI computation expected
- `sql_pattern`: regex or SQL template for validation
- `expected_columns`: key columns that must appear in SELECT or WHERE
- `notes`: explanation of what makes this query hard

---

## CATEGORY 1: CUSTOMER ANALYTICS (15 queries)

### GQ-CUST-001
```yaml
id: GQ-CUST-001
difficulty: simple
question_fr: "Combien de clients avons-nous au total ?"
question_en: "How many customers do we have in total?"
expected_tables: [customers]
expected_entities: [customer]
expected_columns: [customer_id]
sql_pattern: "SELECT COUNT.*FROM customers"
```

### GQ-CUST-002
```yaml
id: GQ-CUST-002
difficulty: simple
question_fr: "Quels sont les clients du segment premium ?"
question_en: "Which customers are in the premium segment?"
expected_tables: [customers]
expected_entities: [customer]
expected_columns: [name, segment]
sql_pattern: "WHERE.*segment.*=.*premium"
```

### GQ-CUST-003
```yaml
id: GQ-CUST-003
difficulty: medium
question_fr: "Quels clients n'ont pas complété leur KYC ?"
question_en: "Which customers have not completed KYC verification?"
expected_tables: [customers]
expected_entities: [customer]
expected_columns: [kyc_verified, name]
sql_pattern: "WHERE.*kyc_verified.*=.*false"
```

### GQ-CUST-004
```yaml
id: GQ-CUST-004
difficulty: medium
question_fr: "Montrez-moi les clients à risque élevé avec leurs scores"
question_en: "Show me high-risk customers with their risk scores"
expected_tables: [customers, customer_risk_scores]
expected_entities: [customer]
expected_columns: [name, risk_score, score_band]
sql_pattern: "JOIN.*customer_risk_scores|WHERE.*risk_score|WHERE.*score_band"
```

### GQ-CUST-005
```yaml
id: GQ-CUST-005
difficulty: medium
question_fr: "Combien de nouveaux clients avons-nous acquis ce mois-ci ?"
question_en: "How many new customers did we acquire this month?"
expected_tables: [customers]
expected_entities: [customer]
expected_columns: [customer_id, created_at]
sql_pattern: "COUNT.*created_at.*INTERVAL.*month|date_trunc.*month"
```

### GQ-CUST-006
```yaml
id: GQ-CUST-006
difficulty: complex
question_fr: "Quels clients ont des comptes actifs mais des dossiers KYC expirés ?"
question_en: "Which customers have active accounts but expired KYC cases?"
expected_tables: [customers, accounts, kyc_cases]
expected_entities: [customer, account, kyc_case]
expected_columns: [status, kyc_case_id, due_date]
sql_pattern: "JOIN.*accounts.*JOIN.*kyc_cases|WHERE.*accounts.status.*active"
```

### GQ-CUST-007
```yaml
id: GQ-CUST-007
difficulty: complex
question_fr: "Quels sont les clients PEP (personnes politiquement exposées) ?"
question_en: "Who are our politically exposed person (PEP) customers?"
expected_tables: [customers, customer_profiles, pep_screening]
expected_entities: [customer]
expected_columns: [politically_exposed, pep_details]
sql_pattern: "WHERE.*politically_exposed.*=.*true|JOIN.*pep_screening"
notes: "Tests PEP → customer_profiles synonym resolution"
```

### GQ-CUST-008
```yaml
id: GQ-CUST-008
difficulty: medium
question_fr: "Répartition des clients par gouvernorat"
question_en: "Customer distribution by governorate"
expected_tables: [customers, customer_addresses]
expected_entities: [customer]
expected_columns: [governorate]
sql_pattern: "GROUP BY.*governorate|JOIN.*customer_addresses"
```

### GQ-CUST-009
```yaml
id: GQ-CUST-009
difficulty: simple
question_fr: "Liste des clients de Sfax avec leurs coordonnées"
question_en: "List customers from Sfax with their contacts"
expected_tables: [customers, customer_addresses, customer_contacts]
expected_entities: [customer]
expected_columns: [city, contact_value]
sql_pattern: "WHERE.*city.*=.*Sfax|JOIN.*customer_addresses"
```

### GQ-CUST-010
```yaml
id: GQ-CUST-010
difficulty: expert
question_fr: "Taux de rétention client ce trimestre vs le trimestre précédent"
question_en: "Customer retention rate this quarter vs last quarter"
expected_tables: [customers, accounts]
expected_kpi_ids: [customer_retention_rate]
sql_pattern: "COUNT.*DISTINCT.*customer_id.*status.*active"
notes: "Requires time-series comparison and KPI formula"
```

### GQ-CUST-011 through GQ-CUST-015
```yaml
GQ-CUST-011: "Clients avec plus de 3 comptes actifs" [customers, accounts]
GQ-CUST-012: "Clients sans transaction depuis 6 mois" [customers, transactions]
GQ-CUST-013: "Profil moyen du client premium" [customers, customer_profiles, accounts]
GQ-CUST-014: "Clients avec solde total > 100 000 TND" [customers, accounts]
GQ-CUST-015: "Top 10 clients par montant total déposé" [customers, accounts]
```

---

## CATEGORY 2: DEPOSIT ANALYTICS (12 queries)

### GQ-DEP-001
```yaml
id: GQ-DEP-001
difficulty: simple
question_fr: "Quel est le total des dépôts dans toutes les agences ?"
question_en: "What is the total deposits across all branches?"
expected_tables: [accounts]
expected_kpi_ids: [total_deposits]
sql_pattern: "SELECT SUM.*balance.*FROM accounts|WHERE.*status.*active"
```

### GQ-DEP-002
```yaml
id: GQ-DEP-002
difficulty: medium
question_fr: "Évolution des dépôts sur les 12 derniers mois"
question_en: "Evolution of deposits over the last 12 months"
expected_tables: [account_balances]
expected_columns: [snapshot_date, total_balance]
sql_pattern: "GROUP BY.*month|date_trunc.*month.*account_balances"
notes: "Requires time-series table account_balances"
```

### GQ-DEP-003
```yaml
id: GQ-DEP-003
difficulty: medium
question_fr: "Dépôts par type de compte (courant, épargne, DAT)"
question_en: "Deposits by account type (checking, savings, term)"
expected_tables: [accounts]
expected_columns: [account_type, balance]
sql_pattern: "GROUP BY.*account_type|SUM.*balance.*GROUP BY"
```

### GQ-DEP-004
```yaml
id: GQ-DEP-004
difficulty: medium
question_fr: "Total des dépôts par agence et par région"
question_en: "Total deposits by branch and region"
expected_tables: [accounts, branches, regions]
expected_columns: [branch_id, region_id, balance]
sql_pattern: "JOIN.*branches.*JOIN.*regions|GROUP BY.*branch"
```

### GQ-DEP-005
```yaml
id: GQ-DEP-005
difficulty: complex
question_fr: "Comptes avec solde négatif ou découvert autorisé dépassé"
question_en: "Accounts with negative balance or exceeded overdraft"
expected_tables: [accounts]
expected_columns: [balance, available_balance]
sql_pattern: "WHERE.*balance.*<.*0|WHERE.*available_balance.*<.*0"
```

### GQ-DEP-006 through GQ-DEP-012
```yaml
GQ-DEP-006: "Taux de croissance des dépôts MoM" [account_balances] kpi: deposit_growth_rate
GQ-DEP-007: "Comptes dormants (sans transaction depuis 12 mois)" [accounts, transactions]
GQ-DEP-008: "Répartition des soldes par segment client" [accounts, customers]
GQ-DEP-009: "Solde moyen par type de compte" [accounts] GROUP BY account_type
GQ-DEP-010: "Dépôts des clients entreprises vs particuliers" [accounts, customers]
GQ-DEP-011: "Top 5 agences par total dépôts" [accounts, branches]
GQ-DEP-012: "Dépôts à terme arrivant à échéance ce mois" [accounts, account_status_history]
```

---

## CATEGORY 3: LOAN ANALYTICS (20 queries)

### GQ-LOAN-001
```yaml
id: GQ-LOAN-001
difficulty: simple
question_fr: "Quel est l'encours total des crédits ?"
question_en: "What is the total outstanding loan balance?"
expected_tables: [loan_contracts]
expected_kpi_ids: [active_loan_portfolio]
sql_pattern: "SELECT SUM.*outstanding_balance.*FROM loan_contracts|WHERE.*status.*actif"
notes: "Basic loan query — was impossible before, tests Loan domain"
```

### GQ-LOAN-002
```yaml
id: GQ-LOAN-002
difficulty: simple
question_fr: "Quels sont les crédits en retard de paiement ?"
question_en: "Which loans are past due?"
expected_tables: [loan_contracts]
expected_columns: [days_past_due, loan_id, customer_id]
sql_pattern: "WHERE.*days_past_due.*>.*0"
```

### GQ-LOAN-003
```yaml
id: GQ-LOAN-003
difficulty: medium
question_fr: "Quel est le taux de créances classées (NPL) ?"
question_en: "What is the non-performing loan (NPL) ratio?"
expected_tables: [loan_contracts, non_performing_loans]
expected_kpi_ids: [npl_ratio]
sql_pattern: "SUM.*days_past_due.*>.*90|non_performing_loans"
notes: "Critical KPI test — was 0% accurate before, now uses metric_registry"
```

### GQ-LOAN-004
```yaml
id: GQ-LOAN-004
difficulty: medium
question_fr: "Montrez-moi les créances douteuses"
question_en: "Show me the bad loans"
expected_tables: [non_performing_loans, loan_contracts]
expected_entities: [npl]
sql_pattern: "FROM non_performing_loans|WHERE.*days_past_due.*>.*90"
notes: "Tests synonym: 'créances douteuses' → non_performing_loans"
```

### GQ-LOAN-005
```yaml
id: GQ-LOAN-005
difficulty: complex
question_fr: "Taux de couverture des provisions sur les NPL"
question_en: "Provision coverage ratio for non-performing loans"
expected_tables: [provisions, non_performing_loans]
expected_kpi_ids: [provision_coverage]
sql_pattern: "SUM.*provision_amount.*SUM.*npl_amount"
```

### GQ-LOAN-006
```yaml
id: GQ-LOAN-006
difficulty: medium
question_fr: "Répartition des crédits par type (immobilier, consommation, auto)"
question_en: "Loan distribution by type (mortgage, consumer, auto)"
expected_tables: [loan_contracts]
expected_columns: [loan_type, principal_amount]
sql_pattern: "GROUP BY.*loan_type"
```

### GQ-LOAN-007
```yaml
id: GQ-LOAN-007
difficulty: complex
question_fr: "Ratio crédits / dépôts (LDR)"
question_en: "Loan-to-deposit ratio (LDR)"
expected_tables: [loan_contracts, accounts]
expected_kpi_ids: [loan_to_deposit]
sql_pattern: "SUM.*outstanding_balance.*SUM.*balance"
```

### GQ-LOAN-008
```yaml
id: GQ-LOAN-008
difficulty: medium
question_fr: "Clients ayant un crédit immobilier et un score de risque élevé"
question_en: "Customers with a mortgage and high risk score"
expected_tables: [loan_contracts, customers]
expected_columns: [loan_type, risk_score]
sql_pattern: "JOIN.*customers|WHERE.*loan_type.*immobilier.*risk_score"
```

### GQ-LOAN-009
```yaml
id: GQ-LOAN-009
difficulty: complex
question_fr: "Prévision des remboursements pour le mois prochain"
question_en: "Loan repayment forecast for next month"
expected_tables: [loan_installments, loan_contracts]
expected_columns: [due_date, installment_amount]
sql_pattern: "WHERE.*due_date.*INTERVAL.*month|date_trunc"
```

### GQ-LOAN-010
```yaml
id: GQ-LOAN-010
difficulty: complex
question_fr: "Crédits dont le collatéral est insuffisant (LTV > 80%)"
question_en: "Loans with insufficient collateral (LTV > 80%)"
expected_tables: [loan_contracts, collateral]
expected_kpi_ids: [collateral_coverage]
sql_pattern: "JOIN.*collateral|outstanding_balance.*collateral_value"
```

### GQ-LOAN-011 through GQ-LOAN-020
```yaml
GQ-LOAN-011: "Historique des incidents de paiement par client" [loan_contracts, loan_delinquency_events]
GQ-LOAN-012: "Crédits restructurés sur les 6 derniers mois" [loan_restructuring]
GQ-LOAN-013: "Montant total des provisions constituées" [provisions]
GQ-LOAN-014: "Classement des agences par NPL" [loan_contracts, branches] GROUP BY branch
GQ-LOAN-015: "Cautions engagées sur les crédits en contentieux" [guarantees, loan_contracts]
GQ-LOAN-016: "Taille moyenne des crédits par segment client" [loan_contracts, customers]
GQ-LOAN-017: "Taux de défaut par type de crédit" [loan_contracts] kpi: default_rate
GQ-LOAN-018: "Crédits arrivant à maturité dans les 90 jours" [loan_contracts] WHERE maturity_date
GQ-LOAN-019: "Encours crédits par région" [loan_contracts, accounts, branches, regions]
GQ-LOAN-020: "Créances en retard entre 30 et 90 jours (Bucket 1-2)" [loan_contracts] WHERE days_past_due BETWEEN
```

---

## CATEGORY 4: RISK ANALYTICS (15 queries)

### GQ-RISK-001
```yaml
id: GQ-RISK-001
difficulty: simple
question_fr: "Combien de signaux de risque ouverts avons-nous ?"
question_en: "How many open risk flags do we have?"
expected_tables: [risk_flags]
expected_kpi_ids: [total_risk_flags]
sql_pattern: "COUNT.*FROM risk_flags.*WHERE.*resolved.*=.*false"
```

### GQ-RISK-002
```yaml
id: GQ-RISK-002
difficulty: medium
question_fr: "Quels clients ont des alertes AML ouvertes ?"
question_en: "Which customers have open AML alerts?"
expected_tables: [aml_alerts, customers]
expected_columns: [alert_type, status, severity]
sql_pattern: "JOIN.*customers|WHERE.*status.*=.*ouvert|open"
notes: "Tests AML domain — was 0% accurate before"
```

### GQ-RISK-003
```yaml
id: GQ-RISK-003
difficulty: medium
question_fr: "Exposition totale aux risques par segment"
question_en: "Total risk exposure by customer segment"
expected_tables: [risk_exposure, customers]
expected_kpi_ids: [total_risk_exposure]
sql_pattern: "JOIN.*customers|GROUP BY.*segment"
```

### GQ-RISK-004
```yaml
id: GQ-RISK-004
difficulty: complex
question_fr: "Évolution du score de risque moyen sur 24 mois"
question_en: "Evolution of average risk score over 24 months"
expected_tables: [customer_risk_scores, risk_score_history]
expected_columns: [score, score_date]
sql_pattern: "GROUP BY.*month.*score_date|date_trunc.*month"
```

### GQ-RISK-005
```yaml
id: GQ-RISK-005
difficulty: expert
question_fr: "Résumé du risque portefeuille de ce mois"
question_en: "Portfolio risk summary for this month"
expected_tables: [portfolio_risk_summary, loan_contracts, risk_flags]
sql_pattern: "portfolio_risk_summary|FROM loan_contracts.*JOIN"
```

### GQ-RISK-006 through GQ-RISK-015
```yaml
GQ-RISK-006: "Clients avec score de risque critique (>0.8)" [customer_risk_scores]
GQ-RISK-007: "Alertes AML par type et sévérité" [aml_alerts] GROUP BY alert_type, severity
GQ-RISK-008: "Taux d'alertes AML par mille clients" [aml_alerts, customers] kpi: aml_alert_rate
GQ-RISK-009: "Limites de risque dépassées" [risk_limits, risk_exposure]
GQ-RISK-010: "Clients avec plusieurs flags de risque actifs" [risk_flags] GROUP BY customer_id HAVING COUNT > 1
GQ-RISK-011: "Événements de risque sur les 30 derniers jours" [risk_events] WHERE created_at
GQ-RISK-012: "Modèles de risque actifs et leurs derniers scores" [risk_models, risk_assessments]
GQ-RISK-013: "Répartition des flags de risque par type et agence" [risk_flags, accounts, branches]
GQ-RISK-014: "Clients PEP avec alertes AML" [customer_profiles, aml_alerts] JOIN on customer_id
GQ-RISK-015: "Score de risque vs défaut sur crédits" [customer_risk_scores, loan_contracts]
```

---

## CATEGORY 5: COMPLIANCE ANALYTICS (12 queries)

### GQ-COMP-001
```yaml
id: GQ-COMP-001
difficulty: simple
question_fr: "Quelles violations de conformité sont ouvertes ?"
question_en: "What compliance violations are open?"
expected_tables: [compliance_violations]
expected_columns: [violation_type, severity, status]
sql_pattern: "FROM compliance_violations.*WHERE.*status.*=.*open"
```

### GQ-COMP-002
```yaml
id: GQ-COMP-002
difficulty: medium
question_fr: "Taux de conformité KYC global"
question_en: "Overall KYC compliance rate"
expected_tables: [customers]
expected_kpi_ids: [kyc_compliance_rate]
sql_pattern: "COUNT.*kyc_verified.*=.*true.*COUNT.*customer_id"
```

### GQ-COMP-003
```yaml
id: GQ-COMP-003
difficulty: medium
question_fr: "Dossiers KYC incomplets ou expirés"
question_en: "Incomplete or expired KYC cases"
expected_tables: [kyc_cases]
expected_columns: [status, due_date]
sql_pattern: "WHERE.*status.*IN.*expiré|rejeté|WHERE.*due_date.*<.*NOW"
```

### GQ-COMP-004
```yaml
id: GQ-COMP-004
difficulty: complex
question_fr: "Déclarations de soupçon émises ce trimestre"
question_en: "Suspicious activity reports filed this quarter"
expected_tables: [suspicious_activity_reports]
expected_columns: [created_at, status]
sql_pattern: "FROM suspicious_activity_reports.*WHERE.*date_trunc.*quarter"
notes: "Tests DSFR/SAR domain"
```

### GQ-COMP-005
```yaml
id: GQ-COMP-005
difficulty: medium
question_fr: "Score de conformité global de la banque"
question_en: "Overall regulatory compliance score"
expected_tables: [compliance_violations, compliance_rules]
expected_kpi_ids: [compliance_score]
sql_pattern: "compliance_violations|compliance_rules"
```

### GQ-COMP-006 through GQ-COMP-012
```yaml
GQ-COMP-006: "Transactions dépassant le seuil réglementaire (>10 000 TND)" [transactions] WHERE amount > 10000
GQ-COMP-007: "Règles de conformité actives par réglementation" [compliance_rules] WHERE enabled = true
GQ-COMP-008: "Constats d'audit non résolus" [audit_findings] WHERE status != 'résolu'
GQ-COMP-009: "Violations AML par agence" [compliance_violations, branches]
GQ-COMP-010: "Clients sous surveillance renforcée" [kyc_cases] WHERE case_type = 'enhanced_dd'
GQ-COMP-011: "Revues de conformité dues ce mois" [compliance_reviews] WHERE due_date
GQ-COMP-012: "Taux d'alertes AML résolues vs ouvertes" [aml_alerts] GROUP BY status
```

---

## CATEGORY 6: BRANCH ANALYTICS (12 queries)

### GQ-BRANCH-001
```yaml
id: GQ-BRANCH-001
difficulty: simple
question_fr: "Quelles sont toutes nos agences en Tunisie ?"
question_en: "What are all our branches in Tunisia?"
expected_tables: [branches]
expected_columns: [name, city, region_id]
sql_pattern: "SELECT.*FROM branches"
```

### GQ-BRANCH-002
```yaml
id: GQ-BRANCH-002
difficulty: medium
question_fr: "Quelle agence a le plus grand volume de dépôts ?"
question_en: "Which branch has the highest deposit volume?"
expected_tables: [accounts, branches]
expected_columns: [branch_id, balance]
sql_pattern: "JOIN.*branches|GROUP BY.*branch_id.*ORDER BY.*SUM.*balance.*DESC"
```

### GQ-BRANCH-003
```yaml
id: GQ-BRANCH-003
difficulty: medium
question_fr: "Performance des agences par région — Grand Tunis"
question_en: "Branch performance by region — Grand Tunis"
expected_tables: [branches, regions, accounts]
expected_columns: [region_id, branch_id]
sql_pattern: "JOIN.*regions.*WHERE.*region_name.*Grand Tunis|region_id"
```

### GQ-BRANCH-004
```yaml
id: GQ-BRANCH-004
difficulty: complex
question_fr: "Rentabilité de chaque agence"
question_en: "Profitability of each branch"
expected_tables: [branches, fee_income, interest_income, operating_expenses]
expected_kpi_ids: [branch_profitability]
sql_pattern: "GROUP BY.*branch_id.*JOIN.*fee_income|interest_income"
```

### GQ-BRANCH-005 through GQ-BRANCH-012
```yaml
GQ-BRANCH-005: "Nombre de clients par agence" [customers, accounts, branches]
GQ-BRANCH-006: "Volume de transactions par agence ce mois" [transactions, accounts, branches]
GQ-BRANCH-007: "NPL par agence classé du plus élevé au plus faible" [loan_contracts, branches]
GQ-BRANCH-008: "Agences avec plus de 10 alertes AML ce mois" [aml_alerts, accounts, branches]
GQ-BRANCH-009: "Effectif par agence" [employees, branches]
GQ-BRANCH-010: "Chargés de clientèle et leur portefeuille" [employees, relationship_managers, customers]
GQ-BRANCH-011: "Agences sans directeur assigné" [branches] WHERE manager_id IS NULL
GQ-BRANCH-012: "Comparaison dépôts agences Tunis vs Sfax vs Sousse" [accounts, branches] WHERE city IN
```

---

## CATEGORY 7: EXECUTIVE ANALYTICS (14 queries)

### GQ-EXEC-001
```yaml
id: GQ-EXEC-001
difficulty: expert
question_fr: "Tableau de bord exécutif — KPIs principaux"
question_en: "Executive dashboard — main KPIs"
expected_tables: [customers, accounts, loan_contracts, aml_alerts, kyc_cases]
sql_pattern: "UNION ALL|multiple SELECT|WITH.*AS"
notes: "Requires multi-KPI query — tests orchestration"
```

### GQ-EXEC-002
```yaml
id: GQ-EXEC-002
difficulty: expert
question_fr: "ROE et ROA de la banque ce trimestre"
question_en: "Bank ROE and ROA this quarter"
expected_tables: [income_statement_snapshots, balance_sheet_snapshots]
expected_kpi_ids: [roe, roa]
sql_pattern: "net_income.*equity|total_assets.*income_statement_snapshots"
notes: "Tests GL/Finance domain — was 0% accurate before"
```

### GQ-EXEC-003
```yaml
id: GQ-EXEC-003
difficulty: expert
question_fr: "Coefficient d'exploitation ce semestre"
question_en: "Cost-to-income ratio this semester"
expected_tables: [income_statement_snapshots]
expected_kpi_ids: [cost_income_ratio]
sql_pattern: "operating_expenses.*pnb|income_statement"
```

### GQ-EXEC-004
```yaml
id: GQ-EXEC-004
difficulty: expert
question_fr: "Résumé risque crédit du portefeuille — NPL, provisions, encours"
question_en: "Credit risk portfolio summary — NPL, provisions, outstanding balance"
expected_tables: [loan_contracts, non_performing_loans, provisions]
expected_kpi_ids: [npl_ratio, provision_coverage, active_loan_portfolio]
sql_pattern: "non_performing_loans|provisions"
```

### GQ-EXEC-005 through GQ-EXEC-014
```yaml
GQ-EXEC-005: "Croissance dépôts et crédits MoM" [account_balances, loan_contracts] time-series
GQ-EXEC-006: "Top 3 risques identifiés ce mois" [risk_events, aml_alerts, compliance_violations]
GQ-EXEC-007: "PNB du mois courant" [fee_income, interest_income] kpi: pnb
GQ-EXEC-008: "Taux KYC conforme vs non conforme par région" [customers, kyc_cases, branches, regions]
GQ-EXEC-009: "Synthèse alertes AML — ouvertes, clôturées, taux résolution" [aml_alerts] GROUP BY status
GQ-EXEC-010: "Performance crédit vs objectifs" [loan_contracts, profitability_metrics]
GQ-EXEC-011: "Evolution du nombre de clients sur 24 mois" [customers] time-series by month
GQ-EXEC-012: "Bilan simplifié du mois" [balance_sheet_snapshots] latest snapshot
GQ-EXEC-013: "Compte de résultat du mois" [income_statement_snapshots] latest snapshot
GQ-EXEC-014: "Classement des 5 meilleures agences tous critères" [branches, accounts, loan_contracts, aml_alerts]
```

---

## EVALUATION SCORING RUBRIC

### Per Query Scoring (0-100)

| Check | Points | Pass Condition |
|-------|--------|----------------|
| Intent classification | 15 | Correct intent category detected |
| Entity resolution | 15 | All expected_entities resolved correctly |
| Table selection | 20 | All expected_tables present in generated SQL |
| Join correctness | 15 | Joins use join_registry-verified keys |
| SQL validity | 10 | SQL parses without error |
| Execution success | 15 | Query executes against DB without error |
| Result quality | 10 | Result contains expected columns/values |

### Difficulty Multipliers
| Difficulty | Multiplier |
|-----------|-----------|
| simple | 1.0x |
| medium | 1.2x |
| complex | 1.5x |
| expert | 2.0x |

### Category Pass Thresholds
| Category | Minimum Score | Current Baseline | Target |
|----------|-------------|-----------------|--------|
| Customer Analytics | 70/100 | ~50 | 85 |
| Deposit Analytics | 70/100 | ~60 | 85 |
| Loan Analytics | 70/100 | ~10 | 80 |
| Risk Analytics | 70/100 | ~35 | 80 |
| Compliance Analytics | 70/100 | ~40 | 80 |
| Branch Analytics | 70/100 | ~55 | 85 |
| Executive Analytics | 70/100 | ~15 | 75 |

---

## IMPLEMENTATION: `golden_queries` Table

```sql
CREATE TABLE golden_queries (
    query_id            VARCHAR(50) PRIMARY KEY,
    category            VARCHAR(50) NOT NULL,
    difficulty          VARCHAR(20) NOT NULL,
    question_fr         TEXT NOT NULL,
    question_en         TEXT,
    expected_tables     TEXT[] NOT NULL,
    expected_entities   TEXT[],
    expected_kpi_ids    TEXT[],
    sql_pattern         TEXT,
    expected_columns    TEXT[],
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## AUTOMATED EVALUATION SCRIPT

```python
# scripts/run_benchmark.py
import asyncio
from typing import List, Dict
import re

async def evaluate_golden_query(gq: dict, pipeline) -> dict:
    """Run a single golden query through the full pipeline and score it."""
    
    # Run pipeline
    result = await pipeline.process(gq['question_fr'])
    
    score = {}
    
    # 1. Intent check (15 pts)
    intent_ok = result.intent in gq.get('expected_intents', [result.intent])
    score['intent'] = 15 if intent_ok else 0
    
    # 2. Entity check (15 pts)
    expected_entities = set(gq.get('expected_entities', []))
    resolved_entities = set(result.entities)
    entity_overlap = len(expected_entities & resolved_entities) / max(len(expected_entities), 1)
    score['entities'] = round(15 * entity_overlap)
    
    # 3. Table selection (20 pts)
    expected_tables = set(gq['expected_tables'])
    used_tables = set(result.tables_used)
    table_recall = len(expected_tables & used_tables) / max(len(expected_tables), 1)
    score['tables'] = round(20 * table_recall)
    
    # 4. SQL validity (10 pts)
    try:
        import sqlparse
        sqlparse.parse(result.sql)
        score['sql_valid'] = 10
    except:
        score['sql_valid'] = 0
    
    # 5. Execution success (15 pts)
    exec_result = await pipeline.execute(result.sql)
    score['execution'] = 15 if exec_result.success else 0
    
    # 6. SQL pattern match (15 pts — join correctness proxy)
    if gq.get('sql_pattern'):
        pattern_match = bool(re.search(gq['sql_pattern'], result.sql, re.IGNORECASE))
        score['joins'] = 15 if pattern_match else 5
    else:
        score['joins'] = 15
    
    # 7. Result quality (10 pts)
    expected_cols = set(gq.get('expected_columns', []))
    if expected_cols and exec_result.columns:
        col_overlap = len(expected_cols & set(exec_result.columns)) / len(expected_cols)
        score['quality'] = round(10 * col_overlap)
    else:
        score['quality'] = 10
    
    total = sum(score.values())
    
    return {
        'query_id': gq['query_id'],
        'category': gq['category'],
        'difficulty': gq['difficulty'],
        'total_score': total,
        'scores': score,
        'question': gq['question_fr'],
        'generated_sql': result.sql,
        'passed': total >= 70,
    }

async def run_full_benchmark(pipeline) -> Dict:
    queries = await load_golden_queries_from_db()
    results = await asyncio.gather(*[
        evaluate_golden_query(gq, pipeline) for gq in queries
    ])
    
    by_category = {}
    for r in results:
        cat = r['category']
        by_category.setdefault(cat, []).append(r)
    
    summary = {}
    for cat, cat_results in by_category.items():
        scores = [r['total_score'] for r in cat_results]
        summary[cat] = {
            'count': len(cat_results),
            'avg_score': sum(scores) / len(scores),
            'pass_rate': sum(1 for r in cat_results if r['passed']) / len(cat_results),
            'min_score': min(scores),
            'max_score': max(scores),
        }
    
    return {'by_category': summary, 'results': results}
```
