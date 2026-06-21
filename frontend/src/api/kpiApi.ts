// src/api/kpiApi.ts
import { apiClient } from './client';
import type { KpiMetric, KpiDefinition, KpiCatalogEntry, KpiDashboard, KpiDetail, KpiInsight } from '../types/api';

export interface KpiTrendsResponse {
  months: number;
  trends: Array<{
    month: string;
    fee_revenue: number;
    transaction_count: number;
    avg_transaction_size: number;
  }>;
  last_updated: string;
}

export const kpiApi = {
  getCatalog: async (params?: { category?: string; status?: string }): Promise<KpiCatalogEntry[]> => {
    const query = new URLSearchParams();
    if (params?.category) query.set('category', params.category);
    if (params?.status) query.set('status', params.status);
    const qs = query.toString();
    const res = await apiClient.get<KpiCatalogEntry[]>(`/kpi/catalog${qs ? '?' + qs : ''}`);
    return res.data;
  },

  getValues: async (): Promise<KpiMetric[]> => {
    const res = await apiClient.get<KpiMetric[]>('/kpi/values');
    return res.data;
  },

  getDashboard: async (): Promise<KpiDashboard> => {
    const res = await apiClient.get<KpiDashboard>('/kpi/dashboard');
    return res.data;
  },

  getDetail: async (kpiId: string): Promise<KpiDetail> => {
    const res = await apiClient.get<KpiDetail>(`/kpi/${kpiId}`);
    return res.data;
  },

  getInsights: async (kpiId: string): Promise<KpiInsight> => {
    const res = await apiClient.get<KpiInsight>(`/kpi/${kpiId}/insights`);
    return res.data;
  },

  getTrends: async (months = 12, kpiId?: string): Promise<KpiTrendsResponse> => {
    const params = new URLSearchParams({ months: String(months) });
    if (kpiId) params.set('kpi_id', kpiId);
    const res = await apiClient.get<KpiTrendsResponse>(`/kpi/trends?${params.toString()}`);
    return res.data;
  },
};
