import { describe, it, expect, vi, beforeEach } from 'vitest';

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}));

vi.mock('../client', () => ({
  apiClient: {
    get: mockGet,
    post: mockPost,
  },
}));

import { adminOutboxApi } from '../adminOutboxApi';

const event = {
  outbox_id: 'outbox_1', idempotency_key: 'alert.alert_1.alert.assigned.abc',
  event_type: 'alert.assigned', entity_type: 'alert', entity_id: 'alert_1',
  actor_id: 'u_1', actor_role: 'analyst', occurred_at: '2026-01-01T00:00:00Z',
  payload: {}, payload_schema_ver: 1, status: 'failed', attempt_count: 3,
  last_attempt_at: null, next_attempt_at: '2026-01-02T00:00:00Z', last_error: 'conn refused',
  locked_by: null, locked_at: null, delivered_at: null, poison_reason: null,
  created_at: '2026-01-01T00:00:00Z',
};

describe('adminOutboxApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue({ data: { total: 1, page: 1, page_size: 50, items: [event] } });
    mockPost.mockResolvedValue({ data: { queued: true, outbox_id: 'outbox_1' } });
  });

  it('list hits /admin/outbox with status, page and per_page', async () => {
    await adminOutboxApi.list({ status: 'poison', page: 2, perPage: 25 });
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/admin/outbox?');
    expect(url).toContain('status=poison');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=25');
  });

  it('list defaults page and per_page and omits status when unset', async () => {
    await adminOutboxApi.list();
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/admin/outbox?');
    expect(url).toContain('page=1');
    expect(url).toContain('per_page=50');
    expect(url).not.toContain('status=');
  });

  it('retry posts /admin/outbox/{id}/retry with request id header', async () => {
    const res = await adminOutboxApi.retry('outbox_1');
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe('/admin/outbox/outbox_1/retry');
    expect(body).toEqual({});
    expect(cfg.headers['X-Request-ID']).toBeTruthy();
    expect(res).toEqual({ queued: true, outbox_id: 'outbox_1' });
  });

  it('does not expose a replay endpoint', async () => {
    await adminOutboxApi.list();
    await adminOutboxApi.retry('outbox_1');
    const urls = [...mockGet.mock.calls, ...mockPost.mock.calls].map((c) => c[0]);
    for (const u of urls) {
      expect(u).not.toMatch(/\/replay/);
    }
  });
});
