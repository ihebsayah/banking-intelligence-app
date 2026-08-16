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

describe('ProtectedRoute · Phase 3A.9A Authorization Alignment', () => {
  beforeEach(() => useAuthStore.getState().logout());

  it('admits Compliance to Investigations via investigation:read (array permission)', () => {
    useAuthStore.setState({
      user: makeUser('compliance', ['investigation:read', 'investigation:review']),
      token: 't', isAuthenticated: true, isLoading: false, error: null,
    });
    render(
      <MemoryRouter initialEntries={['/workbench/investigations']}>
        <Routes>
          <Route path="/workbench/investigations" element={
            <ProtectedRoute requiredPermission={['investigation:read_own', 'investigation:read']}>
              <div>investigations page</div>
            </ProtectedRoute>
          } />
          <Route path="/unauthorized" element={<div>unauthorized-redirect</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('investigations page')).toBeInTheDocument();
  });

  it('admits Analyst to Investigations via investigation:read_own (array permission)', () => {
    useAuthStore.setState({
      user: makeUser('analyst', ['investigation:read_own']),
      token: 't', isAuthenticated: true, isLoading: false, error: null,
    });
    render(
      <MemoryRouter initialEntries={['/workbench/investigations']}>
        <Routes>
          <Route path="/workbench/investigations" element={
            <ProtectedRoute requiredPermission={['investigation:read_own', 'investigation:read']}>
              <div>investigations page</div>
            </ProtectedRoute>
          } />
          <Route path="/unauthorized" element={<div>unauthorized-redirect</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('investigations page')).toBeInTheDocument();
  });

  it('admits Compliance to Information Requests via info_request:read', () => {
    useAuthStore.setState({
      user: makeUser('compliance', ['info_request:read', 'info_request:create']),
      token: 't', isAuthenticated: true, isLoading: false, error: null,
    });
    render(
      <MemoryRouter initialEntries={['/workbench/information-requests']}>
        <Routes>
          <Route path="/workbench/information-requests" element={
            <ProtectedRoute requiredPermission={['info_request:read_assigned', 'info_request:read']}>
              <div>ir inbox page</div>
            </ProtectedRoute>
          } />
          <Route path="/unauthorized" element={<div>unauthorized-redirect</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('ir inbox page')).toBeInTheDocument();
  });

  it('admits Analyst to Information Requests via info_request:read_assigned', () => {
    useAuthStore.setState({
      user: makeUser('analyst', ['info_request:read_assigned', 'info_request:respond']),
      token: 't', isAuthenticated: true, isLoading: false, error: null,
    });
    render(
      <MemoryRouter initialEntries={['/workbench/information-requests']}>
        <Routes>
          <Route path="/workbench/information-requests" element={
            <ProtectedRoute requiredPermission={['info_request:read_assigned', 'info_request:read']}>
              <div>ir inbox page</div>
            </ProtectedRoute>
          } />
          <Route path="/unauthorized" element={<div>unauthorized-redirect</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('ir inbox page')).toBeInTheDocument();
  });

  it('denies user when holding none of the required permissions in array', () => {
    useAuthStore.setState({
      user: makeUser('analyst', ['some:other_permission']),
      token: 't', isAuthenticated: true, isLoading: false, error: null,
    });
    render(
      <MemoryRouter initialEntries={['/workbench/investigations']}>
        <Routes>
          <Route path="/workbench/investigations" element={
            <ProtectedRoute requiredPermission={['investigation:read_own', 'investigation:read']}>
              <div>investigations page</div>
            </ProtectedRoute>
          } />
          <Route path="/unauthorized" element={<div>unauthorized-redirect</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('unauthorized-redirect')).toBeInTheDocument();
    expect(screen.queryByText('investigations page')).not.toBeInTheDocument();
  });
});
