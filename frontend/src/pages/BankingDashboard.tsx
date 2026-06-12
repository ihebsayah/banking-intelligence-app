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

// Cast API ChartResponse to the store's ChartData type
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
      if (force) {
        await dashboardApi.forceRefresh();
      }
      
      // Fetch overview, KPIs, recent activity, and charts in parallel
      const [
        fetchedOverview,
        fetchedKPIs,
        fetchedActivity,
        revChart,
        riskChart,
        concChart,
        growChart
      ] = await Promise.all([
        dashboardApi.getOverview(),
        dashboardApi.getKPIs(),
        dashboardApi.getRecentActivity(10),
        dashboardApi.getChartData('revenue_trend'),
        dashboardApi.getChartData('risk_levels'),
        dashboardApi.getChartData('concentration'),
        dashboardApi.getChartData('growth_rate')
      ]);

      setOverview(fetchedOverview);
      // KpiMetric from API is compatible with dashboard's KPI shape
      setKPIs(fetchedKPIs as any);
      setRecentActivity(fetchedActivity);
      setChartData('revenue_trend', toChartData({ ...revChart, chart_type: 'line' }));
      setChartData('risk_levels',   toChartData({ ...riskChart, chart_type: 'pie' }));
      setChartData('concentration', toChartData({ ...concChart, chart_type: 'bar' }));
      setChartData('growth_rate',   toChartData({ ...growChart, chart_type: 'area' }));
      
      setLastRefreshed(new Date().toISOString());
    } catch (err) {
      console.error('Backend dashboard API failed.', err);
      setError('Dashboard API is temporarily unavailable.');
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const revData = charts['revenue_trend'];
  const riskData = charts['risk_levels'];
  const concData = charts['concentration'];
  const growData = charts['growth_rate'];

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="HQ Financial Intelligence Portal"
        subtitle="Real-time balance concentration, revenue metrics, and portfolio risk distribution"
        lastRefreshed={apiFailed ? null : lastRefreshed}
        onRefresh={() => fetchDashboardData(true)}
        isRefreshing={isLoading}
      />

      <div className="flex-1 p-6 space-y-8 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {apiFailed ? (
          <div className="space-y-6">
            <ServiceUnavailable
              serviceName="Financial Intelligence Dashboard"
              missingEndpoint="GET /dashboard/kpis"
              method="GET"
            />
            <div className="flex justify-center">
              <button
                onClick={() => fetchDashboardData(false)}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#0066CC] hover:bg-[#0052a3] text-white text-sm font-semibold shadow-lg shadow-[#0066CC]/20 hover:shadow-[#0066CC]/35 transition-all duration-200"
              >
                <RefreshCw size={16} className={clsx(isLoading && "animate-spin")} />
                Retry Connection
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Overview Stats Top Bar */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {isLoading && !overview ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-5 animate-pulse h-[88px]" />
                ))
              ) : overview ? (
                <>
                  {/* Total Customers */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-5 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500">Total Portfolios</p>
                      <p className="text-2xl font-bold text-slate-200 mt-1">{formatNumber(overview.total_customers)}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-[#0066CC]/10 border border-[#0066CC]/25 flex items-center justify-center text-[#4d9fff]">
                      <Users size={18} />
                    </div>
                  </div>

                  {/* Active accounts */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-5 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500">Active Accounts</p>
                      <p className="text-2xl font-bold text-slate-200 mt-1">
                        {formatNumber(overview.active_accounts)} 
                        <span className="text-xs text-slate-500 font-normal ml-1.5">/ {formatNumber(overview.total_accounts)} total</span>
                      </p>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400">
                      <CreditCard size={18} />
                    </div>
                  </div>

                  {/* Monthly Transactions */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-5 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500">30D Transactions</p>
                      <p className="text-2xl font-bold text-slate-200 mt-1">{formatNumber(overview.monthly_transactions)}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/25 flex items-center justify-center text-purple-400">
                      <Activity size={18} />
                    </div>
                  </div>

                  {/* High Risk Customers */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-5 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500">High Risk Portfolios</p>
                      <p className="text-2xl font-bold text-red-400 mt-1">{formatNumber(overview.high_risk_customers)}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-red-500/10 border border-red-500/25 flex items-center justify-center text-red-400">
                      <AlertTriangle size={18} />
                    </div>
                  </div>
                </>
              ) : null}
            </div>

            {/* Financial KPIs Grid */}
            <div className="space-y-3">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 pl-1">Financial Intelligence Indexes</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                {isLoading && kpis.length === 0 ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="rounded-xl border border-[#0f2040] bg-[#08111e] p-5 animate-pulse h-[132px]" />
                  ))
                ) : (
                  kpis.map((kpi) => (
                    <KPICard
                      key={kpi.kpi_id}
                      kpi={{
                        ...kpi,
                        metric_type: kpi.metric_type === 'percentage' ? 'percentage' : kpi.metric_type
                      }}
                      loading={isLoading}
                    />
                  ))
                )}
              </div>
            </div>

            {/* Charts Section */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              {/* Revenue Trend */}
              <div className="glass-card-static relative">
                {isLoading && !revData ? (
                  <div className="rounded-xl border border-[#0f2040] bg-[#08111e] h-72 animate-pulse" />
                ) : revData ? (
                  <RevenueChart data={revData} />
                ) : null}
              </div>

              {/* Deposit Growth Rate */}
              <div className="glass-card-static relative">
                {isLoading && !growData ? (
                  <div className="rounded-xl border border-[#0f2040] bg-[#08111e] h-72 animate-pulse" />
                ) : growData ? (
                  <GrowthChart data={growData} />
                ) : null}
              </div>

              {/* Concentration Risk */}
              <div className="glass-card-static relative">
                {isLoading && !concData ? (
                  <div className="rounded-xl border border-[#0f2040] bg-[#08111e] h-72 animate-pulse" />
                ) : concData ? (
                  <ConcentrationChart data={concData} />
                ) : null}
              </div>

              {/* Risk Level Distribution */}
              <div className="glass-card-static relative">
                {isLoading && !riskData ? (
                  <div className="rounded-xl border border-[#0f2040] bg-[#08111e] h-72 animate-pulse" />
                ) : riskData ? (
                  <RiskChart data={riskData} />
                ) : null}
              </div>
            </div>

            {/* Recent Activity Section */}
            <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h3 className="text-sm font-bold text-white">Institutional Activity Log</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Latest 10 transactions executed across all branch networks</p>
                </div>
                <button
                  onClick={() => fetchDashboardData(false)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 hover:text-white bg-[#0e1d35] border border-[#1e3459] rounded-lg transition-all"
                >
                  <RefreshCw size={12} className={clsx(isLoading && "animate-spin")} />
                  Refresh
                </button>
              </div>

              {isLoading && recentActivity.length === 0 ? (
                <div className="space-y-2 py-4">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="h-10 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />
                  ))}
                </div>
              ) : recentActivity.length === 0 ? (
                <div className="text-center py-12 border border-dashed border-[#0f203d] rounded-xl text-slate-500 text-xs">
                  No recent activities recorded in this session.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-[#0f2244] text-slate-500">
                        <th className="pb-3 font-semibold w-24">TX ID</th>
                        <th className="pb-3 font-semibold w-24">Customer</th>
                        <th className="pb-3 font-semibold">Description</th>
                        <th className="pb-3 font-semibold w-24">Type</th>
                        <th className="pb-3 font-semibold text-right w-28">Amount</th>
                        <th className="pb-3 font-semibold text-center w-24">Status</th>
                        <th className="pb-3 font-semibold text-right w-36">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#0f2244]/50">
                      {recentActivity.map((tx) => {
                        const isDeposit = tx.transaction_type.toLowerCase() === 'deposit';
                        const isWithdrawal = tx.transaction_type.toLowerCase() === 'withdrawal';
                        const isTransfer = tx.transaction_type.toLowerCase() === 'transfer';
                        
                        return (
                          <tr key={tx.transaction_id} className="hover:bg-[#0c1930]/35 transition-colors group">
                            <td className="py-3.5 font-mono text-[10px] text-slate-400 select-all font-semibold">{tx.transaction_id.slice(0, 8)}...</td>
                            <td className="py-3.5 font-mono text-[10px] text-slate-400 font-semibold">{tx.customer_id.slice(0, 8)}...</td>
                            <td className="py-3.5 text-slate-350">{tx.description}</td>
                            <td className="py-3.5">
                              <span className={clsx(
                                "px-1.5 py-0.5 rounded text-[9px] font-semibold border uppercase tracking-wider",
                                isDeposit ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/25" :
                                isWithdrawal ? "bg-amber-500/10 text-amber-400 border-amber-500/25" :
                                "bg-blue-500/10 text-blue-400 border-blue-500/25"
                              )}>
                                {tx.transaction_type}
                              </span>
                            </td>
                            <td className={clsx(
                              "py-3.5 text-right font-bold font-mono text-sm",
                              isDeposit ? "text-emerald-400" : isWithdrawal ? "text-red-400" : "text-slate-300"
                            )}>
                              {isDeposit ? '+' : isWithdrawal ? '-' : ''}
                              {formatCurrency(Math.abs(tx.amount))}
                            </td>
                            <td className="py-3.5 text-center">
                              <span className={clsx(
                                "px-1.5 py-0.5 rounded-full text-[9px] font-medium inline-flex items-center gap-1",
                                tx.status.toLowerCase() === 'success' || tx.status.toLowerCase() === 'completed'
                                  ? "bg-emerald-500/8 text-emerald-500 border border-emerald-500/20"
                                  : "bg-red-500/8 text-red-400 border border-red-500/20"
                              )}>
                                <span className={clsx(
                                  "w-1.5 h-1.5 rounded-full",
                                  tx.status.toLowerCase() === 'success' || tx.status.toLowerCase() === 'completed'
                                    ? "bg-emerald-500"
                                    : "bg-red-500"
                                )} />
                                {tx.status}
                              </span>
                            </td>
                            <td className="py-3.5 text-right font-mono text-[10px] text-slate-500">
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
