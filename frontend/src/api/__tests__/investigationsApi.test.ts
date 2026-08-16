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

import { investigationsApi } from '../investigationsApi';

const investigation = {
  investigation_id: 'inv_1', title: 'Round-trip transfer', description: 'D',
  scope_id: 'hq_main', status: 'active', priority: 'high', assigned_to: 'analyst_001',
  created_by: 'analyst_001', version: 4, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

describe('investigationsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue({ data: { total: 1, page: 1, page_size: 50, items: [investigation] } });
    mockPost.mockResolvedValue({ data: { success: true } });
    mockPatch.mockResolvedValue({ data: { success: true, investigation, version: 5 } });
  });

  it('listAssigned sends status/priority/page/per_page query params', async () => {
    await investigationsApi.listAssigned({ status: 'active', priority: 'high', page: 2, perPage: 25 });
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/investigations/assigned?');
    expect(url).toContain('status=active');
    expect(url).toContain('priority=high');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=25');
  });

  it('listAssigned defaults page and per_page', async () => {
    await investigationsApi.listAssigned();
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('page=1');
    expect(url).toContain('per_page=50');
  });

  it('listSubmitted calls GET /investigations/submitted with priority and pagination', async () => {
    await investigationsApi.listSubmitted({ priority: 'high', page: 1, perPage: 50 });
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/investigations/submitted?');
    expect(url).toContain('priority=high');
    expect(url).toContain('page=1');
    expect(url).toContain('per_page=50');
  });

  it('get targets the investigation id', async () => {
    await investigationsApi.get('inv_1');
    expect(mockGet).toHaveBeenCalledWith('/investigations/inv_1');
  });

  it('update sends findings fields, conclusion and expected_version with X-Request-ID', async () => {
    await investigationsApi.update('inv_1', {
      findings_text: 'Evidence', findings_refs: [{ type: 'alert', id: 'a1', description: 'source' }],
      conclusion: 'Confirmed', expected_version: 4,
    });
    const [url, body, cfg] = mockPatch.mock.calls[0];
    expect(url).toBe('/investigations/inv_1');
    expect(body).toEqual({
      findings_text: 'Evidence', findings_refs: [{ type: 'alert', id: 'a1', description: 'source' }],
      conclusion: 'Confirmed', expected_version: 4,
    });
    expect(cfg.headers['X-Request-ID']).toBeTruthy();
  });

  it('transition posts target status, version and idempotency headers', async () => {
    await investigationsApi.transition('inv_1', { target_status: 'submitted', expected_version: 4 });
    const [url, body, cfg] = mockPatch.mock.calls[0];
    expect(url).toBe('/investigations/inv_1/transition');
    expect(body).toEqual({ target_status: 'submitted', expected_version: 4 });
    expect(cfg.headers['X-Request-ID']).toBeTruthy();
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('transition includes return_reason when returning', async () => {
    await investigationsApi.transition('inv_1', { target_status: 'returned', return_reason: 'more evidence needed', expected_version: 4 });
    const [, body] = mockPatch.mock.calls[0];
    expect(body).toEqual({ target_status: 'returned', return_reason: 'more evidence needed', expected_version: 4 });
  });

  it('cancel posts reason, version and idempotency headers', async () => {
    await investigationsApi.cancel('inv_1', { cancel_reason: 'duplicate', expected_version: 4 });
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe('/investigations/inv_1/cancel');
    expect(body).toEqual({ cancel_reason: 'duplicate', expected_version: 4 });
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('listComments sends page and per_page', async () => {
    await investigationsApi.listComments('inv_1', 2, 25);
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/investigations/inv_1/comments?');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=25');
  });

  it('createComment posts content and is_internal with idempotency', async () => {
    await investigationsApi.createComment('inv_1', 'note', true);
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe('/investigations/inv_1/comments');
    expect(body).toEqual({ content: 'note', is_internal: true });
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('listTimeline sends page and per_page', async () => {
    await investigationsApi.listTimeline('inv_1', 1, 10);
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/investigations/inv_1/timeline?');
    expect(url).toContain('page=1');
    expect(url).toContain('per_page=10');
  });
});
