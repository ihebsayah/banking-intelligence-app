// src/components/investigations/InformationRequestsPanel.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ChevronRight, Inbox } from 'lucide-react';
import { clsx } from 'clsx';
import { informationRequestsApi } from '../../api/informationRequestsApi';
import { parseCaseError } from '../cases/caseErrors';
import { IRDetailDialog } from '../cases/dialogs/IRDetailDialog';
import { StatusBadge } from '../ui/StatusBadge';
import { formatDateTime } from '../../utils/formatters';
import type { InformationRequest } from '../../types/cases';

const irStatusVariant: Record<string, 'blue' | 'green' | 'yellow' | 'purple' | 'gray' | 'red'> = {
  open: 'blue',
  acknowledged: 'purple',
  responded: 'yellow',
  accepted: 'green',
  returned: 'yellow',
  cancelled: 'gray',
};

interface Props {
  investigationId: string;
  refreshKey: number;
  onConflict: () => void;
}

export function InformationRequestsPanel({ investigationId, refreshKey, onConflict }: Props) {
  const [items, setItems] = useState<InformationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<InformationRequest | null>(null);

  const fetchItems = useCallback(async () => {
    if (!investigationId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await informationRequestsApi.listForInvestigation(investigationId, { perPage: 50 });
      setItems(res.items);
    } catch (err) {
      setError(parseCaseError(err).message);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  useEffect(() => { fetchItems(); }, [fetchItems, refreshKey]);

  return (
    <div className="rounded-2xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
      <h3 className="text-[10px] font-bold uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
        Information Requests
      </h3>

      {error ? (
        <p className="text-xs" style={{ color: 'var(--accent-red)' }}>{error}</p>
      ) : loading && items.length === 0 ? (
        <div className="space-y-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-10 border rounded-xl animate-pulse"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-6 text-center">
          <Inbox size={20} style={{ color: 'var(--text-muted)' }} />
          <p className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>No information requests</p>
          <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
            Use "Request Additional Information" from the overview action bar to ask the analyst for details.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border divide-y divide-[var(--bg-border)]"
          style={{ borderColor: 'var(--bg-border)' }}>
          {items.map((ir) => (
            <button
              key={ir.ir_id}
              onClick={() => setDetail(ir)}
              className="w-full flex items-center gap-2.5 px-3.5 py-3 text-left transition-colors hover:bg-white/5"
            >
              <ChevronRight size={14} className="flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                  {ir.question ?? 'Information request'}
                </p>
                <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-subtle)' }}>
                  assigned {ir.assigned_to ?? '—'} · created {formatDateTime(ir.created_at)}
                </p>
              </div>
              <StatusBadge variant={irStatusVariant[ir.status] ?? 'gray'}>
                {ir.status.replace(/_/g, ' ')}
              </StatusBadge>
            </button>
          ))}
          <p className={clsx('text-[10px] px-3.5 py-2', items.length > 0 && 'border-t')} style={{ color: 'var(--text-muted)' }}>
            {items.length} request{items.length === 1 ? '' : 's'}
          </p>
        </div>
      )}

      <IRDetailDialog
        open={detail !== null}
        ir={detail}
        onClose={() => setDetail(null)}
        onMutated={fetchItems}
        onConflict={() => { setDetail(null); onConflict(); }}
      />
    </div>
  );
}