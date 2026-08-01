// src/components/cases/dialogs/AdminAssignCaseDialog.tsx
import React, { useState } from 'react';
import { Modal } from '../../ui/Modal';
import { casesApi } from '../../../api/casesApi';
import { parseCaseError } from '../caseErrors';
import type { Case } from '../../../types/cases';

interface Props {
  open: boolean;
  caseData: Case;
  onClose: () => void;
  onSuccess: (c: Case) => void;
  onConflict: () => void;
}

export function AdminAssignCaseDialog({ open, caseData, onClose, onSuccess, onConflict }: Props) {
  const [assignedTo, setAssignedTo] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isReassign = Boolean(caseData.assigned_to);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignedTo.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await casesApi.assign(caseData.case_id, {
        assigned_to: assignedTo.trim(),
        ...(reason.trim() ? { reason: reason.trim() } : {}),
        expected_version: caseData.version,
      });
      onClose();
      onSuccess(res.case);
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
      title={isReassign ? 'Reassign Case' : 'Assign Case'}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          <button type="submit" form="assign-form" disabled={submitting || !assignedTo.trim()}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}>
            {submitting ? 'Assigning…' : isReassign ? 'Reassign' : 'Assign'}
          </button>
        </>
      }
    >
      <form id="assign-form" onSubmit={submit} className="space-y-4">
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {isReassign
            ? `Currently assigned to ${caseData.assigned_to}. Reassignment requires admin privileges and is recorded in the timeline.`
            : 'Assign this case to a compliance analyst to begin review.'}
        </p>
        <div>
          <label htmlFor="assign-to" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Assign to (user id) *
          </label>
          <input
            id="assign-to"
            value={assignedTo}
            onChange={(e) => setAssignedTo(e.target.value)}
            placeholder="e.g. compliance_007"
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)]"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>
        <div>
          <label htmlFor="assign-reason" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            {isReassign ? 'Reason' : 'Reason (optional)'}
          </label>
          <textarea
            id="assign-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder={isReassign ? 'Why is this case being reassigned?' : 'Optional notes…'}
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>
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
