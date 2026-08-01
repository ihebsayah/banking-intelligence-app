// src/components/alerts/dialogs/DismissAlertDialog.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { Modal } from '../../ui/Modal';
import { StatusBadge } from '../../ui/StatusBadge';
import { alertsApi } from '../../../api/alertsApi';
import { approvalsApi } from '../../../api/approvalsApi';
import { parseAlertError } from '../alertErrors';
import { useAuth } from '../../../auth/AuthProvider';
import { PERMISSIONS } from '../../../lib/permissions';
import type { Alert, ApprovalRequest, ApprovalStatus } from '../../../types/alerts';

interface Props {
  alert: Alert;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  onConflict: () => void;
}

const approvalStatusVariant: Record<ApprovalStatus, 'yellow' | 'green' | 'red' | 'gray'> = {
  pending: 'yellow',
  approved: 'green',
  rejected: 'red',
  expired: 'red',
  cancelled: 'gray',
};

export function DismissAlertDialog({ alert, open, onClose, onSuccess, onConflict }: Props) {
  const { hasPermission } = useAuth();
  const needsApproval = alert.severity === 'critical' || alert.severity === 'high';
  const canRequestApproval = hasPermission(PERMISSIONS.APPROVAL_REQUEST);

  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  const reset = useCallback(() => {
    setReason('');
    setError(null);
    setRequestError(null);
    setApproval(null);
    setSubmitting(false);
    setRequesting(false);
  }, []);

  useEffect(() => {
    if (open) reset();
  }, [open, reset]);

  // Poll approval status until it reaches a terminal state.
  useEffect(() => {
    if (!approval || approval.status !== 'pending') return;
    const t = window.setInterval(async () => {
      try {
        const next = await approvalsApi.get(approval.approval_request_id);
        setApproval(next);
      } catch {
        // transient — keep polling until terminal; next successful poll recovers
      }
    }, 4000);
    return () => window.clearInterval(t);
  }, [approval]);

  const requestApproval = async () => {
    if (!reason.trim() || requesting) return;
    setRequesting(true);
    setRequestError(null);
    try {
      const res = await approvalsApi.create({
        action_type: 'alert_dismissal_critical_high',
        entity_type: 'alert',
        entity_id: alert.alert_id,
        proposed_payload: { dismissed_reason: reason.trim() },
        rationale: reason.trim(),
      });
      setApproval(res.approval_request);
    } catch (err) {
      setRequestError(parseAlertError(err).message);
    } finally {
      setRequesting(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim() || submitting) return;
    if (needsApproval && (!approval || approval.status !== 'approved')) return;
    setSubmitting(true);
    setError(null);
    try {
      await alertsApi.dismiss(alert.alert_id, {
        dismissed_reason: reason.trim(),
        expected_version: alert.version,
        approval_request_id: needsApproval && approval ? approval.approval_request_id : undefined,
      });
      onClose();
      onSuccess();
    } catch (err) {
      const parsed = parseAlertError(err);
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

  const approvalReady = !needsApproval || (approval?.status === 'approved' && !approval.executed_at);

  return (
    <Modal
      open={open}
      title="Dismiss Alert"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          <button type="submit" form="dismiss-form" disabled={submitting || !reason.trim() || !approvalReady}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-red)', color: 'var(--text-primary)' }}>
            {submitting ? 'Dismissing…' : 'Dismiss Alert'}
          </button>
        </>
      }
    >
      <form id="dismiss-form" onSubmit={submit} className="space-y-4">
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Dismissal Reason *
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="Why is this alert being dismissed?"
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>

        {needsApproval && (
          <div className="px-3 py-2.5 rounded-lg border space-y-2"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
            <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--accent-amber)' }}>
              Four-eyes approval required
            </p>
            {!approval ? (
              <>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  Dismissing a {alert.severity} alert requires an approved request from a compliance officer.
                </p>
                {canRequestApproval ? (
                  <button type="button" onClick={requestApproval} disabled={requesting || !reason.trim()}
                    className="px-3 py-1.5 rounded-lg text-[11px] font-semibold border transition-all hover:brightness-95 disabled:opacity-40 disabled:pointer-events-none"
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
                    {requesting ? 'Requesting…' : 'Request Approval'}
                  </button>
                ) : (
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    Contact a compliance officer to approve this dismissal.
                  </p>
                )}
                {requestError && (
                  <p className="text-xs" style={{ color: 'var(--accent-red)' }}>{requestError}</p>
                )}
              </>
            ) : (
              <div className="flex items-center gap-2">
                <StatusBadge variant={approvalStatusVariant[approval.status]}>{approval.status}</StatusBadge>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {approval.approval_count}/{approval.required_approvals} approvals · {approval.approval_request_id.slice(0, 8)}…
                </span>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="px-3 py-2 rounded-lg border text-xs" style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
            {error}
          </div>
        )}
      </form>
    </Modal>
  );
}
