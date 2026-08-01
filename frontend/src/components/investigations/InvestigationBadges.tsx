// src/components/investigations/InvestigationBadges.tsx
import { StatusBadge } from '../ui/StatusBadge';
import type { InvestigationPriority, InvestigationStatus } from '../../types/investigations';

const priorityVariant: Record<InvestigationPriority, 'red' | 'yellow' | 'blue' | 'gray'> = {
  critical: 'red',
  high: 'red',
  medium: 'yellow',
  low: 'gray',
};

export function InvestigationPriorityBadge({ priority, className }: { priority: InvestigationPriority; className?: string }) {
  return (
    <StatusBadge variant={priorityVariant[priority] ?? 'gray'} className={className}>
      {priority.toUpperCase()}
    </StatusBadge>
  );
}

const statusVariant: Record<InvestigationStatus, 'blue' | 'yellow' | 'purple' | 'green' | 'gray'> = {
  open: 'gray',
  active: 'blue',
  awaiting_information: 'yellow',
  submitted: 'purple',
  returned: 'yellow',
  completed: 'green',
  cancelled: 'gray',
};

export function InvestigationStatusBadge({ status, className }: { status: InvestigationStatus; className?: string }) {
  const label = status.replace(/_/g, ' ');
  return (
    <StatusBadge variant={statusVariant[status] ?? 'gray'} className={className}>
      {label}
    </StatusBadge>
  );
}
