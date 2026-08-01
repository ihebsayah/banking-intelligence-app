import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';

const mockAuth = vi.hoisted(() => {
  const overrides: { hasPermission?: () => boolean; user?: string } = {};
  return {
    useAuth: () => ({
      applicationUser: { user_id: overrides.user ?? 'analyst_001', role: 'analyst' },
      hasPermission: overrides.hasPermission ?? (() => true),
      hasRole: () => false,
    }),
    setOverrides: (o: { hasPermission?: () => boolean; user?: string }) => {
      overrides.hasPermission = o.hasPermission;
      overrides.user = o.user;
    },
  };
});

vi.mock('../../../auth/AuthProvider', () => ({ useAuth: mockAuth.useAuth }));

const { mockAcknowledge, mockRespond } = vi.hoisted(() => ({
  mockAcknowledge: vi.fn(),
  mockRespond: vi.fn(),
}));

vi.mock('../../../api/informationRequestsApi', () => ({
  informationRequestsApi: {
    acknowledge: mockAcknowledge,
    respond: mockRespond,
  },
}));

import { IRResponseDialog } from '../IRResponseDialog';
import type { InformationRequest } from '../../../types/cases';

const base: InformationRequest = {
  ir_id: 'ir_1', case_id: 'case_1', created_by: 'compliance_001', assigned_to: 'analyst_001',
  question: 'Explain the source of funds', status: 'open', due_date: '2026-12-01',
  version: 1, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

function renderDialog(ir: InformationRequest | null, overrides: { hasPermission?: () => boolean; user?: string } = {}) {
  mockAuth.setOverrides(overrides);
  const onSuccess = vi.fn();
  const onConflict = vi.fn();
  const onClose = vi.fn();
  const view = render(
    <MemoryRouter>
      <IRResponseDialog
        open={ir !== null}
        ir={ir}
        onClose={onClose}
        onSuccess={onSuccess}
        onConflict={onConflict}
      />
    </MemoryRouter>
  );
  return { view, onSuccess, onConflict, onClose };
}

describe('IRResponseDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAcknowledge.mockResolvedValue({ success: true, information_request: { ...base, status: 'acknowledged', version: 2 }, version: 2 });
    mockRespond.mockResolvedValue({ success: true, information_request: { ...base, status: 'responded', version: 2 }, version: 2 });
  });

  it('shows Acknowledge and a disabled textarea for an open request', () => {
    renderDialog(base);
    expect(screen.getByRole('button', { name: 'Acknowledge' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Submit Response' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Your response')).toBeDisabled();
  });

  it('acknowledges with the expected version and keeps the dialog open', async () => {
    const { onSuccess } = renderDialog(base);
    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }));
    await waitFor(() => expect(mockAcknowledge).toHaveBeenCalledWith('ir_1', { expected_version: 1 }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(expect.objectContaining({ status: 'acknowledged' }), false));
  });

  it('shows the returned banner with the return reason', () => {
    const returned: InformationRequest = { ...base, status: 'returned', version: 3, response_text: 'Old response', return_reason: 'Missing documents', returned_by: 'compliance_001', returned_at: '2026-01-05T00:00:00Z' };
    renderDialog(returned);
    expect(screen.getByText('Returned — reason: Missing documents')).toBeInTheDocument();
  });

  it('enables editing and offers Re-acknowledge for a returned request, preserving the prior response', () => {
    const returned: InformationRequest = { ...base, status: 'returned', version: 3, response_text: 'Old response', return_reason: 'Missing documents' };
    renderDialog(returned);
    const textarea = screen.getByLabelText('Your response');
    expect(textarea).toBeEnabled();
    expect(textarea).toHaveValue('Old response');
    expect(screen.getByRole('button', { name: 'Re-acknowledge' })).toBeInTheDocument();
  });

  it('submits a response with text and expected version, then closes', async () => {
    const acknowledged: InformationRequest = { ...base, status: 'acknowledged', version: 2 };
    const { onSuccess } = renderDialog(acknowledged);
    fireEvent.change(screen.getByLabelText('Your response'), { target: { value: 'Source confirmed.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Response' }));
    await waitFor(() => expect(mockRespond).toHaveBeenCalledWith('ir_1', { response_text: 'Source confirmed.', expected_version: 2 }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(expect.objectContaining({ status: 'responded' }), true));
  });

  it('does not submit an empty response', () => {
    const acknowledged: InformationRequest = { ...base, status: 'acknowledged', version: 2 };
    renderDialog(acknowledged);
    expect(screen.getByRole('button', { name: 'Submit Response' })).toBeDisabled();
  });

  it('is read-only when responded, accepted or cancelled', () => {
    for (const status of ['responded', 'accepted', 'cancelled']) {
      renderDialog({ ...base, status: status as InformationRequest['status'], version: 4 });
      expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Submit Response' })).not.toBeInTheDocument();
      expect(screen.getByLabelText('Your response')).toBeDisabled();
    }
  });

  it('hides actions when the user lacks respond permission', () => {
    renderDialog(base, { hasPermission: () => false });
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Your response')).toBeDisabled();
  });

  it('hides actions for a non-assignee even with permission', () => {
    renderDialog(base, { user: 'analyst_999' });
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Your response')).toBeDisabled();
  });

  it('disables submit while a response is in flight', async () => {
    const acknowledged: InformationRequest = { ...base, status: 'acknowledged', version: 2 };
    let resolveRespond: (v: unknown) => void;
    mockRespond.mockReturnValue(new Promise((r) => { resolveRespond = r; }));
    const { onSuccess } = renderDialog(acknowledged);
    fireEvent.change(screen.getByLabelText('Your response'), { target: { value: 'Source confirmed.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Response' }));
    expect(mockRespond).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: /Submitting…/ })).toBeDisabled();
    resolveRespond!({ success: true, information_request: { ...acknowledged, status: 'responded' }, version: 3 });
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(expect.objectContaining({ status: 'responded' }), true));
  });

  it('shows a conflict banner, preserves the draft and does not auto-retry', async () => {
    const acknowledged: InformationRequest = { ...base, status: 'acknowledged', version: 2 };
    const { onConflict } = renderDialog(acknowledged);
    mockRespond.mockRejectedValue({ response: { status: 409, data: { error: 'VERSION_CONFLICT' } } });
    const textarea = screen.getByLabelText('Your response');
    fireEvent.change(textarea, { target: { value: 'My draft answer' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Response' }));
    await waitFor(() => expect(onConflict).toHaveBeenCalled());
    expect(screen.getByRole('alert')).toHaveTextContent(/updated by another user/i);
    expect(screen.getByLabelText('Your response')).toHaveValue('My draft answer');
    await new Promise((r) => setTimeout(r, 0));
    expect(mockRespond).toHaveBeenCalledTimes(1);
  });
});
