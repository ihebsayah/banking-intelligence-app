// src/types/agent.ts

export type AgentName =
  | 'intent'
  | 'schema'
  | 'entity_resolution'
  | 'sql'
  | 'validation'
  | 'execution'
  | 'audit'
  | 'orchestrator'
  | 'embedding';

export type AgentStatus = 'healthy' | 'slow' | 'down' | 'unknown';

export interface AgentInfo {
  name: AgentName;
  displayName: string;
  port: number;
  color: string;
  description: string;
}

export interface AgentHealth {
  name: AgentName;
  status: AgentStatus;
  responseTimeMs: number;
  avgResponseTimeMs: number;
  requestsPerMin: number;
  errorsPerMin: number;
  lastCheck: string; // ISO timestamp
  url: string;
  port: number;
}

export interface AgentStats {
  name: AgentName;
  totalCalls: number;
  successRate: number;
  avgResponseTimeMs: number;
  p95ResponseTimeMs: number;
  errorCount: number;
  lastError?: string;
  lastErrorAt?: string;
}

export type LogDirection = 'request' | 'response' | 'error' | 'info';

export interface AgentLogEntry {
  id: string;
  timestamp: string;
  agentName: AgentName;
  direction: LogDirection;
  data: unknown;
  durationMs?: number;
  status: 'success' | 'error' | 'pending';
  queryId?: string;
  truncated?: boolean;
}

export interface SystemMetrics {
  totalQueriesProcessed: number;
  avgPipelineTimeMs: number;
  cacheHitRate: number;
  errorRate: number;
  concurrentUsers: number;
  uptime: string;
}

export const AGENT_REGISTRY: AgentInfo[] = [
  { name: 'orchestrator',      displayName: 'Orchestrator',      port: 8001, color: '#6366f1', description: 'Master pipeline coordinator' },
  { name: 'intent',            displayName: 'Intent Agent',       port: 8002, color: '#3b82f6', description: 'Natural language intent recognition' },
  { name: 'schema',            displayName: 'Schema Agent',       port: 8003, color: '#8b5cf6', description: 'Database schema understanding' },
  { name: 'entity_resolution', displayName: 'Entity Resolution',  port: 8004, color: '#06b6d4', description: 'Entity and join path resolution' },
  { name: 'sql',               displayName: 'SQL Agent',          port: 8005, color: '#10b981', description: 'SQL query generation' },
  { name: 'validation',        displayName: 'Validation Agent',   port: 8006, color: '#f59e0b', description: 'SQL safety validation & signing' },
  { name: 'execution',         displayName: 'Execution Agent',    port: 8007, color: '#ef4444', description: 'Secure query execution' },
  { name: 'audit',             displayName: 'Audit Agent',        port: 8008, color: '#ec4899', description: 'Immutable audit logging' },
  { name: 'embedding',         displayName: 'Embedding Service',  port: 8009, color: '#14b8a6', description: 'Schema vectorization service' },
];
