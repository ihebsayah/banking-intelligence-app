// src/stores/bankingQueryStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { QueryResult, BankingQueryHistoryItem } from '../types/insights';

interface BankingQueryState {
  currentResult: QueryResult | null;
  history: BankingQueryHistoryItem[];
  activeTab: 'table' | 'json' | 'chart' | 'csv';
  isQuerying: boolean;
  error: string | null;
  currentQuery: string;
}

interface BankingQueryActions {
  setCurrentResult: (result: QueryResult) => void;
  addToHistory: (item: BankingQueryHistoryItem) => void;
  removeFromHistory: (id: string) => void;
  clearHistory: () => void;
  setActiveTab: (tab: 'table' | 'json' | 'chart' | 'csv') => void;
  setQuerying: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setCurrentQuery: (q: string) => void;
}

export const useBankingQueryStore = create<BankingQueryState & BankingQueryActions>()(
  persist(
    (set) => ({
      currentResult: null,
      history: [],
      activeTab: 'table',
      isQuerying: false,
      error: null,
      currentQuery: '',
      setCurrentResult: (result) => set({ currentResult: result, error: null }),
      addToHistory: (item) => set((s) => ({
        history: [item, ...s.history].slice(0, 20),
      })),
      removeFromHistory: (id) => set((s) => ({
        history: s.history.filter((h) => h.id !== id),
      })),
      clearHistory: () => set({ history: [] }),
      setActiveTab: (activeTab) => set({ activeTab }),
      setQuerying: (isQuerying) => set({ isQuerying }),
      setError: (error) => set({ error }),
      setCurrentQuery: (currentQuery) => set({ currentQuery }),
    }),
    { name: 'banking-query-history', partialize: (s) => ({ history: s.history }) }
  )
);
