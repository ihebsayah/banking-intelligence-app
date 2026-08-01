// src/components/approvals/ApprovalQueuePage.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight, RefreshCw, AlertTriangle, Inbox } from 'lucide-react';
import { clsx } from 'clsx';
import { BankingHeader } from '../Layout/BankingHeader';
import { StatusBadge } from '../ui/StatusBadge';
import { approvalsApi } from '../../api/approvalsApi';
import { parseCaseError } from '../cases/caseErrors';
import { formatDateTime } from '../../utils/formatters';
import { ApprovalDetailDialog } from './ApprovalDetailDialog';
import {
  APPROVAL_ACTION_TYPES, APPROVAL_STATUSES, approvalActionLabel,
  approvalEntityLabel, approvalEntityRoute, approvalStatusVariant,
} from './approvalLabels';
import type { ApprovalRequest } from '../../types/alerts';

const PER_PAGE = 50;

function isTimeExpired(item: ApprovalRequest): boolean {
  return item.status === 'pending' && new Date(item.expires_at).getTime() <= Date.now();
}

function statusText(item: ApprovalRequest): string {
  if (item.status === 'expired') return 'Expired';
  if (isTimeExpired(item)) return 'Expired';
  if (item.status === 'approved' && item.executed_at) return 'Executed';
  if (item.status === 'approved') return 'Approved — awaiting execution';
  return item.status.charAt(0).toUpperCase() + item.status.slice(1);
}

export function ApprovalQueuePage() {
  const [items, setItems] = useState<ApprovalRequest[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [actionType, setActionType] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await approvalsApi.list({
        status: status || undefined,
        actionType: actionType || undefined,
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
  }, [page, status, actionType]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  const hasNext = page * PER_PAGE < total;
  const hasFilters = !!status || !!actionType;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title="Workbench — Approvals"
        subtitle="Four-eyes approval requests in your scope"
        onRefresh={fetchItems}
        isRefreshing={loading}
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
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
              {APPROVAL_STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Action type
            </span>
            <select
              value={actionType}
              onChange={(e) => { setActionType(e.target.value); setPage(1); }}
              aria-label="Filter by action type"
              className="rounded-lg px-2.5 py-1.5 text-xs outline-none border focus:border-[var(--accent-blue)]"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
            >
              <option value="">All action types</option>
              {APPROVAL_ACTION_TYPES.map((a) => (
                <option key={a} value={a}>{approvalActionLabel(a)}</option>
              ))}
            </select>
          </div>

          {items.length > 0 && (
            <span className="text-[10px] font-mono ml-auto" style={{ color: 'var(--text-muted)' }}>
              {total} request{total === 1 ? '' : 's'}
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
              {hasFilters ? 'No approval requests match the selected filters' : 'No approval requests in your scope'}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {hasFilters ? 'Try adjusting the filters.' : 'Approval requests created from alert dismissal, case closure and decisions will appear here.'}
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                    <th className="pl-5 pb-3 font-semibold">Action type</th>
                    <th className="pb-3 font-semibold w-52">Entity</th>
                    <th className="pb-3 font-semibold w-36">Requested by</th>
                    <th className="pb-3 font-semibold w-32">Status</th>
                    <th className="pb-3 font-semibold w-28">Approvals</th>
                    <th className="pb-3 font-semibold w-32">Expires</th>
                    <th className="pr-5 pb-3 font-semibold text-right w-32">Requested</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--bg-border)]">
                  {items.map((item) => {
                    const route = approvalEntityRoute(item.entity_type, item.entity_id);
                    const expired = isTimeExpired(item);
                    return (
                      <tr
                        key={item.approval_request_id}
                        onClick={() => setSelectedId(item.approval_request_id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setSelectedId(item.approval_request_id);
                          }
                        }}
                        tabIndex={0}
                        aria-label={`Open approval request ${item.approval_request_id}`}
                        className="cursor-pointer transition-all outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)] hover:bg-[rgba(37,99,235,0.03)]"
                      >
                        <td className="pl-5 py-3.5">
                          <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
                            {approvalActionLabel(item.action_type)}
                          </span>
                        </td>
                        <td className="py-3.5">
                          <div className="flex flex-col gap-0.5">
                            {route ? (
                              <Link
                                to={route}
                                onClick={(e) => e.stopPropagation()}
                                className="font-mono underline hover:brightness-90 outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-blue)] rounded"
                                style={{ color: 'var(--accent-blue)' }}
                              >
                                {item.entity_id}
                              </Link>
                            ) : (
                              <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>{item.entity_id}</span>
                            )}
                            <span className="text-[10px]" style={{ color: 'var(--text-subtle)' }}>
                              {approvalEntityLabel(item.entity_type)}
                            </span>
                          </div>
                        </td>
                        <td className="py-3.5 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                          {item.requested_by}
                        </td>
                        <td className="py-3.5">
                          <StatusBadge variant={approvalStatusVariant(item.status)}>
                            {statusText(item)}
                          </StatusBadge>
                        </td>
                        <td className="py-3.5 font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                          {item.approval_count} / {item.required_approvals}
                        </td>
                        <td className={clsx('py-3.5 font-mono text-[10px]', expired && 'font-bold')}
                          style={{ color: expired ? 'var(--accent-red)' : 'var(--text-muted)' }}>
                          {expired ? 'Expired' : formatDateTime(item.expires_at)}
                        </td>
                        <td className="pr-5 py-3.5 text-right font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                          {formatDateTime(item.created_at)}
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
                Page {page} · {total} request{total === 1 ? '' : 's'}
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

      <ApprovalDetailDialog
        open={selectedId !== null}
        approvalId={selectedId}
        onClose={() => setSelectedId(null)}
        onSuccess={fetchItems}
        onConflict={fetchItems}
      />
    </div>
  );
}
