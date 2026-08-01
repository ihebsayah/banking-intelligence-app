import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const { mockListAssigned } = vi.hoisted(() => ({
  mockListAssigned: vi.fn(),
}));

vi.mock('../../../api/investigationsApi', () => ({
  investigationsApi: { listAssigned: mockListAssigned },
}));

import { InvestigationQueuePage } from '../InvestigationQueuePage';
import type { Investigation } from '../../../types/investigations';

const base: Investigation = {
  investigation_id: 'inv_1', title: 'Round-trip transfer', description: 'D', alert_id: 'al_12345678',
  scope_id: 'hq_main', status: 'active', priority: 'high', assigned_to: 'analyst_001', created_by: 'analyst_001',
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', version: 2,
};

const base2: Investigation = {
  ...base, investigation_id: 'inv_2', status: 'submitted', priority: 'low', title: 'Minor review',
};

function renderQueue() {
  return render(
    <MemoryRouter initialEntries={['/workbench/investigations']}>
      <Routes>
        <Route path="/workbench/investigations" element={<InvestigationQueuePage />} />
        <Route path="/workbench/investigations/:investigationId" element={<div>inv-detail</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('InvestigationQueuePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListAssigned.mockResolvedValue({ total: 2, page: 1, page_size: 50, items: [base, base2] });
  });

  it('renders assigned investigations with priority and status badges', async () => {
    renderQueue();
    expect(await screen.findByText('Round-trip transfer')).toBeInTheDocument();
    expect(screen.getByText('Minor review')).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getAllByText('submitted').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/alert #al_12345/).length).toBe(2);
  });

  it('shows the empty state when nothing is assigned', async () => {
    mockListAssigned.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] });
    renderQueue();
    expect(await screen.findByText('No investigations assigned to you')).toBeInTheDocument();
  });

  it('refetches with filters when status and priority change', async () => {
    renderQueue();
    await screen.findByText('Round-trip transfer');
    fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: 'active' } });
    fireEvent.change(screen.getByLabelText('Filter by priority'), { target: { value: 'high' } });
    await waitFor(() => {
      const calls = mockListAssigned.mock.calls;
      expect(calls[calls.length - 1][0].status).toBe('active');
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
    expect(await screen.findByText('inv-detail')).toBeInTheDocument();
  });
});
