// src/api/agents.ts
import apiClient from './client';
import type { AgentHealth, AgentStats, SystemMetrics } from '../types/agent';
import type { SQLValidationResult } from '../types/results';
import { AGENT_REGISTRY } from '../types/agent';

// Check individual agent health
async function checkAgentHealth(port: number, name: string): Promise<AgentHealth> {
  const url = `http://localhost:${port}`;
  const start = Date.now();

  try {
    const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(3000) });
    const ms = Date.now() - start;
    const data = await res.json().catch(() => ({}));
    const status = ms < 100 ? 'healthy' : ms < 500 ? 'slow' : 'slow';

    return {
      name: name as AgentHealth['name'],
      status,
      responseTimeMs:    ms,
      avgResponseTimeMs: ms,
      requestsPerMin:    0,
      errorsPerMin:      0,
      lastCheck:         new Date().toISOString(),
      url,
      port,
    };
  } catch {
    return {
      name:              name as AgentHealth['name'],
      status:            'down',
      responseTimeMs:    0,
      avgResponseTimeMs: 0,
      requestsPerMin:    0,
      errorsPerMin:      0,
      lastCheck:         new Date().toISOString(),
      url,
      port,
    };
  }
}

export async function getAllAgentHealth(): Promise<AgentHealth[]> {
  const results = await Promise.all(
    AGENT_REGISTRY.map((a) => checkAgentHealth(a.port, a.name))
  );
  return results;
}

export async function getAgentStats(name: string): Promise<AgentStats> {
  // Stub — real impl would hit monitoring endpoint
  return {
    name:              name as AgentStats['name'],
    totalCalls:        Math.floor(Math.random() * 500),
    successRate:       0.95 + Math.random() * 0.05,
    avgResponseTimeMs: 80 + Math.random() * 200,
    p95ResponseTimeMs: 300 + Math.random() * 500,
    errorCount:        Math.floor(Math.random() * 5),
  };
}

export async function getSystemMetrics(): Promise<SystemMetrics> {
  // Stub — real impl would hit /api/system/metrics
  return {
    totalQueriesProcessed: 1247,
    avgPipelineTimeMs:     1820,
    cacheHitRate:          0.34,
    errorRate:             0.02,
    concurrentUsers:       1,
    uptime:                '4h 32m',
  };
}

export async function testSQLSafety(sql: string): Promise<SQLValidationResult> {
  try {
    const { data } = await apiClient.post('/test/sql', { sql });
    return data;
  } catch {
    // Fallback: basic client-side check
    const dangerousPatterns = [
      /drop\s+table/i, /delete\s+from/i, /truncate/i, /alter\s+table/i,
      /insert\s+into/i, /update\s+\w+\s+set/i, /create\s+/i, /exec\s*\(/i,
      /xp_cmdshell/i, /;\s*--/i, /union\s+select/i,
    ];
    const issues: string[] = [];
    dangerousPatterns.forEach((p) => {
      if (p.test(sql)) issues.push(`Dangerous pattern detected: ${p.source.split('\\')[0]}`);
    });
    const valid = sql.trim().length > 0;
    return {
      valid,
      safe:    issues.length === 0,
      issues,
      rawInput: sql,
    };
  }
}

export async function testSingleAgent(agentName: string, input: unknown): Promise<{
  success: boolean;
  output: unknown;
  durationMs: number;
  error?: string;
}> {
  const agentInfo = AGENT_REGISTRY.find((a) => a.name === agentName);
  if (!agentInfo) return { success: false, output: null, durationMs: 0, error: 'Unknown agent' };

  const start = Date.now();
  try {
    const url = `http://localhost:${agentInfo.port}`;
    const endpoint = agentName === 'intent' ? '/analyze'
                   : agentName === 'schema'  ? '/understand'
                   : agentName === 'sql'     ? '/generate'
                   : '/process';

    const res = await fetch(`${url}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
      signal: AbortSignal.timeout(10_000),
    });
    const output = await res.json();
    return { success: res.ok, output, durationMs: Date.now() - start };
  } catch (e) {
    return { success: false, output: null, durationMs: Date.now() - start, error: String(e) };
  }
}
