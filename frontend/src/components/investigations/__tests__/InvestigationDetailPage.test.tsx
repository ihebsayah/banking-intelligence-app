import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const mockAuth = vi.hoisted(() => {
  const state = {
    userId: 'analyst_001',
    role: 'analyst',
    permissions: [
      'investigation:read_own', 'investigation:modify_findings', 'investigation:transition',
      'investigation:review', 'investigation:assign',
    ] as string[],
  };
  return {
    state,
    useAuth: () => ({
      applicationUser: { user_id: state.userId, role: state.role },
      hasPermission: (p: string) => state.permissions.includes(p),
      hasRole: (r: string) => r === state.role,
      permissions: state.permissions,
    }),
  };
});

const { mockGet, mockTransition, mockCancel, mockUpdate, mockListComments, mockListTimeline } =
  vi.hoisted(() => ({
    mockGet: vi.fn(),
    mockTransition: vi.fn(),
    mockCancel: vi.fn(),
    mockUpdate: vi.fn(),
    mockListComments: vi.fn(),
    mockListTimeline: vi.fn(),
  }));

vi.mock('../../../auth/AuthProvider', () => ({ useAuth: mockAuth.useAuth }));

vi.mock('../../../api/investigationsApi', () => ({
  investigationsApi: {
    get: mockGet,
    transition: mockTransition,
    cancel: mockCancel,
    update: mockUpdate,
    listComments: mockListComments,
    listTimeline: mockListTimeline,
  },
}));

import { InvestigationDetailPage } from '../InvestigationDetailPage';

