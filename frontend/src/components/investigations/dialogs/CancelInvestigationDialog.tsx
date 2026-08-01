// src/components/investigations/dialogs/CancelInvestigationDialog.tsx
import React, { useState } from 'react';
import { Modal } from '../../ui/Modal';
import { investigationsApi } from '../../../api/investigationsApi';
import { parseInvestigationError } from '../investigationErrors';
import type { Investigation } from '../../../types/investigations';

interface Props {
  open: boolean;
  investigation: Investigation;
  onClose: () => void;
  onSuccess: (inv: Investigation) => void;
  onConflict: () => void;
}

export function CancelInvestigationDialog({ open, investigation, onClose, onSuccess, onConflict }: Props) {
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await investigationsApi.cancel(investigation.investigation_id, {
        cancel_reason: reason.trim(),
        expected_version: investigation.version,
      });
      onClose();
      onSuccess(res.investigation);
    } catch (err) {
      const parsed = parseInvestigationError(err);
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
      title="Cancel Investigation"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Back
          </button>
          <button type="submit" form="cancel-form" disabled={submitting || !reason.trim()}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-red)', color: 'var(--text-primary)' }}>
            {submitting ? 'Cancelling…' : 'Cancel Investigation'}
          </button>
        </>
      }
    >
      <form id="cancel-form" onSubmit={submit} className="space-y-4">
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          This action is <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>audited</span> and cannot be
          undone. The investigation is <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>not deleted</span> —
          it moves to <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>cancelled</span> and the assigned
          analyst is notified. The linked alert is not affected.
        </p>
        <div>
          <label htmlFor="cancel-reason" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Cancellation reason *
          </label>
          <textarea
            id="cancel-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="Why is this investigation being cancelled?"
            aria-describedby={error ? 'cancel-error' : undefined}
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>
        {error && (
          <div id="cancel-error" role="alert" className="px-3 py-2 rounded-lg border text-xs"
            style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
            {error}
          </div>
        )}
      </form>
    </Modal>
  );
}
