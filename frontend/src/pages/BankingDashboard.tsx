// src/pages/BankingDashboard.tsx
import React, { useEffect, useState } from 'react';
import { useDashboardStore } from '../stores/dashboardStore';
import { KPICard } from '../components/dashboard/KPICard';
import {
  RevenueChart,
  RiskChart,
  ConcentrationChart,
  GrowthChart
} from '../components/dashboard/DashboardCharts';
import { BankingHeader } from '../components/Layout/BankingHeader';
import { dashboardApi } from '../api/dashboard';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { formatCurrency, formatNumber, formatDateTime } from '../utils/formatters';
import type { DashboardOverview, RecentActivity, ChartResponse } from '../types/api';
import type { ChartData } from '../types/dashboard';
import {
  Users,
  CreditCard,
  Activity,
  AlertTriangle,
  RefreshCw
} from 'lucide-react';
import { clsx } from 'clsx';

function toChartData(r: ChartResponse): ChartData {
  return r as unknown as ChartData;
}

export function BankingDashboard() {
  const {
    kpis,
    charts,
    isLoading,
    error,
    lastRefreshed,
    setKPIs,
    setChartData,
    setLoading,
    setError,
    setLastRefreshed
  } = useDashboardStore();

  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>([]);
  const [apiFailed, setApiFailed] = useState(false);

  const fetchDashboardData = async (force = false) => {
    setLoading(true);
    setError(null);
    setApiFailed(false);
    try {
      if (force) await dashboardApi.forceRefresh();

      const [fetchedOverview, fetchedKPIs, fetchedActivity, revChart, riskChart, concChart, growChart] = await Promise.all([
        dashboardApi.getOverview(),
        dashboardApi.getKPIs(),
        dashboardApi.getRecentActivity(10),
        dashboardApi.getChartData('revenue_trend'),
        dashboardApi.getChartData('risk_levels'),
        dashboardApi.getChartData('concentration'),
        dashboardApi.getChartData('growth_rate')
      ]);

      setOverview(fetchedOverview);
      setKPIs(fetchedKPIs as any);
      setRecentActivity(fetchedActivity);
      setChartData('revenue_trend', toChartData({ ...revChart, chart_type: 'line' }));
      setChartData('risk_levels',   toChartData({ ...riskChart, chart_type: 'pie' }));
      setChartData('concentration', toChartData({ ...concChart, chart_type: 'bar' }));
      setChartData('growth_rate',   toChartData({ ...growChart, chart_type: 'area' }));
      setLastRefreshed(new Date().toISOString());
    } catch (err) {
      console.error('Dashboard API failed.', err);
      setError('Dashboard API is temporarily unavailable.');
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDashboardData(); }, []);

  const revData = charts['revenue_trend'];
  const riskData = charts['risk_levels'];
  const concData = charts['concentration'];
  const growData = charts['growth_rate'];

  const overviewCards = overview ? [
    { label: 'Total Portfolios', value: formatNumber(overview.total_customers), icon: <Users size={18} />, color: 'var(--accent-blue)' },
    { label: 'Active Accounts', value: formatNumber(overview.active_accounts), sub: `/ ${formatNumber(overview.total_accounts)} total`, icon: <CreditCard size={18} />, color: 'var(--accent-green)' },
    { label: '30D Transactions', value: formatNumber(overview.monthly_transactions), icon: <Activity size={18} />, color: 'var(--accent-purple)' },
    { label: 'High Risk Portfolios', value: formatNumber(overview.high_risk_customers), icon: <AlertTriangle size={18} />, color: 'var(--accent-red)' },
  ] : [];

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title="Dashboard"
        subtitle="Executive overview of portfolio performance and key metrics"
        lastRefreshed={apiFailed ? null : lastRefreshed}
        onRefresh={() => fetchDashboardData(true)}
        isRefreshing={isLoading}
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {apiFailed ? (
          <div className="space-y-6">
            <ServiceUnavailable serviceName="Dashboard" missingEndpoint="GET /dashboard/kpis" method="GET" />
            <div className="flex justify-center">
              <button onClick={() => fetchDashboardData(false)} className="btn-primary">
                <RefreshCw size={14} className={clsx(isLoading && "animate-spin")} />
                Retry Connection
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Executive Summary */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {isLoading && !overview ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="rounded-xl border h-[88px] animate-pulse"
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
                ))
              ) : overviewCards.map((card) => (
                <div key={card.label} className="rounded-xl border p-5 flex items-center justify-between"
                  style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
                  <div>
                    <p className="text-[10px] uppercase font-bold tracking-wider" style={{ color: 'var(--text-muted)' }}>{card.label}</p>
                    <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>
                      {card.value}
                      {card.sub && <span className="text-xs font-normal ml-1.5" style={{ color: 'var(--text-muted)' }}>{card.sub}</span>}
                    </p>
                  </div>
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ background: `color-mix(in srgb, ${card.color} 10%, transparent)`, color: card.color }}>
                    {card.icon}
                  </div>
                </div>
              ))}
            </div>

            {/* KPIs */}
            {kpis.length > 0 && (
              <div className="space-y-3">
                <h2 className="text-xs font-bold uppercase tracking-wider pl-1" style={{ color: 'var(--text-muted)' }}>
                  Financial Intelligence Indexes
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {kpis.map((kpi) => (
                    <KPICard key={kpi.kpi_id} kpi={{ ...kpi, metric_type: kpi.metric_type === 'percentage' ? 'percentage' : kpi.metric_type }} loading={isLoading} />
                  ))}
                </div>
              </div>
            )}

            {/* Charts */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
              {[
                { data: revData, Chart: RevenueChart, label: 'Revenue Trend' },
                { data: growData, Chart: GrowthChart, label: 'Growth Rate' },
                { data: concData, Chart: ConcentrationChart, label: 'Concentration' },
                { data: riskData, Chart: RiskChart, label: 'Risk Distribution' },
              ].map(({ data, Chart, label }) => (
                <div key={label} className="glass-card-static">
                  {isLoading && !data ? (
                    <div className="h-72 rounded-lg animate-pulse" style={{ background: 'var(--bg-tertiary)' }} />
                  ) : data ? <Chart data={data} /> : null}
                </div>
              ))}
            </div>

            {/* Recent Activity */}
            <div className="rounded-xl border p-5" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Recent Activity</h3>
                  <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>Latest transactions across all branches</p>
                </div>
                <button onClick={() => fetchDashboardData(false)} className="btn-ghost text-xs px-2.5 py-1.5">
                  <RefreshCw size={12} className={clsx(isLoading && "animate-spin")} />
                  Refresh
                </button>
              </div>

              {isLoading && recentActivity.length === 0 ? (
                <div className="space-y-2 py-4">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="h-10 rounded-lg animate-pulse" style={{ background: 'var(--bg-tertiary)' }} />
                  ))}
                </div>
              ) : recentActivity.length === 0 ? (
                <div className="text-center py-12 rounded-xl text-xs"
                  style={{ border: '1px dashed var(--bg-border)', color: 'var(--text-muted)' }}>
                  No recent activities recorded.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--bg-border)' }}>
                        {['TX ID', 'Customer', 'Description', 'Type', 'Amount', 'Status', 'Timestamp'].map((h) => (
                          <th key={h} className="pb-3 font-semibold" style={{ color: 'var(--text-muted)' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {recentActivity.map((tx) => {
                        const isDeposit = tx.transaction_type.toLowerCase() === 'deposit';
                        const isWithdrawal = tx.transaction_type.toLowerCase() === 'withdrawal';
                        return (
                          <tr key={tx.transaction_id} className="border-b transition-colors"
                            style={{ borderColor: 'var(--bg-border)' }}>
                            <td className="py-3 font-mono text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
                              {tx.transaction_id.slice(0, 8)}...
                            </td>
                            <td className="py-3 font-mono text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
                              {tx.customer_id.slice(0, 8)}...
                            </td>
                            <td className="py-3" style={{ color: 'var(--text-secondary)' }}>{tx.description}</td>
                            <td className="py-3">
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold border uppercase"
                                style={{
                                  background: isDeposit ? 'rgba(22,163,74,0.1)' : isWithdrawal ? 'rgba(217,119,6,0.1)' : 'rgba(37,99,235,0.1)',
                                  color: isDeposit ? 'var(--accent-green)' : isWithdrawal ? 'var(--accent-amber)' : 'var(--accent-blue)',
                                  borderColor: isDeposit ? 'rgba(22,163,74,0.2)' : isWithdrawal ? 'rgba(217,119,6,0.2)' : 'rgba(37,99,235,0.2)',
                                }}>
                                {tx.transaction_type}
                              </span>
                            </td>
                            <td className="py-3 text-right font-bold font-mono text-sm"
                              style={{ color: isDeposit ? 'var(--accent-green)' : isWithdrawal ? 'var(--accent-red)' : 'var(--text-secondary)' }}>
                              {isDeposit ? '+' : isWithdrawal ? '-' : ''}{formatCurrency(Math.abs(tx.amount))}
                            </td>
                            <td className="py-3 text-center">
                              <span className="px-1.5 py-0.5 rounded-full text-[9px] font-medium inline-flex items-center gap-1"
                                style={{
                                  background: tx.status.toLowerCase() === 'success' || tx.status.toLowerCase() === 'completed' ? 'rgba(22,163,74,0.08)' : 'rgba(220,38,38,0.08)',
                                  color: tx.status.toLowerCase() === 'success' || tx.status.toLowerCase() === 'completed' ? 'var(--accent-green)' : 'var(--accent-red)',
                                }}>
                                {tx.status}
                              </span>
                            </td>
                            <td className="py-3 text-right font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                              {formatDateTime(tx.transaction_date)}
                            </td>
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
