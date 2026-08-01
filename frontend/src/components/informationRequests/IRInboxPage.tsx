// src/components/informationRequests/IRInboxPage.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, RefreshCw, AlertTriangle, Inbox } from 'lucide-react';
import { clsx } from 'clsx';
import { BankingHeader } from '../Layout/BankingHeader';
import { StatusBadge } from '../ui/StatusBadge';
import { informationRequestsApi } from '../../api/informationRequestsApi';
import { parseCaseError } from '../cases/caseErrors';
import { useAuth } from '../../auth/AuthProvider';
import { formatDateTime } from '../../utils/formatters';
import { IRResponseDialog } from './IRResponseDialog';
import type { InformationRequest } from '../../types/cases';

const PER_PAGE = 50;

const STATUSES = ['open', 'acknowledged', 'responded', 'returned'];

const irStatusVariant: Record<string, 'blue' | 'green' | 'yellow' | 'purple' | 'gray' | 'red'> = {
  open: 'blue',
  acknowledged: 'purple',
  responded: 'yellow',
  accepted: 'green',
  returned: 'yellow',
  cancelled: 'gray',
};

function isOverdue(ir: InformationRequest): boolean {
  if (!ir.due_date) return false;
  if (ir.status === 'accepted' || ir.status === 'cancelled') return false;
  return new Date(ir.due_date).getTime() < Date.now();
}

export function IRInboxPage() {
  const navigate = useNavigate();
  const { applicationUser } = useAuth();

  const [items, setItems] = useState<InformationRequest[]>([]);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<InformationRequest | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await informationRequestsApi.listAssigned({
        status: status || undefined,
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
  }, [page, status]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  const hasNext = items.length === PER_PAGE;

  const handleSuccess = (updated: InformationRequest, close: boolean) => {
    setSelected(close ? null : updated);
    fetchItems();
  };

  const handleConflict = useCallback(async () => {
    if (!selected) return;
    try {
      const latest = await informationRequestsApi.get(selected.ir_id);
      setSelected(latest);
    } catch {
      // Keep the stale view; the list refresh below still runs.
    }
    fetchItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.ir_id]);

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title="Workbench — Information Requests"
        subtitle="Information requests assigned to you"
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

          {items.length > 0 && (
            <span className="text-[10px] font-mono ml-auto" style={{ color: 'var(--text-muted)' }}>
              {items.length} request{items.length === 1 ? '' : 's'}
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
            <Inbox size={28} style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
              No information requests assigned to you
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {status ? 'Try adjusting the filters.' : 'Compliance requests for your cases will appear here.'}
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                    <th className="pl-5 pb-3 font-semibold w-40">Case</th>
                    <th className="pb-3 font-semibold">Question</th>
                    <th className="pb-3 font-semibold w-32">Due date</th>
                    <th className="pb-3 font-semibold w-28">Status</th>
                    <th className="pr-5 pb-3 font-semibold text-right w-36">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--bg-border)]">
                  {items.map((ir) => {
                    const overdue = isOverdue(ir);
                    return (
                      <tr
                        key={ir.ir_id}
                        onClick={() => setSelected(ir)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setSelected(ir);
                          }
                        }}
                        tabIndex={0}
                        aria-label={`Open information request ${ir.ir_id}`}
                        className={clsx('cursor-pointer transition-all outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)]',
                          overdue && 'hover:bg-[rgba(220,38,38,0.04)]')}
                      >
                        <td className="pl-5 py-3.5">
                          <div className="flex flex-col gap-0.5">
                            <Link
                              to={`/workbench/cases/${ir.case_id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="font-mono underline hover:brightness-90 outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-blue)] rounded"
                              style={{ color: 'var(--accent-blue)' }}
                            >
                              {ir.case_id}
                            </Link>
                            <span className="font-mono text-[10px]" style={{ color: 'var(--text-subtle)' }}>
                              {ir.assigned_to === applicationUser?.user_id ? 'assigned to you' : `assigned ${ir.assigned_to ?? '—'}`} · v{ir.version}
                            </span>
                          </div>
                        </td>
                        <td className="py-3.5">
                          <span className="font-medium line-clamp-2" style={{ color: 'var(--text-primary)' }}>
                            {ir.question ?? 'Information request'}
                          </span>
                          {overdue && (
                            <span className="block text-[10px] font-bold uppercase tracking-wider mt-0.5" style={{ color: 'var(--accent-red)' }}>
                              overdue
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 font-mono text-[10px]" style={{ color: overdue ? 'var(--accent-red)' : 'var(--text-muted)' }}>
                          {ir.due_date ?? '—'}
                        </td>
                        <td className="py-3.5">
                          <StatusBadge variant={irStatusVariant[ir.status] ?? 'gray'}>
                            {ir.status.replace(/_/g, ' ')}
                          </StatusBadge>
                        </td>
                        <td className="pr-5 py-3.5 text-right font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                          {formatDateTime(ir.updated_at)}
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
                Page {page} · {items.length} request{items.length === 1 ? '' : 's'} shown
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

      <IRResponseDialog
        open={selected !== null}
        ir={selected}
        onClose={() => setSelected(null)}
        onSuccess={handleSuccess}
        onConflict={handleConflict}
      />
    </div>
  );
}
