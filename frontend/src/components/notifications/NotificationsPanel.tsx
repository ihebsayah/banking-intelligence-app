// src/components/notifications/NotificationsPanel.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCheck, ChevronLeft, ChevronRight, Inbox, RefreshCw, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';
import { BankingHeader } from '../Layout/BankingHeader';
import { StatusBadge } from '../ui/StatusBadge';
import { notificationsApi } from '../../api/notificationsApi';
import { parseCaseError } from '../cases/caseErrors';
import { formatDateTime } from '../../utils/formatters';
import {
  notificationEntityLabel,
  notificationEntityRoute,
  notificationTypeLabel,
} from './notificationLabels';
import type { Notification } from '../../types/alerts';

const PER_PAGE = 50;

type Filter = '' | 'true' | 'false';

export function NotificationsPanel() {
  const [items, setItems] = useState<Notification[]>([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<Filter>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [markingId, setMarkingId] = useState<string | null>(null);
  const [markingAll, setMarkingAll] = useState(false);
  const [liveMessage, setLiveMessage] = useState<string | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await notificationsApi.list({
        isRead: filter === '' ? undefined : filter === 'true',
        page,
        perPage: PER_PAGE,
      });
      setItems(res.items);
      setTotal(res.total);
      setUnreadCount(res.unread_count);
    } catch (err) {
      setError(parseCaseError(err).message);
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, filter]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  useEffect(() => {
    if (!liveMessage) return;
    const id = window.setTimeout(() => setLiveMessage(null), 4000);
    return () => window.clearTimeout(id);
  }, [liveMessage]);

  const markRead = async (n: Notification) => {
    if (markingId) return;
    setMarkingId(n.notification_id);
    setActionError(null);
    try {
      const res = await notificationsApi.markRead(n.notification_id);
      const updated = res.notification;
      if (filter === 'false') {
        setItems((prev) => prev.filter((x) => x.notification_id !== n.notification_id));
      } else {
        setItems((prev) => prev.map((x) => (x.notification_id === n.notification_id ? updated : x)));
      }
      if (!n.is_read) setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      setActionError(parseCaseError(err).message);
    } finally {
      setMarkingId(null);
    }
  };

  const markAllRead = async () => {
    if (markingAll) return;
    setMarkingAll(true);
    setActionError(null);
    try {
      const res = await notificationsApi.markAllRead();
      setLiveMessage(
        res.marked_read > 0
          ? `Marked ${res.marked_read} notification${res.marked_read === 1 ? '' : 's'} as read`
          : 'No unread notifications to mark',
      );
      setUnreadCount(0);
      setItems((prev) => prev.map((n) => (n.is_read ? n : { ...n, is_read: true, read_at: new Date().toISOString() })));
    } catch (err) {
      setActionError(parseCaseError(err).message);
    } finally {
      setMarkingAll(false);
    }
  };

  const hasNext = page * PER_PAGE < total;
  const hasFilters = filter !== '';

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title="Workbench — Notifications"
        subtitle={`${unreadCount} unread`}
        onRefresh={fetchItems}
        isRefreshing={loading}
        actions={
          <button
            onClick={markAllRead}
            disabled={markingAll || unreadCount === 0}
            className="btn-ghost text-xs px-2.5 py-1.5 disabled:opacity-40"
          >
            <CheckCheck size={12} />
            {markingAll ? 'Marking...' : 'Mark all read'}
          </button>
        }
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1200px] mx-auto w-full">
        <div role="status" aria-live="polite">
          {liveMessage && (
            <p className="text-xs font-medium" style={{ color: 'var(--accent-green)' }}>{liveMessage}</p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Status
            </span>
            <select
              value={filter}
              onChange={(e) => { setFilter(e.target.value as Filter); setPage(1); }}
              aria-label="Filter by read status"
              className="rounded-lg px-2.5 py-1.5 text-xs outline-none border focus:border-[var(--accent-blue)]"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
            >
              <option value="">All</option>
              <option value="false">Unread</option>
              <option value="true">Read</option>
            </select>
          </div>

          {total > 0 && (
            <span className="text-[10px] font-mono ml-auto" style={{ color: 'var(--text-muted)' }}>
              {total} notification{total === 1 ? '' : 's'}
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
              <div key={i} className="h-16 border rounded-xl animate-pulse"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border p-12 flex flex-col items-center gap-3 text-center"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <Inbox size={28} style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
              {hasFilters ? 'No notifications match the selected filter' : 'No notifications yet'}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {hasFilters ? 'Try switching the filter.' : 'Workflow updates will appear here.'}
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border overflow-hidden"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                    <th className="pl-5 pb-3 font-semibold">Notification</th>
                    <th className="pb-3 font-semibold w-48">Entity</th>
                    <th className="pb-3 font-semibold w-32">Created</th>
                    <th className="pb-3 font-semibold w-28">Status</th>
                    <th className="pr-5 pb-3 font-semibold text-right w-32">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--bg-border)]">
                  {items.map((n) => {
                    const route = notificationEntityRoute(n.entity_type, n.entity_id);
                    return (
                      <tr key={n.notification_id} className={clsx(!n.is_read && 'bg-[rgba(37,99,235,0.04)]')}>
                        <td className="pl-5 py-3.5">
                          <div className="flex flex-col gap-0.5">
                            <span className={clsx(n.is_read ? 'font-normal' : 'font-semibold')}
                              style={{ color: n.is_read ? 'var(--text-secondary)' : 'var(--text-primary)' }}>
                              {n.title || notificationTypeLabel(n.notification_type)}
                            </span>
                            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                              {notificationTypeLabel(n.notification_type)}
                            </span>
                            {n.body && (
                              <p className="text-[11px] truncate max-w-[420px]" style={{ color: 'var(--text-subtle)' }}>{n.body}</p>
                            )}
                          </div>
                        </td>
                        <td className="py-3.5">
                          {route ? (
                            <Link
                              to={route}
                              className="font-medium underline outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-blue)] rounded"
                              style={{ color: 'var(--accent-blue)' }}
                            >
                              {notificationEntityLabel(n.entity_type ?? '')}
                            </Link>
                          ) : n.entity_type ? (
                            <span style={{ color: 'var(--text-secondary)' }}>{notificationEntityLabel(n.entity_type)}</span>
                          ) : (
                            <span style={{ color: 'var(--text-subtle)' }}>—</span>
                          )}
                        </td>
                        <td className="py-3.5 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                          {formatDateTime(n.created_at)}
                        </td>
                        <td className="py-3.5">
                          {n.is_read ? (
                            <StatusBadge variant="gray">Read</StatusBadge>
                          ) : (
                            <StatusBadge variant="blue">Unread</StatusBadge>
                          )}
                        </td>
                        <td className="pr-5 py-3.5 text-right">
                          {!n.is_read && (
                            <button
                              onClick={() => markRead(n)}
                              disabled={markingId === n.notification_id}
                              aria-label={`Mark notification read: ${n.title || n.notification_type}`}
                              className="text-[11px] font-semibold underline outline-none focus-visible:ring-1 rounded disabled:opacity-40"
                              style={{ color: 'var(--accent-blue)' }}
                            >
                              {markingId === n.notification_id ? 'Marking...' : 'Mark read'}
                            </button>
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
                Page {page} · {total} notification{total === 1 ? '' : 's'}
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
