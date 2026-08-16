-- =============================================================================
-- Migration: Seed Phase 2B permission codes and role_permissions assignments
-- Idempotent — safe to run multiple times. Complements init/02-users-kpis.sql
-- which seeds legacy read:/write: permissions.
-- =============================================================================

-- Seed Phase 2B permission codes
INSERT INTO permissions (permission_key, label, description, category) VALUES
    -- workbench gate
    ('workbench:access', 'Access Workbench', 'Access the investigation workbench UI', 'read'),
    -- alert
    ('alert:read_assigned', 'Read Assigned Alerts', 'List/read alerts assigned to self', 'read'),
    ('alert:read', 'Read All Alerts', 'List/read all alerts (admin)', 'read'),
    ('alert:assign', 'Assign Alert', 'Assign alert to user (admin)', 'admin'),
    ('alert:acknowledge', 'Acknowledge Alert', 'Acknowledge own assigned alert', 'write'),
    ('alert:dismiss', 'Dismiss Alert', 'Dismiss own assigned alert', 'write'),
    ('alert:investigate', 'Create Investigation', 'Create investigation from alert', 'write'),
    ('alert:transition', 'Transition Alert', 'Resolve alert (system-facing)', 'write'),
    -- investigation
    ('investigation:read_own', 'Read Own Investigation', 'Read investigations assigned to self', 'read'),
    ('investigation:read', 'Read Any Investigation', 'Read any investigation (compliance, admin)', 'read'),
    ('investigation:update', 'Update Investigation', 'Update findings_text, findings_refs, conclusion', 'write'),
    ('investigation:modify_findings', 'Modify Findings', 'SENSITIVE — explicit audit for findings changes', 'write'),
    ('investigation:transition', 'Transition Investigation', 'Start, submit, revise, complete transitions', 'write'),
    ('investigation:review', 'Review Investigation', 'Approve/return submitted investigations (compliance)', 'write'),
    ('investigation:assign', 'Assign Investigation', 'Assign investigation (admin) + cancel', 'admin'),
    -- compliance case
    ('case:create', 'Create Case', 'Create case (compliance, system via escalation)', 'write'),
    ('case:read_assigned', 'Read Assigned Case', 'Read cases assigned to self', 'read'),
    ('case:read', 'Read Any Case', 'Read any case (admin)', 'read'),
    ('case:transition', 'Transition Case', 'Begin_review, request_info, etc', 'write'),
    ('case:decision', 'Record Decision', 'Record decision (compliance ONLY)', 'write'),
    ('case:close', 'Close Case', 'Close case (compliance ONLY)', 'write'),
    ('case:assign', 'Assign Case', 'Assign case (admin) + cancel', 'admin'),
    ('case:reopen', 'Reopen Case', 'Reopen closed case (admin, with approval)', 'admin'),
    -- information request
    ('info_request:create', 'Create IR', 'Create information request (compliance)', 'write'),
    ('info_request:read_assigned', 'Read Assigned IR', 'Read IRs assigned to self (analyst)', 'read'),
    ('info_request:read', 'Read Any IR', 'Read any IR on owned case (compliance)', 'read'),
    ('info_request:respond', 'Respond to IR', 'Acknowledge + respond (analyst)', 'write'),
    ('info_request:accept', 'Accept IR', 'Accept response (compliance IR creator)', 'write'),
    ('info_request:return', 'Return IR', 'Return response (compliance IR creator)', 'write'),
    ('info_request:cancel', 'Cancel IR', 'Cancel IR (compliance creator or admin)', 'admin'),
    -- approval
    ('approval:request', 'Request Approval', 'Request approval for gated action', 'write'),
    ('approval:approve', 'Approve', 'Vote on approval (compliance only)', 'write'),
    ('approval:read', 'Read Approval', 'Read approval requests (all roles, own scope)', 'read'),
    -- comments
    ('comment:create', 'Create Comment', 'Create comment on accessible entity', 'write'),
    ('comment:read', 'Read Comment', 'Read public comments on accessible entity', 'read'),
    ('comment:view_internal_content', 'View Internal Comments', 'Read full internal comment text (compliance)', 'read'),
    ('comment:view_metadata', 'View Comment Metadata', 'See comment existence metadata without content (admin)', 'read'),
    ('comment:redact', 'Redact Comment', 'Redact comment (admin only)', 'admin'),
    -- timeline
    ('timeline:read', 'Read Timeline', 'Read timeline of accessible entity', 'read'),
    -- notifications
    ('notification:read', 'Read Notifications', 'Read own notifications', 'read'),
    ('notification:update', 'Update Notifications', 'Mark own notifications read', 'write'),
    -- admin operational
    ('admin:outbox_monitor', 'Monitor Outbox', 'Read audit outbox status (admin only)', 'admin'),
    ('admin:outbox_retry', 'Retry Outbox', 'Trigger outbox retry (admin only)', 'admin')
