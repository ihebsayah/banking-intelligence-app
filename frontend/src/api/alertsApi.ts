// src/api/alertsApi.ts
import { apiClient } from './client';
import type {
  Alert,
  AlertAdminView,
  AlertListResponse,
  EscalateResponse,
  InvestigateResponse,
  MutationResponse,
} from '../types/alerts';

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export interface ListAssignedParams {
  status?: string;
  severity?: string;
  page?: number;
  perPage?: number;
}

export interface DismissAlertPayload {
  dismissed_reason: string;
  expected_version: number;
  approval_request_id?: string;
}

export interface InvestigateAlertPayload {
  title: string;
  description?: string;
  expected_version: number;
}

export interface EscalateAlertPayload {
  title: string;
  description?: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  expected_version: number;
}

export interface AssignAlertPayload {
  assigned_to: string;
  expected_version: number;
  reason?: string;
}

export const alertsApi = {
  listAssigned: async (params: ListAssignedParams = {}): Promise<AlertListResponse> => {
    const qs = new URLSearchParams();
    if (params.status) qs.append('status', params.status);
    if (params.severity) qs.append('severity', params.severity);
    qs.append('page', String(params.page ?? 1));
    qs.append('per_page', String(params.perPage ?? 50));
    const res = await apiClient.get<AlertListResponse>(`/alerts/assigned?${qs.toString()}`);
    return res.data;
  },

  get: async (alertId: string): Promise<Alert | AlertAdminView> => {
    const res = await apiClient.get<Alert | AlertAdminView>(`/alerts/${alertId}`);
    return res.data;
  },

  acknowledge: async (alertId: string, expectedVersion: number): Promise<MutationResponse> => {
    const res = await apiClient.patch<MutationResponse>(`/alerts/${alertId}/acknowledge`,
      { expected_version: expectedVersion },
      { headers: { 'X-Request-ID': uuid() } });
    return res.data;
  },

  dismiss: async (alertId: string, payload: DismissAlertPayload): Promise<MutationResponse> => {
    const res = await apiClient.patch<MutationResponse>(`/alerts/${alertId}/dismiss`, payload,
      { headers: { 'X-Request-ID': uuid() } });
    return res.data;
  },

  investigate: async (alertId: string, payload: InvestigateAlertPayload): Promise<InvestigateResponse> => {
    const res = await apiClient.post<InvestigateResponse>(`/alerts/${alertId}/investigate`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  escalate: async (alertId: string, payload: EscalateAlertPayload): Promise<EscalateResponse> => {
    const res = await apiClient.post<EscalateResponse>(`/alerts/${alertId}/escalate`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  assign: async (alertId: string, payload: AssignAlertPayload): Promise<MutationResponse> => {
    const res = await apiClient.patch<MutationResponse>(`/alerts/${alertId}/assign`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },
};
