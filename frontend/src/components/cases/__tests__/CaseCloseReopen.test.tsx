// src/components/cases/__tests__/CaseCloseReopen.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const mockAuthState = vi.hoisted(() => ({
  userId: 'compliance_001',
  role: 'compliance',
  permissions: [
    'case:read_assigned', 'case:transition', 'case:decision', 'case:close',
    'case:reopen', 'case:assign', 'approval:request', 'approval:approve',
  ] as string[],
}));

vi.mock('../../../auth/AuthProvider', () => ({
  useAuth: () => ({
    applicationUser: { user_id: mockAuthState.userId, role: mockAuthState.role },
    hasPermission: (p: string) => mockAuthState.permissions.includes(p),
    hasRole: (r: string) => r === mockAuthState.role,
  }),
}));

const mocks = vi.hoisted(() => ({
  mockGetCase: vi.fn(),
  mockCloseCase: vi.fn(),
  mockReopenCase: vi.fn(),
  mockCreateApproval: vi.fn(),
  mockListApprovals: vi.fn(),
  mockGetApproval: vi.fn(),
  mockVoteApproval: vi.fn(),
  mockGetInv: vi.fn(),
  mockListAtt: vi.fn(),
}));

vi.mock('../../../api/casesApi', () => ({
  casesApi: {
    get: mocks.mockGetCase,
    close: mocks.mockCloseCase,
    reopen: mocks.mockReopenCase,
    transition: vi.fn(),
    recordDecision: vi.fn(),
    listDecisions: vi.fn().mockResolvedValue({ total: 0, items: [] }),
    listInformationRequests: vi.fn().mockResolvedValue({ total: 0, items: [] }),
    listComments: vi.fn().mockResolvedValue({ total: 0, items: [] }),
    listTimeline: vi.fn().mockResolvedValue({ total: 0, items: [] }),
  },
}));

vi.mock('../../../api/approvalsApi', () => ({
  approvalsApi: {
    create: mocks.mockCreateApproval,
    list: mocks.mockListApprovals,
    get: mocks.mockGetApproval,
    vote: mocks.mockVoteApproval,
  },
}));

vi.mock('../../../api/investigationsApi', () => ({
  investigationsApi: {
    get: mocks.mockGetInv,
  },
}));

vi.mock('../../../api/attachmentsApi', () => ({
  attachmentsApi: {
    list: mocks.mockListAtt,
  },
}));

import { CaseDetailPage } from '../CaseDetailPage';
import type { Case } from '../../../types/cases';

const resolvedMediumCase: Case = {
  case_id: 'case_med_1',
  title: 'Resolved Medium Risk Case',
  scope_id: 'hq_main',
  status: 'resolved',
  priority: 'medium',
  risk_level: 'medium',
  assigned_to: 'compliance_001',
  created_by: 'analyst_001',
  resolution: 'Verified no money laundering.',
  target_date: '2026-12-01',
  version: 2,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const resolvedHighCase: Case = {
  ...resolvedMediumCase,
  case_id: 'case_high_1',
  title: 'Resolved High Risk Case',
  priority: 'high',
  risk_level: 'high',
};

const closedCase: Case = {
  ...resolvedMediumCase,
  case_id: 'case_closed_1',
  title: 'Closed Compliance Case',
  status: 'closed',
  closed_at: '2026-08-10T12:00:00Z',
  closed_by: 'compliance_001',
  version: 3,
};

function renderDetail(caseId = 'case_med_1') {
  return render(
    <MemoryRouter initialEntries={[`/workbench/cases/${caseId}`]}>
      <Routes>
        <Route path="/workbench/cases/:caseId" element={<CaseDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('Phase 3B.4 — Case Close & Reopen UI Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthState.userId = 'compliance_001';
    mockAuthState.role = 'compliance';
    mockAuthState.permissions = [
      'case:read_assigned', 'case:transition', 'case:decision', 'case:close',
      'case:reopen', 'case:assign', 'approval:request', 'approval:approve',
    ];
    mocks.mockListApprovals.mockResolvedValue({ total: 0, items: [] });
  });

  it('renders Close Case button for resolved cases assigned to Compliance Officer', async () => {
    mocks.mockGetCase.mockResolvedValue(resolvedMediumCase);
    renderDetail('case_med_1');

    expect(await screen.findByRole('button', { name: /Close Case/i })).toBeInTheDocument();
  });

  it('closes Medium risk case directly when resolution is provided', async () => {
    mocks.mockGetCase.mockResolvedValue(resolvedMediumCase);
    mocks.mockCloseCase.mockResolvedValue({
      success: true,
      case: { ...resolvedMediumCase, status: 'closed', closed_at: '2026-08-16T12:00:00Z', closed_by: 'compliance_001' },
      version: 3,
    });

    renderDetail('case_med_1');
    const closeBtn = await screen.findByRole('button', { name: /Close Case/i });
    fireEvent.click(closeBtn);

    // Dialog opens
    expect(await screen.findByText('Close Compliance Case')).toBeInTheDocument();
    
    // Submit closure inside dialog
    const confirmBtn = screen.getAllByRole('button', { name: /Close Case/i })[1];
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mocks.mockCloseCase).toHaveBeenCalledWith('case_med_1', {
        resolution: 'Verified no money laundering.',
        expected_version: 2,
      });
    });
  });

  it('requires 4-eyes approval for High risk case closure', async () => {
    mocks.mockGetCase.mockResolvedValue(resolvedHighCase);
    mocks.mockCreateApproval.mockResolvedValue({
      approval_request: {
        approval_request_id: 'app_101',
        action_type: 'case_closure_critical_high',
        entity_type: 'compliance_case',
        entity_id: 'case_high_1',
        requested_by: 'compliance_001',
        status: 'pending',
        required_approvals: 1,
        approval_count: 0,
        version: 1,
        created_at: '2026-08-16T12:00:00Z',
      },
      version: 1,
    });

    renderDetail('case_high_1');
    fireEvent.click(await screen.findByRole('button', { name: /Close Case/i }));

    expect(await screen.findByText(/4-Eyes Approval Required/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Request Closure Approval/i }));

    await waitFor(() => {
      expect(mocks.mockCreateApproval).toHaveBeenCalledWith(expect.objectContaining({
        action_type: 'case_closure_critical_high',
        entity_type: 'compliance_case',
        entity_id: 'case_high_1',
      }));
    });
  });

  it('renders closed case in read-only state with Request Reopen action', async () => {
    mocks.mockGetCase.mockResolvedValue(closedCase);
    renderDetail('case_closed_1');

    expect(await screen.findByText('Case Closed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Request Reopen/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Record Decision/i })).not.toBeInTheDocument();
  });

  it('submits reopen request with mandatory reason', async () => {
    mocks.mockGetCase.mockResolvedValue(closedCase);
    mocks.mockCreateApproval.mockResolvedValue({
      approval_request: {
        approval_request_id: 'app_reopen_1',
        action_type: 'case_reopen',
        entity_type: 'compliance_case',
        entity_id: 'case_closed_1',
        requested_by: 'compliance_001',
        status: 'pending',
        required_approvals: 1,
        approval_count: 0,
        version: 1,
        created_at: '2026-08-16T12:00:00Z',
      },
      version: 1,
    });

    renderDetail('case_closed_1');
    fireEvent.click(await screen.findByRole('button', { name: /Request Reopen/i }));

    expect(await screen.findByText('Request Case Reopening')).toBeInTheDocument();

    const textarea = screen.getByPlaceholderText(/Explain why this closed case needs to be reopened/i);
    fireEvent.change(textarea, { target: { value: 'New evidence surfaced regarding structuring.' } });

    fireEvent.click(screen.getByRole('button', { name: /Request Reopen Approval/i }));

    await waitFor(() => {
      expect(mocks.mockCreateApproval).toHaveBeenCalledWith(expect.objectContaining({
        action_type: 'case_reopen',
        entity_type: 'compliance_case',
        entity_id: 'case_closed_1',
        rationale: 'New evidence surfaced regarding structuring.',
      }));
    });
  });
});

