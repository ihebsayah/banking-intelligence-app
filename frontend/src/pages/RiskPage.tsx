// src/pages/RiskPage.tsx
import React, { useEffect, useState } from 'react';
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

  // Helpers for styling risk scores
  const getRiskScoreColor = (score: number) => {
    if (score >= 0.7) return 'text-red-400 border-red-500/20 bg-red-500/5';
    if (score >= 0.4) return 'text-amber-400 border-amber-500/20 bg-amber-500/5';
    return 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5';
  };

  const getSeverityBadgeClass = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical': return 'bg-red-950/40 text-red-400 border border-red-800/30 font-bold';
      case 'high':     return 'bg-red-500/10 text-red-300 border border-red-500/20';
      case 'medium':   return 'bg-amber-500/10 text-amber-400 border border-amber-500/20';
      default:         return 'bg-blue-500/10 text-blue-400 border border-blue-500/20';
    }
  };

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
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
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#0066CC] hover:bg-[#0052a3] text-white text-sm font-semibold shadow-lg shadow-[#0066CC]/20 hover:shadow-[#0066CC]/35 transition-all duration-200"
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
                  <div key={i} className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 h-24 animate-pulse" />
                ))
              ) : overview ? (
                <>
                  {/* Avg Risk Score */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500">Average Risk Index</p>
                      <div className="flex items-baseline gap-2 mt-1">
                        <span className="text-2xl font-bold text-white">{(overview.average_risk_score * 100).toFixed(1)}%</span>
                        <span className="text-[10px] text-slate-500 font-mono">({overview.average_risk_score.toFixed(4)})</span>
                      </div>
                    </div>
                    <div className={clsx("w-10 h-10 rounded-lg border flex items-center justify-center font-bold text-sm", getRiskScoreColor(overview.average_risk_score))}>
                      {overview.average_risk_score >= 0.7 ? 'H' : overview.average_risk_score >= 0.4 ? 'M' : 'L'}
                    </div>
                  </div>

                  {/* Open Flags */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500">Open Risk Flags</p>
                      <p className="text-2xl font-bold text-slate-200 mt-1">{formatNumber(overview.total_flags)}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-red-500/10 border border-red-500/25 flex items-center justify-center text-red-400 shadow-[0_0_15px_rgba(239,68,68,0.1)]">
                      <ShieldAlert size={18} />
                    </div>
                  </div>

                  {/* Critical Flags */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500">Critical Flags</p>
                      <p className="text-2xl font-bold text-red-400 mt-1">{formatNumber(overview.critical_flags)}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-red-950/30 border border-red-800/40 flex items-center justify-center text-red-400 animate-pulse">
                      <AlertOctagon size={18} />
                    </div>
                  </div>

                  {/* High Risk Portfolios */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500">High Risk Portfolios</p>
                      <p className="text-2xl font-bold text-slate-200 mt-1">{formatNumber(overview.high_risk_customer_count)}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-400">
                      <Users size={18} />
                    </div>
                  </div>

                  {/* KYC Incomplete */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500">KYC Incomplete</p>
                      <p className="text-2xl font-bold text-slate-200 mt-1">{formatNumber(overview.kyc_incomplete_count)}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/25 flex items-center justify-center text-[#4d9fff]">
                      <Percent size={18} />
                    </div>
                  </div>
                </>
              ) : null}
            </div>

            {/* Segment Analysis Grid */}
            <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
              <h3 className="text-sm font-bold text-white mb-5 flex items-center gap-2">
                <Users size={16} className="text-[#0066CC]" />
                Customer Segment Risk Concentration
              </h3>
              
              {loading && segments.length === 0 ? (
                <div className="space-y-2 py-4">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-10 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />
                  ))}
                </div>
              ) : segments.length === 0 ? (
                <div className="text-center py-12 text-slate-500 text-xs">
                  No segment telemetry logs available.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-[#0f2244] text-slate-500">
                        <th className="pb-3 font-semibold">Segment Group</th>
                        <th className="pb-3 font-semibold text-right">Customer Count</th>
                        <th className="pb-3 font-semibold text-center">Avg Credit Risk Score</th>
                        <th className="pb-3 font-semibold text-right">Total Active Balance</th>
                        <th className="pb-3 font-semibold">Exposure Indicator</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#0f2244]/50">
                      {segments.map((seg) => {
                        const pctRisk = Math.min(100, seg.avg_risk_score * 100);
                        const isHigh = seg.avg_risk_score >= 0.6;
                        const isMed = seg.avg_risk_score >= 0.35 && seg.avg_risk_score < 0.6;
                        
                        return (
                          <tr key={seg.segment} className="hover:bg-[#0c1930]/25 transition-all">
                            <td className="py-4 font-bold text-slate-200 capitalize">{seg.segment}</td>
                            <td className="py-4 text-right font-mono text-slate-300">{formatNumber(seg.customer_count)}</td>
                            <td className="py-4 text-center">
                              <span className={clsx(
                                "px-2.5 py-0.5 rounded font-mono font-semibold text-xs border",
                                getRiskScoreColor(seg.avg_risk_score)
                              )}>
                                {(seg.avg_risk_score * 100).toFixed(1)}%
                              </span>
                            </td>
                            <td className="py-4 text-right font-mono text-slate-350">{formatCurrency(seg.total_balance)}</td>
                            <td className="py-4">
                              <div className="w-40 bg-[#03060c] border border-[#0f203d] h-2 rounded-full overflow-hidden flex">
                                <div 
                                  className={clsx(
                                    "h-full rounded-full transition-all duration-300",
                                    isHigh ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]" :
                                    isMed ? "bg-amber-500" : "bg-emerald-500"
                                  )}
                                  style={{ width: `${pctRisk}%` }}
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
            <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <ShieldAlert size={16} className="text-[#0066CC]" />
                    Risk Flag Registry Database
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Filter, trace, and audit active portfolio security warnings</p>
                </div>

                {/* Filters Row */}
                <div className="flex flex-wrap items-center gap-3">
                  {/* Severity filter */}
                  <div className="flex items-center gap-2">
                    <Filter size={12} className="text-slate-500" />
                    <select
                      value={severityFilter}
                      onChange={(e) => { setSeverityFilter(e.target.value); setPage(1); }}
                      className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2 py-1 text-xs text-slate-300 outline-none focus:border-[#0066CC]/50"
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
                    className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2 py-1 text-xs text-slate-300 outline-none focus:border-[#0066CC]/50"
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
                    <div key={i} className="h-10 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />
                  ))}
                </div>
              ) : flags.length === 0 ? (
                <div className="text-center py-12 border border-dashed border-[#0f203d] rounded-xl text-slate-500 text-xs flex flex-col items-center justify-center gap-2">
                  <CheckCircle2 size={24} className="text-emerald-500" />
                  <span>No security flags match your filters.</span>
                </div>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-[#0f2244] text-slate-500">
                          <th className="pb-3 font-semibold w-24">Flag ID</th>
                          <th className="pb-3 font-semibold w-28">Customer ID</th>
                          <th className="pb-3 font-semibold w-40">Type</th>
                          <th className="pb-3 font-semibold w-24">Severity</th>
                          <th className="pb-3 font-semibold">Incident / Flag Description</th>
                          <th className="pb-3 font-semibold text-center w-24">Status</th>
                          <th className="pb-3 font-semibold text-right w-36">Timestamp</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#0f2244]/50">
                        {flags.map((flag) => (
                          <tr key={flag.flag_id} className="hover:bg-[#0c1930]/25 transition-all">
                            <td className="py-4 font-mono text-[10px] text-slate-400 font-semibold select-all">#{flag.flag_id.slice(0, 8)}...</td>
                            <td className="py-4 font-mono text-[10px] text-slate-400 font-semibold">{flag.customer_id.slice(0, 8)}...</td>
                            <td className="py-4">
                              <span className="font-mono text-[10px] text-slate-300 font-semibold bg-[#0a1528] px-1.5 py-0.5 rounded border border-[#0f203d] uppercase">
                                {flag.flag_type.replace('_', ' ')}
                              </span>
                            </td>
                            <td className="py-4">
                              <span className={clsx(
                                "px-1.5 py-0.5 rounded text-[9px] font-bold border uppercase tracking-wider",
                                getSeverityBadgeClass(flag.severity)
                              )}>
                                {flag.severity}
                              </span>
                            </td>
                            <td className="py-4 text-slate-400 leading-relaxed max-w-sm">{flag.description}</td>
                            <td className="py-4 text-center">
                              <span className={clsx(
                                "px-1.5 py-0.5 rounded-full text-[9px] font-semibold inline-flex items-center gap-1",
                                flag.resolved
                                  ? "bg-emerald-500/8 text-emerald-400 border border-emerald-500/20"
                                  : "bg-red-500/8 text-red-400 border border-red-500/20"
                              )}>
                                <span className={clsx("w-1 h-1 rounded-full", flag.resolved ? "bg-emerald-400" : "bg-red-500")} />
                                {flag.resolved ? 'Resolved' : 'Active'}
                              </span>
                            </td>
                            <td className="py-4 text-right font-mono text-[10px] text-slate-500">
                              {formatDateTime(flag.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination Controls */}
                  <div className="flex items-center justify-between border-t border-[#0f2244] mt-5 pt-4">
                    <span className="text-[10px] text-slate-500">
                      Showing page <span className="font-semibold text-slate-300">{page}</span> of <span className="font-semibold text-slate-300">{totalPages}</span> ({totalFlagsCount} items)
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="p-1.5 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-all"
                      >
                        <ChevronLeft size={14} />
                      </button>
                      <button
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages}
                        className="p-1.5 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-all"
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
