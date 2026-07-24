# Database Architecture Report

**Date:** 2026-07-23  
**System:** Banking Intelligence System

---

## Overview

The system runs **4 data stores**: 3 PostgreSQL databases + 1 Redis instance, all containerized via Docker.

| Database | Type | Port | Container | Purpose |
|----------|------|------|-----------|---------|
| `banking_dev` | PostgreSQL 16 | 5432 | `banking_postgres_main` | Core banking data |
| `audit_logs` | PostgreSQL 16 | 5433 | `banking_postgres_audit` | Immutable audit trail |
| `embeddings` | PostgreSQL 16 + pgvector | 5434 | `banking_postgres_embeddings` | Vector similarity search |
| *(Redis)* | Redis 7 | 6379 | `banking_redis` | Caching (6+ logical DBs) |

---

## Database 1: `banking_dev` — Main Banking Database (~70 tables)

**Connection:** `postgresql://banking_user:securepass123@postgres-main:5432/banking_dev`  
**Init scripts:** 11 SQL files loaded in order at first startup.

### Domain Breakdown

#### Core Banking (6 tables)
| Table | Key Columns | Notes |
|-------|-------------|-------|
| `customers` | id (UUID), customer_id, name, email, phone, kyc_verified, risk_score, segment | Core entity |
| `accounts` | id (UUID), account_id, customer_id (FK), account_type, status, balance, branch_id (FK) | Core entity |
| `transactions` | id (UUID), transaction_id, account_id (FK), customer_id (FK), amount, transaction_type, status | Core entity |
| `risk_flags` | id (UUID), customer_id (FK), flag_type, severity, resolved | Risk management |
| `branches` | id (UUID), branch_id, name, state, city, region_id (FK) | Organization |
| `products` | id (UUID), product_id, name, category | Product catalog |

#### Users, Roles & KPIs (10 tables)
| Table | Key Columns | Notes |
|-------|-------------|-------|
| `roles` | role_id, label | RBAC |
| `permissions` | permission_key, label, category | 11 permissions (read/admin/write) |
| `role_permissions` | role_id (FK), permission_key (FK) | Junction table |
| `users` | user_id, email (UNIQUE), name, role (FK), password_hash, permissions (TEXT[]) | 5 seeded users |
| `user_activity_log` | id (BIGSERIAL), actor_id, action, detail (JSONB) | Audit trail |
| `kpi_categories` | category_id, name | 6 categories |
| `kpi_owners` | owner_id, name, email, role | 6 owners |
| `kpi_definitions` | kpi_id, name, formula, category, source_tables (TEXT[]) | 20 KPI definitions |
| `kpi_thresholds` | kpi_id (PK/FK), healthy/warning/critical min/max/labels | 11 thresholds |
| `kpi_history` | history_id, kpi_id (FK), old_value (JSONB), new_value (JSONB) | KPI audit |

#### Semantic Layer (5 tables)
| Table | Key Columns | Notes |
|-------|-------------|-------|
| `business_glossary` | term_id (UUID), term (UNIQUE), definition, synonyms (TEXT[]), domain | 38 glossary terms |
| `metric_registry` | metric_id, metric_name_fr/en, formula, source_tables (TEXT[]) | 25 metric definitions |
| `table_metadata` | table_name (PK), business_description, domain, row_count_estimate | 54 table docs |
| `column_metadata` | metadata_id (UUID), table_name, column_name, synonyms (TEXT[]), is_pii | 11 column entries |
| `join_registry` | source_table/column, target_table/column, relationship_type, confidence | 25 join definitions |

#### Loan Domain (10 tables)
| Table | Key Columns | Notes |
|-------|-------------|-------|
| `loan_products` | loan_product_id, name, min/max_amount, min/max_interest_rate | 4 loan products |
| `loan_contracts` | loan_id, customer_id (FK), account_id (FK), principal_amount, interest_rate, status | Core loan entity |
| `loan_installments` | installment_id (UUID), loan_id (FK), due_date, total_amount, status | Repayment schedule |
| `loan_repayments` | repayment_id (UUID), loan_id (FK), amount, repayment_date | Payment records |
| `loan_delinquency_events` | event_id (UUID), loan_id (FK), days_past_due, resolved | Delinquency tracking |
| `loan_restructuring` | restructuring_id (UUID), loan_id (FK), previous/new principal/rate/term | Restructuring records |
| `collateral` | collateral_id, loan_id (FK), collateral_type, estimated_value | Collateral tracking |
| `guarantees` | guarantee_id, loan_id (FK), guarantor_name, guarantee_amount | Guarantee records |
| `provisions` | provision_id (UUID), loan_id (FK), provision_amount, calculation_model | Provisioning |
| `non_performing_loans` | npl_id (UUID), loan_id (FK UNIQUE), npl_amount, classification | NPL tracking |

