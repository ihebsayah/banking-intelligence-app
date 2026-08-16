import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import type { Customer360Overview } from '../../../types/customer360';

const { mockGetOverview } = vi.hoisted(() => ({
  mockGetOverview: vi.fn(),
}));

vi.mock('../../../api/customer360Api', () => ({
  customer360Api: { getOverview: mockGetOverview, getTransactions: vi.fn() },
  parseCustomer360Error: (err: unknown) => ({
    kind: (err as { response?: { status?: number } })?.response?.status === 403 ? 'forbidden'
      : (err as { response?: { status?: number } })?.response?.status === 404 ? 'not_found'
      : (err as { response?: { status?: number } })?.response?.status === 503 ? 'unavailable'
      : 'unknown',
    status: (err as { response?: { status?: number } })?.response?.status,
    message: 'mock',
  }),
}));

import { CustomerContextPanel } from '../CustomerContextPanel';

function renderPanel(customerId = 'CUST_00001') {
  return render(
    <MemoryRouter>
      <CustomerContextPanel customerId={customerId} />
    </MemoryRouter>
  );
}

function axiosError(status: number) {
  return Object.assign(new Error('request failed'), {
    response: { status, data: { detail: { message: 'test error' } } },
  });
}

const dq = {
  missing_profile: false,
  missing_branch: false,
  missing_relationship_manager: false,
  stale_kyc: false,
  unresolved_workbench_reference: false,
  unavailable_sections: [] as string[],
};

const analystOverview: Customer360Overview = {
  customer: {
    customer_id: 'CUST_00001', name: 'Fouad Ben Salah', customer_type: 'corporate', segment: 'CORP-A', status: 'active',
    onboarding_date: '2019-04-12T00:00:00Z', email: 'f***@***.com', phone: '****0123', nationality: 'TN',
    date_of_birth: '****-**-**', employment_status: 'employed', employer_name: 'Acme SARL',
    national_id: '***', passport_number: '***', tax_id: '***', annual_income: '***', net_worth_band: '***', pep: false,
  },
  relationship: {
    primary_branch: 'Tunis Main Branch', region: 'Tunis',
    relationship_managers: [{ employee_id: 'EMP-1', name: 'Aymen Trabelsi', title: 'Senior RM', portfolio_type: 'corporate' }],
    relationship_duration_days: 2600, products_held: 2,
  },
  financial_summary: {
    account_count: 2,
    active_account_count: 2,
    total_balance_by_currency: { TND: '150000.00', USD: '5000.00' },
    available_balance_by_currency: { TND: '149000.00', USD: '5000.00' },
    loan_count: 1,
    total_outstanding_loans_by_currency: { TND: '80000.00' },
    maximum_days_past_due: 12,
    recent_transaction_count: 34,
    recent_transaction_volume_by_currency: { TND: '320000.00' },
  },
  accounts: [],
  loans: [],
  transaction_summary: {
    d30_inbound_count: 20,
    d30_inbound_amount: { TND: '180000.00' },
    d30_outbound_count: 14,
    d30_outbound_amount: { TND: '140000.00' },
    d30_total_count: 34,
    d30_total_amount: { TND: '320000.00' },
    d90_total_count: 100,
    d90_total_amount: { TND: '900000.00' },
    latest_transaction_date: '2026-07-01T00:00:00Z',
    top_transaction_types: [],
    currencies: ['TND'],
  },
  recent_transactions: [],
  kyc_aml: {
    kyc_verified: true,
    kyc_status: 'verified',
    pep_screening: { status: 'clear', risk_level: null, match_score: null, list_name: null, matched_name: null, checked_at: '2025-01-10T00:00:00Z' },
    sanctions_screening: null,
    aml_alert_counts_by_status: { open: 2 },
    aml_alert_counts_by_severity: { high: 1 },
    sar_count: 0,
  },
  risk: {
    risk_score: 0.55,
    active_flags: [{ flag_id: 'FLAG-1', flag_type: 'transaction_anomaly', severity: 'medium', description: 'Unusual large deposit', created_at: '2026-06-01T00:00:00Z' }],
    highest_active_severity: 'medium',
    risk_factors: ['transaction_anomaly'],
    unresolved_flag_count: 1,
  },
  analytics_alerts: [],
  workbench_links: [],
  admin_metadata: null,
  data_quality: { ...dq },
  generated_at: '2026-08-01T00:00:00Z',
};

