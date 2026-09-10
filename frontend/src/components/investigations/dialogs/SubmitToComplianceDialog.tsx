// src/components/investigations/dialogs/SubmitToComplianceDialog.tsx
import React, { useEffect, useState } from 'react';
import { Modal } from '../../ui/Modal';
import { investigationsApi } from '../../../api/investigationsApi';
import { parseInvestigationError } from '../investigationErrors';
import type { EligibleComplianceOfficer, Investigation } from '../../../types/investigations';

interface Props {
  open: boolean;
  investigation: Investigation;
  onClose: () => void;
  onSuccess: (inv: Investigation) => void;
  onConflict: () => void;
}

export function SubmitToComplianceDialog({
  open, investigation, onClose, onSuccess, onConflict,
}: Props) {
  const [officers, setOfficers] = useState<EligibleComplianceOfficer[]>([]);
  const [selectedOfficer, setSelectedOfficer] = useState('');
  const [loadingOfficers, setLoadingOfficers] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoadingOfficers(true);
    setError(null);
    setSelectedOfficer('');
    investigationsApi.listEligibleComplianceOfficers()
      .then((data) => {
        setOfficers(data);
        if (data.length === 1) setSelectedOfficer(data[0].user_id);
      })
      .catch(() => setError('Failed to load eligible Compliance Officers.'))
      .finally(() => setLoadingOfficers(false));
  }, [open]);

  const submit = async () => {
    if (submitting || !selectedOfficer) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await investigationsApi.submitToCompliance(investigation.investigation_id, {
        compliance_officer_id: selectedOfficer,
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

  const selectedName = officers.find((o) => o.user_id === selectedOfficer)?.name ?? selectedOfficer;

  return (
    <Modal
      open={open}
      title="Submit to Compliance Review"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          <button onClick={submit} disabled={submitting || !selectedOfficer || loadingOfficers}
            className="px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}>
            {submitting ? 'Submitting…' : 'Submit for Review'}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          Submit this investigation for compliance review. Once submitted, the selected
          Compliance Officer will be assigned and you will not be able to edit the report.
        </p>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider mb-1.5"
            style={{ color: 'var(--text-muted)' }}>
            Select Compliance Officer
          </label>
          {loadingOfficers ? (
            <div className="h-9 rounded-lg border animate-pulse"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }} />
          ) : officers.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              No eligible Compliance Officers available.
            </p>
          ) : (
            <select
              value={selectedOfficer}
              onChange={(e) => setSelectedOfficer(e.target.value)}
              aria-label="Select Compliance Officer"
              className="w-full rounded-lg px-3 py-2 text-xs outline-none border focus:border-[var(--accent-blue)]"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
            >
              <option value="">— Select an officer —</option>
              {officers.map((o) => (
                <option key={o.user_id} value={o.user_id}>{o.name} ({o.email})</option>
              ))}
            </select>
          )}
        </div>

        {selectedOfficer && (
          <div className="px-3 py-2 rounded-lg border text-xs"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
            Submit to: <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{selectedName}</span>
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
