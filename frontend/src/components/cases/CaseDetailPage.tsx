// src/components/cases/CaseDetailPage.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, RefreshCw, AlertTriangle, Eye, Link2, FileText,
  PlayCircle, MessageSquarePlus, Flag, CheckCircle2, Gavel, UserRoundPlus, CircleSlash2,
} from 'lucide-react';
import { clsx } from 'clsx';
import { BankingHeader } from '../Layout/BankingHeader';
import { casesApi } from '../../api/casesApi';
import { CasePriorityBadge, CaseRiskBadge, CaseStatusBadge } from './CaseBadges';
import { parseCaseError } from './caseErrors';
import { CaseInvestigationTab } from './CaseInvestigationTab';
import { CaseInformationRequestsTab } from './CaseInformationRequestsTab';
import { CaseDecisionsTab } from './CaseDecisionsTab';
import { CommentsTab } from '../investigations/CommentsTab';
import { TimelineTab } from '../investigations/TimelineTab';
import { TransitionCaseDialog } from './dialogs/TransitionCaseDialog';
import { AdminAssignCaseDialog } from './dialogs/AdminAssignCaseDialog';
import { IRCreateModal } from './dialogs/IRCreateModal';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { formatDateTime } from '../../utils/formatters';
import type { Case } from '../../types/cases';

type Tab = 'overview' | 'investigation' | 'ir' | 'decisions' | 'comments' | 'timeline';
type Dialog = 'begin_review' | 'decision_pending' | 'resolve' | 'assign' | 'ir_create' | null;

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'investigation', label: 'Investigation' },
  { id: 'ir', label: 'Information Requests' },
  { id: 'decisions', label: 'Decisions' },
  { id: 'comments', label: 'Comments' },
  { id: 'timeline', label: 'Timeline' },
];

function workflowGuidance(status: Case['status']): string {
  switch (status) {
    case 'open': return 'Awaiting assignment by an administrator.';
    case 'assigned': return 'Begin review to start working this case.';
    case 'under_review': return 'Review the linked investigation, request information if needed, then mark the case ready for a decision.';
    case 'awaiting_information': return 'Awaiting analyst information — resumes from the Information Request workflow (2B.14).';
    case 'decision_pending': return 'Record a decision on the Decisions tab.';
    case 'awaiting_compliance_action': return 'The required compliance action has been completed — resolve the case.';
    case 'resolved': return 'Case resolved — read-only. (Closure requires a close endpoint, deferred to Phase 2E.)';
    case 'closed': return 'Case closed — read-only.';
    case 'cancelled': return 'Case cancelled — read-only.';
  }
}