ON CONFLICT (permission_key) DO NOTHING;

-- Seed role_permissions for analyst
INSERT INTO role_permissions (role_id, permission_key) VALUES
    ('analyst', 'workbench:access'),
    ('analyst', 'alert:read_assigned'),
    ('analyst', 'alert:acknowledge'),
    ('analyst', 'alert:dismiss'),
    ('analyst', 'alert:investigate'),
    ('analyst', 'alert:transition'),
    ('analyst', 'investigation:read_own'),
    ('analyst', 'investigation:update'),
    ('analyst', 'investigation:modify_findings'),
    ('analyst', 'investigation:transition'),
    ('analyst', 'case:read_assigned'),
    ('analyst', 'info_request:read_assigned'),
    ('analyst', 'info_request:respond'),
    ('analyst', 'approval:request'),
    ('analyst', 'approval:read'),
    ('analyst', 'comment:create'),
    ('analyst', 'comment:read'),
    ('analyst', 'timeline:read'),
    ('analyst', 'notification:read'),
    ('analyst', 'notification:update')
ON CONFLICT DO NOTHING;

-- Seed role_permissions for compliance
INSERT INTO role_permissions (role_id, permission_key) VALUES
    ('compliance', 'workbench:access'),
    ('compliance', 'alert:read_assigned'),
    ('compliance', 'alert:transition'),
    ('compliance', 'investigation:read'),
    ('compliance', 'investigation:review'),
    ('compliance', 'case:create'),
    ('compliance', 'case:read_assigned'),
    ('compliance', 'case:transition'),
    ('compliance', 'case:decision'),
    ('compliance', 'case:close'),
    ('compliance', 'info_request:create'),
    ('compliance', 'info_request:read'),
    ('compliance', 'info_request:accept'),
    ('compliance', 'info_request:return'),
    ('compliance', 'info_request:cancel'),
    ('compliance', 'approval:request'),
    ('compliance', 'approval:approve'),
    ('compliance', 'approval:read'),
    ('compliance', 'comment:create'),
    ('compliance', 'comment:read'),
    ('compliance', 'comment:view_internal_content'),
    ('compliance', 'timeline:read'),
    ('compliance', 'notification:read'),
    ('compliance', 'notification:update')
ON CONFLICT DO NOTHING;

-- Seed role_permissions for admin
INSERT INTO role_permissions (role_id, permission_key) VALUES
    ('admin', 'workbench:access'),
    ('admin', 'alert:read'),
    ('admin', 'alert:assign'),
    ('admin', 'investigation:read'),
    ('admin', 'investigation:assign'),
    ('admin', 'case:read'),
    ('admin', 'case:assign'),
    ('admin', 'case:reopen'),
    ('admin', 'info_request:read'),
    ('admin', 'info_request:cancel'),
    ('admin', 'approval:request'),
    ('admin', 'approval:read'),
    ('admin', 'comment:create'),
    ('admin', 'comment:read'),
    ('admin', 'comment:view_metadata'),
    ('admin', 'comment:redact'),
    ('admin', 'timeline:read'),
    ('admin', 'notification:read'),
    ('admin', 'notification:update'),
    ('admin', 'admin:outbox_monitor'),
    ('admin', 'admin:outbox_retry')
ON CONFLICT DO NOTHING;
