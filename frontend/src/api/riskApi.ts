// src/api/riskApi.ts
import { apiClient } from './client';
import type { RiskOverview, PaginatedRiskFlags, RiskSegment, RiskSummary } from '../types/api';

export const riskApi = {
  getOverview: async (): Promise<RiskOverview> => {
    const res = await apiClient.get<RiskOverview>('/risk/overview');
    return res.data;
  },

  getFlags: async (
    page = 1,
    pageSize = 20,
    severity?: string,
    resolved?: boolean
  ): Promise<PaginatedRiskFlags> => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (severity) params.append('severity', severity);
    if (resolved !== undefined) params.append('resolved', String(resolved));

    const res = await apiClient.get<PaginatedRiskFlags>(`/risk/flags?${params.toString()}`);
    return res.data;
  },

  getSegments: async (): Promise<RiskSegment[]> => {
    const res = await apiClient.get<RiskSegment[]>('/risk/segments');
    return res.data;
  },

  getSummary: async (): Promise<RiskSummary> => {
    const res = await apiClient.get<RiskSummary>('/risk/summary');
    return res.data;
  }
};
