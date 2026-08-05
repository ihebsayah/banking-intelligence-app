// src/components/customers/Customer360Page.tsx
// Customer 360 workspace (/workbench/customers/:customerId). Renders exactly
// what the backend response grants — sections the caller lacks permission for
// are absent from the payload and are shown as "Restricted by policy", never
// fabricated. PII arrives masked from the service and stays masked here.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { clsx } from 'clsx';
import {
  ArrowLeft, RefreshCw, ShieldX, ShieldAlert, AlertTriangle, AlertCircle,
  UserX, Landmark, Building2, Wallet, Scale, FileClock, Inbox, CheckCircle2,
} from 'lucide-react';
import { BankingHeader } from '../Layout/BankingHeader';
import { customer360Api, parseCustomer360Error } from '../../api/customer360Api';
import type { Customer360ApiError } from '../../api/customer360Api';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { StatusBadge } from '../ui/StatusBadge';
import { EmptyState } from '../ui/EmptyState';
import type {
  AccountSummary,
  AmlAlertSummary,
  Customer360Overview,
  CustomerTransactionsResponse,
  DataQuality,
  LoanSummary,
  TransactionRow,
  WorkbenchEntityType,
  WorkbenchLink,
} from '../../types/customer360';

type TabId = 'overview' | 'accounts' | 'transactions' | 'risk' | 'alerts';

// ── formatting helpers ──────────────────────────────────────────────────────

