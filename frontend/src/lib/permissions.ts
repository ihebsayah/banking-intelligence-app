/** Phase 2B permission codes — single source of truth for UI gates.
 * Server is the actual enforcer; this prevents unnecessary round-trips only.
 */

export const PERMISSIONS = {
  WORKBENCH_ACCESS: 'workbench:access',
  ALERT_READ_ASSIGNED: 'alert:read_assigned',
  ALERT_READ: 'alert:read',
  ALERT_ASSIGN: 'alert:assign',
  ALERT_ACKNOWLEDGE: 'alert:acknowledge',
  ALERT_DISMISS: 'alert:dismiss',
  ALERT_INVESTIGATE: 'alert:investigate',
  ALERT_TRANSITION: 'alert:transition',
  INVESTIGATION_READ_OWN: 'investigation:read_own',
  INVESTIGATION_READ: 'investigation:read',
  INVESTIGATION_UPDATE: 'investigation:update',
  INVESTIGATION_MODIFY_FINDINGS: 'investigation:modify_findings',
  INVESTIGATION_TRANSITION: 'investigation:transition',
  INVESTIGATION_REVIEW: 'investigation:review',
  INVESTIGATION_ASSIGN: 'investigation:assign',
  CASE_CREATE: 'case:create',
  CASE_READ_ASSIGNED: 'case:read_assigned',
  CASE_READ: 'case:read',
  CASE_TRANSITION: 'case:transition',
  CASE_DECISION: 'case:decision',
  CASE_CLOSE: 'case:close',
  CASE_ASSIGN: 'case:assign',
  CASE_REOPEN: 'case:reopen',
  INFO_REQUEST_CREATE: 'info_request:create',
  INFO_REQUEST_READ_ASSIGNED: 'info_request:read_assigned',
  INFO_REQUEST_READ: 'info_request:read',
  INFO_REQUEST_RESPOND: 'info_request:respond',
  INFO_REQUEST_ACCEPT: 'info_request:accept',
  INFO_REQUEST_RETURN: 'info_request:return',
  INFO_REQUEST_CANCEL: 'info_request:cancel',
  APPROVAL_REQUEST: 'approval:request',
  APPROVAL_APPROVE: 'approval:approve',
  APPROVAL_READ: 'approval:read',
  COMMENT_CREATE: 'comment:create',
  COMMENT_READ: 'comment:read',
  COMMENT_VIEW_INTERNAL_CONTENT: 'comment:view_internal_content',
  COMMENT_VIEW_METADATA: 'comment:view_metadata',
  COMMENT_REDACT: 'comment:redact',
  TIMELINE_READ: 'timeline:read',
  NOTIFICATION_READ: 'notification:read',
  NOTIFICATION_UPDATE: 'notification:update',
  ADMIN_OUTBOX_MONITOR: 'admin:outbox_monitor',
  ADMIN_OUTBOX_RETRY: 'admin:outbox_retry',
} as const;

export type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

export function usePermissions() {
  const { user } = { user: undefined as { permissions?: string[] } | undefined };
  return {
    hasPermission: (p: Permission): boolean =>
      user?.permissions?.includes(p) ?? false,
    hasAnyPermission: (ps: Permission[]): boolean =>
      ps.some(p => user?.permissions?.includes(p) ?? false),
  };
}
