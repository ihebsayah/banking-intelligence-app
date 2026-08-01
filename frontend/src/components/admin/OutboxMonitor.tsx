// src/components/admin/OutboxMonitor.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, ChevronLeft, ChevronRight, Inbox, RefreshCw, RotateCcw } from 'lucide-react';
import { clsx } from 'clsx';
import { BankingHeader } from '../Layout/BankingHeader';
import { StatusBadge } from '../ui/StatusBadge';
import { Modal } from '../ui/Modal';
import { adminOutboxApi } from '../../api/adminOutboxApi';
import { parseCaseError } from '../cases/caseErrors';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { formatDateTime } from '../../utils/formatters';
import type { AuditOutboxEvent } from '../../types/alerts';

const PER_PAGE = 50;

export const OUTBOX_STATUSES = ['pending', 'delivering', 'delivered', 'failed', 'poison'] as const;

const STATUS_VARIANTS: Record<string, 'blue' | 'yellow' | 'green' | 'orange' | 'red' | 'gray'> = {
  pending: 'blue',
  delivering: 'yellow',
  delivered: 'green',
  failed: 'orange',
  poison: 'red',
};

export function outboxStatusVariant(status: string): 'blue' | 'yellow' | 'green' | 'orange' | 'red' | 'gray' {
  return STATUS_VARIANTS[status] ?? 'gray';
}

