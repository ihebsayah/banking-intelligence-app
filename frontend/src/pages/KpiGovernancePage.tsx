// src/pages/KpiGovernancePage.tsx
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { kpiApi } from '../api/kpiApi';
import { BankingHeader } from '../components/Layout/BankingHeader';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { formatKPIValue } from '../utils/formatters';
import type { KpiDashboard, KpiCatalogEntry, KpiDetail, KpiInsight } from '../types/api';
import {
  Activity, AlertTriangle, BookOpen, CheckCircle2, ChevronDown, ChevronRight, ChevronUp,
  Circle, Filter, Layers, Lightbulb, RefreshCw, Search, Shield, TrendingDown, TrendingUp,
  Minus, XCircle, User, X, Info, BarChart2, Clock
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area
} from 'recharts';
import { clsx } from 'clsx';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  profitability:   { bg: 'bg-blue-500/10',    text: 'text-blue-400',    border: 'border-blue-500/20'   },
  liquidity:       { bg: 'bg-cyan-500/10',     text: 'text-cyan-400',    border: 'border-cyan-500/20'   },
  credit_quality:  { bg: 'bg-amber-500/10',   text: 'text-amber-400',   border: 'border-amber-500/20'  },
  capital:         { bg: 'bg-purple-500/10',  text: 'text-purple-400',  border: 'border-purple-500/20' },
  operational:     { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20'},
  customer:        { bg: 'bg-pink-500/10',    text: 'text-pink-400',    border: 'border-pink-500/20'   },
  compliance:      { bg: 'bg-orange-500/10',  text: 'text-orange-400',  border: 'border-orange-500/20' },
};

function categoryStyle(cat: string) {
  return CATEGORY_COLORS[cat] ?? { bg: 'bg-slate-500/10', text: 'text-slate-400', border: 'border-slate-500/20' };
}

const EVAL_CONFIG = {
  healthy:  { label: 'Healthy',  icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
  warning:  { label: 'Warning',  icon: AlertTriangle, color: 'text-amber-400',  bg: 'bg-amber-500/10',  border: 'border-amber-500/20'  },
  critical: { label: 'Critical', icon: XCircle,       color: 'text-red-400',    bg: 'bg-red-500/10',    border: 'border-red-500/20'    },
  unknown:  { label: 'N/A',      icon: Circle,        color: 'text-slate-500',  bg: 'bg-slate-500/10',  border: 'border-slate-500/20'  },
};

function evalConfig(ev?: string) {
  return EVAL_CONFIG[(ev as keyof typeof EVAL_CONFIG) ?? 'unknown'] ?? EVAL_CONFIG.unknown;
}

function TrendIcon({ dir }: { dir?: string }) {
  if (dir === 'up')   return <TrendingUp size={12} className="text-emerald-400" />;
  if (dir === 'down') return <TrendingDown size={12} className="text-red-400" />;
  return <Minus size={12} className="text-slate-500" />;
}

function Pill({ label, ev }: { label: string; ev?: string }) {
  const c = evalConfig(ev);
  const Icon = c.icon;
  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold border uppercase tracking-wider', c.bg, c.color, c.border)}>
      <Icon size={9} /> {label}
    </span>
  );
}

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

// ─── Summary cards ────────────────────────────────────────────────────────────

interface SummaryCardProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  accent: string;
  sub?: string;
}
function SummaryCard({ label, value, icon, accent, sub }: SummaryCardProps) {
  return (
    <div className={clsx('rounded-2xl border bg-[#050b14]/50 p-5 flex flex-col gap-3 hover:border-[#1e3459] transition-all', accent)}>
      <div className="flex items-start justify-between">
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</p>
        <div className="opacity-60">{icon}</div>
      </div>
      <p className="text-3xl font-bold text-white tracking-tight">{value}</p>
      {sub && <p className="text-[10px] text-slate-600">{sub}</p>}
    </div>
  );
}

