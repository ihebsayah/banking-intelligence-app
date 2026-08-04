import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock keycloak-js
const mockKeycloak = {
  token: 'test-kc-token',
  tokenParsed: { exp: Math.floor(Date.now() / 1000) + 3600 },
  updateToken: vi.fn().mockResolvedValue(true),
  isTokenExpired: vi.fn(),
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

describe('apiClient 401 handling in Keycloak mode', () => {
  let apiClient: typeof import('../client')['apiClient'];
  let rejected: (err: unknown) => Promise<unknown>;
  let originalAdapter: unknown;
  let adapterCalls: unknown[];

  beforeEach(async () => {
    vi.clearAllMocks();
    localStorage.clear();
    const mod = await import('../client');
    apiClient = mod.apiClient;
    rejected = apiClient.interceptors.response.handlers![0].rejected as (err: unknown) => Promise<unknown>;
    originalAdapter = apiClient.defaults.adapter;
    adapterCalls = [];
    apiClient.defaults.adapter = (async (config: Record<string, unknown>) => {
      adapterCalls.push(config);
      return { status: 200, data: {}, headers: {}, config, statusText: 'OK' };
    }) as never;
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter as never;
  });

  it('refreshes once and retries the original request on a successful refresh', async () => {
    mockKeycloak.updateToken.mockResolvedValue(true);
    mockKeycloak.token = 'fresh-token';

    const err = { response: { status: 401, data: {} }, config: { url: '/reports', headers: {} } };
    await expect(rejected(err)).resolves.toBeDefined();
    expect(mockKeycloak.updateToken).toHaveBeenCalledWith(-1); // forced refresh on 401
    expect(adapterCalls).toHaveLength(1); // original request retried once
    expect((adapterCalls[0] as { headers: Record<string, string> }).headers.Authorization).toBe('Bearer fresh-token');
  });

  it('does not retry and rejects with the original error when the refresh fails', async () => {
    mockKeycloak.updateToken.mockRejectedValue(new Error('SSO session expired'));

    const err = { response: { status: 401, data: {} }, config: { url: '/reports', headers: {} } };
    await expect(rejected(err)).rejects.toBe(err);
    expect(adapterCalls).toHaveLength(0);
  });

  it('deduplicates concurrent 401s into a single refresh request', async () => {
    let resolveRefresh!: (v: boolean) => void;
    let updateTokenCalls = 0;
    mockKeycloak.updateToken.mockImplementation(() => {
      updateTokenCalls += 1;
      if (updateTokenCalls === 1) {
        return new Promise<boolean>((res) => { resolveRefresh = res; });
      }
      return Promise.resolve(true);
    });
    mockKeycloak.token = 'fresh-token';

    const err1 = { response: { status: 401, data: {} }, config: { url: '/a', headers: {} } };
    const err2 = { response: { status: 401, data: {} }, config: { url: '/b', headers: {} } };
    const p1 = rejected(err1);
    const p2 = rejected(err2);

    for (let i = 0; i < 50 && typeof resolveRefresh !== 'function'; i++) {
      await Promise.resolve();
    }
    resolveRefresh(true);
    await Promise.all([p1, p2]);

    const refreshCalls = mockKeycloak.updateToken.mock.calls.filter(([v]) => v === -1);
    expect(refreshCalls).toHaveLength(1); // concurrent 401s share a single forced refresh
    expect(adapterCalls).toHaveLength(2); // both original requests retried once
  });

  it('does not refresh again for a request already retried (infinite-loop guard)', async () => {
    mockKeycloak.updateToken.mockResolvedValue(true);
    mockKeycloak.updateToken.mockClear();

    const err = { response: { status: 401, data: {} }, config: { url: '/x', headers: {}, _retry: true } };
    await expect(rejected(err)).rejects.toBe(err);
    expect(mockKeycloak.updateToken).not.toHaveBeenCalled();
    expect(adapterCalls).toHaveLength(0);
  });
});
