// src/components/investigations/EvidenceUploadPanel.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { Paperclip, Upload, Download, Trash2, FileText, AlertCircle, Loader2 } from 'lucide-react';
import { attachmentsApi } from '../../api/attachmentsApi';
import { formatDateTime } from '../../utils/formatters';
import type { InvestigationAttachment } from '../../types/investigations';

interface Props {
  investigationId: string;
  editable: boolean;
  canDownload: boolean;
}

const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.csv', '.xlsx', '.txt'];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function EvidenceUploadPanel({ investigationId, editable, canDownload }: Props) {
  const [attachments, setAttachments] = useState<InvestigationAttachment[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);

  const fetchAttachments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await attachmentsApi.list(investigationId);
      setAttachments(res.items);
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { message?: string } } }).response?.data?.message
        : 'Failed to load evidence attachments.';
      setError(msg || 'Failed to load evidence attachments.');
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  useEffect(() => {
    fetchAttachments();
  }, [fetchAttachments]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const file = e.target.files?.[0];
    if (!file) {
      setSelectedFile(null);
      return;
    }

    const ext = `.${file.name.split('.').pop()?.toLowerCase()}`;
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Invalid file type "${ext}". Allowed types: ${ALLOWED_EXTENSIONS.join(', ')}`);
      setSelectedFile(null);
      e.target.value = '';
      return;
    }

    if (file.size > MAX_SIZE_BYTES) {
      setError(`File size (${formatBytes(file.size)}) exceeds maximum limit of 10 MB.`);
      setSelectedFile(null);
      e.target.value = '';
      return;
    }

    setSelectedFile(file);
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || uploading) return;

    setUploading(true);
    setError(null);
    try {
      await attachmentsApi.upload(investigationId, selectedFile, description);
      setSelectedFile(null);
      setDescription('');
      // Reset file input element
      const fileInput = document.getElementById('evidence-file-input') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
      await fetchAttachments();
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { message?: string } } }).response?.data?.message
        : 'Failed to upload evidence.';
      setError(msg || 'Failed to upload evidence.');
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (att: InvestigationAttachment) => {
    try {
      await attachmentsApi.download(investigationId, att.attachment_id, att.original_filename);
    } catch {
      setError(`Failed to download ${att.original_filename}.`);
    }
  };

  const handleDelete = async (att: InvestigationAttachment) => {
    if (!window.confirm(`Remove evidence file "${att.original_filename}"?`)) return;
    setDeletingId(att.attachment_id);
    setError(null);
    try {
      await attachmentsApi.delete(investigationId, att.attachment_id);
      await fetchAttachments();
    } catch {
      setError(`Failed to delete ${att.original_filename}.`);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="rounded-2xl border p-5 space-y-4"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Paperclip size={16} style={{ color: 'var(--accent-blue)' }} />
          <h3 className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
            Supporting Evidence ({attachments.length})
          </h3>
        </div>
        {!editable && (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono border"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
            Read-only evidence
          </span>
        )}
      </div>

      {/* Error alert */}
      {error && (
        <div role="alert" className="flex items-center gap-2 px-3 py-2 rounded-lg border text-xs"
          style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
          <AlertCircle size={14} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Upload Form (Editable Analyst view only) */}
      {editable && (
        <form onSubmit={handleUpload} className="p-4 rounded-xl border space-y-3"
          style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
          <p className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>
            Add Evidence File (PDF, PNG, JPEG, CSV, XLSX, TXT — max 10MB)
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="evidence-file-input" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                Select File *
              </label>
              <input
                id="evidence-file-input"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.csv,.xlsx,.txt"
                onChange={handleFileSelect}
                disabled={uploading}
                className="w-full text-xs file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[var(--accent-blue)] file:text-[var(--text-primary)] hover:file:brightness-90 cursor-pointer"
                style={{ color: 'var(--text-secondary)' }}
              />
            </div>
            <div>
              <label htmlFor="evidence-desc-input" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                Description (Optional)
              </label>
              <input
                id="evidence-desc-input"
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Bank statement excerpt..."
                disabled={uploading}
                className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)]"
                style={{ background: 'var(--bg-primary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-1">
            {selectedFile ? (
              <p className="text-[10px] font-mono" style={{ color: 'var(--accent-blue)' }}>
                Selected: {selectedFile.name} ({formatBytes(selectedFile.size)})
              </p>
            ) : <span />}

            <button
              type="submit"
              disabled={!selectedFile || uploading}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
              style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
            >
              {uploading ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
              {uploading ? 'Uploading…' : 'Upload Evidence'}
            </button>
          </div>
        </form>
      )}

      {/* Attachment List */}
      {loading ? (
        <div className="h-16 border rounded-xl animate-pulse" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }} />
      ) : attachments.length === 0 ? (
        <div className="p-6 text-center border rounded-xl" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
          <FileText size={20} className="mx-auto mb-1 opacity-40" style={{ color: 'var(--text-muted)' }} />
          <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
            No evidence attachments uploaded yet.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {attachments.map((att) => (
            <div
              key={att.attachment_id}
              className="flex items-center justify-between p-3 rounded-xl border transition-all hover:brightness-95"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}
            >
              <div className="flex items-center gap-3 min-w-0 pr-2">
                <FileText size={16} className="shrink-0" style={{ color: 'var(--accent-blue)' }} />
                <div className="min-w-0">
                  <p className="text-xs font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                    {att.original_filename}
                  </p>
                  <p className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
                    {formatBytes(att.size_bytes)} · {att.content_type} · uploaded by {att.uploaded_by} on {formatDateTime(att.uploaded_at)}
                  </p>
                  {att.description && (
                    <p className="text-[11px] italic mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                      "{att.description}"
                    </p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                {canDownload && (
                  <button
                    onClick={() => handleDownload(att)}
                    title="Download evidence file"
                    className="p-1.5 rounded-lg border transition-all hover:brightness-90"
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--accent-blue)' }}
                  >
                    <Download size={14} />
                  </button>
                )}
                {editable && (
                  <button
                    onClick={() => handleDelete(att)}
                    disabled={deletingId === att.attachment_id}
                    title="Remove evidence file"
                    className="p-1.5 rounded-lg border transition-all hover:brightness-90 disabled:opacity-50"
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--accent-red)' }}
                  >
                    {deletingId === att.attachment_id ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Trash2 size={14} />
                    )}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
