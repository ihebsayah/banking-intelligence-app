import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { initKeycloak, getKeycloak } from './keycloak';
import { apiClient } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import { env } from '../config/env';
import type { User } from '../types/auth';

export type AuthPhase =
  | 'bootstrapping'
  | 'unauthenticated'
  | 'loading-user'
  | 'authenticated'
  | 'unlinked'
  | 'forbidden'
  | 'expired'
  | 'error';

interface AuthContextValue {
  phase: AuthPhase;
  applicationUser: User | null;
  login: () => void;
  logout: () => void;
  getAccessToken: () => Promise<string | undefined>;
  hasRole: (role: string) => boolean;
  hasPermission: (perm: string) => boolean;
  permissions: string[];
  error: string | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

interface MeResponse {
  user_id: string;
  email: string;
  name: string;
  role: string;
  bank_id: string;
  created_at: string;
  last_login: string;
  status: string;
  must_change_password: boolean;
}

async function fetchApplicationUser(): Promise<MeResponse> {
  const res = await apiClient.get<MeResponse>('/auth/me');
  return res.data;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [phase, setPhase] = useState<AuthPhase>('bootstrapping');
  const [applicationUser, setApplicationUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inflightRefresh = useRef<Promise<boolean> | null>(null);

  const store = useAuthStore;
  const isKeycloak = env.AUTH_PROVIDER === 'keycloak';

  // ── Sync authStore with AuthProvider state ──────────────────────────────
  useEffect(() => {
    if (phase === 'authenticated' && applicationUser) {
      store.getState().setUser(applicationUser, 'keycloak');
    }
  }, [phase, applicationUser, store]);

  // ── Fetch /auth/me and resolve application user ─────────────────────────
  const resolveApplicationUser = useCallback(async (): Promise<boolean> => {
    try {
      setPhase('loading-user');
      const me = await fetchApplicationUser();

      if (me.status !== 'active') {
        setPhase('forbidden');
        setError('Your account is inactive or suspended. Contact an administrator.');
        return false;
      }

      const user: User = {
        user_id: me.user_id,
        email: me.email,
        name: me.name,
        role: me.role as User['role'],
        bank_id: me.bank_id,
        created_at: me.created_at,
        last_login: me.last_login,
      };

      setApplicationUser(user);
      setPhase('authenticated');
      setError(null);

      // Load permissions from backend response (stored in Zustand for UX only)
      // Permissions come from backend, not Keycloak realm roles
      return true;
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      const data = (err as { response?: { data?: { error?: string; message?: string } } })?.response?.data;

      if (status === 401) {
        if (data?.error === 'USER_NOT_FOUND') {
          setPhase('unlinked');
          setError('Your identity was authenticated successfully, but no Banking Intelligence account is linked to it. Contact an administrator.');
        } else if (data?.error === 'TOKEN_EXPIRED') {
          // Try refresh once
          const refreshed = await refreshKeycloakToken();
          if (refreshed) {
            try {
              const me = await fetchApplicationUser();
              const user: User = {
                user_id: me.user_id,
                email: me.email,
                name: me.name,
                role: me.role as User['role'],
                bank_id: me.bank_id,
                created_at: me.created_at,
                last_login: me.last_login,
              };
              setApplicationUser(user);
              setPhase('authenticated');
              setError(null);
              return true;
            } catch {
              setPhase('expired');
              setError('Your session has expired. Please sign in again.');
              return false;
            }
          }
          setPhase('expired');
          setError('Your session has expired. Please sign in again.');
          return false;
        } else {
          setPhase('expired');
          setError('Authentication failed. Please sign in again.');
          return false;
        }
      } else if (status === 403) {
        setPhase('forbidden');
        setError('You do not have permission to access this application.');
      } else {
        setPhase('error');
        setError('Unable to load your profile. Please try again later.');
      }
      return false;
    }
  }, []);

  // ── Token refresh ───────────────────────────────────────────────────────
  async function refreshKeycloakToken(): Promise<boolean> {
    if (inflightRefresh.current) return inflightRefresh.current;

    inflightRefresh.current = (async () => {
      try {
        const kc = getKeycloak();
        const refreshed = await kc.updateToken(30);
        if (refreshed) {
          scheduleRefresh();
        }
        return refreshed;
      } catch {
        return false;
      } finally {
        inflightRefresh.current = null;
      }
    })();

    return inflightRefresh.current;
  }

  function scheduleRefresh() {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    const kc = getKeycloak();
    if (!kc.tokenParsed?.exp) return;

    // Refresh 60 seconds before expiry
    const expiresAt = kc.tokenParsed.exp * 1000;
    const now = Date.now();
    const delay = Math.max(expiresAt - now - 60_000, 5_000);

    refreshTimerRef.current = setTimeout(async () => {
      const ok = await refreshKeycloakToken();
      if (!ok) {
        setPhase('expired');
        setError('Your session has expired. Please sign in again.');
      }
    }, delay);
  }

  // ── Bootstrap ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isKeycloak) {
      setPhase('unauthenticated');
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const authenticated = await initKeycloak();
        if (cancelled) return;

        if (!authenticated) {
          setPhase('unauthenticated');
          return;
        }

        // Listen for token expiration
        const kc = getKeycloak();
        kc.onTokenExpired = () => {
          refreshKeycloakToken().then((ok) => {
            if (!ok) {
              setPhase('expired');
              setError('Your session has expired. Please sign in again.');
            }
          });
        };

        const resolved = await resolveApplicationUser();
        if (!cancelled && resolved) {
          scheduleRefresh();
        }
      } catch (err) {
        if (!cancelled) {
          setPhase('error');
          setError('Failed to initialize authentication. Check your configuration.');
        }
      }
    })();

    return () => {
      cancelled = true;
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, [isKeycloak, resolveApplicationUser]);

  // ── Login / Logout ──────────────────────────────────────────────────────
  const login = useCallback(() => {
    const kc = getKeycloak();
    kc.login({ redirectUri: window.location.origin });
  }, []);

  const logout = useCallback(() => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    store.getState().logout();
    setApplicationUser(null);
    setPermissions([]);
    setPhase('unauthenticated');
    setError(null);

    if (isKeycloak) {
      const kc = getKeycloak();
      kc.logout({ redirectUri: window.location.origin });
    }
  }, [isKeycloak, store]);

  const getAccessToken = useCallback(async (): Promise<string | undefined> => {
    if (!isKeycloak) return undefined;
    const kc = getKeycloak();
    const ok = await kc.updateToken(30);
    if (!ok) {
      setPhase('expired');
      return undefined;
    }
    return kc.token;
  }, [isKeycloak]);

  const hasRole = useCallback((role: string): boolean => {
    if (!applicationUser) return false;
    return applicationUser.role === role;
  }, [applicationUser]);

  const hasPermission = useCallback((perm: string): boolean => {
    return permissions.includes(perm);
  }, [permissions]);

  return (
    <AuthContext.Provider value={{ phase, applicationUser, login, logout, getAccessToken, hasRole, hasPermission, permissions, error }}>
      {children}
    </AuthContext.Provider>
  );
}
