import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const { mockList, mockMarkRead, mockMarkAllRead } = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockMarkRead: vi.fn(),
  mockMarkAllRead: vi.fn(),
}));

vi.mock('../../../api/notificationsApi', () => ({
  notificationsApi: {
    list: mockList,
    markRead: mockMarkRead,
    markAllRead: mockMarkAllRead,
  },
}));

import { NotificationsPanel } from '../NotificationsPanel';
import type { Notification } from '../../../types/alerts';

const base: Notification = {
  notification_id: 'n_1', user_id: 'u_1', notification_type: 'alert_assigned',
  title: 'Alert assigned to you', body: 'Critical alert', entity_type: 'alert',
  entity_id: 'alert_1', is_read: false, read_at: null, created_at: '2026-01-01T00:00:00Z',
};

const read: typeof base = {
  ...base, notification_id: 'n_2', notification_type: 'approval_decided',
  title: 'Approval request approved', body: 'Your request was approved',
  entity_type: 'approval_request', entity_id: 'ar_1', is_read: true,
  read_at: '2026-01-02T00:00:00Z',
};

function renderPanel() {
  return render(
    <MemoryRouter initialEntries={['/notifications']}>
      <Routes>
        <Route path="/notifications" element={<NotificationsPanel />} />
        <Route path="/workbench/alerts/:alertId" element={<div>alert-detail</div>} />
        <Route path="/workbench/approvals" element={<div>approvals-page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('NotificationsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({ total: 2, page: 1, page_size: 50, unread_count: 1, items: [base, read] });
    mockMarkRead.mockResolvedValue({ success: true, notification: { ...base, is_read: true } });
    mockMarkAllRead.mockResolvedValue({ marked_read: 1 });
  });

  it('renders current-user notification rows with explicit unread/read text', async () => {
    renderPanel();
    expect(await screen.findByText('Alert assigned to you')).toBeInTheDocument();
    expect(screen.getByText('Approval request approved')).toBeInTheDocument();
    const table = within(screen.getByRole('table'));
    expect(table.getByText('Unread')).toBeInTheDocument();
    expect(table.getByText('Read')).toBeInTheDocument();
    expect(screen.getByText('1 unread')).toBeInTheDocument();
  });

  it('shows the type label and entity label on each row', async () => {
    renderPanel();
    expect(await screen.findByText('Alert assigned')).toBeInTheDocument();
    expect(screen.getByText('Approval decided')).toBeInTheDocument();
  });

  it('links the entity to the mapped 2B route', async () => {
    renderPanel();
    const alertLink = (await screen.findByText('Alert')).closest('a');
    expect(alertLink).toHaveAttribute('href', '/workbench/alerts/alert_1');
    const approvalLink = screen.getByText('Approval').closest('a');
    expect(approvalLink).toHaveAttribute('href', '/workbench/approvals');
  });

  it('sends the read filter to the API and resets to page 1', async () => {
    renderPanel();
    await screen.findByText('Alert assigned to you');
    fireEvent.change(screen.getByLabelText('Filter by read status'), { target: { value: 'false' } });
    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1][0];
      expect(lastCall.isRead).toBe(false);
      expect(lastCall.page).toBe(1);
    });
  });

  it('paginates forward and back', async () => {
    const fifty = Array.from({ length: 50 }, (_, i) => ({ ...base, notification_id: `n_${i}` }));
    mockList.mockResolvedValue({ total: 60, page: 1, page_size: 50, unread_count: 50, items: fifty });
    renderPanel();
    await screen.findAllByText('Alert assigned to you');
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

  it('shows the loading skeleton during the initial fetch', () => {
    let resolveList!: (v: unknown) => void;
    mockList.mockReturnValue(new Promise((r) => { resolveList = r; }));
    renderPanel();
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
    resolveList({ total: 2, page: 1, page_size: 50, unread_count: 1, items: [base, read] });
  });

  it('shows the empty state when there are no notifications', async () => {
    mockList.mockResolvedValue({ total: 0, page: 1, page_size: 50, unread_count: 0, items: [] });
    renderPanel();
    expect(await screen.findByText('No notifications yet')).toBeInTheDocument();
  });

  it('shows an error with retry that refetches', async () => {
    mockList.mockRejectedValueOnce({ response: { status: 503, data: { error: 'DB_UNAVAILABLE' } } });
    renderPanel();
    const retry = await screen.findByRole('button', { name: /Retry/i });
    fireEvent.click(retry);
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(2));
  });

  it('marks one notification read, updates the local row and decrements the unread count', async () => {
    renderPanel();
    await screen.findByText('Alert assigned to you');
    const table = within(screen.getByRole('table'));
    expect(table.getAllByText('Unread').length).toBe(1);
    fireEvent.click(screen.getByRole('button', { name: /Mark notification read: Alert assigned to you/i }));
    await waitFor(() => expect(mockMarkRead).toHaveBeenCalledWith('n_1'));
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Mark notification read/i })).not.toBeInTheDocument();
      expect(screen.getByText('0 unread')).toBeInTheDocument();
    });
  });

  it('does not render a mark-read control for already-read notifications', async () => {
    renderPanel();
    await screen.findByText('Alert assigned to you');
    const buttons = screen.queryAllByRole('button', { name: /Mark notification read/i });
    expect(buttons.length).toBe(1);
  });

  it('marks all read, reports the affected count in a live region and clears unread', async () => {
    renderPanel();
    await screen.findByText('Alert assigned to you');
    fireEvent.click(screen.getByRole('button', { name: /Mark all read/i }));
    await waitFor(() => expect(mockMarkAllRead).toHaveBeenCalled());
    expect(await screen.findByText('Marked 1 notification as read')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('0 unread')).toBeInTheDocument());
  });

  it('keeps the row when mark-one-read fails and shows an error', async () => {
    mockMarkRead.mockRejectedValueOnce({
      response: { status: 404, data: { error: 'NOT_FOUND', message: 'Notification not found: n_1' } },
    });
    renderPanel();
    await screen.findByText('Alert assigned to you');
    fireEvent.click(screen.getByRole('button', { name: /Mark notification read: Alert assigned to you/i }));
    expect(await screen.findByText(/Notification not found/i)).toBeInTheDocument();
    expect(screen.getByText('Alert assigned to you')).toBeInTheDocument();
  });

  it('exposes no cross-user controls', async () => {
    renderPanel();
    await screen.findByText('Alert assigned to you');
    expect(screen.queryByLabelText(/user/i)).not.toBeInTheDocument();
  });
});
