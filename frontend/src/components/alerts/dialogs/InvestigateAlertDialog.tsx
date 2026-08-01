// src/components/alerts/dialogs/InvestigateAlertDialog.tsx
import React, { useState } from 'react';
import { Modal } from '../../ui/Modal';
import { alertsApi } from '../../../api/alertsApi';
import { parseAlertError } from '../alertErrors';
import type { Alert } from '../../../types/alerts';

interface Props {
  alert: Alert;
  open: boolean;
  onClose: () => void;
  onSuccess: (investigationId: string) => void;
  onConflict: () => void;
}

export function InvestigateAlertDialog({ alert, open, onClose, onSuccess, onConflict }: Props) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await alertsApi.investigate(alert.alert_id, {
        title: title.trim(),
        description: description.trim() || undefined,
        expected_version: alert.version,
      });
      onClose();
      onSuccess(res.investigation_id);
    } catch (err) {
      const parsed = parseAlertError(err);
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
      title="Create Investigation"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          <button type="submit" form="investigate-form" disabled={submitting || !title.trim()}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}>
            {submitting ? 'Creating…' : 'Create Investigation'}
          </button>
        </>
      }
    >
      <form id="investigate-form" onSubmit={submit} className="space-y-4">
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          An investigation will be created and the alert moves to <span className="font-semibold" style={{ color: 'var(--text-secondary)' }}>under investigation</span>.
        </p>
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Title *
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Short summary of the investigation"
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)]"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Optional context for the investigation"
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>
        {error && (
          <div className="px-3 py-2 rounded-lg border text-xs" style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
            {error}
          </div>
        )}
      </form>
    </Modal>
  );
}
