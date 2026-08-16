// src/components/customers/CustomerContextPanel.tsx
// Compact, read-only Customer 360 context shown inside the operational workbench
// (alert / investigation / case detail pages). It renders exactly what the
// server-authorized overview response grants — masked values stay masked, and
// forbidden / not-found / unavailable outcomes degrade to a safe empty state
// instead of fabricating data. The Customer 360 page remains the only detailed
// viewer; this panel only adds authorized context to the investigation flow.
import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ExternalLink, RefreshCw, ShieldX, UserX } from 'lucide-react';
import { clsx } from 'clsx';
import { customer360Api, parseCustomer360Error } from '../../api/customer360Api';
import type { Customer360ApiError } from '../../api/customer360Api';
import type { Customer360Overview } from '../../types/customer360';
import { StatusBadge } from '../ui/StatusBadge';
import { dateOnly, isMasked, money, riskClassification, severityVariant, statusVariant } from './customer360Format';

interface Props {
  customerId: string;
  className?: string;
}

type PanelStatus = 'loading' | 'error' | 'ready';

const ERROR_TEXT: Record<Customer360ApiError['kind'], string> = {
  forbidden: 'Customer context is outside your permission scope.',
  not_found: 'Customer record cannot be resolved.',
  unavailable: 'Customer context source is temporarily unavailable.',
  network: 'Customer context source is temporarily unavailable.',
  malformed: 'Customer context could not be loaded.',
  unknown: 'Customer context could not be loaded.',
};

function ErrorState({ kind, onRetry }: { kind: Customer360ApiError['kind']; onRetry: () => void }) {
  const canRetry = kind !== 'forbidden' && kind !== 'not_found';
  return (
    <div className="flex items-start gap-2.5 py-1">
      <span className="mt-0.5 shrink-0">
        {kind === 'forbidden'
          ? <ShieldX size={14} style={{ color: 'var(--accent-red)' }} />
          : <UserX size={14} style={{ color: 'var(--text-muted)' }} />}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          {ERROR_TEXT[kind]}
        </p>
        {canRetry && (
          <button onClick={onRetry} className="text-[10px] font-semibold underline decoration-dotted mt-1 inline-flex items-center gap-1"
            style={{ color: 'var(--accent-blue)' }}>
            <RefreshCw size={10} /> Retry
          </button>
        )}
      </div>
    </div>
  );
}

