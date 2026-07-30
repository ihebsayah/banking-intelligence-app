"""Baseline — capture all existing Inc 1 schema

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-07-30

All CREATE statements use IF NOT EXISTS so this revision is safe to run
on both fresh (empty) and existing (already-seeded) environments.

On existing environments: alembic stamp a1b2c3d4 — no DDL executed.
"""
from typing import Sequence, Union
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Customers ─────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            phone VARCHAR(20),
            kyc_verified BOOLEAN DEFAULT FALSE,
            risk_score DECIMAL(3,2),
            segment VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_customers_customer_id ON customers(customer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_customers_kyc ON customers(kyc_verified);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_customers_segment ON customers(segment);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_customers_risk_score ON customers(risk_score);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_customers_created ON customers(created_at);")

    # ── Accounts ──────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id VARCHAR(50) UNIQUE NOT NULL,
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            account_type VARCHAR(50),
            status VARCHAR(20),
            balance DECIMAL(15,2),
            available_balance DECIMAL(15,2),
            currency VARCHAR(3) DEFAULT 'USD',
            branch_id VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts(account_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_accounts_customer_id ON accounts(customer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_accounts_branch_id ON accounts(branch_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_accounts_created ON accounts(created_at);")

    # ── Transactions ──────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            transaction_id VARCHAR(50) UNIQUE NOT NULL,
            account_id VARCHAR(50) NOT NULL REFERENCES accounts(account_id),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            amount DECIMAL(15,2),
            transaction_type VARCHAR(50),
            status VARCHAR(20),
            description TEXT,
            transaction_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_transaction_id ON transactions(transaction_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_customer_id ON transactions(customer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);")

    # ── Risk Flags ────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS risk_flags (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            flag_type VARCHAR(50),
            severity VARCHAR(20),
            description TEXT,
            resolved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_risk_flags_customer_id ON risk_flags(customer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_risk_flags_severity ON risk_flags(severity);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_risk_flags_type ON risk_flags(flag_type);")

    # ── Branches ──────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS branches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            branch_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(255),
            state VARCHAR(50),
            city VARCHAR(100),
            manager_id VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_branches_branch_id ON branches(branch_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_branches_state ON branches(state);")

    # ── Products ──────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(255),
            category VARCHAR(50),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_products_product_id ON products(product_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);")

    # ── Compliance Rules ──────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS compliance_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            rule_name VARCHAR(255) NOT NULL,
            regulation VARCHAR(50),
            rule_type VARCHAR(50),
            condition VARCHAR(500),
            action VARCHAR(500),
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_compliance_rules_regulation ON compliance_rules(regulation);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_compliance_rules_enabled ON compliance_rules(enabled);")

    # ── Data Lineage ──────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS data_lineage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            query_id VARCHAR(100),
            source_table VARCHAR(100),
            source_column VARCHAR(100),
            destination_column VARCHAR(100),
            user_id VARCHAR(100),
            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_lineage_query_id ON data_lineage(query_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lineage_source_table ON data_lineage(source_table);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lineage_user_id ON data_lineage(user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lineage_accessed_at ON data_lineage(accessed_at);")

    # ── Compliance Violations ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS compliance_violations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            query_id VARCHAR(100),
            user_id VARCHAR(100),
            violation_type VARCHAR(50),
            severity VARCHAR(20),
            description TEXT,
            regulation VARCHAR(50),
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) DEFAULT 'open',
            resolution_notes TEXT
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_violations_query_id ON compliance_violations(query_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_violations_user_id ON compliance_violations(user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_violations_severity ON compliance_violations(severity);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_violations_status ON compliance_violations(status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_violations_detected_at ON compliance_violations(detected_at);")

    # ── Regulatory Reports ────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS regulatory_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            report_type VARCHAR(100),
            regulation VARCHAR(50),
            report_period_start DATE,
            report_period_end DATE,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            report_content TEXT,
            status VARCHAR(20) DEFAULT 'draft',
            submitted_to VARCHAR(255),
            submitted_at TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_report_type ON regulatory_reports(report_type);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_regulation ON regulatory_reports(regulation);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON regulatory_reports(status);")

    # ── Roles ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            role_id VARCHAR(50) PRIMARY KEY,
            label VARCHAR(100) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # ── Permissions ───────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            permission_key VARCHAR(100) PRIMARY KEY,
            label VARCHAR(100) NOT NULL,
            description TEXT,
            category VARCHAR(50) NOT NULL
        );
    """)

    # ── Role-Permissions Junction ─────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id VARCHAR(50) REFERENCES roles(role_id) ON DELETE CASCADE,
            permission_key VARCHAR(100) REFERENCES permissions(permission_key) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permission_key)
        );
    """)

    # ── Users ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR(100) PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255),
            role VARCHAR(50) NOT NULL REFERENCES roles(role_id),
            bank_id VARCHAR(50) DEFAULT 'hq_main',
            password_hash VARCHAR(255) NOT NULL,
            permissions TEXT[] DEFAULT '{}',
            must_change_password BOOLEAN DEFAULT FALSE,
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);")

    # ── User Activity Log ─────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_activity_log (
            id BIGSERIAL PRIMARY KEY,
            actor_id VARCHAR(100) NOT NULL,
            target_id VARCHAR(100),
            action VARCHAR(100) NOT NULL,
            detail JSONB,
            ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_actor ON user_activity_log(actor_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_created ON user_activity_log(created_at);")

    # ── KPI Categories ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS kpi_categories (
            category_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # ── KPI Owners ────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS kpi_owners (
            owner_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            role VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # ── KPI Definitions ───────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS kpi_definitions (
            kpi_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            metric_type VARCHAR(20) NOT NULL,
            category VARCHAR(50),
            data_freshness VARCHAR(20) DEFAULT 'real-time',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_kpis_category ON kpi_definitions(category);")

    # ── KPI Thresholds ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS kpi_thresholds (
            kpi_id VARCHAR(50) PRIMARY KEY REFERENCES kpi_definitions(kpi_id) ON DELETE CASCADE,
            healthy_min DECIMAL(15,4),
            healthy_max DECIMAL(15,4),
            warning_min DECIMAL(15,4),
            warning_max DECIMAL(15,4),
            critical_min DECIMAL(15,4),
            critical_max DECIMAL(15,4),
            healthy_label VARCHAR(50) DEFAULT 'Healthy',
            warning_label VARCHAR(50) DEFAULT 'Warning',
            critical_label VARCHAR(50) DEFAULT 'Critical',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # ── KPI History ───────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS kpi_history (
            history_id SERIAL PRIMARY KEY,
            kpi_id VARCHAR(50) REFERENCES kpi_definitions(kpi_id) ON DELETE CASCADE,
            changed_by VARCHAR(100) NOT NULL,
            change_type VARCHAR(50) NOT NULL,
            old_value JSONB,
            new_value JSONB,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # ── Semantic Layer ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS business_glossary (
            term_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            term VARCHAR(100) UNIQUE NOT NULL,
            definition TEXT NOT NULL,
            synonyms TEXT[],
            domain VARCHAR(50),
            business_owner VARCHAR(100),
            source_tables TEXT[],
            formula TEXT,
            example TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_glossary_term ON business_glossary(term);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_glossary_domain ON business_glossary(domain);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS metric_registry (
            metric_id VARCHAR(50) PRIMARY KEY,
            metric_name_fr VARCHAR(200),
            metric_name_en VARCHAR(200),
            formula TEXT NOT NULL,
            description TEXT,
            domain VARCHAR(50),
            owner VARCHAR(100),
            source_tables TEXT[],
            dependencies TEXT[],
            unit VARCHAR(20),
            refresh_frequency VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_metrics_domain ON metric_registry(domain);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS table_metadata (
            table_name VARCHAR(100) PRIMARY KEY,
            business_description TEXT,
            domain VARCHAR(50),
            owner VARCHAR(100),
            row_count_estimate INTEGER,
            is_analytical BOOLEAN DEFAULT FALSE,
            is_pii_bearing BOOLEAN DEFAULT FALSE,
            refresh_frequency VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_table_metadata_domain ON table_metadata(domain);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS column_metadata (
            metadata_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            table_name VARCHAR(100) NOT NULL,
            column_name VARCHAR(100) NOT NULL,
            business_description TEXT,
            synonyms TEXT[],
            data_type VARCHAR(50),
            is_pii BOOLEAN DEFAULT FALSE,
            example_values TEXT[],
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(table_name, column_name)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_column_metadata_lookup ON column_metadata(table_name, column_name);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS join_registry (
            join_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_table VARCHAR(100) NOT NULL,
            source_column VARCHAR(100) NOT NULL,
            target_table VARCHAR(100) NOT NULL,
            target_column VARCHAR(100) NOT NULL,
            relationship_type VARCHAR(20),
            join_type VARCHAR(20) DEFAULT 'LEFT JOIN',
            confidence DECIMAL(3,2) DEFAULT 1.00,
            notes TEXT,
            is_bidirectional BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_table, source_column, target_table, target_column)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_join_registry_lookup ON join_registry(source_table, target_table);")

    # ── Loan Domain ───────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS loan_products (
            loan_product_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            min_amount DECIMAL(15,2),
            max_amount DECIMAL(15,2),
            min_interest_rate DECIMAL(5,4),
            max_interest_rate DECIMAL(5,4),
            min_term_months INTEGER,
            max_term_months INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS loan_contracts (
            loan_id VARCHAR(50) PRIMARY KEY,
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            account_id VARCHAR(50) REFERENCES accounts(account_id),
            branch_id VARCHAR(50),
            loan_product_id VARCHAR(50) REFERENCES loan_products(loan_product_id),
            loan_type VARCHAR(50),
            principal_amount DECIMAL(15,2) NOT NULL,
            currency VARCHAR(3) DEFAULT 'TND',
            interest_rate DECIMAL(5,4) NOT NULL,
            term_months INTEGER NOT NULL,
            installment_amount DECIMAL(15,2),
            disbursement_date DATE,
            maturity_date DATE,
            status VARCHAR(30),
            outstanding_balance DECIMAL(15,2),
            days_past_due INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_loan_contracts_customer ON loan_contracts(customer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_loan_contracts_account ON loan_contracts(account_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_loan_contracts_branch ON loan_contracts(branch_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_loan_contracts_status ON loan_contracts(status);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS loan_installments (
            installment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            loan_id VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
            installment_number INTEGER NOT NULL,
            due_date DATE NOT NULL,
            principal_amount DECIMAL(15,2) NOT NULL,
            interest_amount DECIMAL(15,2) NOT NULL,
            total_amount DECIMAL(15,2) NOT NULL,
            status VARCHAR(20) DEFAULT 'unpaid',
            paid_amount DECIMAL(15,2) DEFAULT 0,
            paid_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_loan_installments_loan ON loan_installments(loan_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_loan_installments_due ON loan_installments(due_date);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS loan_repayments (
            repayment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            loan_id VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
            installment_id UUID REFERENCES loan_installments(installment_id),
            amount DECIMAL(15,2) NOT NULL,
            repayment_date DATE NOT NULL,
            payment_method VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_loan_repayments_loan ON loan_repayments(loan_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS loan_delinquency_events (
            event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            loan_id VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
            event_date DATE NOT NULL,
            days_past_due INTEGER NOT NULL,
            outstanding_balance DECIMAL(15,2) NOT NULL,
            resolved BOOLEAN DEFAULT FALSE,
            resolved_date DATE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_loan_delinquency_loan ON loan_delinquency_events(loan_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS loan_restructuring (
            restructuring_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            loan_id VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
            request_date DATE NOT NULL,
            approval_date DATE,
            previous_principal DECIMAL(15,2),
            previous_interest_rate DECIMAL(5,4),
            previous_term INTEGER,
            new_principal DECIMAL(15,2),
            new_interest_rate DECIMAL(5,4),
            new_term INTEGER,
            reason TEXT,
            status VARCHAR(30),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_loan_restruct_loan ON loan_restructuring(loan_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS collateral (
            collateral_id VARCHAR(50) PRIMARY KEY,
            loan_id VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
            collateral_type VARCHAR(50),
            description TEXT,
            estimated_value DECIMAL(15,2) NOT NULL,
            valuation_date DATE,
            valuer_name VARCHAR(100),
            status VARCHAR(30),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_collateral_loan ON collateral(loan_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS guarantees (
            guarantee_id VARCHAR(50) PRIMARY KEY,
            loan_id VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
            guarantor_name VARCHAR(255) NOT NULL,
            guarantor_id VARCHAR(50),
            guarantee_amount DECIMAL(15,2) NOT NULL,
            guarantee_type VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_guarantees_loan ON guarantees(loan_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS provisions (
            provision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            loan_id VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id),
            provision_date DATE NOT NULL,
            provision_amount DECIMAL(15,2) NOT NULL,
            calculation_model VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_provisions_loan ON provisions(loan_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS non_performing_loans (
            npl_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            loan_id VARCHAR(50) NOT NULL REFERENCES loan_contracts(loan_id) UNIQUE,
            npl_amount DECIMAL(15,2) NOT NULL,
            npl_date DATE NOT NULL,
            classification VARCHAR(50) NOT NULL,
            recovery_status VARCHAR(30) DEFAULT 'unrecovered',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_npl_loan ON non_performing_loans(loan_id);")

    # ── KYC/AML Domain ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS kyc_cases (
            kyc_case_id VARCHAR(50) PRIMARY KEY,
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            case_type VARCHAR(30),
            status VARCHAR(30),
            risk_level VARCHAR(20),
            assigned_to VARCHAR(100),
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            due_date DATE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_kyc_cases_customer ON kyc_cases(customer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_kyc_cases_status ON kyc_cases(status);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS kyc_documents (
            kyc_doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kyc_case_id VARCHAR(50) NOT NULL REFERENCES kyc_cases(kyc_case_id),
            document_type VARCHAR(50) NOT NULL,
            document_number VARCHAR(100),
            expiry_date DATE,
            verified BOOLEAN DEFAULT FALSE,
            verified_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_kyc_docs_case ON kyc_documents(kyc_case_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS kyc_reviews (
            review_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kyc_case_id VARCHAR(50) NOT NULL REFERENCES kyc_cases(kyc_case_id),
            reviewer_id VARCHAR(100) NOT NULL,
            decision VARCHAR(30) NOT NULL,
            comments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_kyc_reviews_case ON kyc_reviews(kyc_case_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS kyc_verifications (
            verification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kyc_case_id VARCHAR(50) NOT NULL REFERENCES kyc_cases(kyc_case_id),
            verification_type VARCHAR(50) NOT NULL,
            status VARCHAR(30) NOT NULL,
            verified_at TIMESTAMP,
            verified_by VARCHAR(100),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_kyc_verif_case ON kyc_verifications(kyc_case_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS kyc_expirations (
            expiration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            kyc_case_id VARCHAR(50) REFERENCES kyc_cases(kyc_case_id),
            expiry_date DATE NOT NULL,
            review_required BOOLEAN DEFAULT TRUE,
            notification_sent BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_kyc_exp_customer ON kyc_expirations(customer_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS pep_screening (
            screening_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            matched_name VARCHAR(255) NOT NULL,
            risk_level VARCHAR(20) DEFAULT 'moyen',
            source_list VARCHAR(100),
            match_score DECIMAL(5,2),
            status VARCHAR(30) DEFAULT 'unverified',
            reviewed_by VARCHAR(100),
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pep_screen_customer ON pep_screening(customer_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS sanctions_screening (
            screening_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            matched_name VARCHAR(255) NOT NULL,
            sanctions_list VARCHAR(100),
            match_score DECIMAL(5,2),
            status VARCHAR(30) DEFAULT 'unverified',
            reviewed_by VARCHAR(100),
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sanctions_screen_cust ON sanctions_screening(customer_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS aml_alerts (
            alert_id VARCHAR(50) PRIMARY KEY,
            customer_id VARCHAR(50) REFERENCES customers(customer_id),
            account_id VARCHAR(50) REFERENCES accounts(account_id),
            transaction_id VARCHAR(50) REFERENCES transactions(transaction_id),
            alert_type VARCHAR(50),
            alert_label_fr VARCHAR(255),
            severity VARCHAR(20),
            status VARCHAR(20),
            score DECIMAL(5,2),
            triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            analyst_id VARCHAR(100),
            resolution TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_aml_alerts_customer ON aml_alerts(customer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_aml_alerts_status ON aml_alerts(status);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS suspicious_activity_reports (
            sar_id VARCHAR(50) PRIMARY KEY,
            alert_id VARCHAR(50) REFERENCES aml_alerts(alert_id),
            customer_id VARCHAR(50) REFERENCES customers(customer_id),
            report_date DATE NOT NULL,
            status VARCHAR(30) DEFAULT 'brouillon',
            ctaf_reference VARCHAR(100),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sar_customer ON suspicious_activity_reports(customer_id);")

    # legacy compliance_cases (existing Inc 1 table — distinct from Inc 2 compliance_cases)
    op.execute("""
        CREATE TABLE IF NOT EXISTS compliance_cases (
            compliance_case_id VARCHAR(50) PRIMARY KEY,
            customer_id VARCHAR(50) REFERENCES customers(customer_id),
            case_type VARCHAR(50) NOT NULL,
            status VARCHAR(30) DEFAULT 'ouvert',
            severity VARCHAR(20),
            assigned_to VARCHAR(100),
            description TEXT,
            opened_date DATE NOT NULL,
            closed_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_comp_cases_customer ON compliance_cases(customer_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS compliance_reviews (
            review_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            compliance_case_id VARCHAR(50) REFERENCES compliance_cases(compliance_case_id),
            reviewer_id VARCHAR(100) NOT NULL,
            findings TEXT,
            action_plan TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_comp_reviews_case ON compliance_reviews(compliance_case_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_findings (
            finding_id VARCHAR(50) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            source VARCHAR(50),
            severity VARCHAR(20),
            status VARCHAR(30),
            target_resolution_date DATE,
            resolved_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_findings_status ON audit_findings(status);")

    # ── Finance/GL Domain ─────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS general_ledger (
            ledger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_code VARCHAR(20) UNIQUE NOT NULL,
            account_name_fr VARCHAR(200),
            account_type VARCHAR(30),
            parent_code VARCHAR(20),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_gl_account_code ON general_ledger(account_code);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS ledger_entries (
            entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_code VARCHAR(20) NOT NULL REFERENCES general_ledger(account_code),
            transaction_id VARCHAR(50),
            debit_amount DECIMAL(15,2) DEFAULT 0.00,
            credit_amount DECIMAL(15,2) DEFAULT 0.00,
            currency VARCHAR(3) DEFAULT 'TND',
            value_date DATE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_entries_code ON ledger_entries(account_code);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_entries_date ON ledger_entries(value_date);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS fee_income (
            fee_income_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) REFERENCES customers(customer_id),
            account_id VARCHAR(50) REFERENCES accounts(account_id),
            fee_type VARCHAR(50) NOT NULL,
            amount DECIMAL(15,2) NOT NULL,
            value_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_fee_income_customer ON fee_income(customer_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS interest_income (
            interest_income_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            loan_id VARCHAR(50) REFERENCES loan_contracts(loan_id),
            account_id VARCHAR(50) REFERENCES accounts(account_id),
            amount DECIMAL(15,2) NOT NULL,
            value_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS operating_expenses (
            expense_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            expense_type VARCHAR(50) NOT NULL,
            amount DECIMAL(15,2) NOT NULL,
            value_date DATE NOT NULL,
            branch_id VARCHAR(50),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_operating_expenses_type ON operating_expenses(expense_type);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_operating_expenses_date ON operating_expenses(value_date);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS profitability_metrics (
            metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            branch_id VARCHAR(50),
            product_id VARCHAR(50),
            customer_id VARCHAR(50) REFERENCES customers(customer_id),
            pnb DECIMAL(15,2) NOT NULL,
            net_income DECIMAL(15,2) NOT NULL,
            cost_to_income_ratio DECIMAL(5,2),
            calculation_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS balance_sheet_snapshots (
            snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            period VARCHAR(7) NOT NULL,
            total_assets DECIMAL(20,2) NOT NULL,
            total_liabilities DECIMAL(20,2) NOT NULL,
            total_equity DECIMAL(20,2) NOT NULL,
            hqla DECIMAL(20,2),
            net_outflows_30d DECIMAL(20,2),
            available_stable_funding DECIMAL(20,2),
            required_stable_funding DECIMAL(20,2),
            snapshot_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_balance_sheet_period ON balance_sheet_snapshots(period);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS income_statement_snapshots (
            snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            period VARCHAR(7) NOT NULL,
            interest_income DECIMAL(20,2) NOT NULL,
            interest_expense DECIMAL(20,2) NOT NULL,
            fee_income DECIMAL(20,2) NOT NULL,
            net_banking_income DECIMAL(20,2) NOT NULL,
            operating_expenses DECIMAL(20,2) NOT NULL,
            pnb DECIMAL(20,2) NOT NULL,
            net_income DECIMAL(20,2) NOT NULL,
            snapshot_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_income_statement_period ON income_statement_snapshots(period);")

    # ── Organization / Customer Ext Domain ────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS regions (
            region_id VARCHAR(50) PRIMARY KEY,
            region_name_fr VARCHAR(100) NOT NULL,
            governorates TEXT[],
            population INTEGER,
            gdp_contribution DECIMAL(5,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            department_id VARCHAR(50) PRIMARY KEY,
            name_fr VARCHAR(100) NOT NULL,
            name_en VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS business_units (
            unit_id VARCHAR(50) PRIMARY KEY,
            name_fr VARCHAR(100) NOT NULL,
            name_en VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id VARCHAR(50) PRIMARY KEY,
            branch_id VARCHAR(50) REFERENCES branches(branch_id),
            department_id VARCHAR(50) REFERENCES departments(department_id),
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            title VARCHAR(100),
            role VARCHAR(50),
            hire_date DATE,
            is_active BOOLEAN DEFAULT TRUE,
            email VARCHAR(255),
            supervisor_id VARCHAR(50) REFERENCES employees(employee_id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS relationship_managers (
            rm_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            employee_id VARCHAR(50) NOT NULL REFERENCES employees(employee_id),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id) UNIQUE,
            portfolio_type VARCHAR(50),
            assigned_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS customer_profiles (
            profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id) UNIQUE,
            date_of_birth DATE,
            gender VARCHAR(10),
            nationality VARCHAR(50) DEFAULT 'TN',
            national_id VARCHAR(20),
            passport_number VARCHAR(20),
            marital_status VARCHAR(20),
            employment_status VARCHAR(50),
            employer_name VARCHAR(255),
            annual_income DECIMAL(15,2),
            income_currency VARCHAR(3) DEFAULT 'TND',
            net_worth_band VARCHAR(20),
            politically_exposed BOOLEAN DEFAULT FALSE,
            pep_details TEXT,
            tax_id VARCHAR(30),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS customer_segments (
            segment_id VARCHAR(50) PRIMARY KEY,
            segment_name VARCHAR(100) NOT NULL,
            segment_label_fr VARCHAR(100),
            min_balance DECIMAL(15,2),
            min_annual_income DECIMAL(15,2),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS customer_addresses (
            address_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            address_type VARCHAR(20),
            address_line1 VARCHAR(255),
            address_line2 VARCHAR(255),
            city VARCHAR(100),
            governorate VARCHAR(100),
            postal_code VARCHAR(10),
            country VARCHAR(50) DEFAULT 'Tunisie',
            is_primary BOOLEAN DEFAULT FALSE,
            valid_from DATE,
            valid_to DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cust_addr_customer ON customer_addresses(customer_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS customer_contacts (
            contact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            contact_type VARCHAR(20),
            contact_value VARCHAR(255),
            is_primary BOOLEAN DEFAULT FALSE,
            verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cust_cont_customer ON customer_contacts(customer_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS customer_risk_scores (
            score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            model_id VARCHAR(50),
            score DECIMAL(5,4),
            score_band VARCHAR(20),
            score_date DATE NOT NULL,
            factors JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cust_risk_scores_cust ON customer_risk_scores(customer_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS customer_relationships (
            relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            related_customer_id VARCHAR(50) REFERENCES customers(customer_id),
            relationship_type VARCHAR(50),
            valid_from DATE,
            valid_to DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS customer_documents (
            document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            document_type VARCHAR(50),
            document_number VARCHAR(100),
            issued_date DATE,
            expiry_date DATE,
            verified BOOLEAN DEFAULT FALSE,
            verified_by VARCHAR(100),
            verified_at TIMESTAMP,
            storage_ref TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cust_docs_customer ON customer_documents(customer_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS customer_preferences (
            preference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id) UNIQUE,
            language VARCHAR(10) DEFAULT 'fr',
            contact_channel VARCHAR(20) DEFAULT 'email',
            marketing_consent BOOLEAN DEFAULT FALSE,
            digital_banking BOOLEAN DEFAULT TRUE,
            sms_alerts BOOLEAN DEFAULT TRUE,
            email_alerts BOOLEAN DEFAULT TRUE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS customer_status_history (
            history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            previous_status VARCHAR(30),
            new_status VARCHAR(30),
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            changed_by VARCHAR(100),
            reason TEXT
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cust_status_hist_cust ON customer_status_history(customer_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS account_types (
            type_code VARCHAR(50) PRIMARY KEY,
            type_name_fr VARCHAR(100) NOT NULL,
            type_name_en VARCHAR(100),
            currency VARCHAR(3) DEFAULT 'TND',
            interest_rate DECIMAL(5,4),
            min_balance DECIMAL(15,2) DEFAULT 0.00,
            max_balance DECIMAL(20,2),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS account_balances (
            balance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id VARCHAR(50) NOT NULL REFERENCES accounts(account_id),
            balance DECIMAL(15,2) NOT NULL,
            available_balance DECIMAL(15,2) NOT NULL,
            snapshot_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_account_balances_acc ON account_balances(account_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_account_balances_date ON account_balances(snapshot_date);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS account_status_history (
            history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id VARCHAR(50) NOT NULL REFERENCES accounts(account_id),
            previous_status VARCHAR(20),
            new_status VARCHAR(20),
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason TEXT
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS joint_accounts (
            joint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id VARCHAR(50) NOT NULL REFERENCES accounts(account_id),
            customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
            relationship VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, customer_id)
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS account_signatories (
            signatory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id VARCHAR(50) NOT NULL REFERENCES accounts(account_id),
            customer_id VARCHAR(50) REFERENCES customers(customer_id),
            signatory_name VARCHAR(255) NOT NULL,
            signatory_role VARCHAR(50),
            signature_specimen TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # ── Safe ALTER statements (idempotent) ────────────────────────────
    from sqlalchemy import text
    conn = op.get_bind()

    # kpi_definitions columns added incrementally
    conn.execute(text("ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS formula TEXT;"))
    conn.execute(text("ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS owner_id VARCHAR(50);"))
    conn.execute(text("ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS source_tables TEXT[];"))
    conn.execute(text("ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS refresh_frequency VARCHAR(50) DEFAULT 'real-time';"))
    conn.execute(text("ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active';"))
    conn.execute(text("ALTER TABLE kpi_definitions ADD COLUMN IF NOT EXISTS reason TEXT;"))

    # Keycloak identity columns
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS identity_provider_subject VARCHAR(255) UNIQUE NULL;"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS identity_provider VARCHAR(50) DEFAULT 'local';"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_identity_provider_subject ON users(identity_provider_subject) WHERE identity_provider_subject IS NOT NULL;"))

    # Org-customer extensions: FK and region_id
    conn.execute(text("ALTER TABLE branches ADD COLUMN IF NOT EXISTS region_id VARCHAR(50) REFERENCES regions(region_id);"))
    conn.execute(text("ALTER TABLE accounts DROP CONSTRAINT IF EXISTS fk_accounts_branch;"))
    conn.execute(text("ALTER TABLE accounts ADD CONSTRAINT fk_accounts_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id);"))


def downgrade() -> None:
    """No downgrade for baseline — reverting would destroy all production data."""
    pass
