// src/components/alerts/AlertBadges.tsx
import { StatusBadge } from '../ui/StatusBadge';
import type { AlertSeverity, AlertStatus } from '../../types/alerts';

const severityVariant: Record<AlertSeverity, 'red' | 'yellow' | 'blue'> = {
  critical: 'red',
  high: 'red',
  medium: 'yellow',
  low: 'blue',
};

export function AlertSeverityBadge({ severity, className }: { severity: AlertSeverity; className?: string }) {
  return (
    <StatusBadge variant={severityVariant[severity] ?? 'gray'} className={className}>
      {severity.toUpperCase()}
    </StatusBadge>
  );
}

const statusVariant: Record<AlertStatus, 'blue' | 'yellow' | 'purple' | 'green' | 'gray'> = {
  new: 'gray',
  assigned: 'yellow',
  acknowledged: 'purple',
  under_investigation: 'blue',
  resolved: 'green',
  dismissed: 'gray',
};

export function AlertStatusBadge({ status, className }: { status: AlertStatus; className?: string }) {
  const label = status.replace(/_/g, ' ');
  return (
    <StatusBadge variant={statusVariant[status] ?? 'gray'} className={className}>
      {label}
    </StatusBadge>
  );
}
