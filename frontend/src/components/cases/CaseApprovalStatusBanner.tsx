// src/components/cases/CaseApprovalStatusBanner.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert, CheckCircle2 } from 'lucide-react';
import { approvalsApi } from '../../api/approvalsApi';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { approvalActionLabel } from '../approvals/approvalLabels';
import type { ApprovalRequest } from '../../types/alerts';

interface Props {
  caseId: string;
}

const RELEVANT_ACTION_TYPES = ['case_closure_critical_high', 'case_reopen', 'decision_report_to_authority'];

export function CaseApprovalStatusBanner({ caseId }: Props) {
  const { hasPermission } = useAuth();
  const canReadApprovals = hasPermission(PERMISSIONS.APPROVAL_READ);

  const [requests, setRequests] = useState<ApprovalRequest[]>([]);

  const fetchApprovals = useCallback(async () => {
    if (!canReadApprovals) return;
    try {
      const res = await approvalsApi.list({ status: 'pending', perPage: 100 });
      const relevant = res.items.filter(
        (a) => a.entity_type === 'compliance_case' && a.entity_id === caseId
      );
      const withApproved = await approvalsApi.list({ status: 'approved', perPage: 100 });
      const relevantApproved = withApproved.items.filter(
        (a) =>
          a.entity_type === 'compliance_case' &&
          a.entity_id === caseId &&
          !a.executed_at
      );
      setRequests([...relevant, ...relevantApproved]);
    } catch {
      // transient — indicator is non-blocking
    }
  }, [canReadApprovals, caseId]);

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  if (!canReadApprovals || requests.length === 0) return null;

  const relevant = requests.filter((a) => RELEVANT_ACTION_TYPES.includes(a.action_type));
  if (relevant.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl border"
      style={{ background: 'rgba(217,119,6,0.08)', borderColor: 'rgba(217,119,6,0.25)' }}>
      <div className="flex items-center gap-2.5 flex-1 min-w-0">
        {relevant.some((a) => a.status === 'approved') ? (
          <CheckCircle2 size={16} style={{ color: 'var(--accent-green)' }} />
        ) : (
          <ShieldAlert size={16} style={{ color: 'var(--accent-amber)' }} />
        )}
        <div className="min-w-0">
          {relevant.map((a) => (
            <p key={a.approval_request_id} className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
              {a.status === 'approved'
                ? `Approval granted for ${approvalActionLabel(a.action_type).toLowerCase()} — ready to execute.`
                : `4-eyes approval pending for ${approvalActionLabel(a.action_type).toLowerCase()} (${a.approval_count}/${a.required_approvals}).`}
            </p>
          ))}
        </div>
      </div>
      <Link
        to="/workbench/approvals"
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--accent-amber)' }}
      >
        <ShieldAlert size={13} /> View Approval
      </Link>
    </div>
  );
}
