// src/api/adminOutboxApi.ts
import { apiClient } from './client';
import type { OutboxListResponse, OutboxRetryResponse } from '../types/alerts';

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export interface OutboxListParams {
  status?: string;
  page?: number;
  perPage?: number;
}

export const adminOutboxApi = {
  list: async (params: OutboxListParams = {}): Promise<OutboxListResponse> => {
    const qs = new URLSearchParams();
    if (params.status) qs.append('status', params.status);
    qs.append('page', String(params.page ?? 1));
    qs.append('per_page', String(params.perPage ?? 50));
    const res = await apiClient.get<OutboxListResponse>(`/admin/outbox?${qs.toString()}`);
    return res.data;
  },

  retry: async (outboxId: string): Promise<OutboxRetryResponse> => {
    const res = await apiClient.post<OutboxRetryResponse>(
      `/admin/outbox/${outboxId}/retry`,
      {},
      { headers: { 'X-Request-ID': uuid() } },
    );
    return res.data;
  },
};
