-- =============================================================================
-- Script: Seed canonical demo dataset (Phase 2B role-alignment, Step 2)
-- Target: banking_integration (integration DB, container banking_postgres_integration)
-- Run:    docker exec -i banking_postgres_integration psql -U integration_user \
--             -d banking_integration -v ON_ERROR_STOP=1 -f - < scripts/seed_canonical_demo.sql
-- Idempotent: safe to re-run any number of times (ON CONFLICT DO NOTHING).
--            Re-running preserves any workflow state mutated by live API calls.
-- Purpose: Give canonical users (analyst_001, compliance_001, admin_001) owned,
--          actionable records so real Keycloak logins see non-empty queues and
--          can perform one real mutation per role. All records live in hq_main.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. Grant hq_main scope to canonical users (currently they have ZERO scopes)
--    granted_by references the canonical system user row (FK only, no status gate).
-- -----------------------------------------------------------------------------
INSERT INTO user_scopes (user_id, scope_id, granted_by) VALUES
    ('analyst_001',    'hq_main', 'system_001'),
    ('compliance_001', 'hq_main', 'system_001'),
    ('admin_001',      'hq_main', 'system_001')
ON CONFLICT (user_id, scope_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 2. Alerts (all hq_main)
--    A1 assigned to analyst -> analyst can acknowledge / investigate
--    A2 acknowledged critical to analyst -> dismissal approval AP1 (compliance votes)
--    A3 unassigned new -> admin assigns it (alert:assign)
-- -----------------------------------------------------------------------------
INSERT INTO alerts (
    alert_id, alert_type, severity, title, description,
    source_rule_type, source_rule_id, related_entity_type, related_entity_id,
    scope_id, status, assigned_to, version, created_at, updated_at
) VALUES
    ('11111111-1111-4111-8111-111111111111', 'kpi_breach', 'high',
     'KPI breach: customer onboarding timeliness', 'Onboarding SLA breached for 3 consecutive days.',
     'kpi', 'kpi_onboarding_sla', 'customer', 'CUST_00921', 'hq_main', 'assigned',
     'analyst_001', 1, now(), now()),
    ('22222222-2222-4222-8222-222222222222', 'transaction_anomaly', 'critical',
     'Unusual rapid same-account transfers', 'Six rapid transfers to the same counterparty in under 2 hours.',
     'pattern', 'txn_rapid_same_counterparty', 'account', 'ACC_00412', 'hq_main',
     'acknowledged', 'analyst_001', 1, now(), now()),
    ('33333333-3333-4333-8333-333333333333', 'pattern_match', 'medium',
     'Unassigned pattern-match alert', 'Match against standard AML pattern library, no assignee yet.',
     'pattern', 'aml_pattern_lib_014', 'customer', 'CUST_00077', 'hq_main', 'new',
     NULL, 1, now(), now())
ON CONFLICT (alert_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 3. Investigations (all hq_main, owned by analyst_001)
--    I1 active    -> analyst can submit (active -> submitted)
--    I2 returned  -> analyst can rework (returned -> active)
--    I3/I4 submitted -> compliance reviews (submitted -> completed / returned)
-- -----------------------------------------------------------------------------
INSERT INTO investigations (
    investigation_id, title, description, alert_id, scope_id, status, priority,
    assigned_to, created_by, findings_text, conclusion, started_at, submitted_at,
    return_reason, version, created_at, updated_at
) VALUES
    ('aaaaaaaa-1111-4111-8111-111111111111',
     'Investigate KPI onboarding breach', 'Trace onboarding SLA breach to root cause.',
     '11111111-1111-4111-8111-111111111111', 'hq_main', 'active', 'high',
     'analyst_001', 'analyst_001',
     'Preliminary evidence points to queue backlog in the KYB step.', NULL,
     now() - interval '2 days', NULL, NULL, 1, now() - interval '2 days', now()),
    ('aaaaaaaa-2222-4222-8222-222222222222',
     'Rapid transfer pattern review', 'Review counterparty transfers flagged on ACC-00412.',
     '22222222-2222-4222-8222-222222222222', 'hq_main', 'returned', 'high',
     'analyst_001', 'analyst_001',
     'Collected transfer ledger excerpts and counterparty identifiers.', NULL,
     now() - interval '4 days', now() - interval '1 day',
     'Missing transaction-level evidence for all six counterparty hops.', 1,
     now() - interval '4 days', now()),
    ('aaaaaaaa-3333-4333-8333-333333333333',
     'Counterparty due-diligence sweep', 'Sweep open due-diligence gaps for escalated customers.',
     NULL, 'hq_main', 'submitted', 'medium',
     'analyst_001', 'analyst_001',
     'Ran DD sweep across 12 open profiles; gaps documented in findings refs.',
     'Recommend enhanced monitoring for the two highest-risk profiles.',
     now() - interval '3 days', now() - interval '1 hour', NULL, 1,
     now() - interval '3 days', now() - interval '1 hour'),
    ('aaaaaaaa-4444-4444-8444-444444444444',
     'Threshold avoidance analysis', 'Assess potential structuring against daily thresholds.',
     NULL, 'hq_main', 'submitted', 'low',
     'analyst_001', 'analyst_001',
     'Reviewed 30-day deposit ledger; no structuring indicators found.',
     'No further action recommended.',
     now() - interval '5 days', now() - interval '2 hours', NULL, 1,
     now() - interval '5 days', now() - interval '2 hours')
ON CONFLICT (investigation_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 4. Compliance cases (all hq_main, owned by compliance_001 except unassigned C6)
--    C1 assigned   -> compliance begins review (assigned -> under_review)
--    C2 awaiting_information (has open IR1/IR2 + responded IR3 on it)
--    C3 under_review -> compliance moves to decision_pending
--    C4 awaiting_compliance_action -> compliance resolves (needs resolution text)
--    C5 resolved -> compliance closes via transition (resolved -> closed)
--    C6 unassigned open -> admin assigns (case:assign)
-- -----------------------------------------------------------------------------
INSERT INTO compliance_cases (
    case_id, title, description, alert_id, investigation_id, scope_id, status,
    priority, risk_level, regulatory_frameworks, assigned_to, created_by,
    target_date, resolution, resolved_at, resolved_by, version, created_at, updated_at
) VALUES
    ('bbbbbbbb-1111-4111-8111-111111111111',
     'AML escalation: counterparty due-diligence', 'Escalated for formal case review.',
     NULL, 'aaaaaaaa-3333-4333-8333-333333333333', 'hq_main', 'assigned',
     'high', 'high', ARRAY['AML_KYC_2024'], 'compliance_001', 'compliance_001',
     CURRENT_DATE + 14, NULL, NULL, NULL, 1, now() - interval '1 day', now()),
    ('bbbbbbbb-2222-4222-8222-222222222222',
     'Suspicious activity: structured deposits', 'Case awaiting analyst responses to IRs.',
     NULL, NULL, 'hq_main', 'awaiting_information',
     'medium', 'medium', ARRAY['AML_KYC_2024'], 'compliance_001', 'compliance_001',
     CURRENT_DATE + 10, NULL, NULL, NULL, 1, now() - interval '3 days', now()),
    ('bbbbbbbb-3333-4333-8333-333333333333',
     'Sanctions watchlist overlap', 'Under review for possible name overlap.',
     NULL, NULL, 'hq_main', 'under_review',
     'medium', 'medium', ARRAY['OFAC', 'EU_SANCTIONS'], 'compliance_001', 'compliance_001',
     CURRENT_DATE + 7, NULL, NULL, NULL, 1, now() - interval '2 days', now()),
    ('bbbbbbbb-4444-4444-8444-444444444444',
     'High-risk jurisdiction flow review', 'Awaiting compliance action after review.',
     NULL, NULL, 'hq_main', 'awaiting_compliance_action',
     'medium', 'medium', ARRAY['AML_KYC_2024'], 'compliance_001', 'compliance_001',
     CURRENT_DATE + 5, NULL, NULL, NULL, 1, now() - interval '6 days', now()),
    ('bbbbbbbb-5555-4555-8555-555555555555',
     'Resolved CDD gap case', 'CDD gap remediated; case ready to close.',
     NULL, NULL, 'hq_main', 'resolved',
     'low', 'low', ARRAY['AML_KYC_2024'], 'compliance_001', 'compliance_001',
     NULL, 'Customer provided updated ID documents and income proof.',
     now() - interval '1 day', 'compliance_001', 1, now() - interval '9 days', now()),
    ('bbbbbbbb-6666-4666-8666-666666666666',
     'Unassigned wire-tracing case', 'Wire tracing case awaiting assignment.',
     NULL, NULL, 'hq_main', 'open',
     'medium', 'medium', ARRAY['AML_KYC_2024'], NULL, 'compliance_001',
     CURRENT_DATE + 7, NULL, NULL, NULL, 1, now() - interval '1 day', now())
ON CONFLICT (case_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 5. Information requests (created by compliance, assigned to analyst)
--    IR1 open + IR2 acknowledged -> analyst responds (acknowledge/respond)
--    IR3 responded -> compliance accepts (creator-only action, info_request:accept)
-- -----------------------------------------------------------------------------
INSERT INTO information_requests (
    ir_id, case_id, investigation_id, created_by, assigned_to, question, due_date,
    status, response_text, responded_at, version, created_at, updated_at
) VALUES
    ('cccccccc-1111-4111-8111-111111111111',
     'bbbbbbbb-2222-4222-8222-222222222222', NULL,
     'compliance_001', 'analyst_001',
     'Provide the source-of-funds evidence for the deposit series in question.',
     CURRENT_DATE + 3, 'open', NULL, NULL, 1, now() - interval '1 day', now()),
    ('cccccccc-2222-4222-8222-222222222222',
     'bbbbbbbb-2222-4222-8222-222222222222', NULL,
     'compliance_001', 'analyst_001',
     'List all counterparty identifiers touched by the flagged transfers.',
     CURRENT_DATE + 3, 'acknowledged', NULL, NULL, 1, now() - interval '1 day', now()),
    ('cccccccc-3333-4333-8333-333333333333',
     'bbbbbbbb-2222-4222-8222-222222222222', NULL,
     'compliance_001', 'analyst_001',
     'Summarise the rationale for excluding the flagged customer from the referral list.',
     CURRENT_DATE + 2, 'responded',
     'Customer is below the referral threshold; rationale documented in case file.',
     now() - interval '4 hours', 1, now() - interval '2 days', now() - interval '4 hours')
ON CONFLICT (ir_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 6. Approval request (compliance votes; conflict-of-interest guard active)
--    AP1: analyst requests dismissal of critical A2 (alert_dismissal_critical_high)
-- -----------------------------------------------------------------------------
INSERT INTO approval_requests (
    approval_request_id, action_type, entity_type, entity_id, requested_by,
    rationale, required_approvals, approval_count, status, expires_at,
    version, created_at, updated_at
) VALUES
    ('dddddddd-1111-4111-8111-111111111111',
     'alert_dismissal_critical_high', 'alert',
     '22222222-2222-4222-8222-222222222222', 'analyst_001',
     'Transfers confirmed false positive after ledger reconciliation; request dismissal.',
     1, 0, 'pending', now() + interval '72 hours', 1, now() - interval '3 hours',
     now() - interval '3 hours')
ON CONFLICT (approval_request_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 7. Notifications (unread; analyst + compliance queues)
-- -----------------------------------------------------------------------------
INSERT INTO notifications (
    notification_id, user_id, notification_type, title, body, entity_type, entity_id,
    is_read, created_at
) VALUES
    ('eeeeeeee-1111-4111-8111-111111111111', 'analyst_001', 'alert_assigned',
     'Alert assigned to you', 'KPI breach: customer onboarding timeliness', 'alert',
     '11111111-1111-4111-8111-111111111111', false, now() - interval '6 hours'),
    ('eeeeeeee-2222-4222-8222-222222222222', 'analyst_001', 'ir_created',
     'Information request assigned to you', 'Provide the source-of-funds evidence.',
     'information_request', 'cccccccc-1111-4111-8111-111111111111', false,
     now() - interval '5 hours'),
    ('eeeeeeee-3333-4333-8333-333333333333', 'analyst_001', 'investigation_returned',
     'Investigation returned for rework', 'Missing transaction-level evidence for counterparty hops.',
     'investigation', 'aaaaaaaa-2222-4222-8222-222222222222', false,
     now() - interval '20 hours'),
    ('eeeeeeee-4444-4444-8444-444444444444', 'compliance_001', 'approval_requested',
     'Approval requested', 'alert_dismissal_critical_high for alert 22222222-2222-4222-8222-222222222222',
     'approval_request', 'dddddddd-1111-4111-8111-111111111111', false,
     now() - interval '3 hours'),
    ('eeeeeeee-5555-4555-8555-555555555555', 'compliance_001', 'investigation_submitted',
     'Investigation submitted for review', 'Counterparty due-diligence sweep',
     'investigation', 'aaaaaaaa-3333-4333-8333-333333333333', false,
     now() - interval '1 hour'),
    ('eeeeeeee-6666-4666-8666-666666666666', 'compliance_001', 'case_assigned',
     'Case assigned to you', 'AML escalation: counterparty due-diligence',
     'compliance_case', 'bbbbbbbb-1111-4111-8111-111111111111', false,
     now() - interval '1 day')
ON CONFLICT (notification_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 8. Timeline entries (depth for the timeline views)
-- -----------------------------------------------------------------------------
INSERT INTO activity_timeline (
    timeline_id, entity_type, entity_id, event_type, actor_id, old_value,
    new_value, metadata, occurred_at
) VALUES
    ('ffffffff-1111-4111-8111-111111111111', 'investigation',
     'aaaaaaaa-1111-4111-8111-111111111111', 'investigation.created', 'analyst_001',
     NULL, '{"title": "Investigate KPI onboarding breach"}', NULL,
     now() - interval '2 days'),
    ('ffffffff-2222-4222-8222-222222222222', 'compliance_case',
     'bbbbbbbb-1111-4111-8111-111111111111', 'case.created', 'compliance_001',
     NULL, '{"title": "AML escalation: counterparty due-diligence"}', NULL,
     now() - interval '1 day'),
    ('ffffffff-3333-4333-8333-333333333333', 'approval_request',
     'dddddddd-1111-4111-8111-111111111111', 'approval_requested', 'analyst_001',
     NULL, '{"status": "pending", "action_type": "alert_dismissal_critical_high"}', NULL,
     now() - interval '3 hours'),
    ('ffffffff-4444-4444-8444-444444444444', 'alert',
     '11111111-1111-4111-8111-111111111111', 'alert.assigned', 'admin_001',
     '{"assigned_to": null}', '{"assigned_to": "analyst_001"}', NULL,
     now() - interval '6 hours')
ON CONFLICT (timeline_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 9. Assignment history (provenance for the seeded assignments)
-- -----------------------------------------------------------------------------
INSERT INTO assignment_history (
    history_id, entity_type, entity_id, assigned_from, assigned_to, assigned_by,
    reason, assigned_at
) VALUES
    ('99999999-1111-4111-8111-111111111111', 'alert',
     '11111111-1111-4111-8111-111111111111', NULL, 'analyst_001', 'admin_001',
     'Canonical demo assignment', now() - interval '6 hours'),
    ('99999999-2222-4222-8222-222222222222', 'compliance_case',
     'bbbbbbbb-1111-4111-8111-111111111111', NULL, 'compliance_001', 'admin_001',
     'Canonical demo assignment', now() - interval '1 day'),
    ('99999999-3333-4333-8333-333333333333', 'investigation',
     'aaaaaaaa-1111-4111-8111-111111111111', NULL, 'analyst_001', 'admin_001',
     'Canonical demo assignment', now() - interval '2 days')
ON CONFLICT (history_id) DO NOTHING;

COMMIT;

-- -----------------------------------------------------------------------------
-- Post-seed verification (run after COMMIT)
-- -----------------------------------------------------------------------------
SELECT 'scopes_granted' AS check, count(*) FROM user_scopes
WHERE user_id IN ('analyst_001','compliance_001','admin_001');

SELECT 'alerts_owned' AS check, count(*) FROM alerts
WHERE assigned_to IN ('analyst_001','compliance_001','admin_001');

SELECT 'investigations_owned' AS check, count(*) FROM investigations
WHERE assigned_to IN ('analyst_001','compliance_001','admin_001');

SELECT 'cases_owned' AS check, count(*) FROM compliance_cases
WHERE assigned_to IN ('analyst_001','compliance_001','admin_001');

SELECT 'irs_owned' AS check, count(*) FROM information_requests
WHERE assigned_to IN ('analyst_001','compliance_001','admin_001');

SELECT 'approvals_pending_for_compliance' AS check, count(*) FROM approval_requests
WHERE status = 'pending';
