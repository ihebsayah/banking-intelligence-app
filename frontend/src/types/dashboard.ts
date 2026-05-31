// src/types/dashboard.ts
export interface KPI {
  kpi_id: string;
  name: string;
  value: number | string;
  metric_type: 'currency' | 'percentage' | 'count' | 'ratio';
  trend: number;
  trend_direction: 'up' | 'down' | 'stable';
  last_updated: string;
  data_freshness: 'real-time' | '6-hour' | 'daily';
}

export interface ChartDataPoint {
  label: string;
  value: number;
  value2?: number;
  value3?: number;
  [key: string]: string | number | undefined;
}

export interface ChartData {
  chart_id: string;
  chart_type: 'line' | 'bar' | 'pie' | 'area';
  title: string;
  data: ChartDataPoint[];
  last_updated: string;
}

export interface DashboardState {
  kpis: KPI[];
  charts: Record<string, ChartData>;
  isLoading: boolean;
  error: string | null;
  lastRefreshed: string | null;
}
