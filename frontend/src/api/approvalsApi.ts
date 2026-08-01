// src/api/approvalsApi.ts
import { apiClient } from './client';
import type { ApprovalRequest, ApprovalRequestMutationResponse } from '../types/alerts';

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export interface CreateApprovalRequestPayload {
  action_type: string;
  entity_type: string;
  entity_id: string;
  proposed_payload?: Record<string, unknown>;
  rationale: string;
}

export const approvalsApi = {
  create: async (payload: CreateApprovalRequestPayload): Promise<ApprovalRequestMutationResponse> => {
    const res = await apiClient.post<ApprovalRequestMutationResponse>('/approval-requests', payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  get: async (approvalRequestId: string): Promise<ApprovalRequest> => {
    const res = await apiClient.get<ApprovalRequest>(`/approval-requests/${approvalRequestId}`);
    return res.data;
  },
};
