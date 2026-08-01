// src/components/investigations/InvestigationDetailPage.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, RefreshCw, AlertTriangle, CheckCircle2, PlayCircle,
  Flag, Undo2, XCircle, Link2, Eye,
} from 'lucide-react';
import { clsx } from 'clsx';
import { BankingHeader } from '../Layout/BankingHeader';
import { investigationsApi } from '../../api/investigationsApi';
import { InvestigationPriorityBadge, InvestigationStatusBadge } from './InvestigationBadges';
import { parseInvestigationError } from './investigationErrors';
import { FindingsEditor } from './FindingsEditor';
import { CommentsTab } from './CommentsTab';
import { TimelineTab } from './TimelineTab';
import { ConfirmTransitionDialog } from './dialogs/ConfirmTransitionDialog';
import { ReturnInvestigationDialog } from './dialogs/ReturnInvestigationDialog';
import { CancelInvestigationDialog } from './dialogs/CancelInvestigationDialog';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { formatDateTime } from '../../utils/formatters';
import type { Investigation } from '../../types/investigations';

type Tab = 'overview' | 'findings' | 'comments' | 'timeline';
type Dialog = 'submit' | 'complete' | 'approve' | 'return' | 'cancel' | null;

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'findings', label: 'Findings' },
  { id: 'comments', label: 'Comments' },
  { id: 'timeline', label: 'Timeline' },
];

function hasFindings(inv: Investigation): boolean {
  return Boolean(inv.findings_text?.trim()) || (inv.findings_refs?.length ?? 0) > 0;
}

function hasConclusion(inv: Investigation): boolean {
  return Boolean(inv.conclusion?.trim());
}

function workflowGuidance(status: Investigation['status']): string {
  switch (status) {
    case 'open': return 'Start the investigation to begin work on it.';
    case 'active': return 'Record findings and a conclusion, then submit for review.';
    case 'awaiting_information': return 'Awaiting information — resumes from the Information Request workflow (Phase 2D).';
    case 'submitted': return 'Submitted for compliance review.';
    case 'returned': return 'Rework the findings and resume the investigation.';
    case 'completed': return 'Investigation complete — read-only.';
    case 'cancelled': return 'Investigation cancelled — read-only.';
  }
}

