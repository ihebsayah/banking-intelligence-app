import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import React from 'react';

const mockAuth = vi.hoisted(() => ({
  useAuth: () => ({
    applicationUser: { user_id: 'compliance_001', role: 'compliance' },
    hasPermission: () => true,
    hasRole: () => false,
  }),
}));

vi.mock('../../../auth/AuthProvider', () => ({ useAuth: mockAuth.useAuth }));

const { mockListForInvestigation, mockListAttachments, mockDownload, mockAccept, mockReturn } = vi.hoisted(() => ({
  mockListForInvestigation: vi.fn(),
  mockListAttachments: vi.fn(),
  mockDownload: vi.fn(),
  mockAccept: vi.fn(),
  mockReturn: vi.fn(),
}));

vi.mock('../../../api/informationRequestsApi', () => ({
  informationRequestsApi: {
    listForInvestigation: mockListForInvestigation,
    listAttachments: mockListAttachments,
    downloadAttachment: mockDownload,
    accept: mockAccept,
    return: mockReturn,
    get: vi.fn(),
    listAssigned: vi.fn(),
    acknowledge: vi.fn(),
    respond: vi.fn(),
    uploadAttachment: vi.fn(),
  },
}));

import { InformationRequestsPanel } from '../InformationRequestsPanel';
import type { InformationRequest } from '../../../types/cases';

const base = {
  case_id: 'case_1',
  created_by: 'compliance_001',
  assigned_to: 'analyst_001',
  due_date: '2026-12-01',
  version: 2,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const responded: InformationRequest = {
  ...base,
  ir_id: 'ir_1',
  question: 'Explain the source of funds',
  status: 'responded',
  response_text: 'Funds came from the sale of shares.',
  responded_at: '2026-02-01T00:00:00Z',
};

const attachment = {
  attachment_id: 'att_1',
  ir_id: 'ir_1',
  original_filename: 'statement.pdf',
  size_bytes: 2048,
  content_type: 'application/pdf',
  uploaded_by: 'analyst_001',
  uploaded_at: '2026-02-01T00:00:00Z',
};

function renderPanel() {
  return render(
    <InformationRequestsPanel investigationId="inv_1" refreshKey={1} onConflict={() => {}} />
  );
}

async function openDetail() {
  fireEvent.click(await screen.findByText('Explain the source of funds'));
  return within(await screen.findByRole('dialog'));
}

describe('InformationRequestsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListForInvestigation.mockResolvedValue({ total: 1, page: 1, page_size: 50, items: [responded] });
    mockListAttachments.mockResolvedValue({ total: 1, items: [attachment] });
    mockAccept.mockResolvedValue({
      success: true,
      information_request: { ...responded, status: 'accepted', version: 3 },
      version: 3,
    });
    mockReturn.mockResolvedValue({
      success: true,
      information_request: { ...responded, status: 'returned', version: 3 },
      version: 3,
    });
  });

  it('lists information requests for the investigation', async () => {
    renderPanel();
    expect(await screen.findByText('Explain the source of funds')).toBeInTheDocument();
    expect(mockListForInvestigation).toHaveBeenCalledWith('inv_1', { perPage: 50 });
    expect(screen.getByText('responded')).toBeInTheDocument();
  });

  it('opens an IR detail dialog with the response and attachment', async () => {
    renderPanel();
    const dialog = await openDetail();
    expect(dialog.getByText('Funds came from the sale of shares.')).toBeInTheDocument();
    await waitFor(() => expect(mockListAttachments).toHaveBeenCalledWith('ir_1'));
    expect(await dialog.findByText('statement.pdf')).toBeInTheDocument();
    expect(dialog.getByText(/2\.0 KB/)).toBeInTheDocument();
  });

  it('downloads an attachment from the detail dialog', async () => {
    renderPanel();
    const dialog = await openDetail();
    fireEvent.click(await dialog.findByRole('button', { name: 'Download statement.pdf' }));
    expect(mockDownload).toHaveBeenCalledWith('ir_1', 'att_1', 'statement.pdf');
  });

  it('accepts a responded request from the detail dialog', async () => {
    renderPanel();
    const dialog = await openDetail();
    fireEvent.click(dialog.getByRole('button', { name: 'Accept Response' }));
    fireEvent.click(dialog.getByRole('button', { name: 'Confirm Accept' }));
    await waitFor(() => expect(mockAccept).toHaveBeenCalledWith('ir_1', { expected_version: 2 }));
    mockAccept.mockResolvedValueOnce({
      success: true,
      information_request: { ...responded, status: 'accepted', version: 3 },
      version: 3,
    });
    await waitFor(() => expect(dialog.getByText('accepted')).toBeInTheDocument());
  });

  it('requires a reason before returning a responded request', async () => {
    renderPanel();
    const dialog = await openDetail();
    fireEvent.click(dialog.getByRole('button', { name: 'Return Response' }));
    const confirm = dialog.getByRole('button', { name: 'Return for Revision' });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(dialog.getByLabelText(/Return reason/), { target: { value: 'Please include the ledger excerpt' } });
    expect((confirm as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(confirm);
    await waitFor(() => expect(mockReturn).toHaveBeenCalledWith('ir_1', {
      return_reason: 'Please include the ledger excerpt',
      expected_version: 2,
    }));
  });

  it('shows an empty state when the investigation has no requests', async () => {
    mockListForInvestigation.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] });
    renderPanel();
    expect(await screen.findByText('No information requests')).toBeInTheDocument();
  });

  it('surfaces a fetch error', async () => {
    mockListForInvestigation.mockRejectedValue(new Error('boom'));
    renderPanel();
    expect(await screen.findByText('boom')).toBeInTheDocument();
  });
});