// src/api/branches.ts
import { apiClient } from './client';
import type { Branch } from '../types/branch';

export const branchesApi = {
  getAll: async (): Promise<Branch[]> => {
    const res = await apiClient.get<Branch[]>('/branches');
    return res.data;
  },
  getById: async (id: string): Promise<Branch> => {
    const res = await apiClient.get<Branch>(`/branches/${id}`);
    return res.data;
  },
};

export const MOCK_BRANCHES: Branch[] = [
  { branch_id: 'br_nyc', name: 'New York HQ', state: 'NY', city: 'New York', address: '100 Wall Street, New York, NY 10005', phone: '+1 212-555-0100', manager_id: 'm1', manager_name: 'Sarah Mitchell', active_customers: 8943, total_deposits: 680000000, total_revenue: 45600000, staff_count: 127, compliance_score: 98.5, performance_vs_plan: 104.2, customer_satisfaction: 4.6, customer_growth_rate: 3.1, avg_transaction_size: 28400, created_at: '2018-03-01' },
  { branch_id: 'br_la', name: 'Los Angeles', state: 'CA', city: 'Los Angeles', address: '350 S Grand Ave, Los Angeles, CA 90071', phone: '+1 213-555-0200', manager_id: 'm2', manager_name: 'James Chen', active_customers: 6821, total_deposits: 520000000, total_revenue: 34800000, staff_count: 98, compliance_score: 97.2, performance_vs_plan: 98.7, customer_satisfaction: 4.4, customer_growth_rate: 2.8, avg_transaction_size: 24100, created_at: '2019-06-15' },
  { branch_id: 'br_chi', name: 'Chicago', state: 'IL', city: 'Chicago', address: '77 W Wacker Dr, Chicago, IL 60601', phone: '+1 312-555-0300', manager_id: 'm3', manager_name: 'Maria Rodriguez', active_customers: 5430, total_deposits: 412000000, total_revenue: 27500000, staff_count: 84, compliance_score: 99.1, performance_vs_plan: 101.5, customer_satisfaction: 4.7, customer_growth_rate: 2.4, avg_transaction_size: 21300, created_at: '2019-11-01' },
  { branch_id: 'br_mia', name: 'Miami', state: 'FL', city: 'Miami', address: '200 S Biscayne Blvd, Miami, FL 33131', phone: '+1 305-555-0400', manager_id: 'm4', manager_name: 'David Williams', active_customers: 4210, total_deposits: 318000000, total_revenue: 21200000, staff_count: 67, compliance_score: 96.8, performance_vs_plan: 95.3, customer_satisfaction: 4.2, customer_growth_rate: 4.2, avg_transaction_size: 19800, created_at: '2020-02-14' },
  { branch_id: 'br_bos', name: 'Boston', state: 'MA', city: 'Boston', address: '101 Federal St, Boston, MA 02110', phone: '+1 617-555-0500', manager_id: 'm5', manager_name: 'Emily Thompson', active_customers: 3890, total_deposits: 294000000, total_revenue: 19600000, staff_count: 58, compliance_score: 99.4, performance_vs_plan: 107.8, customer_satisfaction: 4.8, customer_growth_rate: 1.9, avg_transaction_size: 22600, created_at: '2020-08-22' },
  { branch_id: 'br_den', name: 'Denver', state: 'CO', city: 'Denver', address: '1670 Broadway, Denver, CO 80202', phone: '+1 720-555-0600', manager_id: 'm6', manager_name: 'Michael O\'Brien', active_customers: 2940, total_deposits: 221000000, total_revenue: 14800000, staff_count: 45, compliance_score: 97.9, performance_vs_plan: 102.1, customer_satisfaction: 4.5, customer_growth_rate: 5.1, avg_transaction_size: 18400, created_at: '2021-03-10' },
];
