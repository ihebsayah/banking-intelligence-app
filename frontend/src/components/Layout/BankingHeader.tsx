// src/components/Layout/BankingHeader.tsx
import React from 'react';
import { RefreshCw, Clock } from 'lucide-react';
import { formatRelativeTime } from '../../utils/formatters';

interface Props {
  title: string;
  subtitle?: string;
  lastRefreshed?: string | null;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  actions?: React.ReactNode;
}

export function BankingHeader({ title, subtitle, lastRefreshed, onRefresh, isRefreshing, actions }: Props) {
  return (
    <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0"
      style={{ borderColor: 'var(--bg-border)', background: 'var(--bg-primary)' }}>
      <div>
        <h1 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{title}</h1>
        {subtitle && <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{subtitle}</p>}
      </div>

      <div className="flex items-center gap-2">
        {lastRefreshed && (
          <div className="hidden md:flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
            <Clock size={12} />
            <span>{formatRelativeTime(lastRefreshed)}</span>
          </div>
        )}

        {onRefresh && (
          <button onClick={onRefresh} disabled={isRefreshing} className="btn-ghost text-xs px-2.5 py-1.5">
            <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        )}

        {actions}
      </div>
    </div>
  );
}
