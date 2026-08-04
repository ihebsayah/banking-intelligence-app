// src/api/client.ts
import axios from 'axios';
import { env } from '../config/env';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
});

// Lazily load the Keycloak module exactly once (promise-cached so concurrent
// callers share a single in-flight import instead of re-evaluating the module).
let keycloakModule: Promise<typeof import('../auth/keycloak')> | null = null;
function loadKeycloakModule() {
  keycloakModule ??= import('../auth/keycloak');
  return keycloakModule;
}

// Attach stored token to every request
apiClient.interceptors.request.use(async (config) => {
  if (env.AUTH_PROVIDER === 'keycloak') {
    // Keycloak mode: get fresh token from keycloak-js
    try {
      const { getKeycloak } = await loadKeycloakModule();
      const kc = getKeycloak();
      if (kc.token) {
        await kc.updateToken(60);
        config.headers.Authorization = `Bearer ${kc.token}`;
      }
    } catch {
      // Keycloak not initialized yet, skip
    }
  } else {
    // Legacy mode: read from localStorage
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Track if a refresh is in progress to prevent loops
let refreshPromise: Promise<boolean> | null = null;

// Intercept 401 → attempt refresh once, then redirect
apiClient.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status !== 401 || env.AUTH_PROVIDER !== 'keycloak') {
      // Legacy 401 handling
      if (err.response?.status === 401 && env.AUTH_PROVIDER === 'legacy') {
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
      }
      return Promise.reject(err);
    }

    // Avoid infinite retry loops (already attempted refresh once)
    const originalRequest = err.config;
    if (originalRequest._retry) {
      return Promise.reject(err);
    }
    originalRequest._retry = true;

    // Deduplicate concurrent refresh attempts
    if (!refreshPromise) {
      refreshPromise = (async () => {
        try {
          const { getKeycloak } = await loadKeycloakModule();
          const kc = getKeycloak();
          // `updateToken(-1)` forces a real refresh attempt. It resolves `true` after a
          // successful refresh and REJECTS when the refresh fails (e.g. SSO session
          // expired). Resolving `false` (token still valid) is not possible here.
          return await kc.updateToken(-1);
        } catch {
          return false;
        } finally {
          refreshPromise = null;
        }
      })();
    }

    const refreshed = await refreshPromise;

    if (refreshed) {
      const { getKeycloak } = await loadKeycloakModule();
      const kc = getKeycloak();
      originalRequest.headers.Authorization = `Bearer ${kc.token}`;
      return apiClient(originalRequest);
    }

    // Refresh failed — let AuthProvider handle the expired state via onTokenExpired
    return Promise.reject(err);
  },
);

export default apiClient;
