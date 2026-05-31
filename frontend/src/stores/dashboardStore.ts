// src/stores/dashboardStore.ts
import { create } from 'zustand';
import type { KPI, ChartData, DashboardState } from '../types/dashboard';

interface DashboardActions {
  setKPIs: (kpis: KPI[]) => void;
  updateKPI: (kpi: KPI) => void;
  setChartData: (chartId: string, data: ChartData) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setLastRefreshed: (ts: string) => void;
}

export const useDashboardStore = create<DashboardState & DashboardActions>((set) => ({
  kpis: [],
  charts: {},
  isLoading: false,
  error: null,
  lastRefreshed: null,
  setKPIs: (kpis) => set({ kpis }),
  updateKPI: (kpi) => set((state) => ({
    kpis: state.kpis.map((k) => k.kpi_id === kpi.kpi_id ? kpi : k),
  })),
  setChartData: (chartId, data) => set((state) => ({
    charts: { ...state.charts, [chartId]: data },
  })),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  setLastRefreshed: (lastRefreshed) => set({ lastRefreshed }),
}));
