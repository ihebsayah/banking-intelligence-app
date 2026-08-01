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

const { mockListAssigned } = vi.hoisted(() => ({
  mockListAssigned: vi.fn(),
}));

vi.mock('../../../api/casesApi', () => ({
  casesApi: { listAssigned: mockListAssigned },
}));

import { CaseQueuePage } from '../CaseQueuePage';
import type { Case } from '../../../types/cases';

const base: Case = {
  case_id: 'case_1', title: 'Round-trip transfer', description: 'D',
  scope_id: 'hq_main', status: 'under_review', priority: 'high', risk_level: 'high',
  assigned_to: 'compliance_001', created_by: 'analyst_001',
  target_date: '2026-12-01', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', version: 3,
};

const overdue: Case = {
  ...base, case_id: 'case_2', title: 'Stale case', status: 'assigned', priority: 'critical',
  target_date: '2000-01-01',
};

const base2: Case = {
  ...base, case_id: 'case_3', title: 'Minor review', status: 'resolved', priority: 'low', risk_level: 'low',
  target_date: '2000-01-01',
};

function renderQueue() {
  return render(
    <MemoryRouter initialEntries={['/workbench/cases']}>
      <Routes>
        <Route path="/workbench/cases" element={<CaseQueuePage />} />
        <Route path="/workbench/cases/:caseId" element={<div>case-detail</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('CaseQueuePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListAssigned.mockResolvedValue({ total: 3, page: 1, page_size: 50, items: [base, base2, overdue] });
  });

  it('renders assigned cases with risk, priority and status badges', async () => {
    renderQueue();
    expect(await screen.findByText('Round-trip transfer')).toBeInTheDocument();
    expect(screen.getByText('Minor review')).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getAllByText('High risk').length).toBe(2);
    expect(screen.getByText('Low risk')).toBeInTheDocument();
    expect(screen.getAllByText('under review').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/assigned to you/).length).toBe(4); // 3 rows + header subtitle
  });

  it('marks overdue rows with an overdue label (resolved excluded)', async () => {
    renderQueue();
    await screen.findByText('Round-trip transfer');
    expect(screen.getByText('overdue')).toBeInTheDocument();
    expect(screen.getByText('Stale case')).toBeInTheDocument();
    // resolved case with a past target date must NOT be overdue
    expect(screen.getAllByText('overdue').length).toBe(1);
  });

  it('shows the empty state when nothing is assigned', async () => {
    mockListAssigned.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] });
    renderQueue();
    expect(await screen.findByText('No cases assigned to you')).toBeInTheDocument();
  });

  it('refetches with filters when status and priority change', async () => {
    renderQueue();
    await screen.findByText('Round-trip transfer');
    fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: 'under_review' } });
    fireEvent.change(screen.getByLabelText('Filter by priority'), { target: { value: 'high' } });
    await waitFor(() => {
      const calls = mockListAssigned.mock.calls;
      expect(calls[calls.length - 1][0].status).toBe('under_review');
      expect(calls[calls.length - 1][0].priority).toBe('high');
      expect(calls[calls.length - 1][0].page).toBe(1);
    });
  });

  it('shows the error state and retries on failure', async () => {
    mockListAssigned.mockRejectedValue({ response: { status: 503, data: { message: 'Down' } } });
    renderQueue();
    expect(await screen.findByText('Down')).toBeInTheDocument();
    mockListAssigned.mockResolvedValue({ total: 1, page: 1, page_size: 50, items: [base] });
    fireEvent.click(screen.getByRole('button', { name: /Retry/i }));
    expect(await screen.findByText('Round-trip transfer')).toBeInTheDocument();
  });

  it('navigates to detail on row click', async () => {
    renderQueue();
    fireEvent.click(await screen.findByText('Round-trip transfer'));
    expect(await screen.findByText('case-detail')).toBeInTheDocument();
  });
});
