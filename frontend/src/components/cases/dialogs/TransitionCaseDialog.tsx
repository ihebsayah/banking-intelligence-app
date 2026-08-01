// src/components/cases/dialogs/TransitionCaseDialog.tsx
import React, { useState } from 'react';
import { Modal } from '../../ui/Modal';
import { casesApi } from '../../../api/casesApi';
import { parseCaseError } from '../caseErrors';
import type { Case } from '../../../types/cases';

interface Props {
  open: boolean;
  title: string;
  body: React.ReactNode;
  confirmLabel: string;
  caseData: Case;
  target: string;
  withResolution?: boolean;
  resolutionRequired?: boolean;
  onClose: () => void;
  onSuccess: (c: Case) => void;
  onConflict: () => void;
}

export function TransitionCaseDialog({
  open, title, body, confirmLabel, caseData, target, withResolution = false, resolutionRequired = false,
  onClose, onSuccess, onConflict,
}: Props) {
  const [resolution, setResolution] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (submitting) return;
    if (resolutionRequired && !resolution.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await casesApi.transition(caseData.case_id, {
        target_status: target,
        ...(withResolution && resolution.trim() ? { resolution: resolution.trim() } : {}),
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
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          <button onClick={submit} disabled={submitting || (resolutionRequired && !resolution.trim())}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}>
            {submitting ? 'Submitting…' : confirmLabel}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{body}</div>
        {withResolution && (
          <div>
            <label htmlFor="resolution-text" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
              {resolutionRequired ? 'Resolution *' : 'Resolution'}
            </label>
            <textarea
              id="resolution-text"
              value={resolution}
              onChange={(e) => setResolution(e.target.value)}
              rows={3}
              placeholder="Optional resolution notes…"
              className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
            />
          </div>
        )}
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
