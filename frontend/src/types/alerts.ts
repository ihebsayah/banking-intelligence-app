// src/types/alerts.ts
// Wire shapes mirror the workbench backend exactly (services/workbench/schemas/alerts.py).

export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low';

export type AlertStatus =
  | 'new'
  | 'assigned'
  | 'acknowledged'
  | 'under_investigation'
  | 'resolved'
  | 'dismissed';

export interface Alert {
  alert_id: string;
  alert_type: string;
  severity: AlertSeverity;
  title: string;
  description?: string | null;
  source_rule_type?: string | null;
  source_rule_id?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  resolved_customer_id?: string | null;
  scope_id: string;
  status: AlertStatus;
  assigned_to?: string | null;
  dismissed_reason?: string | null;
  dismissed_at?: string | null;
  dismissed_by?: string | null;
  resolved_at?: string | null;
  resolved_by?: string | null;
  created_at: string;
  updated_at: string;
  version: number;
}

/** Metadata-only view returned to admins outside direct scope (A2). */
export interface AlertAdminView {
  alert_id: string;
  alert_type: string;
  severity: AlertSeverity;
  status: AlertStatus;
  assigned_to?: string | null;
  scope_id: string;
  created_at: string;
  version: number;
}

export interface AlertListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Alert[];
}

export interface MutationResponse {
  success: boolean;
  alert: Alert;
  version: number;
}

export interface InvestigateResponse {
  success: boolean;
  alert: Alert;
  investigation_id: string;
  version: number;
}

export interface EscalateResponse {
  success: boolean;
  alert: Alert;
  case_id: string;
  version: number;
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired' | 'cancelled';

export interface ApprovalRequest {
  approval_request_id: string;
  action_type: string;
  entity_type: string;
  entity_id: string;
  requested_by: string;
  rationale: string;
  required_approvals: number;
  approval_count: number;
  status: ApprovalStatus;
  expires_at: string;
  executed_at?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ApprovalRequestMutationResponse {
  success: boolean;
  approval_request: ApprovalRequestDetail;
  version: number;
}

export interface ApprovalDecision {
  approval_decision_id: string;
  approver_id: string;
  decision: string;
  rationale?: string | null;
  decided_at: string;
}

export interface ApprovalRequestDetail extends ApprovalRequest {
  decisions: ApprovalDecision[];
}

export interface ApprovalRequestListResponse {
  total: number;
  page: number;
  page_size: number;
  items: ApprovalRequest[];
}

// ── Notification (N1-N3) ───────────────────────────────────────────────────
// Wire shape mirrors services/workbench/schemas/notifications.py exactly.

export interface Notification {
  notification_id: string;
  user_id: string;
  notification_type: string;
  title: string;
  body: string;
  entity_type?: string | null;
  entity_id?: string | null;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  total: number;
  page: number;
  page_size: number;
  unread_count: number;
  items: Notification[];
}

export interface NotificationMutationResponse {
  success: boolean;
  notification: Notification;
}

export interface MarkAllReadResponse {
  marked_read: number;
}

// ── Audit Outbox (AD1-AD2) ─────────────────────────────────────────────────
// Wire shape mirrors services/workbench/schemas/admin_outbox.py + models.py.

export type OutboxStatus = 'pending' | 'delivering' | 'delivered' | 'failed' | 'poison';

export interface AuditOutboxEvent {
  outbox_id: string;
  idempotency_key: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  actor_id: string;
  actor_role: string;
  occurred_at: string;
  payload: Record<string, unknown>;
  payload_schema_ver: number;
  status: string;
  attempt_count: number;
  last_attempt_at?: string | null;
  next_attempt_at?: string | null;
  last_error?: string | null;
  locked_by?: string | null;
  locked_at?: string | null;
  delivered_at?: string | null;
  poison_reason?: string | null;
  created_at: string;
}

export interface OutboxListResponse {
  total: number;
  page: number;
  page_size: number;
  items: AuditOutboxEvent[];
}

export interface OutboxRetryResponse {
  queued: boolean;
  outbox_id: string;
}
