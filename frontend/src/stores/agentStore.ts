// src/stores/agentStore.ts
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { AgentHealth, AgentLogEntry, SystemMetrics } from '../types/agent';

interface AgentState {
  // Health
  agentHealth:       Record<string, AgentHealth>;
  lastHealthCheck:   string | null;
  healthLoading:     boolean;

  // Logs
  communicationLogs: AgentLogEntry[];
  maxLogs:           number;

  // Metrics
  systemMetrics:     SystemMetrics | null;

  // WebSocket status
  wsConnected:       boolean;
  wsUrl:             string;

  // Filter
  logFilter:         string;   // agent name filter
  logSearch:         string;   // text search

  // Actions
  setAgentHealth:     (health: AgentHealth[]) => void;
  setHealthLoading:   (v: boolean) => void;
  addLog:             (entry: AgentLogEntry) => void;
  clearLogs:          () => void;
  setMaxLogs:         (n: number) => void;
  setSystemMetrics:   (m: SystemMetrics) => void;
  setWsConnected:     (v: boolean) => void;
  setWsUrl:           (url: string) => void;
  setLogFilter:       (f: string) => void;
  setLogSearch:       (s: string) => void;
}

export const useAgentStore = create<AgentState>()(
  devtools(
    (set) => ({
      agentHealth:       {},
      lastHealthCheck:   null,
      healthLoading:     false,
      communicationLogs: [],
      maxLogs:           500,
      systemMetrics:     null,
      wsConnected:       false,
      wsUrl:             typeof window !== 'undefined' ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/monitoring` : 'ws://localhost:8001/ws/monitoring',
      logFilter:         'all',
      logSearch:         '',

      setAgentHealth: (health) =>
        set({
          agentHealth: Object.fromEntries(health.map((h) => [h.name, h])),
          lastHealthCheck: new Date().toISOString(),
        }),

      setHealthLoading: (v) => set({ healthLoading: v }),

      addLog: (entry) =>
        set((state) => {
          const logs = [entry, ...state.communicationLogs];
          return { communicationLogs: logs.slice(0, state.maxLogs) };
        }),

      clearLogs: () => set({ communicationLogs: [] }),

      setMaxLogs: (n) => set({ maxLogs: n }),

      setSystemMetrics: (m) => set({ systemMetrics: m }),

      setWsConnected: (v) => set({ wsConnected: v }),

      setWsUrl: (url) => set({ wsUrl: url }),

      setLogFilter: (f) => set({ logFilter: f }),

      setLogSearch: (s) => set({ logSearch: s }),
    }),
    { name: 'agent-store' },
  ),
);
