// src/api/queries.ts
import apiClient from './client';
import type { QueryRequest, QueryResult, PipelineStep } from '../types/query';

export async function submitQuery(req: QueryRequest): Promise<QueryResult> {
  const start = Date.now();
  const id = crypto.randomUUID();

  try {
    const { data } = await apiClient.post('/query', {
      query: req.query,
      format: req.format,
    });

    const steps: PipelineStep[] = (data.pipeline_steps ?? []).map((s: {
      agent?: string;
      name?: string;
      status?: string;
      duration_ms?: number;
      request?: unknown;
      response?: unknown;
      error?: string;
    }) => ({
      name:        s.agent ?? s.name ?? 'unknown',
      displayName: s.agent ?? s.name ?? 'Unknown',
      status:      s.status === 'success' ? 'success' : s.status === 'error' ? 'error' : 'success',
      durationMs:  s.duration_ms,
      request:     s.request,
      response:    s.response,
      error:       s.error,
    }));

    return {
      id,
      query:       req.query,
      format:      req.format,
      status:      data.status === 'success' ? 'success' : 'error',
      submittedAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
      results:     Array.isArray(data.results) ? data.results : [],
      metadata: {
        rowsReturned:        data.metadata?.rows_returned ?? data.metadata?.rowsReturned ?? 0,
        executionTimeMs:     data.metadata?.execution_time_ms ?? Date.now() - start,
        dataFreshness:       data.metadata?.data_freshness ?? 'real-time',
        source:              data.metadata?.source ?? 'database',
        cached:              data.metadata?.cached ?? false,
        userRole:            data.metadata?.user_role ?? 'analyst',
        totalPipelineTimeMs: Date.now() - start,
        agentTimings:        data.metadata?.agent_timings,
      },
      pipelineSteps: steps,
      rawResponse:   data,
      error: data.status !== 'success' ? (data.message ?? 'Query failed') : undefined,
    };
  } catch (err: unknown) {
    const errMsg = (err as { response?: { data?: { detail?: string; message?: string } }; message?: string })
      ?.response?.data?.detail
      ?? (err as { message?: string })?.message
      ?? 'Network error';

    return {
      id,
      query:         req.query,
      format:        req.format,
      status:        'error',
      submittedAt:   new Date().toISOString(),
      completedAt:   new Date().toISOString(),
      pipelineSteps: [],
      error:         typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg),
    };
  }
}

export async function login(username: string, password: string): Promise<{ token: string; role: string; userId: string }> {
  const form = new FormData();
  form.append('username', username);
  form.append('password', password);

  const { data } = await apiClient.post('/auth/login', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

  return {
    token:  data.access_token,
    role:   data.user_role,
    userId: data.user_id,
  };
}

export async function checkHealth(): Promise<boolean> {
  try {
    const { data } = await apiClient.get('/health');
    return data.status === 'healthy';
  } catch {
    return false;
  }
}
