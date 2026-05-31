// src/components/dashboard/KPICard.tsx
import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { clsx } from 'clsx';
import type { KPI } from '../../types/dashboard';
import { formatKPIValue, formatPercent } from '../../utils/formatters';

interface Props {
  kpi: KPI;
  onClick?: () => void;
  loading?: boolean;
}

const METRIC_COLORS: Record<string, { bg: string; border: string; icon: string; glow: string }> = {
  total_deposits:  { bg: 'bg-blue-500/8',    border: 'border-blue-500/15',   icon: 'text-blue-400',    glow: 'shadow-[0_0_20px_rgba(59,130,246,0.08)]' },
  monthly_revenue: { bg: 'bg-emerald-500/8', border: 'border-emerald-500/15', icon: 'text-emerald-400', glow: 'shadow-[0_0_20px_rgba(16,185,129,0.08)]' },
  active_customers:{ bg: 'bg-violet-500/8',  border: 'border-violet-500/15',  icon: 'text-violet-400',  glow: 'shadow-[0_0_20px_rgba(139,92,246,0.08)]' },
  avg_risk_score:  { bg: 'bg-amber-500/8',   border: 'border-amber-500/15',   icon: 'text-amber-400',   glow: 'shadow-[0_0_20px_rgba(245,158,11,0.08)]' },
};

function Skeleton() {
  return (
    <div className="rounded-xl border border-[#0f2040] bg-[#08111e] p-5 animate-pulse">
      <div className="h-3 w-24 bg-[#0d1f3c] rounded mb-4" />
      <div className="h-8 w-32 bg-[#0d1f3c] rounded mb-3" />
      <div className="h-3 w-20 bg-[#0d1f3c] rounded" />
    </div>
  );
}

export function KPICard({ kpi, onClick, loading }: Props) {
  if (loading) return <Skeleton />;

  const colors = METRIC_COLORS[kpi.kpi_id] ?? {
    bg: 'bg-slate-500/8', border: 'border-slate-500/15', icon: 'text-slate-400', glow: ''
  };

  const isUp   = kpi.trend_direction === 'up';
  const isDown = kpi.trend_direction === 'down';
  const trendColor = isUp ? 'text-emerald-400' : isDown ? 'text-red-400' : 'text-slate-500';
  const TrendIcon  = isUp ? TrendingUp : isDown ? TrendingDown : Minus;

  // For risk score, down is GOOD (lower risk)
  const isRisk = kpi.kpi_id === 'avg_risk_score';
  const trendLabel = isRisk
    ? (isDown ? 'Risk improving' : 'Risk increasing')
    : (isUp ? 'vs last period' : 'vs last period');

  return (
    <div
      onClick={onClick}
      className={clsx(
        'rounded-xl border p-5 transition-all duration-200',
        colors.bg, colors.border, colors.glow,
        onClick && 'cursor-pointer hover:scale-[1.01] hover:brightness-110'
      )}
    >
      <p className="text-xs font-medium text-slate-400 mb-3">{kpi.name}</p>
      <p className="text-3xl font-bold text-white tracking-tight mb-2">
        {formatKPIValue(kpi.value, kpi.metric_type)}
      </p>
      <div className="flex items-center gap-1.5">
        <TrendIcon size={13} className={clsx(trendColor)} />
        <span className={clsx('text-xs font-medium', trendColor)}>
          {formatPercent(Math.abs(kpi.trend))}
        </span>
        <span className="text-xs text-slate-600">{trendLabel}</span>
      </div>
      <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between">
        <span className="text-[10px] text-slate-600 capitalize">{kpi.data_freshness} data</span>
        {onClick && <span className="text-[10px] text-[#4d9fff] hover:text-[#66b3ff]">Details →</span>}
      </div>
    </div>
  );
}
