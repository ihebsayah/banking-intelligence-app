// src/api/reportsApi.ts
import { apiClient } from './client';
import type { PaginatedReports } from '../types/api';

export interface GenerateReportRequest {
  report_type: string;
  regulation: string;
  period_start?: string;
  period_end?: string;
}

export interface GenerateReportResponse {
  report_id: string;
  report_type: string;
  regulation: string;
  status: string;
  generated_at: string;
  message: string;
}

export const reportsApi = {
  getReports: async (
    page = 1,
    pageSize = 20,
    regulation?: string,
    status?: string
  ): Promise<PaginatedReports> => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (regulation) params.append('regulation', regulation);
    if (status) params.append('status', status);

    const res = await apiClient.get<PaginatedReports>(`/reports?${params.toString()}`);
    return res.data;
  },

  generateReport: async (data: GenerateReportRequest): Promise<GenerateReportResponse> => {
    const res = await apiClient.post<GenerateReportResponse>('/reports/generate', data);
    return res.data;
  }
};
