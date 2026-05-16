// src/hooks/useQuery.ts
import { useCallback } from 'react';
import { useQueryStore } from '../stores/queryStore';
import { useAgentStore } from '../stores/agentStore';
import { submitQuery } from '../api/queries';
import type { QueryFormat } from '../types/query';
import type { AgentLogEntry } from '../types/agent';
import { PIPELINE_STEP_META } from '../types/query';

export function useQuery() {
  const {
    currentQuery,
    currentFormat,
    status,
    activeResult,
    pipelineSteps,
    history,
    setStatus,
    setActiveResult,
    resetPipeline,
    addToHistory,
    setQuery,
    setFormat,
  } = useQueryStore();

  const { addLog } = useAgentStore();

  const runQuery = useCallback(
    async (queryOverride?: string, formatOverride?: QueryFormat) => {
      const q = queryOverride ?? currentQuery;
      const f = formatOverride ?? currentFormat;
      if (!q.trim() || status === 'running') return;

      resetPipeline();
      setStatus('running');

      const result = await submitQuery({ query: q, format: f });

      // Inject pipeline steps into agent log
      result.pipelineSteps.forEach((step) => {
        const meta = PIPELINE_STEP_META[step.name as keyof typeof PIPELINE_STEP_META];
        if (step.request) {
          addLog({
            id:        crypto.randomUUID(),
            timestamp: step.startedAt ?? new Date().toISOString(),
            agentName: step.name as AgentLogEntry['agentName'],
            direction: 'request',
            data:      step.request,
            status:    'success',
            queryId:   result.id,
          });
        }
        if (step.response || step.error) {
          addLog({
            id:         crypto.randomUUID(),
            timestamp:  step.completedAt ?? new Date().toISOString(),
            agentName:  step.name as AgentLogEntry['agentName'],
            direction:  step.error ? 'error' : 'response',
            data:       step.error ?? step.response,
            durationMs: step.durationMs,
            status:     step.error ? 'error' : 'success',
            queryId:    result.id,
          });
        }
      });

      setStatus(result.status);
      setActiveResult(result);
      addToHistory(result);
    },
    [currentQuery, currentFormat, status, resetPipeline, setStatus, setActiveResult, addToHistory, addLog],
  );

  const clearQuery = useCallback(() => {
    setQuery('');
    resetPipeline();
  }, [setQuery, resetPipeline]);

  return {
    query:  currentQuery,
    format: currentFormat,
    status,
    result: activeResult,
    pipelineSteps,
    history,
    setQuery,
    setFormat,
    runQuery,
    clearQuery,
  };
}