export function InvestigationDetailPage() {
  const { investigationId } = useParams<{ investigationId: string }>();
  const navigate = useNavigate();
  const { applicationUser, hasPermission, hasRole } = useAuth();

  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [tab, setTab] = useState<Tab>('overview');
  const [dialog, setDialog] = useState<Dialog>(null);
  const [acting, setActing] = useState(false);
  const [dirty, setDirty] = useState(false);

  const fetchInvestigation = useCallback(async () => {
    if (!investigationId) return;
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

  // Unsaved-changes guard: warn on tab close and on the page's own navigation
  // actions (the app uses a non-data BrowserRouter, so useBlocker is unavailable).
  const confirmLeave = () => {
    if (!dirty) return true;
    return window.confirm('You have unsaved findings. Leave without saving?');
  };

  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  const onMutationConflict = useCallback(() => {
    setConflict(true);
    fetchInvestigation();
  }, [fetchInvestigation]);

  const runDirectTransition = async (target: 'active') => {
    if (!investigation || acting) return;
    setActing(true);
    try {
      const res = await investigationsApi.transition(investigation.investigation_id, {
        target_status: target,
        expected_version: investigation.version,
      });
      setInvestigation(res.investigation);
    } catch (err) {
      if (parseInvestigationError(err).kind === 'conflict') {
        onMutationConflict();
      } else {
        setError(parseInvestigationError(err).message);
      }
    } finally {
      setActing(false);
    }
  };

  if (loading && !investigation) {
    return (
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        <BankingHeader title="Investigation Detail" subtitle="Loading…" isRefreshing />
        <div className="flex-1 p-6 max-w-[1200px] mx-auto w-full space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 border rounded-xl animate-pulse"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
          ))}
        </div>
      </div>
    );
  }

  if (!investigation) {
    return (
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        <BankingHeader title="Investigation Detail" subtitle="Not available" />
        <div className="flex-1 p-6 max-w-[1200px] mx-auto w-full">
          <div className="rounded-2xl border p-12 flex flex-col items-center gap-3 text-center"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <AlertTriangle size={28} style={{ color: 'var(--accent-red)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>{error ?? 'Investigation not found.'}</p>
            <button
              onClick={() => navigate('/workbench/investigations')}
              className="mt-2 flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold shadow-md hover:brightness-90 transition-all"
              style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
            >
              <ArrowLeft size={14} /> Back to queue
            </button>
          </div>
        </div>
      </div>
    );
  }

  const s = investigation.status;
  const isAssignee = Boolean(applicationUser?.user_id && investigation.assigned_to === applicationUser.user_id);
  const canEditFindings = hasPermission(PERMISSIONS.INVESTIGATION_MODIFY_FINDINGS)
    && isAssignee && (s === 'active' || s === 'returned');
  const canTransition = hasPermission(PERMISSIONS.INVESTIGATION_TRANSITION) && isAssignee;
  const canReview = hasPermission(PERMISSIONS.INVESTIGATION_REVIEW);
  const canCancel = hasPermission(PERMISSIONS.INVESTIGATION_ASSIGN) && hasRole('admin');

  const showSubmit = canTransition && s === 'active' && hasFindings(investigation);
  const showComplete = canTransition && s === 'active' && hasFindings(investigation) && hasConclusion(investigation);
  const showApprove = canReview && s === 'submitted';
  const showReturn = canReview && s === 'submitted';
  const showCancel = canCancel && s !== 'completed' && s !== 'cancelled';
  const showStart = canTransition && s === 'open';
  const showResume = canTransition && s === 'returned';

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title={investigation.title}
        subtitle={`Investigation · created ${formatDateTime(investigation.created_at)}`}
        onRefresh={fetchInvestigation}
        isRefreshing={loading}
        actions={
          <button
            onClick={() => { if (confirmLeave()) navigate('/workbench/investigations'); }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
          >
            <ArrowLeft size={13} /> Queue
          </button>
        }
      />

      <div className="flex-1 p-6 space-y-5 overflow-y-auto max-w-[1200px] mx-auto w-full">
        {/* Optimistic-lock conflict banner */}
        {conflict && (
          <div className="flex items-center justify-between gap-4 px-4 py-3 rounded-xl border"
            style={{ background: 'rgba(217,119,6,0.08)', borderColor: 'rgba(217,119,6,0.25)' }}>
            <div className="flex items-center gap-2.5">
              <AlertTriangle size={16} style={{ color: 'var(--accent-amber)' }} />
              <p className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                Investigation was updated by someone else. Your unsaved changes are preserved — review and re-save.
              </p>
            </div>
            <button
              onClick={() => { setConflict(false); fetchInvestigation(); }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
            >
              <RefreshCw size={13} /> Refresh
            </button>
          </div>
        )}

        {/* Header row: badges + version */}
        <div className="flex flex-wrap items-center gap-2">
          <InvestigationStatusBadge status={s} />
          <InvestigationPriorityBadge priority={investigation.priority} />
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
            v{investigation.version}
          </span>
          {investigation.assigned_to && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
              assigned to {investigation.assigned_to}
            </span>
          )}
        </div>

        {/* Returned investigation banner */}
        {s === 'returned' && (
          <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl border"
            style={{ background: 'rgba(217,119,6,0.1)', borderColor: 'rgba(217,119,6,0.35)' }}>
            <Undo2 size={16} style={{ color: 'var(--accent-amber)' }} />
            <p className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
              Investigation returned — reason: {investigation.return_reason ?? 'not provided'}
            </p>
          </div>
        )}

        {/* Tabs */}
        <div role="tablist" aria-label="Investigation sections"
          className="flex items-center gap-1 border-b" style={{ borderColor: 'var(--bg-border)' }}>
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              role="tab"
              id={`tab-${id}`}
              aria-selected={tab === id}
              aria-controls={`panel-${id}`}
              onClick={() => setTab(id)}
              className={clsx('px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)]',
                tab === id ? 'text-[var(--accent-blue)]' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]')}
              style={{ borderColor: tab === id ? 'var(--accent-blue)' : 'transparent' }}
            >
              {label}
            </button>
          ))}
        </div>

        <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
          {tab === 'overview' && (
            <div className="space-y-5">
              {/* Action bar */}
              {(showStart || showSubmit || showComplete || showApprove || showReturn || showCancel || showResume) && (
                <div className="flex flex-wrap items-center gap-2">
                  {showStart && (
                    <button
                      onClick={() => runDirectTransition('active')}
                      disabled={acting}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-50"
                      style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
                    >
                      <PlayCircle size={14} /> {acting ? 'Starting…' : 'Start Investigation'}
                    </button>
                  )}
                  {showSubmit && (
                    <button
                      onClick={() => setDialog('submit')}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                      style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
                    >
                      <Flag size={14} /> Submit for Review
                    </button>
                  )}
                  {showComplete && (
                    <button
                      onClick={() => setDialog('complete')}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                      style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
                    >
                      <CheckCircle2 size={14} /> Complete
                    </button>
                  )}
                  {showResume && (
                    <button
                      onClick={() => runDirectTransition('active')}
                      disabled={acting}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-50"
                      style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
                    >
                      <PlayCircle size={14} /> {acting ? 'Resuming…' : 'Mark Revision Started'}
                    </button>
                  )}
                  {showApprove && (
                    <button
                      onClick={() => setDialog('approve')}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                      style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
                    >
                      <CheckCircle2 size={14} /> Approve
                    </button>
                  )}
                  {showReturn && (
                    <button
                      onClick={() => setDialog('return')}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                      style={{ background: 'rgba(217,119,6,0.9)', color: 'var(--text-primary)' }}
                    >
                      <Undo2 size={14} /> Return for Revision
                    </button>
                  )}
                  {showCancel && (
                    <button
                      onClick={() => setDialog('cancel')}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
                      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--accent-red)' }}
                    >
                      <XCircle size={14} /> Cancel Investigation
                    </button>
                  )}
                </div>
              )}

              {/* Workflow guidance */}
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl border"
                style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                <Eye size={14} style={{ color: 'var(--text-muted)' }} />
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  <span className="font-semibold" style={{ color: 'var(--text-muted)' }}>Next:</span> {workflowGuidance(s)}
                </p>
              </div>

              {/* Description */}
              <div className="rounded-2xl border p-5"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
                <h3 className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                  Description
                </h3>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                  {investigation.description || 'No description provided.'}
                </p>
              </div>

              {/* Linked alert */}
              {investigation.alert_id && (
                <button
                  onClick={() => { if (confirmLeave()) navigate(`/workbench/alerts/${investigation.alert_id}`); }}
                  className="rounded-2xl border p-4 w-full flex items-center gap-2.5 text-left transition-all hover:brightness-95"
                  style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
                >
                  <Link2 size={14} style={{ color: 'var(--text-muted)' }} />
                  <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                    Linked alert
                  </span>
                  <span className="font-mono text-xs" style={{ color: 'var(--accent-blue)' }}>
                    #{investigation.alert_id.slice(0, 8)}…
                  </span>
                </button>
              )}

              {/* Meta grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { label: 'Status', value: s.replace(/_/g, ' ') },
                  { label: 'Priority', value: investigation.priority },
                  { label: 'Assigned To', value: investigation.assigned_to ?? '—' },
                  { label: 'Created By', value: investigation.created_by },
                  { label: 'Scope', value: investigation.scope_id },
                  { label: 'Started', value: investigation.started_at ? formatDateTime(investigation.started_at) : '—' },
                  { label: 'Submitted', value: investigation.submitted_at ? formatDateTime(investigation.submitted_at) : '—' },
                  { label: 'Completed', value: investigation.completed_at ? formatDateTime(investigation.completed_at) : '—' },
                  { label: 'Created', value: formatDateTime(investigation.created_at) },
                  { label: 'Updated', value: formatDateTime(investigation.updated_at) },
                ].map((m) => (
                  <div key={m.label} className="rounded-xl border p-4"
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
                    <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                      {m.label}
                    </p>
                    <p className={clsx('text-xs', /(to|by|id|scope)/i.test(m.label) ? 'font-mono' : 'font-semibold')}
                      style={{ color: 'var(--text-secondary)' }}>
                      {m.value}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'findings' && (
            <div className="space-y-5">
              <FindingsEditor
                investigation={investigation}
                editable={canEditFindings}
                onSaved={setInvestigation}
                onConflict={onMutationConflict}
                onDirtyChange={setDirty}
              />
              <div className="rounded-2xl border p-5 opacity-70"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
                <h3 className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                  Evidence
                </h3>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  File evidence upload available in Phase 2D.
                </p>
              </div>
            </div>
          )}

          {tab === 'comments' && <CommentsTab investigationId={investigation.investigation_id} />}
          {tab === 'timeline' && <TimelineTab investigationId={investigation.investigation_id} />}
        </div>
      </div>

      {investigation && (
        <>
          <ConfirmTransitionDialog
            open={dialog === 'submit'}
            title="Submit for Review"
            body={
              <>
                <p>
                  The findings become <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>review-oriented</span> and
                  move to a compliance reviewer. You cannot edit findings while the investigation is under review.
                </p>
                <p className="mt-2">
                  This is a submission for review — it is <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>not</span> a final compliance approval.
                </p>
              </>
            }
            confirmLabel="Submit for Review"
            investigation={investigation}
            target="submitted"
            onClose={() => setDialog(null)}
            onSuccess={setInvestigation}
            onConflict={onMutationConflict}
          />
          <ConfirmTransitionDialog
            open={dialog === 'complete'}
            title="Complete Investigation"
            body="The investigation will be marked complete and closed to further edits."
            confirmLabel="Complete"
            investigation={investigation}
            target="completed"
            onClose={() => setDialog(null)}
            onSuccess={setInvestigation}
            onConflict={onMutationConflict}
          />
          <ConfirmTransitionDialog
            open={dialog === 'approve'}
            title="Approve Investigation"
            body="Approve this submitted investigation. It will be marked complete and closed."
            confirmLabel="Approve"
            investigation={investigation}
            target="completed"
            onClose={() => setDialog(null)}
            onSuccess={setInvestigation}
            onConflict={onMutationConflict}
          />
          <ReturnInvestigationDialog
            open={dialog === 'return'}
            investigation={investigation}
            onClose={() => setDialog(null)}
            onSuccess={setInvestigation}
            onConflict={onMutationConflict}
          />
          <CancelInvestigationDialog
            open={dialog === 'cancel'}
            investigation={investigation}
            onClose={() => setDialog(null)}
            onSuccess={setInvestigation}
            onConflict={onMutationConflict}
          />
        </>
      )}
    </div>
  );
}
