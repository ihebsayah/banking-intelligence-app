import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';

const authState = vi.hoisted(() => ({ userId: 'compliance_001', permissions: ['approval:approve'] }));
const mockAuth = vi.hoisted(() => ({
  useAuth: () => ({
    applicationUser: { user_id: authState.userId, role: 'compliance' },
    hasPermission: (p: string) => authState.permissions.includes(p),
    hasRole: () => false,
  }),
}));

vi.mock('../../../auth/AuthProvider', () => ({ useAuth: mockAuth.useAuth }));

const { mockGet, mockVote } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockVote: vi.fn(),
}));

vi.mock('../../../api/approvalsApi', () => ({
  approvalsApi: {
    get: mockGet,
    vote: mockVote,
  },
}));

import { ApprovalDetailDialog } from '../ApprovalDetailDialog';
import type { ApprovalRequestDetail } from '../../../types/alerts';

const base: ApprovalRequestDetail = {
  approval_request_id: 'ar_1', action_type: 'decision_report_to_authority',
  entity_type: 'compliance_case', entity_id: 'case_1', requested_by: 'compliance_002',
  rationale: 'Threshold breached', required_approvals: 1, approval_count: 0,
  status: 'pending', expires_at: '2099-01-01T00:00:00Z', executed_at: null,
  version: 1, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  decisions: [],
};

function renderDialog(open = true, approvalId = 'ar_1', onSuccess = vi.fn(), onConflict = vi.fn()) {
  return render(
    <MemoryRouter initialEntries={['/workbench/approvals']}>
      <ApprovalDetailDialog
        open={open}
        approvalId={approvalId}
        onClose={vi.fn()}
        onSuccess={onSuccess}
        onConflict={onConflict}
      />
    </MemoryRouter>
  );
}

