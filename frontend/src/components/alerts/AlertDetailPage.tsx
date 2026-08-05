// src/components/alerts/AlertDetailPage.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, RefreshCw, AlertTriangle, CheckCircle2,
  Eye, FileSearch, XCircle, TrendingUp, UserPlus,
} from 'lucide-react';
import { clsx } from 'clsx';
import { BankingHeader } from '../Layout/BankingHeader';
import { alertsApi } from '../../api/alertsApi';
import { AlertSeverityBadge, AlertStatusBadge } from './AlertBadges';
import { parseAlertError } from './alertErrors';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { formatDateTime } from '../../utils/formatters';
import type { Alert, AlertAdminView } from '../../types/alerts';
import { InvestigateAlertDialog } from './dialogs/InvestigateAlertDialog';
import { DismissAlertDialog } from './dialogs/DismissAlertDialog';
import { EscalateAlertDialog } from './dialogs/EscalateAlertDialog';
import { AssignAlertDialog } from './dialogs/AssignAlertDialog';

type DialogName = 'investigate' | 'dismiss' | 'escalate' | 'assign' | null;

export function AlertDetailPage() {
  const { alertId } = useParams<{ alertId: string }>();
  const navigate = useNavigate();
  const { applicationUser, hasPermission, hasRole } = useAuth();

  const [alert, setAlert] = useState<Alert | AlertAdminView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [dialog, setDialog] = useState<DialogName>(null);
  const [acting, setActing] = useState(false);

  const fetchAlert = useCallback(async () => {
    if (!alertId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await alertsApi.get(alertId);
      setAlert(data);
    } catch (err) {
      setError(parseAlertError(err).message);
      setAlert(null);
    } finally {
      setLoading(false);
    }
  }, [alertId]);

  useEffect(() => { fetchAlert(); }, [fetchAlert]);

  const acknowledge = async () => {
    if (!alert || acting) return;
    setActing(true);
    try {
      await alertsApi.acknowledge(alert.alert_id, alert.version);
      await fetchAlert();
    } catch (err) {
      if (parseAlertError(err).kind === 'conflict') {
        setConflict(true);
        await fetchAlert();
      }
    } finally {
      setActing(false);
    }
  };

  if (loading && !alert) {
    return (
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        <BankingHeader title="Alert Detail" subtitle="Loading…" isRefreshing />
        <div className="flex-1 p-6 max-w-[1200px] mx-auto w-full space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 border rounded-xl animate-pulse"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
          ))}
        </div>
      </div>
    );
  }

  if (!alert) {
    return (
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        <BankingHeader title="Alert Detail" subtitle="Not available" />
        <div className="flex-1 p-6 max-w-[1200px] mx-auto w-full">
          <div className="rounded-2xl border p-12 flex flex-col items-center gap-3 text-center"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <AlertTriangle size={28} style={{ color: 'var(--accent-red)' }} />
            <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>{error ?? 'Alert not found.'}</p>
            <button
              onClick={() => navigate('/workbench/alerts')}
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

  const isAdminView = !('description' in alert);
  const displayTitle = 'title' in alert ? alert.title : `${alert.alert_type} · ${alert.alert_id.slice(0, 8)}…`;
  const assignee = 'assigned_to' in alert ? alert.assigned_to ?? null : null;
  const isAssignee = Boolean(assignee && assignee === applicationUser?.user_id);
  const s = alert.status;

  const canAcknowledge = !isAdminView && hasPermission(PERMISSIONS.ALERT_ACKNOWLEDGE) && s === 'assigned' && isAssignee;
  const canInvestigate = !isAdminView && hasPermission(PERMISSIONS.ALERT_INVESTIGATE) && s === 'acknowledged' && isAssignee;
  const canDismiss = !isAdminView && hasPermission(PERMISSIONS.ALERT_DISMISS)
    && (s === 'acknowledged' || s === 'under_investigation') && isAssignee;
  const canEscalate = !isAdminView && hasPermission(PERMISSIONS.ALERT_TRANSITION) && s === 'under_investigation' && isAssignee;
  const canAssign = hasPermission(PERMISSIONS.ALERT_ASSIGN) && hasRole('admin')
    && s !== 'resolved' && s !== 'dismissed';

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title={displayTitle}
        subtitle={`${alert.alert_type} · created ${formatDateTime(alert.created_at)}`}
        onRefresh={fetchAlert}
        isRefreshing={loading}
        actions={
          <button
            onClick={() => navigate('/workbench/alerts')}
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
                Alert was updated — refresh and try again.
              </p>
            </div>
            <button
              onClick={() => { setConflict(false); fetchAlert(); }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
            >
              <RefreshCw size={13} /> Refresh
            </button>
          </div>
        )}

        {/* Header row: badges + version */}
        <div className="flex flex-wrap items-center gap-2">
          <AlertSeverityBadge severity={alert.severity} />
          <AlertStatusBadge status={alert.status} />
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
            v{alert.version}
          </span>
          {assignee && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
              assigned to {assignee}
            </span>
          )}
        </div>

        {/* Action bar */}
        {(canAcknowledge || canInvestigate || canDismiss || canEscalate || canAssign) && (
          <div className="flex flex-wrap items-center gap-2">
            {canAcknowledge && (
              <button
                onClick={acknowledge}
                disabled={acting}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-50"
                style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
              >
                <CheckCircle2 size={14} /> {acting ? 'Acknowledging…' : 'Acknowledge'}
              </button>
            )}
            {canInvestigate && (
              <button
                onClick={() => setDialog('investigate')}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                style={{ background: 'var(--accent-green)', color: 'var(--text-primary)' }}
              >
                <FileSearch size={14} /> Create Investigation
              </button>
            )}
            {canDismiss && (
              <button
                onClick={() => setDialog('dismiss')}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                style={{ background: 'rgba(220,38,38,0.12)', color: 'var(--accent-red)' }}
              >
                <XCircle size={14} /> Dismiss
              </button>
            )}
            {canEscalate && (
              <button
                onClick={() => setDialog('escalate')}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90"
                style={{ background: 'rgba(220,38,38,0.12)', color: 'var(--accent-red)' }}
              >
                <TrendingUp size={14} /> Escalate
              </button>
            )}
            {canAssign && (
              <button
                onClick={() => setDialog('assign')}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold border transition-all hover:brightness-95"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
              >
                <UserPlus size={14} /> Assign
              </button>
            )}
          </div>
        )}

        {/* Description */}
        {!isAdminView && (
          <div className="rounded-2xl border p-5"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <h3 className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
              Description
            </h3>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {alert.description || 'No description provided.'}
            </p>
          </div>
        )}

        {/* Related entity */}
        {!isAdminView && (alert.related_entity_type || alert.related_entity_id) && (
          <div className="rounded-2xl border p-5 flex items-center gap-2.5"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <Eye size={14} style={{ color: 'var(--text-muted)' }} />
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Related
            </span>
            <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
              {alert.related_entity_type} · {alert.related_entity_id}
            </span>
            {alert.related_entity_type === 'customer' && alert.related_entity_id && (
              <Link
                to={`/workbench/customers/${encodeURIComponent(alert.related_entity_id)}`}
                className="text-[10px] font-semibold underline decoration-dotted hover:brightness-125"
                style={{ color: 'var(--accent-blue)' }}>
                Open Customer 360
              </Link>
            )}
          </div>
        )}

        {/* Meta grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { label: 'Alert Type', value: alert.alert_type },
            { label: 'Scope', value: alert.scope_id },
            { label: 'Source Rule', value: 'source_rule_type' in alert ? `${alert.source_rule_type ?? '—'} / ${alert.source_rule_id ?? '—'}` : '—' },
            { label: 'Created', value: formatDateTime(alert.created_at) },
            ...(!isAdminView ? [{ label: 'Updated', value: formatDateTime(alert.updated_at) }] : []),
            ...(!isAdminView && alert.status === 'dismissed' ? [{
              label: 'Dismissed', value: `${alert.dismissed_by ?? '—'} · ${formatDateTime(alert.dismissed_at ?? '')}`,
            }] : []),
          ].map((m) => (
            <div key={m.label} className="rounded-xl border p-4"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
              <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                {m.label}
              </p>
              <p className={clsx('text-xs', /(rule|id)/i.test(m.label) ? 'font-mono' : 'font-semibold')}
                style={{ color: 'var(--text-secondary)' }}>
                {m.value}
              </p>
            </div>
          ))}
        </div>

        {isAdminView && (
          <p className="text-[10px]" style={{ color: 'var(--text-subtle)' }}>
            Metadata-only view — this alert is outside your direct scope.
          </p>
        )}
      </div>

      {alert && !isAdminView && (
        <>
          <InvestigateAlertDialog
            alert={alert}
            open={dialog === 'investigate'}
            onClose={() => setDialog(null)}
            onSuccess={(id) => navigate(`/workbench/investigations/${id}`)}
            onConflict={() => { setConflict(true); fetchAlert(); }}
          />
          <DismissAlertDialog
            alert={alert}
            open={dialog === 'dismiss'}
            onClose={() => setDialog(null)}
            onSuccess={() => fetchAlert()}
            onConflict={() => { setConflict(true); fetchAlert(); }}
          />
          <EscalateAlertDialog
            alert={alert}
            open={dialog === 'escalate'}
            onClose={() => setDialog(null)}
            onSuccess={(caseId) => navigate(`/workbench/cases/${caseId}`)}
            onConflict={() => { setConflict(true); fetchAlert(); }}
          />
        </>
      )}
      {alert && canAssign && (
        <AssignAlertDialog
          alert={alert as Alert}
          open={dialog === 'assign'}
          onClose={() => setDialog(null)}
          onSuccess={() => fetchAlert()}
          onConflict={() => { setConflict(true); fetchAlert(); }}
        />
      )}
    </div>
  );
}
