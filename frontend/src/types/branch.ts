// src/types/branch.ts
export interface Branch {
  branch_id: string;
  name: string;
  state: string;
  city: string;
  address?: string;
  phone?: string;
  manager_id: string;
  manager_name: string;
  active_customers: number;
  total_deposits: number;
  total_revenue: number;
  staff_count: number;
  compliance_score: number;
  performance_vs_plan: number;
  customer_satisfaction: number;
  customer_growth_rate: number;
  avg_transaction_size: number;
  created_at: string;
}

export interface BranchState {
  branches: Branch[];
  selectedBranchId: string | null;
  compareMode: boolean;
  compareBranchIds: string[];
  isLoading: boolean;
  error: string | null;
}
