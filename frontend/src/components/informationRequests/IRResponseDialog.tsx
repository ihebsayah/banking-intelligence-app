// src/components/informationRequests/IRResponseDialog.tsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Modal } from '../ui/Modal';
import { StatusBadge } from '../ui/StatusBadge';
import { informationRequestsApi } from '../../api/informationRequestsApi';
import { parseCaseError } from '../cases/caseErrors';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { formatDateTime } from '../../utils/formatters';
import type { InformationRequest } from '../../types/cases';

const irStatusVariant: Record<string, 'blue' | 'green' | 'yellow' | 'purple' | 'gray' | 'red'> = {
  open: 'blue',
  acknowledged: 'purple',
  responded: 'yellow',
  accepted: 'green',
  returned: 'yellow',
  cancelled: 'gray',
};

function isOverdue(ir: InformationRequest): boolean {
  if (!ir.due_date) return false;
  if (ir.status === 'accepted' || ir.status === 'cancelled') return false;
  return new Date(ir.due_date).getTime() < Date.now();
}

interface Props {
  open: boolean;
  ir: InformationRequest | null;
  onClose: () => void;
  onSuccess: (updated: InformationRequest, close: boolean) => void;
  onConflict: () => void;
}

export function IRResponseDialog({ open, ir, onClose, onSuccess, onConflict }: Props) {
  const { applicationUser, hasPermission } = useAuth();
  const canRespond = hasPermission(PERMISSIONS.INFO_REQUEST_RESPOND);
  const isAssignee = !!ir && ir.assigned_to === applicationUser?.user_id;

  const [draft, setDraft] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  useEffect(() => {
    if (open) {
      setDraft(ir?.response_text ?? '');
      setSubmitting(false);
      setError(null);
      setConflict(false);
    }
    // Re-init the draft only when a new request is opened (not on background refetch).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, ir?.ir_id]);

  if (!ir) return null;

  const overdue = isOverdue(ir);
  const isReturned = ir.status === 'returned';
  const canAcknowledge = isAssignee && canRespond && (ir.status === 'open' || isReturned);
  const canEdit = isAssignee && canRespond && (ir.status === 'acknowledged' || isReturned);
  const canSubmit = canEdit && draft.trim().length > 0;
  const readOnly = ir.status === 'responded' || ir.status === 'accepted' || ir.status === 'cancelled';

  const handleAcknowledge = async () => {
    if (!ir || submitting) return;
    setSubmitting(true);
    setError(null);
    setConflict(false);
    try {
      const res = await informationRequestsApi.acknowledge(ir.ir_id, { expected_version: ir.version });
      onSuccess(res.information_request, false);
    } catch (err) {
      const parsed = parseCaseError(err);
      if (parsed.kind === 'conflict') {
        setConflict(true);
        onConflict();
      } else {
        setError(parsed.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleRespond = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ir || submitting) return;
    const text = draft.trim();
    if (!text) return;
    setSubmitting(true);
    setError(null);
    setConflict(false);
    try {
      const res = await informationRequestsApi.respond(ir.ir_id, { response_text: text, expected_version: ir.version });
      onSuccess(res.information_request, true);
    } catch (err) {
      const parsed = parseCaseError(err);
      if (parsed.kind === 'conflict') {
        setConflict(true);
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
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          {canAcknowledge && (
            <button
              type="button"
              onClick={handleAcknowledge}
              disabled={submitting}
              className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
              style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
            >
              {submitting ? 'Submitting…' : isReturned ? 'Re-acknowledge' : 'Acknowledge'}
            </button>
          )}
          {canEdit && (
            <button
              type="submit"
              form="ir-response-form"
              disabled={submitting || !canSubmit}
              className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
              style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
            >
              {submitting ? 'Submitting…' : 'Submit Response'}
            </button>
          )}
        </>
      }
    >
      <form id="ir-response-form" onSubmit={handleRespond} className="space-y-4">
        <div className="flex items-center justify-between gap-2">
          <StatusBadge variant={irStatusVariant[ir.status] ?? 'gray'}>
            {ir.status.replace(/_/g, ' ')}
          </StatusBadge>
          {overdue && (
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--accent-red)' }}>
              overdue
            </span>
          )}
        </div>

        {ir.question && (
          <div className="rounded-lg border px-3 py-2" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Question</p>
            <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>{ir.question}</p>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
          <span className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
            Case{' '}
            <Link
              to={`/workbench/cases/${ir.case_id}`}
              className="underline hover:brightness-90"
              style={{ color: 'var(--accent-blue)' }}
            >
              {ir.case_id}
            </Link>
            {ir.investigation_id && (
              <> · Investigation{' '}
                <Link
                  to={`/workbench/investigations/${ir.investigation_id}`}
                  className="underline hover:brightness-90"
                  style={{ color: 'var(--accent-blue)' }}
                >
                  {ir.investigation_id}
                </Link>
              </>
            )}
          </span>
          <span className="font-mono" style={{ color: overdue ? 'var(--accent-red)' : 'var(--text-muted)' }}>
            due {ir.due_date ?? '—'}
          </span>
          <span className="font-mono" style={{ color: 'var(--text-muted)' }}>
            v{ir.version}
          </span>
        </div>

        {isReturned && (
          <div className="rounded-lg border px-3 py-2" style={{ background: 'rgba(217,119,6,0.08)', borderColor: 'rgba(217,119,6,0.3)' }}>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-0.5" style={{ color: 'var(--accent-amber)' }}>
              Returned — reason: {ir.return_reason ?? 'Not provided'}
            </p>
            <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              {ir.returned_at ? formatDateTime(ir.returned_at) : ''}
              {ir.returned_by ? ` · by ${ir.returned_by}` : ''}
            </p>
          </div>
        )}

        <div>
          <label htmlFor="ir-response" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Your response
          </label>
          <textarea
            id="ir-response"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={4}
            disabled={!canEdit}
            placeholder={canEdit ? 'Enter your response…' : 'Response locked — no further action is required.'}
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none disabled:opacity-50"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
          <p className="text-[10px] mt-1" style={{ color: 'var(--text-subtle)' }}>
            {readOnly
              ? 'This request is complete.'
              : ir.status === 'open'
                ? 'Acknowledge this request before responding.'
                : 'Send your response to compliance for review.'}
          </p>
        </div>

        {conflict && (
          <div role="alert" className="px-3 py-2 rounded-lg border text-xs"
            style={{ background: 'rgba(217,119,6,0.08)', borderColor: 'rgba(217,119,6,0.3)', color: 'var(--accent-amber)' }}>
            This request was updated by another user. Your draft was kept — review the latest version and resubmit.
          </div>
        )}

        {error && (
          <div role="alert" className="px-3 py-2 rounded-lg border text-xs"
            style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
            {error}
          </div>
        )}
      </form>
    </Modal>
  );
}
