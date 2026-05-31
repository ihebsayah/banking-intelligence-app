// src/api/dashboard.ts
import { apiClient } from './client';
import type { KPI, ChartData } from '../types/dashboard';

export const dashboardApi = {
  getKPIs: async (): Promise<KPI[]> => {
    const res = await apiClient.get<KPI[]>('/dashboard/kpis');
    return res.data;
  },
  getChartData: async (chartId: string): Promise<ChartData> => {
    const res = await apiClient.get<ChartData>(`/dashboard/charts/${chartId}`);
    return res.data;
  },
  forceRefresh: async () => {
    const res = await apiClient.get('/dashboard/refresh');
    return res.data;
  },
};

// Mock data for development / when backend is not connected
export const MOCK_KPIS: KPI[] = [
  {
    kpi_id: 'total_deposits',
    name: 'Total Deposits',
    value: 2347650000,
    metric_type: 'currency',
    trend: 2.3,
    trend_direction: 'up',
    last_updated: new Date().toISOString(),
    data_freshness: '6-hour',
  },
  {
    kpi_id: 'monthly_revenue',
    name: 'Monthly Revenue',
    value: 12500000,
    metric_type: 'currency',
    trend: 4.1,
    trend_direction: 'up',
    last_updated: new Date().toISOString(),
    data_freshness: '6-hour',
  },
  {
    kpi_id: 'active_customers',
    name: 'Active Customers',
    value: 45230,
    metric_type: 'count',
    trend: 1.8,
    trend_direction: 'up',
    last_updated: new Date().toISOString(),
    data_freshness: 'daily',
  },
  {
    kpi_id: 'avg_risk_score',
    name: 'Portfolio Risk Score',
    value: 0.45,
    metric_type: 'ratio',
    trend: -0.05,
    trend_direction: 'down',
    last_updated: new Date().toISOString(),
    data_freshness: '6-hour',
  },
];

export const MOCK_REVENUE_CHART: ChartData = {
  chart_id: 'revenue_trend',
  chart_type: 'line',
  title: 'Revenue Trend (12 Months)',
  data: [
    { label: 'Jun', value: 10200000 },
    { label: 'Jul', value: 10800000 },
    { label: 'Aug', value: 11100000 },
    { label: 'Sep', value: 10900000 },
    { label: 'Oct', value: 11400000 },
    { label: 'Nov', value: 11800000 },
    { label: 'Dec', value: 12600000 },
    { label: 'Jan', value: 11900000 },
    { label: 'Feb', value: 12100000 },
    { label: 'Mar', value: 12300000 },
    { label: 'Apr', value: 12000000 },
    { label: 'May', value: 12500000 },
  ],
  last_updated: new Date().toISOString(),
};

export const MOCK_RISK_CHART: ChartData = {
  chart_id: 'risk_levels',
  chart_type: 'pie',
  title: 'Risk Distribution',
  data: [
    { label: 'Low Risk', value: 62 },
    { label: 'Medium Risk', value: 28 },
    { label: 'High Risk', value: 8 },
    { label: 'Critical', value: 2 },
  ],
  last_updated: new Date().toISOString(),
};

export const MOCK_CONCENTRATION_CHART: ChartData = {
  chart_id: 'concentration',
  chart_type: 'bar',
  title: 'Top 10 Customers by Balance',
  data: [
    { label: 'Acme Corp', value: 48200000 },
    { label: 'Global Ltd', value: 41500000 },
    { label: 'Metro Bank', value: 38900000 },
    { label: 'Summit Inc', value: 34200000 },
    { label: 'Zenith Co', value: 29800000 },
    { label: 'Alpha Fund', value: 27100000 },
    { label: 'NovaTech', value: 24600000 },
    { label: 'Pinnacle', value: 22300000 },
    { label: 'Crestline', value: 19800000 },
    { label: 'BlueRidge', value: 17400000 },
  ],
  last_updated: new Date().toISOString(),
};

export const MOCK_GROWTH_CHART: ChartData = {
  chart_id: 'growth_rate',
  chart_type: 'area',
  title: 'Deposit Growth Rate (%)',
  data: [
    { label: 'Jun', value: 1.2 },
    { label: 'Jul', value: 1.8 },
    { label: 'Aug', value: 1.5 },
    { label: 'Sep', value: 2.1 },
    { label: 'Oct', value: 1.9 },
    { label: 'Nov', value: 2.4 },
    { label: 'Dec', value: 3.1 },
    { label: 'Jan', value: 2.2 },
    { label: 'Feb', value: 2.7 },
    { label: 'Mar', value: 2.9 },
    { label: 'Apr', value: 2.5 },
    { label: 'May', value: 3.2 },
  ],
  last_updated: new Date().toISOString(),
};
