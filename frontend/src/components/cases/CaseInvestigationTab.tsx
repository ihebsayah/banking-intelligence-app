// src/components/cases/CaseInvestigationTab.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, FileSearch, Undo2 } from 'lucide-react';
import { investigationsApi } from '../../api/investigationsApi';
import { parseInvestigationError } from '../investigations/investigationErrors';
import { ConfirmTransitionDialog } from '../investigations/dialogs/ConfirmTransitionDialog';
import { ReturnInvestigationDialog } from '../investigations/dialogs/ReturnInvestigationDialog';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { InvestigationPriorityBadge, InvestigationStatusBadge } from '../investigations/InvestigationBadges';
import { formatDateTime } from '../../utils/formatters';
import type { Investigation } from '../../types/investigations';

interface Props {
  investigationId?: string | null;
}

export function CaseInvestigationTab({ investigationId }: Props) {
  const { hasPermission } = useAuth();
  const canReview = hasPermission(PERMISSIONS.INVESTIGATION_REVIEW);
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<'approve' | 'return' | null>(null);

  const fetchInvestigation = useCallback(async () => {
    if (!investigationId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await investigationsApi.get(investigationId);
      setInvestigation(data);
    } catch (err) {
      setError(parseInvestigationError(err).message);
      setInvestigation(null);
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  useEffect(() => { fetchInvestigation(); }, [fetchInvestigation]);

  if (error && !investigation) {
    return (
      <div className="rounded-2xl border p-8 flex flex-col items-center gap-3 text-center"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
        <AlertTriangle size={24} style={{ color: 'var(--accent-amber)' }} />
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{error}</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-14 border rounded-xl animate-pulse"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
        ))}
      </div>
    );
  }

  if (!investigation) {
    return (
      <div className="rounded-2xl border p-10 flex flex-col items-center gap-3 text-center"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
        <FileSearch size={24} style={{ color: 'var(--text-muted)' }} />
        <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
          No linked investigation
        </p>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          This case has not been linked to an investigation.
        </p>
      </div>
    );
  }

  const isSubmitted = investigation.status === 'submitted';

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border p-5"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
        <div className="flex items-center gap-2 flex-wrap mb-3">
          <InvestigationStatusBadge status={investigation.status} />
          <InvestigationPriorityBadge priority={investigation.priority} />
          <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
            v{investigation.version}
          </span>
          <span className="text-[10px]" style={{ color: 'var(--text-subtle)' }}>
            updated {formatDateTime(investigation.updated_at)}
          </span>
        </div>

        {isSubmitted && canReview && (
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <button
              onClick={() => setDialog('approve')}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
              style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
            >
              <CheckCircle2 size={14} /> Approve Investigation
            </button>
            <button
              onClick={() => setDialog('return')}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
              style={{ background: 'rgba(217,119,6,0.9)', color: 'var(--text-primary)' }}
            >
              <Undo2 size={14} /> Return Investigation
            </button>
          </div>
        )}

        <div className="space-y-4">
          <div>
            <h4 className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
              Findings
            </h4>
            <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
              {investigation.findings_text?.trim() || 'No findings recorded.'}
            </p>
          </div>

          {(investigation.findings_refs?.length ?? 0) > 0 && (
            <div>
              <h4 className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                References
              </h4>
              <ul className="space-y-1">
                {investigation.findings_refs?.map((ref, i) => (
                  <li key={i} className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                      {ref.type}:{ref.id}
                    </span>
                    {ref.description ? ` — ${ref.description}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h4 className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
              Conclusion
            </h4>
            <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
              {investigation.conclusion?.trim() || 'No conclusion recorded.'}
            </p>
          </div>

          {investigation.return_reason && (
            <div className="rounded-lg border px-3 py-2" style={{ background: 'rgba(217,119,6,0.08)', borderColor: 'rgba(217,119,6,0.3)' }}>
              <p className="text-[10px] font-bold uppercase tracking-wider mb-0.5" style={{ color: 'var(--accent-amber)' }}>
                Returned
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{investigation.return_reason}</p>
            </div>
          )}
        </div>
      </div>

      {investigation && (
        <>
          <ConfirmTransitionDialog
            open={dialog === 'approve'}
            title="Approve Investigation"
            body="Approve this submitted investigation. It will be marked complete and closed."
            confirmLabel="Approve"
            investigation={investigation}
            target="completed"
            onClose={() => setDialog(null)}
            onSuccess={setInvestigation}
            onConflict={fetchInvestigation}
          />
          <ReturnInvestigationDialog
            open={dialog === 'return'}
            investigation={investigation}
            onClose={() => setDialog(null)}
            onSuccess={setInvestigation}
            onConflict={fetchInvestigation}
          />
        </>
      )}
    </div>
  );
}
