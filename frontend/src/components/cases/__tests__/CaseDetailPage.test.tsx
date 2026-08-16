import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const mockAuth = vi.hoisted(() => {
  const state = {
    userId: 'compliance_001',
    role: 'compliance',
    permissions: [
      'case:read_assigned', 'case:transition', 'case:decision', 'case:assign',
      'investigation:review', 'info_request:create', 'info_request:accept', 'info_request:return',
      'approval:request', 'comment:view_internal_content',
    ] as string[],
  };
  return {
    state,
    useAuth: () => ({
      applicationUser: { user_id: state.userId, role: state.role },
      hasPermission: (p: string) => state.permissions.includes(p),
      hasRole: (r: string) => r === state.role,
    }),
  };
});

vi.mock('../../../auth/AuthProvider', () => ({ useAuth: mockAuth.useAuth }));

const mocks = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockTransition: vi.fn(),
  mockListDecisions: vi.fn(),
  mockRecordDecision: vi.fn(),
  mockListIR: vi.fn(),
  mockCreateIR: vi.fn(),
  mockAcceptIR: vi.fn(),
  mockReturnIR: vi.fn(),
  mockAssign: vi.fn(),
  mockListComments: vi.fn(),
  mockListTimeline: vi.fn(),
  mockInvGet: vi.fn(),
  mockInvTransition: vi.fn(),
  mockApprovalCreate: vi.fn(),
  mockApprovalGet: vi.fn(),
  mockAlertGet: vi.fn(),
  mockGetOverview: vi.fn(),
}));

vi.mock('../../../api/casesApi', () => ({
  casesApi: {
    get: mocks.mockGet,
    transition: mocks.mockTransition,
    listDecisions: mocks.mockListDecisions,
    recordDecision: mocks.mockRecordDecision,
    listInformationRequests: mocks.mockListIR,
    createInformationRequest: mocks.mockCreateIR,
    acceptInformationRequest: mocks.mockAcceptIR,
    returnInformationRequest: mocks.mockReturnIR,
    assign: mocks.mockAssign,
    listComments: mocks.mockListComments,
    createComment: vi.fn(),
    listTimeline: mocks.mockListTimeline,
  },
}));

vi.mock('../../../api/investigationsApi', () => ({
  investigationsApi: {
    get: mocks.mockInvGet,
    transition: mocks.mockInvTransition,
    update: vi.fn(),
    cancel: vi.fn(),
    listComments: vi.fn(),
    listTimeline: vi.fn(),
  },
}));

vi.mock('../../../api/approvalsApi', () => ({
  approvalsApi: {
    create: mocks.mockApprovalCreate,
    get: mocks.mockApprovalGet,
  },
}));

vi.mock('../../../api/alertsApi', () => ({
  alertsApi: { get: mocks.mockAlertGet },
}));

vi.mock('../../../api/customer360Api', () => ({
  customer360Api: { getOverview: mocks.mockGetOverview, getTransactions: vi.fn() },
  parseCustomer360Error: (err: unknown) => ({
    kind: (err as { response?: { status?: number } })?.response?.status === 403 ? 'forbidden'
      : (err as { response?: { status?: number } })?.response?.status === 404 ? 'not_found'
      : (err as { response?: { status?: number } })?.response?.status === 503 ? 'unavailable'
      : 'unknown',
    status: (err as { response?: { status?: number } })?.response?.status,
    message: 'mock',
  }),
}));

import { CaseDetailPage } from '../CaseDetailPage';

