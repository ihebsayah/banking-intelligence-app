// src/pages/Branches.tsx
import React, { useEffect, useState } from 'react';
import { useBranchStore } from '../stores/branchStore';
import { branchesApi, MOCK_BRANCHES } from '../api/branches';
import { BranchPerformanceChart, CustomerGrowthChart } from '../components/dashboard/DashboardCharts';
import { BankingHeader } from '../components/Layout/BankingHeader';
import { formatCurrency, formatNumber, formatPercent } from '../utils/formatters';
import {
  Search,
  Building2,
  Users,
  TrendingUp,
  Shield,
  MapPin,
  User,
  Phone,
  ArrowLeftRight,
  Plus,
  X,
  CheckCircle,
  HelpCircle
} from 'lucide-react';

export function Branches() {
  const {
    branches,
    selectedBranchId,
    compareMode,
    compareBranchIds,
    isLoading,
    error,
    setBranches,
    selectBranch,
    toggleCompareMode,
    addCompare,
    removeCompare,
    setLoading,
    setError
  } = useBranchStore();

  const [search, setSearch] = useState('');
  const [isUsingMock, setIsUsingMock] = useState(false);

  const fetchBranches = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await branchesApi.getAll();
      setBranches(data);
      setIsUsingMock(false);
    } catch (err) {
      console.warn('Branches API failed, falling back to mock data.', err);
      setBranches(MOCK_BRANCHES);
      setIsUsingMock(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (branches.length === 0) {
      fetchBranches();
    }
  }, []);

  const filteredBranches = branches.filter((b) =>
    b.name.toLowerCase().includes(search.toLowerCase()) ||
    b.city.toLowerCase().includes(search.toLowerCase()) ||
    b.state.toLowerCase().includes(search.toLowerCase())
  );

  const selectedBranch = branches.find((b) => b.branch_id === selectedBranchId) || branches[0];
  const comparedBranches = branches.filter((b) => compareBranchIds.includes(b.branch_id));

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="HQ Branch Performance & Operations"
        subtitle="Operational metrics, compliance mapping, and side-by-side performance audits"
        onRefresh={fetchBranches}
        isRefreshing={isLoading}
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full flex flex-col lg:flex-row gap-6">
        {/* Left Column: Branch selector/list */}
        <div className="w-full lg:w-[380px] space-y-4 flex-shrink-0">
          <div className="glass-card p-4 space-y-3">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={15} />
              <input
                type="text"
                placeholder="Search branches..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-[#0d1f3c] border border-[#1e3459] rounded-lg pl-9 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0066CC]/60 transition-all"
              />
            </div>

            {/* Compare Toggle */}
            <div className="flex items-center justify-between pt-1">
              <span className="text-xs font-semibold text-slate-300">Compare Branches</span>
              <button
                onClick={toggleCompareMode}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  compareMode
                    ? 'bg-[#0066CC] text-white shadow-[0_0_12px_rgba(0,102,204,0.3)]'
                    : 'bg-[#0a1628] text-slate-400 hover:text-white border border-[#1a2d4e]'
                }`}
              >
                <ArrowLeftRight size={12} />
                {compareMode ? 'Comparison Mode Active' : 'Enable Compare'}
              </button>
            </div>
            {compareMode && (
              <p className="text-[10px] text-slate-500 leading-normal">
                Select up to 3 branches to compare their financial standing and performance.
              </p>
            )}
          </div>

          {/* List items */}
          <div className="space-y-3 max-h-[calc(100vh-270px)] overflow-y-auto pr-1">
            {filteredBranches.map((branch) => {
              const isSelected = selectedBranchId === branch.branch_id;
              const isCompared = compareBranchIds.includes(branch.branch_id);

              return (
                <div
                  key={branch.branch_id}
                  onClick={() => !compareMode && selectBranch(branch.branch_id)}
                  className={`rounded-xl border p-4 transition-all duration-200 ${
                    compareMode
                      ? 'border-[#1a2d4e] bg-[#08111e]'
                      : isSelected
                      ? 'border-[#0066CC] bg-[#0066CC]/8 shadow-[0_0_16px_rgba(0,102,204,0.08)] cursor-pointer'
                      : 'border-[#0f2040] bg-[#08111e] hover:border-[#1e3459] cursor-pointer'
                  }`}
                >
                  <div className="flex justify-between items-start gap-2">
                    <div>
                      <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
                        <Building2 size={12} className="text-blue-400" />
                        {branch.name}
                      </h4>
                      <p className="text-[10px] text-slate-500 mt-0.5 flex items-center gap-1">
                        <MapPin size={9} />
                        {branch.city}, {branch.state}
                      </p>
                    </div>

                    {compareMode ? (
                      isCompared ? (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            removeCompare(branch.branch_id);
                          }}
                          className="p-1 rounded-md bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/15"
                        >
                          <X size={12} />
                        </button>
                      ) : (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            addCompare(branch.branch_id);
                          }}
                          disabled={compareBranchIds.length >= 3}
                          className="flex items-center gap-1 px-2 py-1 rounded-md bg-[#0066CC]/15 text-[#4d9fff] hover:bg-[#0066CC]/30 disabled:opacity-40 disabled:cursor-not-allowed border border-[#0066CC]/20 text-[10px]"
                        >
                          <Plus size={10} /> Add
                        </button>
                      )
                    ) : (
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                        branch.performance_vs_plan >= 100
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : branch.performance_vs_plan >= 95
                          ? 'bg-amber-500/10 text-amber-400'
                          : 'bg-red-500/10 text-red-400'
                      }`}>
                        {branch.performance_vs_plan.toFixed(1)}% plan
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3 mt-4 pt-3 border-t border-white/5 text-[10px]">
                    <div>
                      <span className="text-slate-500 block">Deposits</span>
                      <span className="font-semibold text-slate-300">
                        {formatCurrency(branch.total_deposits, true)}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Customers</span>
                      <span className="font-semibold text-slate-300">
                        {formatNumber(branch.active_customers)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Details or Compare panel */}
        <div className="flex-1 space-y-6">
          {compareMode ? (
            /* Compare Panel */
            comparedBranches.length === 0 ? (
              <div className="glass-card p-12 flex flex-col items-center justify-center text-center gap-3 min-h-[300px]">
                <ArrowLeftRight size={36} className="text-slate-600 animate-pulse" />
                <h3 className="text-sm font-semibold text-slate-300">Select Branches to Compare</h3>
                <p className="text-xs text-slate-500 max-w-sm">
                  Click the "Add" button on the branch cards in the left panel to populate the comparison view.
                </p>
              </div>
            ) : (
              <div className="space-y-6 animate-fade-in">
                {/* Metrics Table */}
                <div className="glass-card p-5 overflow-x-auto">
                  <h3 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                    <ArrowLeftRight size={15} className="text-blue-400" />
                    Comparative Breakdown ({comparedBranches.length}/3)
                  </h3>
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-[#0f2040] text-slate-500">
                        <th className="py-2.5">Metric</th>
                        {comparedBranches.map((b) => (
                          <th key={b.branch_id} className="py-2.5 px-4 font-bold text-white text-center">
                            {b.name}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      <tr>
                        <td className="py-3 font-medium text-slate-400">Location</td>
                        {comparedBranches.map((b) => (
                          <td key={b.branch_id} className="py-3 px-4 text-slate-300 text-center">
                            {b.city}, {b.state}
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td className="py-3 font-medium text-slate-400">Branch Manager</td>
                        {comparedBranches.map((b) => (
                          <td key={b.branch_id} className="py-3 px-4 text-slate-300 text-center">
                            {b.manager_name}
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td className="py-3 font-medium text-slate-400">Total Deposits</td>
                        {comparedBranches.map((b) => (
                          <td key={b.branch_id} className="py-3 px-4 text-white font-semibold text-center">
                            {formatCurrency(b.total_deposits)}
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td className="py-3 font-medium text-slate-400">Annual Revenue</td>
                        {comparedBranches.map((b) => (
                          <td key={b.branch_id} className="py-3 px-4 text-white font-semibold text-center">
                            {formatCurrency(b.total_revenue)}
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td className="py-3 font-medium text-slate-400">Active Customers</td>
                        {comparedBranches.map((b) => (
                          <td key={b.branch_id} className="py-3 px-4 text-slate-300 text-center">
                            {formatNumber(b.active_customers)}
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td className="py-3 font-medium text-slate-400">Customer Growth Rate</td>
                        {comparedBranches.map((b) => (
                          <td key={b.branch_id} className="py-3 px-4 text-center">
                            <span className={b.customer_growth_rate >= 3 ? 'text-emerald-400' : 'text-slate-400'}>
                              {formatPercent(b.customer_growth_rate)}
                            </span>
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td className="py-3 font-medium text-slate-400">Performance vs Plan</td>
                        {comparedBranches.map((b) => (
                          <td key={b.branch_id} className="py-3 px-4 text-center font-bold">
                            <span className={
                              b.performance_vs_plan >= 100
                                ? 'text-emerald-400'
                                : b.performance_vs_plan >= 95
                                ? 'text-amber-400'
                                : 'text-red-400'
                            }>
                              {b.performance_vs_plan.toFixed(1)}%
                            </span>
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td className="py-3 font-medium text-slate-400">Compliance Audit Score</td>
                        {comparedBranches.map((b) => (
                          <td key={b.branch_id} className="py-3 px-4 text-center">
                            <span className={b.compliance_score >= 98 ? 'text-emerald-400' : 'text-slate-400'}>
                              {b.compliance_score.toFixed(1)}%
                            </span>
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td className="py-3 font-medium text-slate-400">Staff Headcount</td>
                        {comparedBranches.map((b) => (
                          <td key={b.branch_id} className="py-3 px-4 text-slate-300 text-center">
                            {b.staff_count} FTE
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Compare charts */}
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                  <div className="glass-card-static">
                    <BranchPerformanceChart branches={comparedBranches} />
                  </div>
                  <div className="glass-card-static">
                    <CustomerGrowthChart branches={comparedBranches} />
                  </div>
                </div>
              </div>
            )
          ) : (
            /* Selected Branch Details */
            selectedBranch && (
              <div className="space-y-6 animate-fade-in">
                {/* Details Header Card */}
                <div className="glass-card p-6 relative overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-r from-blue-600/5 to-transparent pointer-events-none" />
                  <div className="relative flex flex-col md:flex-row justify-between md:items-center gap-4">
                    <div>
                      <h3 className="text-lg font-bold text-white">{selectedBranch.name}</h3>
                      <p className="text-xs text-slate-500 mt-1 flex items-center gap-1.5">
                        <MapPin size={11} className="text-slate-600" />
                        {selectedBranch.address || `${selectedBranch.city}, ${selectedBranch.state}`}
                      </p>
                    </div>
                    <div className="flex gap-4 border-l border-white/5 pl-4 text-xs">
                      <div>
                        <span className="text-slate-500 block text-[10px]">Manager</span>
                        <span className="font-semibold text-slate-300 flex items-center gap-1 mt-0.5">
                          <User size={10} /> {selectedBranch.manager_name}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block text-[10px]">Phone Contact</span>
                        <span className="font-semibold text-slate-300 flex items-center gap-1 mt-0.5">
                          <Phone size={10} /> {selectedBranch.phone}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Metrics Cards */}
                <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
                  {/* Total Deposits */}
                  <div className="glass-card p-4">
                    <span className="text-[10px] text-slate-500 font-medium">Deposits</span>
                    <p className="text-base font-bold text-white mt-1">
                      {formatCurrency(selectedBranch.total_deposits)}
                    </p>
                    <span className="text-[10px] text-emerald-400 flex items-center gap-0.5 mt-1">
                      {formatPercent(selectedBranch.customer_growth_rate)} YoY
                    </span>
                  </div>

                  {/* Revenue */}
                  <div className="glass-card p-4">
                    <span className="text-[10px] text-slate-500 font-medium">Annual Revenue</span>
                    <p className="text-base font-bold text-white mt-1">
                      {formatCurrency(selectedBranch.total_revenue)}
                    </p>
                    <span className="text-[10px] text-slate-500 block mt-1">
                      Ratio: {(selectedBranch.total_revenue / selectedBranch.total_deposits * 100).toFixed(1)}% of deposits
                    </span>
                  </div>

                  {/* Active Customers */}
                  <div className="glass-card p-4">
                    <span className="text-[10px] text-slate-500 font-medium">Active Customers</span>
                    <p className="text-base font-bold text-white mt-1">
                      {formatNumber(selectedBranch.active_customers)}
                    </p>
                    <span className="text-[10px] text-slate-500 block mt-1">
                      Avg: {formatCurrency(selectedBranch.avg_transaction_size, true)} transaction size
                    </span>
                  </div>

                  {/* Compliance Score */}
                  <div className="glass-card p-4">
                    <span className="text-[10px] text-slate-500 font-medium">Compliance Audit</span>
                    <p className="text-base font-bold text-white mt-1">
                      {selectedBranch.compliance_score.toFixed(1)}%
                    </p>
                    <span className="text-[10px] text-emerald-400 flex items-center gap-0.5 mt-1">
                      <CheckCircle size={10} /> Audit Passed
                    </span>
                  </div>
                </div>

                {/* Single Branch Charts */}
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                  <div className="glass-card-static">
                    <BranchPerformanceChart branches={[selectedBranch]} />
                  </div>
                  <div className="glass-card-static">
                    <CustomerGrowthChart branches={[selectedBranch]} />
                  </div>
                </div>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