const adminOverview: Customer360Overview = {
  ...analystOverview,
  customer: {
    ...analystOverview.customer!,
    email: null, phone: null, nationality: null, date_of_birth: null,
    employment_status: null, employer_name: null, national_id: null, passport_number: null,
    tax_id: null, annual_income: null, net_worth_band: null, pep: null,
  },
  financial_summary: null,
  transaction_summary: null,
  kyc_aml: null,
  risk: null,
  admin_metadata: {
    account_count: 2, active_account_count: 2, product_count: 2, loan_count: 1,
    risk_score: 0.55, risk_classification: 'medium', active_flag_count: 1,
    highest_active_severity: 'medium', kyc_status: 'verified',
  },
};

describe('CustomerContextPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders granted identity, assessment and financial context', async () => {
    mockGetOverview.mockResolvedValue(analystOverview);
    renderPanel();

    expect(await screen.findByText('Fouad Ben Salah')).toBeInTheDocument();
    expect(screen.getByText('#CUST_00001')).toBeInTheDocument();
    expect(screen.getByText('Risk: medium')).toBeInTheDocument();
    expect(screen.getByText('KYC: verified')).toBeInTheDocument();
    expect(screen.getByText('PEP: clear')).toBeInTheDocument();
    expect(screen.getByText('1 active flag')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument(); // Accounts KPI
    expect(screen.getByText('150,000.00 TND · 5,000.00 USD')).toBeInTheDocument();
    expect(screen.getByText('34')).toBeInTheDocument(); // 30d Txns KPI
    expect(screen.getByText(/Tunis Main Branch · Tunis/)).toBeInTheDocument();
    expect(screen.getByText(/RM: Aymen Trabelsi/)).toBeInTheDocument();
    expect(mockGetOverview).toHaveBeenCalledWith('CUST_00001');
  });

  it('keeps masked tokens masked and marks identity as Masked', async () => {
    mockGetOverview.mockResolvedValue(analystOverview);
    renderPanel();
    expect(await screen.findByText('Masked')).toBeInTheDocument();
  });

  it('renders the metadata-only (admin) context without fabricated detail', async () => {
    mockGetOverview.mockResolvedValue(adminOverview);
    renderPanel();
    expect(await screen.findByText('Fouad Ben Salah')).toBeInTheDocument();
    expect(screen.getByText('Risk')).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();
    expect(screen.queryByText(/150,000\.00 TND/)).not.toBeInTheDocument();
    expect(screen.queryByText(/PEP:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/active flag/)).not.toBeInTheDocument();
  });

  it('links to the full Customer 360 page', async () => {
    mockGetOverview.mockResolvedValue(analystOverview);
    renderPanel('CUST_ABC/99');
    const link = await screen.findByRole('link', { name: /Open Customer 360/i });
    expect(link).toHaveAttribute('href', '/workbench/customers/CUST_ABC%2F99');
  });

  it('shows the forbidden state and never renders customer data', async () => {
    mockGetOverview.mockRejectedValue(axiosError(403));
    renderPanel();
    expect(await screen.findByText(/outside your permission scope/i)).toBeInTheDocument();
    expect(screen.queryByText('Fouad Ben Salah')).not.toBeInTheDocument();
  });

  it('shows the not-found state without fabricated content', async () => {
    mockGetOverview.mockRejectedValue(axiosError(404));
    renderPanel();
    expect(await screen.findByText(/cannot be resolved/i)).toBeInTheDocument();
    expect(screen.queryByText('Fouad Ben Salah')).not.toBeInTheDocument();
  });

  it('shows the unavailable state and allows retry', async () => {
    mockGetOverview.mockRejectedValueOnce(axiosError(503))
      .mockResolvedValueOnce(analystOverview);
    renderPanel();
    expect(await screen.findByText(/temporarily unavailable/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Retry/i }));
    expect(await screen.findByText('Fouad Ben Salah')).toBeInTheDocument();
  });
});
