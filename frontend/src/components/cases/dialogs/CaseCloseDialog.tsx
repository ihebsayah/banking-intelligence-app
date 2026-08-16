// src/components/cases/dialogs/CaseCloseDialog.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, ShieldAlert, X } from 'lucide-react';
import { casesApi } from '../../../api/casesApi';
import { approvalsApi } from '../../../api/approvalsApi';
import { parseCaseError } from '../caseErrors';
import { useAuth } from '../../../auth/AuthProvider';
import { PERMISSIONS } from '../../../lib/permissions';
import type { Case } from '../../../types/cases';
import type { ApprovalRequest } from '../../../types/alerts';

interface Props {
  open: boolean;
  caseData: Case;
  onClose: () => void;
  onSuccess: (c: Case) => void;
  onConflict: () => void;
}

export function CaseCloseDialog({ open, caseData, onClose, onSuccess, onConflict }: Props) {
  const { applicationUser, hasPermission } = useAuth();
  const canRequestApproval = hasPermission(PERMISSIONS.APPROVAL_REQUEST);
  const canApprove = hasPermission(PERMISSIONS.APPROVAL_APPROVE);

  const [resolution, setResolution] = useState(caseData.resolution ?? '');
  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [creatingApproval, setCreatingApproval] = useState(false);
  const [voting, setVoting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isHighRisk = ['critical', 'high'].includes(caseData.risk_level?.toLowerCase() ?? '');
  const isApprovalRequired = isHighRisk;
  const isApproved = approval?.status === 'approved';

  useEffect(() => {
    setResolution(caseData.resolution ?? '');
    setError(null);
    setApproval(null);
  }, [caseData, open]);

  const fetchExistingApproval = useCallback(async () => {
    if (!open || !isHighRisk) return;
    try {
      const res = await approvalsApi.list({
        actionType: 'case_closure_critical_high',
        status: 'pending',
      });
      const match = res.items.find(
        (a) => a.entity_id === caseData.case_id && a.entity_type === 'compliance_case'
      );
      if (match) {
        const detail = await approvalsApi.get(match.approval_request_id);
        setApproval(detail);
      }
    } catch {
      // transient
    }
  }, [open, isHighRisk, caseData.case_id]);

  useEffect(() => {
    fetchExistingApproval();
  }, [fetchExistingApproval]);

  if (!open) return null;

  const handleRequestApproval = async () => {
    if (creatingApproval) return;
    setCreatingApproval(true);
    setError(null);
    try {
      const res = await approvalsApi.create({
        action_type: 'case_closure_critical_high',
        entity_type: 'compliance_case',
        entity_id: caseData.case_id,
        rationale: resolution.trim() || `Case closure requested for High/Critical risk case ${caseData.case_id}`,
      });
      setApproval(res.approval_request);
    } catch (err) {
      setError(parseCaseError(err).message);
    } finally {
      setCreatingApproval(false);
    }
  };

  const handleVote = async (decision: 'approved' | 'rejected') => {
    if (!approval || voting) return;
    setVoting(true);
    setError(null);
    try {
      const res = await approvalsApi.vote(approval.approval_request_id, {
        decision,
        rationale: decision === 'rejected' ? 'Rejection vote' : 'Approval vote',
      });
      setApproval(res.approval_request);
    } catch (err) {
      setError(parseCaseError(err).message);
    } finally {
      setVoting(false);
    }
  };

  const handleSubmitClose = async () => {
    if (submitting) return;
    if (isApprovalRequired && !isApproved) return;

    const finalRes = resolution.trim() || caseData.resolution;
    if (!finalRes) {
      setError('Resolution text is required before closing the case.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const res = await casesApi.close(caseData.case_id, {
        resolution: finalRes,
        expected_version: caseData.version,
        ...(approval ? { approval_request_id: approval.approval_request_id } : {}),
      });
      onSuccess(res.case);
      onClose();
    } catch (err) {
      const parsed = parseCaseError(err);
      if (parsed.kind === 'conflict') {
        onConflict();
        onClose();
      } else {
        setError(parsed.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const isRequester = Boolean(approval && applicationUser?.user_id && approval.requested_by === applicationUser.user_id);
  const canVoteHere = canApprove && approval?.status === 'pending' && !isRequester;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border p-6 space-y-5 shadow-2xl animate-in fade-in zoom-in-95 duration-150"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
        
        {/* Header */}
        <div className="flex items-center justify-between border-b pb-4" style={{ borderColor: 'var(--bg-border)' }}>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={18} style={{ color: 'var(--accent-green)' }} />
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Close Compliance Case
            </h3>
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
            style={{ color: 'var(--text-muted)' }}
          >
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="rounded-xl border p-3 flex items-center gap-2"
            style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.25)' }}>
            <AlertTriangle size={16} style={{ color: 'var(--accent-red)' }} />
            <p className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>{error}</p>
          </div>
        )}

        {/* Info notice */}
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          Closing this case completes the operational case lifecycle.
          {isHighRisk && ' Because this is a High/Critical risk case, closure requires 4-eyes approval.'}
        </p>

        {/* Resolution textarea */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Closure Resolution Summary <span className="text-[var(--accent-red)]">*</span>
          </label>
          <textarea
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            rows={3}
            placeholder="Document the final resolution summary and operational outcome…"
            className="w-full rounded-xl p-3 text-xs outline-none border focus:border-[var(--accent-blue)]"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>

        {/* High / Critical Approval section */}
        {isHighRisk && (
          <div className="rounded-xl border p-4 space-y-3" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5" style={{ color: 'var(--accent-amber)' }}>
                <ShieldAlert size={14} /> 4-Eyes Approval Required (Risk: {caseData.risk_level})
              </span>
              {approval && (
                <span className="font-mono text-[10px] uppercase font-bold px-2 py-0.5 rounded border"
                  style={{
                    background: approval.status === 'approved' ? 'rgba(16,185,129,0.1)' : 'rgba(217,119,6,0.1)',
                    borderColor: approval.status === 'approved' ? 'rgba(16,185,129,0.3)' : 'rgba(217,119,6,0.3)',
                    color: approval.status === 'approved' ? 'var(--accent-green)' : 'var(--accent-amber)',
                  }}>
                  {approval.status}
                </span>
              )}
            </div>

            {!approval && canRequestApproval && (
              <button
                onClick={handleRequestApproval}
                disabled={creatingApproval}
                className="w-full py-2 rounded-lg text-xs font-semibold shadow-sm transition-all hover:brightness-95"
                style={{ background: 'var(--accent-amber)', color: 'var(--text-primary)' }}
              >
                {creatingApproval ? 'Submitting Request…' : 'Request Closure Approval'}
              </button>
            )}

            {canVoteHere && (
              <div className="flex items-center gap-2 pt-2 border-t" style={{ borderColor: 'var(--bg-border)' }}>
                <button
                  onClick={() => handleVote('approved')}
                  disabled={voting}
                  className="flex-1 py-1.5 rounded-lg text-xs font-semibold shadow-sm"
                  style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
                >
                  Approve Closure
                </button>
                <button
                  onClick={() => handleVote('rejected')}
                  disabled={voting}
                  className="flex-1 py-1.5 rounded-lg text-xs font-semibold border"
                  style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--accent-red)' }}
                >
                  Reject Closure
                </button>
              </div>
            )}

            {isRequester && approval?.status === 'pending' && (
              <p className="text-[11px] italic" style={{ color: 'var(--text-muted)' }}>
                Approval request pending. Another Compliance Officer in scope must approve before closing.
              </p>
            )}
          </div>
        )}

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t" style={{ borderColor: 'var(--bg-border)' }}>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-colors"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmitClose}
            disabled={submitting || (isApprovalRequired && !isApproved)}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
          >
            {submitting ? 'Closing Case…' : 'Close Case'}
          </button>
        </div>
      </div>
    </div>
  );
}
