// src/api/customer360Api.ts
import { apiClient } from './client';
import type {
  Customer360Overview,
  CustomerTransactionsResponse,
} from '../types/customer360';

export interface CustomerTransactionsParams {
  limit?: number;
  offset?: number;
}

export type Customer360ErrorKind =
  | 'forbidden'
  | 'not_found'
  | 'unavailable'
  | 'network'
  | 'malformed'
  | 'unknown';

export interface Customer360ApiError {
  kind: Customer360ErrorKind;
  status?: number;
  message: string;
}

export function parseCustomer360Error(err: unknown): Customer360ApiError {
  const status = (err as { response?: { status?: number } })?.response?.status;
  const detail = (err as { response?: { data?: { detail?: { message?: string } } } })
    ?.response?.data?.detail;
  const msg = detail?.message || (err as { message?: string })?.message || '';

  if (status === 403) {
    return { kind: 'forbidden', status, message: 'You do not have permission to access this customer profile.' };
  }
  if (status === 404) {
    return { kind: 'not_found', status, message: 'Customer not found or unavailable.' };
  }
  if (status === 503) {
    return { kind: 'unavailable', status, message: 'The customer data source is temporarily unavailable.' };
  }
  if (status == null) {
    return { kind: 'network', message: msg || 'Unable to reach the service. Check your connection and try again.' };
  }
  return { kind: 'unknown', status, message: msg || `The service returned an unexpected response (${status}).` };
}

function isOverviewShape(data: unknown, customerId: string): boolean {
  if (!data || typeof data !== 'object') return false;
  const d = data as { customer?: unknown; data_quality?: unknown };
  return Boolean(
    d.customer &&
    typeof d.customer === 'object' &&
    (d.customer as { customer_id?: unknown }).customer_id === customerId &&
    d.data_quality &&
    typeof d.data_quality === 'object',
  );
}

export interface CustomerSearchResultItem {
  customer_id: string;
  name: string;
  segment?: string | null;
}

export interface CustomerSearchResponse {
  items: CustomerSearchResultItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface CustomerSearchParams {
  q: string;
  limit?: number;
  offset?: number;
}

export const customer360Api = {
  getOverview: async (customerId: string): Promise<Customer360Overview> => {
    const res = await apiClient.get<Customer360Overview>(
      `/v1/customers/${encodeURIComponent(customerId)}/overview`,
    );
    if (!isOverviewShape(res.data, customerId)) {
      throw Object.assign(new Error('Malformed overview response'), { kind: 'malformed' });
    }
    return res.data;
  },

  getTransactions: async (
    customerId: string,
    params: CustomerTransactionsParams = {},
  ): Promise<CustomerTransactionsResponse> => {
    const qs = new URLSearchParams();
    qs.append('limit', String(params.limit ?? 20));
    qs.append('offset', String(params.offset ?? 0));
    const res = await apiClient.get<CustomerTransactionsResponse>(
      `/v1/customers/${encodeURIComponent(customerId)}/transactions?${qs.toString()}`,
    );
    const rows = res.data?.recent_transactions;
    if (!Array.isArray(rows) || typeof res.data?.total_count !== 'number') {
      throw Object.assign(new Error('Malformed transactions response'), { kind: 'malformed' });
    }
    return res.data;
  },

  searchCustomers: async (
    params: CustomerSearchParams,
  ): Promise<CustomerSearchResponse> => {
    const qs = new URLSearchParams();
    qs.append('q', params.q);
    qs.append('limit', String(params.limit ?? 20));
    qs.append('offset', String(params.offset ?? 0));
    const res = await apiClient.get<CustomerSearchResponse>(
      `/v1/customers?${qs.toString()}`,
    );
    if (!res.data || !Array.isArray(res.data.items)) {
      throw Object.assign(new Error('Malformed search response'), { kind: 'malformed' });
    }
    return res.data;
  },
};
