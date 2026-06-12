// src/api/complianceApi.ts
import { apiClient } from './client';
import type { 
  ComplianceOverview, 
  ComplianceRule, 
  ComplianceViolation, 
  PaginatedComplianceViolations,
  AuditLogRow, 
  PaginatedAuditLogs 
} from '../types/api';

export const complianceApi = {
  getOverview: async (): Promise<ComplianceOverview> => {
    const res = await apiClient.get<ComplianceOverview>('/compliance/overview');
    return res.data;
  },

  getRules: async (regulation?: string, enabledOnly = true): Promise<ComplianceRule[]> => {
    const params = new URLSearchParams();
    if (regulation) params.append('regulation', regulation);
    params.append('enabled_only', String(enabledOnly));
    const res = await apiClient.get<ComplianceRule[]>(`/compliance/rules?${params.toString()}`);
    return res.data;
  },

  getViolations: async (
    page = 1, 
    pageSize = 20, 
    regulation?: string, 
    severity?: string
  ): Promise<PaginatedComplianceViolations> => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (regulation) params.append('regulation', regulation);
    if (severity) params.append('severity', severity);
    const res = await apiClient.get<PaginatedComplianceViolations>(`/compliance/violations?${params.toString()}`);
    return res.data;
  },

  getAuditLogs: async (
    page = 1, 
    pageSize = 25, 
    userId?: string, 
    action?: string,
    dateFrom?: string,
    dateTo?: string
  ): Promise<PaginatedAuditLogs> => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (userId) params.append('user_id', userId);
    if (action) params.append('action', action);
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    
    const res = await apiClient.get<PaginatedAuditLogs>(`/audit/logs?${params.toString()}`);
    return res.data;
  }
};
