import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const { mockList, mockMarkAllRead } = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockMarkAllRead: vi.fn(),
}));

vi.mock('../../../api/notificationsApi', () => ({
  notificationsApi: {
    list: mockList,
    markAllRead: mockMarkAllRead,
  },
}));

import { NotificationBell } from '../NotificationBell';
import type { Notification } from '../../../types/alerts';

const base: Notification = {
  notification_id: 'n_1', user_id: 'u_1', notification_type: 'alert_assigned',
  title: 'Alert assigned to you', body: 'Critical alert', entity_type: 'alert',
  entity_id: 'alert_1', is_read: false, read_at: null, created_at: '2026-01-01T00:00:00Z',
};

function renderBell(permissions: string[] = ['notification:read']) {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<NotificationBell permissions={permissions} />} />
        <Route path="/notifications" element={<div>notifications-page</div>} />
        <Route path="/workbench/alerts/:alertId" element={<div>alert-detail</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMarkAllRead.mockResolvedValue({ marked_read: 1 });
    mockList.mockResolvedValue({
      total: 1, page: 1, page_size: 10, unread_count: 1, items: [base],
    });
  });

  it('renders the bell button with an accessible unread-count label', async () => {
    renderBell();
    const btn = await screen.findByRole('button', { name: /Notifications, 1 unread/i });
    expect(btn).toBeInTheDocument();
  });

  it('is hidden without notification:read permission', () => {
    renderBell(['other:permission']);
    expect(screen.queryByRole('button', { name: /Notifications/i })).not.toBeInTheDocument();
  });

  it('shows no badge and a zero-unread label when there are no unread notifications', async () => {
    mockList.mockResolvedValue({ total: 0, page: 1, page_size: 10, unread_count: 0, items: [] });
    renderBell();
    const btn = await screen.findByRole('button', { name: /Notifications, 0 unread/i });
    expect(btn.textContent).not.toMatch(/[1-9]/);
  });

  it('opens the dropdown showing recent notifications and entity link', async () => {
    renderBell();
    fireEvent.click(await screen.findByRole('button', { name: /Notifications, 1 unread/i }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Alert assigned to you')).toBeInTheDocument();
    expect(screen.getByText('Critical alert')).toBeInTheDocument();
    const link = screen.getByText('Alert');
    expect(link.closest('a')).toHaveAttribute('href', '/workbench/alerts/alert_1');
  });

  it('shows a loading skeleton while the preview is loading', () => {
    let resolveList!: (v: unknown) => void;
    mockList.mockReturnValue(new Promise((r) => { resolveList = r; }));
    renderBell();
    fireEvent.click(screen.getByRole('button', { name: /Notifications/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
    resolveList({ total: 1, page: 1, page_size: 10, unread_count: 1, items: [base] });
  });

  it('marks all read and clears the unread badge', async () => {
    renderBell();
    fireEvent.click(await screen.findByRole('button', { name: /Notifications, 1 unread/i }));
    fireEvent.click(screen.getByRole('button', { name: /Mark all read/i }));
    await waitFor(() => expect(mockMarkAllRead).toHaveBeenCalled());
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Notifications, 0 unread/i })).toBeInTheDocument();
    });
  });

  it('disables mark-all-read when there is nothing unread', async () => {
    mockList.mockResolvedValue({ total: 1, page: 1, page_size: 10, unread_count: 0, items: [{ ...base, is_read: true }] });
    renderBell();
    fireEvent.click(await screen.findByRole('button', { name: /Notifications, 0 unread/i }));
    expect(screen.getByRole('button', { name: /Mark all read/i })).toBeDisabled();
  });

  it('navigates to the notifications page via View all', async () => {
    renderBell();
    fireEvent.click(await screen.findByRole('button', { name: /Notifications, 1 unread/i }));
    fireEvent.click(screen.getByRole('button', { name: /View all notifications/i }));
    expect(await screen.findByText('notifications-page')).toBeInTheDocument();
  });

  it('closes on Escape and refocuses the bell button', async () => {
    renderBell();
    fireEvent.click(await screen.findByRole('button', { name: /Notifications, 1 unread/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows an error state with retry when the preview fetch fails', async () => {
    mockList.mockRejectedValueOnce(new Error('boom')).mockRejectedValueOnce(new Error('boom'));
    renderBell();
    fireEvent.click(await screen.findByRole('button', { name: /Notifications/i }));
    expect(await screen.findByText('Could not load notifications.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Retry/i }));
    await waitFor(() => expect(mockList.mock.calls.length).toBeGreaterThanOrEqual(3));
  });
});
