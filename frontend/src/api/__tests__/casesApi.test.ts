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

import { casesApi } from '../casesApi';

const caseData = {
  case_id: 'case_1', title: 'Round-trip transfer', description: 'D',
  scope_id: 'hq_main', status: 'under_review', priority: 'high', risk_level: 'high',
  assigned_to: 'compliance_001', created_by: 'analyst_001',
  version: 4, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

describe('casesApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue({ data: { total: 1, page: 1, page_size: 50, items: [caseData] } });
    mockPost.mockResolvedValue({ data: { success: true } });
    mockPatch.mockResolvedValue({ data: { success: true, case: caseData, version: 5 } });
  });

  it('listAssigned sends status/priority/page/per_page query params', async () => {
    await casesApi.listAssigned({ status: 'under_review', priority: 'high', page: 2, perPage: 25 });
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/cases/assigned?');
    expect(url).toContain('status=under_review');
    expect(url).toContain('priority=high');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=25');
  });

  it('listAssigned defaults page and per_page', async () => {
    await casesApi.listAssigned();
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('page=1');
    expect(url).toContain('per_page=50');
  });

  it('get targets the case id', async () => {
    await casesApi.get('case_1');
    expect(mockGet).toHaveBeenCalledWith('/cases/case_1');
  });

  it('assign patches assigned_to, reason and expected_version with idempotency', async () => {
    await casesApi.assign('case_1', { assigned_to: 'compliance_007', reason: 'workload', expected_version: 4 });
    const [url, body, cfg] = mockPatch.mock.calls[0];
    expect(url).toBe('/cases/case_1/assign');
    expect(body).toEqual({ assigned_to: 'compliance_007', reason: 'workload', expected_version: 4 });
    expect(cfg.headers['X-Request-ID']).toBeTruthy();
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('transition posts target status, optional resolution and version', async () => {
    await casesApi.transition('case_1', { target_status: 'decision_pending', expected_version: 4 });
    const [url, body, cfg] = mockPatch.mock.calls[0];
    expect(url).toBe('/cases/case_1/transition');
    expect(body).toEqual({ target_status: 'decision_pending', expected_version: 4 });
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('transition includes resolution when resolving', async () => {
    await casesApi.transition('case_1', { target_status: 'resolved', resolution: 'case closed out', expected_version: 4 });
    const [, body] = mockPatch.mock.calls[0];
    expect(body).toEqual({ target_status: 'resolved', resolution: 'case closed out', expected_version: 4 });
  });

  it('recordDecision posts decision_type, rationale and approval id when present', async () => {
    await casesApi.recordDecision('case_1', {
      decision_type: 'report_to_authority_recommended', rationale: 'serious breach', approval_request_id: 'ap_1', expected_version: 4,
    });
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe('/cases/case_1/decisions');
    expect(body).toEqual({
      decision_type: 'report_to_authority_recommended', rationale: 'serious breach', approval_request_id: 'ap_1', expected_version: 4,
    });
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('listDecisions hits the decisions endpoint', async () => {
    mockGet.mockResolvedValue({ data: { data: [] } });
    await casesApi.listDecisions('case_1');
    expect(mockGet).toHaveBeenCalledWith('/cases/case_1/decisions', expect.objectContaining({ headers: { 'X-Request-ID': expect.anything() } }));
  });

  it('listInformationRequests sends page and per_page', async () => {
    await casesApi.listInformationRequests('case_1', 2, 25);
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/cases/case_1/information-requests?');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=25');
  });

  it('createInformationRequest posts assigned_to, question, due_date and expected_case_version', async () => {
    await casesApi.createInformationRequest('case_1', {
      assigned_to: 'analyst_002', question: 'Please provide details', due_date: '2026-02-01', expected_case_version: 4,
    });
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe('/cases/case_1/information-requests');
    expect(body).toEqual({
      assigned_to: 'analyst_002', question: 'Please provide details', due_date: '2026-02-01', expected_case_version: 4,
    });
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });

  it('acceptInformationRequest patches the accept endpoint', async () => {
    await casesApi.acceptInformationRequest('ir_1', { acceptance_note: 'thanks', expected_version: 2 });
    const [url, body] = mockPatch.mock.calls[0];
    expect(url).toBe('/information-requests/ir_1/accept');
    expect(body).toEqual({ acceptance_note: 'thanks', expected_version: 2 });
  });

  it('returnInformationRequest patches the return endpoint with reason', async () => {
    await casesApi.returnInformationRequest('ir_1', { return_reason: 'incomplete', expected_version: 2 });
    const [url, body] = mockPatch.mock.calls[0];
    expect(url).toBe('/information-requests/ir_1/return');
    expect(body).toEqual({ return_reason: 'incomplete', expected_version: 2 });
  });

  it('listComments and listTimeline target the case entity segment', async () => {
    await casesApi.listComments('case_1', 1, 50);
    expect(mockGet.mock.calls[0][0]).toContain('/cases/case_1/comments?');
    await casesApi.listTimeline('case_1', 1, 50);
    expect(mockGet.mock.calls[1][0]).toContain('/cases/case_1/timeline?');
  });

  it('createComment posts content and is_internal', async () => {
    await casesApi.createComment('case_1', 'note', true);
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe('/cases/case_1/comments');
    expect(body).toEqual({ content: 'note', is_internal: true });
    expect(cfg.headers['X-Idempotency-Key']).toBeTruthy();
  });
});
