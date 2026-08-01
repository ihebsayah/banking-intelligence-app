import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';

const defaultHasPermission = (p: string): boolean => p === 'admin:outbox_monitor' || p === 'admin:outbox_retry';

const mockAuth = vi.hoisted(() => ({
  useAuth: vi.fn(() => ({ hasPermission: defaultHasPermission })),
}));

vi.mock('../../../auth/AuthProvider', () => ({ useAuth: mockAuth.useAuth }));

const { mockList, mockRetry } = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockRetry: vi.fn(),
}));

vi.mock('../../../api/adminOutboxApi', () => ({
  adminOutboxApi: {
    list: mockList,
    retry: mockRetry,
  },
}));

import { OutboxMonitor } from '../OutboxMonitor';
import type { AuditOutboxEvent } from '../../../types/alerts';

const base: AuditOutboxEvent = {
  outbox_id: 'outbox_12345678', idempotency_key: 'k1', event_type: 'alert.assigned',
  entity_type: 'alert', entity_id: 'alert_1', actor_id: 'u_1', actor_role: 'analyst',
  occurred_at: '2026-01-01T00:00:00Z', payload: {}, payload_schema_ver: 1,
  status: 'pending', attempt_count: 0, last_attempt_at: null, next_attempt_at: '2026-01-01T00:00:00Z',
  last_error: null, locked_by: null, locked_at: null, delivered_at: null,
  poison_reason: null, created_at: '2026-01-01T00:00:00Z',
};

const failed: typeof base = { ...base, outbox_id: 'outbox_failed_1', status: 'failed', attempt_count: 3, last_error: 'connection refused' };
const poison: typeof base = {
  ...base, outbox_id: 'outbox_poison_1', status: 'poison', attempt_count: 5,
  last_error: 'payload rejected', poison_reason: 'Failed after 5 attempts',
  payload: { amount: 99999, account_number: 'SENSITIVE_ACCOUNT' },
};

function renderMonitor() {
  return render(
    <MemoryRouter initialEntries={['/workbench/admin/outbox']}>
      <OutboxMonitor />
    </MemoryRouter>
  );
}

describe('OutboxMonitor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth.useAuth.mockImplementation(() => ({ hasPermission: defaultHasPermission }));
    mockList.mockResolvedValue({
      total: 4, page: 1, page_size: 50,
      items: [base, { ...base, status: 'delivering' }, { ...base, status: 'delivered' }, failed],
    });
    mockRetry.mockResolvedValue({ queued: true, outbox_id: 'outbox_failed_1' });
  });

  it('renders the dense table with event, entity, status, attempts, created and delivered', async () => {
    renderMonitor();
    await screen.findAllByText('alert.assigned');
    const table = within(screen.getByRole('table'));
    expect(table.getAllByText('alert').length).toBeGreaterThan(0);
    expect(table.getAllByText('alert_1').length).toBeGreaterThan(0);
    expect(table.getByText('Pending')).toBeInTheDocument();
    expect(table.getByText('Delivering')).toBeInTheDocument();
    expect(table.getAllByText('Delivered').length).toBeGreaterThan(0);
    expect(table.getByText('Failed')).toBeInTheDocument();
    expect(table.getByText('connection refused')).toBeInTheDocument();
  });

  it('sends the status filter and resets to page 1', async () => {
    renderMonitor();
    await screen.findAllByText('alert.assigned');
    fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: 'poison' } });
    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1][0];
      expect(lastCall.status).toBe('poison');
      expect(lastCall.page).toBe(1);
    });
  });

  it('paginates forward and back', async () => {
    const fifty = Array.from({ length: 50 }, (_, i) => ({ ...base, outbox_id: `outbox_${i}` }));
    mockList.mockResolvedValue({ total: 60, page: 1, page_size: 50, items: fifty });
    renderMonitor();
    await screen.findAllByText('alert.assigned');
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

  it('highlights poison rows with explicit Poison text and reason', async () => {
    mockList.mockResolvedValue({ total: 1, page: 1, page_size: 50, items: [poison] });
    renderMonitor();
    expect(await screen.findByText('Poison')).toBeInTheDocument();
    expect(screen.getByText('Failed after 5 attempts')).toBeInTheDocument();
  });

  it('shows a Retry action only for failed and poison rows', async () => {
    mockList.mockResolvedValue({
      total: 4, page: 1, page_size: 50,
      items: [base, { ...base, status: 'delivering' }, { ...base, status: 'delivered' }, failed],
    });
    renderMonitor();
    await screen.findAllByText('alert.assigned');
    const retries = screen.getAllByRole('button', { name: /Retry outbox event/i });
    expect(retries.length).toBe(1);
    expect(retries[0].getAttribute('aria-label')).toContain('outbox_failed_1');
  });

  it('retry opens a confirmation dialog and on confirm queues the retry and refreshes', async () => {
    renderMonitor();
    fireEvent.click(await screen.findByRole('button', { name: /Retry outbox event outbox_failed_1/i }));
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveTextContent(/resets the event to pending/i);
    expect(dialog).toHaveTextContent(/not.*replayed/i);
    fireEvent.click(screen.getByRole('button', { name: /Confirm retry/i }));
    await waitFor(() => expect(mockRetry).toHaveBeenCalledWith('outbox_failed_1'));
    expect(await screen.findByText('Retry queued — event returned to pending.')).toBeInTheDocument();
    await waitFor(() => expect(mockList.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('hides Retry without admin:outbox_retry permission even for failed rows', async () => {
    mockAuth.useAuth.mockReturnValue({ hasPermission: () => false });
    mockList.mockResolvedValue({ total: 1, page: 1, page_size: 50, items: [failed] });
    renderMonitor();
    await screen.findByText('Failed');
    expect(screen.queryByRole('button', { name: /Retry outbox event/i })).not.toBeInTheDocument();
  });

  it('shows a retry failure message without removing the row', async () => {
    mockRetry.mockRejectedValueOnce({ response: { status: 403, data: { error: 'FORBIDDEN' } } });
    renderMonitor();
    fireEvent.click(await screen.findByRole('button', { name: /Retry outbox event outbox_failed_1/i }));
    fireEvent.click(screen.getByRole('button', { name: /Confirm retry/i }));
    expect(await screen.findByText(/You do not have permission/i)).toBeInTheDocument();
    expect(screen.getAllByText('alert.assigned').length).toBeGreaterThan(0);
  });

  it('shows the empty state when no events match', async () => {
    mockList.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] });
    renderMonitor();
    expect(await screen.findByText('No outbox events')).toBeInTheDocument();
  });

  it('shows an error with retry that refetches', async () => {
    mockList.mockRejectedValueOnce({ response: { status: 503, data: { error: 'DB_UNAVAILABLE' } } });
    renderMonitor();
    const retry = await screen.findByRole('button', { name: /Retry/i });
    fireEvent.click(retry);
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(2));
  });

  it('does not leak sensitive payload content into the table', async () => {
    mockList.mockResolvedValue({ total: 1, page: 1, page_size: 50, items: [poison] });
    renderMonitor();
    await screen.findByText('Poison');
    expect(screen.queryByText('SENSITIVE_ACCOUNT')).not.toBeInTheDocument();
    expect(screen.queryByText('99999')).not.toBeInTheDocument();
  });
});
