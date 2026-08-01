// src/components/investigations/TimelineTab.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, History } from 'lucide-react';
import { clsx } from 'clsx';
import { investigationsApi } from '../../api/investigationsApi';
import { parseInvestigationError } from './investigationErrors';
import { formatDateTime } from '../../utils/formatters';
import type { TimelineEntry } from '../../types/investigations';

const PER_PAGE = 50;

function humanise(eventType: string): string {
  return eventType.replace(/^investigation\./, '').replace(/_/g, ' ');
}

function deltaSummary(entry: TimelineEntry): string | null {
  const oldStatus = entry.old_value?.status;
  const newStatus = entry.new_value?.status;
  if (typeof oldStatus === 'string' || typeof newStatus === 'string') {
    return `status ${String(oldStatus ?? '—')} → ${String(newStatus ?? '—')}`;
  }
  return null;
}

export function TimelineTab({ investigationId }: { investigationId: string }) {
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTimeline = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await investigationsApi.listTimeline(investigationId, page, PER_PAGE);
      setEntries(res.items);
    } catch (err) {
      setError(parseInvestigationError(err).message);
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [investigationId, page]);

  useEffect(() => { fetchTimeline(); }, [fetchTimeline]);

  const hasNext = entries.length === PER_PAGE;

  return (
    <div className="space-y-4">
      {error ? (
        <div className="rounded-2xl border p-8 text-center text-sm"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
          {error}
        </div>
      ) : loading && entries.length === 0 ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-12 border rounded-xl animate-pulse"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <div className="rounded-2xl border p-10 flex flex-col items-center gap-3 text-center"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
          <History size={24} style={{ color: 'var(--text-muted)' }} />
          <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>No activity recorded yet</p>
        </div>
      ) : (
        <div className="rounded-2xl border divide-y divide-[var(--bg-border)]"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
          {entries.map((t) => {
            const delta = deltaSummary(t);
            return (
              <div key={t.timeline_id} className="p-4 flex items-start gap-3">
                <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
                  style={{ background: 'var(--accent-blue)' }} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {humanise(t.event_type)}
                  </p>
                  {delta && (
                    <p className="font-mono text-[10px] mt-0.5" style={{ color: 'var(--text-subtle)' }}>
                      {delta}
                    </p>
                  )}
                  <p className="text-[10px] mt-1" style={{ color: 'var(--text-subtle)' }}>
                    actor <span className="font-mono">{t.actor_id}</span> · {formatDateTime(t.occurred_at)}
                  </p>
                </div>
              </div>
            );
          })}

          <div className="flex items-center justify-between border-t px-5 py-3.5"
            style={{ borderColor: 'var(--bg-border)' }}>
            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              Page {page} · {entries.length} event{entries.length === 1 ? '' : 's'} shown
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                aria-label="Previous timeline page"
                className={clsx('p-1.5 rounded-lg border transition-all', page === 1 && 'opacity-30 pointer-events-none')}
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}
              >
                <ChevronLeft size={14} />
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!hasNext}
                aria-label="Next timeline page"
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
  );
}