export function CustomerContextPanel({ customerId, className }: Props) {
  const [overview, setOverview] = useState<Customer360Overview | null>(null);
  const [status, setStatus] = useState<PanelStatus>('loading');
  const [errorKind, setErrorKind] = useState<Customer360ApiError['kind']>('unknown');

  const fetchOverview = useCallback(async () => {
    setStatus('loading');
    try {
      const data = await customer360Api.getOverview(customerId);
      setOverview(data);
      setStatus('ready');
    } catch (err) {
      setOverview(null);
      setErrorKind(parseCustomer360Error(err).kind);
      setStatus('error');
    }
  }, [customerId]);

  useEffect(() => { fetchOverview(); }, [fetchOverview]);

  const o = overview;
  const isAdmin = Boolean(o?.admin_metadata);
  const adminMeta = o?.admin_metadata ?? null;
  const risk = o?.risk ?? null;
  const kyc = o?.kyc_aml ?? null;
  const fs = o?.financial_summary ?? null;
  const tx = o?.transaction_summary ?? null;
  const rel = o?.relationship ?? null;

  const riskClass =
    adminMeta?.risk_classification ??
    riskClassification(risk?.risk_score ?? null);
  const kycStatus = adminMeta?.kyc_status ?? kyc?.kyc_status ?? null;
  const flagCount =
    risk?.active_flags?.length ??
    adminMeta?.active_flag_count ??
    null;
  const pepStatus = kyc?.pep_screening?.status ?? null;
  const sanctionsStatus = kyc?.sanctions_screening?.status ?? null;

  const deposits = fs?.total_balance_by_currency;
  const loansOutstanding = fs?.total_outstanding_loans_by_currency;

  const identity = o?.customer ?? null;
  const name = identity?.name ?? customerId;
  const masked = isMasked(identity?.email ?? identity?.phone ?? null);

  return (
    <div className={clsx('rounded-2xl border p-4', className)}
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
      data-testid="customer-context-panel">
      <div className="flex items-center justify-between mb-2.5">
        <h3 className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
          Customer context
        </h3>
        <Link
          to={`/workbench/customers/${encodeURIComponent(customerId)}`}
          className="inline-flex items-center gap-1 text-[10px] font-semibold hover:brightness-125"
          style={{ color: 'var(--accent-blue)' }}>
          Open Customer 360 <ExternalLink size={10} />
        </Link>
      </div>

      {status === 'loading' && (
        <div className="space-y-2" aria-busy="true">
          <div className="h-4 w-1/2 rounded animate-pulse" style={{ background: 'var(--bg-tertiary)' }} />
          <div className="h-3 w-3/4 rounded animate-pulse" style={{ background: 'var(--bg-tertiary)' }} />
        </div>
      )}

      {status === 'error' && <ErrorState kind={errorKind} onRetry={() => fetchOverview()} />}

      {status === 'ready' && o && (
        <div className="space-y-2.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{name}</span>
            <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>#{identity?.customer_id ?? customerId}</span>
            {masked && <StatusBadge variant="gray">Masked</StatusBadge>}
            {identity?.customer_type && (
              <StatusBadge variant="blue">{identity.customer_type}</StatusBadge>
            )}
            {identity?.segment && (
              <StatusBadge variant="gray">{identity.segment}</StatusBadge>
            )}
          </div>

          {!isAdmin && (risk || kyc || flagCount != null) && (
            <div className="flex items-center gap-1.5 flex-wrap">
              {riskClass && (
                <StatusBadge variant={severityVariant(riskClass)}>Risk: {riskClass}</StatusBadge>
              )}
              {kycStatus && (
                <StatusBadge variant={statusVariant(kycStatus)}>KYC: {kycStatus}</StatusBadge>
              )}
              {pepStatus && (
                <StatusBadge variant={pepStatus === 'clear' ? 'green' : 'yellow'}>PEP: {pepStatus}</StatusBadge>
              )}
              {sanctionsStatus && (
                <StatusBadge variant={sanctionsStatus === 'clear' ? 'green' : 'yellow'}>Sanctions: {sanctionsStatus}</StatusBadge>
              )}
              {flagCount != null && (
                <StatusBadge variant={flagCount > 0 ? 'red' : 'green'}>
                  {flagCount === 0 ? 'No active flags' : `${flagCount} active flag${flagCount === 1 ? '' : 's'}`}
                </StatusBadge>
              )}
            </div>
          )}

          {!isAdmin && (fs || tx) && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {fs?.account_count != null && (
                <div className="rounded-lg border px-2.5 py-1.5" style={{ borderColor: 'var(--bg-border)' }}>
                  <p className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Accounts</p>
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{fs.account_count}</p>
                </div>
              )}
              {deposits && Object.keys(deposits).length > 0 && (
                <div className="rounded-lg border px-2.5 py-1.5" style={{ borderColor: 'var(--bg-border)' }}>
                  <p className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Deposits</p>
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {Object.entries(deposits).map(([cur, v]) => money(v, cur)).join(' · ')}
                  </p>
                </div>
              )}
              {loansOutstanding && Object.keys(loansOutstanding).length > 0 && (
                <div className="rounded-lg border px-2.5 py-1.5" style={{ borderColor: 'var(--bg-border)' }}>
                  <p className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Loans</p>
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {Object.entries(loansOutstanding).map(([cur, v]) => money(v, cur)).join(' · ')}
                  </p>
                </div>
              )}
              {tx?.d30_total_count != null && (
                <div className="rounded-lg border px-2.5 py-1.5" style={{ borderColor: 'var(--bg-border)' }}>
                  <p className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>30d Txns</p>
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{tx.d30_total_count}</p>
                </div>
              )}
            </div>
          )}

          {isAdmin && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {adminMeta?.account_count != null && (
                <div className="rounded-lg border px-2.5 py-1.5" style={{ borderColor: 'var(--bg-border)' }}>
                  <p className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Accounts</p>
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{adminMeta.account_count}</p>
                </div>
              )}
              {adminMeta?.loan_count != null && (
                <div className="rounded-lg border px-2.5 py-1.5" style={{ borderColor: 'var(--bg-border)' }}>
                  <p className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Loans</p>
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{adminMeta.loan_count}</p>
                </div>
              )}
              {adminMeta?.product_count != null && (
                <div className="rounded-lg border px-2.5 py-1.5" style={{ borderColor: 'var(--bg-border)' }}>
                  <p className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Products</p>
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{adminMeta.product_count}</p>
                </div>
              )}
              {riskClass && (
                <div className="rounded-lg border px-2.5 py-1.5" style={{ borderColor: 'var(--bg-border)' }}>
                  <p className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Risk</p>
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{riskClass}</p>
                </div>
              )}
            </div>
          )}

          {rel && (rel.primary_branch || rel.region || (rel.relationship_managers ?? []).length > 0) && (
            <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              {[rel.primary_branch, rel.region].filter(Boolean).join(' · ')}
              {((rel.relationship_managers ?? []).length > 0) && (
                <> · RM: {rel.relationship_managers?.map((rm) => rm.name).join(', ')}</>
              )}
            </p>
          )}

          {o.generated_at && (
            <p className="text-[10px] flex items-center gap-1" style={{ color: 'var(--text-subtle, var(--text-muted))' }}>
              <AlertCircle size={10} /> Generated {dateOnly(o.generated_at)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
