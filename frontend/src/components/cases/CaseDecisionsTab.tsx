// src/components/cases/CaseDecisionsTab.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { Gavel } from 'lucide-react';
import { casesApi } from '../../api/casesApi';
import { parseCaseError } from './caseErrors';
import { DecisionForm } from './dialogs/DecisionForm';
import { DecisionTypeBadge } from './CaseBadges';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { StatusBadge } from '../ui/StatusBadge';
import { formatDateTime } from '../../utils/formatters';
import type { Case, Decision } from '../../types/cases';

interface Props {
  caseData: Case;
  onRecorded: (c: Case) => void;
  onConflict: () => void;
}

export function CaseDecisionsTab({ caseData, onRecorded, onConflict }: Props) {
  const { hasPermission } = useAuth();
  const canDecide = hasPermission(PERMISSIONS.CASE_DECISION);

  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDecisions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await casesApi.listDecisions(caseData.case_id);
      setDecisions(res.data);
    } catch (err) {
      setError(parseCaseError(err).message);
      setDecisions([]);
    } finally {
      setLoading(false);
    }
  }, [caseData.case_id]);

  useEffect(() => { fetchDecisions(); }, [fetchDecisions, caseData.status]);

  const showForm = canDecide && caseData.status === 'decision_pending';

  return (
    <div className="space-y-4">
      {showForm && (
        <DecisionForm
          caseData={caseData}
          onRecorded={(c) => { onRecorded(c); fetchDecisions(); }}
          onConflict={onConflict}
        />
      )}

      {error ? (
        <div className="rounded-2xl border p-8 text-center text-sm"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
          {error}
        </div>
      ) : loading && decisions.length === 0 ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-14 border rounded-xl animate-pulse"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
          ))}
        </div>
      ) : decisions.length === 0 ? (
        <div className="rounded-2xl border p-10 flex flex-col items-center gap-3 text-center"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
          <Gavel size={24} style={{ color: 'var(--text-muted)' }} />
          <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>No decisions recorded</p>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Decisions appear here once recorded from the decision form.
          </p>
        </div>
      ) : (
        <div className="rounded-2xl border divide-y divide-[var(--bg-border)]"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
          {decisions.map((d) => (
            <div key={d.decision_id} className="p-4">
              <div className="flex items-center gap-2 flex-wrap mb-1.5">
                <DecisionTypeBadge decisionType={d.decision_type} />
                {d.is_final && (
                  <StatusBadge variant="green">final</StatusBadge>
                )}
                <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  by {d.decided_by}
                </span>
                <span className="font-mono text-[10px]" style={{ color: 'var(--text-subtle)' }}>
                  {formatDateTime(d.decided_at)}
                </span>
              </div>
              <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                {d.rationale}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
