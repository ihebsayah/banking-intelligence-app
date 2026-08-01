// src/components/cases/dialogs/IRAcceptReturnDialog.tsx
import React, { useState } from 'react';
import { Modal } from '../../ui/Modal';
import { casesApi } from '../../../api/casesApi';
import { parseCaseError } from '../caseErrors';
import type { InformationRequest } from '../../../types/cases';

interface Props {
  open: boolean;
  mode: 'accept' | 'return';
  ir: InformationRequest | null;
  onClose: () => void;
  onSuccess: () => void;
  onConflict: () => void;
}

export function IRAcceptReturnDialog({ open, mode, ir, onClose, onSuccess, onConflict }: Props) {
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isReturn = mode === 'return';

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ir || submitting) return;
    if (isReturn && !note.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      if (isReturn) {
        await casesApi.returnInformationRequest(ir.ir_id, {
          return_reason: note.trim(),
          expected_version: ir.version,
        });
      } else {
        await casesApi.acceptInformationRequest(ir.ir_id, {
          ...(note.trim() ? { acceptance_note: note.trim() } : {}),
          expected_version: ir.version,
        });
      }
      setNote('');
      onClose();
      onSuccess();
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

  if (!ir) return null;

  return (
    <Modal
      open={open}
      title={isReturn ? 'Return Response' : 'Accept Response'}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          <button type="submit" form="ir-action-form" disabled={submitting || (isReturn && !note.trim())}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: isReturn ? 'rgba(217,119,6,0.9)' : 'var(--accent-green)', color: 'var(--text-primary)' }}>
            {submitting ? 'Submitting…' : isReturn ? 'Return for Revision' : 'Accept'}
          </button>
        </>
      }
    >
      <form id="ir-action-form" onSubmit={submit} className="space-y-4">
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>
          {isReturn
            ? 'The response is returned to the analyst for rework, with the reason below.'
            : 'Accepting this response records it against the case.'}
        </p>
        {ir.question && (
          <div className="rounded-lg border px-3 py-2" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Question</p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{ir.question}</p>
          </div>
        )}
        <div>
          <label htmlFor="ir-action-note" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            {isReturn ? 'Return reason *' : 'Acceptance note (optional)'}
          </label>
          <textarea
            id="ir-action-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            placeholder={isReturn ? 'What needs to change?' : 'Optional note…'}
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