// ─── KPI Row ─────────────────────────────────────────────────────────────────

interface KpiRowProps {
  entry: KpiCatalogEntry;
  liveKpi?: { value: number | null; trend_direction?: string; threshold_evaluation?: string };
  onSelect: (id: string) => void;
  selected: boolean;
}

function KpiRow({ entry, liveKpi, onSelect, selected }: KpiRowProps) {
  const catStyle = categoryStyle(entry.category);
  const ev = liveKpi?.threshold_evaluation ?? (entry.status === 'unavailable' ? 'unknown' : 'unknown');
  const evalCfg = evalConfig(ev);
  const EvalIcon = evalCfg.icon;

  return (
    <tr
      onClick={() => onSelect(entry.kpi_id)}
      className={clsx(
        'cursor-pointer transition-all border-b border-[#0f2244]/50',
        selected ? 'bg-[#0066CC]/10 border-[#0066CC]/20' : 'hover:bg-[#0c1930]/25'
      )}
    >
      {/* KPI ID */}
      <td className="py-3.5 pl-4 font-mono text-[10px] text-slate-400 select-all">
        <span className="font-bold">{entry.kpi_id}</span>
      </td>

      {/* Name + description */}
      <td className="py-3.5 pr-4">
        <p className="text-xs font-semibold text-slate-200 leading-tight">{entry.name}</p>
        {entry.description && (
          <p className="text-[10px] text-slate-500 mt-0.5 line-clamp-1">{entry.description}</p>
        )}
      </td>

      {/* Category */}
      <td className="py-3.5 pr-4">
        <span className={clsx('px-1.5 py-0.5 rounded text-[9px] font-bold border uppercase tracking-wider', catStyle.bg, catStyle.text, catStyle.border)}>
          {entry.category_name ?? entry.category}
        </span>
      </td>

      {/* Live value */}
      <td className="py-3.5 pr-4 text-right">
        {entry.status === 'unavailable' ? (
          <span className="text-[10px] text-slate-600 italic">Unavailable</span>
        ) : liveKpi?.value != null ? (
          <div className="flex items-center justify-end gap-1.5">
            <TrendIcon dir={liveKpi.trend_direction} />
            <span className="text-xs font-bold text-white font-mono">
              {formatKPIValue(liveKpi.value ?? 0, entry.metric_type as any)}
            </span>
          </div>
        ) : (
          <Skeleton className="h-4 w-16 ml-auto" />
        )}
      </td>

      {/* Threshold */}
      <td className="py-3.5 pr-4">
        {entry.status === 'unavailable' ? (
          <span className="text-[9px] text-slate-700">—</span>
        ) : (
          <span className={clsx('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold border uppercase', evalCfg.bg, evalCfg.color, evalCfg.border)}>
            <EvalIcon size={9} />
            {evalCfg.label}
          </span>
        )}
      </td>

      {/* Owner */}
      <td className="py-3.5 pr-4">
        {entry.owner_name ? (
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded-full bg-[#0066CC]/20 border border-[#0066CC]/30 flex items-center justify-center text-[9px] font-bold text-[#4d9fff]">
              {entry.owner_name.charAt(0)}
            </div>
            <span className="text-[10px] text-slate-400">{entry.owner_name}</span>
          </div>
        ) : (
          <span className="text-[9px] text-slate-700">—</span>
        )}
      </td>

      {/* Arrow */}
      <td className="py-3.5 pr-4">
        <ChevronRight size={12} className={clsx('transition-colors', selected ? 'text-[#4d9fff]' : 'text-slate-600 group-hover:text-slate-400')} />
      </td>
    </tr>
  );
}

// ─── Detail Panel ─────────────────────────────────────────────────────────────

interface DetailPanelProps {
  kpiId: string;
  entry?: KpiCatalogEntry;
  onClose: () => void;
}

function DetailPanel({ kpiId, entry, onClose }: DetailPanelProps) {
  const [detail, setDetail] = useState<KpiDetail | null>(null);
  const [insight, setInsight] = useState<KpiInsight | null>(null);
  const [trends, setTrends] = useState<Array<{ month: string; value?: number }>>([]);
  const [loading, setLoading] = useState(true);
  const [insightLoading, setInsightLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setInsightLoading(true);
    setDetail(null);
    setInsight(null);
    setTrends([]);

    kpiApi.getDetail(kpiId).then(d => { setDetail(d); setLoading(false); }).catch(() => setLoading(false));

    kpiApi.getInsights(kpiId).then(i => { setInsight(i); setInsightLoading(false); }).catch(() => setInsightLoading(false));

    if (entry?.status !== 'unavailable') {
      kpiApi.getTrends(12, kpiId).then(t => {
        // Backend may return generic trends or kpi-specific
        setTrends((t.trends as any[]).map(r => ({
          month: r.month,
          value: r.value ?? r.fee_revenue ?? null,
        })).filter(r => r.value != null));
      }).catch(() => {});
    }
  }, [kpiId]);

  const ev = detail?.threshold_evaluation ?? 'unknown';
  const evalCfg = evalConfig(ev);
  const EvalIcon = evalCfg.icon;
  const catStyle = categoryStyle(entry?.category ?? '');

  return (
    <div className="fixed inset-y-0 right-0 w-[420px] z-50 flex flex-col bg-[#06101e] border-l border-[#0f2040] shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between p-5 border-b border-[#0f2040] flex-shrink-0">
        <div>
          <p className="font-mono text-[10px] text-slate-500 mb-1">{kpiId}</p>
          <h2 className="text-sm font-bold text-white leading-snug">
            {loading ? <Skeleton className="h-4 w-40" /> : (detail?.name ?? entry?.name)}
          </h2>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors mt-0.5 ml-3 flex-shrink-0">
          <X size={16} />
        </button>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">

        {/* Status + eval row */}
        <div className="flex items-center gap-2 flex-wrap">
          {entry?.category && (
            <span className={clsx('px-2 py-0.5 rounded text-[9px] font-bold border uppercase tracking-wider', catStyle.bg, catStyle.text, catStyle.border)}>
              {entry.category_name ?? entry.category}
            </span>
          )}
          {loading ? <Skeleton className="h-5 w-20" /> : (
            <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold border uppercase tracking-wider', evalCfg.bg, evalCfg.color, evalCfg.border)}>
              <EvalIcon size={9} /> {evalCfg.label}
            </span>
          )}
          {detail?.status === 'unavailable' && (
            <span className="px-2 py-0.5 rounded text-[9px] font-bold border uppercase bg-slate-500/10 text-slate-400 border-slate-500/20">
              Data Unavailable
            </span>
          )}
        </div>

        {/* Value card */}
        <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Current Value</p>
          {loading ? <Skeleton className="h-8 w-28" /> : (
            detail?.value != null ? (
              <p className="text-3xl font-bold text-white font-mono">
                {formatKPIValue(detail.value ?? 0, detail.metric_type as any)}
              </p>
            ) : (
              <p className="text-sm text-slate-600 italic">{detail?.unavailable_reason ?? 'No data available'}</p>
            )
          )}
        </div>

        {/* Trend sparkline */}
        {trends.length > 0 && (
          <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <BarChart2 size={10} /> 12-Month Trend
            </p>
            <div className="h-24">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trends} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="kpiGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#0066CC" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#0066CC" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="2 2" stroke="#0f2040" />
                  <XAxis dataKey="month" tick={{ fill: '#475569', fontSize: 9 }} axisLine={false} tickLine={false} />
                  <YAxis hide />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0a1628', border: '1px solid #1a2d4e', borderRadius: '6px', fontSize: '11px', color: '#e2e8f0' }}
                    formatter={(v: number) => [formatKPIValue(v, detail?.metric_type as any ?? 'count'), 'Value']}
                  />
                  <Area type="monotone" dataKey="value" stroke="#0066CC" strokeWidth={2} fill="url(#kpiGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Formula */}
        {(entry?.formula ?? detail?.formula) && (
          <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Layers size={10} /> Formula
            </p>
            <p className="font-mono text-[11px] text-[#4d9fff] leading-relaxed break-words">
              {entry?.formula_display ?? entry?.formula ?? detail?.formula}
            </p>
          </div>
        )}

        {/* Thresholds */}
        {detail?.thresholds && (
          <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <Shield size={10} /> Governance Thresholds
            </p>
            <div className="space-y-2">
              {[
                { label: 'Critical', min: detail.thresholds.critical_min, max: detail.thresholds.critical_max, lbl: detail.thresholds.critical_label, cls: 'text-red-400 border-red-500/20 bg-red-500/5' },
                { label: 'Warning',  min: detail.thresholds.warning_min,  max: detail.thresholds.warning_max,  lbl: detail.thresholds.warning_label,  cls: 'text-amber-400 border-amber-500/20 bg-amber-500/5' },
                { label: 'Healthy',  min: detail.thresholds.healthy_min,  max: detail.thresholds.healthy_max,  lbl: detail.thresholds.healthy_label,  cls: 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5' },
              ].map(t => (
                <div key={t.label} className={clsx('flex items-center justify-between px-3 py-2 rounded-lg border text-[10px]', t.cls)}>
                  <span className="font-semibold uppercase tracking-wider">{t.label}</span>
                  <span className="font-mono">
                    {t.min != null && t.max != null ? `${t.min} – ${t.max}` :
                     t.min != null ? `≥ ${t.min}` :
                     t.max != null ? `≤ ${t.max}` : t.lbl ?? '—'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Owner */}
        {entry?.owner_name && (
          <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <User size={10} /> KPI Owner
            </p>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#0066CC]/20 border border-[#0066CC]/30 flex items-center justify-center text-[11px] font-bold text-[#4d9fff]">
                {entry.owner_name.charAt(0)}
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-200">{entry.owner_name}</p>
                {entry.owner_email && <p className="text-[10px] text-slate-500 font-mono">{entry.owner_email}</p>}
                {entry.owner_role && <p className="text-[9px] text-slate-600 capitalize mt-0.5">{entry.owner_role}</p>}
              </div>
            </div>
          </div>
        )}

        {/* AI Insights */}
        <div className="rounded-xl border border-[#1a3a5c] bg-gradient-to-br from-[#051830]/60 to-[#050b14]/40 p-4">
          <p className="text-[10px] text-[#4d9fff] uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Lightbulb size={10} className="text-yellow-400" /> AI Intelligence Insight
          </p>
          {insightLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
              <Skeleton className="h-3 w-3/5" />
            </div>
          ) : insight ? (
            <div className="space-y-3">
              <p className="text-[11px] text-slate-300 leading-relaxed">{insight.explanation}</p>
              {insight.suggested_actions && insight.suggested_actions.length > 0 && (
                <div>
                  <p className="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">Suggested Actions</p>
                  <ul className="space-y-1">
                    {insight.suggested_actions.map((action, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-[10px] text-slate-400">
                        <ChevronRight size={10} className="text-[#4d9fff] mt-0.5 flex-shrink-0" />
                        {action}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {insight.risk_level && (
                <div className="flex items-center gap-2 pt-1 border-t border-[#0f2040]/50">
                  <Info size={10} className="text-slate-500" />
                  <span className="text-[10px] text-slate-500">Risk Level: <span className="text-slate-300 capitalize">{insight.risk_level}</span></span>
                </div>
              )}
            </div>
          ) : (
            <p className="text-[11px] text-slate-600 italic">Insight service unavailable for this KPI.</p>
          )}
        </div>

        {/* Changelog */}
        {detail?.history && detail.history.length > 0 && (
          <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <Clock size={10} /> Change History
            </p>
            <div className="space-y-2">
              {detail.history.map((h, i) => (
                <div key={i} className="flex items-start justify-between text-[10px] pb-2 border-b border-[#0f2040]/30 last:border-0 last:pb-0">
                  <div>
                    <span className="text-slate-400">{h.change_type}</span>
                    <span className="text-slate-600 mx-1">by</span>
                    <span className="text-slate-400 font-mono">{h.changed_by}</span>
                  </div>
                  <span className="text-slate-600 font-mono">{new Date(h.changed_at).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function KpiGovernancePage() {
  const [dashboard, setDashboard] = useState<KpiDashboard | null>(null);
  const [catalog, setCatalog] = useState<KpiCatalogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiFailed, setApiFailed] = useState(false);

  // Filters
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [evalFilter, setEvalFilter] = useState('');

  // UI
  const [selectedKpi, setSelectedKpi] = useState<string | null>(null);
  const [sortField, setSortField] = useState<'name' | 'category' | 'value' | 'eval'>('category');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const load = useCallback(async () => {
    setLoading(true);
    setApiFailed(false);
    try {
      const [dash, cat] = await Promise.all([kpiApi.getDashboard(), kpiApi.getCatalog()]);
      setDashboard(dash);
      setCatalog(cat);
    } catch {
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Build live-value map from dashboard KPIs
  const liveMap = useMemo(() => {
    const m: Record<string, { value: number | null; trend_direction?: string; threshold_evaluation?: string }> = {};
    dashboard?.kpis.forEach(k => { m[k.kpi_id] = { value: k.value, trend_direction: k.trend_direction, threshold_evaluation: k.threshold_evaluation }; });
    return m;
  }, [dashboard]);

  // Categories for filter dropdown
  const categories = useMemo(() => {
    const seen = new Set<string>();
    catalog.forEach(e => { if (e.category) seen.add(e.category); });
    return Array.from(seen).sort();
  }, [catalog]);

  // Filtered + sorted rows
  const filtered = useMemo(() => {
    let rows = [...catalog];
    const q = search.toLowerCase();
    if (q) rows = rows.filter(r =>
      r.name.toLowerCase().includes(q) ||
      r.kpi_id.toLowerCase().includes(q) ||
      (r.description ?? '').toLowerCase().includes(q) ||
      r.category.toLowerCase().includes(q)
    );
    if (categoryFilter) rows = rows.filter(r => r.category === categoryFilter);
    if (statusFilter)   rows = rows.filter(r => r.status === statusFilter);
    if (evalFilter)     rows = rows.filter(r => {
      const ev = liveMap[r.kpi_id]?.threshold_evaluation ?? 'unknown';
      return ev === evalFilter;
    });

    rows.sort((a, b) => {
      let cmp = 0;
      if (sortField === 'name')     cmp = a.name.localeCompare(b.name);
      if (sortField === 'category') cmp = a.category.localeCompare(b.category);
      if (sortField === 'value') {
        const av = liveMap[a.kpi_id]?.value ?? -Infinity;
        const bv = liveMap[b.kpi_id]?.value ?? -Infinity;
        cmp = av - bv;
      }
      if (sortField === 'eval') {
        const order = { critical: 0, warning: 1, healthy: 2, unknown: 3 };
        const ae = order[(liveMap[a.kpi_id]?.threshold_evaluation ?? 'unknown') as keyof typeof order] ?? 3;
        const be = order[(liveMap[b.kpi_id]?.threshold_evaluation ?? 'unknown') as keyof typeof order] ?? 3;
        cmp = ae - be;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [catalog, liveMap, search, categoryFilter, statusFilter, evalFilter, sortField, sortDir]);

  function toggleSort(field: typeof sortField) {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('asc'); }
  }

  function SortIcon({ field }: { field: typeof sortField }) {
    if (sortField !== field) return <Minus size={9} className="opacity-30" />;
    return sortDir === 'asc' ? <ChevronUp size={10} /> : <ChevronDown size={10} />;
  }

  const selectedEntry = selectedKpi ? catalog.find(e => e.kpi_id === selectedKpi) : undefined;

  if (apiFailed) {
    return (
      <div className="min-h-screen bg-[#040711] flex flex-col">
        <BankingHeader
          title="KPI Governance Center"
          subtitle="Banking KPI Governance & Intelligence Framework"
          onRefresh={load}
          isRefreshing={loading}
        />
        <div className="flex-1 p-6 max-w-4xl mx-auto w-full space-y-6">
          <ServiceUnavailable
            serviceName="KPI Governance Service"
            missingEndpoint="GET /kpi/dashboard"
            method="GET"
          />
          <div className="flex justify-center">
            <button
              onClick={load}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#0066CC] hover:bg-[#0052a3] text-white text-sm font-semibold shadow-lg shadow-[#0066CC]/20 transition-all"
            >
              <RefreshCw size={16} className={clsx(loading && 'animate-spin')} />
              Retry Connection
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="KPI Governance Center"
        subtitle="Banking KPI Governance & Intelligence Framework — Formulas, Thresholds, Ownership & Insights"
        onRefresh={load}
        isRefreshing={loading}
      />

      <div className={clsx('flex-1 flex flex-col overflow-hidden transition-all duration-300', selectedKpi ? 'mr-[420px]' : '')}>
        <div className="flex-1 p-6 space-y-7 overflow-y-auto max-w-[1600px] mx-auto w-full">

          {/* ── Summary band ─────────────────────────────────────────────── */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {loading ? Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-28 rounded-2xl border border-[#0f2040] bg-[#050b14]/50 animate-pulse" />
            )) : dashboard ? (
              <>
                <SummaryCard label="Total KPIs" value={dashboard.total_kpis} icon={<Layers size={18} className="text-blue-400" />} accent="border-[#0f2040]" sub="In governance catalog" />
                <SummaryCard label="Active KPIs" value={dashboard.active_kpis} icon={<Activity size={18} className="text-emerald-400" />} accent="border-emerald-500/20" sub="Computed from live data" />
                <SummaryCard label="Unavailable" value={dashboard.unavailable_kpis} icon={<Circle size={18} className="text-slate-500" />} accent="border-[#0f2040]" sub="Missing source data" />
                <SummaryCard label="Warning" value={dashboard.warning_kpis} icon={<AlertTriangle size={18} className="text-amber-400" />} accent="border-amber-500/20" sub="Threshold breached" />
                <SummaryCard label="Critical" value={dashboard.critical_kpis} icon={<XCircle size={18} className="text-red-400" />} accent="border-red-500/20" sub="Immediate attention" />
              </>
            ) : null}
          </div>

          {/* ── Filter bar ───────────────────────────────────────────────── */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Search */}
            <div className="relative flex-1 min-w-[220px] max-w-sm">
              <Search size={13} className="absolute inset-y-0 left-3 my-auto text-slate-600 pointer-events-none" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search KPIs…"
                className="w-full pl-8 pr-4 py-2 bg-[#050b14] border border-[#0f2040] rounded-lg text-xs text-white placeholder-slate-600 outline-none focus:border-[#0066CC]/50 transition-colors"
              />
            </div>

            {/* Category filter */}
            <div className="relative">
              <Filter size={11} className="absolute left-3 inset-y-0 my-auto text-slate-600 pointer-events-none" />
              <select
                value={categoryFilter}
                onChange={e => setCategoryFilter(e.target.value)}
                className="pl-7 pr-4 py-2 bg-[#050b14] border border-[#0f2040] rounded-lg text-xs text-slate-300 outline-none focus:border-[#0066CC]/50 appearance-none cursor-pointer"
              >
                <option value="">All Categories</option>
                {categories.map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
              </select>
            </div>

            {/* Status filter */}
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="px-3 py-2 bg-[#050b14] border border-[#0f2040] rounded-lg text-xs text-slate-300 outline-none focus:border-[#0066CC]/50 appearance-none cursor-pointer"
            >
              <option value="">All Statuses</option>
              <option value="active">Active</option>
              <option value="unavailable">Unavailable</option>
            </select>

            {/* Eval filter */}
            <select
              value={evalFilter}
              onChange={e => setEvalFilter(e.target.value)}
              className="px-3 py-2 bg-[#050b14] border border-[#0f2040] rounded-lg text-xs text-slate-300 outline-none focus:border-[#0066CC]/50 appearance-none cursor-pointer"
            >
              <option value="">All Evaluations</option>
              <option value="healthy">Healthy</option>
              <option value="warning">Warning</option>
              <option value="critical">Critical</option>
              <option value="unknown">Unknown</option>
            </select>

            <div className="ml-auto text-[10px] text-slate-600">
              Showing <span className="text-slate-400 font-bold">{filtered.length}</span> of {catalog.length} KPIs
            </div>
          </div>

          {/* ── KPI Table ────────────────────────────────────────────────── */}
          <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl overflow-hidden backdrop-blur-md">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#0f2244]">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <BookOpen size={15} className="text-[#0066CC]" />
                KPI Governance Catalog
              </h3>
              <p className="text-[10px] text-slate-500">Click any row to inspect formula, thresholds &amp; AI insights</p>
            </div>

            {loading && catalog.length === 0 ? (
              <div className="p-5 space-y-2">
                {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-16 text-slate-500 text-xs border-t border-dashed border-[#0f2244]">
                No KPIs match the selected filters.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-[#0f2244] text-slate-500 bg-[#040b17]/40">
                      <th className="py-3 pl-4 font-semibold w-40">
                        <button className="flex items-center gap-1 hover:text-slate-300 transition-colors" onClick={() => toggleSort('name')}>
                          KPI ID <SortIcon field="name" />
                        </button>
                      </th>
                      <th className="py-3 pr-4 font-semibold">
                        <button className="flex items-center gap-1 hover:text-slate-300 transition-colors" onClick={() => toggleSort('name')}>
                          Name / Description <SortIcon field="name" />
                        </button>
                      </th>
                      <th className="py-3 pr-4 font-semibold w-36">
                        <button className="flex items-center gap-1 hover:text-slate-300 transition-colors" onClick={() => toggleSort('category')}>
                          Category <SortIcon field="category" />
                        </button>
                      </th>
                      <th className="py-3 pr-4 font-semibold text-right w-32">
                        <button className="flex items-center gap-1 hover:text-slate-300 transition-colors ml-auto" onClick={() => toggleSort('value')}>
                          Live Value <SortIcon field="value" />
                        </button>
                      </th>
                      <th className="py-3 pr-4 font-semibold w-28">
                        <button className="flex items-center gap-1 hover:text-slate-300 transition-colors" onClick={() => toggleSort('eval')}>
                          Threshold <SortIcon field="eval" />
                        </button>
                      </th>
                      <th className="py-3 pr-4 font-semibold w-32">Owner</th>
                      <th className="py-3 pr-4 w-8" />
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(entry => (
                      <KpiRow
                        key={entry.kpi_id}
                        entry={entry}
                        liveKpi={liveMap[entry.kpi_id]}
                        onSelect={id => setSelectedKpi(s => s === id ? null : id)}
                        selected={selectedKpi === entry.kpi_id}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Detail Drawer ─────────────────────────────────────────────── */}
      {selectedKpi && (
        <>
          {/* Backdrop on mobile */}
          <div className="fixed inset-0 bg-black/40 z-40 lg:hidden" onClick={() => setSelectedKpi(null)} />
          <DetailPanel
            kpiId={selectedKpi}
            entry={selectedEntry}
            onClose={() => setSelectedKpi(null)}
          />
        </>
      )}
    </div>
  );
}
