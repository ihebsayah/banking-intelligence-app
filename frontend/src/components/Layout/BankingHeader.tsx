// src/components/Layout/BankingHeader.tsx
import React from 'react';
import { RefreshCw, Clock, Wifi } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
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
  const { user } = useAuthStore();

  return (
    <header className="flex items-center justify-between h-16 px-6 bg-[#06101e]/90 border-b border-[#0f2040] backdrop-blur-sm flex-shrink-0">
      {/* Left: title */}
      <div>
        <h1 className="text-base font-semibold text-white leading-tight">{title}</h1>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>

      {/* Right: status + refresh + actions + user */}
      <div className="flex items-center gap-3">
        {/* Live indicator */}
        <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-500">
          <Wifi size={12} className="text-emerald-500" />
          <span>Live</span>
        </div>

        {/* Last refreshed */}
        {lastRefreshed && (
          <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-500 bg-[#0a1628] border border-[#1a2d4e] rounded-lg px-3 py-1.5">
            <Clock size={12} />
            <span>{formatRelativeTime(lastRefreshed)}</span>
          </div>
        )}

        {/* Refresh button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white bg-[#0a1628] hover:bg-[#0d1f3c] border border-[#1a2d4e] rounded-lg px-3 py-1.5 transition-all disabled:opacity-50"
          >
            <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        )}

        {/* Custom actions */}
        {actions}

        {/* User chip */}
        {user && (
          <div className="flex items-center gap-2 bg-[#0a1628] border border-[#1a2d4e] rounded-lg px-3 py-1.5">
            <div className="w-5 h-5 rounded-full bg-gradient-to-br from-[#0066CC] to-[#003366] flex items-center justify-center text-[10px] font-bold text-white">
              {user.name?.charAt(0).toUpperCase() ?? 'A'}
            </div>
            <span className="text-xs text-slate-300 hidden md:inline">{user.name}</span>
            <span className="text-[10px] text-slate-600 hidden lg:inline capitalize">· {user.role}</span>
          </div>
        )}
      </div>
    </header>
  );
}
