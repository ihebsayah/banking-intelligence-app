// src/api/queryApi.ts
import { apiClient } from './client';
import type { QueryResult } from '../types/insights';

export const queryApi = {
  submitQuery: async (query: string, userRole: string): Promise<QueryResult> => {
    const res = await apiClient.post<any>('/query', { query, user_role: userRole });
    const raw = res.data;

    const meta = raw.metadata ?? {};
    const insights = raw.insights ?? null;

    let normalisedInsight: any;
    if (insights) {
      normalisedInsight = {
        insight_id: raw.request_id ?? 'n/a',
        query_id: raw.request_id ?? 'n/a',
        summary: insights.summary ?? '',
        key_metrics: insights.key_metrics ?? {},
        trends: (insights.trends ?? []).map((t: any) => ({
          label: t.metric ?? t.label ?? '',
          direction: t.direction ?? 'stable',
          value: t.value != null ? String(t.value) : '',
        })),
        anomalies: insights.anomalies ?? [],
        recommendations: insights.recommendations ?? [],
        confidence: insights.confidence ?? 1.0,
        generated_at: new Date().toISOString(),
      };
    }

    return {
      query_id: raw.request_id ?? crypto.randomUUID(),
      query_text: query,
      user_id: userRole,
      results: raw.results ?? [],
      row_count: meta.rows_returned ?? (raw.results ?? []).length,
      execution_time_ms: meta.execution_time_ms ?? 0,
      source: meta.source === 'cache' ? 'cache' : 'database',
      data_freshness: 'real-time',
      created_at: new Date().toISOString(),
      insights: normalisedInsight,
      request_id: raw.request_id,
      debug_url: raw.debug_url,
      pipeline_steps: raw.pipeline_steps,
    };
  },

  getHistory: async (): Promise<any[]> => {
    const res = await apiClient.get('/queries/history');
    return res.data;
  }
};

export const SUGGESTED_QUERIES = [
  { category: 'Customer', label: 'Top 10 customers by balance', query: 'Show me the top 10 customers by total account balance' },
  { category: 'Customer', label: 'Zero activity this quarter', query: 'List customers with no transactions this quarter' },
  { category: 'Customer', label: 'New customers last 30 days', query: 'How many new customers joined in the last 30 days?' },
  { category: 'Customer', label: 'Customer segments', query: 'Show customer distribution by segment (Premium, Standard, Basic)' },
  { category: 'Risk', label: 'High-risk customers', query: 'List customers with risk score above 0.8' },
  { category: 'Risk', label: 'KYC violations', query: 'Show all KYC compliance violations this month' },
  { category: 'Risk', label: 'AML flags', query: 'List all AML flags and sanctions screening results' },
  { category: 'Risk', label: 'Delinquent accounts', query: 'Show delinquent accounts by 30, 60, and 90 days past due' },
  { category: 'Revenue', label: 'Revenue by product line', query: 'Show total revenue broken down by product line' },
  { category: 'Revenue', label: 'Fee income analysis', query: 'Analyze fee income by top products this quarter' },
  { category: 'Revenue', label: 'Monthly revenue trend', query: 'Show monthly recurring revenue trend for the past 12 months' },
  { category: 'Operations', label: 'Transaction volume by branch', query: 'Show transaction volume grouped by branch for this month' },
  { category: 'Operations', label: 'Branch vs plan', query: 'Show branch performance vs plan for all branches' },
  { category: 'Compliance', label: 'Regulatory violations', query: 'List all regulatory violations reported this month' },
  { category: 'Compliance', label: 'Large transaction monitoring', query: 'Show all transactions above $10,000 for AML monitoring' },
  { category: 'Compliance', label: 'Fraud detection alerts', query: 'List all active fraud detection alerts' },
];
