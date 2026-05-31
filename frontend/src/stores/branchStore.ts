// src/stores/branchStore.ts
import { create } from 'zustand';
import type { Branch, BranchState } from '../types/branch';

interface BranchActions {
  setBranches: (branches: Branch[]) => void;
  selectBranch: (id: string) => void;
  toggleCompareMode: () => void;
  addCompare: (id: string) => void;
  removeCompare: (id: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useBranchStore = create<BranchState & BranchActions>((set) => ({
  branches: [],
  selectedBranchId: null,
  compareMode: false,
  compareBranchIds: [],
  isLoading: false,
  error: null,
  setBranches: (branches) => set({ branches, selectedBranchId: branches[0]?.branch_id ?? null }),
  selectBranch: (id) => set({ selectedBranchId: id }),
  toggleCompareMode: () => set((s) => ({ compareMode: !s.compareMode, compareBranchIds: [] })),
  addCompare: (id) => set((s) => ({
    compareBranchIds: s.compareBranchIds.includes(id)
      ? s.compareBranchIds
      : [...s.compareBranchIds, id].slice(0, 3),
  })),
  removeCompare: (id) => set((s) => ({
    compareBranchIds: s.compareBranchIds.filter((b) => b !== id),
  })),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}));
