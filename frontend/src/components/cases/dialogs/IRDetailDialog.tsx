// src/components/cases/dialogs/IRDetailDialog.tsx
import React, { useEffect, useState } from 'react';
import { Download, Paperclip } from 'lucide-react';
import { Modal } from '../../ui/Modal';
import { StatusBadge } from '../../ui/StatusBadge';
import { informationRequestsApi } from '../../../api/informationRequestsApi';
import { parseCaseError } from '../caseErrors';
import { useAuth } from '../../../auth/AuthProvider';
import { PERMISSIONS } from '../../../lib/permissions';
import { formatDateTime } from '../../../utils/formatters';
import type { InformationRequest, InformationRequestAttachment } from '../../../types/cases';

const irStatusVariant: Record<string, 'blue' | 'green' | 'yellow' | 'purple' | 'gray' | 'red'> = {
  open: 'blue',
  acknowledged: 'purple',
  responded: 'yellow',
  accepted: 'green',
  returned: 'yellow',
  cancelled: 'gray',
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
  open: boolean;
  ir: InformationRequest | null;
  onClose: () => void;
  onMutated: () => void;
  onConflict: () => void;
}

export function IRDetailDialog({ open, ir, onClose, onMutated, onConflict }: Props) {
  const { hasPermission } = useAuth();
  const canAccept = hasPermission(PERMISSIONS.INFO_REQUEST_ACCEPT);
  const canReturn = hasPermission(PERMISSIONS.INFO_REQUEST_RETURN);

  const [current, setCurrent] = useState<InformationRequest | null>(ir);
  const [attachments, setAttachments] = useState<InformationRequestAttachment[]>([]);
  const [attachmentsLoading, setAttachmentsLoading] = useState(false);
  const [action, setAction] = useState<'accept' | 'return' | null>(null);
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !ir) return;
    setCurrent(ir);
    setAttachments([]);
    setAction(null);
    setNote('');
    setError(null);
    setAttachmentsLoading(true);
    informationRequestsApi.listAttachments(ir.ir_id)
      .then((res) => setAttachments(res.items))
      .catch(() => setAttachments([]))
      .finally(() => setAttachmentsLoading(false));
  }, [open, ir]);

  if (!current) return null;

  const isReturn = action === 'return';

  const handleDownload = async (att: InformationRequestAttachment) => {
    try {
      await informationRequestsApi.downloadAttachment(current.ir_id, att.attachment_id, att.original_filename);
    } catch (err) {
      setError(parseCaseError(err).message);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!current || submitting) return;
    if (isReturn && !note.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      if (isReturn) {
        const res = await informationRequestsApi.return(current.ir_id, {
          return_reason: note.trim(),
          expected_version: current.version,
        });
        setCurrent(res.information_request);
      } else {
        const res = await informationRequestsApi.accept(current.ir_id, {
          ...(note.trim() ? { acceptance_note: note.trim() } : {}),
          expected_version: current.version,
        });
        setCurrent(res.information_request);
      }
      setNote('');
      setAction(null);
      onMutated();
    } catch (err) {
      const parsed = parseCaseError(err);
      if (parsed.kind === 'conflict') {
        onClose();
        onConflict();
      } else {
        setError(parsed.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title="Information Request"
      onClose={onClose}
      footer={
        action ? (
          <form id="ir-detail-action-form" onSubmit={submit} className="flex items-end justify-end gap-2">
            <button type="button" onClick={() => { setAction(null); setError(null); }}
              className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
              Cancel
            </button>
            <button type="submit" disabled={submitting || (isReturn && !note.trim())}
              className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
              style={{ background: isReturn ? 'rgba(217,119,6,0.9)' : 'var(--accent-green)', color: 'var(--text-primary)' }}>
              {submitting ? 'Submitting…' : isReturn ? 'Return for Revision' : 'Confirm Accept'}
            </button>
          </form>
        ) : (
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Close
          </button>
        )
      }
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wider mb-0.5" style={{ color: 'var(--text-muted)' }}>
              Question
            </p>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{current.question}</p>
          </div>
          <StatusBadge variant={irStatusVariant[current.status] ?? 'gray'}>
            {current.status.replace(/_/g, ' ')}
          </StatusBadge>
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px]" style={{ color: 'var(--text-subtle)' }}>
          <span>assigned <span className="font-mono">{current.assigned_to ?? '—'}</span></span>
          <span>created <span className="font-mono">{current.created_by ?? '—'}</span></span>
          <span>requested {formatDateTime(current.created_at)}</span>
          {current.due_date && <span>due {current.due_date}</span>}
          <span>v{current.version}</span>
        </div>

        {current.response_text && (
          <div className="rounded-lg border px-3 py-2" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
              Response
              {current.responded_at ? ` · ${formatDateTime(current.responded_at)}` : ''}
            </p>
            <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
              {current.response_text}
            </p>
          </div>
        )}

        <div>
          <p className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            <Paperclip size={11} />
            Attached files
          </p>
          {attachmentsLoading ? (
            <div className="h-9 rounded-lg border animate-pulse" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }} />
          ) : attachments.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--text-subtle)' }}>No files attached.</p>
          ) : (
            <ul className="space-y-1">
              {attachments.map((att) => (
                <li key={att.attachment_id}
                  className="flex items-center justify-between gap-2 rounded-lg border px-3 py-1.5"
                  style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                  <span className="font-mono text-[11px] truncate" style={{ color: 'var(--text-primary)' }}>
                    {att.original_filename}
                    <span className="text-[10px]" style={{ color: 'var(--text-subtle)' }}>
                      {' '}· {formatFileSize(att.size_bytes)} · by {att.uploaded_by}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDownload(att)}
                    aria-label={`Download ${att.original_filename}`}
                    className="shrink-0 flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-semibold border transition-all hover:brightness-95"
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--accent-blue)' }}
                  >
                    <Download size={11} />
                    Download
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {current.return_reason && (
          <div className="rounded-lg border px-3 py-2" style={{ background: 'rgba(217,119,6,0.08)', borderColor: 'rgba(217,119,6,0.3)' }}>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-0.5" style={{ color: 'var(--accent-amber)' }}>Returned</p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{current.return_reason}</p>
          </div>
        )}

        {current.status === 'responded' && !action && (canAccept || canReturn) && (
          <div className="flex items-center gap-2">
            {canAccept && (
              <button
                onClick={() => { setAction('accept'); setError(null); }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
              >
                Accept Response
              </button>
            )}
            {canReturn && (
              <button
                onClick={() => { setAction('return'); setError(null); }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                style={{ background: 'rgba(217,119,6,0.9)', color: 'var(--text-primary)' }}
              >
                Return Response
              </button>
            )}
          </div>
        )}

        {action && (
          <div>
            <label htmlFor="ir-detail-note" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
              {isReturn ? 'Return reason *' : 'Acceptance note (optional)'}
            </label>
            <textarea
              id="ir-detail-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder={isReturn ? 'What needs to change?' : 'Optional note…'}
              className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
            />
          </div>
        )}

        {error && (
          <div role="alert" className="px-3 py-2 rounded-lg border text-xs"
            style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
            {error}
          </div>
        )}
      </div>
    </Modal>
  );
}