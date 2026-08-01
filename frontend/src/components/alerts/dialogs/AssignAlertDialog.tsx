// src/components/alerts/dialogs/AssignAlertDialog.tsx
import React, { useEffect, useState } from 'react';
import { Modal } from '../../ui/Modal';
import { alertsApi } from '../../../api/alertsApi';
import { adminApi } from '../../../api/adminApi';
import { parseAlertError } from '../alertErrors';
import type { Alert } from '../../../types/alerts';
import type { AdminUserRow } from '../../../types/api';

interface Props {
  alert: Alert;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  onConflict: () => void;
}

export function AssignAlertDialog({ alert, open, onClose, onSuccess, onConflict }: Props) {
  const [candidates, setCandidates] = useState<AdminUserRow[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [assignedTo, setAssignedTo] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isReassignment = Boolean(alert.assigned_to) && alert.assigned_to !== assignedTo;
  const isReopen = alert.status === 'dismissed' || alert.status === 'resolved';
  const reasonRequired = isReassignment || isReopen;

  useEffect(() => {
    if (!open) return;
    setAssignedTo('');
    setReason('');
    setError(null);
    setSubmitting(false);
    setLoadingUsers(true);
    (async () => {
      try {
        const [analysts, compliance] = await Promise.all([
          adminApi.getUsers(1, 100, 'analyst', 'active'),
          adminApi.getUsers(1, 100, 'compliance', 'active'),
        ]);
        const seen = new Set<string>();
        const merged: AdminUserRow[] = [];
        for (const u of [...analysts.items, ...compliance.items]) {
          if (!seen.has(u.user_id)) { seen.add(u.user_id); merged.push(u); }
        }
        setCandidates(merged);
      } catch {
        setError('Unable to load candidate users.');
      } finally {
        setLoadingUsers(false);
      }
    })();
  }, [open, alert]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignedTo || submitting) return;
    if (reasonRequired && !reason.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await alertsApi.assign(alert.alert_id, {
        assigned_to: assignedTo,
        expected_version: alert.version,
        reason: reason.trim() || undefined,
      });
      onClose();
      onSuccess();
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
      title="Assign Alert"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          <button type="submit" form="assign-form"
            disabled={submitting || !assignedTo || (reasonRequired && !reason.trim())}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}>
            {submitting ? 'Assigning…' : 'Assign'}
          </button>
        </>
      }
    >
      <form id="assign-form" onSubmit={submit} className="space-y-4">
        <div className="text-xs flex items-center justify-between" style={{ color: 'var(--text-muted)' }}>
          <span>Current assignee: <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>{alert.assigned_to ?? 'unassigned'}</span></span>
          <span>Version: <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>{alert.version}</span></span>
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Assign To *
          </label>
          {loadingUsers ? (
            <div className="h-9 rounded-lg animate-pulse" style={{ background: 'var(--bg-tertiary)' }} />
          ) : (
            <select
              value={assignedTo}
              onChange={(e) => setAssignedTo(e.target.value)}
              className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)]"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
            >
              <option value="">Select an active analyst or compliance user…</option>
              {candidates.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.user_id} — {u.name ?? u.email} ({u.role})
                </option>
              ))}
            </select>
          )}
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
            Reason {reasonRequired ? '*' : '(optional)'}
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            placeholder={reasonRequired ? 'Required for reassignment or reopening' : 'Optional note'}
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