#### KYC/AML/Compliance (11 tables)
| Table | Key Columns | Notes |
|-------|-------------|-------|
| `kyc_cases` | kyc_case_id, customer_id (FK), case_type, status, risk_level | KYC management |
| `kyc_documents` | kyc_doc_id (UUID), kyc_case_id (FK), document_type, verified | KYC documents |
| `kyc_reviews` | review_id (UUID), kyc_case_id (FK), decision, comments | KYC reviews |
| `kyc_verifications` | verification_id (UUID), kyc_case_id (FK), verification_type, status | Verification steps |
| `kyc_expirations` | expiration_id (UUID), customer_id (FK), expiry_date, review_required | Expiration alerts |
| `pep_screening` | screening_id (UUID), customer_id (FK), matched_name, match_score, status | PEP screening |
| `sanctions_screening` | screening_id (UUID), customer_id (FK), matched_name, sanctions_list, status | Sanctions screening |
| `aml_alerts` | alert_id, customer_id (FK), alert_type, severity, score, status | AML alerts |
| `suspicious_activity_reports` | sar_id, alert_id (FK), report_date, status, ctaf_reference | SAR/DSFR |
| `compliance_cases` | compliance_case_id, customer_id (FK), case_type, severity, status | Investigations |
| `compliance_reviews` | review_id (UUID), compliance_case_id (FK), findings, action_plan | Reviews |
| `audit_findings` | finding_id, title, severity, status, target_resolution_date | Audit tracking |

#### Finance/GL Domain (8 tables)
| Table | Key Columns | Notes |
|-------|-------------|-------|
| `general_ledger` | ledger_id (UUID), account_code (UNIQUE), account_name_fr, account_type | Chart of accounts |
| `ledger_entries` | entry_id (UUID), account_code (FK), debit_amount, credit_amount, value_date | Journal entries |
| `fee_income` | fee_income_id (UUID), customer_id (FK), fee_type, amount | Fee revenue |
| `interest_income` | interest_income_id (UUID), loan_id (FK), amount | Interest revenue |
| `operating_expenses` | expense_id (UUID), expense_type, amount, branch_id | Expense tracking |
| `profitability_metrics` | metric_id (UUID), branch_id, pnb, net_income, cost_to_income_ratio | Profitability analytics |
| `balance_sheet_snapshots` | snapshot_id (UUID), period, total_assets, total_liabilities, total_equity | Balance sheet history |
| `income_statement_snapshots` | snapshot_id (UUID), period, interest_income, pnb, net_income | P&L history |

#### Org/Customer Extensions (20 tables)
| Table | Key Columns | Notes |
|-------|-------------|-------|
| `regions` | region_id, region_name_fr, governorates (TEXT[]) | Geography |
| `departments` | department_id, name_fr/en | Org structure |
| `business_units` | unit_id, name_fr/en | Org structure |
| `employees` | employee_id, branch_id (FK), department_id (FK), title, role, hire_date | 100 employees seeded |
| `relationship_managers` | rm_id (UUID), employee_id (FK), customer_id (FK UNIQUE) | RM assignment |
| `customer_profiles` | profile_id (UUID), customer_id (FK UNIQUE), dob, gender, nationality, annual_income | Extended customer data |
| `customer_segments` | segment_id, segment_name, min_balance, min_annual_income | 4 segments |
| `customer_addresses` | address_id (UUID), customer_id (FK), city, governorate, country | Addresses |
| `customer_contacts` | contact_id (UUID), customer_id (FK), contact_type, contact_value | Contacts |
| `customer_risk_scores` | score_id (UUID), customer_id (FK), score (DECIMAL 5,4), factors (JSONB) | Risk scoring history |
| `customer_relationships` | relationship_id (UUID), customer_id (FK), related_customer_id (FK) | Inter-customer links |
| `customer_documents` | document_id (UUID), customer_id (FK), document_type, verified | Documents |
| `customer_preferences` | preference_id (UUID), customer_id (FK UNIQUE), language, contact_channel | Communication prefs |
| `customer_status_history` | history_id (UUID), customer_id (FK), previous/new_status | Status audit |
| `account_types` | type_code (PK), type_name_fr/en, interest_rate | Account type config |
| `account_balances` | balance_id (UUID), account_id (FK), balance, snapshot_date | Balance snapshots |
| `account_status_history` | history_id (UUID), account_id (FK), previous/new_status | Status audit |
| `joint_accounts` | joint_id (UUID), account_id (FK), customer_id (FK) | Multi-holder accounts |
| `account_signatories` | signatory_id (UUID), account_id (FK), customer_id (FK), signatory_role | Authorized signatories |

