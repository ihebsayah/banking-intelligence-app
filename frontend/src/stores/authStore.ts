// src/stores/authStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, AuthState } from '../types/auth';

interface AuthActions {
  setUser: (user: User, token: string) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      setUser: (user, token) => {
        // In Keycloak mode, don't persist tokens to localStorage (Keycloak-js manages its own storage)
        // In legacy mode, store as before
        if (token !== 'keycloak') {
          localStorage.setItem('auth_token', token);
        }
        set({ user, token: token === 'keycloak' ? 'keycloak' : token, isAuthenticated: true, error: null });
      },
      logout: () => {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_role');
        localStorage.removeItem('user_id');
        set({ user: null, token: null, isAuthenticated: false, error: null });
      },
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
    }),
    {
      name: 'banking-auth',
      partialize: (state) => ({
        // Only persist user info in Keycloak mode, not tokens
        user: state.user,
        token: state.token === 'keycloak' ? null : state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
