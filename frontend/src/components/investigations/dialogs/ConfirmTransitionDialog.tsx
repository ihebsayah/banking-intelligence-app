// src/components/investigations/dialogs/ConfirmTransitionDialog.tsx
import React, { useState } from 'react';
import { Modal } from '../../ui/Modal';
import { investigationsApi } from '../../../api/investigationsApi';
import { parseInvestigationError } from '../investigationErrors';
import type { Investigation, InvestigationStatus } from '../../../types/investigations';

interface Props {
  open: boolean;
  title: string;
  body: React.ReactNode;
  confirmLabel: string;
  investigation: Investigation;
  target: InvestigationStatus;
  onClose: () => void;
  onSuccess: (inv: Investigation) => void;
  onConflict: () => void;
}

export function ConfirmTransitionDialog({
  open, title, body, confirmLabel, investigation, target, onClose, onSuccess, onConflict,
}: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await investigationsApi.transition(investigation.investigation_id, {
        target_status: target,
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
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          <button onClick={submit} disabled={submitting}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}>
            {submitting ? 'Submitting…' : confirmLabel}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{body}</div>
        {error && (
          <div className="px-3 py-2 rounded-lg border text-xs"
            style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
            {error}
          </div>
        )}
      </div>
    </Modal>
  );
}
