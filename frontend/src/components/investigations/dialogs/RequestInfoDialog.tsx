// src/components/investigations/dialogs/RequestInfoDialog.tsx
import React, { useState } from 'react';
import { Modal } from '../../ui/Modal';
import { informationRequestsApi } from '../../../api/informationRequestsApi';
import { parseInvestigationError } from '../investigationErrors';
import type { Investigation } from '../../../types/investigations';

interface Props {
  open: boolean;
  investigation: Investigation;
  onClose: () => void;
  onSuccess: () => void;
  onConflict: () => void;
}

export function RequestInfoDialog({ open, investigation, onClose, onSuccess, onConflict }: Props) {
  const defaultAssignee = investigation.assigned_to || investigation.created_by;
  const [assignedTo, setAssignedTo] = useState(defaultAssignee);
  const [question, setQuestion] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || !assignedTo.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await informationRequestsApi.createForInvestigation(investigation.investigation_id, {
        assigned_to: assignedTo.trim(),
        question: question.trim(),
        due_date: dueDate || null,
        expected_investigation_version: investigation.version,
      });
      onClose();
      onSuccess();
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
      title="Request Additional Information"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          <button type="submit" form="request-info-form" disabled={submitting || !question.trim() || !assignedTo.trim()}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}>
            {submitting ? 'Submitting…' : 'Send Information Request'}
          </button>
        </>
      }
    >
      <form id="request-info-form" onSubmit={submit} className="space-y-4">
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          Create an Information Request linked directly to this investigation. The investigation will move to <strong>awaiting_information</strong> until responded and accepted.
        </p>

        <div>
          <label htmlFor="assigned-to" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Assignee (Analyst) *
          </label>
          <input
            id="assigned-to"
            type="text"
            value={assignedTo}
            onChange={(e) => setAssignedTo(e.target.value)}
            required
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] font-mono"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>

        <div>
          <label htmlFor="ir-question" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Question / Requested Information *
          </label>
          <textarea
            id="ir-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={4}
            required
            placeholder="Specify what additional evidence or explanation is required..."
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>

        <div>
          <label htmlFor="due-date" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Due Date (Optional)
          </label>
          <input
            id="due-date"
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] font-mono"
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
