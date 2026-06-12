// src/api/kpiApi.ts
import { apiClient } from './client';
import type { KpiMetric, KpiDefinition } from '../types/api';

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
  getCatalog: async (): Promise<KpiDefinition[]> => {
    const res = await apiClient.get<KpiDefinition[]>('/kpi/catalog');
    return res.data;
  },

  getValues: async (): Promise<KpiMetric[]> => {
    const res = await apiClient.get<KpiMetric[]>('/kpi/values');
    return res.data;
  },

  getTrends: async (months = 12): Promise<KpiTrendsResponse> => {
    const res = await apiClient.get<KpiTrendsResponse>(`/kpi/trends?months=${months}`);
    return res.data;
  }
};