describe('ApprovalDetailDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.userId = 'compliance_001';
    authState.permissions = ['approval:approve'];
    mockGet.mockResolvedValue(base);
    mockVote.mockResolvedValue({ success: true, approval_request: { ...base, status: 'approved', approval_count: 1, decisions: [{ approval_decision_id: 'd1', approver_id: 'compliance_001', decision: 'approved', rationale: null, decided_at: '2026-01-02T00:00:00Z' }] }, version: 2 });
  });

  it('renders requester, action type, entity link, rationale, dates and votes', async () => {
    mockGet.mockResolvedValue({
      ...base,
      action_type: 'case_reopen',
      decisions: [
        { approval_decision_id: 'd1', approver_id: 'compliance_003', decision: 'approved', rationale: 'Reasoned', decided_at: '2026-01-02T00:00:00Z' },
      ],
    });
    renderDialog();
    expect(await screen.findByText('Case Reopen')).toBeInTheDocument();
    expect(screen.getByText('compliance_002')).toBeInTheDocument();
    const link = screen.getByText('Case ·', { exact: false }).closest('a');
    expect(link).toHaveAttribute('href', '/workbench/cases/case_1');
    expect(screen.getByText('Threshold breached')).toBeInTheDocument();
    expect(screen.getByText('compliance_003')).toBeInTheDocument();
    expect(screen.getByText('Reasoned')).toBeInTheDocument();
  });

  it('shows approved awaiting execution state without vote controls', async () => {
    mockGet.mockResolvedValue({ ...base, status: 'approved', approval_count: 1, executed_at: null });
    renderDialog();
    expect(await screen.findByText('Approved — awaiting execution')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
  });

  it('shows executed state', async () => {
    mockGet.mockResolvedValue({ ...base, status: 'approved', approval_count: 1, executed_at: '2026-02-01T00:00:00Z' });
    renderDialog();
    expect(await screen.findByText('Executed')).toBeInTheDocument();
  });

  it('shows expired state without vote controls', async () => {
    mockGet.mockResolvedValue({ ...base, status: 'expired' });
    renderDialog();
    expect(await screen.findByText('Expired')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('shows rejected state without vote controls', async () => {
    mockGet.mockResolvedValue({ ...base, status: 'rejected', decisions: [{ approval_decision_id: 'd1', approver_id: 'compliance_003', decision: 'rejected', rationale: 'No', decided_at: '2026-01-02T00:00:00Z' }] });
    renderDialog();
    expect(await screen.findByText('Rejected')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('approves through the confirmation step and reflects the server response', async () => {
    const onSuccess = vi.fn();
    renderDialog(undefined, undefined, onSuccess);
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approve' }));
    await waitFor(() => expect(mockVote).toHaveBeenCalledWith('ar_1', { decision: 'approved' }));
    expect(await screen.findByText('Approved — awaiting execution')).toBeInTheDocument();
    expect(onSuccess).toHaveBeenCalled();
  });

  it('rejects with a required rationale', async () => {
    mockVote.mockResolvedValue({ success: true, approval_request: { ...base, status: 'rejected', approval_count: 1, decisions: [{ approval_decision_id: 'd1', approver_id: 'compliance_001', decision: 'rejected', rationale: 'Insufficient', decided_at: '2026-01-02T00:00:00Z' }] }, version: 2 });
    renderDialog();
    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }));
    fireEvent.change(screen.getByLabelText('Rejection rationale *'), { target: { value: 'Insufficient evidence' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm reject' }));
    await waitFor(() => expect(mockVote).toHaveBeenCalledWith('ar_1', { decision: 'rejected', rationale: 'Insufficient evidence' }));
    expect(await screen.findByText('Rejected')).toBeInTheDocument();
  });

  it('blocks rejection until a rationale is provided', async () => {
    renderDialog();
    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }));
    const confirm = screen.getByRole('button', { name: 'Confirm reject' });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Rejection rationale *'), { target: { value: 'ok' } });
    expect(confirm).not.toBeDisabled();
  });

  it('hides vote controls and explains when the user is the requester', async () => {
    mockGet.mockResolvedValue({ ...base, requested_by: 'compliance_001' });
    renderDialog();
    expect(await screen.findByText('You cannot vote on your own approval request.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('hides vote controls when the user already voted', async () => {
    mockGet.mockResolvedValue({ ...base, decisions: [{ approval_decision_id: 'd1', approver_id: 'compliance_001', decision: 'approved', rationale: null, decided_at: '2026-01-02T00:00:00Z' }] });
    renderDialog();
    expect(await screen.findByText('You have already voted on this request. Your vote is listed above.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('hides vote controls without the approval:approve permission', async () => {
    authState.permissions = [];
    renderDialog();
    await screen.findByText('Threshold breached');
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('hides vote controls for pending requests past expiry time', async () => {
    mockGet.mockResolvedValue({ ...base, expires_at: '2000-01-01T00:00:00Z' });
    renderDialog();
    expect(await screen.findByText(/passed its expiry time/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('disables the confirm button while a vote is submitting', async () => {
    let release!: (v: unknown) => void;
    mockVote.mockImplementation(() => new Promise((resolve) => { release = resolve; }));
    renderDialog();
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approve' }));
    const confirm = screen.getByRole('button', { name: 'Submitting…' });
    expect(confirm).toBeDisabled();
    release({ success: true, approval_request: { ...base, status: 'approved', approval_count: 1, decisions: [] }, version: 2 });
    await waitFor(() => expect(screen.queryByText('Submitting…')).not.toBeInTheDocument());
  });

  it('keeps the request pending and shows progress for multi-approval requests', async () => {
    mockGet.mockResolvedValue({ ...base, required_approvals: 2, approval_count: 0 });
    mockVote.mockResolvedValue({ success: true, approval_request: { ...base, required_approvals: 2, approval_count: 1, status: 'pending', decisions: [{ approval_decision_id: 'd1', approver_id: 'compliance_001', decision: 'approved', rationale: null, decided_at: '2026-01-02T00:00:00Z' }] }, version: 2 });
    renderDialog();
    expect(await screen.findByText('0 of 2 approvals received')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm approve' }));
    await waitFor(() => expect(screen.getByText('1 of 2 approvals received')).toBeInTheDocument());
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  it('on 409 shows a conflict banner, refetches the detail, preserves the draft and stays read-only', async () => {
    const onConflict = vi.fn();
    mockVote.mockRejectedValue({ response: { status: 409, data: { error: 'INVALID_TRANSITION' } } });
    mockGet
      .mockResolvedValueOnce(base)
      .mockResolvedValueOnce({ ...base, status: 'approved', approval_count: 1, executed_at: null, decisions: [{ approval_decision_id: 'd1', approver_id: 'compliance_003', decision: 'approved', rationale: null, decided_at: '2026-01-02T00:00:00Z' }] });
    renderDialog(undefined, undefined, vi.fn(), onConflict);
    await screen.findByText('Threshold breached');
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));
    fireEvent.change(screen.getByLabelText('Rejection rationale *'), { target: { value: 'still drafting' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm reject' }));
    await waitFor(() => expect(onConflict).toHaveBeenCalled());
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(mockGet).toHaveBeenCalledTimes(2);
    expect(mockVote).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Approved — awaiting execution')).toBeInTheDocument());
  });

  it('shows a load error when the detail cannot be fetched', async () => {
    mockGet.mockRejectedValue({ response: { status: 404, data: { error: 'NOT_FOUND' } } });
    renderDialog();
    expect(await screen.findByText(/not found/i)).toBeInTheDocument();
  });
});
