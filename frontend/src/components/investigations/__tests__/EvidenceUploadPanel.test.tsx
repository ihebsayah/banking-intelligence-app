// src/components/investigations/__tests__/EvidenceUploadPanel.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { EvidenceUploadPanel } from '../EvidenceUploadPanel';
import type { InvestigationAttachment } from '../../../types/investigations';

const { mockList, mockUpload, mockDownload, mockDelete } = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockUpload: vi.fn(),
  mockDownload: vi.fn(),
  mockDelete: vi.fn(),
}));

vi.mock('../../../api/attachmentsApi', () => ({
  attachmentsApi: {
    list: mockList,
    upload: mockUpload,
    download: mockDownload,
    delete: mockDelete,
  },
}));

const mockAtt: InvestigationAttachment = {
  attachment_id: 'att_1',
  investigation_id: 'inv_123',
  original_filename: 'bank_statement.pdf',
  content_type: 'application/pdf',
  size_bytes: 1048576, // 1 MB
  sha256_hash: '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
  description: 'Monthly statement excerpt',
  uploaded_by: 'analyst1',
  uploaded_at: '2026-08-16T12:00:00Z',
};

describe('EvidenceUploadPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({ total: 1, items: [mockAtt] });
    mockUpload.mockResolvedValue(mockAtt);
    mockDownload.mockResolvedValue(undefined);
    mockDelete.mockResolvedValue({ success: true });
  });

  it('renders evidence list and metadata', async () => {
    render(<EvidenceUploadPanel investigationId="inv_123" editable={false} canDownload={true} />);
    expect(await screen.findByText('bank_statement.pdf')).toBeInTheDocument();
    expect(screen.getByText(/1\.0 MB/)).toBeInTheDocument();
    expect(screen.getByText(/"Monthly statement excerpt"/)).toBeInTheDocument();
  });

  it('hides upload form when editable is false', async () => {
    render(<EvidenceUploadPanel investigationId="inv_123" editable={false} canDownload={true} />);
    await screen.findByText('bank_statement.pdf');
    expect(screen.queryByText(/Add Evidence File/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Read-only evidence/i)).toBeInTheDocument();
  });

  it('shows upload form when editable is true', async () => {
    render(<EvidenceUploadPanel investigationId="inv_123" editable={true} canDownload={true} />);
    await screen.findByText('bank_statement.pdf');
    expect(screen.getByText(/Add Evidence File/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Upload Evidence/i })).toBeInTheDocument();
  });

  it('client-side rejects file with invalid extension .exe', async () => {
    render(<EvidenceUploadPanel investigationId="inv_123" editable={true} canDownload={true} />);
    await screen.findByText('bank_statement.pdf');

    const fileInput = screen.getByLabelText(/Select File/i) as HTMLInputElement;
    const file = new File(['dummy executable binary'], 'malware.exe', { type: 'application/x-msdownload' });

    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(await screen.findByRole('alert')).toHaveTextContent(/Invalid file type "\.exe"/i);
    expect(mockUpload).not.toHaveBeenCalled();
  });

  it('client-side rejects oversized file > 10MB', async () => {
    render(<EvidenceUploadPanel investigationId="inv_123" editable={true} canDownload={true} />);
    await screen.findByText('bank_statement.pdf');

    const fileInput = screen.getByLabelText(/Select File/i) as HTMLInputElement;
    // Create dummy 11MB file representation
    const bigFile = new File(['x'], 'large_document.pdf', { type: 'application/pdf' });
    Object.defineProperty(bigFile, 'size', { value: 11 * 1024 * 1024 });

    fireEvent.change(fileInput, { target: { files: [bigFile] } });

    expect(await screen.findByRole('alert')).toHaveTextContent(/exceeds maximum limit of 10 MB/i);
    expect(mockUpload).not.toHaveBeenCalled();
  });

  it('triggers download when download button clicked', async () => {
    render(<EvidenceUploadPanel investigationId="inv_123" editable={false} canDownload={true} />);
    await screen.findByText('bank_statement.pdf');

    const downloadBtn = screen.getByTitle('Download evidence file');
    fireEvent.click(downloadBtn);

    await waitFor(() => expect(mockDownload).toHaveBeenCalledWith('inv_123', 'att_1', 'bank_statement.pdf'));
  });

  it('triggers delete when delete button clicked and confirmed', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<EvidenceUploadPanel investigationId="inv_123" editable={true} canDownload={true} />);
    await screen.findByText('bank_statement.pdf');

    const deleteBtn = screen.getByTitle('Remove evidence file');
    fireEvent.click(deleteBtn);

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith('inv_123', 'att_1'));
  });
});
