// src/types/api.ts
import { QueryResultRow, PipelineStep, Insight } from './insights';

export type UserRole = 'analyst' | 'manager' | 'compliance' | 'admin';

export interface QueryApiResponse {
  request_id: string;
  results: QueryResultRow[];
  metadata: {
    rows_returned?: number;
    execution_time_ms?: number;
    source?: string;
    data_freshness?: string;
  };
  insights?: {
    summary: string;
    key_metrics: Record<string, any>;
    trends: Array<{
      metric?: string;
      label?: string;
      direction: 'up' | 'down' | 'stable';
      value: any;
    }>;
    anomalies: string[];
    recommendations: string[];
    confidence: number;
  } | null;
  pipeline_steps?: PipelineStep[];
}

export interface KpiMetric {
  kpi_id: string;
  name: string;
  value: number;
  metric_type: 'currency' | 'percent' | 'count' | 'ratio';
  trend: number;
  trend_direction: 'up' | 'down' | 'stable';
  last_updated: string;
  data_freshness: string;
}

export interface RiskSummary {
  risk_level_distribution: Record<string, number>;
  total_high_risk_customers: number;
  critical_alerts_count: number;
  average_risk_score: number;
  last_updated: string;
}

export interface ComplianceReportResponse {
  gdpr_status: string;
  pci_status: string;
  aml_alerts_count: number;
  kyc_status: string;
  active_violations_count: number;
  last_updated: string;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  user_id: string;
  user_role: string;
  action: string;
  status: 'success' | 'failure';
  details: string;
  ip_address: string;
}

export interface AdminUser {
  user_id: string;
  email: string;
  name?: string;
  role: UserRole;
  bank_id: string;
  created_at: string;
  last_login: string;
  status: 'active' | 'suspended';
}
