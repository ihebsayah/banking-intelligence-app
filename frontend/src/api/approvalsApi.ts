// src/api/approvalsApi.ts
import { apiClient } from './client';
import type {
  ApprovalRequestDetail,
  ApprovalRequestListResponse,
  ApprovalRequestMutationResponse,
} from '../types/alerts';

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

export interface ApprovalListParams {
  status?: string;
  actionType?: string;
  page?: number;
  perPage?: number;
}

export type ApprovalVoteDecision = 'approved' | 'rejected';

export interface VoteApprovalPayload {
  decision: ApprovalVoteDecision;
  rationale?: string;
}

export const approvalsApi = {
  create: async (payload: CreateApprovalRequestPayload): Promise<ApprovalRequestMutationResponse> => {
    const res = await apiClient.post<ApprovalRequestMutationResponse>('/approval-requests', payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  list: async (params: ApprovalListParams = {}): Promise<ApprovalRequestListResponse> => {
    const qs = new URLSearchParams();
    if (params.status) qs.append('status', params.status);
    if (params.actionType) qs.append('action_type', params.actionType);
    qs.append('page', String(params.page ?? 1));
    qs.append('per_page', String(params.perPage ?? 50));
    const res = await apiClient.get<ApprovalRequestListResponse>(`/approval-requests?${qs.toString()}`);
    return res.data;
  },

  get: async (approvalRequestId: string): Promise<ApprovalRequestDetail> => {
    const res = await apiClient.get<ApprovalRequestDetail>(`/approval-requests/${approvalRequestId}`);
    return res.data;
  },

  vote: async (approvalRequestId: string, payload: VoteApprovalPayload): Promise<ApprovalRequestMutationResponse> => {
    const res = await apiClient.post<ApprovalRequestMutationResponse>(`/approval-requests/${approvalRequestId}/vote`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },
};
