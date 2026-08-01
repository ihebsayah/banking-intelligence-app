// src/components/approvals/approvalLabels.ts
// Canonical 2B.15 approval vocabulary — labels for UI, values sent verbatim to the backend.
import type { ApprovalStatus } from '../../types/alerts';

export const APPROVAL_ACTION_TYPES = [
  'alert_dismissal_critical_high',
  'case_closure_critical_high',
  'decision_report_to_authority',
  'case_reopen',
] as const;

export type ApprovalActionType = (typeof APPROVAL_ACTION_TYPES)[number];

export const APPROVAL_STATUSES = ['pending', 'approved', 'rejected', 'expired', 'cancelled'] as const;

const ACTION_LABELS: Record<ApprovalActionType, string> = {
  alert_dismissal_critical_high: 'Critical/High Alert Dismissal',
  case_closure_critical_high: 'Critical/High Case Closure',
  decision_report_to_authority: 'Report to Authority Decision',
  case_reopen: 'Case Reopen',
};

export function approvalActionLabel(actionType: string): string {
  return ACTION_LABELS[actionType as ApprovalActionType] ?? actionType.replace(/_/g, ' ');
}

export function approvalEntityLabel(entityType: string): string {
  if (entityType === 'compliance_case') return 'Case';
  if (entityType === 'alert') return 'Alert';
  return entityType.replace(/_/g, ' ');
}

export function approvalEntityRoute(entityType: string, entityId: string): string | null {
  if (entityType === 'alert') return `/workbench/alerts/${entityId}`;
  if (entityType === 'compliance_case') return `/workbench/cases/${entityId}`;
  return null;
}

const STATUS_VARIANTS: Record<ApprovalStatus, 'yellow' | 'green' | 'red' | 'gray'> = {
  pending: 'yellow',
  approved: 'green',
  rejected: 'red',
  expired: 'gray',
  cancelled: 'gray',
};

export function approvalStatusVariant(status: string): 'yellow' | 'green' | 'red' | 'gray' {
  return STATUS_VARIANTS[status as ApprovalStatus] ?? 'gray';
}

const DECISION_VARIANTS: Record<string, 'green' | 'red'> = {
  approved: 'green',
  rejected: 'red',
};

export function approvalDecisionVariant(decision: string): 'green' | 'red' {
  return DECISION_VARIANTS[decision] ?? 'gray';
}
