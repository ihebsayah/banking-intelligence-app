// src/pages/RiskPage.tsx
import React, { useEffect, useState } from 'react';
import { dashboardApi } from '../api/dashboard';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { BankingHeader } from '../components/Layout/BankingHeader';
import type { RiskSummary } from '../types/api';

export function RiskPage() {
  const [summary, setSummary] = useState<RiskSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiFailed, setApiFailed] = useState(false);

  const fetchRisk = async () => {
    setLoading(true);
    setApiFailed(false);
    try {
      const data = await dashboardApi.getRiskSummary();
      setSummary(data);
    } catch (err) {
      console.error('Failed to fetch risk summary:', err);
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRisk();
  }, []);

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="Credit & Portfolio Risk Monitor"
        subtitle="Exposure analytics, delinquent levels, and critical risk notifications"
        onRefresh={fetchRisk}
        isRefreshing={loading}
      />
      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {apiFailed ? (
          <ServiceUnavailable
            serviceName="Portfolio Risk Agent"
            missingEndpoint="GET /risk/summary"
            method="GET"
            requiredRole="analyst, manager, admin"
          />
        ) : loading ? (
          <div className="flex items-center justify-center min-h-[400px]">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#0066CC]"></div>
          </div>
        ) : (
          <div className="text-slate-400 text-sm text-center">
            Risk Score: {summary?.average_risk_score}
          </div>
        )}
      </div>
    </div>
  );
}
