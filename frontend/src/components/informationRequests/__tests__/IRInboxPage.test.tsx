import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const mockAuth = vi.hoisted(() => ({
  useAuth: () => ({
    applicationUser: { user_id: 'analyst_001', role: 'analyst' },
    hasPermission: () => true,
    hasRole: () => false,
  }),
}));

vi.mock('../../../auth/AuthProvider', () => ({ useAuth: mockAuth.useAuth }));

const { mockListAssigned, mockGet, mockAcknowledge, mockRespond } = vi.hoisted(() => ({
  mockListAssigned: vi.fn(),
  mockGet: vi.fn(),
  mockAcknowledge: vi.fn(),
  mockRespond: vi.fn(),
}));

vi.mock('../../../api/informationRequestsApi', () => ({
  informationRequestsApi: {
    listAssigned: mockListAssigned,
    get: mockGet,
    acknowledge: mockAcknowledge,
    respond: mockRespond,
  },
}));

import { IRInboxPage } from '../IRInboxPage';
import type { InformationRequest } from '../../../types/cases';

const base: InformationRequest = {
  ir_id: 'ir_1', case_id: 'case_1', created_by: 'compliance_001', assigned_to: 'analyst_001',
  question: 'Explain the source of funds', status: 'open', due_date: '2026-12-01',
  version: 1, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

const overdue: InformationRequest = {
  ...base, ir_id: 'ir_2', case_id: 'case_2', question: 'Provide proof of ownership',
  status: 'acknowledged', due_date: '2000-01-01', version: 2,
};

const accepted: InformationRequest = {
  ...base, ir_id: 'ir_3', case_id: 'case_3', question: 'List the beneficiaries',
  status: 'accepted', due_date: '2000-01-01', version: 3,
};

function renderInbox() {
  return render(
    <MemoryRouter initialEntries={['/workbench/information-requests']}>
      <Routes>
        <Route path="/workbench/information-requests" element={<IRInboxPage />} />
        <Route path="/workbench/cases/:caseId" element={<div>case-detail</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('IRInboxPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListAssigned.mockResolvedValue({ total: 3, page: 1, page_size: 50, items: [base, overdue, accepted] });
  });

  it('renders assigned requests with case id, question, due date and status', async () => {
    renderInbox();
    expect(await screen.findByText('Explain the source of funds')).toBeInTheDocument();
    expect(screen.getByText('Provide proof of ownership')).toBeInTheDocument();
    expect(screen.getAllByText('case_1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('open').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('accepted').length).toBeGreaterThanOrEqual(1);
  });

  it('marks past-due active requests as overdue but not accepted ones', async () => {
    renderInbox();
    await screen.findByText('Provide proof of ownership');
    const overdueLabels = screen.getAllByText('overdue');
    expect(overdueLabels.length).toBe(1);
  });

  it('shows the empty state when nothing is assigned', async () => {
    mockListAssigned.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] });
    renderInbox();
    expect(await screen.findByText('No information requests assigned to you')).toBeInTheDocument();
  });

  it('shows an error with retry that refetches', async () => {
    mockListAssigned.mockRejectedValueOnce({ response: { status: 503, data: { error: 'DB_UNAVAILABLE' } } });
    renderInbox();
    const retry = await screen.findByRole('button', { name: /Retry/i });
    fireEvent.click(retry);
    await waitFor(() => expect(mockListAssigned).toHaveBeenCalledTimes(2));
  });

  it('sends the status filter and resets to page 1', async () => {
    renderInbox();
    await screen.findByText('Explain the source of funds');
    const select = screen.getByLabelText('Filter by status');
    fireEvent.change(select, { target: { value: 'returned' } });
    await waitFor(() => {
      const lastCall = mockListAssigned.mock.calls[mockListAssigned.mock.calls.length - 1][0];
      expect(lastCall.status).toBe('returned');
      expect(lastCall.page).toBe(1);
    });
  });

  it('opens the response dialog when a row is clicked', async () => {
    renderInbox();
    const row = await screen.findByLabelText('Open information request ir_1');
    fireEvent.click(row);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByLabelText('Your response')).toBeInTheDocument();
  });

  it('opens the response dialog via keyboard (Enter)', async () => {
    renderInbox();
    const row = await screen.findByLabelText('Open information request ir_1');
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('does not open the dialog when the case link is clicked', async () => {
    renderInbox();
    const link = (await screen.findByText('case_1')).closest('a');
    fireEvent.click(link!);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('paginates forward and back', async () => {
    const fifty = Array.from({ length: 50 }, (_, i) => ({ ...base, ir_id: `ir_${i + 1}`, case_id: `case_${i + 1}` }));
    mockListAssigned.mockResolvedValue({ total: 60, page: 1, page_size: 50, items: fifty });
    renderInbox();
    await screen.findByLabelText('Open information request ir_1');
    fireEvent.click(screen.getByLabelText('Next page'));
    await waitFor(() => {
      const lastCall = mockListAssigned.mock.calls[mockListAssigned.mock.calls.length - 1][0];
      expect(lastCall.page).toBe(2);
    });
    fireEvent.click(screen.getByLabelText('Previous page'));
    await waitFor(() => {
      const lastCall = mockListAssigned.mock.calls[mockListAssigned.mock.calls.length - 1][0];
      expect(lastCall.page).toBe(1);
    });
  });

  it('refreshes the selected request on conflict and keeps the dialog open', async () => {
    const latest: InformationRequest = { ...base, status: 'acknowledged', version: 2 };
    mockGet.mockResolvedValue(latest);
    renderInbox();
    const row = await screen.findByLabelText('Open information request ir_1');
    fireEvent.click(row);
    mockAcknowledge.mockRejectedValue({ response: { status: 409, data: { error: 'VERSION_CONFLICT' } } });
    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }));
    await waitFor(() => expect(mockGet).toHaveBeenCalledWith('ir_1'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getAllByText('acknowledged').length).toBeGreaterThanOrEqual(1);
  });
});
