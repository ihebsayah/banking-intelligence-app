// src/components/customers/customer360Format.ts
// Pure formatting helpers shared by the Customer 360 page and the compact
// CustomerContextPanel embedded in the operational workbench. All values are
// rendered exactly as delivered by the (server-authorized) overview response.
export function money(value: string | null | undefined, currency?: string | null): string {
  if (value == null || value === '') return '—';
  if (!/^-?\d+(\.\d+)?$/.test(value)) return value; // masked / non-numeric token
  const num = Number(value);
  const cur = (currency ?? 'TND').toUpperCase();
  const digits = num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${digits} ${cur}`;
}

export function isMasked(value: string | null | undefined): boolean {
  return typeof value === 'string' && (value.includes('***') || value.startsWith('****'));
}

export function dateOnly(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = iso.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : '—';
}

export function severityVariant(sev?: string | null) {
  switch ((sev ?? '').toLowerCase()) {
    case 'critical': return 'red' as const;
    case 'high': return 'orange' as const;
    case 'medium': return 'yellow' as const;
    case 'low': return 'green' as const;
    default: return 'gray' as const;
  }
}

export function statusVariant(status?: string | null) {
  switch ((status ?? '').toLowerCase()) {
    case 'active': case 'approved': case 'completed': case 'cleared':
    case 'passed': case 'verified': case 'resolved': case 'success':
      return 'green' as const;
    case 'blocked': case 'default': case 'past_due': case 'overdue':
    case 'critical': case 'failed': case 'rejected': case 'escalated':
      return 'red' as const;
    case 'pending': case 'review': case 'under_review': case 'processing':
    case 'under_investigation': case 'acknowledged': case 'assigned': case 'new':
      return 'yellow' as const;
    default: return 'gray' as const;
  }
}

export function riskClassification(score?: number | null): string | null {
  if (score == null) return null;
  if (score >= 0.8) return 'critical';
  if (score >= 0.6) return 'high';
  if (score >= 0.4) return 'medium';
  return 'low';
}
