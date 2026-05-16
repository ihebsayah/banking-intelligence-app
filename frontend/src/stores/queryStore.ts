// src/stores/queryStore.ts
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { QueryResult, QueryFormat, PipelineStep } from '../types/query';

interface QueryState {
  // Current query
  currentQuery:    string;
  currentFormat:   QueryFormat;
  status:          'idle' | 'running' | 'success' | 'error';
  activeResult:    QueryResult | null;
  pipelineSteps:   PipelineStep[];

  // History
  history:         QueryResult[];

  // Auth
  authToken:       string | null;
  userRole:        string;
  userId:          string;

  // Actions
  setQuery:        (q: string) => void;
  setFormat:       (f: QueryFormat) => void;
  setStatus:       (s: QueryState['status']) => void;
  setActiveResult: (r: QueryResult | null) => void;
  updateStep:      (name: string, updates: Partial<PipelineStep>) => void;
  resetPipeline:   () => void;
  addToHistory:    (r: QueryResult) => void;
  clearHistory:    () => void;
  setAuth:         (token: string, role: string, userId: string) => void;
  clearAuth:       () => void;
}

export const useQueryStore = create<QueryState>()(
  devtools(
    (set) => ({
      currentQuery:    '',
      currentFormat:   'json',
      status:          'idle',
      activeResult:    null,
      pipelineSteps:   [],
      history:         [],
      authToken:       localStorage.getItem('auth_token'),
      userRole:        localStorage.getItem('user_role') ?? 'analyst',
      userId:          localStorage.getItem('user_id') ?? 'analyst_001',

      setQuery:        (q)  => set({ currentQuery: q }),
      setFormat:       (f)  => set({ currentFormat: f }),
      setStatus:       (s)  => set({ status: s }),
      setActiveResult: (r)  => set({ activeResult: r }),

      updateStep: (name, updates) =>
        set((state) => ({
          pipelineSteps: state.pipelineSteps.map((s) =>
            s.name === name ? { ...s, ...updates } : s
          ),
        })),

      resetPipeline: () =>
        set({
          status:        'idle',
          activeResult:  null,
          pipelineSteps: [],
        }),

      addToHistory: (r) =>
        set((state) => ({
          history: [r, ...state.history].slice(0, 50),
        })),

      clearHistory: () => set({ history: [] }),

      setAuth: (token, role, userId) => {
        localStorage.setItem('auth_token', token);
        localStorage.setItem('user_role', role);
        localStorage.setItem('user_id', userId);
        set({ authToken: token, userRole: role, userId });
      },

      clearAuth: () => {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_role');
        localStorage.removeItem('user_id');
        set({ authToken: null, userRole: 'analyst', userId: '' });
      },
    }),
    { name: 'query-store' },
  ),
);
