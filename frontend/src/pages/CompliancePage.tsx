// src/pages/CompliancePage.tsx
import React, { useEffect, useState } from 'react';
import { complianceApi } from '../api/complianceApi';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { BankingHeader } from '../components/Layout/BankingHeader';
import { formatDateTime } from '../utils/formatters';
import type { 
  ComplianceOverview, 
  ComplianceRule, 
  ComplianceViolation, 
  AuditLogRow 
} from '../types/api';
import {
  Scale,
  ShieldCheck,
  AlertTriangle,
  History,
  ShieldAlert,
  Search,
  ChevronLeft,
  ChevronRight,
  Filter,
  CheckCircle2,
  Lock,
  Terminal,
  RefreshCw
} from 'lucide-react';
import { clsx } from 'clsx';

export function CompliancePage() {
  const [overview, setOverview] = useState<ComplianceOverview | null>(null);
  const [rules, setRules] = useState<ComplianceRule[]>([]);
  const [violations, setViolations] = useState<ComplianceViolation[]>([]);
  const [violationsCount, setViolationsCount] = useState(0);
  const [auditLogs, setAuditLogs] = useState<AuditLogRow[]>([]);
  const [auditCount, setAuditCount] = useState(0);
  
  // UI / Fetch States
  const [activeTab, setActiveTab] = useState<'rules' | 'violations' | 'audit'>('rules');
  const [loading, setLoading] = useState(true);
  const [apiFailed, setApiFailed] = useState(false);

  // Filters & Paginations
  const [ruleRegulation, setRuleRegulation] = useState<string>('');
  
  const [violationPage, setViolationPage] = useState(1);
  const [violationRegulation, setViolationRegulation] = useState<string>('');
  const [violationSeverity, setViolationSeverity] = useState<string>('');
  const violationPageSize = 10;

  const [auditPage, setAuditPage] = useState(1);
  const [auditUserQuery, setAuditUserQuery] = useState<string>('');
  const [auditActionQuery, setAuditActionQuery] = useState<string>('');
  const auditPageSize = 15;

  const fetchComplianceData = async () => {
    setLoading(true);
    setApiFailed(false);
    try {
      // 1. Always load Overview
      const fetchedOverview = await complianceApi.getOverview();
      setOverview(fetchedOverview);

      // 2. Load tab-specific data in parallel
      if (activeTab === 'rules') {
        const fetchedRules = await complianceApi.getRules(ruleRegulation || undefined, false);
        setRules(fetchedRules);
      } else if (activeTab === 'violations') {
        const paginatedViolations = await complianceApi.getViolations(
          violationPage, 
          violationPageSize, 
          violationRegulation || undefined, 
          violationSeverity || undefined
        );
        setViolations(paginatedViolations.items);
        setViolationsCount(paginatedViolations.total);
      } else if (activeTab === 'audit') {
        const paginatedAudit = await complianceApi.getAuditLogs(
          auditPage, 
          auditPageSize, 
          auditUserQuery || undefined, 
          auditActionQuery || undefined
        );
        setAuditLogs(paginatedAudit.items);
        setAuditCount(paginatedAudit.total);
      }
    } catch (err) {
      console.error('Failed to query Compliance APIs:', err);
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchComplianceData();
  }, [
    activeTab, 
    ruleRegulation, 
    violationPage, 
    violationRegulation, 
    violationSeverity, 
    auditPage
  ]);

  // Handle queries search triggering
  const triggerAuditSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setAuditPage(1);
    fetchComplianceData();
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'compliant': 
      case 'success':
        return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
      case 'warning':
      case 'open':
        return 'bg-amber-500/10 text-amber-400 border border-amber-500/20';
      case 'rejected':
      case 'error':
      case 'failure':
        return 'bg-red-500/10 text-red-400 border border-red-500/20';
      default:
        return 'bg-slate-500/10 text-slate-400 border border-slate-500/20';
    }
  };

  const totalViolationPages = Math.ceil(violationsCount / violationPageSize) || 1;
  const totalAuditPages = Math.ceil(auditCount / auditPageSize) || 1;

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="Regulatory Compliance Control"
        subtitle="GDPR PII tracking, AML monitoring flags, and compliance rule assertions"
        onRefresh={fetchComplianceData}
        isRefreshing={loading}
      />
      
      <div className="flex-1 p-6 space-y-8 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {apiFailed ? (
          <div className="space-y-6">
            <ServiceUnavailable
              serviceName="GDPR & AML Compliance Agent"
              missingEndpoint="GET /compliance/overview"
              method="GET"
            />
            <div className="flex justify-center">
              <button
                onClick={() => fetchComplianceData()}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#0066CC] hover:bg-[#0052a3] text-white text-sm font-semibold shadow-lg shadow-[#0066CC]/20 hover:shadow-[#0066CC]/35 transition-all duration-200"
              >
                <RefreshCw size={16} className={clsx(loading && "animate-spin")} />
                Retry Connection
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Overview Indicators Bar */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
              {loading && !overview ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 h-24 animate-pulse" />
                ))
              ) : overview ? (
                <>
                  {/* GDPR Status */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500 font-mono">GDPR Status</p>
                      <p className="text-xl font-bold text-white mt-1 capitalize">{overview.gdpr_status}</p>
                    </div>
                    <div className={clsx("w-9 h-9 rounded-lg flex items-center justify-center border", 
                      overview.gdpr_status === 'compliant' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400'
                    )}>
                      <Lock size={16} />
                    </div>
                  </div>

                  {/* AML Alerts */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500 font-mono">AML Alerts</p>
                      <p className="text-xl font-bold text-slate-200 mt-1">
                        {overview.aml_alerts_count}
                        <span className="text-[10px] text-slate-500 font-normal ml-1.5 font-mono">Unresolved</span>
                      </p>
                    </div>
                    <div className="w-9 h-9 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400">
                      <ShieldAlert size={16} />
                    </div>
                  </div>

                  {/* KYC Compliance */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500 font-mono">KYC Audit Index</p>
                      <p className="text-xl font-bold text-slate-200 mt-1 capitalize">{overview.kyc_status}</p>
                    </div>
                    <div className={clsx("w-9 h-9 rounded-lg flex items-center justify-center border",
                      overview.kyc_status === 'compliant' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                    )}>
                      <ShieldCheck size={16} />
                    </div>
                  </div>

                  {/* Active Violations */}
                  <div className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-4 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500 font-mono">Open Violations</p>
                      <p className="text-xl font-bold text-slate-200 mt-1">
                        {overview.active_violations_count}
                        <span className="text-[10px] text-slate-500 font-normal ml-1.5 font-mono">/ {overview.total_rules} rules</span>
                      </p>
                    </div>
                    <div className="w-9 h-9 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400">
                      <AlertTriangle size={16} />
                    </div>
                  </div>
                </>
              ) : null}
            </div>

            {/* TAB Navigation */}
            <div className="flex border-b border-[#0f2244] gap-6 text-sm">
              <button
                onClick={() => { setActiveTab('rules'); }}
                className={clsx(
                  "pb-3 font-semibold transition-colors relative",
                  activeTab === 'rules' ? "text-[#4d9fff]" : "text-slate-500 hover:text-slate-350"
                )}
              >
                <span className="flex items-center gap-2">
                  <Scale size={15} />
                  Active Compliance Rules ({overview ? overview.total_rules : 0})
                </span>
                {activeTab === 'rules' && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#0066CC]" />}
              </button>

              <button
                onClick={() => { setActiveTab('violations'); setViolationPage(1); }}
                className={clsx(
                  "pb-3 font-semibold transition-colors relative",
                  activeTab === 'violations' ? "text-[#4d9fff]" : "text-slate-500 hover:text-slate-350"
                )}
              >
                <span className="flex items-center gap-2">
                  <AlertTriangle size={15} />
                  Violations Register ({overview ? overview.active_violations_count : 0})
                </span>
                {activeTab === 'violations' && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#0066CC]" />}
              </button>

              <button
                onClick={() => { setActiveTab('audit'); setAuditPage(1); }}
                className={clsx(
                  "pb-3 font-semibold transition-colors relative",
                  activeTab === 'audit' ? "text-[#4d9fff]" : "text-slate-500 hover:text-slate-350"
                )}
              >
                <span className="flex items-center gap-2">
                  <History size={15} />
                  Immutable Audit Trail
                </span>
                {activeTab === 'audit' && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#0066CC]" />}
              </button>
            </div>

            {/* TAB CONTENTS */}
            {activeTab === 'rules' && (
              <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
                <div className="flex items-center justify-between mb-5">
                  <div>
                    <h3 className="text-sm font-bold text-white">System Compliance Rule Assertions</h3>
                    <p className="text-[10px] text-slate-500 mt-0.5 font-mono">Immutable logic triggers verifying GDPR, AML and KYC compliance</p>
                  </div>
                  
                  {/* Regulation selector */}
                  <select
                    value={ruleRegulation}
                    onChange={(e) => setRuleRegulation(e.target.value)}
                    className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2.5 py-1 text-xs text-slate-300 outline-none focus:border-[#0066CC]/50"
                  >
                    <option value="">All Regulations</option>
                    <option value="AML">AML (Anti-Money Laundering)</option>
                    <option value="KYC">KYC (Know Your Customer)</option>
                    <option value="GDPR">GDPR Data Privacy</option>
                    <option value="PCI-DSS">PCI-DSS Security</option>
                    <option value="SOX">SOX Corporate Audit</option>
                  </select>
                </div>

                {loading && rules.length === 0 ? (
                  <div className="space-y-2 py-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="h-10 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />
                    ))}
                  </div>
                ) : rules.length === 0 ? (
                  <div className="text-center py-12 text-slate-500 text-xs">
                    No rules matching this regulation category.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-[#0f2244] text-slate-500">
                          <th className="pb-3 font-semibold w-24">Rule ID</th>
                          <th className="pb-3 font-semibold w-40">Rule Name</th>
                          <th className="pb-3 font-semibold w-24">Regulation</th>
                          <th className="pb-3 font-semibold w-32">Rule Type</th>
                          <th className="pb-3 font-semibold">Assertion Condition</th>
                          <th className="pb-3 font-semibold">Action Trigger</th>
                          <th className="pb-3 font-semibold text-center w-24">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#0f2244]/50">
                        {rules.map((rule) => (
                          <tr key={rule.rule_id} className="hover:bg-[#0c1930]/25 transition-all">
                            <td className="py-4 font-mono text-[10px] text-slate-400 font-semibold select-all">#{rule.rule_id.slice(0, 8)}...</td>
                            <td className="py-4 font-bold text-slate-200">{rule.rule_name}</td>
                            <td className="py-4">
                              <span className="bg-[#0a1528] text-[#4d9fff] px-1.5 py-0.5 rounded border border-[#0f203d] font-semibold text-[9px] uppercase tracking-wider font-mono">
                                {rule.regulation}
                              </span>
                            </td>
                            <td className="py-4 text-slate-400 font-mono text-[10px]">{rule.rule_type}</td>
                            <td className="py-4 font-mono text-[10px] text-amber-500/80 bg-amber-500/[0.01] px-2 rounded border border-[#0f203d]/20 max-w-xs truncate">{rule.condition}</td>
                            <td className="py-4 text-slate-400">{rule.action}</td>
                            <td className="py-4 text-center">
                              <span className={clsx(
                                "px-2 py-0.5 rounded text-[9px] font-semibold",
                                rule.enabled ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
                              )}>
                                {rule.enabled ? 'Enabled' : 'Disabled'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'violations' && (
              <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                  <div>
                    <h3 className="text-sm font-bold text-white">Active Regulatory Violation Register</h3>
                    <p className="text-[10px] text-slate-500 mt-0.5">Track, audit, and provide resolution updates to active policy discrepancies</p>
                  </div>

                  <div className="flex items-center gap-3">
                    <select
                      value={violationRegulation}
                      onChange={(e) => { setViolationRegulation(e.target.value); setViolationPage(1); }}
                      className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2.5 py-1 text-xs text-slate-300 outline-none focus:border-[#0066CC]/50"
                    >
                      <option value="">All Regulations</option>
                      <option value="AML">AML</option>
                      <option value="KYC">KYC</option>
                      <option value="GDPR">GDPR</option>
                    </select>

                    <select
                      value={violationSeverity}
                      onChange={(e) => { setViolationSeverity(e.target.value); setViolationPage(1); }}
                      className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2.5 py-1 text-xs text-slate-300 outline-none focus:border-[#0066CC]/50"
                    >
                      <option value="">All Severities</option>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                </div>

                {loading && violations.length === 0 ? (
                  <div className="space-y-2 py-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="h-10 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />
                    ))}
                  </div>
                ) : violations.length === 0 ? (
                  <div className="text-center py-12 border border-dashed border-[#0f203d] rounded-xl text-slate-500 text-xs flex flex-col items-center justify-center gap-2">
                    <CheckCircle2 size={24} className="text-emerald-500" />
                    <span>No unresolved regulatory violations found.</span>
                  </div>
                ) : (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="border-b border-[#0f2244] text-slate-500">
                            <th className="pb-3 font-semibold w-24">Violation ID</th>
                            <th className="pb-3 font-semibold w-24">Regulation</th>
                            <th className="pb-3 font-semibold w-36">Type</th>
                            <th className="pb-3 font-semibold w-24">Severity</th>
                            <th className="pb-3 font-semibold">Incident Details</th>
                            <th className="pb-3 font-semibold w-24">Status</th>
                            <th className="pb-3 font-semibold text-right w-36">Detected</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#0f2244]/50">
                          {violations.map((v) => (
                            <tr key={v.violation_id} className="hover:bg-[#0c1930]/25 transition-all">
                              <td className="py-4 font-mono text-[10px] text-slate-400 font-semibold select-all">#{v.violation_id.slice(0, 8)}...</td>
                              <td className="py-4">
                                <span className="bg-[#0a1528] text-amber-400 px-1.5 py-0.5 rounded border border-[#0f203d] font-semibold text-[9px] uppercase tracking-wider font-mono">
                                  {v.regulation}
                                </span>
                              </td>
                              <td className="py-4 font-semibold text-slate-200">{v.violation_type.replace('_', ' ')}</td>
                              <td className="py-4">
                                <span className={clsx(
                                  "px-1.5 py-0.5 rounded text-[9px] font-bold border uppercase tracking-wider",
                                  v.severity.toLowerCase() === 'critical' ? 'bg-red-950/40 text-red-400 border border-red-800/30 font-bold' :
                                  v.severity.toLowerCase() === 'high' ? 'bg-red-500/10 text-red-300 border border-red-500/20' :
                                  v.severity.toLowerCase() === 'medium' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                                  'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                                )}>
                                  {v.severity}
                                </span>
                              </td>
                              <td className="py-4 text-slate-400 max-w-sm leading-relaxed">{v.description}</td>
                              <td className="py-4">
                                <span className={clsx("px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider", getStatusBadge(v.status))}>
                                  {v.status}
                                </span>
                              </td>
                              <td className="py-4 text-right font-mono text-[10px] text-slate-500">
                                {formatDateTime(v.detected_at)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Pagination */}
                    <div className="flex items-center justify-between border-t border-[#0f2244] mt-5 pt-4">
                      <span className="text-[10px] text-slate-500">
                        Showing page <span className="font-semibold text-slate-300">{violationPage}</span> of <span className="font-semibold text-slate-300">{totalViolationPages}</span> ({violationsCount} items)
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setViolationPage((p) => Math.max(1, p - 1))}
                          disabled={violationPage === 1}
                          className="p-1.5 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-all"
                        >
                          <ChevronLeft size={14} />
                        </button>
                        <button
                          onClick={() => setViolationPage((p) => Math.min(totalViolationPages, p + 1))}
                          disabled={violationPage === totalViolationPages}
                          className="p-1.5 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-all"
                        >
                          <ChevronRight size={14} />
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {activeTab === 'audit' && (
              <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
                <div className="mb-6">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Terminal size={16} className="text-[#0066CC]" />
                    Immutable Access & Audit Database
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Search logs representing database reads, query executions, and regulatory assertions</p>
                </div>

                {/* Audit Search Form */}
                <form onSubmit={triggerAuditSearch} className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
                  <div>
                    <input
                      type="text"
                      value={auditUserQuery}
                      onChange={(e) => setAuditUserQuery(e.target.value)}
                      placeholder="Operator User ID (e.g. analyst_001)..."
                      className="w-full px-3 py-1.5 bg-[#03060c] border border-[#0f203d] rounded-lg text-xs text-white placeholder-slate-650 outline-none focus:border-[#0066CC]/50"
                    />
                  </div>
                  <div>
                    <input
                      type="text"
                      value={auditActionQuery}
                      onChange={(e) => setAuditActionQuery(e.target.value)}
                      placeholder="Action executed (e.g. query_database)..."
                      className="w-full px-3 py-1.5 bg-[#03060c] border border-[#0f203d] rounded-lg text-xs text-white placeholder-slate-650 outline-none focus:border-[#0066CC]/50"
                    />
                  </div>
                  <button
                    type="submit"
                    className="flex items-center justify-center gap-1.5 px-4 py-1.5 bg-[#0066CC] hover:bg-[#0052a3] text-white text-xs font-semibold rounded-lg shadow-md transition-all"
                  >
                    <Search size={14} />
                    Search Audit Logs
                  </button>
                </form>

                {loading && auditLogs.length === 0 ? (
                  <div className="space-y-2 py-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="h-10 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />
                    ))}
                  </div>
                ) : auditLogs.length === 0 ? (
                  <div className="text-center py-12 border border-dashed border-[#0f203d] rounded-xl text-slate-500 text-xs">
                    No matching security logs found in the audit DB.
                  </div>
                ) : (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="border-b border-[#0f2244] text-slate-500">
                            <th className="pb-3 font-semibold w-24">Trace ID</th>
                            <th className="pb-3 font-semibold w-36">Operator</th>
                            <th className="pb-3 font-semibold w-24">Role</th>
                            <th className="pb-3 font-semibold w-40">Action</th>
                            <th className="pb-3 font-semibold w-24 text-center">Status</th>
                            <th className="pb-3 font-semibold text-right w-24">Duration</th>
                            <th className="pb-3 font-semibold text-right w-36">IP Address</th>
                            <th className="pb-3 font-semibold text-right w-36">Timestamp</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#0f2244]/50">
                          {auditLogs.map((log) => (
                            <tr key={log.id} className="hover:bg-[#0c1930]/25 transition-all">
                              <td className="py-3.5 font-mono text-[10px] text-slate-400 font-semibold select-all">#{log.audit_id.slice(0, 8)}...</td>
                              <td className="py-3.5 font-semibold text-slate-200">{log.user_id}</td>
                              <td className="py-3.5 capitalize font-mono text-[10px] text-slate-400">{log.user_role}</td>
                              <td className="py-3.5">
                                <div className="flex flex-col">
                                  <span className="font-mono text-[10px] text-slate-350">{log.action}</span>
                                  {log.endpoint && <span className="text-[8px] text-slate-600 font-mono mt-0.5">{log.http_method} {log.endpoint}</span>}
                                </div>
                              </td>
                              <td className="py-3.5 text-center">
                                <span className={clsx("px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider", getStatusBadge(log.status))}>
                                  {log.status}
                                </span>
                              </td>
                              <td className="py-3.5 text-right font-mono text-[10px] text-slate-400">{log.execution_time_ms}ms</td>
                              <td className="py-3.5 text-right font-mono text-[10px] text-slate-500">{log.ip_address ?? '127.0.0.1'}</td>
                              <td className="py-3.5 text-right font-mono text-[10px] text-slate-500">
                                {formatDateTime(log.timestamp)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Pagination */}
                    <div className="flex items-center justify-between border-t border-[#0f2244] mt-5 pt-4">
                      <span className="text-[10px] text-slate-500">
                        Showing page <span className="font-semibold text-slate-300">{auditPage}</span> of <span className="font-semibold text-slate-300">{totalAuditPages}</span> ({auditCount} items)
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setAuditPage((p) => Math.max(1, p - 1))}
                          disabled={auditPage === 1}
                          className="p-1.5 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-all"
                        >
                          <ChevronLeft size={14} />
                        </button>
                        <button
                          onClick={() => setAuditPage((p) => Math.min(totalAuditPages, p + 1))}
                          disabled={auditPage === totalAuditPages}
                          className="p-1.5 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-all"
                        >
                          <ChevronRight size={14} />
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
