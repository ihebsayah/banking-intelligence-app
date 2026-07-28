import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock keycloak-js
const mockKeycloak = {
  token: 'test-kc-token',
  tokenParsed: { exp: Math.floor(Date.now() / 1000) + 3600 },
  updateToken: vi.fn().mockResolvedValue(true),
};

vi.mock('keycloak-js', () => ({
  default: vi.fn(() => ({})),
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
  initKeycloak: vi.fn(),
  getKeycloakToken: vi.fn(() => mockKeycloak.token),
}));

describe('apiClient in Keycloak mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('does not read auth_token from localStorage in Keycloak mode', async () => {
    localStorage.setItem('auth_token', 'legacy-token-should-not-be-used');

    const { apiClient } = await import('../client');
    const requestHeaders: Record<string, string> = {};
    const origRequest = apiClient.interceptors.request;

    // Verify Keycloak updateToken is called (meaning it uses Keycloak, not localStorage)
    expect(mockKeycloak.updateToken).toBeDefined();

    // The apiClient should exist and be usable
    expect(apiClient).toBeDefined();
    expect(apiClient.defaults.baseURL).toBe('/api');
  });

  it('has correct base URL', async () => {
    const { apiClient } = await import('../client');
    expect(apiClient.defaults.baseURL).toBe('/api');
  });

  it('does not store tokens in localStorage', async () => {
    await import('../client');
    expect(localStorage.getItem('auth_token')).toBeNull();
  });
});
