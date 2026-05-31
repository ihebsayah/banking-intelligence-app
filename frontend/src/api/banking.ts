// src/api/banking.ts  — query + insights endpoints
import { apiClient } from './client';
import type { QueryResult, Insight } from '../types/insights';

export const bankingApi = {
  submitQuery: async (query: string, userRole: string): Promise<QueryResult> => {
    const res = await apiClient.post<QueryResult>('/query', { query, user_role: userRole });
    return res.data;
  },
  getHistory: async () => {
    const res = await apiClient.get('/queries/history');
    return res.data;
  },
  generateInsights: async (queryId: string, results: object[]): Promise<Insight> => {
    const res = await apiClient.post<Insight>('/insights/generate', { query_id: queryId, results });
    return res.data;
  },
  getInsights: async (queryId: string): Promise<Insight> => {
    const res = await apiClient.get<Insight>(`/insights/${queryId}`);
    return res.data;
  },
};

// Preset suggested queries for banking agents
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

// Mock query result for dev mode
export function getMockQueryResult(query: string): QueryResult {
  const mockRows = Array.from({ length: 10 }, (_, i) => ({
    rank: i + 1,
    customer_name: ['Acme Corp', 'Global Ltd', 'Metro Bank', 'Summit Inc', 'Zenith Co', 'Alpha Fund', 'NovaTech', 'Pinnacle', 'Crestline', 'BlueRidge'][i],
    customer_id: `C${String(1001 + i).padStart(4, '0')}`,
    balance: Math.round((50000000 - i * 3800000) * (0.9 + Math.random() * 0.2)),
    branch: ['New York HQ', 'Los Angeles', 'Chicago', 'Miami', 'Boston'][i % 5],
    risk_score: parseFloat((0.1 + Math.random() * 0.4).toFixed(2)),
    segment: i < 3 ? 'Premium' : i < 7 ? 'Standard' : 'Basic',
  }));

  return {
    query_id: crypto.randomUUID(),
    query_text: query,
    query_intent: 'customer_analysis',
    user_id: 'u1',
    results: mockRows,
    row_count: mockRows.length,
    execution_time_ms: Math.round(200 + Math.random() * 300),
    source: 'database',
    data_freshness: '6-hour',
    created_at: new Date().toISOString(),
    insights: {
      insight_id: crypto.randomUUID(),
      query_id: 'mock',
      summary: `Top 10 customers account for approximately 45% of total deposits. Average balance is $32.4M, up 12% year-over-year. New York HQ shows the highest concentration with 4 of the top 10 customers.`,
      key_metrics: {
        total_represented: '$324M',
        avg_balance: '$32.4M',
        yoy_growth: '+12%',
        top_branch: 'New York HQ',
      },
      trends: [
        { label: 'Balance concentration', direction: 'up', value: '+2.1% vs last quarter' },
        { label: 'Premium segment share', direction: 'up', value: '+0.8%' },
        { label: 'Average risk score', direction: 'down', value: '-0.03 (improving)' },
      ],
      anomalies: ['BlueRidge Corp shows 34% balance decline vs Q3', 'Zenith Co opened 3 new accounts this week'],
      recommendations: [
        'Review BlueRidge Corp relationship — significant balance outflow detected',
        'Schedule premium client review for top 5 customers before Q3 close',
        'Consider cross-sell opportunities for Standard segment customers near Premium threshold',
      ],
      confidence: 0.87,
      generated_at: new Date().toISOString(),
    },
  };
}
