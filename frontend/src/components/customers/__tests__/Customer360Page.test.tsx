import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useParams } from 'react-router-dom';
import React from 'react';
import type { Customer360Overview, CustomerTransactionsResponse } from '../../../types/customer360';

const { mockGetOverview, mockGetTransactions, mockUseAuth, mockAlertGet } = vi.hoisted(() => ({
  mockGetOverview: vi.fn(),
  mockGetTransactions: vi.fn(),
  mockUseAuth: vi.fn(),
  mockAlertGet: vi.fn(),
}));

vi.mock('../../../api/customer360Api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/customer360Api')>();
  return {
    ...actual,
    customer360Api: { getOverview: mockGetOverview, getTransactions: mockGetTransactions },
  };
});

vi.mock('../../../api/alertsApi', () => ({
  alertsApi: { get: mockAlertGet },
}));

vi.mock('../../../auth/AuthProvider', () => ({
  useAuth: () => mockUseAuth(),
}));

import { Customer360Page } from '../Customer360Page';
import { AlertDetailPage } from '../../alerts/AlertDetailPage';

// ── fixtures ────────────────────────────────────────────────────────────────

const dq = {
  missing_profile: false,
  missing_branch: false,
  missing_relationship_manager: false,
  stale_kyc: false,
  unresolved_workbench_reference: false,
  unavailable_sections: [] as string[],
};

const relationship = {
  primary_branch: 'Tunis Main Branch',
  region: 'Tunis',
  relationship_managers: [
    { employee_id: 'EMP-1', name: 'Aymen Trabelsi', title: 'Senior RM', portfolio_type: 'corporate' },
  ],
  relationship_duration_days: 2600,
  products_held: 2,
};

const accounts = [
  { account_id: 'ACC-0001', account_type: 'current', status: 'active', balance: '100000.00', available_balance: '99000.00', currency: 'TND', branch: 'Tunis Main Branch', opened_at: '2019-04-12T00:00:00Z' },
  { account_id: 'ACC-0002', account_type: 'savings', status: 'active', balance: '5000.00', available_balance: '5000.00', currency: 'USD', branch: 'Sfax Branch', opened_at: '2020-01-05T00:00:00Z' },
];

const loans = [
  { loan_id: 'LOAN-001', loan_type: 'mortgage', product: 'Home Loan', principal: '120000.00', outstanding_balance: '80000.00', currency: 'TND', interest_rate: '6.5', maturity_date: '2035-06-01T00:00:00Z', status: 'active', days_past_due: 12 },
];

const financialSummary = {
  account_count: 2,
  active_account_count: 2,
  total_balance_by_currency: { TND: '150000.00', USD: '5000.00' },
  available_balance_by_currency: { TND: '149000.00', USD: '5000.00' },
  loan_count: 1,
  total_outstanding_loans_by_currency: { TND: '80000.00' },
  maximum_days_past_due: 12,
  recent_transaction_count: 34,
  recent_transaction_volume_by_currency: { TND: '320000.00' },
};

const txSummary = {
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
};

const txRow = (i: number) => ({
  transaction_id: `TX-${i}`,
  account_id: 'ACC-0001',
  amount: '150.00',
  currency: 'TND',
  type: 'deposit',
  status: 'completed',
  description: 'Wire transfer',
  transaction_date: '2026-07-01T00:00:00Z',
});

const kycAnalyst = {
  kyc_verified: true,
  latest_kyc_case: { kyc_case_id: null, case_type: 'onboarding', status: 'verified', risk_level: 'medium', opened_at: '2025-01-10T00:00:00Z' },
  kyc_status: 'verified',
  next_review_date: '2026-12-01T00:00:00Z',
  pep_screening: { status: 'clear', risk_level: null, match_score: null, list_name: null, matched_name: null, checked_at: '2025-01-10T00:00:00Z' },
  sanctions_screening: null,
  aml_alert_counts_by_status: { open: 2 },
  aml_alert_counts_by_severity: { high: 1 },
  sar_count: 0,
};

const kycCompliance = {
  ...kycAnalyst,
  latest_kyc_case: { kyc_case_id: 'KC-0001', case_type: 'onboarding', status: 'verified', risk_level: 'medium', opened_at: '2025-01-10T00:00:00Z' },
  pep_screening: { status: 'clear', risk_level: null, match_score: '0.02', list_name: 'PEP list', matched_name: null, checked_at: '2025-01-10T00:00:00Z' },
};

