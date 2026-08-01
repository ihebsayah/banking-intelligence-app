// src/components/cases/CaseQueuePage.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, RefreshCw, Scale, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';
import { BankingHeader } from '../Layout/BankingHeader';
import { casesApi } from '../../api/casesApi';
import { CasePriorityBadge, CaseRiskBadge, CaseStatusBadge } from './CaseBadges';
import { parseCaseError } from './caseErrors';
import { useAuth } from '../../auth/AuthProvider';
import { formatDateTime } from '../../utils/formatters';
import type { Case } from '../../types/cases';

const PER_PAGE = 50;

const STATUSES = ['open', 'assigned', 'under_review', 'awaiting_information', 'decision_pending', 'awaiting_compliance_action', 'resolved', 'closed', 'cancelled'];
const PRIORITIES = ['critical', 'high', 'medium', 'low'];

function isOverdue(c: Case): boolean {
  if (!c.target_date) return false;
  if (c.status === 'resolved' || c.status === 'closed') return false;
  return new Date(c.target_date).getTime() < Date.now();
}

export function CaseQueuePage() {
  const navigate = useNavigate();
  const { applicationUser } = useAuth();

  const [items, setItems] = useState<Case[]>([]);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [priority, setPriority] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await casesApi.listAssigned({
        status: status || undefined,
        priority: priority || undefined,
        page,
        perPage: PER_PAGE,
      });
      setItems(res.items);
    } catch (err) {
      setError(parseCaseError(err).message);
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
        title="Workbench — Case Queue"
        subtitle="Compliance cases assigned to you"
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
              {items.length} case{items.length === 1 ? '' : 's'}
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
            <Scale size={28} style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
              No cases assigned to you
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {status || priority ? 'Try adjusting the filters.' : 'Cases escalated from your alerts will appear here.'}
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                    <th className="pl-5 pb-3 font-semibold">Case</th>
                    <th className="pb-3 font-semibold w-24">Risk</th>
                    <th className="pb-3 font-semibold w-24">Priority</th>
                    <th className="pb-3 font-semibold w-32">Status</th>
                    <th className="pb-3 font-semibold w-36">Target date</th>
                    <th className="pr-5 pb-3 font-semibold text-right w-36">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--bg-border)]">
                  {items.map((c) => {
                    const overdue = isOverdue(c);
                    return (
                      <tr
                        key={c.case_id}
                        onClick={() => navigate(`/workbench/cases/${c.case_id}`)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            navigate(`/workbench/cases/${c.case_id}`);
                          }
                        }}
                        tabIndex={0}
                        aria-label={`Open case ${c.title}`}
                        className={clsx('cursor-pointer transition-all outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)]',
                          overdue && 'hover:bg-[rgba(220,38,38,0.04)]')}
                      >
                        <td className="pl-5 py-3.5">
                          <div className="flex flex-col gap-0.5">
                            <span className="font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                              {c.title}
                              {overdue && (
                                <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--accent-red)' }}>
                                  overdue
                                </span>
                              )}
                            </span>
                            <span className="font-mono text-[10px]" style={{ color: 'var(--text-subtle)' }}>
                              {c.assigned_to === applicationUser?.user_id ? 'assigned to you' : `assigned ${c.assigned_to ?? '—'}`} · v{c.version}
                            </span>
                          </div>
                        </td>
                        <td className="py-3.5">
                          <CaseRiskBadge riskLevel={c.risk_level} />
                        </td>
                        <td className="py-3.5">
                          <CasePriorityBadge priority={c.priority} />
                        </td>
                        <td className="py-3.5">
                          <CaseStatusBadge status={c.status} />
                        </td>
                        <td className="py-3.5 font-mono text-[10px]" style={{ color: overdue ? 'var(--accent-red)' : 'var(--text-muted)' }}>
                          {c.target_date ?? '—'}
                        </td>
                        <td className="pr-5 py-3.5 text-right font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                          {formatDateTime(c.updated_at)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between border-t px-5 py-3.5"
              style={{ borderColor: 'var(--bg-border)' }}>
              <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                Page {page} · {items.length} case{items.length === 1 ? '' : 's'} shown
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
