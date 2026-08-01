// src/components/cases/dialogs/DecisionForm.tsx
// Inline Decision Form — six decision types; Report-to-Authority runs an inline
// four-eyes approval flow (create approval request → poll until approved).
import React, { useCallback, useEffect, useState } from 'react';
import { BadgeCheck, ShieldAlert, TimerReset } from 'lucide-react';
import { casesApi } from '../../../api/casesApi';
import { approvalsApi } from '../../../api/approvalsApi';
import { parseCaseError } from '../caseErrors';
import { useAuth } from '../../../auth/AuthProvider';
import { PERMISSIONS } from '../../../lib/permissions';
import { decisionTypeLabel } from '../CaseBadges';
import type { Case, DecisionType } from '../../../types/cases';
import type { ApprovalRequest } from '../../../types/alerts';

const DECISION_TYPES: DecisionType[] = [
  'no_action',
  'warning',
  'enhanced_due_diligence_recommended',
  'report_to_authority_recommended',
  'account_action_recommended',
  'closure_recommended',
];

const APPROVAL_POLL_MS = 10_000;

interface Props {
  caseData: Case;
  onRecorded: (c: Case) => void;
  onConflict: () => void;
}

export function DecisionForm({ caseData, onRecorded, onConflict }: Props) {
  const { hasPermission } = useAuth();
  const canRequestApproval = hasPermission(PERMISSIONS.APPROVAL_REQUEST);

  const [decisionType, setDecisionType] = useState<DecisionType>('no_action');
  const [rationale, setRationale] = useState('');
  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [creatingApproval, setCreatingApproval] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const isAuthority = decisionType === 'report_to_authority_recommended';
  const approvalApproved = approval?.status === 'approved';
  const approvalActive = approval && ['pending', 'approved'].includes(approval.status);

  const pollApproval = useCallback(async (id: string) => {
    try {
      const a = await approvalsApi.get(id);
      setApproval(a);
    } catch {
      // transient — keep previous state; next poll retries
    }
  }, []);

  // Poll approval status every 10s until it leaves the pending state.
  useEffect(() => {
    if (!approval || approval.status !== 'pending') return;
    const t = setInterval(() => pollApproval(approval.approval_request_id), APPROVAL_POLL_MS);
    return () => clearInterval(t);
  }, [approval, pollApproval]);

  const requestApproval = async () => {
    if (creatingApproval) return;
    setCreatingApproval(true);
    setError(null);
    try {
      const res = await approvalsApi.create({
        action_type: 'decision_report_to_authority',
        entity_type: 'compliance_case',
        entity_id: caseData.case_id,
        proposed_payload: { decision_type: decisionType, rationale },
        rationale: rationale.trim() || `Report to authority recommended for case ${caseData.case_id}`,
      });
      setApproval(res.approval_request);
      pollApproval(res.approval_request.approval_request_id);
    } catch (err) {
      setError(parseCaseError(err).message);
    } finally {
      setCreatingApproval(false);
    }
  };

  const submit = async () => {
    if (submitting || !rationale.trim()) return;
    if (isAuthority && !approvalApproved) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await casesApi.recordDecision(caseData.case_id, {
        decision_type: decisionType,
        rationale: rationale.trim(),
        ...(isAuthority && approval ? { approval_request_id: approval.approval_request_id } : {}),
        expected_version: caseData.version,
      });
      setSuccess(true);
      setRationale('');
      setApproval(null);
      onRecorded(res.case);
      setTimeout(() => setSuccess(false), 4000);
    } catch (err) {
      const parsed = parseCaseError(err);
      if (parsed.kind === 'conflict' || parsed.kind === 'approval_required') {
        onConflict();
      } else {
        setError(parsed.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const needsApprovalAndCannotRequest = isAuthority && !approval && !canRequestApproval;

  return (
    <div className="rounded-2xl border p-5"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
      <h3 className="text-[10px] font-bold uppercase tracking-wider mb-4" style={{ color: 'var(--text-muted)' }}>
        Record Decision
      </h3>

      <div className="space-y-3">
        {DECISION_TYPES.map((t) => (
          <label key={t} className="flex items-start gap-2.5 cursor-pointer rounded-lg border px-3 py-2.5 transition-all hover:brightness-95"
            style={{
              background: decisionType === t ? 'rgba(37,99,235,0.08)' : 'var(--bg-tertiary)',
              borderColor: decisionType === t ? 'var(--accent-blue)' : 'var(--bg-border)',
            }}>
            <input
              type="radio"
              name="decision-type"
              checked={decisionType === t}
              onChange={() => { setDecisionType(t); setApproval(null); }}
              className="mt-0.5 accent-[var(--accent-blue)]"
            />
            <span className="flex-1 min-w-0">
              <span className="flex items-center gap-2 text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                {decisionTypeLabel(t)}
                {t === 'report_to_authority_recommended' && (
                  <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] border"
                    style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
                    <ShieldAlert size={10} /> Approval required
                  </span>
                )}
              </span>
            </span>
          </label>
        ))}
      </div>

      <div className="mt-4">
        <label htmlFor="decision-rationale" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
          Rationale *
        </label>
        <textarea
          id="decision-rationale"
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={4}
          placeholder="Explain the basis for this decision…"
          className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
          style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
        />
      </div>

      {isAuthority && (
        <div className="mt-4 rounded-lg border px-3 py-3"
          style={{ background: 'rgba(220,38,38,0.05)', borderColor: 'rgba(220,38,38,0.2)' }}>
          <p className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--accent-red)' }}>
            Four-eyes approval required
          </p>
          {needsApprovalAndCannotRequest ? (
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Your account cannot request this approval. Contact a compliance approver to create the request for this decision.
            </p>
          ) : approval ? (
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                {approvalApproved ? (
                  <BadgeCheck size={14} style={{ color: 'var(--accent-green)' }} />
                ) : (
                  <TimerReset size={14} style={{ color: 'var(--accent-amber)' }} />
                )}
                <span className="text-xs font-semibold" style={{ color: approvalApproved ? 'var(--accent-green)' : 'var(--text-secondary)' }}>
                  Approval {approval.status === 'pending' ? `pending (${approval.approval_count}/${approval.required_approvals})` : approval.status}
                </span>
              </div>
              <button onClick={() => pollApproval(approval.approval_request_id)}
                className="text-[10px] font-semibold underline" style={{ color: 'var(--text-muted)' }}>
                Refresh status
              </button>
            </div>
          ) : (
            <button
              onClick={requestApproval}
              disabled={creatingApproval || !rationale.trim()}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
              style={{ background: 'rgba(220,38,38,0.9)', color: 'var(--text-primary)' }}
            >
              <ShieldAlert size={13} /> {creatingApproval ? 'Requesting…' : 'Request Approval'}
            </button>
          )}
          {approvalActive && approval.status !== 'approved' && (
            <p className="text-[10px] mt-2" style={{ color: 'var(--text-muted)' }}>
              Status refreshes automatically every 10 seconds.
            </p>
          )}
        </div>
      )}

      {error && (
        <div role="alert" className="mt-4 px-3 py-2 rounded-lg border text-xs"
          style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
          {error}
        </div>
      )}
      {success && (
        <div role="status" className="mt-4 px-3 py-2 rounded-lg border text-xs"
          style={{ background: 'rgba(22,163,74,0.08)', borderColor: 'rgba(22,163,74,0.2)', color: 'var(--accent-green)' }}>
          Decision recorded.
        </div>
      )}

      <div className="mt-4 flex justify-end">
        <button
          onClick={submit}
          disabled={submitting || !rationale.trim() || (isAuthority && !approvalApproved)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
          style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
        >
          {submitting ? 'Recording…' : 'Submit Decision'}
        </button>
      </div>
    </div>
  );
}
