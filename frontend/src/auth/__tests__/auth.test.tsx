import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import React from 'react';

const mockKeycloak = {
  init: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  updateToken: vi.fn(),
  isTokenExpired: vi.fn(),
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

vi.mock('../../config/env', () => ({
  env: {
    AUTH_PROVIDER: 'keycloak',
    KEYCLOAK_URL: 'http://localhost:8080',
    KEYCLOAK_REALM: 'banking-intelligence',
    KEYCLOAK_CLIENT_ID: 'banking-portal-web',
    API_BASE_URL: '/api',
  },
  requireKeycloakEnv: vi.fn(),
}));

vi.mock('../../auth/keycloak', () => ({
  getKeycloak: vi.fn(() => mockKeycloak),
  initKeycloak: mockInitKeycloak,
  getKeycloakToken: vi.fn(() => mockKeycloak.token),
}));

vi.mock('../../api/client', () => ({
  apiClient: {
    get: mockGet,
    post: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}));

const mockSetUser = vi.fn();
const mockLogoutStore = vi.fn();

vi.mock('../../stores/authStore', () => ({
  useAuthStore: Object.assign(
    vi.fn(() => ({
      user: null, token: null, isAuthenticated: false, isLoading: false, error: null,
      setUser: mockSetUser, logout: mockLogoutStore, setLoading: vi.fn(), setError: vi.fn(),
    })),
    { getState: vi.fn(() => ({
      user: null, token: null, isAuthenticated: false, setUser: mockSetUser, logout: mockLogoutStore,
    })) }
  ),
}));

import { AuthProvider, useAuth } from '../AuthProvider';

function createWrapper() {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <AuthProvider>{children}</AuthProvider>;
  };
}

const ANALYST_ME = {
  user_id: 'analyst_001',
  email: 'analyst@bankintel.hq',
  name: 'Analyst',
  role: 'analyst',
  bank_id: 'hq_main',
  created_at: '',
  last_login: '',
  status: 'active',
  must_change_password: false,
  permissions: ['view_dashboard', 'view_cases'],
};

async function bootAuthenticatedUser() {
  mockInitKeycloak.mockResolvedValue(true);
  mockKeycloak.token = 'test-token';
  mockKeycloak.tokenParsed = { exp: Math.floor(Date.now() / 1000) + 600 };
  mockKeycloak.authenticated = true;
  mockGet.mockResolvedValue({ data: ANALYST_ME });
  const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });
  await waitFor(() => expect(result.current.phase).toBe('authenticated'));
  return result;
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockKeycloak.token = undefined;
    mockKeycloak.tokenParsed = undefined;
    mockKeycloak.authenticated = false;
    mockKeycloak.isTokenExpired.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
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

  it('calls /auth/me when Keycloak is authenticated', async () => {
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

  it('stays authenticated when a scheduled refresh finds the token still valid (updateToken resolves false)', async () => {
    vi.useFakeTimers();
    mockInitKeycloak.mockResolvedValue(true);
    mockKeycloak.updateToken.mockResolvedValue(false); // token still valid → no refresh
    mockKeycloak.token = 'test-token';
    mockKeycloak.tokenParsed = { exp: Math.floor(Date.now() / 1000) + 600 };
    mockGet.mockResolvedValue({ data: ANALYST_ME });

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(result.current.phase).toBe('authenticated');

    // The refresh timer (armed for 540s) fires: updateToken resolves `false` because the
    // token is still valid. This must NOT be treated as a failure/logout.
    await act(async () => { await vi.advanceTimersByTimeAsync(600_000); });
    expect(result.current.phase).toBe('authenticated');
    expect(result.current.error).toBeNull();
    expect(result.current.hasRole('analyst')).toBe(true);
    expect(result.current.permissions).toEqual(['view_dashboard', 'view_cases']);
  });

  it('calls updateToken when the scheduled refresh fires near expiry and stays authenticated', async () => {
    vi.useFakeTimers();
    mockInitKeycloak.mockResolvedValue(true);
    mockKeycloak.updateToken.mockResolvedValue(true); // refresh succeeds
    mockKeycloak.token = 'test-token';
    mockKeycloak.tokenParsed = { exp: Math.floor(Date.now() / 1000) + 65 }; // timer delay floor = 5s
    mockGet.mockResolvedValue({ data: ANALYST_ME });

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(result.current.phase).toBe('authenticated');

    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(mockKeycloak.updateToken).toHaveBeenCalled();
    expect(result.current.phase).toBe('authenticated');
    expect(result.current.hasRole('analyst')).toBe(true);
  });

  it('keeps the session alive when onTokenExpired fires and the refresh succeeds', async () => {
    const result = await bootAuthenticatedUser();
    mockKeycloak.updateToken.mockResolvedValue(true);
    const onExpired = mockKeycloak.onTokenExpired;
    expect(onExpired).toBeDefined();

    await act(async () => { await onExpired!(); });
    expect(result.current.phase).toBe('authenticated');
    expect(result.current.error).toBeNull();
  });

  it('logs the user out when onTokenExpired fires and the refresh genuinely fails', async () => {
    const result = await bootAuthenticatedUser();
    mockKeycloak.updateToken.mockRejectedValue(new Error('SSO session expired'));
    const onExpired = mockKeycloak.onTokenExpired;

    await act(async () => { await onExpired!(); });
    await waitFor(() => expect(result.current.phase).toBe('expired'));
    expect(result.current.error).toContain('expired');
  });

  it('refreshes a near-expiry token on window focus', async () => {
    const result = await bootAuthenticatedUser();
    mockKeycloak.isTokenExpired.mockReturnValue(true); // token close to expiry
    mockKeycloak.updateToken.mockResolvedValue(true);

    await act(async () => { window.dispatchEvent(new Event('focus')); });
    expect(mockKeycloak.updateToken).toHaveBeenCalled();
    expect(result.current.phase).toBe('authenticated');
  });

  it('does not refresh on window focus when the token is far from expiry', async () => {
    const result = await bootAuthenticatedUser();
    mockKeycloak.isTokenExpired.mockReturnValue(false);
    mockKeycloak.updateToken.mockClear();

    await act(async () => { window.dispatchEvent(new Event('focus')); });
    expect(mockKeycloak.updateToken).not.toHaveBeenCalled();
    expect(result.current.phase).toBe('authenticated');
  });

  it('returns the current token from getAccessToken without logging out when still valid', async () => {
    const result = await bootAuthenticatedUser();
    mockKeycloak.updateToken.mockResolvedValue(false); // token still valid
    mockKeycloak.token = 'current-token';

    let token: string | undefined;
    await act(async () => { token = await result.current.getAccessToken(); });
    expect(token).toBe('current-token');
    expect(result.current.phase).toBe('authenticated');
    expect(result.current.error).toBeNull();
  });

  it('clears the refresh timer on unmount', async () => {
    mockInitKeycloak.mockResolvedValue(true);
    mockKeycloak.updateToken.mockResolvedValue(true);
    mockKeycloak.token = 'test-token';
    mockKeycloak.tokenParsed = { exp: Math.floor(Date.now() / 1000) + 600 };
    mockGet.mockResolvedValue({ data: ANALYST_ME });

    const clearSpy = vi.spyOn(globalThis, 'clearTimeout');
    const { unmount, result } = renderHook(() => useAuth(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.phase).toBe('authenticated'));

    const callsBefore = clearSpy.mock.calls.length;
    unmount();
    expect(clearSpy.mock.calls.length).toBeGreaterThan(callsBefore);
    clearSpy.mockRestore();
  });

  it('remains authenticated on a direct page refresh (existing SSO session + /auth/me)', async () => {
    mockInitKeycloak.mockResolvedValue(true);
    mockKeycloak.updateToken.mockResolvedValue(true);
    mockKeycloak.token = 'existing-session-token';
    mockKeycloak.tokenParsed = { exp: Math.floor(Date.now() / 1000) + 600 };
    mockGet.mockResolvedValue({ data: ANALYST_ME });

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.phase).toBe('authenticated'));
    expect(result.current.phase).not.toBe('unauthenticated');
    expect(result.current.applicationUser?.user_id).toBe('analyst_001');
    expect(result.current.hasPermission('view_cases')).toBe(true);
  });
});
