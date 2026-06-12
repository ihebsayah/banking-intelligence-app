// src/api/complianceApi.ts
import { apiClient } from './client';
import type { ComplianceReportResponse, AuditLogEntry } from '../types/api';

export const complianceApi = {
  getComplianceReport: async (): Promise<ComplianceReportResponse> => {
    const res = await apiClient.get<ComplianceReportResponse>('/compliance/report');
    return res.data;
  },

  getAuditLogs: async (): Promise<AuditLogEntry[]> => {
    const res = await apiClient.get<AuditLogEntry[]>('/audit/logs');
    return res.data;
  }
};
