// src/components/cases/CaseInvestigationTab.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle, CheckCircle2, FileSearch, Undo2, Download, Paperclip,
  Link2, User, Clock, FileText,
} from 'lucide-react';
import { investigationsApi } from '../../api/investigationsApi';
import { attachmentsApi } from '../../api/attachmentsApi';
import { parseInvestigationError } from '../investigations/investigationErrors';
import { ConfirmTransitionDialog } from '../investigations/dialogs/ConfirmTransitionDialog';
import { ReturnInvestigationDialog } from '../investigations/dialogs/ReturnInvestigationDialog';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { InvestigationPriorityBadge, InvestigationStatusBadge } from '../investigations/InvestigationBadges';
import { formatDateTime } from '../../utils/formatters';
import type { Investigation, InvestigationAttachment } from '../../types/investigations';

interface Props {
  investigationId?: string | null;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export function CaseInvestigationTab({ investigationId }: Props) {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canReview = hasPermission(PERMISSIONS.INVESTIGATION_REVIEW);

  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<'approve' | 'return' | null>(null);

  const [attachments, setAttachments] = useState<InvestigationAttachment[]>([]);
  const [attachmentsLoading, setAttachmentsLoading] = useState(false);
  const [attachmentsError, setAttachmentsError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const fetchInvestigation = useCallback(async () => {
    if (!investigationId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await investigationsApi.get(investigationId);
      setInvestigation(data);
    } catch (err) {
      setError(parseInvestigationError(err).message);
      setInvestigation(null);
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  const fetchAttachments = useCallback(async () => {
    if (!investigationId) return;
    setAttachmentsLoading(true);
    setAttachmentsError(null);
    try {
      const res = await attachmentsApi.list(investigationId);
      setAttachments(res.items);
    } catch (err) {
      setAttachmentsError('Unable to load evidence attachments.');
    } finally {
      setAttachmentsLoading(false);
    }
  }, [investigationId]);

  useEffect(() => {
    fetchInvestigation();
    fetchAttachments();
  }, [fetchInvestigation, fetchAttachments]);

  const handleDownload = async (att: InvestigationAttachment) => {
    if (!investigationId) return;
    setDownloadingId(att.attachment_id);
    try {
      await attachmentsApi.download(investigationId, att.attachment_id, att.original_filename);
    } catch (err) {
      setAttachmentsError(`Failed to download ${att.original_filename}`);
    } finally {
      setDownloadingId(null);
    }
  };

  if (error && !investigation) {
    return (
      <div className="rounded-2xl border p-8 flex flex-col items-center gap-3 text-center"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
        <AlertTriangle size={24} style={{ color: 'var(--accent-amber)' }} />
        <p className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>{error}</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-14 border rounded-xl animate-pulse"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
        ))}
      </div>
    );
  }

  if (!investigationId || !investigation) {
    return (
      <div className="rounded-2xl border p-10 flex flex-col items-center gap-3 text-center"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
        <FileSearch size={24} style={{ color: 'var(--text-muted)' }} />
        <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
          No originating investigation linked to this case.
        </p>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          This case has not been linked to an investigation package.
        </p>
      </div>
    );
  }

  const isSubmitted = investigation.status === 'submitted';

  return (
    <div className="space-y-5">
      {/* Investigation Package Overview Card */}
      <div className="rounded-2xl border p-5 space-y-4"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs font-semibold px-2 py-1 rounded border"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--accent-blue)' }}>
              #{investigation.investigation_id.slice(0, 8)}…
            </span>
            <InvestigationStatusBadge status={investigation.status} />
            <InvestigationPriorityBadge priority={investigation.priority} />
            <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
              v{investigation.version}
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
            <span className="flex items-center gap-1">
              <User size={13} /> Analyst: {investigation.assigned_to ?? investigation.created_by}
            </span>
            {investigation.submitted_at && (
              <span className="flex items-center gap-1">
                <Clock size={13} /> Submitted: {formatDateTime(investigation.submitted_at)}
              </span>
            )}
          </div>
        </div>

        {isSubmitted && canReview && (
          <div className="flex flex-wrap items-center gap-2 pt-1 border-t" style={{ borderColor: 'var(--bg-border)' }}>
            <button
              onClick={() => setDialog('approve')}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
              style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
            >
              <CheckCircle2 size={14} /> Approve Investigation
            </button>
            <button
              onClick={() => setDialog('return')}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
              style={{ background: 'rgba(217,119,6,0.9)', color: 'var(--text-primary)' }}
            >
              <Undo2 size={14} /> Return Investigation
            </button>
          </div>
        )}

        {/* Executive Summary */}
        {investigation.description && (
          <div>
            <h4 className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
              Executive Summary
            </h4>
            <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
              {investigation.description}
            </p>
          </div>
        )}

        {/* Detailed Findings */}
        <div>
          <h4 className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Detailed Findings
          </h4>
          <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
            {investigation.findings_text?.trim() || 'No detailed findings recorded.'}
          </p>
        </div>

        {/* References */}
        {(investigation.findings_refs?.length ?? 0) > 0 && (
          <div>
            <h4 className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
              Evidence References
            </h4>
            <div className="flex flex-wrap gap-2">
              {investigation.findings_refs?.map((ref, i) => (
                <div key={i} className="rounded-lg border px-2.5 py-1 text-xs flex items-center gap-1.5"
                  style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                  <FileText size={12} style={{ color: 'var(--text-muted)' }} />
                  <span className="font-mono text-[10px] font-semibold" style={{ color: 'var(--accent-blue)' }}>
                    {ref.type}:{ref.id}
                  </span>
                  {ref.description && (
                    <span className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                      — {ref.description}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Conclusion */}
        <div>
          <h4 className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Analyst Conclusion & Recommendation
          </h4>
          <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
            {investigation.conclusion?.trim() || 'No conclusion recorded.'}
          </p>
        </div>

        {/* Return Reason Banner */}
        {investigation.return_reason && (
          <div className="rounded-lg border px-3.5 py-2.5" style={{ background: 'rgba(217,119,6,0.08)', borderColor: 'rgba(217,119,6,0.3)' }}>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-0.5" style={{ color: 'var(--accent-amber)' }}>
              Returned Reason
            </p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{investigation.return_reason}</p>
          </div>
        )}
      </div>

      {/* Evidence Attachments Section (Read-Only) */}
      <div className="rounded-2xl border p-5 space-y-4"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Paperclip size={16} style={{ color: 'var(--accent-blue)' }} />
            <h3 className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
              Evidence Attachments
            </h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
              {attachments.length}
            </span>
          </div>
        </div>

        {attachmentsError && (
          <div className="rounded-lg border px-3 py-2 flex items-center gap-2"
            style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.25)' }}>
            <AlertTriangle size={14} style={{ color: 'var(--accent-red)' }} />
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{attachmentsError}</p>
          </div>
        )}

        {attachmentsLoading && attachments.length === 0 ? (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-12 border rounded-xl animate-pulse"
                style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }} />
            ))}
          </div>
        ) : attachments.length === 0 ? (
          <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>
            No evidence attachments uploaded for this investigation.
          </p>
        ) : (
          <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'var(--bg-border)' }}>
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                  <th className="pl-4 py-2.5 font-semibold">Filename</th>
                  <th className="py-2.5 font-semibold w-24">Type</th>
                  <th className="py-2.5 font-semibold w-24">Size</th>
                  <th className="py-2.5 font-semibold w-36">Uploaded</th>
                  <th className="pr-4 py-2.5 font-semibold text-right w-28">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--bg-border)]">
                {attachments.map((att) => {
                  const isDownloading = downloadingId === att.attachment_id;
                  return (
                    <tr key={att.attachment_id} className="hover:bg-[var(--bg-tertiary)] transition-colors">
                      <td className="pl-4 py-3">
                        <div className="flex flex-col gap-0.5">
                          <span className="font-semibold flex items-center gap-1.5" style={{ color: 'var(--text-primary)' }}>
                            {att.original_filename}
                          </span>
                          {att.description && (
                            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                              {att.description}
                            </span>
                          )}
                          <span className="font-mono text-[9px]" style={{ color: 'var(--text-subtle)' }}>
                            sha256: {att.sha256_hash.slice(0, 12)}…
                          </span>
                        </div>
                      </td>
                      <td className="py-3 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                        {att.content_type}
                      </td>
                      <td className="py-3 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                        {formatBytes(att.size_bytes)}
                      </td>
                      <td className="py-3 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                        {formatDateTime(att.uploaded_at)}
                        <span className="block text-[9px]" style={{ color: 'var(--text-subtle)' }}>
                          by {att.uploaded_by}
                        </span>
                      </td>
                      <td className="pr-4 py-3 text-right">
                        <button
                          onClick={() => handleDownload(att)}
                          disabled={isDownloading}
                          className="px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all hover:brightness-95 flex items-center gap-1 ml-auto"
                          style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--accent-blue)' }}
                        >
                          <Download size={13} />
                          {isDownloading ? 'Downloading…' : 'Download'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Originating Alert Link */}
      {investigation.alert_id && (
        <button
          onClick={() => navigate(`/workbench/alerts/${investigation.alert_id}`)}
          className="rounded-2xl border p-4 w-full flex items-center gap-2.5 text-left transition-all hover:brightness-95"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
        >
          <Link2 size={14} style={{ color: 'var(--text-muted)' }} />
          <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Originating alert
          </span>
          <span className="font-mono text-xs" style={{ color: 'var(--accent-blue)' }}>
            #{investigation.alert_id.slice(0, 8)}…
          </span>
        </button>
      )}

      {investigation && (
        <>
          <ConfirmTransitionDialog
            open={dialog === 'approve'}
            title="Approve Investigation"
            body="Approve this submitted investigation. It will be marked complete and closed."
            confirmLabel="Approve"
            investigation={investigation}
            target="completed"
            onClose={() => setDialog(null)}
            onSuccess={setInvestigation}
            onConflict={fetchInvestigation}
          />
          <ReturnInvestigationDialog
            open={dialog === 'return'}
            investigation={investigation}
            onClose={() => setDialog(null)}
            onSuccess={setInvestigation}
            onConflict={fetchInvestigation}
          />
        </>
      )}
    </div>
  );
}
