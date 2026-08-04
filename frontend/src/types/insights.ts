// src/types/insights.ts
export interface Insight {
  insight_id: string;
  query_id: string;
  summary: string;
  key_metrics: Record<string, string | number>;
  trends: { label: string; direction: 'up' | 'down' | 'stable'; value: string }[];
  anomalies: string[];
  recommendations: string[];
  confidence: number;
  generated_at: string;
}

export interface QueryResultRow {
  [key: string]: string | number | boolean | null;
}

export interface PipelineStep {
  agent: string;
  status: 'success' | 'error';
  response: Record<string, unknown>;
}

export interface QueryResult {
  query_id: string;
  query_text: string;
  query_intent?: string;
  user_id: string;
  results: QueryResultRow[];
  row_count: number;
  execution_time_ms: number;
  source: 'database' | 'cache';
  data_freshness: 'real-time' | '6-hour' | 'daily';
  created_at: string;
  insights?: Insight;
  // Debug tracing
  request_id?: string;
  debug_url?: string;
  pipeline_steps?: PipelineStep[];
  // Clarification flow (branch resolution, ambiguity, etc.)
  requires_clarification?: boolean;
  clarification?: {
    requires_clarification: boolean;
    clarification_type: string;
    message: string;
    candidates?: string[];
    raw_value?: string;
  };
  error?: string;
}

export interface BankingQueryHistoryItem {
  id: string;
  query_text: string;
  row_count: number;
  execution_time_ms: number;
  created_at: string;
  status: 'success' | 'error';
  error?: string;
}

export interface InsightState {
  savedInsights: Insight[];
}
