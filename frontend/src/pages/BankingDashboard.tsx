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
import {
  dashboardApi,
  MOCK_KPIS,
  MOCK_REVENUE_CHART,
  MOCK_RISK_CHART,
  MOCK_CONCENTRATION_CHART,
  MOCK_GROWTH_CHART
} from '../api/dashboard';
import { AlertCircle } from 'lucide-react';

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

  const [isUsingMock, setIsUsingMock] = useState(false);

  const fetchDashboardData = async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      if (force) {
        await dashboardApi.forceRefresh();
      }
      const fetchedKPIs = await dashboardApi.getKPIs();
      const revChart = await dashboardApi.getChartData('revenue_trend');
      const riskChart = await dashboardApi.getChartData('risk_levels');
      const concChart = await dashboardApi.getChartData('concentration');
      const growChart = await dashboardApi.getChartData('growth_rate');

      setKPIs(fetchedKPIs);
      setChartData('revenue_trend', revChart);
      setChartData('risk_levels', riskChart);
      setChartData('concentration', concChart);
      setChartData('growth_rate', growChart);
      setLastRefreshed(new Date().toISOString());
      setIsUsingMock(false);
    } catch (err) {
      console.warn('Backend dashboard API failed, falling back to mock data.', err);
      // Fallback to mocks
      setKPIs(MOCK_KPIS);
      setChartData('revenue_trend', MOCK_REVENUE_CHART);
      setChartData('risk_levels', MOCK_RISK_CHART);
      setChartData('concentration', MOCK_CONCENTRATION_CHART);
      setChartData('growth_rate', MOCK_GROWTH_CHART);
      setLastRefreshed(new Date().toISOString());
      setIsUsingMock(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (kpis.length === 0) {
      fetchDashboardData();
    }
  }, []);

  const revData = charts['revenue_trend'] || MOCK_REVENUE_CHART;
  const riskData = charts['risk_levels'] || MOCK_RISK_CHART;
  const concData = charts['concentration'] || MOCK_CONCENTRATION_CHART;
  const growData = charts['growth_rate'] || MOCK_GROWTH_CHART;

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="HQ Financial Intelligence Portal"
        subtitle="Real-time balance concentration, revenue metrics, and portfolio risk distribution"
        lastRefreshed={lastRefreshed}
        onRefresh={() => fetchDashboardData(true)}
        isRefreshing={isLoading}
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {isUsingMock && (
          <div className="flex items-center gap-2.5 bg-blue-500/5 border border-blue-500/10 rounded-xl px-4 py-3 text-xs text-slate-400">
            <AlertCircle size={14} className="text-blue-400" />
            <span>Running in preview mode: displaying high-fidelity simulated bank intelligence data.</span>
          </div>
        )}

        {/* KPIs Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {kpis.map((kpi) => (
            <KPICard
              key={kpi.kpi_id}
              kpi={kpi}
              loading={isLoading && kpis.length === 0}
            />
          ))}
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* Revenue Trend */}
          <div className="glass-card-static">
            <RevenueChart data={revData} />
          </div>

          {/* Deposit Growth Rate */}
          <div className="glass-card-static">
            <GrowthChart data={growData} />
          </div>

          {/* Concentration Risk */}
          <div className="glass-card-static">
            <ConcentrationChart data={concData} />
          </div>

          {/* Risk Level Distribution */}
          <div className="glass-card-static">
            <RiskChart data={riskData} />
          </div>
        </div>
      </div>
    </div>
  );
}
