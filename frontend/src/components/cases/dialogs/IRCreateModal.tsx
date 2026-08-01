// src/components/cases/dialogs/IRCreateModal.tsx
import React, { useState } from 'react';
import { Modal } from '../../ui/Modal';
import { casesApi } from '../../../api/casesApi';
import { parseCaseError } from '../caseErrors';
import type { Case } from '../../../types/cases';

interface Props {
  open: boolean;
  caseData: Case;
  onClose: () => void;
  onSuccess: () => void;
  onConflict: () => void;
}

export function IRCreateModal({ open, caseData, onClose, onSuccess, onConflict }: Props) {
  const [assignedTo, setAssignedTo] = useState('');
  const [question, setQuestion] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignedTo.trim() || !question.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await casesApi.createInformationRequest(caseData.case_id, {
        assigned_to: assignedTo.trim(),
        question: question.trim(),
        ...(dueDate ? { due_date: dueDate } : {}),
        expected_case_version: caseData.version,
      });
      setAssignedTo('');
      setQuestion('');
      setDueDate('');
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

  return (
    <Modal
      open={open}
      title="Request Information"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          <button type="submit" form="ir-create-form" disabled={submitting || !assignedTo.trim() || !question.trim()}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}>
            {submitting ? 'Creating…' : 'Create Request'}
          </button>
        </>
      }
    >
      <form id="ir-create-form" onSubmit={submit} className="space-y-4">
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          Assigning a request moves the case to awaiting information. The analyst is notified once assigned.
        </p>
        <div>
          <label htmlFor="ir-assignee" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Assigned analyst (user id) *
          </label>
          <input
            id="ir-assignee"
            value={assignedTo}
            onChange={(e) => setAssignedTo(e.target.value)}
            placeholder="e.g. analyst_002"
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)]"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>
        <div>
          <label htmlFor="ir-question" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Question *
          </label>
          <textarea
            id="ir-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={4}
            placeholder="What information is needed?"
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>
        <div>
          <label htmlFor="ir-due" className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Due date (optional)
          </label>
          <input
            id="ir-due"
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)]"
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
