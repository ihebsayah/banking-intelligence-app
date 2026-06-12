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

  const [apiFailed, setApiFailed] = useState(false);

  const fetchDashboardData = async (force = false) => {
    setLoading(true);
    setError(null);
    setApiFailed(false);
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
    } catch (err) {
      console.error('Backend dashboard API failed.', err);
      setError('Dashboard API is not available.');
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

      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {apiFailed ? (
          <ServiceUnavailable
            serviceName="Financial Intelligence Dashboard"
            missingEndpoint="GET /dashboard/kpis"
            method="GET"
          />
        ) : isLoading && kpis.length === 0 ? (
          <div className="flex items-center justify-center min-h-[400px]">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#0066CC]"></div>
          </div>
        ) : (
          <>
            {/* KPIs Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
              {kpis.map((kpi) => (
                <KPICard
                  key={kpi.kpi_id}
                  kpi={kpi}
                  loading={isLoading}
                />
              ))}
            </div>

            {/* Charts Section */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              {/* Revenue Trend */}
              <div className="glass-card-static">
                {revData && <RevenueChart data={revData} />}
              </div>

              {/* Deposit Growth Rate */}
              <div className="glass-card-static">
                {growData && <GrowthChart data={growData} />}
              </div>

              {/* Concentration Risk */}
              <div className="glass-card-static">
                {concData && <ConcentrationChart data={concData} />}
              </div>

              {/* Risk Level Distribution */}
              <div className="glass-card-static">
                {riskData && <RiskChart data={riskData} />}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
