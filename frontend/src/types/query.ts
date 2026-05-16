// src/types/query.ts

export type QueryFormat = 'json' | 'csv' | 'table';
export type QueryStatus = 'idle' | 'running' | 'success' | 'error';

export type PipelineStepName =
  | 'intent'
  | 'schema'
  | 'entity_resolution'
  | 'sql'
  | 'validation'
  | 'execution';

export type StepStatus = 'pending' | 'running' | 'success' | 'error' | 'skipped';

export interface PipelineStep {
  name: PipelineStepName;
  displayName: string;
  status: StepStatus;
  durationMs?: number;
  request?: unknown;
  response?: unknown;
  error?: string;
  startedAt?: string;
  completedAt?: string;
}

export interface QueryRequest {
  query: string;
  format: QueryFormat;
  role?: string;
  userId?: string;
}

export interface QueryMetadata {
  rowsReturned: number;
  executionTimeMs: number;
  dataFreshness: string;
  source: string;
  cached: boolean;
  userRole: string;
  queryId?: string;
  totalPipelineTimeMs?: number;
  agentTimings?: Record<string, number>;
}

export interface QueryResult {
  id: string;
  query: string;
  format: QueryFormat;
  status: QueryStatus;
  submittedAt: string;
  completedAt?: string;
  results?: unknown[];
  csvData?: string;
  metadata?: QueryMetadata;
  pipelineSteps: PipelineStep[];
  error?: string;
  rawResponse?: unknown;
}

export interface PresetQuery {
  id: string;
  category: string;
  label: string;
  query: string;
  expectedAgents: PipelineStepName[];
  description?: string;
}

export const PRESET_QUERIES: PresetQuery[] = [
  // Customer Analysis
  { id: 'c1', category: 'Customer Analysis',  label: 'Top 10 by balance',        query: 'Top 10 customers by balance',               expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'c2', category: 'Customer Analysis',  label: 'Unverified KYC',            query: 'Customers with kyc_verified = false',        expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'c3', category: 'Customer Analysis',  label: 'Avg balance by segment',    query: 'Average balance by customer segment',        expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'c4', category: 'Customer Analysis',  label: 'Count by state',            query: 'Customer count by state',                   expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'c5', category: 'Customer Analysis',  label: 'Created this month',        query: 'Customers created this month',              expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  // Risk Analysis
  { id: 'r1', category: 'Risk Analysis',      label: 'High-risk NY',             query: 'High-risk customers in New York',            expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'r2', category: 'Risk Analysis',      label: 'Risk score > 0.8',         query: 'Customers with risk_score above 0.8',        expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'r3', category: 'Risk Analysis',      label: 'AML flags',                query: 'AML flags by customer',                     expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'r4', category: 'Risk Analysis',      label: 'Fraud flags this week',    query: 'Fraud detection flags this week',            expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'r5', category: 'Risk Analysis',      label: 'Multiple violations',      query: 'Customers with multiple compliance violations', expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  // Revenue
  { id: 'rv1', category: 'Revenue Analysis',  label: 'Revenue by product',       query: 'Total revenue by product',                  expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'rv2', category: 'Revenue Analysis',  label: 'Avg fees by account type', query: 'Average fees by account type',              expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'rv3', category: 'Revenue Analysis',  label: 'Top 5 products',           query: 'Top 5 products by commission',              expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  // Compliance
  { id: 'cp1', category: 'Compliance',        label: 'Violations this month',    query: 'Compliance violations this month',          expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'cp2', category: 'Compliance',        label: 'KYC status overview',      query: 'KYC status by customer',                   expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'cp3', category: 'Compliance',        label: 'Audit log entries',        query: 'Recent audit log entries',                 expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  // Operational
  { id: 'op1', category: 'Operational',       label: 'Transaction volume',       query: 'Transaction volume by branch',             expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
  { id: 'op2', category: 'Operational',       label: 'Avg transaction amount',   query: 'Average transaction amount',               expectedAgents: ['intent','schema','entity_resolution','sql','validation','execution'] },
];

export const PIPELINE_STEP_META: Record<PipelineStepName, { displayName: string; description: string; color: string }> = {
  intent:           { displayName: 'Intent Agent',      description: 'Classify query intent & category',         color: '#3b82f6' },
  schema:           { displayName: 'Schema Agent',      description: 'Map to relevant DB domains & tables',      color: '#8b5cf6' },
  entity_resolution:{ displayName: 'Entity Resolution', description: 'Resolve entities & join paths',            color: '#06b6d4' },
  sql:              { displayName: 'SQL Generation',    description: 'Generate parameterized SQL query',         color: '#10b981' },
  validation:       { displayName: 'Validation Agent',  description: 'Validate SQL safety & sign query',         color: '#f59e0b' },
  execution:        { displayName: 'Execution Agent',   description: 'Execute signed query & apply RLS',         color: '#ef4444' },
};
