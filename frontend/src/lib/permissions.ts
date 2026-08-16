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
  CUSTOMER_READ: 'customer:read',
  CUSTOMER_READ_BASIC: 'customer:read_basic',
  CUSTOMER_READ_FINANCIAL: 'customer:read_financial',
  CUSTOMER_READ_TRANSACTIONS: 'customer:read_transactions',
  CUSTOMER_READ_KYC: 'customer:read_kyc',
  CUSTOMER_READ_RISK: 'customer:read_risk',
  CUSTOMER_READ_COMPLIANCE_HISTORY: 'customer:read_compliance_history',
  CUSTOMER_READ_OPERATIONAL_METADATA: 'customer:read_operational_metadata',
  CUSTOMER_READ_PII: 'customer:read_pii',
} as const;

export type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

import { useCallback } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { useAuthStore } from '../stores/authStore';
import { env } from '../config/env';

export interface CanAccessOptions {
  requiredPermissions?: Permission | Permission[] | string | string[];
  requiredRoles?: string | string[];
}

export function usePermissions() {
  const isKeycloak = env.AUTH_PROVIDER === 'keycloak';

  let keycloakAuth: ReturnType<typeof useAuth> | null = null;
  if (isKeycloak) {
    try {
      keycloakAuth = useAuth();
    } catch {
      keycloakAuth = null;
    }
  }

  const legacyUser = useAuthStore((s) => s.user);

  const permissions = isKeycloak && keycloakAuth
    ? (keycloakAuth.permissions ?? [])
    : (legacyUser?.permissions ?? []);

  const userRole = isKeycloak && keycloakAuth
    ? keycloakAuth.applicationUser?.role
    : legacyUser?.role;

  const hasPermission = useCallback(
    (p: Permission | string): boolean => permissions.includes(p),
    [permissions]
  );

  const hasAnyPermission = useCallback(
    (ps: (Permission | string)[]): boolean => ps.some((p) => permissions.includes(p)),
    [permissions]
  );

  const hasAllPermissions = useCallback(
    (ps: (Permission | string)[]): boolean => ps.every((p) => permissions.includes(p)),
    [permissions]
  );

  const canAccess = useCallback(
    (opts: CanAccessOptions): boolean => {
      // 1. Permission evaluation: if specified, user must possess at least one of the required permissions
      if (opts.requiredPermissions) {
        const reqs = Array.isArray(opts.requiredPermissions)
          ? opts.requiredPermissions
          : [opts.requiredPermissions];
        if (reqs.length > 0) {
          const hasPerm = reqs.some((p) => permissions.includes(p));
          if (!hasPerm) return false;
        }
      }

      // 2. Role evaluation: if specified
      if (opts.requiredRoles && userRole) {
        const roles = Array.isArray(opts.requiredRoles)
          ? opts.requiredRoles
          : [opts.requiredRoles];
        if (roles.length > 0 && !roles.includes(userRole)) {
          return false;
        }
      }

      return true;
    },
    [permissions, userRole]
  );

  return { permissions, userRole, hasPermission, hasAnyPermission, hasAllPermissions, canAccess };
}

