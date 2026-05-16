// src/stores/configStore.ts
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface ConfigState {
  // API
  apiUrl:             string;
  wsUrl:              string;
  requestTimeoutMs:   number;
  maxRetries:         number;

  // Display
  theme:              'dark' | 'light';
  defaultFormat:      'json' | 'csv' | 'table';
  autoRefreshHealth:  boolean;
  healthRefreshMs:    number;
  showTimestamps:     boolean;
  showExecutionTimes: boolean;
  logRetention:       100 | 500 | 1000 | 5000;

  // Debug
  debugMode:          boolean;
  showRawResponses:   boolean;
  showTimings:        boolean;

  // Actions
  setApiUrl:             (v: string) => void;
  setWsUrl:              (v: string) => void;
  setTimeout:            (v: number) => void;
  setMaxRetries:         (v: number) => void;
  setTheme:              (v: 'dark' | 'light') => void;
  setDefaultFormat:      (v: 'json' | 'csv' | 'table') => void;
  setAutoRefreshHealth:  (v: boolean) => void;
  setHealthRefreshMs:    (v: number) => void;
  setShowTimestamps:     (v: boolean) => void;
  setShowExecutionTimes: (v: boolean) => void;
  setLogRetention:       (v: 100 | 500 | 1000 | 5000) => void;
  setDebugMode:          (v: boolean) => void;
  setShowRawResponses:   (v: boolean) => void;
  setShowTimings:        (v: boolean) => void;
  resetToDefaults:       () => void;
}

const WS_PROTO = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const DEFAULT_WS = typeof window !== 'undefined' ? `${WS_PROTO}//${window.location.host}/ws/monitoring` : 'ws://localhost:8001/ws/monitoring';

const DEFAULTS = {
  apiUrl:             '/api',
  wsUrl:              DEFAULT_WS,
  requestTimeoutMs:   30_000,
  maxRetries:         3,
  theme:              'dark' as const,
  defaultFormat:      'json' as const,
  autoRefreshHealth:  true,
  healthRefreshMs:    5_000,
  showTimestamps:     true,
  showExecutionTimes: true,
  logRetention:       500 as const,
  debugMode:          false,
  showRawResponses:   false,
  showTimings:        true,
};

export const useConfigStore = create<ConfigState>()(
  devtools(
    persist(
      (set) => ({
        ...DEFAULTS,

        setApiUrl:             (v) => set({ apiUrl: v }),
        setWsUrl:              (v) => set({ wsUrl: v }),
        setTimeout:            (v) => set({ requestTimeoutMs: v }),
        setMaxRetries:         (v) => set({ maxRetries: v }),
        setTheme:              (v) => set({ theme: v }),
        setDefaultFormat:      (v) => set({ defaultFormat: v }),
        setAutoRefreshHealth:  (v) => set({ autoRefreshHealth: v }),
        setHealthRefreshMs:    (v) => set({ healthRefreshMs: v }),
        setShowTimestamps:     (v) => set({ showTimestamps: v }),
        setShowExecutionTimes: (v) => set({ showExecutionTimes: v }),
        setLogRetention:       (v) => set({ logRetention: v }),
        setDebugMode:          (v) => set({ debugMode: v }),
        setShowRawResponses:   (v) => set({ showRawResponses: v }),
        setShowTimings:        (v) => set({ showTimings: v }),
        resetToDefaults:       () => set({ ...DEFAULTS }),
      }),
      { name: 'banking-dashboard-config' },
    ),
    { name: 'config-store' },
  ),
);
