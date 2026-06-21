-- =============================================================================
-- Phase 6A: KYC & AML / Compliance Domain Schema
-- init/05-kyc-aml-domain.sql
-- =============================================================================

-- 1. KYC Cases Table
CREATE TABLE IF NOT EXISTS kyc_cases (
    kyc_case_id       VARCHAR(50) PRIMARY KEY,
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    case_type         VARCHAR(30),         -- initial_kyc, periodic_review, enhanced_dd
    status            VARCHAR(30),         -- ouvert, en_cours, approuvé, rejeté, expiré
    risk_level        VARCHAR(20),         -- standard, élevé, pep
    assigned_to       VARCHAR(100),
    opened_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at         TIMESTAMP,
    due_date          DATE,
    notes             TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kyc_cases_customer ON kyc_cases(customer_id);
CREATE INDEX IF NOT EXISTS idx_kyc_cases_status ON kyc_cases(status);

-- 2. KYC Documents Table
CREATE TABLE IF NOT EXISTS kyc_documents (
    kyc_doc_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kyc_case_id       VARCHAR(50) NOT NULL REFERENCES kyc_cases(kyc_case_id),
    document_type     VARCHAR(50) NOT NULL,          -- CIN, passeport, justificatif_domicile
    document_number   VARCHAR(100),
    expiry_date       DATE,
    verified          BOOLEAN DEFAULT FALSE,
    verified_at       TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kyc_docs_case ON kyc_documents(kyc_case_id);

-- 3. KYC Reviews Table
CREATE TABLE IF NOT EXISTS kyc_reviews (
    review_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kyc_case_id       VARCHAR(50) NOT NULL REFERENCES kyc_cases(kyc_case_id),
    reviewer_id       VARCHAR(100) NOT NULL,
    decision          VARCHAR(30) NOT NULL,          -- approuvé, rejeté, escaladé
    comments          TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kyc_reviews_case ON kyc_reviews(kyc_case_id);

-- 4. KYC Verifications Table
CREATE TABLE IF NOT EXISTS kyc_verifications (
    verification_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kyc_case_id       VARCHAR(50) NOT NULL REFERENCES kyc_cases(kyc_case_id),
    verification_type VARCHAR(50) NOT NULL,          -- identité, adresse, revenus, PEP
    status            VARCHAR(30) NOT NULL,          -- vérifié, rejeté, en_attente
    verified_at       TIMESTAMP,
    verified_by       VARCHAR(100),
    notes             TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kyc_verif_case ON kyc_verifications(kyc_case_id);

-- 5. KYC Expirations Table
CREATE TABLE IF NOT EXISTS kyc_expirations (
    expiration_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    kyc_case_id       VARCHAR(50) REFERENCES kyc_cases(kyc_case_id),
    expiry_date       DATE NOT NULL,
    review_required   BOOLEAN DEFAULT TRUE,
    notification_sent BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kyc_exp_customer ON kyc_expirations(customer_id);

-- 6. PEP Screening Table
CREATE TABLE IF NOT EXISTS pep_screening (
    screening_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    matched_name      VARCHAR(255) NOT NULL,
    risk_level        VARCHAR(20) DEFAULT 'moyen',   -- faible, moyen, élevé
    source_list       VARCHAR(100),
    match_score       DECIMAL(5,2),
    status            VARCHAR(30) DEFAULT 'unverified', -- faux_positif, confirmé, unverified
    reviewed_by       VARCHAR(100),
    reviewed_at       TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pep_screen_customer ON pep_screening(customer_id);

-- 7. Sanctions Screening Table
CREATE TABLE IF NOT EXISTS sanctions_screening (
    screening_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    matched_name      VARCHAR(255) NOT NULL,
    sanctions_list    VARCHAR(100),                  -- OFAC, ONU, UE, etc.
    match_score       DECIMAL(5,2),
    status            VARCHAR(30) DEFAULT 'unverified', -- faux_positif, confirmé, unverified
    reviewed_by       VARCHAR(100),
    reviewed_at       TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sanctions_screen_cust ON sanctions_screening(customer_id);

-- 8. AML Alerts Table
CREATE TABLE IF NOT EXISTS aml_alerts (
    alert_id          VARCHAR(50) PRIMARY KEY,
    customer_id       VARCHAR(50) REFERENCES customers(customer_id),
    account_id        VARCHAR(50) REFERENCES accounts(account_id),
    transaction_id    VARCHAR(50) REFERENCES transactions(transaction_id),
    alert_type        VARCHAR(50),                   -- transaction_inhabituelle, seuil_dépassé, structuring, PEP
    alert_label_fr    VARCHAR(255),                  -- Suspicion AML: Dépôt espèces atypique
    severity          VARCHAR(20),                   -- faible, moyen, élevé, critique
    status            VARCHAR(20),                   -- ouvert, en_cours, clôturé, faux_positif
    score             DECIMAL(5,2),
    triggered_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at         TIMESTAMP,
    analyst_id        VARCHAR(100),
    resolution        TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_aml_alerts_customer ON aml_alerts(customer_id);
CREATE INDEX IF NOT EXISTS idx_aml_alerts_status ON aml_alerts(status);

-- 9. Suspicious Activity Reports (SAR / DSFR) Table
CREATE TABLE IF NOT EXISTS suspicious_activity_reports (
    sar_id            VARCHAR(50) PRIMARY KEY,
    alert_id          VARCHAR(50) REFERENCES aml_alerts(alert_id),
    customer_id       VARCHAR(50) REFERENCES customers(customer_id),
    report_date       DATE NOT NULL,
    status            VARCHAR(30) DEFAULT 'brouillon', -- brouillon, soumis, approuvé
    ctaf_reference    VARCHAR(100),
    description       TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sar_customer ON suspicious_activity_reports(customer_id);

-- 10. Compliance Cases Table
CREATE TABLE IF NOT EXISTS compliance_cases (
    compliance_case_id VARCHAR(50) PRIMARY KEY,
    customer_id       VARCHAR(50) REFERENCES customers(customer_id),
    case_type         VARCHAR(50) NOT NULL,          -- aml, kyc, plainte, audit
    status            VARCHAR(30) DEFAULT 'ouvert',  -- ouvert, en_cours, clos
    severity          VARCHAR(20),                   -- faible, moyen, élevé, critique
    assigned_to       VARCHAR(100),
    description       TEXT,
    opened_date       DATE NOT NULL,
    closed_date       DATE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_comp_cases_customer ON compliance_cases(customer_id);

-- 11. Compliance Reviews Table
CREATE TABLE IF NOT EXISTS compliance_reviews (
    review_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    compliance_case_id VARCHAR(50) REFERENCES compliance_cases(compliance_case_id),
    reviewer_id       VARCHAR(100) NOT NULL,
    findings          TEXT,
    action_plan       TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_comp_reviews_case ON compliance_reviews(compliance_case_id);

-- 12. Audit Findings Table
CREATE TABLE IF NOT EXISTS audit_findings (
    finding_id        VARCHAR(50) PRIMARY KEY,
    title             VARCHAR(255) NOT NULL,
    description       TEXT,
    source            VARCHAR(50),                   -- audit_interne, audit_externe, régulateur
    severity          VARCHAR(20),                   -- faible, moyen, élevé, critique
    status            VARCHAR(30),                   -- ouvert, résolu, en_attente
    target_resolution_date DATE,
    resolved_date     DATE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_findings_status ON audit_findings(status);
