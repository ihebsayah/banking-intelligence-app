// src/components/cases/CaseInformationRequestsTab.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight, Inbox } from 'lucide-react';
import { clsx } from 'clsx';
import { casesApi } from '../../api/casesApi';
import { parseCaseError } from './caseErrors';
import { IRAcceptReturnDialog } from './dialogs/IRAcceptReturnDialog';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { StatusBadge } from '../ui/StatusBadge';
import { formatDateTime } from '../../utils/formatters';
import type { InformationRequest } from '../../types/cases';

const PER_PAGE = 50;

const irStatusVariant: Record<string, 'blue' | 'green' | 'yellow' | 'purple' | 'gray' | 'red'> = {
  open: 'blue',
  acknowledged: 'purple',
  responded: 'yellow',
  accepted: 'green',
  returned: 'yellow',
  cancelled: 'gray',
};

interface Props {
  caseId: string;
  refreshKey: number;
  onConflict: () => void;
}

export function CaseInformationRequestsTab({ caseId, refreshKey, onConflict }: Props) {
  const { hasPermission } = useAuth();
  const canAccept = hasPermission(PERMISSIONS.INFO_REQUEST_ACCEPT);
  const canReturn = hasPermission(PERMISSIONS.INFO_REQUEST_RETURN);

  const [items, setItems] = useState<InformationRequest[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [action, setAction] = useState<{ mode: 'accept' | 'return'; ir: InformationRequest } | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await casesApi.listInformationRequests(caseId, page, PER_PAGE);
      setItems(res.items);
    } catch (err) {
      setError(parseCaseError(err).message);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [caseId, page]);

  useEffect(() => { fetchItems(); }, [fetchItems, refreshKey]);

  const hasNext = items.length === PER_PAGE;

  return (
    <div className="space-y-4">
      {error ? (
        <div className="rounded-2xl border p-8 text-center text-sm"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
          {error}
        </div>
      ) : loading && items.length === 0 ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-14 border rounded-xl animate-pulse"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border p-10 flex flex-col items-center gap-3 text-center"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
          <Inbox size={24} style={{ color: 'var(--text-muted)' }} />
          <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>No information requests</p>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Use "Request Information" from the Overview action bar to ask an analyst for details.
          </p>
        </div>
      ) : (
        <div className="rounded-2xl border divide-y divide-[var(--bg-border)]"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
          {items.map((ir) => {
            const isOpen = expanded === ir.ir_id;
            return (
              <div key={ir.ir_id}>
                <button
                  onClick={() => setExpanded(isOpen ? null : ir.ir_id)}
                  aria-expanded={isOpen}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/5"
                >
                  {isOpen ? <ChevronDown size={14} className="flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
                    : <ChevronRight size={14} className="flex-shrink-0" style={{ color: 'var(--text-muted)' }} />}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                      {ir.question ?? 'Information request'}
                    </p>
                    <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-subtle)' }}>
                      {ir.assigned_to ? <>assigned {ir.assigned_to} · </> : null}
                      {ir.due_date ? <>due {ir.due_date} · </> : null}
                      created {formatDateTime(ir.created_at)}
                    </p>
                  </div>
                  <StatusBadge variant={irStatusVariant[ir.status] ?? 'gray'}>
                    {ir.status.replace(/_/g, ' ')}
                  </StatusBadge>
                </button>

                {isOpen && (
                  <div className="px-4 pb-4 pl-11 space-y-3">
                    <div className="rounded-lg border px-3 py-2" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                      <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                        {ir.question}
                      </p>
                    </div>

                    {ir.response_text && (
                      <div className="rounded-lg border px-3 py-2" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                        <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Response</p>
                        <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                          {ir.response_text}
                        </p>
                      </div>
                    )}

                    {ir.return_reason && (
                      <div className="rounded-lg border px-3 py-2" style={{ background: 'rgba(217,119,6,0.08)', borderColor: 'rgba(217,119,6,0.3)' }}>
                        <p className="text-[10px] font-bold uppercase tracking-wider mb-0.5" style={{ color: 'var(--accent-amber)' }}>Returned</p>
                        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{ir.return_reason}</p>
                      </div>
                    )}

                    {ir.status === 'responded' && (
                      <div className="flex items-center gap-2">
                        {canAccept && (
                          <button
                            onClick={() => setAction({ mode: 'accept', ir })}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                            style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
                          >
                            Accept Response
                          </button>
                        )}
                        {canReturn && (
                          <button
                            onClick={() => setAction({ mode: 'return', ir })}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                            style={{ background: 'rgba(217,119,6,0.9)', color: 'var(--text-primary)' }}
                          >
                            Return Response
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          <div className="flex items-center justify-between border-t px-5 py-3.5"
            style={{ borderColor: 'var(--bg-border)' }}>
            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              Page {page} · {items.length} request{items.length === 1 ? '' : 's'} shown
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                aria-label="Previous information requests page"
                className={clsx('p-1.5 rounded-lg border transition-all', page === 1 && 'opacity-30 pointer-events-none')}
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}
              >
                <ChevronLeft size={14} />
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!hasNext}
                aria-label="Next information requests page"
                className={clsx('p-1.5 rounded-lg border transition-all', !hasNext && 'opacity-30 pointer-events-none')}
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}
              >
                <ChevronRight size={14} />              </button>
            </div>
          </div>
        </div>
      )}

      <IRAcceptReturnDialog
        open={action !== null}
        mode={action?.mode ?? 'accept'}
        ir={action?.ir ?? null}
        onClose={() => setAction(null)}
        onSuccess={() => { setAction(null); fetchItems(); }}
        onConflict={() => { setAction(null); onConflict(); }}
      />
    </div>
  );
}
