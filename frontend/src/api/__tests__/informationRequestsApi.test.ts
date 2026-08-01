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

import { informationRequestsApi } from '../informationRequestsApi';

const irData = {
  ir_id: 'ir_1', case_id: 'case_1', created_by: 'compliance_001', assigned_to: 'analyst_001',
  question: 'Explain the source of funds', status: 'acknowledged', due_date: '2026-12-01',
  version: 2, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

describe('informationRequestsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue({ data: { total: 1, page: 1, page_size: 50, items: [irData] } });
    mockPatch.mockResolvedValue({ data: { success: true, information_request: irData, version: 3 } });
  });

  it('listAssigned sends status/page/per_page query params', async () => {
    await informationRequestsApi.listAssigned({ status: 'returned', page: 2, perPage: 25 });
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/information-requests/assigned?');
    expect(url).toContain('status=returned');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=25');
  });

  it('listAssigned defaults page and per_page', async () => {
    await informationRequestsApi.listAssigned();
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('page=1');
    expect(url).toContain('per_page=50');
  });

  it('get targets the information request id', async () => {
    await informationRequestsApi.get('ir_1');
    expect(mockGet).toHaveBeenCalledWith('/information-requests/ir_1');
  });

  it('acknowledge patches /acknowledge with expected_version and idempotency headers', async () => {
    await informationRequestsApi.acknowledge('ir_1', { expected_version: 2 });
    const [url, body, cfg] = mockPatch.mock.calls[0];
    expect(url).toBe('/information-requests/ir_1/acknowledge');
    expect(body).toEqual({ expected_version: 2 });
    expect(cfg.headers['X-Request-ID']).toBeTruthy();
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('respond patches /respond with response_text and expected_version', async () => {
    await informationRequestsApi.respond('ir_1', { response_text: 'Source confirmed.', expected_version: 2 });
    const [url, body, cfg] = mockPatch.mock.calls[0];
    expect(url).toBe('/information-requests/ir_1/respond');
    expect(body).toEqual({ response_text: 'Source confirmed.', expected_version: 2 });
    expect(cfg.headers['X-Request-ID']).toBeTruthy();
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('never calls obsolete submit or close routes', async () => {
    await informationRequestsApi.listAssigned();
    await informationRequestsApi.get('ir_1');
    await informationRequestsApi.acknowledge('ir_1', { expected_version: 2 });
    await informationRequestsApi.respond('ir_1', { response_text: 'ok', expected_version: 2 });
    const allUrls = [...mockGet.mock.calls, ...mockPatch.mock.calls].map((c) => c[0]);
    for (const url of allUrls) {
      expect(url).not.toMatch(/\/submit($|\/)/);
      expect(url).not.toMatch(/\/close($|\/)/);
    }
  });
});
