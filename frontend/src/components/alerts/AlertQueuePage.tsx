// src/components/alerts/AlertQueuePage.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, RefreshCw, BellOff, AlertTriangle, ShieldAlert } from 'lucide-react';
import { clsx } from 'clsx';
import { BankingHeader } from '../Layout/BankingHeader';
import { alertsApi } from '../../api/alertsApi';
import { AlertSeverityBadge, AlertStatusBadge } from './AlertBadges';
import { parseAlertError } from './alertErrors';
import { formatDateTime } from '../../utils/formatters';
import type { Alert } from '../../types/alerts';

const PER_PAGE = 50;

const SEVERITIES = ['critical', 'high', 'medium', 'low'];
const STATUSES = ['new', 'assigned', 'acknowledged', 'under_investigation', 'resolved', 'dismissed'];

export function AlertQueuePage() {
  const navigate = useNavigate();

  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [page, setPage] = useState(1);
  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await alertsApi.listAssigned({
        severity: severity || undefined,
        status: status || undefined,
        page,
        perPage: PER_PAGE,
      });
      setAlerts(res.items);
    } catch (err) {
      setError(parseAlertError(err).message);
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, [page, severity, status]);

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

  const hasNext = alerts.length === PER_PAGE;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title="Workbench — Alert Queue"
        subtitle="Alerts assigned to you"
        onRefresh={fetchAlerts}
        isRefreshing={loading}
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {/* Filter bar */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Severity
            </span>
            <select
              value={severity}
              onChange={(e) => { setSeverity(e.target.value); setPage(1); }}
              aria-label="Filter by severity"
              className="rounded-lg px-2.5 py-1.5 text-xs outline-none border focus:border-[var(--accent-blue)]"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
            >
              <option value="">All severities</option>
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Status
            </span>
            <select
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1); }}
              aria-label="Filter by status"
              className="rounded-lg px-2.5 py-1.5 text-xs outline-none border focus:border-[var(--accent-blue)]"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
            >
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>

          {alerts.length > 0 && (
            <span className="text-[10px] font-mono ml-auto" style={{ color: 'var(--text-muted)' }}>
              {alerts.length} alert{alerts.length === 1 ? '' : 's'}
            </span>
          )}
        </div>

        {error ? (
          <div className="rounded-2xl border p-10 flex flex-col items-center gap-4"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <AlertTriangle size={28} style={{ color: 'var(--accent-red)' }} />
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{error}</p>
            <button
              onClick={fetchAlerts}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold shadow-md hover:brightness-90 transition-all"
              style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
            >
              <RefreshCw size={14} />
              Retry
            </button>
          </div>
        ) : loading && alerts.length === 0 ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-14 border rounded-xl animate-pulse"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
            ))}
          </div>
        ) : alerts.length === 0 ? (
          <div className="rounded-2xl border p-12 flex flex-col items-center gap-3 text-center"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <BellOff size={28} style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
              No alerts assigned to you
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {severity || status ? 'Try adjusting the filters.' : 'New alerts will appear here as they are assigned.'}
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                    <th className="pl-5 pb-3 font-semibold w-28">Severity</th>
                    <th className="pb-3 font-semibold">Alert</th>
                    <th className="pb-3 font-semibold w-40">Assigned To</th>
                    <th className="pb-3 font-semibold w-40">Status</th>
                    <th className="pr-5 pb-3 font-semibold text-right w-36">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--bg-border)]">
                  {alerts.map((a) => (
                    <tr
                      key={a.alert_id}
                      onClick={() => navigate(`/workbench/alerts/${a.alert_id}`)}
                      className="cursor-pointer hover:bg-white/5 transition-all"
                      style={{ background: a.severity === 'critical' ? 'rgba(220,38,38,0.04)' : undefined }}
                    >
                      <td className="pl-5 py-3.5">
                        <AlertSeverityBadge severity={a.severity} />
                      </td>
                      <td className="py-3.5">
                        <div className="flex flex-col gap-0.5">
                          <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{a.title}</span>
                          <span className="font-mono text-[10px]" style={{ color: 'var(--text-subtle)' }}>
                            {a.alert_type} · #{a.alert_id.slice(0, 8)}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5">
                        <span className="flex items-center gap-1.5 font-mono text-[10px]"
                          style={{ color: 'var(--text-muted)' }}>
                          <ShieldAlert size={12} style={{ color: 'var(--accent-blue)' }} />
                          {a.assigned_to ?? '—'}
                        </span>
                      </td>
                      <td className="py-3.5">
                        <AlertStatusBadge status={a.status} />
                      </td>
                      <td className="pr-5 py-3.5 text-right font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                        {formatDateTime(a.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between border-t px-5 py-3.5"
              style={{ borderColor: 'var(--bg-border)' }}>
              <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                Page {page} · {alerts.length} alert{alerts.length === 1 ? '' : 's'} shown
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  aria-label="Previous page"
                  className={clsx('p-1.5 rounded-lg border transition-all', page === 1 && 'opacity-30 pointer-events-none')}
                  style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}
                >
                  <ChevronLeft size={14} />
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={!hasNext}
                  aria-label="Next page"
                  className={clsx('p-1.5 rounded-lg border transition-all', !hasNext && 'opacity-30 pointer-events-none')}
                  style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
