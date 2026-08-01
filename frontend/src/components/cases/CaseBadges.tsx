// src/components/cases/CaseBadges.tsx
import { StatusBadge } from '../ui/StatusBadge';
import type { CasePriority, CaseRiskLevel, CaseStatus, DecisionType } from '../../types/cases';

const priorityVariant: Record<CasePriority, 'red' | 'yellow' | 'blue' | 'gray'> = {
  critical: 'red',
  high: 'red',
  medium: 'yellow',
  low: 'gray',
};

export function CasePriorityBadge({ priority, className }: { priority: CasePriority; className?: string }) {
  return (
    <StatusBadge variant={priorityVariant[priority] ?? 'gray'} className={className}>
      {priority.toUpperCase()}
    </StatusBadge>
  );
}

// Spec §2.2: critical → dark red, high → red, medium → amber, low → gray.
const riskVariant: Record<CaseRiskLevel, 'red' | 'yellow' | 'blue' | 'gray'> = {
  critical: 'red',
  high: 'red',
  medium: 'yellow',
  low: 'gray',
};

export function CaseRiskBadge({ riskLevel, className }: { riskLevel: CaseRiskLevel | null | undefined; className?: string }) {
  if (!riskLevel) return null;
  const label = riskLevel.charAt(0).toUpperCase() + riskLevel.slice(1);
  return (
    <StatusBadge variant={riskVariant[riskLevel] ?? 'gray'} className={className}>
      {label} risk
    </StatusBadge>
  );
}

const statusVariant: Record<CaseStatus, 'blue' | 'yellow' | 'purple' | 'green' | 'gray' | 'red'> = {
  open: 'gray',
  assigned: 'yellow',
  under_review: 'blue',
  awaiting_information: 'purple',
  decision_pending: 'purple',
  awaiting_compliance_action: 'yellow',
  resolved: 'green',
  closed: 'gray',
  cancelled: 'gray',
};

export function CaseStatusBadge({ status, className }: { status: CaseStatus; className?: string }) {
  const label = status.replace(/_/g, ' ');
  return (
    <StatusBadge variant={statusVariant[status] ?? 'gray'} className={className}>
      {label}
    </StatusBadge>
  );
}

const decisionLabel: Record<DecisionType, string> = {
  no_action: 'No Action',
  warning: 'Warning',
  enhanced_due_diligence_recommended: 'EDD Recommended',
  report_to_authority_recommended: 'Report to Authority',
  account_action_recommended: 'Account Action',
  closure_recommended: 'Closure Recommended',
};

export function decisionTypeLabel(t: string): string {
  return decisionLabel[t as DecisionType] ?? t.replace(/_/g, ' ');
}

export function DecisionTypeBadge({ decisionType, className }: { decisionType: string; className?: string }) {
  const isAuthority = decisionType === 'report_to_authority_recommended';
  return (
    <StatusBadge variant={isAuthority ? 'red' : 'blue'} className={className}>
      {decisionTypeLabel(decisionType)}
    </StatusBadge>
  );
}
