import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const { mockListAssigned, mockListSubmitted, mockHasPermission } = vi.hoisted(() => ({
  mockListAssigned: vi.fn(),
  mockListSubmitted: vi.fn(),
  mockHasPermission: vi.fn(),
}));

vi.mock('../../../api/investigationsApi', () => ({
  investigationsApi: {
    listAssigned: mockListAssigned,
    listSubmitted: mockListSubmitted,
  },
}));

vi.mock('../../../auth/AuthProvider', () => ({
  useAuth: () => ({
    hasPermission: mockHasPermission,
  }),
}));

import { InvestigationQueuePage } from '../InvestigationQueuePage';
import type { Investigation } from '../../../types/investigations';
import { PERMISSIONS } from '../../../lib/permissions';

const base: Investigation = {
  investigation_id: 'inv_1', title: 'Round-trip transfer', description: 'D', alert_id: 'al_12345678',
  scope_id: 'hq_main', status: 'active', priority: 'high', assigned_to: 'analyst_001', created_by: 'analyst_001',
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', version: 2,
};

const baseSubmitted: Investigation = {
  ...base, investigation_id: 'inv_sub_1', status: 'submitted', priority: 'high', title: 'Submitted Review',
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
    mockHasPermission.mockImplementation((perm: string) => perm === PERMISSIONS.INVESTIGATION_READ_OWN);
    mockListAssigned.mockResolvedValue({ total: 1, page: 1, page_size: 50, items: [base] });
    mockListSubmitted.mockResolvedValue({ total: 1, page: 1, page_size: 50, items: [baseSubmitted] });
  });

  it('renders analyst assigned queue when user has investigation:read_own', async () => {
    renderQueue();
    expect(await screen.findByText('Round-trip transfer')).toBeInTheDocument();
    expect(mockListAssigned).toHaveBeenCalled();
    expect(mockListSubmitted).not.toHaveBeenCalled();
    expect(screen.getByText('Workbench — Investigation Queue')).toBeInTheDocument();
  });

  it('renders compliance review queue when user has investigation:review', async () => {
    mockHasPermission.mockImplementation((perm: string) => perm === PERMISSIONS.INVESTIGATION_REVIEW);
    renderQueue();
    expect(await screen.findByText('Submitted Review')).toBeInTheDocument();
    expect(mockListSubmitted).toHaveBeenCalled();
    expect(mockListAssigned).not.toHaveBeenCalled();
    expect(screen.getByText('Workbench — Compliance Review Queue')).toBeInTheDocument();
  });

  it('allows tab switching between submitted and assigned queues when user has both permissions', async () => {
    mockHasPermission.mockImplementation((perm: string) =>
      perm === PERMISSIONS.INVESTIGATION_REVIEW || perm === PERMISSIONS.INVESTIGATION_READ_OWN
    );
    renderQueue();
    expect(await screen.findByText('Submitted Review')).toBeInTheDocument();

    const assignedTab = screen.getByRole('button', { name: /My Assigned Investigations/i });
    fireEvent.click(assignedTab);

    expect(await screen.findByText('Round-trip transfer')).toBeInTheDocument();
    expect(mockListAssigned).toHaveBeenCalled();
  });

  it('shows empty state for compliance submitted queue', async () => {
    mockHasPermission.mockImplementation((perm: string) => perm === PERMISSIONS.INVESTIGATION_REVIEW);
    mockListSubmitted.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] });
    renderQueue();
    expect(await screen.findByText('No submitted investigations awaiting review')).toBeInTheDocument();
  });

  it('navigates to detail on row click', async () => {
    renderQueue();
    fireEvent.click(await screen.findByText('Round-trip transfer'));
    expect(await screen.findByText('inv-detail')).toBeInTheDocument();
  });
});
