// src/components/approvals/ApprovalDetailDialog.tsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Modal } from '../ui/Modal';
import { StatusBadge } from '../ui/StatusBadge';
import { approvalsApi } from '../../api/approvalsApi';
import { parseCaseError } from '../cases/caseErrors';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { formatDateTime } from '../../utils/formatters';
import {
  approvalActionLabel, approvalDecisionVariant, approvalEntityLabel,
  approvalEntityRoute, approvalStatusVariant,
} from './approvalLabels';
import type { ApprovalRequestDetail } from '../../types/alerts';

interface Props {
  open: boolean;
  approvalId: string | null;
  onClose: () => void;
  onSuccess: () => void;
  onConflict: () => void;
}

type Decision = 'approved' | 'rejected';

function isTimeExpired(detail: ApprovalRequestDetail): boolean {
  return detail.status === 'pending' && new Date(detail.expires_at).getTime() <= Date.now();
}

function statusLabel(detail: ApprovalRequestDetail): string {
  if (detail.status === 'expired') return 'Expired';
  if (isTimeExpired(detail)) return 'Expired';
  if (detail.status === 'approved' && detail.executed_at) return 'Executed';
  if (detail.status === 'approved') return 'Approved — awaiting execution';
  return detail.status.charAt(0).toUpperCase() + detail.status.slice(1);
}

