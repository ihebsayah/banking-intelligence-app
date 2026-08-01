import { describe, it, expect, vi, beforeEach } from 'vitest';

const { mockGet, mockPatch } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPatch: vi.fn(),
}));

vi.mock('../client', () => ({
  apiClient: {
    get: mockGet,
    patch: mockPatch,
  },
}));

import { notificationsApi } from '../notificationsApi';

const notif = {
  notification_id: 'n_1', user_id: 'u_1', notification_type: 'alert_assigned',
  title: 'Alert assigned to you', body: 'Critical alert', entity_type: 'alert',
  entity_id: 'alert_1', is_read: false, read_at: null, created_at: '2026-01-01T00:00:00Z',
};

describe('notificationsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue({ data: { total: 1, page: 1, page_size: 50, unread_count: 1, items: [notif] } });
    mockPatch.mockResolvedValue({ data: { success: true, notification: { ...notif, is_read: true } } });
  });

  it('list hits /notifications with is_read, page and per_page', async () => {
    await notificationsApi.list({ isRead: false, page: 2, perPage: 10 });
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/notifications?');
    expect(url).toContain('is_read=false');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=10');
  });

  it('list defaults page and per_page and omits is_read when unset', async () => {
    await notificationsApi.list();
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/notifications?');
    expect(url).toContain('page=1');
    expect(url).toContain('per_page=50');
    expect(url).not.toContain('is_read=');
  });

  it('markRead patches /notifications/{id}/read with idempotency headers', async () => {
    await notificationsApi.markRead('n_1');
    const [url, body, cfg] = mockPatch.mock.calls[0];
    expect(url).toBe('/notifications/n_1/read');
    expect(body).toEqual({});
    expect(cfg.headers['X-Request-ID']).toBeTruthy();
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('markAllRead patches /notifications/read-all', async () => {
    mockPatch.mockResolvedValue({ data: { marked_read: 3 } });
    const res = await notificationsApi.markAllRead();
    expect(mockPatch.mock.calls[0][0]).toBe('/notifications/read-all');
    expect(res.marked_read).toBe(3);
  });

  it('does not expose delete, dismiss, archive or detail routes', async () => {
    await notificationsApi.list();
    await notificationsApi.markRead('n_1');
    await notificationsApi.markAllRead();
    const urls = [...mockGet.mock.calls, ...mockPatch.mock.calls].map((c) => c[0]);
    for (const u of urls) {
      expect(u).not.toMatch(/\/(delete|dismiss|archive)(\?|$)/);
    }
    for (const u of mockGet.mock.calls.map((c) => c[0])) {
      expect(u).not.toContain('/notifications/');
    }
  });
});
