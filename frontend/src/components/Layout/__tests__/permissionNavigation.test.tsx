import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

vi.mock('../../../config/env', () => ({
  env: {
    AUTH_PROVIDER: 'legacy',
    KEYCLOAK_URL: '',
    KEYCLOAK_REALM: '',
    KEYCLOAK_CLIENT_ID: '',
    API_BASE_URL: '/api',
  },
  requireKeycloakEnv: () => {},
}));

import { BankingSidebar } from '../BankingSidebar';
import { CommandPalette } from '../../CommandPalette';
import { ProtectedRoute } from '../../auth/ProtectedRoute';
import { useAuthStore } from '../../../stores/authStore';
import { useUIStore } from '../../../stores/uiStore';
import type { User } from '../../../types/auth';

function makeUser(role: User['role'], permissions: string[]): User {
  return {
    user_id: 'test_user_1',
    email: 'test@bankintel.hq',
    name: 'Test User',
    role,
    bank_id: 'hq_main',
    created_at: '2026-01-01T00:00:00Z',
    last_login: '2026-01-01T00:00:00Z',
    permissions,
  };
}

function renderSidebar(user: User) {
  useAuthStore.setState({ user, token: 'fake-token', isAuthenticated: true, isLoading: false, error: null });
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <BankingSidebar />
    </MemoryRouter>
  );
}

function renderCommandPalette(user: User) {
  useAuthStore.setState({ user, token: 'fake-token', isAuthenticated: true, isLoading: false, error: null });
  useUIStore.setState({ commandPaletteOpen: true });
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <CommandPalette />
    </MemoryRouter>
  );
}

