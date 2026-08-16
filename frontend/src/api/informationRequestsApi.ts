// src/api/informationRequestsApi.ts
import { apiClient } from './client';
import type {
  InformationRequest,
  InformationRequestListResponse,
  InformationRequestMutationResponse,
} from '../types/cases';

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export interface ListAssignedParams {
  status?: string;
  page?: number;
  perPage?: number;
}

export const informationRequestsApi = {
  listAssigned: async (params: ListAssignedParams = {}): Promise<InformationRequestListResponse> => {
    const qs = new URLSearchParams();
    if (params.status) qs.append('status', params.status);
    qs.append('page', String(params.page ?? 1));
    qs.append('per_page', String(params.perPage ?? 50));
    const res = await apiClient.get<InformationRequestListResponse>(`/information-requests/assigned?${qs.toString()}`);
    return res.data;
  },

  get: async (irId: string): Promise<InformationRequest> => {
    const res = await apiClient.get<InformationRequest>(`/information-requests/${irId}`);
    return res.data;
  },

  createForInvestigation: async (
    investigationId: string,
    payload: { assigned_to: string; question: string; due_date?: string | null; expected_investigation_version?: number }
  ): Promise<InformationRequestMutationResponse> => {
    const res = await apiClient.post<InformationRequestMutationResponse>(
      `/investigations/${investigationId}/information-requests`,
      payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } }
    );
    return res.data;
  },

  listForInvestigation: async (
    investigationId: string,
    params: ListAssignedParams = {}
  ): Promise<InformationRequestListResponse> => {
    const qs = new URLSearchParams();
    if (params.status) qs.append('status', params.status);
    qs.append('page', String(params.page ?? 1));
    qs.append('per_page', String(params.perPage ?? 50));
    const res = await apiClient.get<InformationRequestListResponse>(
      `/investigations/${investigationId}/information-requests?${qs.toString()}`
    );
    return res.data;
  },

  acknowledge: async (irId: string, payload: { expected_version: number }): Promise<InformationRequestMutationResponse> => {
    const res = await apiClient.patch<InformationRequestMutationResponse>(`/information-requests/${irId}/acknowledge`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  respond: async (irId: string, payload: { response_text: string; expected_version: number }): Promise<InformationRequestMutationResponse> => {
    const res = await apiClient.patch<InformationRequestMutationResponse>(`/information-requests/${irId}/respond`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  accept: async (irId: string, payload: { acceptance_note?: string; expected_version: number }): Promise<InformationRequestMutationResponse> => {
    const res = await apiClient.patch<InformationRequestMutationResponse>(`/information-requests/${irId}/accept`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  return: async (irId: string, payload: { return_reason: string; expected_version: number }): Promise<InformationRequestMutationResponse> => {
    const res = await apiClient.patch<InformationRequestMutationResponse>(`/information-requests/${irId}/return`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },
};
