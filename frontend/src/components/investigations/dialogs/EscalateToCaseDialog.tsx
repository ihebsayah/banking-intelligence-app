// src/components/investigations/dialogs/EscalateToCaseDialog.tsx
import React, { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, AlertTriangle } from 'lucide-react';
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

const PRIORITIES = ['low', 'medium', 'high', 'critical'] as const;

export function EscalateToCaseDialog({ open, investigation, onClose, onSuccess, onConflict }: Props) {
  const navigate = useNavigate();
  const [title, setTitle] = useState(investigation.title);
  const [priority, setPriority] = useState<string>('high');
  const [rationale, setRationale] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdCaseId, setCreatedCaseId] = useState<string | null>(null);
  const [completedInvestigation, setCompletedInvestigation] = useState<Investigation | null>(null);

  const canSubmit = title.trim().length > 0 && rationale.trim().length > 0 && !submitting;

  const reset = useCallback(() => {
    setTitle(investigation.title);
    setPriority('high');
    setRationale('');
    setError(null);
    setSubmitting(false);
    setCreatedCaseId(null);
    setCompletedInvestigation(null);
  }, [investigation.title]);

  const handleClose = () => {
    if (completedInvestigation) {
      onSuccess(completedInvestigation);
    }
    reset();
    onClose();
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await investigationsApi.escalateToCase(investigation.investigation_id, {
        title: title.trim(),
        priority,
        rationale: rationale.trim(),
        expected_version: investigation.version,
      });
      setCreatedCaseId(res.case_id);
      setCompletedInvestigation(res.investigation);
    } catch (err) {
      const parsed = parseInvestigationError(err);
      if (parsed.kind === 'conflict') {
        reset();
        onClose();
        onConflict();
      } else {
        setError(parsed.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Success state — case created
  if (createdCaseId && completedInvestigation) {
    return (
      <Modal
        open={open}
        title="Escalated to Compliance Case"
        onClose={handleClose}
        footer={
          <>
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
            >
              Close
            </button>
            <button
              type="button"
              onClick={() => {
                handleClose();
                navigate(`/workbench/cases/${createdCaseId}`);
              }}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
              style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
            >
              Go to Case <ArrowRight size={13} />
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div
            className="flex items-center gap-2.5 px-4 py-3 rounded-xl border"
            style={{ background: 'rgba(16,185,129,0.08)', borderColor: 'rgba(16,185,129,0.25)' }}
          >
            <AlertTriangle size={15} style={{ color: 'var(--accent-green)' }} />
            <p className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
              Compliance Case created successfully.
            </p>
          </div>
          <div className="rounded-xl border p-3 space-y-2"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                Case ID
              </p>
              <p className="text-xs font-mono mt-0.5" style={{ color: 'var(--accent-blue)' }}>
                {createdCaseId}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                Investigation
              </p>
              <p className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                {investigation.investigation_id} — now completed
              </p>
            </div>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      open={open}
      title="Escalate to Compliance Case"
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
            form="escalate-case-form"
            disabled={!canSubmit}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-red)', color: 'var(--text-primary)' }}
          >
            <ArrowRight size={13} />
            {submitting ? 'Escalating…' : 'Escalate to Case'}
          </button>
        </>
      }
    >
      <form id="escalate-case-form" onSubmit={submit} className="space-y-4">
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          This will create a formal <strong>Compliance Case</strong> linked to this investigation.
          The investigation will be <strong>completed</strong> and removed from the review queue.
        </p>

        {/* Read-only originating context */}
        <div className="rounded-xl border p-3 space-y-2"
          style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
          <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Originating Context (read-only)
          </p>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Investigation</p>
              <p className="text-[10px] font-mono mt-0.5 truncate" style={{ color: 'var(--text-secondary)' }}>
                {investigation.investigation_id.slice(0, 16)}…
              </p>
            </div>
            {investigation.alert_id && (
              <div>
                <p className="text-[9px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Alert</p>
                <p className="text-[10px] font-mono mt-0.5 truncate" style={{ color: 'var(--text-secondary)' }}>
                  {investigation.alert_id.slice(0, 16)}…
                </p>
              </div>
            )}
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Scope</p>
              <p className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                {investigation.scope_id}
              </p>
            </div>
          </div>
        </div>

        {/* Case title */}
        <div>
          <label
            htmlFor="escalate-title"
            className="block text-[10px] font-bold uppercase tracking-wider mb-1"
            style={{ color: 'var(--text-muted)' }}
          >
            Case Title *
          </label>
          <input
            id="escalate-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)]"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
        </div>

        {/* Priority */}
        <div>
          <label
            htmlFor="escalate-priority"
            className="block text-[10px] font-bold uppercase tracking-wider mb-1"
            style={{ color: 'var(--text-muted)' }}
          >
            Priority *
          </label>
          <select
            id="escalate-priority"
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)]"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>
        </div>

        {/* Rationale */}
        <div>
          <label
            htmlFor="escalate-rationale"
            className="block text-[10px] font-bold uppercase tracking-wider mb-1"
            style={{ color: 'var(--text-muted)' }}
          >
            Rationale / Summary *
          </label>
          <textarea
            id="escalate-rationale"
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            rows={4}
            required
            placeholder="Describe why this investigation requires formal compliance case handling…"
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
