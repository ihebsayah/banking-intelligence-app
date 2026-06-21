-- =============================================================================
-- Phase 6A: Semantic Layer Seed Data
-- init/08-semantic-layer-seed.sql
-- =============================================================================

-- ==========================================
-- 1. SEED BUSINESS GLOSSARY
-- ==========================================
INSERT INTO business_glossary (term, definition, synonyms, domain, business_owner, source_tables, formula, example) VALUES
('NPL', 'Créance classée non performante. Prêt en retard de paiement supérieur à 90 jours.', ARRAY['créances classées','bad loans','prêts non performants','sinistres','créances douteuses','défauts'], 'loan', 'Risques', ARRAY['non_performing_loans','loan_contracts'], 'COUNT(*) FROM non_performing_loans WHERE status = ''contentieux''', 'Afficher les dossiers NPL par agence'),
('ROE', 'Rendement des capitaux propres. Mesure la rentabilité des actionnaires.', ARRAY['return on equity','rentabilité des fonds propres','RCP'], 'finance', 'Finance', ARRAY['income_statement_snapshots','balance_sheet_snapshots'], 'net_income / equity * 100', 'Calculer le ROE du mois dernier'),
('ROA', 'Rendement des actifs. Profit généré pour chaque dinar d''actif.', ARRAY['return on assets','rentabilité des actifs'], 'finance', 'Finance', ARRAY['income_statement_snapshots','balance_sheet_snapshots'], 'net_income / total_assets * 100', 'Quel est le ROA actuel ?'),
('LCR', 'Ratio de couverture des liquidités. Actifs liquides / sorties nettes sur 30 jours.', ARRAY['liquidity coverage ratio','ratio de liquidité','LCR ratio'], 'liquidity', 'Trésorerie', ARRAY['balance_sheet_snapshots'], 'hqla / net_outflows_30d * 100', 'Evolution du LCR sur 12 mois'),
('NSFR', 'Ratio structurel de liquidité à long terme.', ARRAY['net stable funding ratio','NSFR ratio'], 'liquidity', 'Trésorerie', ARRAY['balance_sheet_snapshots'], 'available_stable_funding / required_stable_funding * 100', 'Dernier rapport du ratio NSFR'),
('KYC', 'Connaissance du client. Processus de vérification d''identité réglementaire.', ARRAY['know your customer','connaissance client','identification client','diligence client'], 'kyc', 'Conformité', ARRAY['kyc_cases','customers','customer_documents'], NULL, 'Combien de dossiers KYC sont ouverts ?'),
('AML', 'Lutte contre le blanchiment de capitaux et le financement du terrorisme.', ARRAY['anti-money laundering','LBC','LCB-FT','lutte contre blanchiment'], 'compliance', 'Conformité', ARRAY['aml_alerts','suspicious_activity_reports'], NULL, 'Nombre d''alertes AML détectées'),
('Dépôt', 'Fonds déposés par un client sur un compte bancaire.', ARRAY['épargne','solde','balance','avoirs','dépôts','placements'], 'account', 'Réseau de Détail', ARRAY['accounts','account_balances'], 'SUM(balance) FROM accounts WHERE account_type IN (''savings'',''checking'')', 'Total des dépôts des clients'),
('Encours', 'Montant total des crédits accordés non encore remboursés.', ARRAY['outstanding balance','capital restant dû','exposition crédit','encours crédit'], 'loan', 'Crédits', ARRAY['loan_contracts'], 'SUM(outstanding_balance) FROM loan_contracts WHERE status = ''actif''', 'Quel est l''encours total des crédits ?'),
('Provision', 'Montant mis de côté pour couvrir des pertes potentielles sur créances.', ARRAY['provisions','provisionnement','réserve pour créances','dotations aux provisions'], 'loan', 'Risques', ARRAY['provisions','loan_contracts'], 'SUM(provision_amount) FROM provisions', 'Total des provisions constituées'),
('Taux NPL', 'Ratio créances non performantes / total encours crédits.', ARRAY['NPL ratio','taux de sinistralité','taux créances douteuses','taux de défaut'], 'loan', 'Risques', ARRAY['non_performing_loans','loan_contracts'], 'COUNT(npl) / COUNT(loans) * 100', 'Quel est le taux de NPL actuel ?'),
('PEP', 'Personne Politiquement Exposée. Client à risque AML élevé.', ARRAY['politically exposed person','personne politique','client PEP'], 'kyc', 'Conformité', ARRAY['pep_screening','customer_profiles'], NULL, 'Liste des clients classés PEP'),
('Tiers', 'Client individuel ou entreprise.', ARRAY['client','customer','bénéficiaire','tiers payant'], 'customer', 'Réseau de Détail', ARRAY['customers'], NULL, 'Nombre de tiers actifs'),
('Virement', 'Transfert de fonds entre comptes bancaires.', ARRAY['transfer','transfert','virement bancaire','virement SWIFT'], 'payment', 'Opérations', ARRAY['transfers','transactions'], NULL, 'Volume des virements reçus'),
('Découvert', 'Solde négatif autorisé sur un compte courant.', ARRAY['overdraft','débit','autorisation de découvert','facilité de caisse'], 'account', 'Réseau de Détail', ARRAY['accounts','loan_contracts'], NULL, 'Montant total des découverts autorisés'),
('Collatéral', 'Actif mis en garantie pour un prêt.', ARRAY['garantie réelle','hypothèque','nantissement','sûreté'], 'loan', 'Crédits', ARRAY['collateral'], NULL, 'Valeur totale du collatéral'),
('Caution', 'Garantie personnelle d''un tiers pour un prêt.', ARRAY['garantie personnelle','garant','aval'], 'loan', 'Crédits', ARRAY['guarantees'], NULL, 'Liste des cautions personnelles actives'),
('Chargé de clientèle', 'Gestionnaire de relation client en agence.', ARRAY['RM','relationship manager','commercial','conseiller'], 'organization', 'Réseau de Détail', ARRAY['employees','relationship_managers'], NULL, 'Nombre de clients par chargé de clientèle'),
('Taux d''intérêt', 'Coût du crédit exprimé en pourcentage annuel.', ARRAY['taux','interest rate','TEG','TAEG'], 'loan', 'Crédits', ARRAY['loan_contracts','loan_products'], NULL, 'Taux d''intérêt moyen pondéré'),
('Mensualité', 'Montant de remboursement mensuel d''un crédit.', ARRAY['installment','échéance mensuelle','remboursement mensuel'], 'loan', 'Crédits', ARRAY['loan_installments'], NULL, 'Somme des mensualités dues ce mois-ci'),
('Sinistre', 'Incident de paiement sur un crédit (retard, défaut).', ARRAY['défaut','impayé','incident de paiement','delinquency'], 'loan', 'Risques', ARRAY['loan_delinquency_events'], NULL, 'Nombre de sinistres enregistrés'),
('Score crédit', 'Note de risque attribuée à un client pour l''octroi de crédit.', ARRAY['credit score','note de risque','scoring'], 'risk', 'Risques', ARRAY['customer_risk_scores','risk_assessments'], NULL, 'Score de risque moyen de la clientèle'),
('Compte courant', 'Compte bancaire principal pour les transactions quotidiennes.', ARRAY['current account','compte chèque','CC','compte de dépôt'], 'account', 'Réseau de Détail', ARRAY['accounts'], NULL, 'Nombre de comptes courants ouverts'),
('Compte épargne', 'Compte rémunéré pour l''épargne.', ARRAY['savings account','DAT','dépôt à terme','compte sur livret'], 'account', 'Réseau de Détail', ARRAY['accounts'], NULL, 'Solde moyen des comptes épargne'),
('Résultat net', 'Bénéfice ou perte nette après impôts.', ARRAY['net income','profit','bénéfice net','résultat'], 'finance', 'Finance', ARRAY['income_statement_snapshots'], NULL, 'Résultat net du trimestre courant'),
('Total actif', 'Somme de tous les actifs de la banque.', ARRAY['total assets','bilan total','total du bilan'], 'finance', 'Finance', ARRAY['balance_sheet_snapshots'], 'SUM(total_assets) FROM balance_sheet_snapshots WHERE period = latest', 'Actif total de la banque'),
('Ratio coût/revenu', 'Charges d''exploitation / Produit Net Bancaire.', ARRAY['cost to income','CIR','coefficient d''exploitation'], 'finance', 'Finance', ARRAY['income_statement_snapshots'], 'operating_expenses / pnb * 100', 'Quel est le coefficient d''exploitation ?'),
('PNB', 'Produit Net Bancaire. Différence entre produits et charges bancaires.', ARRAY['produit net bancaire','net banking income','NBI'], 'finance', 'Finance', ARRAY['income_statement_snapshots'], 'interest_income + fee_income - interest_expense', 'PNB mensuel cumulé'),
('Agence', 'Succursale bancaire physique.', ARRAY['branch','succursale','point de vente','PDV'], 'organization', 'Réseau de Détail', ARRAY['branches'], NULL, 'Nombre total d''agences opérationnelles'),
('Région', 'Zone géographique regroupant plusieurs agences.', ARRAY['region','zone','territoire'], 'organization', 'Réseau de Détail', ARRAY['regions','branches'], NULL, 'Répartition des dépôts par région'),
('Actif client', 'Ensemble des produits détenus par un client.', ARRAY['customer assets','patrimoine client','AUM'], 'customer', 'Réseau de Détail', ARRAY['accounts','loan_contracts'], NULL, 'Valeur globale des actifs sous gestion'),
('Dépôt à terme', 'Placement bloqué à taux fixe pour une durée déterminée.', ARRAY['DAT','term deposit','fixed deposit','certificat de dépôt'], 'account', 'Réseau de Détail', ARRAY['accounts'], NULL, 'Volume total des DAT'),
('LTV', 'Ratio crédit/valeur du collatéral.', ARRAY['loan to value','ratio hypothécaire','LTV ratio'], 'loan', 'Risques', ARRAY['loan_contracts','collateral'], 'outstanding_balance / collateral_value * 100', 'LTV moyen des prêts immobiliers'),
('LDR', 'Ratio crédits/dépôts. Mesure la liquidité structurelle.', ARRAY['loan to deposit ratio','taux transformation','LDR ratio'], 'liquidity', 'Trésorerie', ARRAY['loan_contracts','accounts'], 'SUM(loans) / SUM(deposits) * 100', 'LDR global de la banque'),
('CTAF', 'Commission Tunisienne des Analyses Financières. Régulateur AML en Tunisie.', ARRAY['financial intelligence unit','FIU Tunisia','CTAF'], 'compliance', 'Conformité', ARRAY['suspicious_activity_reports'], NULL, 'Rapports envoyés à la CTAF'),
('DSFR', 'Déclaration de Soupçon de Financement du Terrorisme ou Blanchiment.', ARRAY['suspicious activity report','SAR','déclaration de soupçon'], 'compliance', 'Conformité', ARRAY['suspicious_activity_reports'], NULL, 'Nombre de déclarations de soupçon'),
('BCT', 'Banque Centrale de Tunisie. Régulateur bancaire national.', ARRAY['central bank','banque centrale','BCT'], 'compliance', 'Conformité', ARRAY[]::TEXT[], NULL, 'Historique des audits de la BCT')
ON CONFLICT (term) DO NOTHING;

