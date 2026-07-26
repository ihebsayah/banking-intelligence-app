# Database Inventory

> **Source of truth**: VERIFIED SQL init scripts
> **Last verified**: 2026-07-26

---

## Database 1: banking_dev (Main)

**Engine**: PostgreSQL 16-alpine (`docker-compose.yml:482`)
**Tables from SQL scripts**: 74

### postgres-main-init.sql (10 tables)

| Table | Key Columns |
|-------|------------|
| customers | customer_id, name, email, phone, kyc_verified, risk_score, segment |
| accounts | account_id, customer_id (FK), account_type, status, balance, branch_id |
| transactions | transaction_id, account_id (FK), customer_id (FK), amount, transaction_type, status |
| risk_flags | customer_id (FK), flag_type, severity, resolved |
| branches | branch_id, name, state, city, manager_id |
| products | product_id, name, category |
| compliance_rules | rule_name, regulation, rule_type, condition, action, enabled |
| data_lineage | query_id, source_table, source_column, user_id |
| compliance_violations | query_id, user_id, violation_type, severity, regulation, status |
| regulatory_reports | report_type, regulation, report_content, status |

### 02-users-kpis.sql (10 tables)

| Table | Key Columns |
|-------|------------|
| roles | role_id, label, description |
| permissions | permission_key, label, category |
| role_permissions | role_id (FK), permission_key (FK) |
| users | user_id, email, role (FK), password_hash, permissions[], status |
| user_activity_log | actor_id, target_id, action, detail (JSONB) |
| kpi_categories | category_id, name |
| kpi_owners | owner_id, name, email |
| kpi_definitions | kpi_id, name, metric_type, category, formula, status |
| kpi_thresholds | kpi_id (FK), healthy_min/max, warning_min/max, critical_min/max |
| kpi_history | kpi_id (FK), changed_by, change_type, old_value, new_value |

### 03-semantic-layer.sql (5 tables)

| Table | Key Columns |
|-------|------------|
| business_glossary | term, definition, domain |
| metric_registry | name, formula, domain |
| table_metadata | table_name, description, domain |
| join_registry | source_table, target_table, join_condition |
| term_embeddings | term, embedding (vector(1024)) |

### 04-loan-domain.sql (10 tables)

| Table | Key Columns |
|-------|------------|
| loan_products | name, interest_rate, term_months |
| loan_contracts | customer_id, product_id, amount, status |
| non_performing_loans | contract_id, npl_status |
| loan_repayments | contract_id, amount, due_date, paid_date |
| loan_installments | contract_id, installment_number, amount |
| loan_delinquency_events | contract_id, days_past_due |
| loan_restructuring | contract_id, restructured_amount |
| collateral | contract_id, collateral_type, value |
| guarantees | contract_id, guarantor_id |
| provisions | contract_id, provision_amount |

### 05-kyc-aml-domain.sql (12 tables)

| Table | Key Columns |
|-------|------------|
| kyc_cases | customer_id, status, assigned_to |
| kyc_documents | case_id, doc_type, file_path |
| kyc_review | case_id, reviewer_id, decision |
| aml_transactions | transaction_id, risk_score, flagged_reason |
| aml_watchlist | name, list_type, country |
| sanctions_screening | customer_id, match_score, status |
| regulatory_reports_kyc | (reporting table) |
| customer_due_diligence | customer_id, risk_level |
| enhanced_due_diligence | customer_id, edd_status |
| pep_check | customer_id, pep_status |
| beneficial_ownership | customer_id, ownership_pct |
| transaction_monitoring | transaction_id, monitoring_status |

### 06-finance-gl-domain.sql (8 tables)

| Table | Key Columns |
|-------|------------|
| general_ledger | account_code, account_name, account_type |
| ledger_entries | gl_id, debit, credit, entry_date |
| fee_income | fee_type, amount, recorded_date |
| income_statement_snapshots | period, revenue, expenses, net_income |
| balance_sheet_snapshots | period, assets, liabilities, equity |
| interest_income | account_id, interest_amount |
| operating_expenses | expense_type, amount |
| profitability_metrics | period, metric_name, metric_value |

### 07-org-customer-ext.sql (19 tables)

| Table | Key Columns |
|-------|------------|
| regions | name, code |
| departments | name, region_id |
| business_units | name, department_id |
| employees | name, role, branch_id |
| customer_interactions | customer_id, type, notes |
| customer_segments | name, criteria |
| relationship_managers | name, email |
| data_lineage_ext | (extension tables) |
| + 11 more extension tables | |

---

## Database 2: audit_logs

**Engine**: PostgreSQL 16-alpine
**Tables**: 1

| Table | Key Columns |
|-------|------------|
| audit_log | id, audit_id (UNIQUE), timestamp, user_id, user_role, action, status, metadata (JSONB) |

**Immutability**: RULE protection (no UPDATE, no DELETE). INSERT + SELECT only.
**Source**: `postgres-audit-init.sql`

---

## Database 3: embeddings

**Engine**: pgvector/pgvector:pg16
**Tables**: 3

| Table | Key Columns |
|-------|------------|
| schema_embeddings | entity_type, entity_name, embedding (vector(384)) |
| domain_categories | domain_name, tables (TEXT[]) |
| semantic_id_mappings | semantic_entity, table_name, column_name, confidence |

**Source**: `postgres-embeddings-init.sql`

---

## Table Count Summary

| Database   | Tables |
|------------|--------|
| banking_dev | 74     |
| audit_logs  | 1      |
| embeddings  | 3      |
| **TOTAL**   | **78** |

---

## Seed Data

- **postgres-main-init.sql**: 5 branches, 5 customers, 5 accounts, 5 transactions, 3 risk_flags, 5 products + 200 Tunisia branches/customers/accounts/transactions/risk_flags/products
- **02-users-kpis.sql**: 4 roles, 11 permissions, 17 role_permissions, 5 users, 6 KPI categories, 6 KPI owners, 20 KPI definitions, 11 KPI thresholds
- **08-semantic-layer-seed.sql**: business_glossary, metric_registry, table_metadata, join_registry seed data
- **09-tunisian-banking-data-seed.sql**: Additional Tunisia banking data