function money(value: string | null | undefined, currency?: string | null): string {
  if (value == null || value === '') return '—';
  if (!/^-?\d+(\.\d+)?$/.test(value)) return value; // masked / non-numeric token
  const num = Number(value);
  const cur = (currency ?? 'TND').toUpperCase();
  const digits = num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${digits} ${cur}`;
}

function isMasked(value: string | null | undefined): boolean {
  return typeof value === 'string' && (value.includes('***') || value.startsWith('****'));
}

function dateOnly(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = iso.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : '—';
}

function severityVariant(sev?: string | null) {
  switch ((sev ?? '').toLowerCase()) {
    case 'critical': return 'red' as const;
    case 'high': return 'orange' as const;
    case 'medium': return 'yellow' as const;
    case 'low': return 'green' as const;
    default: return 'gray' as const;
  }
}

function statusVariant(status?: string | null) {
  switch ((status ?? '').toLowerCase()) {
    case 'active': case 'approved': case 'completed': case 'cleared':
    case 'passed': case 'verified': case 'resolved': case 'success':
      return 'green' as const;
    case 'blocked': case 'default': case 'past_due': case 'overdue':
    case 'critical': case 'failed': case 'rejected': case 'escalated':
      return 'red' as const;
    case 'pending': case 'review': case 'under_review': case 'processing':
    case 'under_investigation': case 'acknowledged': case 'assigned': case 'new':
      return 'yellow' as const;
    default: return 'gray' as const;
  }
}

function riskClassification(score?: number | null): string | null {
  if (score == null) return null;
  if (score >= 0.8) return 'critical';
  if (score >= 0.6) return 'high';
  if (score >= 0.4) return 'medium';
  return 'low';
}

// ── small shared presentational pieces ──────────────────────────────────────

function SectionCard({ title, icon, children, className }: {
  title: string; icon?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={clsx('rounded-2xl border p-5', className)}
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
      <h2 className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider mb-4"
        style={{ color: 'var(--text-muted)' }}>
        {icon}{title}
      </h2>
      {children}
    </section>
  );
}

function RestrictedNotice({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-[11px] italic" style={{ color: 'var(--text-subtle)' }}>
      <ShieldX size={13} /> {label} — restricted by policy
    </div>
  );
}

function MaskedTag() {
  return (
    <span className="px-1 py-0.5 rounded text-[9px] font-semibold border whitespace-nowrap"
      style={{ background: 'rgba(37,99,235,0.06)', color: 'var(--text-muted)', borderColor: 'var(--bg-border)' }}>
      Masked
    </span>
  );
}

function Field({ label, value, masked, restricted, mono }: {
  label: string; value?: string | number | boolean | null; masked?: boolean;
  restricted?: boolean; mono?: boolean;
}) {
  return (
    <div className="rounded-xl border p-3" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
      <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
        {label}
      </p>
      {restricted ? (
        <p className="text-[10px] italic flex items-center gap-1" style={{ color: 'var(--text-subtle)' }}>
          <ShieldX size={11} /> Restricted by policy
        </p>
      ) : value == null || value === '' ? (
        <p className="text-[11px]" style={{ color: 'var(--text-subtle)' }}>—</p>
      ) : (
        <p className="flex items-center gap-1.5 text-xs font-semibold flex-wrap" style={{ color: 'var(--text-secondary)' }}>
          <span className={mono ? 'font-mono' : undefined}>{String(value)}</span>
          {masked && <MaskedTag />}
        </p>
      )}
    </div>
  );
}

function KeyValueRow({ label, value, mono }: { label: string; value?: string | number | null; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 text-xs">
      <span className="shrink-0 text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span className={clsx('text-right font-semibold', mono && 'font-mono')} style={{ color: 'var(--text-secondary)' }}>
        {value == null || value === '' ? '—' : String(value)}
      </span>
    </div>
  );
}

function dataQualityWarnings(dq: DataQuality): { message: string; warn: boolean }[] {
  const out: { message: string; warn: boolean }[] = [];
  if (dq.missing_profile) out.push({ message: 'Customer profile record is missing — some identity fields are unavailable.', warn: true });
  if (dq.missing_branch) out.push({ message: 'No branch could be determined for this customer.', warn: true });
  if (dq.missing_relationship_manager) out.push({ message: 'No relationship manager is currently assigned.', warn: false });
  if (dq.stale_kyc) out.push({ message: 'KYC information may be out of date.', warn: true });
  if (dq.unresolved_workbench_reference) out.push({ message: 'Some operational records could not be linked to this customer.', warn: true });
  if (dq.unavailable_sections.length > 0) {
    out.push({ message: `Some sections are temporarily unavailable: ${dq.unavailable_sections.join(', ')}.`, warn: true });
  }
  return out;
}

const ENTITY_LABELS: Record<WorkbenchEntityType, string> = {
  alert: 'Workbench alert',
  investigation: 'Investigation',
  case: 'Compliance case',
  information_request: 'Information request',
};

const ENTITY_ROUTES: Record<WorkbenchEntityType, string> = {
  alert: '/workbench/alerts',
  investigation: '/workbench/investigations',
  case: '/workbench/cases',
  information_request: '/workbench/information-requests',
};

function entityVariant(type: WorkbenchEntityType) {
  switch (type) {
    case 'alert': return 'blue' as const;
    case 'investigation': return 'purple' as const;
    case 'case': return 'yellow' as const;
    default: return 'gray' as const;
  }
}

// ── transactions mini-table (shared by Overview recent activity + tab) ─────

function TransactionsTable({ rows }: { rows: TransactionRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs border-collapse">
        <thead>
          <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
            <th className="pb-2 pr-3 font-semibold">Date</th>
            <th className="pb-2 pr-3 font-semibold">Type</th>
            <th className="pb-2 pr-3 font-semibold">Status</th>
            <th className="pb-2 pr-3 font-semibold text-right">Amount</th>
            <th className="pb-2 font-semibold">Description</th>
            <th className="pb-2 font-semibold">Account</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {rows.map((tx) => (
            <tr key={tx.transaction_id} style={{ color: 'var(--text-secondary)' }}>
              <td className="py-2.5 pr-3 font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                {dateOnly(tx.transaction_date)}
              </td>
              <td className="py-2.5 pr-3">{tx.type ?? '—'}</td>
              <td className="py-2.5 pr-3">
                <StatusBadge variant={statusVariant(tx.status)}>{tx.status ?? '—'}</StatusBadge>
              </td>
              <td className="py-2.5 pr-3 text-right font-mono font-semibold whitespace-nowrap">
                {money(tx.amount, tx.currency)}
              </td>
              <td className="py-2.5 pr-3 max-w-xs truncate">{tx.description ?? '—'}</td>
              <td className="py-2.5 font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                {tx.account_id ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── the page ───────────────────────────────────────────────────────────────

export function Customer360Page() {
  const { customerId } = useParams<{ customerId: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const [overview, setOverview] = useState<Customer360Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Customer360ApiError | null>(null);
  const [tab, setTab] = useState<TabId>('overview');
  const [retryKey, setRetryKey] = useState(0);

  const [txData, setTxData] = useState<CustomerTransactionsResponse | null>(null);
  const [txLoading, setTxLoading] = useState(false);
  const [txError, setTxError] = useState<Customer360ApiError | null>(null);
  const [txOffset, setTxOffset] = useState(0);
  const TX_PAGE_SIZE = 20;

  const adminView =
    hasPermission(PERMISSIONS.CUSTOMER_READ_OPERATIONAL_METADATA) &&
    !hasPermission(PERMISSIONS.CUSTOMER_READ_PII);

  const fetchOverview = useCallback(async () => {
    if (!customerId) {
      setError({ kind: 'not_found', message: 'Customer not found or unavailable.' });
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await customer360Api.getOverview(customerId);
      setOverview(data);
      setTab('overview');
    } catch (err) {
      setError(parseCustomer360Error(err));
      setOverview(null);
    } finally {
      setLoading(false);
    }
  }, [customerId, retryKey]);

  useEffect(() => { fetchOverview(); }, [fetchOverview]);

  // Section grants come from the payload, never from the role alone.
  const financialGranted = Boolean(overview?.financial_summary);
  const transactionsGranted =
    Boolean(overview?.transaction_summary) ||
    hasPermission(PERMISSIONS.CUSTOMER_READ_TRANSACTIONS);
  const kycGranted = Boolean(overview?.kyc_aml);
  const riskGranted = Boolean(overview?.risk);
  const workbenchGranted =
    hasPermission(PERMISSIONS.CUSTOMER_READ_COMPLIANCE_HISTORY) ||
    hasPermission(PERMISSIONS.CUSTOMER_READ_OPERATIONAL_METADATA);
  const analyticsGranted = kycGranted;

  const tabs = useMemo<TabId[]>(() => {
    const list: TabId[] = ['overview'];
    if (financialGranted) list.push('accounts');
    if (transactionsGranted) list.push('transactions');
    if (riskGranted || kycGranted) list.push('risk');
    if (analyticsGranted || workbenchGranted) list.push('alerts');
    return list;
  }, [financialGranted, transactionsGranted, riskGranted, kycGranted, analyticsGranted, workbenchGranted]);

  useEffect(() => {
    if (!tabs.includes(tab)) setTab('overview');
  }, [tabs, tab]);

  const fetchTransactions = useCallback(async () => {
    if (!customerId || !transactionsGranted) return;
    setTxLoading(true);
    setTxError(null);
    try {
      const data = await customer360Api.getTransactions(customerId, { limit: TX_PAGE_SIZE, offset: txOffset });
      setTxData(data);
    } catch (err) {
      setTxError(parseCustomer360Error(err));
      setTxData(null);
    } finally {
      setTxLoading(false);
    }
  }, [customerId, transactionsGranted, txOffset]);

  useEffect(() => {
    if (tab === 'transactions' && transactionsGranted) fetchTransactions();
  }, [tab, transactionsGranted, fetchTransactions]);

  const onTabKeyDown = (e: React.KeyboardEvent) => {
    const idx = tabs.indexOf(tab);
    if (e.key === 'ArrowRight') { e.preventDefault(); setTab(tabs[(idx + 1) % tabs.length]); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); setTab(tabs[(idx - 1 + tabs.length) % tabs.length]); }
    if (e.key === 'Home') { e.preventDefault(); setTab(tabs[0]); }
    if (e.key === 'End') { e.preventDefault(); setTab(tabs[tabs.length - 1]); }
  };

  // ── loading ──
  if (loading) {
    return (
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        <BankingHeader title="Customer 360" subtitle="Loading…" />
        <div className="flex-1 p-6 max-w-[1200px] mx-auto w-full space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-20 border rounded-2xl animate-pulse"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
          ))}
        </div>
      </div>
    );
  }

  // ── error states ──
  if (!overview || error) {
    const kind = error?.kind ?? 'unknown';
    const isForbidden = kind === 'forbidden';
    const isNotFound = kind === 'not_found';
    const isUnavailable = kind === 'unavailable';
    return (
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        <BankingHeader title="Customer 360" subtitle={customerId ?? 'No customer selected'} />
        <div className="flex-1 p-6 max-w-[1200px] mx-auto w-full">
          <div className="rounded-2xl border p-12 flex flex-col items-center gap-4 text-center"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
              style={{ background: isForbidden ? 'rgba(220,38,38,0.08)' : 'rgba(37,99,235,0.08)' }}>
              {isForbidden
                ? <ShieldX size={24} style={{ color: 'var(--accent-red)' }} />
                : <UserX size={24} style={{ color: 'var(--accent-blue)' }} />}
            </div>
            <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
              {isForbidden ? 'Access Denied' : isNotFound ? 'Customer Not Found or Unavailable' : isUnavailable ? 'Service Unavailable' : 'Something Went Wrong'}
            </h2>
            <p className="text-sm max-w-md" style={{ color: 'var(--text-muted)' }}>
              {error?.message ?? 'Unable to load this customer profile.'}
            </p>
            {!isForbidden && (
              <button onClick={() => setRetryKey(k => k + 1)} className="btn-primary mt-2">
                <RefreshCw size={14} /> Retry
              </button>
            )}
            <button onClick={() => navigate(-1)} className="btn-ghost text-xs">
              <ArrowLeft size={14} /> Back
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { customer, relationship, data_quality: dq, admin_metadata: adminMeta } = overview;
  const warnings = dataQualityWarnings(dq);
  const isAdmin = Boolean(adminMeta);
  const sensitiveRestricted = adminView;

  // ── summary strip stats ──
  const stats: { label: string; value: string; variant?: 'green' | 'red' | 'yellow' | 'gray' | 'orange' }[] = [];
  const fs = overview.financial_summary;
  const risk = overview.risk;
  const kyc = overview.kyc_aml;
  stats.push({ label: 'Accounts', value: String(fs?.account_count ?? adminMeta?.account_count ?? '—') });
  stats.push({ label: 'Active', value: String(fs?.active_account_count ?? adminMeta?.active_account_count ?? '—') });
  stats.push({
    label: 'Products',
    value: String(
      adminMeta?.product_count ??
      (overview.accounts.length
        ? new Set(overview.accounts.map(a => a.account_type).filter(Boolean)).size
        : '—'),
    ),
  });
  stats.push({ label: 'Loans', value: String(fs?.loan_count ?? adminMeta?.loan_count ?? '—') });

  const riskScore = risk?.risk_score ?? adminMeta?.risk_score ?? null;
  const riskClass = risk ? riskClassification(riskScore) : (adminMeta?.risk_classification ?? riskClassification(riskScore));
  if (riskScore != null || adminMeta) {
    stats.push({ label: 'Risk', value: riskScore != null ? String(riskScore) : '—', variant: riskClass ? severityVariant(riskClass) : undefined });
  }
  const flagCount = risk?.unresolved_flag_count ?? adminMeta?.active_flag_count ?? null;
  if (flagCount != null) stats.push({ label: 'Active flags', value: String(flagCount), variant: flagCount > 0 ? 'red' : 'green' });
  const kycStatus = kyc?.kyc_status ?? adminMeta?.kyc_status ?? null;
  if (kycStatus != null) stats.push({ label: 'KYC', value: kycStatus, variant: statusVariant(kycStatus) });

  const TAB_LABELS: Record<TabId, string> = {
    overview: 'Overview',
    accounts: 'Accounts & Loans',
    transactions: 'Transactions',
    risk: 'Risk & KYC',
    alerts: 'Alerts & Cases',
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title={customer?.name ?? customerId ?? 'Customer'}
        subtitle={`${customerId}${customer?.segment ? ` · ${customer.segment}` : ''}${customer?.status ? ` · ${customer.status}` : ''}`}
        actions={
          <button onClick={() => navigate(-1)} className="btn-ghost text-xs px-2.5 py-1.5">
            <ArrowLeft size={13} /> Back
          </button>
        }
      />

      <div className="flex-1 p-6 space-y-5 max-w-[1200px] mx-auto w-full">

        {/* Risk classification + KYC badges row */}
        {(riskClass || kycStatus) && (
          <div className="flex flex-wrap items-center gap-2">
            {riskClass && (
              <StatusBadge variant={severityVariant(riskClass)}>
                <ShieldAlert size={11} /> Risk: {riskClass}
              </StatusBadge>
            )}
            {kycStatus && (
              <StatusBadge variant={statusVariant(kycStatus)}>
                <Scale size={11} /> KYC: {kycStatus}
              </StatusBadge>
            )}
            {flagCount != null && flagCount > 0 && (
              <StatusBadge variant="red"><AlertCircle size={11} /> {flagCount} active risk {flagCount === 1 ? 'flag' : 'flags'}</StatusBadge>
            )}
          </div>
        )}

        {/* Summary strip */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {stats.map((s) => (
            <div key={s.label} className="rounded-xl border p-3"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
              <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                {s.label}
              </p>
              {s.variant
                ? <StatusBadge variant={s.variant}>{s.value}</StatusBadge>
                : <p className="text-sm font-bold font-mono" style={{ color: 'var(--text-secondary)' }}>{s.value}</p>}
            </div>
          ))}
        </div>

        {/* Data quality warnings */}
        {warnings.length > 0 && (
          <div className="rounded-xl border p-4 space-y-2"
            style={{ background: 'rgba(217,119,6,0.06)', borderColor: 'rgba(217,119,6,0.25)' }}>
            <div className="flex items-center gap-2">
              <AlertTriangle size={14} style={{ color: 'var(--accent-amber)' }} />
              <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
                Data quality
              </span>
            </div>
            <ul className="space-y-1">
              {warnings.map((w, i) => (
                <li key={i} className="text-xs" style={{ color: w.warn ? 'var(--text-secondary)' : 'var(--text-muted)' }}>
                  {w.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Tabs */}
        <div role="tablist" aria-label="Customer profile sections"
          className="flex items-center gap-1 overflow-x-auto border-b pb-0.5"
          style={{ borderColor: 'var(--bg-border)' }}
          onKeyDown={onTabKeyDown}>
          {tabs.map((id) => (
            <button
              key={id}
              role="tab"
              id={`c360-tab-${id}`}
              aria-selected={tab === id}
              aria-controls={`c360-panel-${id}`}
              tabIndex={tab === id ? 0 : -1}
              onClick={() => setTab(id)}
              className="px-3.5 py-2 text-xs font-semibold rounded-t-lg transition-colors focus:outline-none focus-visible:ring-2"
              style={{
                color: tab === id ? 'var(--accent-blue)' : 'var(--text-muted)',
                borderBottom: tab === id ? '2px solid var(--accent-blue)' : '2px solid transparent',
              }}>
              {TAB_LABELS[id]}
            </button>
          ))}
        </div>

        <div role="tabpanel" id={`c360-panel-${tab}`} aria-labelledby={`c360-tab-${tab}`} className="space-y-5">
          {tab === 'overview' && (
            <OverviewTab
              overview={overview}
              adminView={adminView}
              sensitiveRestricted={sensitiveRestricted}
              isAdmin={isAdmin}
            />
          )}
          {tab === 'accounts' && <AccountsTab overview={overview} />}
          {tab === 'transactions' && (
            <TransactionsTab
              overview={overview}
              data={txData}
              loading={txLoading}
              error={txError}
              offset={txOffset}
              pageSize={TX_PAGE_SIZE}
              onOffsetChange={setTxOffset}
              onRetry={fetchTransactions}
            />
          )}
          {tab === 'risk' && <RiskKycTab overview={overview} adminView={adminView} />}
          {tab === 'alerts' && (
            <AlertsTab
              analyticsGranted={analyticsGranted}
              workbenchGranted={workbenchGranted}
              alerts={overview.analytics_alerts}
              links={overview.workbench_links}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Overview tab ────────────────────────────────────────────────────────────

function OverviewTab({ overview, adminView, sensitiveRestricted, isAdmin }: {
  overview: Customer360Overview;
  adminView: boolean;
  sensitiveRestricted: boolean;
  isAdmin: boolean;
}) {
  const { customer, relationship } = overview;
  const kyc = overview.kyc_aml;
  const risk = overview.risk;
  const fs = overview.financial_summary;
  const adminMeta = overview.admin_metadata;
  const financialGranted = Boolean(fs);
  const riskGranted = Boolean(risk);
  const kycGranted = Boolean(kyc);

  const piiRestricted = (v: string | null | undefined) =>
    sensitiveRestricted && (v == null || v === '');

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* Identity & profile */}
      <SectionCard title="Identity & Profile" icon={<Building2 size={12} />} className="lg:col-span-2">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
          <Field label="Customer ID" value={customer?.customer_id} mono />
          <Field label="Type" value={customer?.customer_type} />
          <Field label="Segment" value={customer?.segment} />
          <Field label="Status" value={customer?.status} />
          <Field label="Onboarding" value={dateOnly(customer?.onboarding_date)} mono />
          <Field label="Email" value={customer?.email} masked={isMasked(customer?.email)} restricted={piiRestricted(customer?.email)} />
          <Field label="Phone" value={customer?.phone} masked={isMasked(customer?.phone)} restricted={piiRestricted(customer?.phone)} />
          <Field label="Nationality" value={customer?.nationality} restricted={piiRestricted(customer?.nationality)} />
          <Field label="Date of birth" value={customer?.date_of_birth ? dateOnly(customer.date_of_birth) : customer?.date_of_birth}
            masked={isMasked(customer?.date_of_birth)} restricted={piiRestricted(customer?.date_of_birth)} />
          <Field label="Employment" value={customer?.employment_status} />
          <Field label="Employer" value={customer?.employer_name} />
          <Field label="PEP" value={customer?.pep == null ? null : (customer.pep ? 'Yes' : 'No')} />
          {!isAdmin && (
            <>
              <Field label="National ID" value={customer?.national_id} masked={isMasked(customer?.national_id)} restricted={piiRestricted(customer?.national_id)} />
              <Field label="Passport" value={customer?.passport_number} masked={isMasked(customer?.passport_number)} restricted={piiRestricted(customer?.passport_number)} />
              <Field label="Tax ID" value={customer?.tax_id} masked={isMasked(customer?.tax_id)} restricted={piiRestricted(customer?.tax_id)} />
              <Field label="Annual income" value={customer?.annual_income ? money(customer.annual_income) : customer?.annual_income}
                masked={isMasked(customer?.annual_income)} restricted={piiRestricted(customer?.annual_income)} />
              <Field label="Net worth band" value={customer?.net_worth_band} masked={isMasked(customer?.net_worth_band)} restricted={piiRestricted(customer?.net_worth_band)} />
            </>
          )}
        </div>
      </SectionCard>

      {/* Banking relationship */}
      <SectionCard title="Banking Relationship" icon={<Landmark size={12} />}>
        <div className="divide-y divide-white/5">
          <KeyValueRow label="Primary branch" value={relationship?.primary_branch} />
          <KeyValueRow label="Region" value={relationship?.region} />
          <KeyValueRow label="Relationship duration" value={relationship?.relationship_duration_days != null ? `${relationship.relationship_duration_days} days` : null} />
          <KeyValueRow label="Products held" value={relationship?.products_held} />
        </div>
        {relationship?.relationship_managers?.length ? (
          <div className="mt-3 space-y-2">
            {relationship.relationship_managers.map((rm, i) => (
              <div key={rm.employee_id ?? i} className="rounded-xl border p-3"
                style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                <p className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>{rm.name ?? 'Unnamed'}</p>
                <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
                  {[rm.title, rm.portfolio_type].filter(Boolean).join(' · ') || 'Relationship manager'}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[11px] mt-3" style={{ color: 'var(--text-subtle)' }}>No relationship manager assigned.</p>
        )}
      </SectionCard>

      {/* Financial / operational summary */}
      <SectionCard title={isAdmin ? 'Operational Summary' : 'Financial Summary'} icon={<Wallet size={12} />}>
        {financialGranted && fs ? (
          <div className="space-y-3">
            <div className="flex gap-6 text-xs">
              <span style={{ color: 'var(--text-muted)' }}>{fs.account_count} accounts ({fs.active_account_count} active)</span>
              <span style={{ color: 'var(--text-muted)' }}>{fs.loan_count} loans</span>
              {fs.maximum_days_past_due != null && (
                <span className="flex items-center gap-1" style={{ color: 'var(--accent-red)' }}>
                  <AlertCircle size={12} /> Max DPD {fs.maximum_days_past_due}
                </span>
              )}
            </div>
            {Object.entries(fs.total_balance_by_currency).map(([cur, val]) => (
              <KeyValueRow key={cur} label={`Total balance (${cur})`} value={money(val, cur)} mono />
            ))}
            {Object.entries(fs.available_balance_by_currency).map(([cur, val]) => (
              <KeyValueRow key={cur} label={`Available (${cur})`} value={money(val, cur)} mono />
            ))}
            {Object.entries(fs.total_outstanding_loans_by_currency).map(([cur, val]) => (
              <KeyValueRow key={cur} label={`Loans outstanding (${cur})`} value={money(val, cur)} mono />
            ))}
            <div className="flex items-center gap-2 pt-1 text-[10px]" style={{ color: 'var(--text-muted)' }}>
              <FileClock size={11} />
              {fs.recent_transaction_count} transactions in the last 30 days
            </div>
          </div>
        ) : adminMeta ? (
          <div className="space-y-2">
            <div className="flex gap-6 text-xs">
              <span style={{ color: 'var(--text-muted)' }}>{adminMeta.account_count} accounts ({adminMeta.active_account_count} active)</span>
              <span style={{ color: 'var(--text-muted)' }}>{adminMeta.product_count} products</span>
              <span style={{ color: 'var(--text-muted)' }}>{adminMeta.loan_count} loans</span>
            </div>
            <RestrictedNotice label="Balances and loan amounts are not available in the metadata view" />
          </div>
        ) : (
          <RestrictedNotice label="Financial details are not available for your access level" />
        )}
      </SectionCard>

      {/* Risk summary */}
      <SectionCard title="Risk Summary" icon={<ShieldAlert size={12} />}>
        {riskGranted && risk ? (
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-xl font-bold font-mono" style={{ color: 'var(--text-secondary)' }}>
                {risk.risk_score != null ? risk.risk_score.toFixed(2) : '—'}
              </span>
              {risk.highest_active_severity && (
                <StatusBadge variant={severityVariant(risk.highest_active_severity)}>
                  {risk.highest_active_severity}
                </StatusBadge>
              )}
            </div>
            {risk.risk_factors.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {risk.risk_factors.map((f) => (
                  <span key={f} className="px-2 py-0.5 rounded text-[10px] font-mono border"
                    style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                    {f}
                  </span>
                ))}
              </div>
            )}
            <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              {risk.unresolved_flag_count} unresolved {risk.unresolved_flag_count === 1 ? 'flag' : 'flags'}
            </p>
          </div>
        ) : adminMeta ? (
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-xl font-bold font-mono" style={{ color: 'var(--text-secondary)' }}>
                {adminMeta.risk_score != null ? adminMeta.risk_score.toFixed(2) : '—'}
              </span>
              {adminMeta.risk_classification && (
                <StatusBadge variant={severityVariant(adminMeta.risk_classification)}>
                  {adminMeta.risk_classification}
                </StatusBadge>
              )}
              {adminMeta.highest_active_severity && (
                <StatusBadge variant={severityVariant(adminMeta.highest_active_severity)}>
                  top {adminMeta.highest_active_severity}
                </StatusBadge>
              )}
            </div>
            <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              {adminMeta.active_flag_count} active {adminMeta.active_flag_count === 1 ? 'flag' : 'flags'} (metadata only)
            </p>
            <RestrictedNotice label="Risk flag details are not available in the metadata view" />
          </div>
        ) : (
          <RestrictedNotice label="Risk details are not available for your access level" />
        )}
      </SectionCard>

      {/* KYC status */}
      <SectionCard title="KYC & AML" icon={<Scale size={12} />}>
        {kycGranted && kyc ? (
          <div className="space-y-2">
            <KeyValueRow label="KYC status" value={kyc.kyc_status} />
            <KeyValueRow label="Next review" value={dateOnly(kyc.next_review_date)} mono />
            <KeyValueRow label="PEP screening" value={kyc.pep_screening?.status} />
            <KeyValueRow label="Sanctions screening" value={kyc.sanctions_screening?.status} />
            <KeyValueRow label="SAR count" value={kyc.sar_count} />
            <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              Status-level view{adminView ? '' : ' — detailed screening is on the Risk & KYC tab'}
            </p>
          </div>
        ) : adminMeta ? (
          <div className="space-y-2">
            <KeyValueRow label="KYC status" value={adminMeta.kyc_status} />
            <RestrictedNotice label="KYC and AML details are not available in the metadata view" />
          </div>
        ) : (
          <RestrictedNotice label="KYC and AML details are not available for your access level" />
        )}
      </SectionCard>

      {/* Recent activity */}
      {overview.recent_transactions.length > 0 && (
        <SectionCard title="Recent Activity" icon={<FileClock size={12} />} className="lg:col-span-2">
          <TransactionsTable rows={overview.recent_transactions.slice(0, 10)} />
        </SectionCard>
      )}
    </div>
  );
}

// ── Accounts & Loans tab ────────────────────────────────────────────────────

function AccountsTab({ overview }: { overview: Customer360Overview }) {
  const { accounts, loans, financial_summary: fs } = overview;
  const hasAny = accounts.length > 0 || loans.length > 0;

  if (!hasAny) {
    return (
      <EmptyState
        icon={<Wallet size={18} />}
        title="No accounts or loans on record"
        description="This customer has no accounts or loans within your permitted scope."
      />
    );
  }

  const delinquent = loans.filter((l) => (l.days_past_due ?? 0) > 0);

  return (
    <div className="space-y-5">
      {fs && (Object.keys(fs.total_balance_by_currency).length > 0 || Object.keys(fs.total_outstanding_loans_by_currency).length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(fs.total_balance_by_currency).map(([cur, val]) => (
            <div key={cur} className="rounded-xl border p-4" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
              <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Total balance · {cur}</p>
              <p className="text-lg font-bold font-mono" style={{ color: 'var(--accent-green)' }}>{money(val, cur)}</p>
            </div>
          ))}
          {Object.entries(fs.total_outstanding_loans_by_currency).map(([cur, val]) => (
            <div key={cur} className="rounded-xl border p-4" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
              <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Loans outstanding · {cur}</p>
              <p className="text-lg font-bold font-mono" style={{ color: 'var(--accent-red)' }}>{money(val, cur)}</p>
            </div>
          ))}
        </div>
      )}

      {delinquent.length > 0 && (
        <div className="rounded-xl border p-3 text-xs flex items-center gap-2"
          style={{ background: 'rgba(220,38,38,0.06)', borderColor: 'rgba(220,38,38,0.2)' }}>
          <AlertCircle size={14} style={{ color: 'var(--accent-red)' }} />
          <span style={{ color: 'var(--text-secondary)' }}>
            {delinquent.length} {delinquent.length === 1 ? 'loan is' : 'loans are'} past due.
          </span>
        </div>
      )}

      <SectionCard title="Accounts" icon={<Wallet size={12} />}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                {['Account ID', 'Type', 'Status', 'Balance', 'Available', 'Currency', 'Branch', 'Opened'].map((h) => (
                  <th key={h} className="pb-2 pr-3 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {accounts.map((a: AccountSummary) => (
                <tr key={a.account_id} style={{ color: 'var(--text-secondary)' }}>
                  <td className="py-2.5 pr-3 font-mono text-[11px]">{a.account_id}</td>
                  <td className="py-2.5 pr-3">{a.account_type ?? '—'}</td>
                  <td className="py-2.5 pr-3"><StatusBadge variant={statusVariant(a.status)}>{a.status ?? '—'}</StatusBadge></td>
                  <td className="py-2.5 pr-3 text-right font-mono font-semibold whitespace-nowrap">{money(a.balance, a.currency)}</td>
                  <td className="py-2.5 pr-3 text-right font-mono whitespace-nowrap">{money(a.available_balance, a.currency)}</td>
                  <td className="py-2.5 pr-3">{a.currency ?? '—'}</td>
                  <td className="py-2.5 pr-3">{a.branch ?? '—'}</td>
                  <td className="py-2.5 font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>{dateOnly(a.opened_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {accounts.length === 0 && (
          <p className="text-[11px]" style={{ color: 'var(--text-subtle)' }}>No accounts within your permitted scope.</p>
        )}
      </SectionCard>

      <SectionCard title="Loans" icon={<Landmark size={12} />}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                {['Loan ID', 'Product', 'Principal', 'Outstanding', 'Rate', 'Maturity', 'Status', 'DPD'].map((h) => (
                  <th key={h} className="pb-2 pr-3 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loans.map((l: LoanSummary) => {
                const isDelinquent = (l.days_past_due ?? 0) > 0;
                return (
                  <tr key={l.loan_id}
                    style={{
                      color: 'var(--text-secondary)',
                      background: isDelinquent ? 'rgba(220,38,38,0.04)' : undefined,
                    }}>
                    <td className="py-2.5 pr-3 font-mono text-[11px]">{l.loan_id}</td>
                    <td className="py-2.5 pr-3">{l.product ?? l.loan_type ?? '—'}</td>
                    <td className="py-2.5 pr-3 text-right font-mono whitespace-nowrap">{money(l.principal, l.currency)}</td>
                    <td className="py-2.5 pr-3 text-right font-mono font-semibold whitespace-nowrap" style={{ color: isDelinquent ? 'var(--accent-red)' : undefined }}>
                      {money(l.outstanding_balance, l.currency)}
                    </td>
                    <td className="py-2.5 pr-3">{l.interest_rate != null ? `${l.interest_rate}%` : '—'}</td>
                    <td className="py-2.5 pr-3 font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>{dateOnly(l.maturity_date)}</td>
                    <td className="py-2.5 pr-3"><StatusBadge variant={statusVariant(l.status)}>{l.status ?? '—'}</StatusBadge></td>
                    <td className="py-2.5 font-mono text-[11px]" style={{ color: isDelinquent ? 'var(--accent-red)' : 'var(--text-muted)' }}>
                      {l.days_past_due != null ? l.days_past_due : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {loans.length === 0 && (
          <p className="text-[11px]" style={{ color: 'var(--text-subtle)' }}>No loans within your permitted scope.</p>
        )}
      </SectionCard>
    </div>
  );
}

// ── Transactions tab ────────────────────────────────────────────────────────

function TransactionsTab({ overview, data, loading, error, offset, pageSize, onOffsetChange, onRetry }: {
  overview: Customer360Overview;
  data: CustomerTransactionsResponse | null;
  loading: boolean;
  error: Customer360ApiError | null;
  offset: number;
  pageSize: number;
  onOffsetChange: (offset: number) => void;
  onRetry: () => void;
}) {
  const txSummary = data?.transaction_summary ?? overview.transaction_summary;

  const first = data && data.total_count > 0 ? offset + 1 : 0;
  const last = data ? Math.min(offset + (data.recent_transactions?.length ?? 0), data.total_count) : 0;
  const hasPrev = offset > 0;
  const hasNext = data != null && last < data.total_count;

  const summaryCards = txSummary
    ? [
        { label: 'Inbound (30d)', count: txSummary.d30_inbound_count, byCurrency: txSummary.d30_inbound_amount },
        { label: 'Outbound (30d)', count: txSummary.d30_outbound_count, byCurrency: txSummary.d30_outbound_amount },
        { label: 'Total (90d)', count: txSummary.d90_total_count, byCurrency: txSummary.d90_total_amount },
      ]
    : [];

  return (
    <div className="space-y-5">
      {summaryCards.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {summaryCards.map((c) => (
            <div key={c.label} className="rounded-xl border p-4" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
              <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>{c.label}</p>
              <p className="text-sm font-bold font-mono" style={{ color: 'var(--text-secondary)' }}>{c.count}</p>
              {Object.entries(c.byCurrency).map(([cur, val]) => (
                <p key={cur} className="text-[11px] font-mono mt-0.5" style={{ color: 'var(--text-muted)' }}>{money(val, cur)}</p>
              ))}
            </div>
          ))}
        </div>
      )}

      <SectionCard title="Transactions" icon={<FileClock size={12} />}>
        {loading && data === null ? (
          <div className="space-y-2 py-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-10 border rounded-lg animate-pulse" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
            ))}
          </div>
        ) : error ? (
          <div className="py-8 text-center">
            {error.kind === 'forbidden' ? (
              <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
                You do not have permission to view transactions.
              </p>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <AlertCircle size={20} style={{ color: 'var(--accent-amber)' }} />
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  {error.kind === 'not_found'
                    ? 'Customer not found or unavailable.'
                    : error.kind === 'unavailable'
                      ? 'Transactions are temporarily unavailable.'
                      : error.message}
                </p>
                <button onClick={onRetry} className="btn-secondary text-xs">
                  <RefreshCw size={12} /> Retry
                </button>
              </div>
            )}
          </div>
        ) : !data || data.recent_transactions.length === 0 ? (
          <EmptyState
            icon={<FileClock size={18} />}
            title="No transactions on record"
            description="No transactions were found for this customer within your permitted scope."
          />
        ) : (
          <>
            <TransactionsTable rows={data.recent_transactions} />
            <div className="flex items-center justify-between pt-3 mt-2 border-t" style={{ borderColor: 'var(--bg-border)' }}>
              <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                {data.total_count === 0 ? 'No records' : `Showing ${first}–${last} of ${data.total_count}`}
              </p>
              <div className="flex items-center gap-2">
                <button onClick={() => onOffsetChange(Math.max(0, offset - pageSize))} disabled={!hasPrev || loading}
                  className="btn-ghost text-xs px-2.5 py-1.5 disabled:opacity-40">
                  Previous
                </button>
                <button onClick={() => onOffsetChange(offset + pageSize)} disabled={!hasNext || loading}
                  className="btn-ghost text-xs px-2.5 py-1.5 disabled:opacity-40">
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </SectionCard>
    </div>
  );
}

// ── Risk & KYC tab ──────────────────────────────────────────────────────────

function RiskKycTab({ overview, adminView }: { overview: Customer360Overview; adminView: boolean }) {
  const risk = overview.risk;
  const kyc = overview.kyc_aml;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {risk && (
        <SectionCard title="Risk Profile" icon={<ShieldAlert size={12} />}>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl font-bold font-mono" style={{ color: 'var(--text-secondary)' }}>
              {risk.risk_score != null ? risk.risk_score.toFixed(2) : '—'}
            </span>
            {risk.highest_active_severity && (
              <StatusBadge variant={severityVariant(risk.highest_active_severity)}>
                highest {risk.highest_active_severity}
              </StatusBadge>
            )}
          </div>
          {risk.risk_factors.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-4">
              {risk.risk_factors.map((f) => (
                <span key={f} className="px-2 py-0.5 rounded text-[10px] font-mono border"
                  style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                  {f}
                </span>
              ))}
            </div>
          )}
          {risk.active_flags.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                    {['Type', 'Severity', 'Description', 'Created'].map((h) => (
                      <th key={h} className="pb-2 pr-3 font-semibold">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {risk.active_flags.map((f) => (
                    <tr key={f.flag_id} style={{ color: 'var(--text-secondary)' }}>
                      <td className="py-2.5 pr-3 font-mono text-[11px]">{f.flag_type ?? '—'}</td>
                      <td className="py-2.5 pr-3"><StatusBadge variant={severityVariant(f.severity)}>{f.severity ?? '—'}</StatusBadge></td>
                      <td className="py-2.5 pr-3 max-w-xs">{f.description ?? '—'}</td>
                      <td className="py-2.5 font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>{dateOnly(f.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-[11px] flex items-center gap-1.5" style={{ color: 'var(--accent-green)' }}>
              <CheckCircle2 size={13} /> No active risk flags.
            </p>
          )}
        </SectionCard>
      )}

      {kyc && (
        <SectionCard title="KYC & AML" icon={<Scale size={12} />}>
          <div className="space-y-3">
            <KeyValueRow label="KYC status" value={kyc.kyc_status} />
            <KeyValueRow label="Next review" value={dateOnly(kyc.next_review_date)} mono />
            {kyc.latest_kyc_case && (
              <div className="rounded-xl border p-3" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
                  Latest KYC case
                </p>
                <div className="space-y-1.5">
                  {kyc.latest_kyc_case.kyc_case_id && (
                    <KeyValueRow label="Case ID" value={kyc.latest_kyc_case.kyc_case_id} mono />
                  )}
                  <KeyValueRow label="Type" value={kyc.latest_kyc_case.case_type} />
                  <KeyValueRow label="Status" value={kyc.latest_kyc_case.status} />
                  <KeyValueRow label="Risk level" value={kyc.latest_kyc_case.risk_level} />
                  <KeyValueRow label="Opened" value={dateOnly(kyc.latest_kyc_case.opened_at)} mono />
                </div>
              </div>
            )}

            {(kyc.pep_screening || kyc.sanctions_screening) && (
              <div className="space-y-2">
                {kyc.pep_screening && (
                  <div className="rounded-xl border p-3" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                    <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>PEP screening</p>
                    <KeyValueRow label="Status" value={kyc.pep_screening.status} />
                    <KeyValueRow label="Risk level" value={kyc.pep_screening.risk_level} />
                    <KeyValueRow label="Match score" value={kyc.pep_screening.match_score != null ? money(kyc.pep_screening.match_score) : null} />
                    <KeyValueRow label="List" value={kyc.pep_screening.list_name} />
                    {kyc.pep_screening.matched_name && (
                      <KeyValueRow label="Matched name" value={kyc.pep_screening.matched_name} />
                    )}
                    <KeyValueRow label="Checked" value={dateOnly(kyc.pep_screening.checked_at)} mono />
                  </div>
                )}
                {kyc.sanctions_screening && (
                  <div className="rounded-xl border p-3" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                    <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Sanctions screening</p>
                    <KeyValueRow label="Status" value={kyc.sanctions_screening.status} />
                    <KeyValueRow label="Risk level" value={kyc.sanctions_screening.risk_level} />
                    <KeyValueRow label="Match score" value={kyc.sanctions_screening.match_score != null ? money(kyc.sanctions_screening.match_score) : null} />
                    <KeyValueRow label="List" value={kyc.sanctions_screening.list_name} />
                    {kyc.sanctions_screening.matched_name && (
                      <KeyValueRow label="Matched name" value={kyc.sanctions_screening.matched_name} />
                    )}
                    <KeyValueRow label="Checked" value={dateOnly(kyc.sanctions_screening.checked_at)} mono />
                  </div>
                )}
              </div>
            )}

            {(Object.keys(kyc.aml_alert_counts_by_status).length > 0 ||
              Object.keys(kyc.aml_alert_counts_by_severity).length > 0 ||
              kyc.sar_count > 0) && (
              <div className="rounded-xl border p-3" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>AML summary</p>
                <div className="flex flex-wrap gap-x-6 gap-y-1">
                  {Object.entries(kyc.aml_alert_counts_by_status).map(([s, c]) => (
                    <span key={s} className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {s}: <strong className="font-mono">{c}</strong>
                    </span>
                  ))}
                  {Object.entries(kyc.aml_alert_counts_by_severity).map(([s, c]) => (
                    <span key={s} className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {s}: <strong className="font-mono">{c}</strong>
                    </span>
                  ))}
                  {kyc.sar_count > 0 && (
                    <span className="text-xs" style={{ color: 'var(--accent-red)' }}>
                      SARs: <strong className="font-mono">{kyc.sar_count}</strong>
                    </span>
                  )}
                </div>
              </div>
            )}

            {adminView && <RestrictedNotice label="Only status-level KYC is shown in your view" />}
          </div>
        </SectionCard>
      )}
    </div>
  );
}

// ── Alerts & Cases tab ──────────────────────────────────────────────────────

function AlertsTab({ analyticsGranted, workbenchGranted, alerts, links }: {
  analyticsGranted: boolean;
  workbenchGranted: boolean;
  alerts: AmlAlertSummary[];
  links: WorkbenchLink[];
}) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <SectionCard title="Analytics Alerts" icon={<Inbox size={12} />}>
        {!analyticsGranted ? (
          <RestrictedNotice label="Analytics alerts" />
        ) : alerts.length === 0 ? (
          <p className="text-[11px]" style={{ color: 'var(--text-subtle)' }}>No analytics alerts on record.</p>
        ) : (
          <div className="space-y-2">
            {alerts.map((a) => (
              <div key={a.alert_id} className="rounded-xl border p-3" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>{a.alert_id}</span>
                  <StatusBadge variant={severityVariant(a.severity)}>{a.severity ?? '—'}</StatusBadge>
                </div>
                <p className="text-xs font-semibold mt-1" style={{ color: 'var(--text-secondary)' }}>
                  {a.label ?? a.alert_type ?? 'AML alert'}
                </p>
                <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
                  {[a.alert_type, a.status, a.score != null ? `score ${money(a.score)}` : null, dateOnly(a.triggered_at)].filter(Boolean).join(' · ')}
                </p>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      <SectionCard title="Workbench Records" icon={<Inbox size={12} />}>
        {!workbenchGranted ? (
          <RestrictedNotice label="Workbench records" />
        ) : links.length === 0 ? (
          <p className="text-[11px]" style={{ color: 'var(--text-subtle)' }}>No operational records explicitly linked to this customer.</p>
        ) : (
          <div className="space-y-2">
            {links.map((l) => {
              const route = `${ENTITY_ROUTES[l.entity_type]}/${l.entity_id}`;
              return (
                <div key={`${l.entity_type}-${l.entity_id}`} className="rounded-xl border p-3"
                  style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <StatusBadge variant={entityVariant(l.entity_type)}>{ENTITY_LABELS[l.entity_type]}</StatusBadge>
                    <StatusBadge variant={statusVariant(l.status)}>{l.status ?? '—'}</StatusBadge>
                  </div>
                  <Link to={route} className="font-mono text-[11px] mt-1.5 block underline decoration-dotted hover:brightness-125"
                    style={{ color: 'var(--accent-blue)' }}>
                    {l.entity_id}
                  </Link>
                  <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
                    {[
                      l.assigned_to ? `assigned to ${l.assigned_to}` : null,
                      l.updated_at ? `updated ${dateOnly(l.updated_at)}` : null,
                      l.scope_id ? `scope ${l.scope_id}` : null,
                      l.source ? `source ${l.source}` : null,
                    ].filter(Boolean).join(' · ')}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
