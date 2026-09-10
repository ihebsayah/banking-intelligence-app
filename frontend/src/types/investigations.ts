// src/types/investigations.ts
// Wire shapes mirror the workbench backend exactly (services/workbench/schemas/investigations.py,
// comments.py, timeline.py).

export type InvestigationStatus =
  | 'open'
  | 'active'
  | 'awaiting_information'
  | 'submitted'
  | 'returned'
  | 'completed'
  | 'cancelled';

export type InvestigationPriority = 'critical' | 'high' | 'medium' | 'low';

/** findings_refs entry — structured reference [{ type, id, description }]. */
export interface FindingRef {
  type?: string;
  id?: string;
  description?: string;
}

/** Authoritative immutable snapshot of the analyst report at submission time. */
export interface SubmissionSnapshot {
  submission_id: string;
  analyst_id: string;
  compliance_officer_id?: string | null;
  findings_text?: string | null;
  findings_refs?: FindingRef[] | null;
  conclusion?: string | null;
  submitted_at: string;
  evidence_manifest?: Array<{ filename: string; sha256: string; uploaded_by: string; uploaded_at: string } | Record<string, unknown>> | null;
  report_hash: string;
}

export interface Investigation {
  investigation_id: string;
  title: string;
  description?: string | null;
  alert_id?: string | null;
  scope_id: string;
  status: InvestigationStatus;
  priority: InvestigationPriority;
  assigned_to?: string | null;
  created_by: string;
  findings_text?: string | null;
  findings_refs?: FindingRef[] | null;
  conclusion?: string | null;
  started_at?: string | null;
  submitted_at?: string | null;
  completed_at?: string | null;
  return_reason?: string | null;
  compliance_officer_id?: string | null;
  submission_snapshot?: SubmissionSnapshot | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface EligibleComplianceOfficer {
  user_id: string;
  name: string;
  email: string;
}

export interface InvestigationListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Investigation[];
}

export interface InvestigationMutationResponse {
  success: boolean;
  investigation: Investigation;
  version: number;
}

export interface Comment {
  comment_id: string;
  entity_type: string;
  entity_id: string;
  content?: string;
  author_id: string;
  is_internal: boolean;
  is_redacted: boolean;
  redacted_at?: string | null;
  redacted_by?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CommentListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Comment[];
}

export interface CommentMutationResponse {
  success: boolean;
  comment: Comment;
  version: number;
}

export interface TimelineEntry {
  timeline_id: string;
  entity_type: string;
  entity_id: string;
  event_type: string;
  actor_id: string;
  old_value?: Record<string, unknown> | null;
  new_value?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  occurred_at: string;
}

export interface TimelineListResponse {
  total: number;
  page: number;
  page_size: number;
  items: TimelineEntry[];
}

export interface InvestigationAttachment {
  attachment_id: string;
  investigation_id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256_hash: string;
  description?: string | null;
  uploaded_by: string;
  uploaded_at: string;
}

export interface AttachmentListResponse {
  total: number;
  items: InvestigationAttachment[];
}