-- ==========================================
-- 2. SEED METRIC REGISTRY
-- ==========================================
INSERT INTO metric_registry (metric_id, metric_name_fr, metric_name_en, formula, description, domain, owner, source_tables, dependencies, unit, refresh_frequency) VALUES
('npl_ratio', 'Taux de créances classées', 'Non-Performing Loan Ratio', 'SUM(CASE WHEN days_past_due > 90 THEN outstanding_balance ELSE 0 END) / SUM(outstanding_balance) * 100', 'Ratio des crédits en souffrance par rapport à l''encours total.', 'loan', 'Risques', ARRAY['loan_contracts'], ARRAY[]::TEXT[], '%', 'mensuel'),
('provision_coverage', 'Taux de couverture des provisions', 'Provision Coverage Ratio', 'SUM(p.provision_amount) / SUM(n.npl_amount) * 100', 'Mesure le niveau de provisionnement des créances classées.', 'loan', 'Risques', ARRAY['provisions','non_performing_loans'], ARRAY[]::TEXT[], '%', 'mensuel'),
('loan_to_deposit', 'Ratio crédits / dépôts (LDR)', 'Loan-to-Deposit Ratio', 'SUM(l.outstanding_balance) / SUM(a.balance) * 100', 'Ratio comparant les encours de crédit aux dépôts de la clientèle.', 'liquidity', 'Trésorerie', ARRAY['loan_contracts','accounts'], ARRAY[]::TEXT[], '%', 'mensuel'),
('roe', 'Rentabilité des fonds propres (ROE)', 'Return on Equity', 'i.net_income / b.total_equity * 100', 'Rentabilité des capitaux investis par les actionnaires.', 'finance', 'Finance', ARRAY['income_statement_snapshots','balance_sheet_snapshots'], ARRAY[]::TEXT[], '%', 'mensuel'),
('roa', 'Rentabilité des actifs (ROA)', 'Return on Assets', 'i.net_income / b.total_assets * 100', 'Rentabilité globale des actifs du bilan.', 'finance', 'Finance', ARRAY['income_statement_snapshots','balance_sheet_snapshots'], ARRAY[]::TEXT[], '%', 'mensuel'),
('cost_income_ratio', 'Coefficient d''exploitation', 'Cost to Income Ratio', 'i.operating_expenses / i.pnb * 100', 'Ratio d''efficience comparant les charges d''exploitation au PNB.', 'finance', 'Finance', ARRAY['income_statement_snapshots'], ARRAY[]::TEXT[], '%', 'mensuel'),
('kyc_compliance_rate', 'Taux de conformité KYC', 'KYC Compliance Rate', 'COUNT(CASE WHEN kyc_verified THEN 1 END) / COUNT(*) * 100', 'Pourcentage de clients dont les pièces KYC sont validées.', 'kyc', 'Conformité', ARRAY['customers'], ARRAY[]::TEXT[], '%', 'hebdomadaire'),
('aml_alert_rate', 'Taux d''alertes AML', 'AML Alert Rate', 'COUNT(aml_alerts) / COUNT(DISTINCT customer_id) * 1000', 'Nombre d''alertes AML générées pour 1000 clients.', 'compliance', 'Conformité', ARRAY['aml_alerts','customers'], ARRAY[]::TEXT[], 'alertes/1k_clients', 'hebdomadaire'),
('customer_growth_rate', 'Taux de croissance clientèle MoM', 'Customer Growth Rate MoM', '(current_month - prior_month) / prior_month * 100', 'Taux d''évolution mensuel du nombre de clients.', 'customer', 'Commercial', ARRAY['customers'], ARRAY[]::TEXT[], '%', 'mensuel'),
('deposit_growth_rate', 'Taux de croissance des dépôts', 'Deposit Growth Rate', '(current_balance - prior_balance) / prior_balance * 100', 'Taux de croissance des encours de dépôt.', 'account', 'Commercial', ARRAY['account_balances'], ARRAY[]::TEXT[], '%', 'mensuel'),
('avg_loan_size', 'Taille moyenne des crédits', 'Average Loan Size', 'AVG(principal_amount)', 'Montant moyen accordé par contrat de crédit.', 'loan', 'Crédits', ARRAY['loan_contracts'], ARRAY[]::TEXT[], 'TND', 'mensuel'),
('default_rate', 'Taux de défaut', 'Default Rate', 'COUNT(CASE WHEN status = ''contentieux'' THEN 1 END) / COUNT(*) * 100', 'Ratio des contrats en contentieux sur le total.', 'loan', 'Risques', ARRAY['loan_contracts'], ARRAY[]::TEXT[], '%', 'mensuel'),
('avg_days_past_due', 'Retard moyen de paiement', 'Average Days Past Due', 'AVG(days_past_due) WHERE days_past_due > 0', 'Nombre moyen de jours de retard sur les échéances impayées.', 'loan', 'Risques', ARRAY['loan_contracts'], ARRAY[]::TEXT[], 'jours', 'mensuel'),
('total_risk_exposure', 'Exposition totale aux risques', 'Total Risk Exposure', 'COUNT(*) WHERE risk_level IN (''high'', ''critical'')', 'Nombre de signaux de risque élevé ou critique actifs.', 'risk', 'Risques', ARRAY['risk_flags'], ARRAY[]::TEXT[], 'signaux', 'mensuel'),
('branch_profitability', 'Rentabilité par agence', 'Branch Profitability', 'SUM(fee_income + interest_income) - SUM(operating_expenses) GROUP BY branch_id', 'Bénéfice opérationnel net par agence.', 'organization', 'Réseau de Détail', ARRAY['fee_income','interest_income','operating_expenses'], ARRAY[]::TEXT[], 'TND', 'mensuel'),
('active_loan_portfolio', 'Portefeuille crédits actif', 'Active Loan Portfolio', 'SUM(outstanding_balance) WHERE status = ''actif''', 'Encours total des crédits en cours de remboursement.', 'loan', 'Crédits', ARRAY['loan_contracts'], ARRAY[]::TEXT[], 'TND', 'mensuel'),
('overdue_loans', 'Crédits en retard', 'Overdue Loans', 'COUNT(*) WHERE days_past_due BETWEEN 1 AND 90', 'Nombre de prêts ayant un retard de paiement inférieur ou égal à 90 jours.', 'loan', 'Risques', ARRAY['loan_contracts'], ARRAY[]::TEXT[], 'prêts', 'mensuel'),
('pep_customer_rate', '% Clients PEP', 'PEP Customer Rate', 'COUNT(CASE WHEN politically_exposed THEN 1 END) / COUNT(*) * 100', 'Pourcentage de clients identifiés comme personnes politiquement exposées.', 'kyc', 'Conformité', ARRAY['customer_profiles'], ARRAY[]::TEXT[], '%', 'mensuel'),
('pending_kyc_cases', 'Dossiers KYC en attente', 'Pending KYC Cases', 'COUNT(*) WHERE status IN (''ouvert'',''en_cours'')', 'Nombre de dossiers KYC non encore finalisés.', 'kyc', 'Conformité', ARRAY['kyc_cases'], ARRAY[]::TEXT[], 'dossiers', 'quotidien'),
('open_aml_alerts', 'Alertes AML ouvertes', 'Open AML Alerts', 'COUNT(*) WHERE status = ''ouvert''', 'Nombre d''alertes de blanchiment en attente d''analyse.', 'compliance', 'Conformité', ARRAY['aml_alerts'], ARRAY[]::TEXT[], 'alertes', 'quotidien'),
('transaction_volume_30d', 'Volume de transactions 30j', 'Transaction Volume 30d', 'COUNT(*) WHERE transaction_date >= NOW() - INTERVAL ''30 days''', 'Nombre total de transactions effectuées au cours des 30 derniers jours.', 'payment', 'Opérations', ARRAY['transactions'], ARRAY[]::TEXT[], 'transactions', 'quotidien'),
('avg_transaction_value', 'Montant moyen transaction', 'Average Transaction Value', 'AVG(ABS(amount))', 'Valeur moyenne des flux financiers par transaction.', 'payment', 'Opérations', ARRAY['transactions'], ARRAY[]::TEXT[], 'TND', 'mensuel'),
('income_per_customer', 'PNB par client', 'Income per Customer', 'SUM(fee_income + interest_income) / COUNT(DISTINCT customer_id)', 'Revenu net bancaire moyen par client.', 'finance', 'Commercial', ARRAY['fee_income','interest_income','customers'], ARRAY[]::TEXT[], 'TND/client', 'mensuel'),
('collateral_coverage', 'Couverture collatérale', 'Collateral Coverage', 'SUM(collateral_value) / SUM(outstanding_balance) * 100', 'Rapport entre la valeur des garanties réelles et l''encours de prêt.', 'loan', 'Risques', ARRAY['collateral','loan_contracts'], ARRAY[]::TEXT[], '%', 'mensuel'),
('restructured_loan_rate', 'Taux de prêts restructurés', 'Restructured Loan Rate', 'COUNT(DISTINCT loan_id) / COUNT(*) * 100', 'Proportion de prêts ayant subi une modification contractuelle pour restructuration.', 'loan', 'Risques', ARRAY['loan_restructuring','loan_contracts'], ARRAY[]::TEXT[], '%', 'mensuel')
ON CONFLICT (metric_id) DO UPDATE SET source_tables = EXCLUDED.source_tables, formula = EXCLUDED.formula, description = EXCLUDED.description;

