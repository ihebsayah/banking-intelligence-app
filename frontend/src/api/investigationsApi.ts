// src/api/investigationsApi.ts
import { apiClient } from './client';
import type {
  CommentListResponse,
  CommentMutationResponse,
  FindingRef,
  Investigation,
  InvestigationListResponse,
  InvestigationMutationResponse,
  TimelineListResponse,
} from '../types/investigations';

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export interface ListAssignedParams {
  status?: string;
  priority?: string;
  page?: number;
  perPage?: number;
}

export interface UpdateFindingsPayload {
  findings_text?: string;
  findings_refs?: FindingRef[];
  conclusion?: string;
  expected_version: number;
}

export interface TransitionPayload {
  target_status: Investigation['status'];
  return_reason?: string;
  expected_version: number;
}

export interface CancelInvestigationPayload {
  cancel_reason: string;
  expected_version: number;
}

export const investigationsApi = {
  listAssigned: async (params: ListAssignedParams = {}): Promise<InvestigationListResponse> => {
    const qs = new URLSearchParams();
    if (params.status) qs.append('status', params.status);
    if (params.priority) qs.append('priority', params.priority);
    qs.append('page', String(params.page ?? 1));
    qs.append('per_page', String(params.perPage ?? 50));
    const res = await apiClient.get<InvestigationListResponse>(`/investigations/assigned?${qs.toString()}`);
    return res.data;
  },

  get: async (investigationId: string): Promise<Investigation> => {
    const res = await apiClient.get<Investigation>(`/investigations/${investigationId}`);
    return res.data;
  },

  update: async (investigationId: string, payload: UpdateFindingsPayload): Promise<InvestigationMutationResponse> => {
    const res = await apiClient.patch<InvestigationMutationResponse>(`/investigations/${investigationId}`, payload,
      { headers: { 'X-Request-ID': uuid() } });
    return res.data;
  },

  transition: async (investigationId: string, payload: TransitionPayload): Promise<InvestigationMutationResponse> => {
    const res = await apiClient.patch<InvestigationMutationResponse>(`/investigations/${investigationId}/transition`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  cancel: async (investigationId: string, payload: CancelInvestigationPayload): Promise<InvestigationMutationResponse> => {
    const res = await apiClient.post<InvestigationMutationResponse>(`/investigations/${investigationId}/cancel`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  listComments: async (investigationId: string, page = 1, perPage = 50): Promise<CommentListResponse> => {
    const res = await apiClient.get<CommentListResponse>(`/investigations/${investigationId}/comments?page=${page}&per_page=${perPage}`);
    return res.data;
  },

  createComment: async (investigationId: string, content: string, isInternal: boolean): Promise<CommentMutationResponse> => {
    const res = await apiClient.post<CommentMutationResponse>(`/investigations/${investigationId}/comments`,
      { content, is_internal: isInternal },
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  listTimeline: async (investigationId: string, page = 1, perPage = 50): Promise<TimelineListResponse> => {
    const res = await apiClient.get<TimelineListResponse>(`/investigations/${investigationId}/timeline?page=${page}&per_page=${perPage}`);
    return res.data;
  },
};
