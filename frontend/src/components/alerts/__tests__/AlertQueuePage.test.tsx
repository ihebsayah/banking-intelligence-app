import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const { mockListAssigned } = vi.hoisted(() => ({
  mockListAssigned: vi.fn(),
}));

vi.mock('../../../api/alertsApi', () => ({
  alertsApi: { listAssigned: mockListAssigned },
}));

import { AlertQueuePage } from '../AlertQueuePage';
import type { Alert } from '../../../types/alerts';

const base: Alert = {
  alert_id: 'a1', alert_type: 'transaction_anomaly', severity: 'high', title: 'Suspicious transfer',
  description: 'D', scope_id: 'hq_main', status: 'assigned', assigned_to: 'analyst_001',
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', version: 2,
};

const base2: Alert = { ...base, alert_id: 'a2', severity: 'low', status: 'new', title: 'Minor flag' };

function renderQueue() {
  return render(
    <MemoryRouter initialEntries={['/workbench/alerts']}>
      <Routes>
        <Route path="/workbench/alerts" element={<AlertQueuePage />} />
        <Route path="/workbench/alerts/:alertId" element={<div>detail-page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('AlertQueuePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListAssigned.mockResolvedValue({ total: 2, page: 1, page_size: 50, items: [base, base2] });
  });

  it('renders assigned alerts with severity and status badges', async () => {
    renderQueue();
    expect(await screen.findByText('Suspicious transfer')).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getByText('Minor flag')).toBeInTheDocument();
    expect(screen.getAllByText('assigned').length).toBeGreaterThan(0);
  });

  it('shows the empty state when no alerts are assigned', async () => {
    mockListAssigned.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] });
    renderQueue();
    expect(await screen.findByText('No alerts assigned to you')).toBeInTheDocument();
  });

  it('refetches with severity filter when the filter changes', async () => {
    renderQueue();
    await screen.findByText('Suspicious transfer');
    fireEvent.change(screen.getByLabelText('Filter by severity'), { target: { value: 'high' } });
    await waitFor(() => {
      const calls = mockListAssigned.mock.calls;
      expect(calls[calls.length - 1][0].severity).toBe('high');
      expect(calls[calls.length - 1][0].page).toBe(1);
    });
  });

  it('navigates to alert detail on row click', async () => {
    renderQueue();
    fireEvent.click(await screen.findByText('Suspicious transfer'));
    expect(await screen.findByText('detail-page')).toBeInTheDocument();
  });
});
