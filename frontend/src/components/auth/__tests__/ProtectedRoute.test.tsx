import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';

const mockKeycloak = {
  init: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  updateToken: vi.fn(),
  token: undefined as string | undefined,
  tokenParsed: undefined as Record<string, unknown> | undefined,
  onTokenExpired: undefined as (() => void) | undefined,
  authenticated: false,
};

const { mockGet } = vi.hoisted(() => ({
  mockGet: vi.fn(),
}));

const mockInitKeycloak = vi.hoisted(() => vi.fn());

vi.mock('keycloak-js', () => ({
  default: vi.fn(() => mockKeycloak),
}));

vi.mock('../../../config/env', () => ({
  env: {
    AUTH_PROVIDER: 'keycloak',
    KEYCLOAK_URL: 'http://localhost:8080',
    KEYCLOAK_REALM: 'banking-intelligence',
    KEYCLOAK_CLIENT_ID: 'banking-portal-web',
    API_BASE_URL: '/api',
  },
  requireKeycloakEnv: vi.fn(),
}));

vi.mock('../../../auth/keycloak', () => ({
  getKeycloak: vi.fn(() => mockKeycloak),
  initKeycloak: mockInitKeycloak,
  getKeycloakToken: vi.fn(() => mockKeycloak.token),
}));

vi.mock('../../../api/client', () => ({
  apiClient: {
    get: mockGet,
    post: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}));

vi.mock('../../../stores/authStore', () => ({
  useAuthStore: Object.assign(
    vi.fn(() => ({
      user: null, token: null, isAuthenticated: false, isLoading: false, error: null,
      setUser: vi.fn(), logout: vi.fn(), setLoading: vi.fn(), setError: vi.fn(),
    })),
    { getState: vi.fn(() => ({
      user: null, token: null, isAuthenticated: false, setUser: vi.fn(), logout: vi.fn(),
    })) }
  ),
}));

import { renderHook, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from '../../../auth/AuthProvider';

function createWrapper() {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <AuthProvider>{children}</AuthProvider>;
  };
}

describe('AuthProvider integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockKeycloak.token = undefined;
    mockKeycloak.tokenParsed = undefined;
    mockKeycloak.authenticated = false;
  });

  it('starts in bootstrapping phase', () => {
    mockInitKeycloak.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });
    expect(result.current.phase).toBe('bootstrapping');
  });

  it('transitions to unauthenticated when Keycloak returns false', async () => {
    mockInitKeycloak.mockResolvedValue(false);
    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.phase).toBe('unauthenticated'));
  });

  it('resolves application user from /auth/me', async () => {
    mockInitKeycloak.mockResolvedValue(true);
    mockKeycloak.updateToken.mockResolvedValue(true);
    mockGet.mockResolvedValue({
      data: {
        user_id: 'analyst_001', email: 'analyst@bankintel.hq', name: 'Analyst',
        role: 'analyst', bank_id: 'hq_main', created_at: '', last_login: '',
        status: 'active', must_change_password: false,
      },
    });

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.phase).toBe('authenticated'));
    expect(result.current.applicationUser?.user_id).toBe('analyst_001');
    expect(result.current.hasRole('analyst')).toBe(true);
    expect(result.current.hasRole('admin')).toBe(false);
  });

  it('handles unlinked user (401 USER_NOT_FOUND)', async () => {
    mockInitKeycloak.mockResolvedValue(true);
    mockKeycloak.updateToken.mockResolvedValue(true);
    mockGet.mockRejectedValue({
      response: { status: 401, data: { error: 'USER_NOT_FOUND' } },
    });

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.phase).toBe('unlinked'));
    expect(result.current.error).toContain('no Banking Intelligence account is linked');
  });

  it('handles forbidden user (403)', async () => {
    mockInitKeycloak.mockResolvedValue(true);
    mockKeycloak.updateToken.mockResolvedValue(true);
    mockGet.mockRejectedValue({
      response: { status: 403, data: { error: 'INSUFFICIENT_PERMISSIONS' } },
    });

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.phase).toBe('forbidden'));
  });

  it('does not store tokens in localStorage', async () => {
    mockInitKeycloak.mockResolvedValue(true);
    mockKeycloak.updateToken.mockResolvedValue(true);
    mockGet.mockResolvedValue({
      data: {
        user_id: 'analyst_001', email: 'analyst@bankintel.hq', name: 'Analyst',
        role: 'analyst', bank_id: 'hq_main', created_at: '', last_login: '',
        status: 'active', must_change_password: false,
      },
    });

    renderHook(() => useAuth(), { wrapper: createWrapper() });
    await waitFor(() => expect(mockGet).toHaveBeenCalled());
    expect(localStorage.getItem('auth_token')).toBeNull();
  });
});