export function outboxStatusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function shortId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}…` : id;
}

export function OutboxMonitor() {
  const { hasPermission } = useAuth();
  const [items, setItems] = useState<AuditOutboxEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [confirmRow, setConfirmRow] = useState<AuditOutboxEvent | null>(null);
  const [retrying, setRetrying] = useState(false);

  const canRetry = hasPermission(PERMISSIONS.ADMIN_OUTBOX_RETRY);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminOutboxApi.list({
        status: status || undefined,
        page,
        perPage: PER_PAGE,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(parseCaseError(err).message);
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, status]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  useEffect(() => {
    if (!successMessage) return;
    const id = window.setTimeout(() => setSuccessMessage(null), 4000);
    return () => window.clearTimeout(id);
  }, [successMessage]);

  const confirmRetry = async () => {
    if (!confirmRow || retrying) return;
    setRetrying(true);
    setActionError(null);
    try {
      await adminOutboxApi.retry(confirmRow.outbox_id);
      setConfirmRow(null);
      setSuccessMessage('Retry queued — event returned to pending.');
      fetchItems();
    } catch (err) {
      setActionError(parseCaseError(err).message);
      setConfirmRow(null);
    } finally {
      setRetrying(false);
    }
  };

  const hasNext = page * PER_PAGE < total;
  const hasFilters = status !== '';

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title="Admin — Outbox Monitor"
        subtitle="Audit delivery status for outbound events"
        onRefresh={fetchItems}
        isRefreshing={loading}
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
        <div role="status" aria-live="polite">
          {successMessage && (
            <p className="text-xs font-medium" style={{ color: 'var(--accent-green)' }}>{successMessage}</p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
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
              {OUTBOX_STATUSES.map((s) => (
                <option key={s} value={s}>{outboxStatusLabel(s)}</option>
              ))}
            </select>
          </div>

          {total > 0 && (
            <span className="text-[10px] font-mono ml-auto" style={{ color: 'var(--text-muted)' }}>
              {total} event{total === 1 ? '' : 's'}
            </span>
          )}
        </div>

        {actionError && (
          <div className="rounded-xl border px-4 py-2.5 flex items-center gap-2"
            style={{ background: 'rgba(220,38,38,0.05)', borderColor: 'var(--accent-red)' }}>
            <AlertTriangle size={13} style={{ color: 'var(--accent-red)' }} />
            <p className="text-xs" style={{ color: 'var(--accent-red)' }}>{actionError}</p>
          </div>
        )}

        {error ? (
          <div className="rounded-2xl border p-10 flex flex-col items-center gap-4"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <AlertTriangle size={28} style={{ color: 'var(--accent-red)' }} />
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{error}</p>
            <button
              onClick={fetchItems}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold shadow-md hover:brightness-90 transition-all"
              style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
            >
              <RefreshCw size={14} />
              Retry
            </button>
          </div>
        ) : loading && items.length === 0 ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-12 border rounded-xl animate-pulse"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border p-12 flex flex-col items-center gap-3 text-center"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <Inbox size={28} style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
              {hasFilters ? 'No outbox events match the selected status' : 'No outbox events'}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {hasFilters ? 'Try clearing the filter.' : 'Audit delivery events will appear here.'}
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                    <th className="pl-5 pb-3 font-semibold w-28">Event</th>
                    <th className="pb-3 font-semibold w-28">Entity</th>
                    <th className="pb-3 font-semibold w-28">Entity ID</th>
                    <th className="pb-3 font-semibold w-28">Status</th>
                    <th className="pb-3 font-semibold w-20">Attempts</th>
                    <th className="pb-3 font-semibold">Last error</th>
                    <th className="pb-3 font-semibold w-32">Created</th>
                    <th className="pb-3 font-semibold w-32">Delivered</th>
                    <th className="pr-5 pb-3 font-semibold text-right w-24">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--bg-border)]">
                  {items.map((row) => {
                    const isPoison = row.status === 'poison';
                    const retryable = (row.status === 'failed' || isPoison) && canRetry;
                    return (
                      <tr key={row.outbox_id}
                        className={clsx(isPoison && 'bg-[rgba(220,38,38,0.05)]')}>
                        <td className="pl-5 py-3.5">
                          <div className="flex flex-col gap-0.5">
                            <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{row.event_type}</span>
                            <span className="text-[10px] font-mono" style={{ color: 'var(--text-subtle)' }}>
                              {shortId(row.outbox_id)}
                            </span>
                          </div>
                        </td>
                        <td className="py-3.5">
                          <span className="capitalize" style={{ color: 'var(--text-secondary)' }}>{row.entity_type}</span>
                        </td>
                        <td className="py-3.5 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>{row.entity_id}</td>
                        <td className="py-3.5">
                          <StatusBadge variant={outboxStatusVariant(row.status)}>
                            {outboxStatusLabel(row.status)}
                          </StatusBadge>
                        </td>
                        <td className="py-3.5 font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                          {row.attempt_count}
                        </td>
                        <td className="py-3.5">
                          <div className="flex flex-col gap-0.5 max-w-[300px]">
                            {row.last_error ? (
                              <>
                                <p className="font-mono text-[10px] truncate" style={{ color: isPoison ? 'var(--accent-red)' : 'var(--text-muted)' }}>
                                  {row.last_error}
                                </p>
                                {isPoison && row.poison_reason && (
                                  <p className="text-[10px]" style={{ color: 'var(--accent-red)' }}>
                                    <span className="font-bold">Poison:</span> {row.poison_reason}
                                  </p>
                                )}
                              </>
                            ) : (
                              <span style={{ color: 'var(--text-subtle)' }}>—</span>
                            )}
                          </div>
                        </td>
                        <td className="py-3.5 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                          {formatDateTime(row.created_at)}
                        </td>
                        <td className="py-3.5 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                          {row.delivered_at ? formatDateTime(row.delivered_at) : '—'}
                        </td>
                        <td className="pr-5 py-3.5 text-right">
                          {retryable ? (
                            <button
                              onClick={() => setConfirmRow(row)}
                              aria-label={`Retry outbox event ${row.outbox_id}`}
                              className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-lg border transition-all outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)]"
                              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
                            >
                              <RotateCcw size={11} />
                              Retry
                            </button>
                          ) : (
                            <span className="text-[10px]" style={{ color: 'var(--text-subtle)' }}>—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between border-t px-5 py-3.5"
              style={{ borderColor: 'var(--bg-border)' }}>
              <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                Page {page} · {total} event{total === 1 ? '' : 's'}
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

      <Modal
        open={confirmRow !== null}
        title="Retry outbox event"
        onClose={() => { if (!retrying) setConfirmRow(null); }}
        footer={
          <>
            <button onClick={() => setConfirmRow(null)} disabled={retrying} className="btn-ghost text-xs px-3 py-1.5">
              Cancel
            </button>
            <button
              onClick={confirmRetry}
              disabled={retrying}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold shadow-md hover:brightness-90 transition-all disabled:opacity-40"
              style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
            >
              <RotateCcw size={12} />
              {retrying ? 'Queuing...' : 'Confirm retry'}
            </button>
          </>
        }
      >
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          This resets the event to <span className="font-semibold">pending</span>, resets its attempt count, and clears
          any poison reason so the outbox worker can redeliver it. The originating business action is
          <span className="font-semibold"> not</span> replayed.
        </p>
        {confirmRow && (
          <dl className="mt-3 space-y-1.5">
            {[
              ['Event', confirmRow.event_type],
              ['Outbox ID', confirmRow.outbox_id],
              ['Status', outboxStatusLabel(confirmRow.status)],
              ['Attempts', String(confirmRow.attempt_count)],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4">
                <dt className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{k}</dt>
                <dd className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>{v}</dd>
              </div>
            ))}
          </dl>
        )}
      </Modal>
    </div>
  );
}
