// src/pages/RiskPage.tsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { riskApi } from '../api/riskApi';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { BankingHeader } from '../components/Layout/BankingHeader';
import { formatCurrency, formatNumber, formatPercent, formatDateTime } from '../utils/formatters';
import type { RiskOverview, RiskFlag, RiskSegment } from '../types/api';
import {
  ShieldAlert,
  AlertOctagon,
  Percent,
  Users,
  Search,
  CheckCircle2,
  XCircle,
  Filter,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Info
} from 'lucide-react';
import { clsx } from 'clsx';

export function RiskPage() {
  const [overview, setOverview] = useState<RiskOverview | null>(null);
  const [segments, setSegments] = useState<RiskSegment[]>([]);
  const [flags, setFlags] = useState<RiskFlag[]>([]);
  const [totalFlagsCount, setTotalFlagsCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [apiFailed, setApiFailed] = useState(false);

  // Pagination & Filtering
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [resolvedFilter, setResolvedFilter] = useState<string>(''); // 'true', 'false', or '' for all

  const fetchRiskData = async () => {
    setLoading(true);
    setApiFailed(false);
    try {
      const resolvedParam = resolvedFilter === 'true' ? true : resolvedFilter === 'false' ? false : undefined;
      const [fetchedOverview, fetchedSegments, paginatedFlags] = await Promise.all([
        riskApi.getOverview(),
        riskApi.getSegments(),
        riskApi.getFlags(page, pageSize, severityFilter || undefined, resolvedParam)
      ]);

      setOverview(fetchedOverview);
      setSegments(fetchedSegments);
      setFlags(paginatedFlags.items);
      setTotalFlagsCount(paginatedFlags.total);
    } catch (err) {
      console.error('Failed to fetch credit risk data:', err);
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRiskData();
  }, [page, severityFilter, resolvedFilter]);

  const totalPages = Math.ceil(totalFlagsCount / pageSize) || 1;

  // Helpers for styling risk scores — returns inline style objects using CSS variables
  const getRiskScoreStyles = (score: number): React.CSSProperties => {
    if (score >= 0.7) return {
      color: 'var(--accent-red)',
      borderColor: 'color-mix(in srgb, var(--accent-red) 20%, transparent)',
      background: 'color-mix(in srgb, var(--accent-red) 5%, transparent)',
    };
    if (score >= 0.4) return {
      color: 'var(--accent-amber)',
      borderColor: 'color-mix(in srgb, var(--accent-amber) 20%, transparent)',
      background: 'color-mix(in srgb, var(--accent-amber) 5%, transparent)',
    };
    return {
      color: 'var(--accent-green)',
      borderColor: 'color-mix(in srgb, var(--accent-green) 20%, transparent)',
      background: 'color-mix(in srgb, var(--accent-green) 5%, transparent)',
    };
  };

  const getSeverityBadgeStyles = (severity: string): React.CSSProperties => {
    switch (severity.toLowerCase()) {
      case 'critical': return {
        color: 'var(--accent-red)',
        background: 'color-mix(in srgb, var(--accent-red) 40%, transparent)',
        borderColor: 'color-mix(in srgb, var(--accent-red) 30%, transparent)',
      };
      case 'high': return {
        color: 'var(--accent-red)',
        background: 'color-mix(in srgb, var(--accent-red) 10%, transparent)',
        borderColor: 'color-mix(in srgb, var(--accent-red) 20%, transparent)',
      };
      case 'medium': return {
        color: 'var(--accent-amber)',
        background: 'color-mix(in srgb, var(--accent-amber) 10%, transparent)',
        borderColor: 'color-mix(in srgb, var(--accent-amber) 20%, transparent)',
      };
      default: return {
        color: 'var(--accent-blue)',
        background: 'color-mix(in srgb, var(--accent-blue) 10%, transparent)',
        borderColor: 'color-mix(in srgb, var(--accent-blue) 20%, transparent)',
      };
    }
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <BankingHeader
        title="Credit & Portfolio Risk Monitor"
        subtitle="Exposure analytics, delinquent levels, and critical risk notifications"
        onRefresh={fetchRiskData}
        isRefreshing={loading}
      />
      <div className="flex-1 p-6 space-y-8 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {apiFailed ? (
          <div className="space-y-6">
            <ServiceUnavailable
              serviceName="Credit & Portfolio Risk Service"
              missingEndpoint="GET /risk/overview"
              method="GET"
            />
            <div className="flex justify-center">
              <button
                onClick={() => fetchRiskData()}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 hover:opacity-90"
                style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
              >
                <RefreshCw size={16} className={clsx(loading && "animate-spin")} />
                Retry Connection
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Top Indicator Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-5">
              {loading && !overview ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="rounded-xl border h-24 animate-pulse" style={{ borderColor: 'var(--bg-border)', background: 'var(--bg-card)' }} />
                ))
              ) : overview ? (
                <>
                  {/* Avg Risk Score */}
                  <div className="rounded-xl border p-4 flex items-center justify-between" style={{ borderColor: 'var(--bg-border)', background: 'var(--bg-card)' }}>
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider" style={{ color: 'var(--text-muted)' }}>Average Risk Index</p>
                      <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{(overview.average_risk_score * 100).toFixed(1)}%</span>
                        <span className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>({overview.average_risk_score.toFixed(4)})</span>
                      </div>
                    </div>
                    <div className="w-10 h-10 rounded-lg border flex items-center justify-center font-bold text-sm" style={getRiskScoreStyles(overview.average_risk_score)}>
                      {overview.average_risk_score >= 0.7 ? 'H' : overview.average_risk_score >= 0.4 ? 'M' : 'L'}
                    </div>
                  </div>

                  {/* Open Flags */}
                  <div className="rounded-xl border p-4 flex items-center justify-between" style={{ borderColor: 'var(--bg-border)', background: 'var(--bg-card)' }}>
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider" style={{ color: 'var(--text-muted)' }}>Open Risk Flags</p>
                      <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-secondary)' }}>{formatNumber(overview.total_flags)}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg border flex items-center justify-center" style={{ background: 'color-mix(in srgb, var(--accent-red) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--accent-red) 25%, transparent)', color: 'var(--accent-red)' }}>
                      <ShieldAlert size={18} />
                    </div>
                  </div>

                  {/* Critical Flags */}
                  <div className="rounded-xl border p-4 flex items-center justify-between" style={{ borderColor: 'var(--bg-border)', background: 'var(--bg-card)' }}>
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider" style={{ color: 'var(--text-muted)' }}>Critical Flags</p>
                      <p className="text-2xl font-bold mt-1" style={{ color: 'var(--accent-red)' }}>{formatNumber(overview.critical_flags)}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg border flex items-center justify-center animate-pulse" style={{ background: 'color-mix(in srgb, var(--accent-red) 30%, transparent)', borderColor: 'color-mix(in srgb, var(--accent-red) 40%, transparent)', color: 'var(--accent-red)' }}>
                      <AlertOctagon size={18} />
                    </div>
                  </div>

                  {/* High Risk Portfolios */}
                  <div className="rounded-xl border p-4 flex items-center justify-between" style={{ borderColor: 'var(--bg-border)', background: 'var(--bg-card)' }}>
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider" style={{ color: 'var(--text-muted)' }}>High Risk Portfolios</p>
                      <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-secondary)' }}>{formatNumber(overview.high_risk_customer_count)}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg border flex items-center justify-center" style={{ background: 'color-mix(in srgb, var(--accent-amber) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--accent-amber) 25%, transparent)', color: 'var(--accent-amber)' }}>
                      <Users size={18} />
                    </div>
                  </div>

                  {/* KYC Incomplete */}
                  <div className="rounded-xl border p-4 flex items-center justify-between" style={{ borderColor: 'var(--bg-border)', background: 'var(--bg-card)' }}>
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider" style={{ color: 'var(--text-muted)' }}>KYC Incomplete</p>
                      <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-secondary)' }}>{formatNumber(overview.kyc_incomplete_count)}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg border flex items-center justify-center" style={{ background: 'color-mix(in srgb, var(--accent-blue) 10%, transparent)', borderColor: 'color-mix(in srgb, var(--accent-blue) 25%, transparent)', color: 'var(--accent-blue)' }}>
                      <Percent size={18} />
                    </div>
                  </div>
                </>
              ) : null}
            </div>

            {/* Segment Analysis Grid */}
            <div className="border rounded-2xl p-6 backdrop-blur-md" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
              <h3 className="text-sm font-bold mb-5 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Users size={16} style={{ color: 'var(--accent-blue)' }} />
                Customer Segment Risk Concentration
              </h3>

              {loading && segments.length === 0 ? (
                <div className="space-y-2 py-4">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-10 border rounded-lg animate-pulse" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
                  ))}
                </div>
              ) : segments.length === 0 ? (
                <div className="text-center py-12 text-xs" style={{ color: 'var(--text-muted)' }}>
                  No segment telemetry logs available.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                        <th className="pb-3 font-semibold">Segment Group</th>
                        <th className="pb-3 font-semibold text-right">Customer Count</th>
                        <th className="pb-3 font-semibold text-center">Avg Credit Risk Score</th>
                        <th className="pb-3 font-semibold text-right">Total Active Balance</th>
                        <th className="pb-3 font-semibold">Exposure Indicator</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {segments.map((seg) => {
                        const pctRisk = Math.min(100, seg.avg_risk_score * 100);
                        const isHigh = seg.avg_risk_score >= 0.6;
                        const isMed = seg.avg_risk_score >= 0.35 && seg.avg_risk_score < 0.6;

                        return (
                          <tr key={seg.segment} className="hover:bg-white/5 transition-all">
                            <td className="py-4 font-bold capitalize" style={{ color: 'var(--text-secondary)' }}>{seg.segment}</td>
                            <td className="py-4 text-right font-mono" style={{ color: 'var(--text-secondary)' }}>{formatNumber(seg.customer_count)}</td>
                            <td className="py-4 text-center">
                              <span className="px-2.5 py-0.5 rounded font-mono font-semibold text-xs border" style={getRiskScoreStyles(seg.avg_risk_score)}>
                                {(seg.avg_risk_score * 100).toFixed(1)}%
                              </span>
                            </td>
                            <td className="py-4 text-right font-mono" style={{ color: 'var(--text-secondary)' }}>{formatCurrency(seg.total_balance)}</td>
                            <td className="py-4">
                              <div className="w-40 border h-2 rounded-full overflow-hidden flex" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
                                <div
                                  className="h-full rounded-full transition-all duration-300"
                                  style={{
                                    width: `${pctRisk}%`,
                                    background: isHigh ? 'var(--accent-red)' : isMed ? 'var(--accent-amber)' : 'var(--accent-green)',
                                  }}
                                />
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Risk Flags registry database table */}
            <div className="border rounded-2xl p-6 backdrop-blur-md" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                  <h3 className="text-sm font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                    <ShieldAlert size={16} style={{ color: 'var(--accent-blue)' }} />
                    Risk Flag Registry Database
                  </h3>
                  <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>Filter, trace, and audit active portfolio security warnings</p>
                </div>

                {/* Filters Row */}
                <div className="flex flex-wrap items-center gap-3">
                  {/* Severity filter */}
                  <div className="flex items-center gap-2">
                    <Filter size={12} style={{ color: 'var(--text-muted)' }} />
                    <select
                      value={severityFilter}
                      onChange={(e) => { setSeverityFilter(e.target.value); setPage(1); }}
                      className="border rounded-lg px-2 py-1 text-xs outline-none focus:outline-none focus:border-[var(--accent-blue)]"
                      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
                    >
                      <option value="">All Severities</option>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>

                  {/* Status filter */}
                  <select
                    value={resolvedFilter}
                    onChange={(e) => { setResolvedFilter(e.target.value); setPage(1); }}
                    className="border rounded-lg px-2 py-1 text-xs outline-none focus:outline-none focus:border-[var(--accent-blue)]"
                    style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}
                  >
                    <option value="">All Statuses</option>
                    <option value="false">Active / Open</option>
                    <option value="true">Resolved</option>
                  </select>
                </div>
              </div>

              {loading && flags.length === 0 ? (
                <div className="space-y-2 py-4">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-10 border rounded-lg animate-pulse" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
                  ))}
                </div>
              ) : flags.length === 0 ? (
                <div className="text-center py-12 border border-dashed rounded-xl text-xs flex flex-col items-center justify-center gap-2" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                  <CheckCircle2 size={24} style={{ color: 'var(--accent-green)' }} />
                  <span>No security flags match your filters.</span>
                </div>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                          <th className="pb-3 font-semibold w-24">Flag ID</th>
                          <th className="pb-3 font-semibold w-28">Customer ID</th>
                          <th className="pb-3 font-semibold w-40">Type</th>
                          <th className="pb-3 font-semibold w-24">Severity</th>
                          <th className="pb-3 font-semibold">Incident / Flag Description</th>
                          <th className="pb-3 font-semibold text-center w-24">Status</th>
                          <th className="pb-3 font-semibold text-right w-36">Timestamp</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {flags.map((flag) => (
                          <tr key={flag.flag_id} className="hover:bg-white/5 transition-all">
                            <td className="py-4 font-mono text-[10px] font-semibold select-all" style={{ color: 'var(--text-muted)' }}>#{flag.flag_id.slice(0, 8)}...</td>
                            <td className="py-4 font-mono text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
                              <Link to={`/workbench/customers/${flag.customer_id}`}
                                className="underline decoration-dotted hover:brightness-125" style={{ color: 'var(--accent-blue)' }}>
                                {flag.customer_id.slice(0, 8)}...
                              </Link>
                            </td>
                            <td className="py-4">
                              <span className="font-mono text-[10px] font-semibold px-1.5 py-0.5 rounded border uppercase" style={{ color: 'var(--text-secondary)', background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
                                {flag.flag_type.replace('_', ' ')}
                              </span>
                            </td>
                            <td className="py-4">
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold border uppercase tracking-wider" style={getSeverityBadgeStyles(flag.severity)}>
                                {flag.severity}
                              </span>
                            </td>
                            <td className="py-4 leading-relaxed max-w-sm" style={{ color: 'var(--text-muted)' }}>{flag.description}</td>
                            <td className="py-4 text-center">
                              <span
                                className="px-1.5 py-0.5 rounded-full text-[9px] font-semibold inline-flex items-center gap-1 border"
                                style={flag.resolved ? {
                                  color: 'var(--accent-green)',
                                  background: 'color-mix(in srgb, var(--accent-green) 8%, transparent)',
                                  borderColor: 'color-mix(in srgb, var(--accent-green) 20%, transparent)',
                                } : {
                                  color: 'var(--accent-red)',
                                  background: 'color-mix(in srgb, var(--accent-red) 8%, transparent)',
                                  borderColor: 'color-mix(in srgb, var(--accent-red) 20%, transparent)',
                                }}
                              >
                                <span className="w-1 h-1 rounded-full" style={{ background: flag.resolved ? 'var(--accent-green)' : 'var(--accent-red)' }} />
                                {flag.resolved ? 'Resolved' : 'Active'}
                              </span>
                            </td>
                            <td className="py-4 text-right font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                              {formatDateTime(flag.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination Controls */}
                  <div className="flex items-center justify-between border-t mt-5 pt-4" style={{ borderColor: 'var(--bg-border)' }}>
                    <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                      Showing page <span className="font-semibold" style={{ color: 'var(--text-secondary)' }}>{page}</span> of <span className="font-semibold" style={{ color: 'var(--text-secondary)' }}>{totalPages}</span> ({totalFlagsCount} items)
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="p-1.5 rounded-lg border disabled:opacity-30 disabled:pointer-events-none transition-all hover:opacity-80"
                        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}
                      >
                        <ChevronLeft size={14} />
                      </button>
                      <button
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages}
                        className="p-1.5 rounded-lg border disabled:opacity-30 disabled:pointer-events-none transition-all hover:opacity-80"
                        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}
                      >
                        <ChevronRight size={14} />
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
