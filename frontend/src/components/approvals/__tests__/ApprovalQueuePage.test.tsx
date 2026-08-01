import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const mockAuth = vi.hoisted(() => ({
  useAuth: () => ({
    applicationUser: { user_id: 'compliance_001', role: 'compliance' },
    hasPermission: () => true,
    hasRole: () => false,
  }),
}));

vi.mock('../../../auth/AuthProvider', () => ({ useAuth: mockAuth.useAuth }));

const { mockList, mockGet, mockVote } = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockGet: vi.fn(),
  mockVote: vi.fn(),
}));

vi.mock('../../../api/approvalsApi', () => ({
  approvalsApi: {
    list: mockList,
    get: mockGet,
    vote: mockVote,
  },
}));

import { ApprovalQueuePage } from '../ApprovalQueuePage';
import type { ApprovalRequest, ApprovalRequestDetail } from '../../../types/alerts';

const base: ApprovalRequest = {
  approval_request_id: 'ar_1', action_type: 'alert_dismissal_critical_high',
  entity_type: 'alert', entity_id: 'alert_1', requested_by: 'compliance_001',
  rationale: 'Noise', required_approvals: 1, approval_count: 0, status: 'pending',
  expires_at: '2099-01-01T00:00:00Z', executed_at: null, version: 1,
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

const approvedAwaiting: ApprovalRequest = {
  ...base, approval_request_id: 'ar_2', entity_id: 'case_1',
  entity_type: 'compliance_case', action_type: 'case_closure_critical_high',
  status: 'approved', approval_count: 1,
};

const expiredByTime: ApprovalRequest = {
  ...base, approval_request_id: 'ar_3', action_type: 'case_reopen',
  entity_id: 'case_2', status: 'pending', expires_at: '2000-01-01T00:00:00Z',
};

const detail: ApprovalRequestDetail = { ...base, decisions: [] };

function renderQueue() {
  return render(
    <MemoryRouter initialEntries={['/workbench/approvals']}>
      <Routes>
        <Route path="/workbench/approvals" element={<ApprovalQueuePage />} />
        <Route path="/workbench/alerts/:alertId" element={<div>alert-detail</div>} />
        <Route path="/workbench/cases/:caseId" element={<div>case-detail</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ApprovalQueuePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue(detail);
    mockList.mockResolvedValue({ total: 3, page: 1, page_size: 50, items: [base, approvedAwaiting, expiredByTime] });
  });

  it('renders approval rows with action label, entity, requester, status, progress and expiry', async () => {
    renderQueue();
    expect(await screen.findByText('Critical/High Alert Dismissal')).toBeInTheDocument();
    expect(screen.getAllByText('alert_1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Alert').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('compliance_001').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Approved — awaiting execution')).toBeInTheDocument();
    expect(screen.getAllByText('0 / 1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('1 / 1')).toBeInTheDocument();
  });

  it('shows Expired text for pending requests past their expiry time', async () => {
    renderQueue();
    await screen.findByText('Critical/High Alert Dismissal');
    expect(screen.getAllByText('Expired').length).toBeGreaterThanOrEqual(1);
  });

  it('sends the status and action type filters and resets to page 1', async () => {
    renderQueue();
    await screen.findByText('Critical/High Alert Dismissal');
    fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: 'pending' } });
    fireEvent.change(screen.getByLabelText('Filter by action type'), { target: { value: 'case_reopen' } });
    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1][0];
      expect(lastCall.status).toBe('pending');
      expect(lastCall.actionType).toBe('case_reopen');
      expect(lastCall.page).toBe(1);
    });
  });

  it('shows the empty state when nothing is in scope', async () => {
    mockList.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] });
    renderQueue();
    expect(await screen.findByText('No approval requests in your scope')).toBeInTheDocument();
  });

  it('shows a filtered empty state when filters match nothing', async () => {
    mockList.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] });
    renderQueue();
    await screen.findByText('No approval requests in your scope');
    fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: 'expired' } });
    expect(await screen.findByText('No approval requests match the selected filters')).toBeInTheDocument();
  });

  it('shows an error with retry that refetches', async () => {
    mockList.mockRejectedValueOnce({ response: { status: 503, data: { error: 'DB_UNAVAILABLE' } } });
    renderQueue();
    const retry = await screen.findByRole('button', { name: /Retry/i });
    fireEvent.click(retry);
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(2));
  });

  it('opens the detail dialog on row click and fetches the detail', async () => {
    renderQueue();
    const row = await screen.findByLabelText('Open approval request ar_1');
    fireEvent.click(row);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await waitFor(() => expect(mockGet).toHaveBeenCalledWith('ar_1'));
  });

  it('opens the detail dialog via keyboard (Enter)', async () => {
    renderQueue();
    const row = await screen.findByLabelText('Open approval request ar_1');
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });

  it('does not open the dialog when the entity link is clicked', async () => {
    renderQueue();
    const link = (await screen.findByText('alert_1')).closest('a');
    fireEvent.click(link!);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('paginates forward and back', async () => {
    const fifty = Array.from({ length: 50 }, (_, i) => ({ ...base, approval_request_id: `ar_${i + 1}` }));
    mockList.mockResolvedValue({ total: 60, page: 1, page_size: 50, items: fifty });
    renderQueue();
    await screen.findByLabelText('Open approval request ar_1');
    fireEvent.click(screen.getByLabelText('Next page'));
    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1][0];
      expect(lastCall.page).toBe(2);
    });
    fireEvent.click(screen.getByLabelText('Previous page'));
    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1][0];
      expect(lastCall.page).toBe(1);
    });
  });
});