#### Compliance Rules & Lineage (4 tables)
| Table | Key Columns | Notes |
|-------|-------------|-------|
| `compliance_rules` | id (UUID), rule_name, regulation, condition, action, enabled | 12 rules (GDPR, PCI-DSS, SOX, AML, KYC) |
| `data_lineage` | id (UUID), query_id, source_table, user_id | Data lineage tracking |
| `compliance_violations` | id (UUID), violation_type, severity, regulation | Violation tracking |
| `regulatory_reports` | id (UUID), report_type, regulation, report_period | Regulatory reporting |

### Seeded Data Summary

| Seed Source | Records |
|-------------|---------|
| `postgres-main-init.sql` | 5 US + 200 Tunisia branches, customers, accounts, transactions, risk flags, products + 12 compliance rules |
| `02-users-kpis.sql` | 4 roles, 11 permissions, 5 users, 20 KPI definitions, 11 thresholds |
| `08-semantic-layer-seed.sql` | 38 glossary terms, 25 metrics, 54 table docs, 11 column entries, 25 joins |
| `09-tunisian-banking-data-seed.sql` | 5 regions, 30 branches, 5 products, 4 segments, 100 employees, 100+ customers, loans, transactions, compliance data |

---

## Database 2: `audit_logs` — Immutable Audit Trail (1 table)

**Connection:** `postgresql://audit_user:securepass123@postgres-audit:5432/audit_logs`

| Table | Key Columns | Notes |
|-------|-------------|-------|
| `audit_log` | id (UUID), audit_id (UNIQUE), timestamp, user_id, action, query_intent, tables_accessed, rows_accessed, status | Immutability enforced via PostgreSQL RULEs (no UPDATE/DELETE allowed) |

**No seed data** — purely runtime, written to by all services via the Audit Agent.

---

## Database 3: `embeddings` — Vector Database (3 tables)

**Connection:** `postgresql://embedding_user:securepass123@postgres-embeddings:5432/embeddings`  
**Image:** `pgvector/pgvector:pg16` (vector extension enabled)

| Table | Key Columns | Notes |
|-------|-------------|-------|
| `schema_embeddings` | id (UUID), entity_type, entity_name, embedding (vector 384) | IVFFlat index, cosine similarity |
| `domain_categories` | id (UUID), domain_name (UNIQUE), tables (TEXT[]), embedding (vector 384) | 8 domains seeded |
| `semantic_id_mappings` | id (UUID), semantic_entity, table_name, column_name, confidence | 9 mappings seeded |

---

## Database 4: Redis — Caching Layer

**Connection:** `redis://redis:6379`  
**Persistence:** AOF enabled

| DB# | Used By | TTL |
|-----|---------|-----|
| 0 | API Gateway | Session: 8hr |
| 1 | Orchestrator Agent | — |
| 2 | Schema Agent | 24hr |
| 3 | Entity Resolution Agent | — |
| 4 | SQL Agent | — |
| 5 | Execution Agent | Query cache: 1hr |

---

## Service → Database Mapping

| Service | Port | `banking_dev` | `audit_logs` | `embeddings` | Redis |
|---------|------|:---:|:---:|:---:|:---:|
| api-gateway | 8000 | R/W | W (audit) | — | 0 |
| orchestrator-agent | 8001 | R | — | — | 1 |
| intent-agent | 8002 | R | — | — | * |
| schema-agent | 8003 | — | — | — | 2 |
| entity-resolution-agent | 8004 | — | — | R/W | 3 |
| sql-agent | 8005 | — | — | — | 4 |
| validation-agent | 8006 | — | — | — | — |
| execution-agent | 8007 | R | — | — | 5 |
| audit-agent | 8008 | — | R/W | — | — |
| embedding-service | 8009 | — | — | R/W | — |
| compliance-agent | 8011 | R | — | — | — |
| audit-enhancement | 8012 | R | R | — | — |
| insights-agent | 8013 | R | — | — | — |

---

## Statistics

| Metric | Count |
|--------|-------|
| PostgreSQL databases | 3 |
| Total tables (`banking_dev`) | ~70 |
| Total tables (all PostgreSQL) | ~74 |
| Redis logical databases | 6+ |
| SQL init files | 11 |
| Foreign key relationships | 50+ |
| Semantic layer entries | 38 glossary, 25 metrics, 54 table docs, 25 joins |
| Compliance rules | 12 (GDPR, PCI-DSS, SOX, AML, KYC) |
| Seeded users | 5 |
| Seeded employees | 100 |
| Seeded customers | 100+ |