export function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const { applicationUser, hasPermission, hasRole } = useAuth();

  const [caseData, setCaseData] = useState<Case | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [tab, setTab] = useState<Tab>('overview');
  const [dialog, setDialog] = useState<Dialog>(null);
  const [irRefreshKey, setIrRefreshKey] = useState(0);

  const fetchCase = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await casesApi.get(caseId);
      setCaseData(data);
    } catch (err) {
      setError(parseCaseError(err).message);
      setCaseData(null);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { fetchCase(); }, [fetchCase]);

  const onMutationConflict = useCallback(() => {
    setConflict(true);
    fetchCase();
  }, [fetchCase]);

  if (loading && !caseData) {
    return (
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        <BankingHeader title="Case Detail" subtitle="Loading…" isRefreshing />
        <div className="flex-1 p-6 max-w-[1200px] mx-auto w-full space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 border rounded-xl animate-pulse"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
          ))}
        </div>
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        <BankingHeader title="Case Detail" subtitle="Not available" />
        <div className="flex-1 p-6 max-w-[1200px] mx-auto w-full">
          <div className="rounded-2xl border p-12 flex flex-col items-center gap-3 text-center"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <AlertTriangle size={28} style={{ color: 'var(--accent-red)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>{error ?? 'Case not found.'}</p>
            <button
              onClick={() => navigate('/workbench/cases')}
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

  const s = caseData.status;
  const isAssignee = Boolean(applicationUser?.user_id && caseData.assigned_to === applicationUser.user_id);
  const canTransition = hasPermission(PERMISSIONS.CASE_TRANSITION) && isAssignee;
  const canDecide = hasPermission(PERMISSIONS.CASE_DECISION) && isAssignee;
  const canAssign = hasPermission(PERMISSIONS.CASE_ASSIGN) && hasRole('admin');

  const showBeginReview = canTransition && s === 'assigned';
  const showRequestInfo = canTransition && s === 'under_review';
  const showDecisionPending = canTransition && s === 'under_review';
  const showResolve = canTransition && s === 'awaiting_compliance_action';
  const showRecordDecision = canDecide && s === 'decision_pending';
  const showAssign = canAssign && !caseData.assigned_to;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title={caseData.title}
        subtitle={`Case · created ${formatDateTime(caseData.created_at)}`}
        onRefresh={fetchCase}
        isRefreshing={loading}
        actions={
          <button
            onClick={() => navigate('/workbench/cases')}
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
                Case was updated by someone else. Refresh to see the latest state and retry.
              </p>
            </div>
            <button
              onClick={() => { setConflict(false); fetchCase(); }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
            >
              <RefreshCw size={13} /> Refresh
            </button>
          </div>
        )}

        {/* Header row: badges + version + assignee */}
        <div className="flex flex-wrap items-center gap-2">
          <CaseStatusBadge status={s} />
          <CaseRiskBadge riskLevel={caseData.risk_level} />
          <CasePriorityBadge priority={caseData.priority} />
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
            v{caseData.version}
          </span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
            {caseData.assigned_to ? `assigned to ${caseData.assigned_to}` : 'unassigned'}
          </span>
        </div>

        {/* Tabs */}
        <div role="tablist" aria-label="Case sections"
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
              {(showBeginReview || showRequestInfo || showDecisionPending || showResolve || showRecordDecision || showAssign) && (
                <div className="flex flex-wrap items-center gap-2">
                  {showBeginReview && (
                    <button
                      onClick={() => setDialog('begin_review')}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                      style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
                    >
                      <PlayCircle size={14} /> Begin Review
                    </button>
                  )}
                  {showRequestInfo && (
                    <button
                      onClick={() => setDialog('ir_create')}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                      style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
                    >
                      <MessageSquarePlus size={14} /> Request Information
                    </button>
                  )}
                  {showDecisionPending && (
                    <button
                      onClick={() => setDialog('decision_pending')}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                      style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
                    >
                      <Flag size={14} /> Mark Decision Pending
                    </button>
                  )}
                  {showResolve && (
                    <button
                      onClick={() => setDialog('resolve')}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                      style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
                    >
                      <CheckCircle2 size={14} /> Resolve Case
                    </button>
                  )}
                  {showRecordDecision && (
                    <button
                      onClick={() => setTab('decisions')}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                      style={{ background: 'var(--accent-purple)', color: 'var(--text-primary)' }}
                    >
                      <Gavel size={14} /> Record Decision
                    </button>
                  )}
                  {showAssign && (
                    <button
                      onClick={() => setDialog('assign')}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
                      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
                    >
                      <UserRoundPlus size={14} /> Assign Case
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

              {/* Awaiting-information note */}
              {s === 'awaiting_information' && (
                <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl border"
                  style={{ background: 'rgba(217,119,6,0.08)', borderColor: 'rgba(217,119,6,0.25)' }}>
                  <CircleSlash2 size={16} style={{ color: 'var(--accent-amber)' }} />
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                    Case is awaiting analyst information — resumes from the Information Request workflow (2B.14).
                  </p>
                </div>
              )}

              {/* Description */}
              {caseData.description && (
                <div className="rounded-2xl border p-5"
                  style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
                  <h3 className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                    Description
                  </h3>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                    {caseData.description}
                  </p>
                </div>
              )}

              {/* Resolution */}
              {caseData.resolution && (
                <div className="rounded-2xl border p-5"
                  style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
                  <h3 className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                    Resolution
                  </h3>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                    {caseData.resolution}
                  </p>
                </div>
              )}

              {/* Linked alert */}
              {caseData.alert_id && (
                <button
                  onClick={() => navigate(`/workbench/alerts/${caseData.alert_id}`)}
                  className="rounded-2xl border p-4 w-full flex items-center gap-2.5 text-left transition-all hover:brightness-95"
                  style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
                >
                  <Link2 size={14} style={{ color: 'var(--text-muted)' }} />
                  <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                    Linked alert
                  </span>
                  <span className="font-mono text-xs" style={{ color: 'var(--accent-blue)' }}>
                    #{caseData.alert_id.slice(0, 8)}…
                  </span>
                </button>
              )}

              {/* Meta grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { label: 'Status', value: s.replace(/_/g, ' ') },
                  { label: 'Risk Level', value: caseData.risk_level ?? '—' },
                  { label: 'Priority', value: caseData.priority },
                  { label: 'Assigned To', value: caseData.assigned_to ?? 'Unassigned' },
                  { label: 'Created By', value: caseData.created_by },
                  { label: 'Scope', value: caseData.scope_id },
                  { label: 'Regulatory Frameworks', value: caseData.regulatory_frameworks?.join(', ') ?? '—' },
                  { label: 'Target Date', value: caseData.target_date ?? '—' },
                  { label: 'Resolved', value: caseData.resolved_at ? formatDateTime(caseData.resolved_at) : '—' },
                  { label: 'Investigation', value: caseData.investigation_id ? `#${caseData.investigation_id.slice(0, 8)}` : '—' },
                  { label: 'Created', value: formatDateTime(caseData.created_at) },
                  { label: 'Updated', value: formatDateTime(caseData.updated_at) },
                ].map((m) => (
                  <div key={m.label} className="rounded-xl border p-4"
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
                    <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                      {m.label}
                    </p>
                    <p className={clsx('text-xs', /(to|by|id|scope|date|frameworks)/i.test(m.label) ? 'font-mono' : 'font-semibold')}
                      style={{ color: 'var(--text-secondary)' }}>
                      {m.value}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'investigation' && <CaseInvestigationTab investigationId={caseData.investigation_id} />}
          {tab === 'ir' && (
            <CaseInformationRequestsTab
              caseId={caseData.case_id}
              refreshKey={irRefreshKey}
              onConflict={onMutationConflict}
            />
          )}
          {tab === 'decisions' && (
            <CaseDecisionsTab
              caseData={caseData}
              onRecorded={setCaseData}
              onConflict={onMutationConflict}
            />
          )}
          {tab === 'comments' && <CommentsTab entityId={caseData.case_id} api={casesApi} />}
          {tab === 'timeline' && <TimelineTab entityId={caseData.case_id} api={casesApi} />}
        </div>
      </div>

      {caseData && (
        <>
          <TransitionCaseDialog
            open={dialog === 'begin_review'}
            title="Begin Review"
            body="Start reviewing this case. The linked investigation becomes the primary reference."
            confirmLabel="Begin Review"
            caseData={caseData}
            target="under_review"
            onClose={() => setDialog(null)}
            onSuccess={setCaseData}
            onConflict={onMutationConflict}
          />
          <TransitionCaseDialog
            open={dialog === 'decision_pending'}
            title="Mark Decision Pending"
            body="Move this case to decision pending so a decision can be recorded on the Decisions tab."
            confirmLabel="Mark Decision Pending"
            caseData={caseData}
            target="decision_pending"
            onClose={() => setDialog(null)}
            onSuccess={setCaseData}
            onConflict={onMutationConflict}
          />
          <TransitionCaseDialog
            open={dialog === 'resolve'}
            title="Resolve Case"
            body="Resolve this case. The resolution text is required and recorded on the case."
            confirmLabel="Resolve Case"
            caseData={caseData}
            target="resolved"
            withResolution
            resolutionRequired
            onClose={() => setDialog(null)}
            onSuccess={setCaseData}
            onConflict={onMutationConflict}
          />
          <AdminAssignCaseDialog
            open={dialog === 'assign'}
            caseData={caseData}
            onClose={() => setDialog(null)}
            onSuccess={setCaseData}
            onConflict={onMutationConflict}
          />
          <IRCreateModal
            open={dialog === 'ir_create'}
            caseData={caseData}
            onClose={() => setDialog(null)}
            onSuccess={() => { setIrRefreshKey((k) => k + 1); fetchCase(); }}
            onConflict={onMutationConflict}
          />
        </>
      )}
    </div>
  );
}
