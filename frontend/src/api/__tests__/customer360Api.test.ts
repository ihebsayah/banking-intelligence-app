import { describe, it, expect, vi, beforeEach } from 'vitest';

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }));

vi.mock('../client', () => ({
  apiClient: { get: mockGet },
}));

import { customer360Api } from '../customer360Api';

const overview = {
  customer: { customer_id: 'CUST_00001', name: 'Fouad Ben Salah' },
  relationship: null,
  accounts: [],
  loans: [],
  recent_transactions: [],
  analytics_alerts: [],
  workbench_links: [],
  data_quality: {
    missing_profile: false,
    missing_branch: false,
    missing_relationship_manager: false,
    stale_kyc: false,
    unresolved_workbench_reference: false,
    unavailable_sections: [],
  },
  generated_at: '2026-08-01T00:00:00Z',
};

describe('customer360Api', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getOverview requests the overview path and returns the parsed response', async () => {
    mockGet.mockResolvedValue({ data: overview });
    const result = await customer360Api.getOverview('CUST_00001');
    expect(mockGet).toHaveBeenCalledWith('/v1/customers/CUST_00001/overview');
    expect(result.customer?.name).toBe('Fouad Ben Salah');
  });

  it('getOverview rejects a malformed response (customer id mismatch)', async () => {
    mockGet.mockResolvedValue({ data: { ...overview, customer: { customer_id: 'OTHER' } } });
    await expect(customer360Api.getOverview('CUST_00001')).rejects.toMatchObject({ kind: 'malformed' });
  });

  it('getTransactions sends only limit/offset query params supported by the backend', async () => {
    mockGet.mockResolvedValue({
      data: {
        transaction_summary: { currencies: [] },
        recent_transactions: [],
        total_count: 0,
        limit: 20,
        offset: 40,
        data_quality: overview.data_quality,
        generated_at: '2026-08-01T00:00:00Z',
      },
    });
    await customer360Api.getTransactions('CUST_00001', { limit: 20, offset: 40 });
    const [url] = mockGet.mock.calls[0];
    expect(url).toBe('/v1/customers/CUST_00001/transactions?limit=20&offset=40');
  });

  it('getTransactions defaults limit to 20 and offset to 0', async () => {
    mockGet.mockResolvedValue({
      data: {
        transaction_summary: { currencies: [] },
        recent_transactions: [],
        total_count: 0,
        limit: 20,
        offset: 0,
        data_quality: overview.data_quality,
        generated_at: '2026-08-01T00:00:00Z',
      },
    });
    await customer360Api.getTransactions('CUST_00001');
    const [url] = mockGet.mock.calls[0];
    expect(url).toBe('/v1/customers/CUST_00001/transactions?limit=20&offset=0');
  });
});
