// src/pages/AdminPage.tsx
import React, { useEffect, useState } from 'react';
import { adminApi } from '../api/adminApi';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { BankingHeader } from '../components/Layout/BankingHeader';
import { Link } from 'react-router-dom';
import { Terminal, Shield, Cpu, Users, Settings2, ShieldCheck, Filter, Key, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import type { AdminUserRow, RoleInfo, PermissionInfo } from '../types/api';
import { formatDateTime } from '../utils/formatters';
import { clsx } from 'clsx';

export function AdminPage() {
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [permissions, setPermissions] = useState<PermissionInfo[]>([]);
  
  // UI & Loading States
  const [activeTab, setActiveTab] = useState<'users' | 'roles' | 'permissions'>('users');
  const [loading, setLoading] = useState(true);
  const [apiFailed, setApiFailed] = useState(false);

  // Pagination & Filters (Users table)
  const [page, setPage] = useState(1);
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const pageSize = 15;

  const fetchAdminData = async () => {
    setLoading(true);
    setApiFailed(false);
    try {
      if (activeTab === 'users') {
        const data = await adminApi.getUsers(page, pageSize, roleFilter || undefined, statusFilter || undefined);
        setUsers(data);
      } else if (activeTab === 'roles') {
        const fetchedRoles = await adminApi.getRoles();
        setRoles(fetchedRoles);
      } else if (activeTab === 'permissions') {
        const fetchedPerms = await adminApi.getPermissions();
        setPermissions(fetchedPerms);
      }
    } catch (err) {
      console.error('Failed to fetch admin dashboard telemetry:', err);
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, [activeTab, page, roleFilter, statusFilter]);

  const getRoleBadgeClass = (role: string) => {
    switch (role.toLowerCase()) {
      case 'admin':      return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'compliance': return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'manager':    return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
      default:           return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    }
  };

  const getStatusBadgeClass = (status: string) => {
    return status.toLowerCase() === 'active'
      ? 'bg-emerald-500/8 text-emerald-400 border border-emerald-500/20'
      : 'bg-slate-500/8 text-slate-400 border border-slate-500/20';
  };

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="Headquarters Admin Console"
        subtitle="Manage users, security authorization, and monitor active background tasks"
        onRefresh={fetchAdminData}
        isRefreshing={loading}
      />
      <div className="flex-1 p-6 space-y-8 overflow-y-auto max-w-[1600px] mx-auto w-full font-sans">
        
        {/* Developer / Dev Ops Utilities Section (Admin only link cards) */}
        <div className="bg-[#070d19]/60 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-2">
            <Cpu size={14} className="text-[#0066CC]" />
            Developer Monitor Tools
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link to="/dev" className="flex items-center gap-3.5 p-4 rounded-xl bg-[#03060c] border border-[#0f203d] hover:border-[#0066CC]/40 hover:bg-[#03060c]/85 transition-all group">
              <div className="w-10 h-10 rounded-lg bg-[#0066CC]/10 flex items-center justify-center text-[#4d9fff] border border-[#0066CC]/20">
                <Cpu size={18} />
              </div>
              <div>
                <h3 className="text-xs font-bold text-slate-200 group-hover:text-white transition-colors">Agent Dashboard</h3>
                <p className="text-[10px] text-slate-500 mt-0.5">Pipeline status & trace logs</p>
              </div>
            </Link>
            <Link to="/dev/query" className="flex items-center gap-3.5 p-4 rounded-xl bg-[#03060c] border border-[#0f203d] hover:border-[#0066CC]/40 hover:bg-[#03060c]/85 transition-all group">
              <div className="w-10 h-10 rounded-lg bg-[#0066CC]/10 flex items-center justify-center text-[#4d9fff] border border-[#0066CC]/20">
                <Terminal size={18} />
              </div>
              <div>
                <h3 className="text-xs font-bold text-slate-200 group-hover:text-white transition-colors">Query Tester</h3>
                <p className="text-[10px] text-slate-500 mt-0.5">Raw NL-to-SQL endpoint testing</p>
              </div>
            </Link>
            <Link to="/dev/debug" className="flex items-center gap-3.5 p-4 rounded-xl bg-[#03060c] border border-[#0f203d] hover:border-[#0066CC]/40 hover:bg-[#03060c]/85 transition-all group">
              <div className="w-10 h-10 rounded-lg bg-[#0066CC]/10 flex items-center justify-center text-[#4d9fff] border border-[#0066CC]/20">
                <Shield size={18} />
              </div>
              <div>
                <h3 className="text-xs font-bold text-slate-200 group-hover:text-white transition-colors">Security Audit</h3>
                <p className="text-[10px] text-slate-500 mt-0.5">Detailed system traces & flags</p>
              </div>
            </Link>
          </div>
        </div>

        {/* Administration Section Tabs */}
        <div className="flex border-b border-[#0f2244] gap-6 text-sm">
          <button
            onClick={() => { setActiveTab('users'); setPage(1); }}
            className={clsx(
              "pb-3 font-semibold transition-colors relative",
              activeTab === 'users' ? "text-[#4d9fff]" : "text-slate-500 hover:text-slate-350"
            )}
          >
            <span className="flex items-center gap-2">
              <Users size={15} />
              User Directory
            </span>
            {activeTab === 'users' && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#0066CC]" />}
          </button>

          <button
            onClick={() => setActiveTab('roles')}
            className={clsx(
              "pb-3 font-semibold transition-colors relative",
              activeTab === 'roles' ? "text-[#4d9fff]" : "text-slate-500 hover:text-slate-350"
            )}
          >
            <span className="flex items-center gap-2">
              <Settings2 size={15} />
              RBAC Role Matrix
            </span>
            {activeTab === 'roles' && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#0066CC]" />}
          </button>

          <button
            onClick={() => setActiveTab('permissions')}
            className={clsx(
              "pb-3 font-semibold transition-colors relative",
              activeTab === 'permissions' ? "text-[#4d9fff]" : "text-slate-500 hover:text-slate-350"
            )}
          >
            <span className="flex items-center gap-2">
              <ShieldCheck size={15} />
              System Permissions Registry
            </span>
            {activeTab === 'permissions' && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#0066CC]" />}
          </button>
        </div>

        {/* ERROR / UNAVAILABLE STATE */}
        {apiFailed ? (
          <div className="space-y-6">
            <ServiceUnavailable
              serviceName="HQ Admin Management Portal"
              missingEndpoint={`GET /admin/${activeTab}`}
              method="GET"
            />
            <div className="flex justify-center">
              <button
                onClick={() => fetchAdminData()}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#0066CC] hover:bg-[#0052a3] text-white text-sm font-semibold shadow-lg shadow-[#0066CC]/20 hover:shadow-[#0066CC]/35 transition-all duration-200"
              >
                <RefreshCw size={16} className={clsx(loading && "animate-spin")} />
                Retry Connection
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* USERS DIRECTORY TAB */}
            {activeTab === 'users' && (
              <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                  <div>
                    <h3 className="text-sm font-bold text-white">Institutional User Profiles</h3>
                    <p className="text-[10px] text-slate-500 mt-0.5">List and filter active user sessions, authority levels and access status</p>
                  </div>

                  <div className="flex items-center gap-3">
                    <Filter size={12} className="text-slate-650" />
                    <select
                      value={roleFilter}
                      onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}
                      className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2.5 py-1 text-xs text-slate-300 outline-none focus:border-[#0066CC]/50"
                    >
                      <option value="">All Roles</option>
                      <option value="analyst">Analyst</option>
                      <option value="manager">Manager</option>
                      <option value="compliance">Compliance</option>
                      <option value="admin">Admin</option>
                    </select>

                    <select
                      value={statusFilter}
                      onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                      className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2.5 py-1 text-xs text-slate-300 outline-none focus:border-[#0066CC]/50"
                    >
                      <option value="">All Statuses</option>
                      <option value="active">Active</option>
                      <option value="suspended">Suspended</option>
                    </select>
                  </div>
                </div>

                {loading && users.length === 0 ? (
                  <div className="space-y-2 py-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="h-10 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />
                    ))}
                  </div>
                ) : users.length === 0 ? (
                  <div className="text-center py-12 border border-dashed border-[#0f203d] rounded-xl text-slate-500 text-xs">
                    No operator profiles match the filter parameters.
                  </div>
                ) : (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="border-b border-[#0f2244] text-slate-500">
                            <th className="pb-3 font-semibold w-24">User ID</th>
                            <th className="pb-3 font-semibold w-48">Name</th>
                            <th className="pb-3 font-semibold w-48">Email Scope</th>
                            <th className="pb-3 font-semibold w-24">RBAC Role</th>
                            <th className="pb-3 font-semibold w-24">Bank ID</th>
                            <th className="pb-3 font-semibold text-center w-24">Status</th>
                            <th className="pb-3 font-semibold text-right w-36">Created Date</th>
                            <th className="pb-3 font-semibold text-right w-36">Last Login</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#0f2244]/50">
                          {users.map((usr) => (
                            <tr key={usr.user_id} className="hover:bg-[#0c1930]/25 transition-all">
                              <td className="py-4 font-mono text-[10px] text-slate-400 font-semibold select-all">#{usr.user_id}</td>
                              <td className="py-4 font-semibold text-slate-200">{usr.name ?? usr.user_id.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}</td>
                              <td className="py-4 font-mono text-[10px] text-slate-400">{usr.email}</td>
                              <td className="py-4">
                                <span className={clsx("px-1.5 py-0.5 rounded border text-[9px] font-semibold uppercase tracking-wider capitalize", getRoleBadgeClass(usr.role))}>
                                  {usr.role}
                                </span>
                              </td>
                              <td className="py-4 font-mono text-[10px] text-slate-400 uppercase">{usr.bank_id}</td>
                              <td className="py-4 text-center">
                                <span className={clsx("px-1.5 py-0.5 rounded-full text-[9px] font-semibold capitalize inline-flex items-center gap-1", getStatusBadgeClass(usr.status))}>
                                  <span className={clsx("w-1.5 h-1.5 rounded-full", usr.status === 'active' ? 'bg-emerald-400' : 'bg-slate-500')} />
                                  {usr.status}
                                </span>
                              </td>
                              <td className="py-4 text-right font-mono text-[10px] text-slate-500">
                                {usr.created_at ? formatDateTime(usr.created_at) : 'HQ Default System'}
                              </td>
                              <td className="py-4 text-right font-mono text-[10px] text-slate-500">
                                {usr.last_login ? formatDateTime(usr.last_login) : 'Never logged'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Simple prev/next paging fallback since /admin/users returns List */}
                    <div className="flex items-center justify-between border-t border-[#0f2244] mt-5 pt-4">
                      <span className="text-[10px] text-slate-500">
                        Page <span className="font-semibold text-slate-300">{page}</span>
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
                          onClick={() => setPage((p) => p + 1)}
                          disabled={users.length < pageSize}
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

            {/* ROLE MATRIX TAB */}
            {activeTab === 'roles' && (
              <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
                <div className="mb-6">
                  <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                    <ShieldCheck size={16} className="text-[#0066CC]" />
                    Role-Based Access Matrix (RBAC)
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Displays global system roles, users mapped, and their compiled permission tokens</p>
                </div>

                {loading && roles.length === 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="h-32 bg-[#03060c] border border-[#0f203d]/30 rounded-xl animate-pulse" />
                    ))}
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    {roles.map((rInfo) => (
                      <div key={rInfo.role} className="rounded-xl border border-[#0f2040] bg-[#050b14]/50 p-5 space-y-4">
                        <div className="flex items-center justify-between">
                          <span className={clsx("px-2 py-0.5 rounded border text-xs font-semibold uppercase tracking-wider capitalize", getRoleBadgeClass(rInfo.role))}>
                            {rInfo.role}
                          </span>
                          <span className="text-[10px] text-slate-500 font-mono">
                            Users Mapped: <strong className="text-white">{rInfo.user_count}</strong>
                          </span>
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-[9px] uppercase font-bold tracking-wider text-slate-550 flex items-center gap-1.5">
                            <Key size={10} />
                            Authorized Permission Tokens
                          </label>
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {rInfo.permissions.map((perm) => (
                              <span key={perm} className="bg-[#03060c] text-slate-350 px-1.5 py-0.5 rounded border border-[#0f203d] font-mono text-[9px]">
                                {perm}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* PERMISSIONS REGISTRY TAB */}
            {activeTab === 'permissions' && (
              <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
                <div className="mb-6">
                  <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                    <Key size={16} className="text-[#0066CC]" />
                    Permissions Capability Index
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-0.5 font-mono">Exposes system capability tokens mapped to legal system actions and holding roles</p>
                </div>

                {loading && permissions.length === 0 ? (
                  <div className="space-y-2 py-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="h-10 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />
                    ))}
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-[#0f2244] text-slate-500">
                          <th className="pb-3 font-semibold w-64">Permission Token</th>
                          <th className="pb-3 font-semibold w-72">Scope Description</th>
                          <th className="pb-3 font-semibold">Authorized Role Carriers</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#0f2244]/50">
                        {permissions.map((perm) => (
                          <tr key={perm.permission} className="hover:bg-[#0c1930]/25 transition-all">
                            <td className="py-4 font-mono text-[11px] text-amber-500/90 font-bold select-all">{perm.permission}</td>
                            <td className="py-4 text-slate-300 max-w-sm leading-relaxed">{perm.description}</td>
                            <td className="py-4">
                              <div className="flex flex-wrap gap-1.5">
                                {perm.roles.map((carrierRole) => (
                                  <span key={carrierRole} className={clsx(
                                    "px-1.5 py-0.5 rounded border text-[8px] font-bold uppercase tracking-wider capitalize",
                                    getRoleBadgeClass(carrierRole)
                                  )}>
                                    {carrierRole}
                                  </span>
                                ))}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