-- ==========================================
-- 3. SEED TABLE METADATA (All 96 tables placeholder / key tables seeded)
-- ==========================================
INSERT INTO table_metadata (table_name, business_description, domain, owner, row_count_estimate, is_analytical, is_pii_bearing, refresh_frequency) VALUES
('customers', 'Registre principal des clients de la banque', 'customer', 'Réseau de Détail', 2000, FALSE, TRUE, 'temps réel'),
('accounts', 'Comptes bancaires des clients de la banque', 'account', 'Réseau de Détail', 5000, FALSE, FALSE, 'temps réel'),
('transactions', 'Mouvements financiers sur les comptes clients', 'payment', 'Opérations', 50000, FALSE, FALSE, 'temps réel'),
('branches', 'Liste des succursales et agences physiques', 'organization', 'Réseau de Détail', 30, FALSE, FALSE, 'statique'),
('products', 'Catalogue général des produits bancaires', 'product', 'Marketing', 20, FALSE, FALSE, 'statique'),
('risk_flags', 'Signalements de risques sur les clients', 'risk', 'Risques', 100, FALSE, FALSE, 'temps réel'),
('loan_contracts', 'Contrats de crédit accordés aux clients', 'loan', 'Crédits', 1500, FALSE, FALSE, 'temps réel'),
('loan_products', 'Types de produits de crédit proposés', 'loan', 'Marketing', 10, FALSE, FALSE, 'statique'),
('loan_installments', 'Échéancier détaillé des prêts', 'loan', 'Crédits', 36000, FALSE, FALSE, 'temps réel'),
('loan_repayments', 'Remboursements de crédits encaissés', 'loan', 'Crédits', 30000, FALSE, FALSE, 'temps réel'),
('loan_delinquency_events', 'Historique des incidents de paiement de prêts', 'loan', 'Risques', 500, FALSE, FALSE, 'temps réel'),
('loan_restructuring', 'Demandes et contrats de restructuration de prêt', 'loan', 'Risques', 100, FALSE, FALSE, 'temps réel'),
('collateral', 'Garanties réelles associées aux crédits', 'loan', 'Risques', 1000, FALSE, FALSE, 'temps réel'),
('guarantees', 'Cautions personnelles associées aux crédits', 'loan', 'Risques', 500, FALSE, FALSE, 'temps réel'),
('provisions', 'Dotations aux provisions par contrat', 'loan', 'Risques', 1500, TRUE, FALSE, 'mensuel'),
('non_performing_loans', 'Créances compromises et dossiers contentieux', 'loan', 'Risques', 200, TRUE, FALSE, 'mensuel'),
('kyc_cases', 'Dossiers de vérification d''identité', 'kyc', 'Conformité', 2000, FALSE, TRUE, 'temps réel'),
('kyc_documents', 'Pièces justificatives d''identité attachées aux dossiers', 'kyc', 'Conformité', 4000, FALSE, TRUE, 'temps réel'),
('kyc_reviews', 'Historique des décisions KYC par analyste', 'kyc', 'Conformité', 2200, FALSE, TRUE, 'temps réel'),
('kyc_verifications', 'Contrôles individuels effectués par dossier KYC', 'kyc', 'Conformité', 8000, FALSE, TRUE, 'temps réel'),
('kyc_expirations', 'Alertes d''échéance des pièces KYC', 'kyc', 'Conformité', 300, FALSE, TRUE, 'temps réel'),
('pep_screening', 'Screening des personnes politiquement exposées', 'kyc', 'Conformité', 100, FALSE, TRUE, 'temps réel'),
('sanctions_screening', 'Screening des listes de sanctions internationales', 'kyc', 'Conformité', 2000, FALSE, TRUE, 'temps réel'),
('aml_alerts', 'Alertes de blanchiment générées par le moteur transactionnel', 'compliance', 'Conformité', 500, FALSE, FALSE, 'temps réel'),
('suspicious_activity_reports', 'Déclarations de soupçon (DSFR) destinées à la CTAF', 'compliance', 'Conformité', 50, FALSE, TRUE, 'temps réel'),
('compliance_cases', 'Enquêtes et dossiers de conformité ouverts', 'compliance', 'Conformité', 100, FALSE, TRUE, 'temps réel'),
('compliance_reviews', 'Audits de conformité par dossier', 'compliance', 'Conformité', 150, FALSE, TRUE, 'temps réel'),
('audit_findings', 'Constats d''audit à résoudre', 'compliance', 'Audit Interne', 50, FALSE, FALSE, 'périodique'),
('general_ledger', 'Plan comptable et balances générales', 'finance', 'Finance', 200, FALSE, FALSE, 'statique'),
('ledger_entries', 'Écritures comptables générées', 'finance', 'Finance', 100000, FALSE, FALSE, 'temps réel'),
('fee_income', 'Commissions perçues sur comptes et services', 'finance', 'Finance', 25000, FALSE, FALSE, 'temps réel'),
('interest_income', 'Intérêts perçus sur les crédits', 'finance', 'Finance', 15000, FALSE, FALSE, 'temps réel'),
('operating_expenses', 'Charges d''exploitation comptabilisées', 'finance', 'Finance', 2000, FALSE, FALSE, 'temps réel'),
('profitability_metrics', 'Indicateurs de rentabilité calculés', 'finance', 'Finance', 500, TRUE, FALSE, 'mensuel'),
('balance_sheet_snapshots', 'Bilans mensuels de la banque', 'finance', 'Finance', 24, TRUE, FALSE, 'mensuel'),
('income_statement_snapshots', 'Comptes de résultat mensuels', 'finance', 'Finance', 24, TRUE, FALSE, 'mensuel'),
('regions', 'Découpage régional des agences', 'organization', 'Réseau de Détail', 6, FALSE, FALSE, 'statique'),
('departments', 'Départements fonctionnels de la banque', 'organization', 'Réseau de Détail', 10, FALSE, FALSE, 'statique'),
('business_units', 'Unités commerciales de la banque', 'organization', 'Réseau de Détail', 5, FALSE, FALSE, 'statique'),
('employees', 'Registre du personnel de la banque', 'organization', 'Ressources Humaines', 150, FALSE, FALSE, 'temps réel'),
('relationship_managers', 'Affectation des portefeuilles clients aux chargés', 'organization', 'Réseau de Détail', 100, FALSE, FALSE, 'temps réel'),
('customer_profiles', 'Données démographiques et revenus des clients', 'customer', 'Réseau de Détail', 2000, FALSE, TRUE, 'temps réel'),
('customer_addresses', 'Adresses physiques des clients', 'customer', 'Réseau de Détail', 2200, FALSE, TRUE, 'temps réel'),
('customer_contacts', 'Coordonnées téléphoniques et e-mails', 'customer', 'Réseau de Détail', 3000, FALSE, TRUE, 'temps réel'),
('customer_risk_scores', 'Historique des scores de risques par client', 'risk', 'Risques', 5000, TRUE, FALSE, 'mensuel'),
('customer_relationships', 'Liens familiaux et de garanties entre clients', 'customer', 'Réseau de Détail', 500, FALSE, TRUE, 'temps réel'),
('customer_documents', 'Fichiers justificatifs scannés', 'customer', 'Réseau de Détail', 4000, FALSE, TRUE, 'temps réel'),
('customer_preferences', 'Préférences de communication et alertes', 'customer', 'Réseau de Détail', 2000, FALSE, TRUE, 'temps réel'),
('customer_status_history', 'Historique de changement de statut client', 'customer', 'Réseau de Détail', 100, FALSE, TRUE, 'temps réel'),
('account_types', 'Grille de paramétrage des types de compte', 'account', 'Marketing', 5, FALSE, FALSE, 'statique'),
('account_balances', 'Historique quotidien des soldes de comptes', 'account', 'Réseau de Détail', 120000, TRUE, FALSE, 'quotidien'),
('account_status_history', 'Historique des statuts de compte', 'account', 'Réseau de Détail', 200, FALSE, FALSE, 'temps réel'),
('joint_accounts', 'Comptes joints multidépositaires', 'account', 'Réseau de Détail', 200, FALSE, TRUE, 'temps réel'),
('account_signatories', 'Mandataires et signataires autorisés', 'account', 'Réseau de Détail', 300, FALSE, TRUE, 'temps réel')
ON CONFLICT (table_name) DO NOTHING;