describe('Phase 3B.5 — Approval-Gated Action Inline Indicator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthState.userId = 'compliance_001';
    mockAuthState.role = 'compliance';
    mockAuthState.permissions = [
      'case:read_assigned', 'case:close', 'case:reopen', 'approval:read',
      'approval:request', 'approval:approve',
    ];
  });

  const pendingClosureApproval = {
    approval_request_id: 'app_pending_1',
    action_type: 'case_closure_critical_high',
    entity_type: 'compliance_case',
    entity_id: 'case_high_1',
    requested_by: 'compliance_002',
    rationale: 'Closure of high risk case',
    required_approvals: 1,
    approval_count: 0,
    status: 'pending',
    expires_at: '2026-09-01T00:00:00Z',
    version: 1,
    created_at: '2026-08-16T12:00:00Z',
    updated_at: '2026-08-16T12:00:00Z',
  };

  const approvedReopenApproval = {
    ...pendingClosureApproval,
    approval_request_id: 'app_approved_1',
    action_type: 'case_reopen',
    entity_id: 'case_closed_1',
    status: 'approved',
    approval_count: 1,
  };

  it('shows inline pending approval banner when a closure approval is pending', async () => {
    mocks.mockGetCase.mockResolvedValue(resolvedHighCase);
    mocks.mockListApprovals.mockImplementation((params: { status?: string }) => {
      return Promise.resolve({
        total: params.status === 'pending' ? 1 : 0,
        items: params.status === 'pending' ? [pendingClosureApproval] : [],
      });
    });

    renderDetail('case_high_1');

    expect(await screen.findByText(/4-eyes approval pending/i)).toBeInTheDocument();
    expect(screen.getByText(/case closure/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /View Approval/i })).toBeInTheDocument();
  });

  it('shows inline granted banner when reopen approval is approved but not executed', async () => {
    mocks.mockGetCase.mockResolvedValue(closedCase);
    mocks.mockListApprovals.mockImplementation((params: { status?: string }) => {
      return Promise.resolve({
        total: params.status === 'approved' ? 1 : 0,
        items: params.status === 'approved' ? [approvedReopenApproval] : [],
      });
    });

    renderDetail('case_closed_1');

    expect(await screen.findByText(/approval granted/i)).toBeInTheDocument();
    expect(screen.getByText(/ready to execute/i)).toBeInTheDocument();
  });

  it('renders no banner without approval:read permission', async () => {
    mockAuthState.permissions = ['case:read_assigned', 'case:close', 'case:reopen'];
    mocks.mockGetCase.mockResolvedValue(resolvedHighCase);
    mocks.mockListApprovals.mockResolvedValue({ total: 0, items: [] });

    renderDetail('case_high_1');

    expect(await screen.findByRole('button', { name: /Close Case/i })).toBeInTheDocument();
    expect(screen.queryByText(/4-eyes approval pending/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/approval granted/i)).not.toBeInTheDocument();
  });
});