describe('Phase 3A.7 Permission-Aware Platform Navigation', () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
    useUIStore.setState({ sidebarCollapsed: false, commandPaletteOpen: false });
  });

  it('1. Analyst sees only permitted operational modules and Customer 360', () => {
    const analystPermissions = [
      'workbench:access',
      'alert:read_assigned',
      'investigation:read_own',
      'case:read_assigned',
      'info_request:read_assigned',
      'approval:read',
      'customer:read_basic',
    ];
    renderSidebar(makeUser('analyst', analystPermissions));

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Customer 360')).toBeInTheDocument();
    expect(screen.getByText('Alert Queue')).toBeInTheDocument();
    expect(screen.getByText('Investigations')).toBeInTheDocument();
    expect(screen.getByText('Cases')).toBeInTheDocument();
    expect(screen.getByText('Information Requests')).toBeInTheDocument();
    expect(screen.getByText('Approvals')).toBeInTheDocument();

    // Restricted areas for analyst
    expect(screen.queryByText('Outbox Monitor')).not.toBeInTheDocument();
    expect(screen.queryByText('Compliance')).not.toBeInTheDocument();
    expect(screen.queryByText('Reports')).not.toBeInTheDocument();
    expect(screen.queryByText('Admin')).not.toBeInTheDocument();
  });

  it('2. Compliance Officer sees compliance-authorized modules', () => {
    const compliancePermissions = [
      'workbench:access',
      'alert:read_assigned',
      'investigation:read',
      'case:read_assigned',
      'info_request:read',
      'approval:read',
      'customer:read_basic',
    ];
    renderSidebar(makeUser('compliance', compliancePermissions));

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Compliance')).toBeInTheDocument();
    expect(screen.getByText('Customer 360')).toBeInTheDocument();
    expect(screen.getByText('Alert Queue')).toBeInTheDocument();
    expect(screen.getByText('Investigations')).toBeInTheDocument();
    expect(screen.getByText('Cases')).toBeInTheDocument();

    expect(screen.queryByText('Outbox Monitor')).not.toBeInTheDocument();
    expect(screen.queryByText('Reports')).not.toBeInTheDocument();
  });

  it('3. Manager sees only manager-authorized modules and NO Customer 360 or queues', () => {
    const managerPermissions = ['workbench:access'];
    renderSidebar(makeUser('manager', managerPermissions));

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Branches')).toBeInTheDocument();
    expect(screen.getByText('Compliance')).toBeInTheDocument();
    expect(screen.getByText('Reports')).toBeInTheDocument();

    // Hidden from manager because permissions are absent
    expect(screen.queryByText('Customer 360')).not.toBeInTheDocument();
    expect(screen.queryByText('Alert Queue')).not.toBeInTheDocument();
    expect(screen.queryByText('Investigations')).not.toBeInTheDocument();
    expect(screen.queryByText('Cases')).not.toBeInTheDocument();
    expect(screen.queryByText('Outbox Monitor')).not.toBeInTheDocument();
    expect(screen.queryByText('Admin')).not.toBeInTheDocument();
  });

  it('4. Admin sees modules granted by its actual effective permissions', () => {
    const adminPermissions = [
      'workbench:access',
      'alert:read',
      'investigation:read',
      'case:read',
      'info_request:read',
      'approval:read',
      'customer:read_basic',
      'admin:outbox_monitor',
    ];
    renderSidebar(makeUser('admin', adminPermissions));

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Customer 360')).toBeInTheDocument();
    expect(screen.getByText('Alert Queue')).toBeInTheDocument();
    expect(screen.getByText('Outbox Monitor')).toBeInTheDocument();
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getByText('Dev Monitor')).toBeInTheDocument();
  });

  it('5. User lacking alert permission does not see Alert Queue', () => {
    const permissions = ['workbench:access', 'investigation:read_own', 'customer:read_basic'];
    renderSidebar(makeUser('analyst', permissions));

    expect(screen.queryByText('Alert Queue')).not.toBeInTheDocument();
  });

  it('6. User lacking investigation permission does not see Investigations', () => {
    const permissions = ['workbench:access', 'alert:read_assigned', 'customer:read_basic'];
    renderSidebar(makeUser('analyst', permissions));

    expect(screen.queryByText('Investigations')).not.toBeInTheDocument();
  });

  it('7. User lacking compliance permission does not see Compliance module', () => {
    const permissions = ['workbench:access', 'alert:read_assigned'];
    renderSidebar(makeUser('analyst', permissions));

    expect(screen.queryByText('Compliance')).not.toBeInTheDocument();
  });

  it('8. User lacking customer:read_basic does not see Customer 360 entry point', () => {
    const permissions = ['workbench:access', 'alert:read_assigned'];
    renderSidebar(makeUser('analyst', permissions));

    expect(screen.queryByText('Customer 360')).not.toBeInTheDocument();
  });

  it('9. CommandPalette uses identical permission filtering', () => {
    const permissions = ['workbench:access']; // missing customer:read_basic, alert:read, etc.
    renderCommandPalette(makeUser('manager', permissions));

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Compliance')).toBeInTheDocument();
    expect(screen.getByText('Reports')).toBeInTheDocument();

    expect(screen.queryByText('Customer 360')).not.toBeInTheDocument();
    expect(screen.queryByText('Alert Queue')).not.toBeInTheDocument();
    expect(screen.queryByText('Admin')).not.toBeInTheDocument();
  });

  it('10. Empty navigation groups disappear entirely (no orphan headers)', () => {
    // Grant only general permissions so Workbench & Administration groups are completely empty
    const permissions: string[] = [];
    renderSidebar(makeUser('analyst', permissions));

    expect(screen.queryByText('Operational Workbench')).not.toBeInTheDocument();
    expect(screen.queryByText('Administration')).not.toBeInTheDocument();
    expect(screen.getByText('General')).toBeInTheDocument();
  });

  it('11. Direct restricted URL remains denied by ProtectedRoute', () => {
    const managerNoCustomer = makeUser('manager', ['workbench:access']);
    useAuthStore.setState({ user: managerNoCustomer, token: 'fake-token', isAuthenticated: true, isLoading: false, error: null });

    render(
      <MemoryRouter initialEntries={['/workbench/customers/CUST_00001']}>
        <Routes>
          <Route
            path="/workbench/customers/:customerId"
            element={
              <ProtectedRoute requiredPermission="customer:read_basic">
                <div>Protected Customer Detail</div>
              </ProtectedRoute>
            }
          />
          <Route path="/unauthorized" element={<div>Access Denied Target</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Access Denied Target')).toBeInTheDocument();
    expect(screen.queryByText('Protected Customer Detail')).not.toBeInTheDocument();
  });
});
