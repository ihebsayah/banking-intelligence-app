// src/components/investigations/dialogs/MarkNotHarmfulDialog.tsx
import React, { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
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

export function MarkNotHarmfulDialog({ open, investigation, onClose, onSuccess, onConflict }: Props) {
  const [rationale, setRationale] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = rationale.trim().length > 0 && !submitting;

  const reset = () => {
    setRationale('');
    setError(null);
    setSubmitting(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await investigationsApi.reviewNotHarmful(investigation.investigation_id, {
        rationale: rationale.trim(),
        expected_version: investigation.version,
      });
      reset();
      onClose();
      onSuccess(res.investigation);
    } catch (err) {
      const parsed = parseInvestigationError(err);
      if (parsed.kind === 'conflict') {
        handleClose();
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
      title="Mark Not Harmful"
      onClose={handleClose}
      footer={
        <>
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="not-harmful-form"
            disabled={!canSubmit}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
          >
            <CheckCircle2 size={13} />
            {submitting ? 'Marking…' : 'Mark Not Harmful'}
          </button>
        </>
      }
    >
      <form id="not-harmful-form" onSubmit={submit} className="space-y-4">
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          Compliance reviewed this investigation and determined the activity does{' '}
          <strong>not</strong> require a formal Compliance Case. The investigation will be{' '}
          <strong>completed</strong> and removed from the review queue.
        </p>

        {/* Read-only context */}
        <div className="rounded-xl border p-3 space-y-1"
          style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
          <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Investigation
          </p>
          <p className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
            {investigation.investigation_id}
          </p>
          {investigation.alert_id && (
            <>
              <p className="text-[10px] font-bold uppercase tracking-wider mt-2" style={{ color: 'var(--text-muted)' }}>
                Originating Alert
              </p>
              <p className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                {investigation.alert_id}
              </p>
            </>
          )}
        </div>

        <div>
          <label
            htmlFor="not-harmful-rationale"
            className="block text-[10px] font-bold uppercase tracking-wider mb-1"
            style={{ color: 'var(--text-muted)' }}
          >
            Rationale *
          </label>
          <textarea
            id="not-harmful-rationale"
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            rows={4}
            required
            placeholder="Explain why this investigation does not require further compliance action…"
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>

        {error && (
          <div
            role="alert"
            className="px-3 py-2 rounded-lg border text-xs"
            style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}
          >
            {error}
          </div>
        )}
      </form>
    </Modal>
  );
}