const riskSection = {
  risk_score: 0.55,
  active_flags: [{ flag_id: 'FLAG-1', flag_type: 'transaction_anomaly', severity: 'medium', description: 'Unusual large deposit', created_at: '2026-06-01T00:00:00Z' }],
  highest_active_severity: 'medium',
  risk_factors: ['transaction_anomaly'],
  unresolved_flag_count: 1,
};

const analyticsAlerts = [
  { alert_id: 'AML-1', alert_type: 'large_cash', label: 'Large cash deposit', severity: 'high', status: 'open', score: '0.82', triggered_at: '2026-06-20T00:00:00Z' },
];

const adminMetadata = {
  account_count: 2,
  active_account_count: 2,
  product_count: 2,
  loan_count: 1,
  risk_score: 0.55,
  risk_classification: 'medium',
  active_flag_count: 1,
  highest_active_severity: 'medium',
  kyc_status: 'verified',
};

const analystOverview: Customer360Overview = {
  customer: {
    customer_id: 'CUST_00001', name: 'Fouad Ben Salah', customer_type: 'corporate', segment: 'CORP-A', status: 'active',
    onboarding_date: '2019-04-12T00:00:00Z', email: 'f***@***.com', phone: '****0123', nationality: 'TN',
    date_of_birth: '****-**-**', employment_status: 'employed', employer_name: 'Acme SARL',
    national_id: '***', passport_number: '***', tax_id: '***', annual_income: '***', net_worth_band: '***', pep: false,
  },
  relationship,
  financial_summary: financialSummary,
  accounts,
  loans,
  transaction_summary: txSummary,
  recent_transactions: [txRow(1)],
  kyc_aml: kycAnalyst,
  risk: riskSection,
  analytics_alerts: analyticsAlerts,
  workbench_links: [],
  admin_metadata: null,
  data_quality: { ...dq },
  generated_at: '2026-08-01T00:00:00Z',
};

const complianceOverview: Customer360Overview = {
  ...analystOverview,
  customer: {
    customer_id: 'CUST_00001', name: 'Fouad Ben Salah', customer_type: 'corporate', segment: 'CORP-A', status: 'active',
    onboarding_date: '2019-04-12T00:00:00Z', email: 'fouad.bensalah@example.com', phone: '+21698123456', nationality: 'TN',
    date_of_birth: '1985-06-15', employment_status: 'employed', employer_name: 'Acme SARL',
    national_id: '09987654', passport_number: 'P54321', tax_id: 'TAX-88', annual_income: '250000.00', net_worth_band: '1-5M', pep: false,
  },
  kyc_aml: kycCompliance,
  workbench_links: [
    { entity_type: 'alert', entity_id: 'AL-0001', status: 'assigned', assigned_to: 'comp_1', updated_at: '2026-07-15T00:00:00Z', scope_id: 'hq_main', source: 'workbench' },
    { entity_type: 'investigation', entity_id: 'INV-0001', status: 'active', assigned_to: 'analyst_001', updated_at: '2026-07-14T00:00:00Z', scope_id: 'hq_main', source: 'workbench' },
    { entity_type: 'case', entity_id: 'CASE-9', status: 'under_review', assigned_to: 'comp_1', updated_at: '2026-07-13T00:00:00Z', scope_id: 'hq_main', source: 'workbench' },
    { entity_type: 'information_request', entity_id: 'IR-0001', status: 'open', assigned_to: 'analyst_001', updated_at: '2026-07-12T00:00:00Z', scope_id: null, source: 'workbench' },
  ],
};