-- ==========================================
-- 4. SEED COLUMN METADATA
-- ==========================================
INSERT INTO column_metadata (table_name, column_name, business_description, synonyms, data_type, is_pii, example_values) VALUES
('loan_contracts', 'outstanding_balance', 'Montant restant dû sur le crédit', ARRAY['encours','capital restant dû','solde crédit','solde du prêt'], 'DECIMAL(15,2)', FALSE, ARRAY['52400.12','1205.50']),
('loan_contracts', 'days_past_due', 'Nombre de jours de retard de paiement', ARRAY['DPD','retard','impayé jours','jours de retard'], 'INTEGER', FALSE, ARRAY['0','45','95']),
('loan_contracts', 'status', 'Statut du crédit (actif/en_retard/contentieux/remboursé)', ARRAY['état crédit','statut crédit','status prêt'], 'VARCHAR(30)', FALSE, ARRAY['actif','en_retard','contentieux']),
('customers', 'risk_score', 'Score de risque global du client (0-1)', ARRAY['score risk','note de risque','rating risk'], 'DECIMAL(3,2)', FALSE, ARRAY['0.12','0.85']),
('customers', 'kyc_verified', 'Statut de vérification KYC du client', ARRAY['vérifié','KYC status','statut KYC'], 'BOOLEAN', FALSE, ARRAY['true','false']),
('aml_alerts', 'severity', 'Niveau de sévérité de l''alerte compliance', ARRAY['criticité','niveau alerte','sévérité alerte'], 'VARCHAR(20)', FALSE, ARRAY['faible','moyen','élevé','critique']),
('accounts', 'balance', 'Solde actuel du compte client', ARRAY['solde','avoirs','solde compte','balance'], 'DECIMAL(15,2)', FALSE, ARRAY['1500.45','-120.00']),
('customer_profiles', 'politically_exposed', 'Indicateur PEP (personne politiquement exposée)', ARRAY['PEP flag','pep_status','politiquement exposé'], 'BOOLEAN', FALSE, ARRAY['true','false']),
('transactions', 'amount', 'Montant brut de la transaction', ARRAY['montant','valeur','somme','montant transaction'], 'DECIMAL(15,2)', FALSE, ARRAY['150.00','-45.50']),
('non_performing_loans', 'classification', 'Classe de risque BCT pour créances classées', ARRAY['classe BCT','classification BCT','classement créance'], 'VARCHAR(50)', FALSE, ARRAY['pré-douteux','douteux','compromis'])
ON CONFLICT (table_name, column_name) DO NOTHING;

