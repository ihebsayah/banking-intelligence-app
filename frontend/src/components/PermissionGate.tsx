import React, { type ReactNode } from 'react';
import { useAuth } from '../auth/AuthProvider';
import type { Permission } from '../lib/permissions';

interface Props {
  requires: Permission | Permission[];
  requireAll?: boolean;
  fallback?: ReactNode;
  children: ReactNode;
}

export function PermissionGate({ requires, requireAll = false, fallback = null, children }: Props) {
  const { hasPermission } = useAuth();
  const ps = Array.isArray(requires) ? requires : [requires];
  const ok = requireAll ? ps.every(hasPermission) : ps.some(hasPermission);
  return ok ? <>{children}</> : <>{fallback}</>;
}
