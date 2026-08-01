import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const { mockGet, mockAcknowledge, mockDismiss, mockEscalate, mockInvestigate, mockCreateApproval } =
  vi.hoisted(() => ({
    mockGet: vi.fn(),
    mockAcknowledge: vi.fn(),
    mockDismiss: vi.fn(),
    mockEscalate: vi.fn(),
    mockInvestigate: vi.fn(),
    mockCreateApproval: vi.fn(),
  }));

vi.mock('../../../auth/AuthProvider', () => {
  const permissions: string[] = [
    'alert:acknowledge', 'alert:investigate', 'alert:dismiss', 'alert:transition', 'approval:request',
  ];
  return {
    useAuth: () => ({
      applicationUser: { user_id: 'analyst_001', role: 'analyst' },
      hasPermission: (p: string) => permissions.includes(p),
      hasRole: (r: string) => r === 'analyst',
      permissions,
    }),
  };
});

vi.mock('../../../api/alertsApi', () => ({
  alertsApi: {
    get: mockGet,
    acknowledge: mockAcknowledge,
    dismiss: mockDismiss,
    escalate: mockEscalate,
    investigate: mockInvestigate,
    assign: vi.fn(),
  },
}));

vi.mock('../../../api/approvalsApi', () => ({
  approvalsApi: {
    create: mockCreateApproval,
    get: vi.fn(),
  },
}));

import { AlertDetailPage } from '../AlertDetailPage';
import { useParams } from 'react-router-dom';

function CaseMarker() {
  const { caseId } = useParams();
  return <div>case-detail-{caseId}</div>;
}

function InvMarker() {
  const { invId } = useParams();
  return <div>inv-detail-{invId}</div>;
}

function makeAlert(overrides: Record<string, unknown> = {}) {
  return {
    alert_id: 'a1', alert_type: 'transaction_anomaly', severity: 'high', title: 'Suspicious transfer',
    description: 'Large round-trip transaction', source_rule_type: 'ml_anomaly', source_rule_id: 'r1',
    related_entity_type: 'customer', related_entity_id: 'c_9', scope_id: 'hq_main',
    status: 'assigned', assigned_to: 'analyst_001', dismissed_reason: null, dismissed_at: null,
    dismissed_by: null, resolved_at: null, resolved_by: null,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', version: 3,
    ...overrides,
  };
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/workbench/alerts/a1']}>
      <Routes>
        <Route path="/workbench/alerts/:alertId" element={<AlertDetailPage />} />
        <Route path="/workbench/cases/:caseId" element={<CaseMarker />} />
        <Route path="/workbench/investigations/:invId" element={<InvMarker />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('AlertDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue(makeAlert());
    mockAcknowledge.mockResolvedValue({ success: true });
    mockDismiss.mockResolvedValue({ success: true });
  });

  it('renders alert fields, badges and version', async () => {
    renderDetail();
    expect(await screen.findByText('Suspicious transfer')).toBeInTheDocument();
    expect(screen.getByText('Large round-trip transaction')).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getByText('v3')).toBeInTheDocument();
    expect(screen.getByText('hq_main')).toBeInTheDocument();
  });

  it('acknowledges an assigned alert and refetches', async () => {
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Acknowledge/i }));
    await waitFor(() => expect(mockAcknowledge).toHaveBeenCalledWith('a1', 3));
    await waitFor(() => expect(mockGet.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('shows a conflict banner on 409 and refetches', async () => {
    mockAcknowledge.mockRejectedValue({
      response: { status: 409, data: { error: 'VERSION_CONFLICT', message: 'Resource was modified by another user. Refresh and retry.' } },
    });
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Acknowledge/i }));
    expect(await screen.findByText('Alert was updated — refresh and try again.')).toBeInTheDocument();
    await waitFor(() => expect(mockGet.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('dismiss requires four-eyes approval for high severity and submits with approval_request_id', async () => {
    mockGet.mockResolvedValue(makeAlert({ status: 'acknowledged' }));
    mockCreateApproval.mockResolvedValue({
      success: true,
      approval_request: {
        approval_request_id: 'apr_1', action_type: 'alert_dismissal_critical_high', entity_type: 'alert',
        entity_id: 'a1', requested_by: 'analyst_001', rationale: 'false positive',
        required_approvals: 1, approval_count: 1, status: 'approved',
        expires_at: '2026-02-01T00:00:00Z', executed_at: null,
        version: 2, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
      },
      version: 2,
    });

    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Dismiss$/i }));
    expect(await screen.findByText('Four-eyes approval required')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Why is this alert being dismissed?'), {
      target: { value: 'false positive' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Request Approval/i }));
    expect(await screen.findByText('approved')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Dismiss Alert$/i }));
    await waitFor(() =>
      expect(mockDismiss).toHaveBeenCalledWith('a1', {
        dismissed_reason: 'false positive',
        expected_version: 3,
        approval_request_id: 'apr_1',
      }),
    );
  });

  it('escalates an under-investigation alert and navigates to the created case', async () => {
    mockGet.mockResolvedValue(makeAlert({ status: 'under_investigation' }));
    mockEscalate.mockResolvedValue({
      success: true, alert: makeAlert({ status: 'under_investigation' }), case_id: 'case_9', version: 4,
    });

    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: /Escalate/i }));
    fireEvent.change(screen.getByPlaceholderText('Summary of the compliance concern'), {
      target: { value: 'Round-trip case' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Escalate to Case/i }));

    await waitFor(() => expect(mockEscalate).toHaveBeenCalledWith('a1', {
      title: 'Round-trip case',
      description: undefined,
      priority: 'medium',
      expected_version: 3,
    }));
    expect(await screen.findByText('case-detail-case_9')).toBeInTheDocument();
  });
});
