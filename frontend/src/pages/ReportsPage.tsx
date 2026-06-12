// src/pages/ReportsPage.tsx
import React, { useEffect, useState } from 'react';
import { reportsApi, GenerateReportRequest } from '../api/reportsApi';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { BankingHeader } from '../components/Layout/BankingHeader';
import { formatDateTime } from '../utils/formatters';
import type { Report } from '../types/api';
import {
  FileText,
  Plus,
  Filter,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Calendar,
  AlertCircle,
  CheckCircle2,
  X
} from 'lucide-react';
import { clsx } from 'clsx';

export function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [apiFailed, setApiFailed] = useState(false);
  
  // Filtering & Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [regFilter, setRegFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Form State
  const [reportType, setReportType] = useState('aml_summary');
  const [regulation, setRegulation] = useState('AML');
  const [periodStart, setPeriodStart] = useState('');
  const [periodEnd, setPeriodEnd] = useState('');
  
  // Feedback States
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);

  const fetchReports = async () => {
    setLoading(true);
    setApiFailed(false);
    try {
      const paginated = await reportsApi.getReports(
        page,
        pageSize,
        regFilter || undefined,
        statusFilter || undefined
      );
      setReports(paginated.items);
      setTotalCount(paginated.total);
    } catch (err) {
      console.error('Failed to fetch generated reports:', err);
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [page, regFilter, statusFilter]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerating(true);
    setFormError(null);
    setFormSuccess(null);

    const payload: GenerateReportRequest = {
      report_type: reportType,
      regulation: regulation,
      period_start: periodStart || undefined,
      period_end: periodEnd || undefined,
    };

    try {
      const response = await reportsApi.generateReport(payload);
      setFormSuccess(response.message || `Report ${response.report_id} generated successfully!`);
      // Reset form period
      setPeriodStart('');
      setPeriodEnd('');
      
      // Delay closing modal and refresh list
      setTimeout(() => {
        setShowGenerateModal(false);
        setFormSuccess(null);
        setPage(1);
        fetchReports();
      }, 1500);
    } catch (err: any) {
      console.error('Report generation failed:', err);
      setFormError(err.response?.data?.detail?.message || 'Report generation failed. Please check inputs.');
    } finally {
      setGenerating(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'approved': 
      case 'submitted':
        return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
      case 'draft':
        return 'bg-amber-500/10 text-amber-400 border border-amber-500/20';
      default:
        return 'bg-slate-500/10 text-slate-400 border border-slate-500/20';
    }
  };

  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="Institutional Financial Reporting"
        subtitle="Generate, schedule, and review automated regulatory reports"
        onRefresh={fetchReports}
        isRefreshing={loading}
      />
      <div className="flex-1 p-6 space-y-8 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {apiFailed ? (
          <div className="space-y-6">
            <ServiceUnavailable
              serviceName="Reporting & Audit Service"
              missingEndpoint="GET /reports"
              method="GET"
            />
            <div className="flex justify-center">
              <button
                onClick={() => fetchReports()}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#0066CC] hover:bg-[#0052a3] text-white text-sm font-semibold shadow-lg shadow-[#0066CC]/20 hover:shadow-[#0066CC]/35 transition-all duration-200"
              >
                <RefreshCw size={16} className={clsx(loading && "animate-spin")} />
                Retry Connection
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Top Toolbar & Registry Summary */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-5 backdrop-blur-md">
              <div>
                <h3 className="text-sm font-bold text-white">Institutional Reports Database</h3>
                <p className="text-[10px] text-slate-500 mt-0.5 font-mono">Governed audit aggregates for AML, KYC, and credit risk compliance audits</p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                {/* Filters */}
                <select
                  value={regFilter}
                  onChange={(e) => { setRegFilter(e.target.value); setPage(1); }}
                  className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2.5 py-1.5 text-xs text-slate-350 outline-none focus:border-[#0066CC]/50"
                >
                  <option value="">All Regulations</option>
                  <option value="AML">AML</option>
                  <option value="KYC">KYC</option>
                  <option value="GDPR">GDPR</option>
                  <option value="PCI-DSS">PCI-DSS</option>
                </select>

                <select
                  value={statusFilter}
                  onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                  className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2.5 py-1.5 text-xs text-slate-350 outline-none focus:border-[#0066CC]/50"
                >
                  <option value="">All Statuses</option>
                  <option value="draft">Draft</option>
                  <option value="submitted">Submitted</option>
                </select>

                {/* Generate Action Button */}
                <button
                  onClick={() => setShowGenerateModal(true)}
                  className="flex items-center gap-1.5 px-4 py-1.5 bg-[#0066CC] hover:bg-[#0052a3] text-white text-xs font-semibold rounded-lg shadow-md transition-all shadow-[#0066CC]/15"
                >
                  <Plus size={14} />
                  Generate Report
                </button>
              </div>
            </div>

            {/* Reports List Table */}
            <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
              {loading && reports.length === 0 ? (
                <div className="space-y-2 py-4">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-10 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />
                  ))}
                </div>
              ) : reports.length === 0 ? (
                <div className="text-center py-16 border border-dashed border-[#0f203d] rounded-xl text-slate-500 text-xs flex flex-col items-center justify-center gap-2">
                  <FileText size={28} className="text-slate-700 mb-1" />
                  <span>No regulatory reports generated yet in this database.</span>
                </div>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-[#0f2244] text-slate-500">
                          <th className="pb-3 font-semibold w-24">Report ID</th>
                          <th className="pb-3 font-semibold w-40">Report Type</th>
                          <th className="pb-3 font-semibold w-24">Regulation</th>
                          <th className="pb-3 font-semibold">Auditing Period</th>
                          <th className="pb-3 font-semibold text-center w-28">Status</th>
                          <th className="pb-3 font-semibold text-right w-44">Generated At</th>
                          <th className="pb-3 font-semibold text-right w-44">Submitted At</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#0f2244]/50">
                        {reports.map((report) => (
                          <tr key={report.report_id} className="hover:bg-[#0c1930]/25 transition-all">
                            <td className="py-4 font-mono text-[10px] text-slate-400 font-semibold select-all">#{report.report_id.slice(0, 8)}...</td>
                            <td className="py-4 font-semibold text-slate-200 uppercase tracking-wider">{report.report_type.replace('_', ' ')}</td>
                            <td className="py-4">
                              <span className="bg-[#0a1528] text-[#4d9fff] px-1.5 py-0.5 rounded border border-[#0f203d] font-semibold text-[9px] uppercase tracking-wider font-mono">
                                {report.regulation}
                              </span>
                            </td>
                            <td className="py-4 text-slate-400 font-mono text-[10px]">
                              {report.report_period_start && report.report_period_end ? (
                                <span className="flex items-center gap-1 text-slate-350">
                                  <Calendar size={11} className="text-slate-650" />
                                  {report.report_period_start} to {report.report_period_end}
                                </span>
                              ) : 'Full Database Scope'}
                            </td>
                            <td className="py-4 text-center">
                              <span className={clsx("px-2 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider", getStatusBadge(report.status))}>
                                {report.status}
                              </span>
                            </td>
                            <td className="py-4 text-right font-mono text-[10px] text-slate-500">
                              {formatDateTime(report.generated_at)}
                            </td>
                            <td className="py-4 text-right font-mono text-[10px] text-slate-500">
                              {report.submitted_at ? formatDateTime(report.submitted_at) : (
                                <span className="text-slate-700 italic">Pending Submission</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination */}
                  <div className="flex items-center justify-between border-t border-[#0f2244] mt-5 pt-4">
                    <span className="text-[10px] text-slate-500">
                      Showing page <span className="font-semibold text-slate-300">{page}</span> of <span className="font-semibold text-slate-300">{totalPages}</span> ({totalCount} items)
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

            {/* GENERATE REPORT MODAL WIZARD */}
            {showGenerateModal && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                <div className="bg-[#08111e] border border-[#0f2244] rounded-2xl p-6 w-full max-w-md shadow-[0_20px_50px_rgba(0,0,0,0.7)] relative animate-fade-in">
                  <button
                    onClick={() => setShowGenerateModal(false)}
                    className="absolute top-4 right-4 text-slate-500 hover:text-white transition-colors"
                  >
                    <X size={18} />
                  </button>

                  <h3 className="text-base font-bold text-white mb-1 flex items-center gap-2">
                    <FileText size={18} className="text-[#0066CC]" />
                    Generate Compliance Audit
                  </h3>
                  <p className="text-[10px] text-slate-500 mb-6 font-mono">Compile database aggregates into legal regulatory reports</p>

                  <form onSubmit={handleGenerate} className="space-y-4 text-xs">
                    {/* Error and Success Feedback */}
                    {formError && (
                      <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg flex items-start gap-2">
                        <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />
                        <span>{formError}</span>
                      </div>
                    )}
                    {formSuccess && (
                      <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg flex items-start gap-2">
                        <CheckCircle2 size={14} className="mt-0.5 flex-shrink-0" />
                        <span>{formSuccess}</span>
                      </div>
                    )}

                    {/* Report Type */}
                    <div className="space-y-1.5">
                      <label className="text-slate-400 font-medium">Reporting Stream</label>
                      <select
                        value={reportType}
                        onChange={(e) => setReportType(e.target.value)}
                        className="w-full bg-[#03060c] border border-[#0f203d] rounded-lg px-3 py-2 text-white outline-none focus:border-[#0066CC]/50"
                      >
                        <option value="aml_summary">AML Transaction Summary</option>
                        <option value="kyc_status">KYC Segment Status</option>
                        <option value="risk_exposure">Segment Credit Risk Exposure</option>
                        <option value="transaction_volume">Transaction Volume Aggregates</option>
                      </select>
                    </div>

                    {/* Target Regulation */}
                    <div className="space-y-1.5">
                      <label className="text-slate-400 font-medium">Compliance Governance Frame</label>
                      <select
                        value={regulation}
                        onChange={(e) => setRegulation(e.target.value)}
                        className="w-full bg-[#03060c] border border-[#0f203d] rounded-lg px-3 py-2 text-white outline-none focus:border-[#0066CC]/50"
                      >
                        <option value="AML">AML (Anti-Money Laundering)</option>
                        <option value="KYC">KYC (Know Your Customer)</option>
                        <option value="GDPR">GDPR Data Privacy</option>
                        <option value="PCI-DSS">PCI-DSS Security</option>
                        <option value="SOX">SOX Corporate Audit</option>
                      </select>
                    </div>

                    {/* Date Period selectors */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1.5">
                        <label className="text-slate-400 font-medium">Period Start</label>
                        <input
                          type="date"
                          value={periodStart}
                          onChange={(e) => setPeriodStart(e.target.value)}
                          className="w-full bg-[#03060c] border border-[#0f203d] rounded-lg px-3 py-2 text-white outline-none focus:border-[#0066CC]/50"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-slate-400 font-medium">Period End</label>
                        <input
                          type="date"
                          value={periodEnd}
                          onChange={(e) => setPeriodEnd(e.target.value)}
                          className="w-full bg-[#03060c] border border-[#0f203d] rounded-lg px-3 py-2 text-white outline-none focus:border-[#0066CC]/50"
                        />
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex justify-end gap-2.5 pt-4">
                      <button
                        type="button"
                        onClick={() => setShowGenerateModal(false)}
                        className="px-4 py-2 bg-[#0d1d33] border border-[#1e3459] text-slate-300 rounded-lg font-semibold hover:text-white"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={generating || !!formSuccess}
                        className="flex items-center gap-1.5 px-5 py-2 bg-[#0066CC] hover:bg-[#0052a3] text-white font-semibold rounded-lg shadow-md disabled:opacity-50"
                      >
                        <RefreshCw size={13} className={clsx(generating && "animate-spin")} />
                        {generating ? 'Compiling Database...' : 'Run Aggregator'}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
