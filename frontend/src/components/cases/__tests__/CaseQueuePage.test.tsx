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

const { mockListAssigned, mockListUnassigned, mockAssign } = vi.hoisted(() => ({
  mockListAssigned: vi.fn(),
  mockListUnassigned: vi.fn(),
  mockAssign: vi.fn(),
}));

vi.mock('../../../api/casesApi', () => ({
  casesApi: {
    listAssigned: mockListAssigned,
    listUnassigned: mockListUnassigned,
    assign: mockAssign,
  },
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

const unassignedCase: Case = {
  ...base, case_id: 'case_unassigned_1', title: 'Suspicious Structuring', status: 'open', assigned_to: null, version: 1,
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
    mockListAssigned.mockResolvedValue({ total: 2, page: 1, page_size: 50, items: [base, overdue] });
    mockListUnassigned.mockResolvedValue({ total: 1, page: 1, page_size: 50, items: [unassignedCase] });
  });

  it('renders assigned cases by default on My Cases tab', async () => {
    renderQueue();
    expect(await screen.findByText('Round-trip transfer')).toBeInTheDocument();
    expect(screen.getByText('Stale case')).toBeInTheDocument();
    expect(mockListAssigned).toHaveBeenCalled();
  });

  it('switches to Unassigned Cases tab and fetches unassigned cases', async () => {
    renderQueue();
    await screen.findByText('Round-trip transfer');
    
    fireEvent.click(screen.getByRole('button', { name: /Unassigned Cases/i }));
    
    expect(await screen.findByText('Suspicious Structuring')).toBeInTheDocument();
    expect(mockListUnassigned).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /Claim Case/i })).toBeInTheDocument();
  });

  it('handles successful claim of an unassigned case', async () => {
    mockAssign.mockResolvedValue({ success: true, case: { ...unassignedCase, assigned_to: 'compliance_001', status: 'assigned' }, version: 2 });
    renderQueue();
    fireEvent.click(screen.getByRole('button', { name: /Unassigned Cases/i }));
    await screen.findByText('Suspicious Structuring');

    fireEvent.click(screen.getByRole('button', { name: /Claim Case/i }));

    await waitFor(() => {
      expect(mockAssign).toHaveBeenCalledWith('case_unassigned_1', {
        assigned_to: 'compliance_001',
        expected_version: 1,
      });
    });
  });

  it('handles 409 conflict during claim gracefully', async () => {
    mockAssign.mockRejectedValue({ response: { status: 409, data: { error: 'VERSION_CONFLICT', message: 'Version conflict' } } });
    renderQueue();
    fireEvent.click(screen.getByRole('button', { name: /Unassigned Cases/i }));
    await screen.findByText('Suspicious Structuring');

    fireEvent.click(screen.getByRole('button', { name: /Claim Case/i }));

    await waitFor(() => {
      expect(screen.getByText('This case has already been claimed by another Compliance Officer.')).toBeInTheDocument();
    });
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
    });
  });
});