const adminOverview: Customer360Overview = {
  customer: {
    customer_id: 'CUST_00001', name: 'Fouad Ben Salah', customer_type: 'corporate', segment: 'CORP-A', status: 'active',
    onboarding_date: '2019-04-12T00:00:00Z', email: null, phone: null, nationality: null, date_of_birth: null,
    employment_status: null, employer_name: null, national_id: null, passport_number: null, tax_id: null,
    annual_income: null, net_worth_band: null, pep: null,
  },
  relationship,
  financial_summary: null,
  accounts: [],
  loans: [],
  transaction_summary: null,
  recent_transactions: [],
  kyc_aml: null,
  risk: null,
  analytics_alerts: [],
  workbench_links: [
    { entity_type: 'case', entity_id: 'CASE-9', status: 'open', assigned_to: 'comp_1', updated_at: '2026-07-01T00:00:00Z', scope_id: 'hq_main', source: 'workbench' },
  ],
  admin_metadata: adminMetadata,
  data_quality: { ...dq },
  generated_at: '2026-08-01T00:00:00Z',
};

const ANALYST_PERMS = ['customer:read_basic', 'customer:read_financial', 'customer:read_transactions', 'customer:read_kyc', 'customer:read_risk'];
const COMPLIANCE_PERMS = [...ANALYST_PERMS, 'customer:read_compliance_history', 'customer:read_pii'];
const ADMIN_PERMS = ['customer:read_basic', 'customer:read_operational_metadata'];

// ── helpers ────────────────────────────────────────────────────────────────

function renderPage(route = '/workbench/customers/CUST_00001') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/workbench/customers/:customerId" element={<Customer360Page />} />
      </Routes>
    </MemoryRouter>
  );
}

