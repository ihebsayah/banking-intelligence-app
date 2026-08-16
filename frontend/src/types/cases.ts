// src/types/cases.ts
// Wire shapes mirror the workbench backend exactly (services/workbench/schemas/cases.py,
// information_requests.py, comments.py, timeline.py).

export type CaseStatus =
  | 'open'
  | 'assigned'
  | 'under_review'
  | 'awaiting_information'
  | 'decision_pending'
  | 'awaiting_compliance_action'
  | 'resolved'
  | 'closed'
  | 'cancelled';

export type CasePriority = 'critical' | 'high' | 'medium' | 'low';
export type CaseRiskLevel = 'critical' | 'high' | 'medium' | 'low';

export type DecisionType =
  | 'no_action'
  | 'warning'
  | 'enhanced_due_diligence_recommended'
  | 'report_to_authority_recommended'
  | 'account_action_recommended'
  | 'closure_recommended';

export interface Case {
  case_id: string;
  title: string;
  description?: string | null;
  alert_id?: string | null;
  investigation_id?: string | null;
  scope_id: string;
  status: CaseStatus;
  priority: CasePriority;
  risk_level?: CaseRiskLevel | null;
  regulatory_frameworks?: string[] | null;
  assigned_to?: string | null;
  created_by: string;
  target_date?: string | null;
  resolution?: string | null;
  resolved_at?: string | null;
  resolved_by?: string | null;
  closed_at?: string | null;
  closed_by?: string | null;
  current_disposition_id?: string | null;
  closure_approval_id?: string | null;
  reopen_reason?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CaseListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Case[];
}

export interface CaseMutationResponse {
  success: boolean;
  case: Case;
  version: number;
}

export interface CaseDecisionResponse {
  success: boolean;
  case: Case;
  decision: Record<string, unknown>;
  version: number;
}

export interface Decision {
  decision_id: string;
  case_id: string;
  decision_type: string;
  rationale: string;
  decided_by: string;
  decided_at: string;
  is_final: boolean;
  supersedes_decision_id?: string | null;
  approval_id?: string | null;
  version: number;
  created_at: string;
}

export interface CaseDecisionListResponse {
  data: Decision[];
}

export type InformationRequestStatus =
  | 'open'
  | 'acknowledged'
  | 'responded'
  | 'accepted'
  | 'returned'
  | 'cancelled';

/** Full IR (assignee/`info_request:read_assigned`) or restricted admin view —
 * optional content fields tolerate the metadata-only admin shape. */
export interface InformationRequest {
  ir_id: string;
  case_id?: string | null;
  investigation_id?: string | null;
  created_by: string;
  assigned_to?: string | null;
  question?: string | null;
  due_date?: string | null;
  status: InformationRequestStatus;
  response_text?: string | null;
  responded_at?: string | null;
  acceptance_note?: string | null;
  return_reason?: string | null;
  accepted_at?: string | null;
  returned_at?: string | null;
  accepted_by?: string | null;
  returned_by?: string | null;
  cancelled_at?: string | null;
  cancelled_by?: string | null;
  cancel_reason?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface InformationRequestListResponse {
  total: number;
  page: number;
  page_size: number;
  items: InformationRequest[];
}

export interface InformationRequestMutationResponse {
  success: boolean;
  information_request: InformationRequest;
  version: number;
}