-- ==========================================
-- 5. SEED JOIN REGISTRY
-- ==========================================
INSERT INTO join_registry (source_table, source_column, target_table, target_column, relationship_type, join_type, confidence, notes) VALUES
('customers', 'customer_id', 'accounts', 'customer_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Jointure naturelle entre client et comptes'),
('customers', 'customer_id', 'loan_contracts', 'customer_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Jointure naturelle entre client et prêts'),
('customers', 'customer_id', 'transactions', 'customer_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Jointure naturelle entre client et transactions'),
('customers', 'customer_id', 'risk_flags', 'customer_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Lien client et historique des drapeaux risques'),
('customers', 'customer_id', 'kyc_cases', 'customer_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Lien client et dossiers KYC'),
('customers', 'customer_id', 'aml_alerts', 'customer_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Lien client et alertes AML'),
('customers', 'customer_id', 'customer_profiles', 'customer_id', 'one_to_one', 'LEFT JOIN', 1.00, 'Extension profil démographique du client'),
('accounts', 'account_id', 'transactions', 'account_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Mouvements d''un compte bancaire'),
('accounts', 'account_id', 'loan_contracts', 'account_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Lien compte de prélèvement du crédit'),
('accounts', 'branch_id', 'branches', 'branch_id', 'many_to_one', 'LEFT JOIN', 1.00, 'Rattachement d''un compte à son agence'),
('loan_contracts', 'loan_id', 'loan_installments', 'loan_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Échéances de remboursement d''un crédit'),
('loan_contracts', 'loan_id', 'loan_repayments', 'loan_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Paiements effectués pour un crédit'),
('loan_contracts', 'loan_id', 'loan_delinquency_events', 'loan_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Incidents de remboursement sur un prêt'),
('loan_contracts', 'loan_id', 'collateral', 'loan_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Garanties réelles affectées à un prêt'),
('loan_contracts', 'loan_id', 'provisions', 'loan_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Provisions d''un prêt'),
('loan_contracts', 'loan_id', 'non_performing_loans', 'loan_id', 'one_to_one', 'LEFT JOIN', 1.00, 'Lien si créance compromise'),
('transactions', 'transaction_id', 'aml_alerts', 'transaction_id', 'one_to_many', 'LEFT JOIN', 0.90, 'Lien alerte AML déclenchée par transaction'),
('branches', 'branch_id', 'employees', 'branch_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Personnel d''une agence'),
('branches', 'region_id', 'regions', 'region_id', 'many_to_one', 'LEFT JOIN', 1.00, 'Région administrative d''une agence'),
('kyc_cases', 'kyc_case_id', 'kyc_reviews', 'kyc_case_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Décisions de revue KYC d''un dossier'),
('kyc_cases', 'kyc_case_id', 'kyc_documents', 'kyc_case_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Documents du dossier KYC'),
('kyc_cases', 'kyc_case_id', 'kyc_verifications', 'kyc_case_id', 'one_to_many', 'LEFT JOIN', 1.00, 'Contrôles unitaires KYC'),
('aml_alerts', 'alert_id', 'suspicious_activity_reports', 'alert_id', 'one_to_one', 'LEFT JOIN', 1.00, 'Déclaration DSFR pour alerte confirmée'),
('general_ledger', 'account_code', 'ledger_entries', 'account_code', 'one_to_many', 'LEFT JOIN', 1.00, 'Écritures comptables par compte de la balance')
ON CONFLICT (source_table, source_column, target_table, target_column) DO NOTHING;