function axiosError(status: number) {
  return Object.assign(new Error('request failed'), {
    response: { status, data: { detail: { message: 'test error' } } },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseAuth.mockReturnValue({
    applicationUser: { user_id: 'analyst_001', role: 'analyst' },
    hasPermission: (p: string) => ANALYST_PERMS.includes(p),
    hasRole: () => false,
  });
});

// ── tests ──────────────────────────────────────────────────────────────────

describe('Customer360Page', () => {
  it('renders Analyst overview with masked PII and no restricted-by-policy leakage', async () => {
    mockGetOverview.mockResolvedValue(analystOverview);
    renderPage();

    expect(await screen.findByText('Fouad Ben Salah')).toBeInTheDocument();
    expect(screen.getByText('f***@***.com')).toBeInTheDocument();
    expect(screen.getAllByText('Masked').length).toBeGreaterThan(0);
    expect(screen.getByText('150,000.00 TND')).toBeInTheDocument();
    expect(screen.queryByText(/Restricted by policy/)).not.toBeInTheDocument();
  });

  it('renders Compliance view with permitted KYC/AML detail and workbench records', async () => {
    mockUseAuth.mockReturnValue({
      applicationUser: { user_id: 'comp_1', role: 'compliance' },
      hasPermission: (p: string) => COMPLIANCE_PERMS.includes(p),
      hasRole: () => false,
    });
    mockGetOverview.mockResolvedValue(complianceOverview);
    renderPage();

    await screen.findByText('Fouad Ben Salah');
    expect(screen.getByText('fouad.bensalah@example.com')).toBeInTheDocument();
    expect(screen.queryByText('Masked')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Risk & KYC' }));
    expect(await screen.findByText('KC-0001')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Workbench' }));
    const alertLink = await screen.findByRole('link', { name: 'AL-0001' });
    expect(alertLink).toHaveAttribute('href', '/workbench/alerts/AL-0001');
    expect(screen.getByRole('link', { name: 'INV-0001' })).toHaveAttribute('href', '/workbench/investigations/INV-0001');
    expect(screen.getByRole('link', { name: 'CASE-9' })).toHaveAttribute('href', '/workbench/cases/CASE-9');

    // No detail route exists for information requests → plain non-link row.
    expect(screen.getByText('IR-0001')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'IR-0001' })).not.toBeInTheDocument();
  });

  it('hides the Workbench tab for an Analyst who is not granted workbench records', async () => {
    mockGetOverview.mockResolvedValue(analystOverview);
    renderPage();

    await screen.findByText('Fouad Ben Salah');
    expect(screen.queryByRole('tab', { name: 'Workbench' })).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Alerts & Cases' })).toBeInTheDocument();
  });

  it('shows the real error state instead of falling back to fabricated data when the API fails', async () => {
    mockGetOverview.mockRejectedValue(axiosError(503));
    renderPage();

    expect(await screen.findByText('Service Unavailable')).toBeInTheDocument();
    expect(screen.queryByText('Fouad Ben Salah')).not.toBeInTheDocument();
    expect(screen.queryByText('150,000.00 TND')).not.toBeInTheDocument();
  });

  it('navigates from a linked Workbench case into its detail route', async () => {
    mockUseAuth.mockReturnValue({
      applicationUser: { user_id: 'comp_1', role: 'compliance' },
      hasPermission: (p: string) => COMPLIANCE_PERMS.includes(p),
      hasRole: () => false,
    });
    mockGetOverview.mockResolvedValue(complianceOverview);

    function CaseStub() {
      const { caseId } = useParams<{ caseId: string }>();
      return <div>case:{caseId}</div>;
    }

    render(
      <MemoryRouter initialEntries={['/workbench/customers/CUST_00001']}>
        <Routes>
          <Route path="/workbench/customers/:customerId" element={<Customer360Page />} />
          <Route path="/workbench/cases/:caseId" element={<CaseStub />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('tab', { name: 'Workbench' }));
    const caseLink = await screen.findByRole('link', { name: 'CASE-9' });
    fireEvent.click(caseLink);
    expect(await screen.findByText('case:CASE-9')).toBeInTheDocument();
  });

  it('renders Admin metadata-only view with no balances, transactions or KYC content', async () => {
    mockUseAuth.mockReturnValue({
      applicationUser: { user_id: 'admin_1', role: 'admin' },
      hasPermission: (p: string) => ADMIN_PERMS.includes(p),
      hasRole: () => false,
    });
    mockGetOverview.mockResolvedValue(adminOverview);
    renderPage();

    await screen.findByText('Fouad Ben Salah');
    expect(screen.getByText(/2 accounts \(2 active\)/)).toBeInTheDocument();
    expect(screen.getByText(/Balances and loan amounts are not available/)).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Transactions' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Accounts & Loans' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Risk & KYC' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Alerts & Cases' })).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Workbench' })).toBeInTheDocument();
    expect(screen.queryByText('150,000.00 TND')).not.toBeInTheDocument();
    expect(mockGetTransactions).not.toHaveBeenCalled();
  });

  it('loads and paginates the Transactions tab for an Analyst', async () => {
    mockGetOverview.mockResolvedValue(analystOverview);
    const makePage = (offset: number): CustomerTransactionsResponse => ({
      transaction_summary: txSummary,
      recent_transactions: Array.from({ length: 20 }, (_, i) => txRow(offset + i + 1)),
      total_count: 45,
      limit: 20,
      offset,
      data_quality: { ...dq },
      generated_at: '2026-08-01T00:00:00Z',
    });
    mockGetTransactions.mockImplementation((_id: string, params: { offset?: number }) =>
      Promise.resolve(makePage(params.offset ?? 0)),
    );
    renderPage();

    fireEvent.click(await screen.findByRole('tab', { name: 'Transactions' }));
    expect(await screen.findByText('Showing 1–20 of 45')).toBeInTheDocument();
    expect(screen.getAllByRole('row').length).toBeGreaterThan(5);

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Showing 21–40 of 45')).toBeInTheDocument();
    expect(mockGetTransactions).toHaveBeenLastCalledWith('CUST_00001', { limit: 20, offset: 20 });
  });

  it('renders a leakage-safe not-found state for 404', async () => {
    mockGetOverview.mockRejectedValue(axiosError(404));
    renderPage();

    expect(await screen.findByText('Customer Not Found or Unavailable')).toBeInTheDocument();
    expect(screen.queryByText('Fouad Ben Salah')).not.toBeInTheDocument();
  });

  it('keeps valid sections visible when part of the response is unavailable', async () => {
    mockGetOverview.mockResolvedValue({
      ...analystOverview,
      data_quality: { ...dq, unresolved_workbench_reference: true, unavailable_sections: ['workbench_links'] },
    });
    renderPage();

    await screen.findByText('Fouad Ben Salah');
    expect(screen.getByText('Some operational records could not be linked to this customer.')).toBeInTheDocument();
    expect(screen.getByText('150,000.00 TND')).toBeInTheDocument();
  });

  it('navigates from a workbench Alert related to a customer into Customer 360', async () => {
    const alertFixture = {
      alert_id: 'AL-0001',
      alert_type: 'transaction_anomaly',
      severity: 'high',
      title: 'Unusual deposits',
      description: 'Unusual deposit pattern',
      scope_id: 'hq_main',
      related_entity_type: 'customer',
      related_entity_id: 'CUST_00001',
      status: 'assigned',
      assigned_to: 'analyst_001',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      version: 1,
    };
    mockAlertGet.mockResolvedValue(alertFixture);

    mockUseAuth.mockReturnValue({
      applicationUser: { user_id: 'analyst_001', role: 'analyst' },
      hasPermission: () => false,
      hasRole: () => false,
    });
    mockGetOverview.mockResolvedValue(analystOverview);

    function CustomerStub() {
      const { customerId } = useParams<{ customerId: string }>();
      return <div>customer:{customerId}</div>;
    }

    render(
      <MemoryRouter initialEntries={['/workbench/alerts/AL-0001']}>
        <Routes>
          <Route path="/workbench/alerts/:alertId" element={<AlertDetailPage />} />
          <Route path="/workbench/customers/:customerId" element={<CustomerStub />} />
        </Routes>
      </MemoryRouter>,
    );

    const links = await screen.findAllByRole('link', { name: /Open Customer 360/i });
    expect(links.length).toBe(2); // Related-row link + customer-context panel link
    for (const link of links) expect(link).toHaveAttribute('href', '/workbench/customers/CUST_00001');
    fireEvent.click(links[0]);
    expect(await screen.findByText('customer:CUST_00001')).toBeInTheDocument();
  });

  it('renders the profile header and executive summary strip with banking KPIs', async () => {
    mockGetOverview.mockResolvedValue(analystOverview);
    renderPage();

    await screen.findByText('Fouad Ben Salah');
    expect(screen.getByText('MEDIUM')).toBeInTheDocument();
    expect(screen.getByText('KYC VERIFIED')).toBeInTheDocument();
    expect(screen.getByText('Risk')).toBeInTheDocument();
    expect(screen.getByText('2 active')).toBeInTheDocument();
    expect(screen.getByText('Deposits · TND')).toBeInTheDocument();
    expect(screen.getByText('1 past due')).toBeInTheDocument();
    expect(screen.getByText('Loans out · TND')).toBeInTheDocument();
    expect(screen.getByText('Active flags')).toBeInTheDocument();
    expect(screen.getByText('AML alerts')).toBeInTheDocument();
  });

  it('groups accounts by product family with per-group subtotals and highlights non-active statuses', async () => {
    mockGetOverview.mockResolvedValue({
      ...analystOverview,
      accounts: [
        { account_id: 'ACC-0001', account_type: 'current', status: 'active', balance: '100000.00', available_balance: '99000.00', currency: 'TND', branch: 'Tunis', opened_at: '2019-04-12T00:00:00Z' },
        { account_id: 'ACC-0003', account_type: 'checking', status: 'frozen', balance: '5000.00', available_balance: '0.00', currency: 'TND', branch: 'Tunis', opened_at: '2022-01-01T00:00:00Z' },
        { account_id: 'ACC-0002', account_type: 'savings', status: 'active', balance: '5000.00', available_balance: '5000.00', currency: 'USD', branch: 'Sfax', opened_at: '2020-01-05T00:00:00Z' },
      ],
    });
    renderPage();

    fireEvent.click(await screen.findByRole('tab', { name: 'Accounts & Loans' }));
    expect(await screen.findByText('Checking · 2 accounts')).toBeInTheDocument();
    expect(screen.getByText('Savings · 1 account')).toBeInTheDocument();
    expect(screen.getAllByText('105,000.00 TND').length).toBe(1);
    expect(screen.getByText('frozen')).toBeInTheDocument();
  });

  it('classifies loan operational risk (past due vs current)', async () => {
    mockGetOverview.mockResolvedValue({
      ...analystOverview,
      loans: [
        { loan_id: 'LOAN-001', loan_type: 'mortgage', product: 'Home Loan', principal: '120000.00', outstanding_balance: '80000.00', currency: 'TND', interest_rate: '6.5', maturity_date: '2035-06-01T00:00:00Z', status: 'active', days_past_due: 12 },
        { loan_id: 'LOAN-002', loan_type: 'consumer', product: 'Auto Loan', principal: '20000.00', outstanding_balance: '5000.00', currency: 'TND', interest_rate: '8.0', maturity_date: '2028-01-01T00:00:00Z', status: 'actif', days_past_due: 0 },
      ],
    });
    renderPage();

    fireEvent.click(await screen.findByRole('tab', { name: 'Accounts & Loans' }));
    expect(await screen.findByText('Past due')).toBeInTheDocument();
    expect(screen.getByText('Current')).toBeInTheDocument();
  });

  it('shows a professional empty state for a customer with no accounts or loans', async () => {
    mockGetOverview.mockResolvedValue({ ...analystOverview, accounts: [], loans: [] });
    renderPage();

    fireEvent.click(await screen.findByRole('tab', { name: 'Accounts & Loans' }));
    expect(await screen.findByText('No accounts or loans on record')).toBeInTheDocument();
    expect(screen.getByText(/no accounts or loans within your permitted scope/)).toBeInTheDocument();
  });

  it('splits data quality into attention and informational boxes', async () => {
    mockGetOverview.mockResolvedValue({
      ...analystOverview,
      data_quality: { ...dq, missing_relationship_manager: true, unresolved_workbench_reference: true },
    });
    renderPage();

    await screen.findByText('Fouad Ben Salah');
    expect(screen.getByText('Needs attention')).toBeInTheDocument();
    expect(screen.getByText('Some operational records could not be linked to this customer.')).toBeInTheDocument();
    expect(screen.getByText('Profile notes')).toBeInTheDocument();
    expect(screen.getByText('No relationship manager is currently assigned.')).toBeInTheDocument();
  });

  it('caches transactions across tab switches instead of refetching', async () => {
    mockGetOverview.mockResolvedValue(analystOverview);
    mockGetTransactions.mockResolvedValue({
      transaction_summary: txSummary,
      recent_transactions: Array.from({ length: 20 }, (_, i) => txRow(i + 1)),
      total_count: 45,
      limit: 20,
      offset: 0,
      data_quality: { ...dq },
      generated_at: '2026-08-01T00:00:00Z',
    });
    renderPage();

    fireEvent.click(await screen.findByRole('tab', { name: 'Transactions' }));
    expect(await screen.findByText('Showing 1–20 of 45')).toBeInTheDocument();
    expect(mockGetTransactions).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('tab', { name: 'Overview' }));
    fireEvent.click(screen.getByRole('tab', { name: 'Transactions' }));
    expect(await screen.findByText('Showing 1–20 of 45')).toBeInTheDocument();
    expect(mockGetTransactions).toHaveBeenCalledTimes(1);
  });

  it('marks transaction direction (IN/OUT) from the signed amount', async () => {
    mockGetOverview.mockResolvedValue(analystOverview);
    const rows = Array.from({ length: 20 }, (_, i) => txRow(i + 1));
    rows[0] = { ...rows[0], amount: '-322.00' };
    mockGetTransactions.mockResolvedValue({
      transaction_summary: txSummary,
      recent_transactions: rows,
      total_count: 20,
      limit: 20,
      offset: 0,
      data_quality: { ...dq },
      generated_at: '2026-08-01T00:00:00Z',
    });
    renderPage();

    fireEvent.click(await screen.findByRole('tab', { name: 'Transactions' }));
    expect(await screen.findByText('OUT')).toBeInTheDocument();
    expect(screen.getAllByText('IN').length).toBeGreaterThan(0);
  });

  it('groups workbench records by entity type', async () => {
    mockUseAuth.mockReturnValue({
      applicationUser: { user_id: 'comp_1', role: 'compliance' },
      hasPermission: (p: string) => COMPLIANCE_PERMS.includes(p),
      hasRole: () => false,
    });
    mockGetOverview.mockResolvedValue(complianceOverview);
    renderPage();

    fireEvent.click(await screen.findByRole('tab', { name: 'Workbench' }));
    expect(await screen.findByText('Alerts (1)')).toBeInTheDocument();
    expect(screen.getByText('Investigations (1)')).toBeInTheDocument();
    expect(screen.getByText('Compliance cases (1)')).toBeInTheDocument();
    expect(screen.getByText('Information requests (1)')).toBeInTheDocument();
  });
});
