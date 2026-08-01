// src/components/notifications/notificationLabels.ts
// Canonical 2B.16 notification vocabulary — UI labels + navigation for the
// notification-type CHECK constraint in migrations/0004_add_operational_entities.py.
// Unknown future types fall back to a safe title-cased label, never a hard error.

export const NOTIFICATION_TYPES = [
  'alert_assigned', 'alert_dismissed', 'alert_escalated',
  'investigation_assigned', 'investigation_returned', 'investigation_submitted',
  'case_assigned', 'case_decision_recorded', 'case_resolved', 'case_closed', 'case_reopened',
  'ir_created', 'ir_acknowledged', 'ir_responded', 'ir_accepted', 'ir_returned',
  'approval_requested', 'approval_decided', 'approval_expired',
] as const;

const TYPE_LABELS: Record<string, string> = {
  alert_assigned: 'Alert assigned',
  alert_dismissed: 'Alert dismissed',
  alert_escalated: 'Alert escalated',
  investigation_assigned: 'Investigation assigned',
  investigation_returned: 'Investigation returned',
  investigation_submitted: 'Investigation submitted',
  case_assigned: 'Case assigned',
  case_decision_recorded: 'Decision recorded',
  case_resolved: 'Case resolved',
  case_closed: 'Case closed',
  case_reopened: 'Case reopened',
  ir_created: 'Information request created',
  ir_acknowledged: 'Information request acknowledged',
  ir_responded: 'Information request responded',
  ir_accepted: 'Information request accepted',
  ir_returned: 'Information request returned',
  approval_requested: 'Approval requested',
  approval_decided: 'Approval decided',
  approval_expired: 'Approval expired',
};

export function notificationTypeLabel(type: string): string {
  const label = TYPE_LABELS[type];
  if (label) return label;
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function notificationEntityLabel(entityType: string): string {
  if (entityType === 'alert') return 'Alert';
  if (entityType === 'investigation') return 'Investigation';
  if (entityType === 'compliance_case') return 'Case';
  if (entityType === 'information_request') return 'Information Request';
  if (entityType === 'approval_request') return 'Approval';
  return entityType.replace(/_/g, ' ');
}

/** Map backend entity_type/entity_id to an existing 2B route, or null. */
export function notificationEntityRoute(
  entityType: string | null | undefined,
  entityId: string | null | undefined,
): string | null {
  if (!entityType || !entityId) return null;
  if (entityType === 'alert') return `/workbench/alerts/${entityId}`;
  if (entityType === 'investigation') return `/workbench/investigations/${entityId}`;
  if (entityType === 'compliance_case') return `/workbench/cases/${entityId}`;
  if (entityType === 'information_request') return `/workbench/information-requests`;
  if (entityType === 'approval_request') return `/workbench/approvals`;
  return null;
}