export function ApprovalDetailDialog({ open, approvalId, onClose, onSuccess, onConflict }: Props) {
  const { applicationUser, hasPermission } = useAuth();
  const currentUserId = applicationUser?.user_id ?? '';

  const [detail, setDetail] = useState<ApprovalRequestDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [confirmDecision, setConfirmDecision] = useState<Decision | null>(null);
  const [rationale, setRationale] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [announce, setAnnounce] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !approvalId) return;
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    setDetail(null);
    setConfirmDecision(null);
    setRationale('');
    setError(null);
    setConflict(false);
    setAnnounce(null);
    approvalsApi.get(approvalId)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch((err) => { if (!cancelled) setLoadError(parseCaseError(err).message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, approvalId]);

  const refetch = async () => {
    if (!approvalId) return;
    try {
      const latest = await approvalsApi.get(approvalId);
      setDetail(latest);
      if (latest.status !== 'pending' || isTimeExpired(latest) || latest.decisions.some((d) => d.approver_id === currentUserId)) {
        setConfirmDecision(null);
      }
    } catch {
      // Stale view kept; the queue refresh still surfaces the change.
    }
  };

  const submitVote = async (decision: Decision) => {
    if (!detail || submitting) return;
    if (decision === 'rejected' && !rationale.trim()) return;
    setSubmitting(true);
    setError(null);
    setConflict(false);
    setAnnounce(null);
    try {
      const res = await approvalsApi.vote(detail.approval_request_id, {
        decision,
        rationale: decision === 'rejected' ? rationale.trim() : undefined,
      });
      setDetail(res.approval_request);
      setConfirmDecision(null);
      setRationale('');
      setAnnounce(res.approval_request.status === 'approved' ? 'Approval recorded.' : 'Rejection recorded.');
      onSuccess();
    } catch (err) {
      const parsed = parseCaseError(err);
      if (parsed.kind === 'conflict') {
        setConflict(true);
        await refetch();
        onConflict();
      } else {
        setError(parsed.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const entityRoute = detail ? approvalEntityRoute(detail.entity_type, detail.entity_id) : null;
  const timeExpired = detail ? isTimeExpired(detail) : false;
  const hasVoted = detail ? detail.decisions.some((d) => d.approver_id === currentUserId) : false;
  const isSelf = detail ? detail.requested_by === currentUserId : false;
  const canVote = !!detail && detail.status === 'pending'
    && !timeExpired
    && hasPermission(PERMISSIONS.APPROVAL_APPROVE)
    && !isSelf
    && !hasVoted;

  return (
    <Modal open={open} title="Approval Request" onClose={onClose}>
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-10 border rounded-lg animate-pulse"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }} />
          ))}
        </div>
      ) : loadError ? (
        <div className="rounded-lg border p-6 text-center"
          style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)' }}>
          <p className="text-xs" style={{ color: 'var(--accent-red)' }}>{loadError}</p>
        </div>
      ) : detail ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <StatusBadge variant={approvalStatusVariant(detail.status)}>{statusLabel(detail)}</StatusBadge>
            <span className="text-[10px] font-mono" style={{ color: 'var(--text-subtle)' }}>
              v{detail.version} · {approvalActionLabel(detail.action_type)}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Action type</p>
              <p style={{ color: 'var(--text-primary)' }}>{approvalActionLabel(detail.action_type)}</p>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Linked entity</p>
              {entityRoute ? (
                <Link to={entityRoute} onClick={onClose} className="underline hover:brightness-90"
                  style={{ color: 'var(--accent-blue)' }}>
                  {approvalEntityLabel(detail.entity_type)} · <span className="font-mono">{detail.entity_id}</span>
                </Link>
              ) : (
                <p className="font-mono" style={{ color: 'var(--text-secondary)' }}>
                  {approvalEntityLabel(detail.entity_type)} · {detail.entity_id}
                </p>
              )}
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Requested by</p>
              <p className="font-mono" style={{ color: 'var(--text-secondary)' }}>{detail.requested_by}</p>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Requested at</p>
              <p className="font-mono" style={{ color: 'var(--text-secondary)' }}>{formatDateTime(detail.created_at)}</p>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Expires at</p>
              <p className="font-mono" style={{ color: timeExpired ? 'var(--accent-red)' : 'var(--text-secondary)' }}>
                {formatDateTime(detail.expires_at)}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Executed at</p>
              <p className="font-mono" style={{ color: 'var(--text-secondary)' }}>{detail.executed_at ? formatDateTime(detail.executed_at) : '—'}</p>
            </div>
          </div>

          <div className="rounded-lg border px-3 py-2" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-0.5" style={{ color: 'var(--text-muted)' }}>
              Approval progress
            </p>
            <p className="text-xs" style={{ color: 'var(--text-primary)' }}>
              {detail.approval_count} of {detail.required_approvals} approvals received
            </p>
          </div>

          <div className="rounded-lg border px-3 py-2" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-0.5" style={{ color: 'var(--text-muted)' }}>Rationale</p>
            <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>{detail.rationale}</p>
          </div>

          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
              Vote history {detail.decisions.length > 0 && `(${detail.decisions.length})`}
            </p>
            {detail.decisions.length === 0 ? (
              <p className="text-xs" style={{ color: 'var(--text-subtle)' }}>No votes cast yet.</p>
            ) : (
              <ul className="space-y-1.5">
                {detail.decisions.map((d) => (
                  <li key={d.approval_decision_id} className="rounded-lg border px-3 py-2"
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>{d.approver_id}</span>
                      <div className="flex items-center gap-2">
                        <StatusBadge variant={approvalDecisionVariant(d.decision)}>{d.decision}</StatusBadge>
                        <span className="font-mono text-[10px]" style={{ color: 'var(--text-subtle)' }}>{formatDateTime(d.decided_at)}</span>
                      </div>
                    </div>
                    {d.rationale && (
                      <p className="text-[11px] mt-1 whitespace-pre-wrap" style={{ color: 'var(--text-muted)' }}>{d.rationale}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {confirmDecision ? (
            <div className="rounded-lg border px-3 py-3 space-y-2"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
              {confirmDecision === 'rejected' && (
                <div>
                  <label htmlFor="reject-rationale" className="block text-[10px] font-bold uppercase tracking-wider mb-1"
                    style={{ color: 'var(--text-muted)' }}>
                    Rejection rationale *
                  </label>
                  <textarea
                    id="reject-rationale"
                    value={rationale}
                    onChange={(e) => setRationale(e.target.value)}
                    rows={3}
                    placeholder="Explain why this request is rejected."
                    className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
                  />
                </div>
              )}
              <div className="flex items-center justify-end gap-2">
                <button type="button" onClick={() => setConfirmDecision(null)} disabled={submitting}
                  className="px-3 py-1.5 rounded-lg text-[11px] font-semibold border transition-all hover:brightness-95 disabled:opacity-40"
                  style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => submitVote(confirmDecision)}
                  disabled={submitting || (confirmDecision === 'rejected' && !rationale.trim())}
                  className="px-3 py-1.5 rounded-lg text-[11px] font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
                  style={{
                    background: confirmDecision === 'approved' ? 'var(--accent-green)' : 'var(--accent-red)',
                    color: 'var(--text-primary)',
                  }}
                >
                  {submitting ? 'Submitting…' : confirmDecision === 'approved' ? 'Confirm approve' : 'Confirm reject'}
                </button>
              </div>
            </div>
          ) : canVote ? (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setConfirmDecision('rejected')}
                className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
                style={{ background: 'var(--bg-card)', borderColor: 'rgba(220,38,38,0.4)', color: 'var(--accent-red)' }}
              >
                Reject
              </button>
              <button
                type="button"
                onClick={() => setConfirmDecision('approved')}
                className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
              >
                Approve
              </button>
            </div>
          ) : (
            <div>
              {isSelf && (
                <p className="text-xs" style={{ color: 'var(--accent-amber)' }}>
                  You cannot vote on your own approval request.
                </p>
              )}
              {!isSelf && hasVoted && (
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  You have already voted on this request. Your vote is listed above.
                </p>
              )}
              {!isSelf && !hasVoted && detail.status !== 'pending' && (
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  This request is no longer pending — voting is closed.
                </p>
              )}
              {timeExpired && (
                <p className="text-xs" style={{ color: 'var(--accent-red)' }}>
                  This request has passed its expiry time and can no longer be voted on.
                </p>
              )}
            </div>
          )}

          {conflict && (
            <div role="alert" className="px-3 py-2 rounded-lg border text-xs"
              style={{ background: 'rgba(217,119,6,0.08)', borderColor: 'rgba(217,119,6,0.3)', color: 'var(--accent-amber)' }}>
              Another approver or the system updated this request while you were working. Your draft was kept — review the latest state before resubmitting.
            </div>
          )}

          {error && (
            <div role="alert" className="px-3 py-2 rounded-lg border text-xs"
              style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
              {error}
            </div>
          )}

          <div aria-live="polite" className="sr-only">{announce}</div>
        </div>
      ) : null}
    </Modal>
  );
}
