// src/types/customer360.ts
// Wire shapes mirror the API gateway Customer 360 contract exactly
// (services/api_gateway/customer360/models.py). Monetary values arrive as
// exact strings (Decimal -> str); masked values arrive as "***" / partial
// tokens; sections the caller lacks permission for are omitted (null / []).

export interface CustomerIdentity {
  customer_id: string;
  name?: string | null;
  customer_type?: string | null;
  segment?: string | null;
  status?: string | null;
  onboarding_date?: string | null;
  email?: string | null;
  phone?: string | null;
  nationality?: string | null;
  date_of_birth?: string | null;
  employment_status?: string | null;
  employer_name?: string | null;
  // Sensitive — masked (analyst) or suppressed (admin) unless customer:read_pii
  national_id?: string | null;
  passport_number?: string | null;
  tax_id?: string | null;
  annual_income?: string | null;
  net_worth_band?: string | null;
  pep?: boolean | null;
}

export interface RelationshipManager {
  employee_id?: string | null;
  name?: string | null;
  title?: string | null;
  portfolio_type?: string | null;
}

export interface Relationship {
  primary_branch?: string | null;
  region?: string | null;
  relationship_managers: RelationshipManager[];
  relationship_duration_days?: number | null;
  products_held: number;
}

export interface AccountSummary {
  account_id: string;
  account_type?: string | null;
  status?: string | null;
  balance?: string | null;
  available_balance?: string | null;
  currency?: string | null;
  branch?: string | null;
  opened_at?: string | null;
}

export interface LoanSummary {
  loan_id: string;
  loan_type?: string | null;
  product?: string | null;
  principal?: string | null;
  outstanding_balance?: string | null;
  currency?: string | null;
  interest_rate?: string | null;
  maturity_date?: string | null;
  status?: string | null;
  days_past_due?: number | null;
}

export interface FinancialSummary {
  account_count: number;
  active_account_count: number;
  total_balance_by_currency: Record<string, string>;
  available_balance_by_currency: Record<string, string>;
  loan_count: number;
  total_outstanding_loans_by_currency: Record<string, string>;
  maximum_days_past_due?: number | null;
  recent_transaction_count: number;
  recent_transaction_volume_by_currency: Record<string, string>;
}

export interface TransactionSummary {
  d30_inbound_count: number;
  d30_inbound_amount: Record<string, string>;
  d30_outbound_count: number;
  d30_outbound_amount: Record<string, string>;
  d30_total_count: number;
  d30_total_amount: Record<string, string>;
  d90_total_count: number;
  d90_total_amount: Record<string, string>;
  latest_transaction_date?: string | null;
  top_transaction_types: { transaction_type?: string; cnt?: number }[];
  currencies: string[];
}

export interface TransactionRow {
  transaction_id: string;
  account_id?: string | null;
  amount?: string | null;
  currency?: string | null;
  type?: string | null;
  status?: string | null;
  description?: string | null;
  transaction_date?: string | null;
}

export interface KycCaseSummary {
  // Internal case id suppressed unless the caller holds customer:read_pii
  kyc_case_id?: string | null;
  case_type?: string | null;
  status?: string | null;
  risk_level?: string | null;
  opened_at?: string | null;
}

export interface ScreeningSummary {
  status?: string | null;
  risk_level?: string | null;
  match_score?: string | null;
  list_name?: string | null;
  matched_name?: string | null;
  checked_at?: string | null;
}

export interface AmlAlertSummary {
  alert_id: string;
  alert_type?: string | null;
  label?: string | null;
  severity?: string | null;
  status?: string | null;
  score?: string | null;
  triggered_at?: string | null;
}

export interface KycAml {
  kyc_verified?: boolean | null;
  latest_kyc_case?: KycCaseSummary | null;
  kyc_status?: string | null;
  next_review_date?: string | null;
  pep_screening?: ScreeningSummary | null;
  sanctions_screening?: ScreeningSummary | null;
  aml_alert_counts_by_status: Record<string, number>;
  aml_alert_counts_by_severity: Record<string, number>;
  sar_count: number;
}

export interface RiskFlagSummary {
  flag_id: string;
  flag_type?: string | null;
  severity?: string | null;
  description?: string | null;
  created_at?: string | null;
}

export interface RiskSection {
  risk_score?: number | null;
  active_flags: RiskFlagSummary[];
  highest_active_severity?: string | null;
  risk_factors: string[];
  unresolved_flag_count: number;
}

export interface AdminCustomerMetadata {
  account_count: number;
  active_account_count: number;
  product_count: number;
  loan_count: number;
  risk_score?: number | null;
  risk_classification?: string | null;
  active_flag_count: number;
  highest_active_severity?: string | null;
  kyc_status?: string | null;
}

export type WorkbenchEntityType =
  | 'alert'
  | 'investigation'
  | 'case'
  | 'information_request'
  | 'approval';

export interface WorkbenchLink {
  entity_type: WorkbenchEntityType;
  entity_id: string;
  status?: string | null;
  assigned_to?: string | null;
  updated_at?: string | null;
  scope_id?: string | null;
  source: string;
}

export interface DataQuality {
  missing_profile: boolean;
  missing_branch: boolean;
  missing_relationship_manager: boolean;
  stale_kyc: boolean;
  unresolved_workbench_reference: boolean;
  unavailable_sections: string[];
}

export interface Customer360Overview {
  customer?: CustomerIdentity | null;
  relationship?: Relationship | null;
  financial_summary?: FinancialSummary | null;
  accounts: AccountSummary[];
  loans: LoanSummary[];
  transaction_summary?: TransactionSummary | null;
  recent_transactions: TransactionRow[];
  kyc_aml?: KycAml | null;
  risk?: RiskSection | null;
  analytics_alerts: AmlAlertSummary[];
  workbench_links: WorkbenchLink[];
  admin_metadata?: AdminCustomerMetadata | null;
  data_quality: DataQuality;
  generated_at: string;
}

export interface CustomerTransactionsResponse {
  transaction_summary: TransactionSummary;
  recent_transactions: TransactionRow[];
  total_count: number;
  limit: number;
  offset: number;
  data_quality: DataQuality;
  generated_at: string;
}
