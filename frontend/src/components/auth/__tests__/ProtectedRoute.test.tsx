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

import { ProtectedRoute } from '../ProtectedRoute';
import { useAuthStore } from '../../../stores/authStore';
import type { User } from '../../../types/auth';

function makeUser(role: User['role'], permissions: string[]): User {
  return {
    user_id: 'u1', email: 'u@example.com', name: 'User', role, bank_id: 'b1',
    created_at: '2026-01-01T00:00:00Z', last_login: '2026-01-01T00:00:00Z', permissions,
  };
}

function renderRoute(user: User) {
  useAuthStore.setState({ user, token: 't', isAuthenticated: true, isLoading: false, error: null });
  return render(
    <MemoryRouter initialEntries={['/workbench/customers/CUST_00001']}>
      <Routes>
        <Route path="/workbench/customers/:customerId" element={
          <ProtectedRoute requiredPermission="customer:read_basic"><div>customer page</div></ProtectedRoute>
        } />
        <Route path="/unauthorized" element={<div>unauthorized-redirect</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ProtectedRoute · Customer 360 gate', () => {
  beforeEach(() => useAuthStore.getState().logout());

  it('denies a Manager who holds no customer:read_basic permission', () => {
    renderRoute(makeUser('manager', []));
    expect(screen.getByText('unauthorized-redirect')).toBeInTheDocument();
    expect(screen.queryByText('customer page')).not.toBeInTheDocument();
  });

  it('admits a role with the customer:read_basic permission', () => {
    renderRoute(makeUser('analyst', ['customer:read_basic']));
    expect(screen.getByText('customer page')).toBeInTheDocument();
  });
});
