// src/components/cases/__tests__/CaseInvestigationTab.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';

const mockAuth = vi.hoisted(() => ({
  useAuth: () => ({
    applicationUser: { user_id: 'compliance_001', role: 'compliance' },
    hasPermission: (p: string) => p === 'investigation:review',
    hasRole: () => false,
  }),
}));

vi.mock('../../../auth/AuthProvider', () => ({ useAuth: mockAuth.useAuth }));

const mocks = vi.hoisted(() => ({
  mockInvGet: vi.fn(),
  mockAttList: vi.fn(),
  mockAttDownload: vi.fn(),
}));

vi.mock('../../../api/investigationsApi', () => ({
  investigationsApi: {
    get: mocks.mockInvGet,
  },
}));

vi.mock('../../../api/attachmentsApi', () => ({
  attachmentsApi: {
    list: mocks.mockAttList,
    download: mocks.mockAttDownload,
  },
}));

import { CaseInvestigationTab } from '../CaseInvestigationTab';
import type { Investigation, InvestigationAttachment } from '../../../types/investigations';

const sampleInv: Investigation = {
  investigation_id: 'inv_1001',
  title: 'Suspicious Structuring Investigation',
  description: 'Executive summary of round-trip transaction activity.',
  alert_id: 'alert_99',
  scope_id: 'hq_main',
  status: 'completed',
  priority: 'high',
  assigned_to: 'analyst_42',
  created_by: 'analyst_42',
  findings_text: 'Detailed analysis reveals 5 transactions structured just below 10k threshold.',
  findings_refs: [{ type: 'transaction', id: 'tx_555', description: 'Structured cash deposit' }],
  conclusion: 'High suspicion of money laundering. Recommend Case escalation.',
  started_at: '2026-08-01T10:00:00Z',
  submitted_at: '2026-08-02T14:00:00Z',
  completed_at: '2026-08-03T09:00:00Z',
  return_reason: null,
  version: 2,
  created_at: '2026-08-01T10:00:00Z',
  updated_at: '2026-08-03T09:00:00Z',
};

const sampleAttachment: InvestigationAttachment = {
  attachment_id: 'att_2001',
  investigation_id: 'inv_1001',
  original_filename: 'bank_statement_august.pdf',
  content_type: 'application/pdf',
  size_bytes: 1468006, // ~1.4 MB
  sha256_hash: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef',
  description: 'Monthly account statement for Customer C',
  uploaded_by: 'analyst_42',
  uploaded_at: '2026-08-02T12:00:00Z',
};

function renderTab(investigationId?: string | null) {
  return render(
    <MemoryRouter>
      <CaseInvestigationTab investigationId={investigationId} />
    </MemoryRouter>
  );
}

describe('CaseInvestigationTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.mockInvGet.mockResolvedValue(sampleInv);
    mocks.mockAttList.mockResolvedValue({ total: 1, items: [sampleAttachment] });
  });

  it('renders graceful empty state when investigationId is null or missing', async () => {
    renderTab(null);
    expect(await screen.findByText('No originating investigation linked to this case.')).toBeInTheDocument();
    expect(mocks.mockInvGet).not.toHaveBeenCalled();
  });

  it('renders full Investigation Package metadata, Executive Summary, Findings and Conclusion', async () => {
    renderTab('inv_1001');

    expect(await screen.findByText('Executive Summary')).toBeInTheDocument();
    expect(screen.getByText('Executive summary of round-trip transaction activity.')).toBeInTheDocument();
    expect(screen.getByText('Detailed analysis reveals 5 transactions structured just below 10k threshold.')).toBeInTheDocument();
    expect(screen.getByText('High suspicion of money laundering. Recommend Case escalation.')).toBeInTheDocument();
    expect(screen.getByText(/transaction:tx_555/)).toBeInTheDocument();
    expect(screen.getAllByText(/analyst_42/i).length).toBeGreaterThanOrEqual(1);
  });

  it('fetches and renders evidence attachments with filename, size, type and uploaded date', async () => {
    renderTab('inv_1001');

    expect(await screen.findByText('bank_statement_august.pdf')).toBeInTheDocument();
    expect(screen.getByText('Monthly account statement for Customer C')).toBeInTheDocument();
    expect(screen.getByText('application/pdf')).toBeInTheDocument();
    expect(screen.getByText('1.4 MB')).toBeInTheDocument();
    expect(mocks.mockAttList).toHaveBeenCalledWith('inv_1001');
  });

  it('calls secure download action when Download button is clicked', async () => {
    mocks.mockAttDownload.mockResolvedValue(undefined);
    renderTab('inv_1001');

    const downloadBtn = await screen.findByRole('button', { name: /Download/i });
    fireEvent.click(downloadBtn);

    await waitFor(() => {
      expect(mocks.mockAttDownload).toHaveBeenCalledWith(
        'inv_1001',
        'att_2001',
        'bank_statement_august.pdf'
      );
    });
  });

  it('does NOT render upload or delete actions (read-only for Compliance)', async () => {
    renderTab('inv_1001');

    await screen.findByText('bank_statement_august.pdf');
    expect(screen.queryByText(/Upload File/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Delete/i })).not.toBeInTheDocument();
  });

  it('renders appropriate empty state when no attachments exist', async () => {
    mocks.mockAttList.mockResolvedValue({ total: 0, items: [] });
    renderTab('inv_1001');

    expect(await screen.findByText('No evidence attachments uploaded for this investigation.')).toBeInTheDocument();
  });

  it('renders safe error message when attachments API fails', async () => {
    mocks.mockAttList.mockRejectedValue(new Error('Network error'));
    renderTab('inv_1001');

    expect(await screen.findByText('Unable to load evidence attachments.')).toBeInTheDocument();
  });

  it('renders originating alert reference link', async () => {
    renderTab('inv_1001');

    expect(await screen.findByText(/Originating alert/i)).toBeInTheDocument();
    expect(screen.getByText('#alert_99…')).toBeInTheDocument();
  });
});
