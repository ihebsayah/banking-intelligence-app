// src/types/api.ts
import { QueryResultRow, PipelineStep } from './insights';

export type UserRole = 'analyst' | 'manager' | 'compliance' | 'admin';

export interface QueryApiResponse {
  status: string;
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
  message?: string;
  error?: string;
  debug_url?: string;
}

export interface KpiMetric {
  kpi_id: string;
  name: string;
  value: number;
  metric_type: 'currency' | 'percentage' | 'count' | 'ratio';
  trend: number;
  trend_direction: 'up' | 'down' | 'stable';
  last_updated: string;
  data_freshness: string;
}

export interface KpiDefinition {
  kpi_id: string;
  name: string;
  category: string;
  description?: string;
  metric_type: string;
}

export interface DashboardOverview {
  total_customers: number;
  total_accounts: number;
  active_accounts: number;
  total_deposits: number;
  monthly_transactions: number;
  high_risk_customers: number;
  last_updated: string;
}

export interface RecentActivity {
  transaction_id: string;
  customer_id: string;
  account_id: string;
  amount: number;
  transaction_type: string;
  status: string;
  description: string;
  transaction_date: string;
}

export interface ChartDataPoint {
  label: string;
  value: number;
}

export interface ChartResponse {
  chart_id: string;
  chart_type: 'line' | 'bar' | 'pie' | 'area';
  title: string;
  data: ChartDataPoint[];
  last_updated: string;
}

export interface RiskOverview {
  total_flags: number;
  critical_flags: number;
  high_flags: number;
  medium_flags: number;
  low_flags: number;
  average_risk_score: number;
  high_risk_customer_count: number;
  kyc_incomplete_count: number;
  last_updated: string;
}

export interface RiskFlag {
  flag_id: string;
  customer_id: string;
  flag_type: string;
  severity: string;
  description: string;
  resolved: boolean;
  created_at: string;
}

export interface PaginatedRiskFlags {
  total: number;
  page: number;
  page_size: number;
  items: RiskFlag[];
}

export interface RiskSegment {
  segment: string;
  customer_count: number;
  avg_risk_score: number;
  total_balance: number;
}

export interface RiskSummary {
  risk_level_distribution: Record<string, number>;
  total_high_risk_customers: number;
  critical_alerts_count: number;
  average_risk_score: number;
  last_updated: string;
}

export interface ComplianceOverview {
  gdpr_status: string;
  pci_status: string;
  aml_alerts_count: number;
  kyc_status: string;
  active_violations_count: number;
  total_rules: number;
  enabled_rules: number;
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

export interface ComplianceRule {
  rule_id: string;
  rule_name: string;
  regulation: string;
  rule_type: string;
  condition: string;
  action: string;
  enabled: boolean;
  created_at: string;
}

export interface ComplianceViolation {
  violation_id: string;
  query_id?: string;
  user_id?: string;
  violation_type: string;
  severity: string;
  description: string;
  regulation: string;
  detected_at: string;
  status: string;
  resolution_notes?: string;
}

export interface PaginatedComplianceViolations {
  total: number;
  page: number;
  page_size: number;
  items: ComplianceViolation[];
}

export interface AuditLogRow {
  id: string;
  audit_id: string;
  timestamp: string;
  user_id: string;
  user_role: string;
  action: string;
  status: string;
  ip_address?: string;
  endpoint?: string;
  http_method?: string;
  execution_time_ms: number;
  error_message?: string;
}

export interface PaginatedAuditLogs {
  total: number;
  page: number;
  page_size: number;
  items: AuditLogRow[];
}

export interface Report {
  report_id: string;
  report_type: string;
  regulation: string;
  report_period_start?: string;
  report_period_end?: string;
  generated_at: string;
  status: string;
  submitted_to?: string;
  submitted_at?: string;
}

export interface PaginatedReports {
  total: number;
  page: number;
  page_size: number;
  items: Report[];
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

export interface AdminUserRow {
  user_id: string;
  email: string;
  name?: string;
  role: string;
  bank_id: string;
  created_at: string;
  last_login: string;
  status: string;
}

export interface RoleInfo {
  role: string;
  user_count: number;
  permissions: string[];
}

export interface PermissionInfo {
  permission: string;
  roles: string[];
  description: string;
}
