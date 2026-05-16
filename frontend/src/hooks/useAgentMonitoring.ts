// src/hooks/useAgentMonitoring.ts
import { useEffect, useCallback } from 'react';
import { useAgentStore } from '../stores/agentStore';
import { useConfigStore } from '../stores/configStore';
import { getAllAgentHealth, getSystemMetrics } from '../api/agents';

export function useAgentMonitoring() {
  const {
    setAgentHealth,
    setHealthLoading,
    setSystemMetrics,
    agentHealth,
    communicationLogs,
    systemMetrics,
    wsConnected,
    logFilter,
    logSearch,
  } = useAgentStore();

  const { autoRefreshHealth, healthRefreshMs } = useConfigStore();

  const refreshHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const [health, metrics] = await Promise.all([
        getAllAgentHealth(),
        getSystemMetrics(),
      ]);
      setAgentHealth(health);
      setSystemMetrics(metrics);
    } finally {
      setHealthLoading(false);
    }
  }, [setAgentHealth, setHealthLoading, setSystemMetrics]);

  // Auto-refresh agent health
  useEffect(() => {
    refreshHealth();
    if (!autoRefreshHealth) return;

    const id = setInterval(refreshHealth, healthRefreshMs);
    return () => clearInterval(id);
  }, [refreshHealth, autoRefreshHealth, healthRefreshMs]);

  // Filtered logs
  const filteredLogs = communicationLogs.filter((log) => {
    const passFilter = logFilter === 'all' || log.agentName === logFilter;
    const passSearch = !logSearch || JSON.stringify(log).toLowerCase().includes(logSearch.toLowerCase());
    return passFilter && passSearch;
  });

  return {
    agentHealth: Object.values(agentHealth),
    systemMetrics,
    communicationLogs: filteredLogs,
    wsConnected,
    refreshHealth,
  };
}