function makeInvestigation(overrides: Record<string, unknown> = {}) {
  return {
    investigation_id: 'inv_1', title: 'Round-trip transfer', description: 'Large round-trip transaction',
    alert_id: 'al_12345678', scope_id: 'hq_main', status: 'active', priority: 'high',
    assigned_to: 'analyst_001', created_by: 'analyst_001',
    findings_text: null, findings_refs: [], conclusion: null,
    started_at: null, submitted_at: null, completed_at: null, return_reason: null,
    version: 4, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/workbench/investigations/inv_1']}>
      <Routes>
        <Route path="/workbench/investigations/:investigationId" element={<InvestigationDetailPage />} />
        <Route path="/workbench/investigations" element={<div>queue-page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

const defaultTimeline = {
  total: 1, page: 1, page_size: 50,
  items: [{
    timeline_id: 't1', entity_type: 'investigation', entity_id: 'inv_1',
    event_type: 'investigation.status_changed', actor_id: 'analyst_001',
    old_value: { status: 'active' }, new_value: { status: 'submitted' },
    occurred_at: '2026-01-01T00:00:00Z',
  }],
};

describe('InvestigationDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth.state.userId = 'analyst_001';
    mockAuth.state.role = 'analyst';
    mockAuth.state.permissions = [
      'investigation:read_own', 'investigation:modify_findings', 'investigation:transition',
      'investigation:review', 'investigation:assign',
    ];
    mockGet.mockResolvedValue(makeInvestigation());
    mockTransition.mockResolvedValue({ success: true, investigation: makeInvestigation({ status: 'active', version: 5 }), version: 5 });
    mockCancel.mockResolvedValue({ success: true, investigation: makeInvestigation({ status: 'cancelled', version: 5 }), version: 5 });
    mockUpdate.mockResolvedValue({
      success: true,
      investigation: makeInvestigation({ findings_text: 'Evidence found', version: 5 }),
      version: 5,
    });
    mockListComments.mockResolvedValue({ total: 1, page: 1, page_size: 50, items: [{ comment_id: 'c1', entity_type: 'investigation', entity_id: 'inv_1', content: 'review note', author_id: 'analyst_001', is_internal: false, is_redacted: false, version: 1, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }] });
    mockListTimeline.mockResolvedValue(defaultTimeline);
  });

  it('renders fields, badges, version and linked alert', async () => {
    renderDetail();
    expect(await screen.findByText('Round-trip transfer')).toBeInTheDocument();
    expect(screen.getByText('Large round-trip transaction')).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getByText('v4')).toBeInTheDocument();
    expect(screen.getByText('hq_main')).toBeInTheDocument();
    expect(screen.getByText(/al_12345/)).toBeInTheDocument();
    expect(mockGet).toHaveBeenCalledWith('inv_1');
  });

  it('shows the not-found state for an unknown investigation', async () => {
    mockGet.mockRejectedValue({ response: { status: 404, data: { message: 'Investigation not found.' } } });
    renderDetail();
    expect(await screen.findByText('Investigation not found.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Back to queue/i }));
    expect(await screen.findByText('queue-page')).toBeInTheDocument();
  });

  it('analyst starts an open investigation', async () => {
    mockGet.mockResolvedValue(makeInvestigation({ status: 'open' }));
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Start Investigation/i }));
    await waitFor(() => expect(mockTransition).toHaveBeenCalledWith('inv_1', { target_status: 'active', expected_version: 4 }));
  });

  it('submits an active investigation for review after confirming', async () => {
    mockGet.mockResolvedValue(makeInvestigation({ findings_text: 'Evidence found' }));
    mockTransition.mockResolvedValue({ success: true, investigation: makeInvestigation({ status: 'submitted', findings_text: 'Evidence found', version: 5 }), version: 5 });
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Submit for Review/i }));
    expect(await screen.findByText(/final compliance approval/i)).toBeInTheDocument();
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Submit for Review/i }));
    await waitFor(() => expect(mockTransition).toHaveBeenCalledWith('inv_1', { target_status: 'submitted', expected_version: 4 }));
  });

  it('analyst completes when findings and conclusion exist', async () => {
    mockGet.mockResolvedValue(makeInvestigation({ findings_text: 'Evidence found', conclusion: 'Confirmed' }));
    mockTransition.mockResolvedValue({ success: true, investigation: makeInvestigation({ status: 'completed', version: 5 }), version: 5 });
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Complete/i }));
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Complete/i }));
    await waitFor(() => expect(mockTransition).toHaveBeenCalledWith('inv_1', { target_status: 'completed', expected_version: 4 }));
  });

  it('hides Submit/Complete when findings are missing', async () => {
    renderDetail();
    await screen.findByText('Round-trip transfer');
    expect(screen.queryByRole('button', { name: /Submit for Review/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Complete/i })).not.toBeInTheDocument();
  });

  it('compliance reviewer approves a submitted investigation', async () => {
    mockAuth.state.role = 'compliance';
    mockAuth.state.permissions = ['investigation:read_own', 'investigation:review'];
    mockGet.mockResolvedValue(makeInvestigation({ status: 'submitted', submitted_at: '2026-01-02T00:00:00Z' }));
    mockTransition.mockResolvedValue({ success: true, investigation: makeInvestigation({ status: 'completed', version: 5 }), version: 5 });
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Approve/i }));
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Approve/i }));
    await waitFor(() => expect(mockTransition).toHaveBeenCalledWith('inv_1', { target_status: 'completed', expected_version: 4 }));
  });

  it('compliance reviewer returns for revision with a reason', async () => {
    mockAuth.state.role = 'compliance';
    mockAuth.state.permissions = ['investigation:read_own', 'investigation:review'];
    mockGet.mockResolvedValue(makeInvestigation({ status: 'submitted' }));
    mockTransition.mockResolvedValue({
      success: true,
      investigation: makeInvestigation({ status: 'returned', return_reason: 'more evidence', version: 5 }),
      version: 5,
    });
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Return for Revision/i }));
    fireEvent.change(screen.getByLabelText(/Return reason/i), { target: { value: 'more evidence' } });
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Return for Revision/i }));
    await waitFor(() => expect(mockTransition).toHaveBeenCalledWith('inv_1', {
      target_status: 'returned', return_reason: 'more evidence', expected_version: 4,
    }));
  });

  it('analyst without review permission sees no Approve/Return buttons', async () => {
    mockAuth.state.permissions = ['investigation:read_own', 'investigation:modify_findings', 'investigation:transition'];
    mockGet.mockResolvedValue(makeInvestigation({ status: 'submitted' }));
    renderDetail();
    await screen.findByText('Round-trip transfer');
    expect(screen.queryByRole('button', { name: /Approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Return for Revision/i })).not.toBeInTheDocument();
  });

  it('returned investigation shows reason banner and resume action', async () => {
    mockGet.mockResolvedValue(makeInvestigation({ status: 'returned', return_reason: 'more evidence needed' }));
    renderDetail();
    expect(await screen.findByText(/returned — reason: more evidence needed/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Mark Revision Started/i }));
    await waitFor(() => expect(mockTransition).toHaveBeenCalledWith('inv_1', { target_status: 'active', expected_version: 4 }));
  });

  it('admin cancels an investigation with a reason', async () => {
    mockAuth.state.role = 'admin';
    mockAuth.state.permissions = ['investigation:read_own', 'investigation:assign'];
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Cancel Investigation/i }));
    fireEvent.change(screen.getByLabelText(/Cancellation reason/i), { target: { value: 'duplicate' } });
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Cancel Investigation/i }));
    await waitFor(() => expect(mockCancel).toHaveBeenCalledWith('inv_1', { cancel_reason: 'duplicate', expected_version: 4 }));
  });

  it('non-admin analyst cannot cancel', async () => {
    renderDetail();
    await screen.findByText('Round-trip transfer');
    expect(screen.queryByRole('button', { name: /Cancel Investigation/i })).not.toBeInTheDocument();
  });

  it('edits and saves findings', async () => {
    renderDetail();
    fireEvent.click(await screen.findByRole('tab', { name: 'Findings' }));
    const textarea = screen.getByLabelText('Findings', { selector: 'textarea' });
    expect(textarea).not.toBeDisabled();
    fireEvent.change(textarea, { target: { value: 'Evidence found' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Findings/i }));
    await waitFor(() => expect(mockUpdate).toHaveBeenCalledWith('inv_1', {
      findings_text: 'Evidence found', findings_refs: [], conclusion: '', expected_version: 4,
    }));
    expect(await screen.findByText('Findings saved.')).toBeInTheDocument();
  });

  it('read-only findings for a compliance reviewer', async () => {
    mockAuth.state.role = 'compliance';
    mockAuth.state.permissions = ['investigation:read_own', 'investigation:review'];
    renderDetail();
    fireEvent.click(await screen.findByRole('tab', { name: 'Findings' }));
    expect(await screen.findByText('Read-only view')).toBeInTheDocument();
    expect(screen.getByLabelText('Findings', { selector: 'textarea' })).toBeDisabled();
  });

  it('shows a conflict banner and refetches on 409', async () => {
    mockGet.mockResolvedValue(makeInvestigation({ findings_text: 'Evidence found' }));
    mockTransition.mockRejectedValue({ response: { status: 409, data: { message: 'Investigation was updated' } } });
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Submit for Review/i }));
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Submit for Review/i }));
    expect(await screen.findByText(/Investigation was updated by someone else/i)).toBeInTheDocument();
    await waitFor(() => expect(mockGet.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('loads and renders comments in the Comments tab', async () => {
    renderDetail();
    fireEvent.click(await screen.findByRole('tab', { name: 'Comments' }));
    expect(await screen.findByText('review note')).toBeInTheDocument();
    expect(mockListComments).toHaveBeenCalledWith('inv_1', 1, 50);
  });

  it('loads and renders the timeline', async () => {
    renderDetail();
    fireEvent.click(await screen.findByRole('tab', { name: 'Timeline' }));
    expect(await screen.findByText('status changed')).toBeInTheDocument();
    expect(await screen.findByText('status active → submitted')).toBeInTheDocument();
    expect(mockListTimeline).toHaveBeenCalledWith('inv_1', 1, 50);
  });
});
