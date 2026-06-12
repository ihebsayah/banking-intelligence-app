// src/pages/KpiPage.tsx
import React, { useEffect, useState } from 'react';
import { dashboardApi } from '../api/dashboard';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { BankingHeader } from '../components/Layout/BankingHeader';
import type { KpiMetric } from '../types/api';

export function KpiPage() {
  const [metrics, setMetrics] = useState<KpiMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiFailed, setApiFailed] = useState(false);

  const fetchMetrics = async () => {
    setLoading(true);
    setApiFailed(false);
    try {
      const data = await dashboardApi.getKpiMetrics();
      setMetrics(data);
    } catch (err) {
      console.error('Failed to fetch KPI metrics:', err);
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="KPI Performance Intelligence"
        subtitle="Operational metrics, profitability ratios, and core performance indicators"
        onRefresh={fetchMetrics}
        isRefreshing={loading}
      />
      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {apiFailed ? (
          <ServiceUnavailable
            serviceName="KPI Intelligence Service"
            missingEndpoint="GET /kpi/metrics"
            method="GET"
          />
        ) : loading ? (
          <div className="flex items-center justify-center min-h-[400px]">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#0066CC]"></div>
          </div>
        ) : (
          <div className="text-slate-400 text-sm text-center">
            Rendering {metrics.length} KPI metrics.
          </div>
        )}
      </div>
    </div>
  );
}
