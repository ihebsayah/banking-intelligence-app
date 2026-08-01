import { describe, it, expect, vi, beforeEach } from 'vitest';

const { mockGet, mockPost, mockPatch } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPatch: vi.fn(),
}));

vi.mock('../client', () => ({
  apiClient: {
    get: mockGet,
    post: mockPost,
    patch: mockPatch,
  },
}));

import { alertsApi } from '../alertsApi';
import { approvalsApi } from '../approvalsApi';

const alert = {
  alert_id: 'a1', alert_type: 'transaction_anomaly', severity: 'high', title: 'T',
  description: 'D', scope_id: 'hq_main', status: 'assigned', assigned_to: 'analyst_001',
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', version: 3,
};

describe('alertsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue({ data: { total: 1, page: 1, page_size: 50, items: [alert] } });
    mockPost.mockResolvedValue({ data: { success: true } });
    mockPatch.mockResolvedValue({ data: { success: true, alert, version: 3 } });
  });

  it('listAssigned sends severity/status/page/per_page query params', async () => {
    await alertsApi.listAssigned({ severity: 'high', status: 'assigned', page: 2, perPage: 25 });
    expect(mockGet).toHaveBeenCalledTimes(1);
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/alerts/assigned?');
    expect(url).toContain('severity=high');
    expect(url).toContain('status=assigned');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=25');
  });

  it('listAssigned defaults page and per_page', async () => {
    await alertsApi.listAssigned();
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('page=1');
    expect(url).toContain('per_page=50');
  });

  it('get targets the alert id', async () => {
    await alertsApi.get('a1');
    expect(mockGet).toHaveBeenCalledWith('/alerts/a1');
  });

  it('acknowledge sends expected_version and X-Request-ID', async () => {
    await alertsApi.acknowledge('a1', 3);
    const [url, body, cfg] = mockPatch.mock.calls[0];
    expect(url).toBe('/alerts/a1/acknowledge');
    expect(body).toEqual({ expected_version: 3 });
    expect(cfg.headers['X-Request-ID']).toBeTruthy();
  });

  it('dismiss sends reason, version and optional approval_request_id', async () => {
    await alertsApi.dismiss('a1', { dismissed_reason: 'false positive', expected_version: 3 });
    const [, body] = mockPatch.mock.calls[0];
    expect(body).toEqual({ dismissed_reason: 'false positive', expected_version: 3 });
  });

  it('investigate sends X-Idempotency-Key and body', async () => {
    await alertsApi.investigate('a1', { title: 'Inv', expected_version: 3 });
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe('/alerts/a1/investigate');
    expect(body).toEqual({ title: 'Inv', expected_version: 3 });
    expect(cfg.headers['X-Request-ID']).toBeTruthy();
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('escalate sends priority and idempotency headers', async () => {
    await alertsApi.escalate('a1', { title: 'Case', priority: 'critical', expected_version: 3 });
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe('/alerts/a1/escalate');
    expect(body).toEqual({ title: 'Case', priority: 'critical', expected_version: 3 });
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('assign sends assigned_to, version and reason', async () => {
    await alertsApi.assign('a1', { assigned_to: 'analyst_002', expected_version: 3, reason: 'reassign' });
    const [, body] = mockPatch.mock.calls[0];
    expect(body).toEqual({ assigned_to: 'analyst_002', expected_version: 3, reason: 'reassign' });
  });

  it('approvalsApi.create posts to /approval-requests with idempotency', async () => {
    await approvalsApi.create({
      action_type: 'alert_dismissal_critical_high',
      entity_type: 'alert',
      entity_id: 'a1',
      rationale: 'false positive',
    });
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe('/approval-requests');
    expect(body).toEqual({
      action_type: 'alert_dismissal_critical_high',
      entity_type: 'alert',
      entity_id: 'a1',
      rationale: 'false positive',
    });
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('approvalsApi.get fetches a single approval request', async () => {
    await approvalsApi.get('apr_1');
    expect(mockGet).toHaveBeenCalledWith('/approval-requests/apr_1');
  });
});
