// src/components/investigations/InvestigationQueuePage.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, RefreshCw, FolderSearch, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';
import { BankingHeader } from '../Layout/BankingHeader';
import { investigationsApi } from '../../api/investigationsApi';
import { InvestigationPriorityBadge, InvestigationStatusBadge } from './InvestigationBadges';
import { parseInvestigationError } from './investigationErrors';
import { formatDateTime } from '../../utils/formatters';
import type { Investigation } from '../../types/investigations';

const PER_PAGE = 50;

const STATUSES = ['open', 'active', 'awaiting_information', 'submitted', 'returned', 'completed', 'cancelled'];
const PRIORITIES = ['critical', 'high', 'medium', 'low'];

export function InvestigationQueuePage() {
  const navigate = useNavigate();

  const [items, setItems] = useState<Investigation[]>([]);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [priority, setPriority] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await investigationsApi.listAssigned({
        status: status || undefined,
        priority: priority || undefined,
        page,
        perPage: PER_PAGE,
      });
      setItems(res.items);
    } catch (err) {
      setError(parseInvestigationError(err).message);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [page, status, priority]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  const hasNext = items.length === PER_PAGE;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title="Workbench — Investigation Queue"
        subtitle="Investigations assigned to you"
        onRefresh={fetchItems}
        isRefreshing={loading}
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {/* Filter bar */}
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
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Priority
            </span>
            <select
              value={priority}
              onChange={(e) => { setPriority(e.target.value); setPage(1); }}
              aria-label="Filter by priority"
              className="rounded-lg px-2.5 py-1.5 text-xs outline-none border focus:border-[var(--accent-blue)]"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
            >
              <option value="">All priorities</option>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
              ))}
            </select>
          </div>

          {items.length > 0 && (
            <span className="text-[10px] font-mono ml-auto" style={{ color: 'var(--text-muted)' }}>
              {items.length} investigation{items.length === 1 ? '' : 's'}
            </span>
          )}
        </div>

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
              <div key={i} className="h-14 border rounded-xl animate-pulse"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border p-12 flex flex-col items-center gap-3 text-center"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <FolderSearch size={28} style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
              No investigations assigned to you
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {status || priority ? 'Try adjusting the filters.' : 'Investigations created from your alerts will appear here.'}
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                    <th className="pl-5 pb-3 font-semibold">Investigation</th>
                    <th className="pb-3 font-semibold w-28">Priority</th>
                    <th className="pb-3 font-semibold w-40">Status</th>
                    <th className="pb-3 font-semibold w-36">Started</th>
                    <th className="pb-3 font-semibold w-36">Submitted</th>
                    <th className="pr-5 pb-3 font-semibold text-right w-36">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--bg-border)]">
                  {items.map((inv) => (
                    <tr
                      key={inv.investigation_id}
                      onClick={() => navigate(`/workbench/investigations/${inv.investigation_id}`)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          navigate(`/workbench/investigations/${inv.investigation_id}`);
                        }
                      }}
                      tabIndex={0}
                      aria-label={`Open investigation ${inv.title}`}
                      className="cursor-pointer hover:bg-white/5 transition-all outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)]"
                    >
                      <td className="pl-5 py-3.5">
                        <div className="flex flex-col gap-0.5">
                          <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{inv.title}</span>
                          <span className="font-mono text-[10px]" style={{ color: 'var(--text-subtle)' }}>
                            {inv.alert_id ? <>alert #{inv.alert_id.slice(0, 8)}</> : 'no linked alert'} · v{inv.version}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5">
                        <InvestigationPriorityBadge priority={inv.priority} />
                      </td>
                      <td className="py-3.5">
                        <InvestigationStatusBadge status={inv.status} />
                      </td>
                      <td className="py-3.5 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                        {inv.started_at ? formatDateTime(inv.started_at) : '—'}
                      </td>
                      <td className="py-3.5 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                        {inv.submitted_at ? formatDateTime(inv.submitted_at) : '—'}
                      </td>
                      <td className="pr-5 py-3.5 text-right font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                        {formatDateTime(inv.updated_at)}
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
                Page {page} · {items.length} investigation{items.length === 1 ? '' : 's'} shown
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
