// src/pages/KpiPage.tsx
import React, { useEffect, useState } from 'react';
import { kpiApi, KpiTrendsResponse } from '../api/kpiApi';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { BankingHeader } from '../components/Layout/BankingHeader';
import { formatCurrency, formatNumber, formatPercent, formatKPIValue } from '../utils/formatters';
import type { KpiMetric, KpiDefinition } from '../types/api';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Search,
  BookOpen,
  LineChart as LineChartIcon,
  RefreshCw,
  SlidersHorizontal
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import { clsx } from 'clsx';

export function KpiPage() {
  const [metrics, setMetrics] = useState<KpiMetric[]>([]);
  const [catalog, setCatalog] = useState<KpiDefinition[]>([]);
  const [trends, setTrends] = useState<KpiTrendsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiFailed, setApiFailed] = useState(false);
  
  // Interactive states
  const [selectedMetric, setSelectedMetric] = useState<'fee_revenue' | 'transaction_count' | 'avg_transaction_size'>('fee_revenue');
  const [searchQuery, setSearchQuery] = useState('');
  const [timeframe, setTimeframe] = useState<number>(12);

  const fetchMetrics = async () => {
    setLoading(true);
    setApiFailed(false);
    try {
      const [fetchedValues, fetchedCatalog, fetchedTrends] = await Promise.all([
        kpiApi.getValues(),
        kpiApi.getCatalog(),
        kpiApi.getTrends(timeframe)
      ]);
      setMetrics(fetchedValues);
      setCatalog(fetchedCatalog);
      setTrends(fetchedTrends);
    } catch (err) {
      console.error('Failed to fetch KPI metrics:', err);
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, [timeframe]);

  const filteredCatalog = catalog.filter((kpi) => 
    kpi.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    kpi.kpi_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (kpi.description && kpi.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
    kpi.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const metricLabelMap = {
    fee_revenue: { label: 'Fee Revenue', color: '#0066CC', formatter: (v: number) => formatCurrency(v, true) },
    transaction_count: { label: 'Transaction Count', color: '#10b981', formatter: (v: number) => formatNumber(v, true) },
    avg_transaction_size: { label: 'Avg Transaction Size', color: '#8b5cf6', formatter: (v: number) => formatCurrency(v, true) },
  };

  const chartInfo = metricLabelMap[selectedMetric];

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="KPI Performance Intelligence"
        subtitle="Operational metrics, profitability ratios, and core performance indicators"
        onRefresh={fetchMetrics}
        isRefreshing={loading}
      />
      <div className="flex-1 p-6 space-y-8 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {apiFailed ? (
          <div className="space-y-6">
            <ServiceUnavailable
              serviceName="KPI Intelligence Service"
              missingEndpoint="GET /kpi/values"
              method="GET"
            />
            <div className="flex justify-center">
              <button
                onClick={() => fetchMetrics()}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#0066CC] hover:bg-[#0052a3] text-white text-sm font-semibold shadow-lg shadow-[#0066CC]/20 hover:shadow-[#0066CC]/35 transition-all duration-200"
              >
                <RefreshCw size={16} className={clsx(loading && "animate-spin")} />
                Retry Connection
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Core Values Cards Grid */}
            <div className="space-y-3">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 pl-1">Live Intelligence Indexes</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-5">
                {loading && metrics.length === 0 ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 h-[120px] animate-pulse" />
                  ))
                ) : (
                  metrics.map((kpi) => {
                    const isUp = kpi.trend_direction === 'up';
                    const isDown = kpi.trend_direction === 'down';
                    const trendColor = isUp ? 'text-emerald-400' : isDown ? 'text-red-400' : 'text-slate-500';
                    const TrendIcon = isUp ? TrendingUp : isDown ? TrendingDown : Minus;

                    return (
                      <div key={kpi.kpi_id} className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4 relative group hover:border-[#1e3459] transition-all">
                        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider truncate mb-2">{kpi.name}</p>
                        <p className="text-2xl font-bold text-white tracking-tight mb-2">
                          {formatKPIValue(kpi.value, kpi.metric_type)}
                        </p>
                        <div className="flex items-center gap-1">
                          <TrendIcon size={12} className={trendColor} />
                          <span className={clsx('text-[10px] font-bold', trendColor)}>
                            {formatPercent(Math.abs(kpi.trend))}
                          </span>
                          <span className="text-[9px] text-slate-600 truncate ml-1">vs prev period</span>
                        </div>
                        <p className="text-[8px] text-slate-700 font-mono mt-2 pt-2 border-t border-[#0f2040]/30 uppercase">
                          Freshness: {kpi.data_freshness}
                        </p>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Trends charting section */}
            <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <LineChartIcon size={16} className="text-[#0066CC]" />
                    Historical Trend Analysis
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Explore monthly aggregations and business performance curves</p>
                </div>
                
                {/* Metric Selector Toggles */}
                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex rounded-lg bg-[#03060c] border border-[#0f203d] p-1 text-xs">
                    {(['fee_revenue', 'transaction_count', 'avg_transaction_size'] as const).map((metric) => (
                      <button
                        key={metric}
                        onClick={() => setSelectedMetric(metric)}
                        className={clsx(
                          "px-3 py-1.5 rounded-md font-medium transition-all duration-200 capitalize",
                          selectedMetric === metric
                            ? "bg-[#0066CC]/20 text-[#4d9fff] shadow-inner"
                            : "text-slate-500 hover:text-slate-350"
                        )}
                      >
                        {metric.replace('_', ' ')}
                      </button>
                    ))}
                  </div>

                  <select
                    value={timeframe}
                    onChange={(e) => setTimeframe(Number(e.target.value))}
                    className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-medium outline-none focus:border-[#0066CC]/50"
                  >
                    <option value={6}>6 Months</option>
                    <option value={12}>12 Months</option>
                    <option value={24}>24 Months</option>
                  </select>
                </div>
              </div>

              {loading && !trends ? (
                <div className="h-72 border border-[#0f2040] bg-[#050b14]/50 rounded-xl animate-pulse" />
              ) : trends ? (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trends.trends} margin={{ top: 10, right: 10, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#0f2040" />
                      <XAxis dataKey="month" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis
                        tick={{ fill: '#64748b', fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v) => chartInfo.formatter(v)}
                        width={65}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0a1628',
                          border: '1px solid #1a2d4e',
                          borderRadius: '8px',
                          fontSize: '12px',
                          color: '#e2e8f0',
                        }}
                        formatter={(v: number) => [chartInfo.formatter(v), chartInfo.label]}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }} />
                      <Line
                        name={chartInfo.label}
                        type="monotone"
                        dataKey={selectedMetric}
                        stroke={chartInfo.color}
                        strokeWidth={2.5}
                        dot={{ r: 2, fill: chartInfo.color, strokeWidth: 0 }}
                        activeDot={{ r: 5, strokeWidth: 0 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-72 flex items-center justify-center border border-[#0f2040] rounded-xl text-slate-500 text-xs">
                  No trend metrics loaded.
                </div>
              )}
            </div>

            {/* Catalog list section */}
            <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <BookOpen size={16} className="text-[#0066CC]" />
                    KPI Definitions Index
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Explore standard formulas and governance categories for institutional indicators</p>
                </div>

                {/* Search query box */}
                <div className="relative w-full sm:w-72">
                  <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-600">
                    <Search size={14} />
                  </span>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search KPI database..."
                    className="w-full pl-9 pr-4 py-1.5 bg-[#03060c] border border-[#0f203d] rounded-lg text-xs text-white placeholder-slate-600 outline-none focus:border-[#0066CC]/50 transition-colors"
                  />
                </div>
              </div>

              {loading && catalog.length === 0 ? (
                <div className="space-y-2 py-4">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-10 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />
                  ))}
                </div>
              ) : filteredCatalog.length === 0 ? (
                <div className="text-center py-12 border border-dashed border-[#0f203d] rounded-xl text-slate-500 text-xs">
                  No catalog records match your query.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-[#0f2244] text-slate-500">
                        <th className="pb-3 font-semibold w-48">KPI Identifier</th>
                        <th className="pb-3 font-semibold w-56">Name</th>
                        <th className="pb-3 font-semibold w-36">Category</th>
                        <th className="pb-3 font-semibold w-36">Metric Type</th>
                        <th className="pb-3 font-semibold">Formula / Governance Description</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#0f2244]/50">
                      {filteredCatalog.map((kpi) => {
                        const isFinancial = kpi.category.toLowerCase().includes('financial') || kpi.category.toLowerCase().includes('revenue');
                        const isCompliance = kpi.category.toLowerCase().includes('compliance') || kpi.category.toLowerCase().includes('audit');
                        const isRisk = kpi.category.toLowerCase().includes('risk');

                        return (
                          <tr key={kpi.kpi_id} className="hover:bg-[#0c1930]/25 transition-all">
                            <td className="py-4 font-mono text-[10px] text-slate-400 select-all font-semibold">{kpi.kpi_id}</td>
                            <td className="py-4 font-semibold text-slate-250">{kpi.name}</td>
                            <td className="py-4">
                              <span className={clsx(
                                "px-1.5 py-0.5 rounded text-[9px] font-semibold border uppercase tracking-wider",
                                isFinancial ? "bg-blue-500/10 text-blue-400 border-blue-500/25" :
                                isCompliance ? "bg-purple-500/10 text-purple-400 border-purple-500/25" :
                                isRisk ? "bg-amber-500/10 text-amber-400 border-amber-500/25" :
                                "bg-emerald-500/10 text-emerald-400 border-emerald-500/25"
                              )}>
                                {kpi.category}
                              </span>
                            </td>
                            <td className="py-4 capitalize font-mono text-[10px] text-slate-500">{kpi.metric_type}</td>
                            <td className="py-4 text-slate-400 leading-relaxed max-w-md">{kpi.description ?? '—'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
