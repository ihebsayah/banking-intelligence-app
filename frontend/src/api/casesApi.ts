// src/api/casesApi.ts
import { apiClient } from './client';
import type {
  Case,
  CaseDecisionListResponse,
  CaseDecisionResponse,
  CaseListResponse,
  CaseMutationResponse,
  DecisionType,
  InformationRequest,
  InformationRequestListResponse,
  InformationRequestMutationResponse,
} from '../types/cases';
import type {
  CommentListResponse,
  CommentMutationResponse,
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

export interface TransitionCasePayload {
  target_status: string;
  resolution?: string;
  expected_version: number;
}

export interface AssignCasePayload {
  assigned_to: string;
  reason?: string;
  expected_version: number;
}

export interface RecordDecisionPayload {
  decision_type: DecisionType;
  rationale: string;
  approval_request_id?: string;
  expected_version: number;
}

export interface CreateInformationRequestPayload {
  assigned_to: string;
  question: string;
  due_date?: string;
  expected_case_version: number;
}

export const casesApi = {
  listAssigned: async (params: ListAssignedParams = {}): Promise<CaseListResponse> => {
    const qs = new URLSearchParams();
    if (params.status) qs.append('status', params.status);
    if (params.priority) qs.append('priority', params.priority);
    qs.append('page', String(params.page ?? 1));
    qs.append('per_page', String(params.perPage ?? 50));
    const res = await apiClient.get<CaseListResponse>(`/cases/assigned?${qs.toString()}`);
    return res.data;
  },

  get: async (caseId: string): Promise<Case> => {
    const res = await apiClient.get<Case>(`/cases/${caseId}`);
    return res.data;
  },

  assign: async (caseId: string, payload: AssignCasePayload): Promise<CaseMutationResponse> => {
    const res = await apiClient.patch<CaseMutationResponse>(`/cases/${caseId}/assign`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  transition: async (caseId: string, payload: TransitionCasePayload): Promise<CaseMutationResponse> => {
    const res = await apiClient.patch<CaseMutationResponse>(`/cases/${caseId}/transition`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  recordDecision: async (caseId: string, payload: RecordDecisionPayload): Promise<CaseDecisionResponse> => {
    const res = await apiClient.post<CaseDecisionResponse>(`/cases/${caseId}/decisions`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  listDecisions: async (caseId: string): Promise<CaseDecisionListResponse> => {
    const res = await apiClient.get<CaseDecisionListResponse>(`/cases/${caseId}/decisions`,
      { headers: { 'X-Request-ID': uuid() } });
    return res.data;
  },

  listInformationRequests: async (caseId: string, page = 1, perPage = 50): Promise<InformationRequestListResponse> => {
    const res = await apiClient.get<InformationRequestListResponse>(`/cases/${caseId}/information-requests?page=${page}&per_page=${perPage}`);
    return res.data;
  },

  createInformationRequest: async (caseId: string, payload: CreateInformationRequestPayload): Promise<InformationRequestMutationResponse> => {
    const res = await apiClient.post<InformationRequestMutationResponse>(`/cases/${caseId}/information-requests`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  acceptInformationRequest: async (irId: string, payload: { acceptance_note?: string; expected_version: number }): Promise<InformationRequestMutationResponse> => {
    const res = await apiClient.patch<InformationRequestMutationResponse>(`/information-requests/${irId}/accept`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  returnInformationRequest: async (irId: string, payload: { return_reason: string; expected_version: number }): Promise<InformationRequestMutationResponse> => {
    const res = await apiClient.patch<InformationRequestMutationResponse>(`/information-requests/${irId}/return`, payload,
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  listComments: async (caseId: string, page = 1, perPage = 50): Promise<CommentListResponse> => {
    const res = await apiClient.get<CommentListResponse>(`/cases/${caseId}/comments?page=${page}&per_page=${perPage}`);
    return res.data;
  },

  createComment: async (caseId: string, content: string, isInternal: boolean): Promise<CommentMutationResponse> => {
    const res = await apiClient.post<CommentMutationResponse>(`/cases/${caseId}/comments`,
      { content, is_internal: isInternal },
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } });
    return res.data;
  },

  listTimeline: async (caseId: string, page = 1, perPage = 50): Promise<TimelineListResponse> => {
    const res = await apiClient.get<TimelineListResponse>(`/cases/${caseId}/timeline?page=${page}&per_page=${perPage}`);
    return res.data;
  },
};

export type CaseInformationRequest = InformationRequest;
