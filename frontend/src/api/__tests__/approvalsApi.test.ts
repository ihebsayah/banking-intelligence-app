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

import { approvalsApi } from '../approvalsApi';

const arData = {
  approval_request_id: 'ar_1', action_type: 'alert_dismissal_critical_high',
  entity_type: 'alert', entity_id: 'alert_1', requested_by: 'compliance_001',
  rationale: 'Noise', required_approvals: 1, approval_count: 0, status: 'pending',
  expires_at: '2099-01-01T00:00:00Z', executed_at: null, version: 1,
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

describe('approvalsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue({ data: { total: 1, page: 1, page_size: 50, items: [arData] } });
    mockPost.mockResolvedValue({ data: { success: true, approval_request: { ...arData, decisions: [] }, version: 2 } });
  });

  it('list hits /approval-requests with status, action_type, page and per_page', async () => {
    await approvalsApi.list({ status: 'pending', actionType: 'case_reopen', page: 2, perPage: 25 });
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/approval-requests?');
    expect(url).toContain('status=pending');
    expect(url).toContain('action_type=case_reopen');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=25');
  });

  it('list defaults page and per_page and omits empty filters', async () => {
    await approvalsApi.list();
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/approval-requests?');
    expect(url).toContain('page=1');
    expect(url).toContain('per_page=50');
    expect(url).not.toContain('status=');
    expect(url).not.toContain('action_type=');
  });

  it('get targets the approval request id', async () => {
    await approvalsApi.get('ar_1');
    expect(mockGet).toHaveBeenCalledWith('/approval-requests/ar_1');
  });

  it('vote posts /vote with decision approved, request id and idempotency headers', async () => {
    await approvalsApi.vote('ar_1', { decision: 'approved' });
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe('/approval-requests/ar_1/vote');
    expect(body).toEqual({ decision: 'approved' });
    expect(cfg.headers['X-Request-ID']).toBeTruthy();
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('vote rejects with rationale', async () => {
    await approvalsApi.vote('ar_1', { decision: 'rejected', rationale: 'Insufficient evidence' });
    const [url, body] = mockPost.mock.calls[0];
    expect(url).toBe('/approval-requests/ar_1/vote');
    expect(body).toEqual({ decision: 'rejected', rationale: 'Insufficient evidence' });
  });

  it('does not call obsolete approve or reject routes', async () => {
    await approvalsApi.list();
    await approvalsApi.get('ar_1');
    await approvalsApi.vote('ar_1', { decision: 'approved' });
    await approvalsApi.vote('ar_1', { decision: 'rejected', rationale: 'no' });
    const allUrls = [...mockGet.mock.calls, ...mockPost.mock.calls].map((c) => c[0]);
    for (const url of allUrls) {
      expect(url).not.toMatch(/\/approve($|\/)/);
      expect(url).not.toMatch(/\/reject($|\/)/);
    }
  });

  it('does not send idempotency headers on GET requests', async () => {
    await approvalsApi.list();
    await approvalsApi.get('ar_1');
    for (const call of mockGet.mock.calls) {
      expect(call.length).toBe(1);
    }
  });
});
