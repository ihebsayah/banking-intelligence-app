// src/components/notifications/NotificationBell.tsx
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bell, CheckCheck, Inbox, RefreshCw } from 'lucide-react';
import { clsx } from 'clsx';
import { notificationsApi } from '../../api/notificationsApi';
import { PERMISSIONS } from '../../lib/permissions';
import { formatRelativeTime } from '../../utils/formatters';
import {
  notificationEntityLabel,
  notificationEntityRoute,
  notificationTypeLabel,
} from './notificationLabels';
import type { Notification } from '../../types/alerts';

const POLL_INTERVAL_MS = 30_000;

interface Props {
  /** Permissions of the current user (auth-store permissions in both modes). */
  permissions?: string[];
}

export function NotificationBell({ permissions }: Props) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [markingAll, setMarkingAll] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const canRead = permissions?.includes(PERMISSIONS.NOTIFICATION_READ) ?? false;

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await notificationsApi.list({ perPage: 10 });
      setItems(res.items);
      setUnread(res.unread_count);
    } catch {
      setError('Could not load notifications.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Frozen 4.2: poll on window focus + 30s interval for the unread badge.
  useEffect(() => {
    if (!canRead) return;
    refresh();
    const id = window.setInterval(refresh, POLL_INTERVAL_MS);
    const onFocus = () => { refresh(); };
    window.addEventListener('focus', onFocus);
    return () => {
      window.clearInterval(id);
      window.removeEventListener('focus', onFocus);
    };
  }, [canRead, refresh]);

  // Close on outside click + Escape.
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!canRead) return null;

  const badge = unread > 99 ? '99+' : String(unread);

  const markAllRead = async () => {
    if (markingAll) return;
    setMarkingAll(true);
    try {
      await notificationsApi.markAllRead();
      setUnread(0);
      setItems((prev) => prev.map((n) => (n.is_read ? n : { ...n, is_read: true, read_at: new Date().toISOString() })));
    } catch {
      // Keep existing state; the dropdown keeps its current data.
    } finally {
      setMarkingAll(false);
    }
  };

  const toggle = () => {
    if (open) {
      setOpen(false);
    } else {
      refresh();
      setOpen(true);
    }
  };

  return (
    <div className="relative" ref={bellRef}>
      <button
        ref={buttonRef}
        onClick={toggle}
        aria-label={`Notifications, ${unread} unread`}
        aria-haspopup="dialog"
        aria-expanded={open}
        className="relative p-2 rounded-lg transition-colors duration-150 outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)]"
        style={{ color: 'var(--text-muted)' }}
      >
        <Bell size={15} />
        {unread > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full flex items-center justify-center text-[9px] font-bold leading-none"
            style={{ background: 'var(--accent-red)', color: '#fff' }}
          >
            {badge}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Recent notifications"
          className="absolute right-0 top-full mt-1 w-80 rounded-xl shadow-lg border z-50 animate-fade-in"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
        >
          <div className="flex items-center justify-between px-4 py-2.5 border-b"
            style={{ borderColor: 'var(--bg-border)' }}>
            <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
              Notifications
            </span>
            <button
              onClick={markAllRead}
              disabled={markingAll || unread === 0}
              className="flex items-center gap-1 text-[11px] font-medium transition-colors outline-none focus-visible:ring-1 rounded disabled:opacity-40"
              style={{ color: 'var(--accent-blue)' }}
            >
              <CheckCheck size={12} />
              {markingAll ? 'Marking...' : 'Mark all read'}
            </button>
          </div>

          <div className="max-h-80 overflow-y-auto py-1">
            {loading && items.length === 0 ? (
              <div className="space-y-2 p-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-10 rounded-lg animate-pulse" style={{ background: 'var(--bg-tertiary)' }} />
                ))}
              </div>
            ) : error && items.length === 0 ? (
              <div className="p-6 flex flex-col items-center gap-3 text-center">
                <RefreshCw size={18} style={{ color: 'var(--text-muted)' }} />
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{error}</p>
                <button
                  onClick={refresh}
                  className="text-[11px] font-semibold underline outline-none focus-visible:ring-1 rounded"
                  style={{ color: 'var(--accent-blue)' }}
                >
                  Retry
                </button>
              </div>
            ) : items.length === 0 ? (
              <div className="p-6 flex flex-col items-center gap-2 text-center">
                <Inbox size={18} style={{ color: 'var(--text-muted)' }} />
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>No notifications</p>
              </div>
            ) : (
              items.map((n) => {
                const route = notificationEntityRoute(n.entity_type, n.entity_id);
                return (
                  <div
                    key={n.notification_id}
                    className={clsx('px-4 py-2.5 border-b last:border-0', !n.is_read && 'bg-[rgba(37,99,235,0.05)]')}
                    style={{ borderColor: 'var(--bg-border)' }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span
                        className={clsx('text-xs', n.is_read ? 'font-normal' : 'font-semibold')}
                        style={{ color: n.is_read ? 'var(--text-secondary)' : 'var(--text-primary)' }}
                      >
                        {n.title || notificationTypeLabel(n.notification_type)}
                      </span>
                      <span className="text-[10px] font-mono flex-shrink-0" style={{ color: 'var(--text-subtle)' }}>
                        {formatRelativeTime(n.created_at)}
                      </span>
                    </div>
                    {n.body && (
                      <p className="text-[11px] mt-0.5 truncate" style={{ color: 'var(--text-subtle)' }}>{n.body}</p>
                    )}
                    {route ? (
                      <Link
                        to={route}
                        onClick={() => setOpen(false)}
                        className="text-[11px] font-medium underline outline-none focus-visible:ring-1 rounded"
                        style={{ color: 'var(--accent-blue)' }}
                      >
                        {notificationEntityLabel(n.entity_type ?? '')}
                      </Link>
                    ) : (
                      n.entity_type && (
                        <span className="text-[11px]" style={{ color: 'var(--text-subtle)' }}>
                          {notificationEntityLabel(n.entity_type)}
                        </span>
                      )
                    )}
                  </div>
                );
              })
            )}
          </div>

          <div className="border-t px-4 py-2" style={{ borderColor: 'var(--bg-border)' }}>
            <button
              onClick={() => { setOpen(false); navigate('/notifications'); }}
              className="w-full text-xs font-semibold text-center outline-none focus-visible:ring-1 rounded"
              style={{ color: 'var(--accent-blue)' }}
            >
              View all notifications
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