function makeCase(overrides: Record<string, unknown> = {}) {
  return {
    case_id: 'case_1', title: 'Round-trip transfer', description: 'Large round-trip transaction',
    alert_id: 'al_12345678', investigation_id: 'inv_1', scope_id: 'hq_main',
    status: 'under_review', priority: 'high', risk_level: 'high',
    regulatory_frameworks: ['AML', 'KYC'], assigned_to: 'compliance_001', created_by: 'analyst_001',
    target_date: '2026-02-01', resolution: null, resolved_at: null, resolved_by: null,
    closed_at: null, closed_by: null, version: 4, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

const investigationSubmitted = {
  investigation_id: 'inv_1', title: 'Round-trip transfer', scope_id: 'hq_main',
  status: 'submitted', priority: 'high', assigned_to: 'analyst_001', created_by: 'analyst_001',
  findings_text: 'Evidence found', findings_refs: [], conclusion: 'Confirmed',
  version: 5, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

const approval = (status: string) => ({
  approval_request_id: 'ap_1', action_type: 'decision_report_to_authority',
  entity_type: 'compliance_case', entity_id: 'case_1', requested_by: 'compliance_001',
  rationale: 'serious breach', required_approvals: 1, approval_count: status === 'approved' ? 1 : 0,
  status, expires_at: '2026-03-01T00:00:00Z', version: 1,
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
});

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/workbench/cases/case_1']}>
      <Routes>
        <Route path="/workbench/cases/:caseId" element={<CaseDetailPage />} />
        <Route path="/workbench/cases" element={<div>queue-page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('CaseDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth.state.userId = 'compliance_001';
    mockAuth.state.role = 'compliance';
    mockAuth.state.permissions = [
      'case:read_assigned', 'case:transition', 'case:decision', 'case:assign',
      'investigation:review', 'info_request:create', 'info_request:accept', 'info_request:return',
      'approval:request', 'comment:view_internal_content',
    ];
    mocks.mockGet.mockResolvedValue(makeCase());
    mocks.mockTransition.mockResolvedValue({ success: true, case: makeCase({ status: 'under_review', version: 5 }), version: 5 });
    mocks.mockListDecisions.mockResolvedValue({ data: [] });
    mocks.mockListIR.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] });
    mocks.mockCreateIR.mockResolvedValue({ success: true, information_request: { ir_id: 'ir_1' }, version: 1 });
    mocks.mockListComments.mockResolvedValue({ total: 1, page: 1, page_size: 50, items: [{ comment_id: 'c1', entity_type: 'compliance_case', entity_id: 'case_1', content: 'review note', author_id: 'compliance_001', is_internal: false, is_redacted: false, version: 1, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }] });
    mocks.mockListTimeline.mockResolvedValue({ total: 1, page: 1, page_size: 50, items: [{ timeline_id: 't1', entity_type: 'compliance_case', entity_id: 'case_1', event_type: 'case.status_changed', actor_id: 'compliance_001', old_value: { status: 'assigned' }, new_value: { status: 'under_review' }, occurred_at: '2026-01-01T00:00:00Z' }] });
    mocks.mockInvGet.mockResolvedValue(investigationSubmitted);
    mocks.mockInvTransition.mockResolvedValue({ success: true, investigation: { ...investigationSubmitted, status: 'completed' }, version: 6 });
    mocks.mockApprovalCreate.mockResolvedValue({ success: true, approval_request: approval('pending'), version: 1 });
    mocks.mockApprovalGet.mockResolvedValue(approval('pending'));
    mocks.mockAlertGet.mockResolvedValue({
      alert_id: 'al_12345678', alert_type: 'transaction_anomaly', severity: 'high', title: 'Suspicious transfer',
      description: 'Large round-trip transaction', source_rule_type: 'ml_anomaly', source_rule_id: 'r1',
      related_entity_type: 'customer', related_entity_id: 'CUST_00001', scope_id: 'hq_main',
      status: 'assigned', assigned_to: 'analyst_001', dismissed_reason: null, dismissed_at: null,
      dismissed_by: null, resolved_at: null, resolved_by: null,
      created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', version: 3,
    });
    mocks.mockGetOverview.mockResolvedValue({
      customer: { customer_id: 'CUST_00001', name: 'Fouad Ben Salah', customer_type: 'corporate', segment: 'CORP-A', status: 'active', onboarding_date: '2019-04-12T00:00:00Z', email: null, phone: null, nationality: null, date_of_birth: null, employment_status: null, employer_name: null, national_id: null, passport_number: null, tax_id: null, annual_income: null, net_worth_band: null, pep: false },
      relationship: null, financial_summary: null, accounts: [], loans: [], transaction_summary: null, recent_transactions: [],
      kyc_aml: null, risk: null, analytics_alerts: [], workbench_links: [], admin_metadata: null,
      data_quality: { missing_profile: false, missing_branch: false, missing_relationship_manager: false, stale_kyc: false, unresolved_workbench_reference: false, unavailable_sections: [] },
      generated_at: '2026-08-01T00:00:00Z',
    });
  });

  it('renders fields, badges, version and assignee', async () => {
    renderDetail();
    expect(await screen.findByText('Round-trip transfer')).toBeInTheDocument();
    expect(screen.getByText('High risk')).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getByText('v4')).toBeInTheDocument();
    expect(screen.getByText('assigned to compliance_001')).toBeInTheDocument();
    expect(screen.getByText('AML, KYC')).toBeInTheDocument();
    expect(mocks.mockGet).toHaveBeenCalledWith('case_1');
  });

  it('shows the not-found state for an unknown case', async () => {
    mocks.mockGet.mockRejectedValue({ response: { status: 404, data: { message: 'Case not found.' } } });
    renderDetail();
    expect(await screen.findByText('Case not found.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Back to queue/i }));
    expect(await screen.findByText('queue-page')).toBeInTheDocument();
  });

  it('compliance begins review on an assigned case', async () => {
    mocks.mockGet.mockResolvedValue(makeCase({ status: 'assigned' }));
    mocks.mockTransition.mockResolvedValue({ success: true, case: makeCase({ status: 'under_review', version: 5 }), version: 5 });
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Begin Review/i }));
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Begin Review/i }));
    await waitFor(() => expect(mocks.mockTransition).toHaveBeenCalledWith('case_1', { target_status: 'under_review', expected_version: 4 }));
  });

  it('marks a case decision pending from under_review', async () => {
    mocks.mockTransition.mockResolvedValue({ success: true, case: makeCase({ status: 'decision_pending', version: 5 }), version: 5 });
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Mark Decision Pending/i }));
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Mark Decision Pending/i }));
    await waitFor(() => expect(mocks.mockTransition).toHaveBeenCalledWith('case_1', { target_status: 'decision_pending', expected_version: 4 }));
  });

  it('resolves a case and requires a resolution', async () => {
    mocks.mockGet.mockResolvedValue(makeCase({ status: 'awaiting_compliance_action' }));
    mocks.mockTransition.mockResolvedValue({ success: true, case: makeCase({ status: 'resolved', resolution: 'resolved text', version: 5 }), version: 5 });
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Resolve Case/i }));
    const dialog = screen.getByRole('dialog');
    const submit = within(dialog).getByRole('button', { name: /Resolve Case/i });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Resolution \*/i), { target: { value: 'resolved text' } });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    await waitFor(() => expect(mocks.mockTransition).toHaveBeenCalledWith('case_1', { target_status: 'resolved', resolution: 'resolved text', expected_version: 4 }));
  });

  it('record decision button opens the Decisions tab and records a no_action decision', async () => {
    mocks.mockGet.mockResolvedValue(makeCase({ status: 'decision_pending' }));
    mocks.mockListDecisions.mockResolvedValue({ data: [{ decision_id: 'd1', case_id: 'case_1', decision_type: 'no_action', rationale: 'clean', decided_by: 'compliance_001', decided_at: '2026-01-01T00:00:00Z', is_final: true, version: 1, created_at: '2026-01-01T00:00:00Z' }] });
    mocks.mockRecordDecision.mockResolvedValue({ success: true, case: makeCase({ status: 'resolved', version: 5 }), decision: {}, version: 5 });

    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Record Decision/i }));
    expect(await screen.findByText('Record Decision')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Rationale/i), { target: { value: 'clean' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit Decision/i }));
    await waitFor(() => expect(mocks.mockRecordDecision).toHaveBeenCalledWith('case_1', { decision_type: 'no_action', rationale: 'clean', expected_version: 4 }));
  });

  it('report_to_authority requires an approved approval before submit', async () => {
    mocks.mockGet.mockResolvedValue(makeCase({ status: 'decision_pending' }));
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Record Decision/i }));
    fireEvent.change(await screen.findByLabelText(/Rationale/i), { target: { value: 'serious breach' } });
    fireEvent.click(screen.getByLabelText(/report to authority/i));
    expect(await screen.findByText('Four-eyes approval required')).toBeInTheDocument();

    // submit is disabled while no approval approved
    const submit = screen.getByRole('button', { name: /Submit Decision/i });
    expect(submit).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /Request Approval/i }));
    await waitFor(() => expect(mocks.mockApprovalCreate).toHaveBeenCalledWith(expect.objectContaining({
      action_type: 'decision_report_to_authority', entity_type: 'compliance_case', entity_id: 'case_1',
    })));

    // approval granted via refresh poll
    mocks.mockApprovalGet.mockResolvedValue(approval('approved'));
    fireEvent.click(screen.getByRole('button', { name: /Refresh status/i }));
    expect(await screen.findByText(/Approval approved/i)).toBeInTheDocument();
    expect(submit).toBeEnabled();
  });

  it('IR create modal posts a new information request', async () => {
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Request Information/i }));
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(/Assigned analyst/i), { target: { value: 'analyst_002' } });
    fireEvent.change(within(dialog).getByLabelText(/Question/i), { target: { value: 'Please provide details' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /Create Request/i }));
    await waitFor(() => expect(mocks.mockCreateIR).toHaveBeenCalledWith('case_1', {
      assigned_to: 'analyst_002', question: 'Please provide details', expected_case_version: 4,
    }));
    expect(mocks.mockGet.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('compliance reviewer approves a submitted investigation in the Investigation tab', async () => {
    renderDetail();
    fireEvent.click(await screen.findByRole('tab', { name: 'Investigation' }));
    expect(await screen.findByText('Evidence found')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Approve Investigation/i }));
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Approve/i }));
    await waitFor(() => expect(mocks.mockInvTransition).toHaveBeenCalledWith('inv_1', { target_status: 'completed', expected_version: 5 }));
  });

  it('awaits information with a guidance note and no transition buttons', async () => {
    mocks.mockGet.mockResolvedValue(makeCase({ status: 'awaiting_information' }));
    renderDetail();
    expect((await screen.findAllByText(/awaiting analyst information/i)).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /Begin Review/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Mark Decision Pending/i })).not.toBeInTheDocument();
  });

  it('shows a conflict banner and refetches on 409', async () => {
    mocks.mockGet.mockResolvedValue(makeCase({ status: 'assigned' }));
    mocks.mockTransition.mockRejectedValue({ response: { status: 409, data: { message: 'Case was updated' } } });
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Begin Review/i }));
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Begin Review/i }));
    expect(await screen.findByText(/Case was updated by someone else/i)).toBeInTheDocument();
    await waitFor(() => expect(mocks.mockGet.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('loads comments and timeline for the case', async () => {
    renderDetail();
    fireEvent.click(await screen.findByRole('tab', { name: 'Comments' }));
    expect(await screen.findByText('review note')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: 'Timeline' }));
    expect(await screen.findByText('status changed')).toBeInTheDocument();
    expect(await screen.findByText('status assigned → under_review')).toBeInTheDocument();
  });

  it('admin can assign an unassigned case', async () => {
    mockAuth.state.role = 'admin';
    mockAuth.state.permissions = ['case:read_assigned', 'case:assign'];
    mocks.mockGet.mockResolvedValue(makeCase({ assigned_to: null }));
    mocks.mockAssign.mockResolvedValue({ success: true, case: makeCase({ assigned_to: 'compliance_007', version: 5 }), version: 5 });
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Assign Case/i }));
    fireEvent.change(screen.getByLabelText(/Assign to/i), { target: { value: 'compliance_007' } });
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Assign/i }));
    await waitFor(() => expect(mocks.mockAssign).toHaveBeenCalledWith('case_1', { assigned_to: 'compliance_007', expected_version: 4 }));
  });

  it('shows customer context when the case links an alert to a customer', async () => {
    renderDetail();
    expect(await screen.findByTestId('customer-context-panel')).toBeInTheDocument();
    expect(await screen.findByText('Fouad Ben Salah')).toBeInTheDocument();
    expect(mocks.mockAlertGet).toHaveBeenCalledWith('al_12345678');
    expect(mocks.mockGetOverview).toHaveBeenCalledWith('CUST_00001');
  });

  it('resolves customer context via the investigation when the case has no direct alert', async () => {
    mocks.mockGet.mockResolvedValue(makeCase({ alert_id: null }));
    mocks.mockInvGet.mockResolvedValue({ ...investigationSubmitted, alert_id: 'al_55555555' });
    mocks.mockAlertGet.mockResolvedValue({ alert_id: 'al_55555555', related_entity_type: 'customer', related_entity_id: 'CUST_00099', scope_id: 'hq_main', status: 'assigned', assigned_to: 'analyst_001', severity: 'high', alert_type: 'transaction_anomaly', title: 'Suspicious transfer', description: '', source_rule_type: 'ml_anomaly', source_rule_id: 'r1', dismissed_reason: null, dismissed_at: null, dismissed_by: null, resolved_at: null, resolved_by: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', version: 3 });
    renderDetail();
    expect(await screen.findByTestId('customer-context-panel')).toBeInTheDocument();
    expect(mocks.mockInvGet).toHaveBeenCalledWith('inv_1');
    expect(mocks.mockAlertGet).toHaveBeenCalledWith('al_55555555');
    expect(mocks.mockGetOverview).toHaveBeenCalledWith('CUST_00099');
  });

  it('shows no customer context for a non-customer linked alert', async () => {
    mocks.mockAlertGet.mockResolvedValue({ alert_id: 'al_12345678', related_entity_type: 'account', related_entity_id: 'ACC-1', scope_id: 'hq_main', status: 'assigned', assigned_to: 'analyst_001', severity: 'high', alert_type: 'transaction_anomaly', title: 'Suspicious transfer', description: '', source_rule_type: 'ml_anomaly', source_rule_id: 'r1', dismissed_reason: null, dismissed_at: null, dismissed_by: null, resolved_at: null, resolved_by: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', version: 3 });
    renderDetail();
    await screen.findByText('Round-trip transfer');
    await waitFor(() => expect(mocks.mockAlertGet).toHaveBeenCalled());
    expect(screen.queryByTestId('customer-context-panel')).not.toBeInTheDocument();
    expect(mocks.mockGetOverview).not.toHaveBeenCalled();
  });

  it('renders CustomerContextPanel when linked alert carries resolved_customer_id', async () => {
    mocks.mockAlertGet.mockResolvedValue({
      alert_id: 'al_12345678',
      related_entity_type: 'account',
      related_entity_id: 'ACC_00412',
      resolved_customer_id: 'CUST_00141',
      scope_id: 'hq_main',
      status: 'assigned',
      assigned_to: 'analyst_001',
      severity: 'high',
      alert_type: 'transaction_anomaly',
      title: 'Suspicious transfer',
      description: '',
      source_rule_type: 'ml_anomaly',
      source_rule_id: 'r1',
      dismissed_reason: null, dismissed_at: null, dismissed_by: null, resolved_at: null, resolved_by: null,
      created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', version: 3,
    });
    renderDetail();
    expect(await screen.findByTestId('customer-context-panel')).toBeInTheDocument();
    expect(mocks.mockGetOverview).toHaveBeenCalledWith('CUST_00141');
  });

  it('shows no customer context when the case has no linked alert or investigation', async () => {
    mocks.mockGet.mockResolvedValue(makeCase({ alert_id: null, investigation_id: null }));
    renderDetail();
    await screen.findByText('Round-trip transfer');
    expect(screen.queryByTestId('customer-context-panel')).not.toBeInTheDocument();
    expect(mocks.mockInvGet).not.toHaveBeenCalled();
    expect(mocks.mockAlertGet).not.toHaveBeenCalled();
  });
});
