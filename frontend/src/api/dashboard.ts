// src/api/dashboard.ts
import { apiClient } from './client';
import type { KPI, ChartData } from '../types/dashboard';
import type { RiskSummary, KpiMetric } from '../types/api';

export const dashboardApi = {
  getKPIs: async (): Promise<KPI[]> => {
    const res = await apiClient.get<KPI[]>('/dashboard/kpis');
    return res.data;
  },
  getChartData: async (chartId: string): Promise<ChartData> => {
    const res = await apiClient.get<ChartData>(`/dashboard/charts/${chartId}`);
    return res.data;
  },
  forceRefresh: async () => {
    const res = await apiClient.get('/dashboard/refresh');
    return res.data;
  },
  getRiskSummary: async (): Promise<RiskSummary> => {
    const res = await apiClient.get<RiskSummary>('/risk/summary');
    return res.data;
  },
  getKpiMetrics: async (): Promise<KpiMetric[]> => {
    const res = await apiClient.get<KpiMetric[]>('/kpi/metrics');
    return res.data;
  }
};
