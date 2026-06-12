// src/pages/AdminPage.tsx
import React, { useEffect, useState } from 'react';
import { adminApi } from '../api/adminApi';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { BankingHeader } from '../components/Layout/BankingHeader';
import { Link } from 'react-router-dom';
import { Terminal, Shield, Cpu } from 'lucide-react';
import type { AdminUser } from '../types/api';

export function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiFailed, setApiFailed] = useState(false);

  const fetchAdminData = async () => {
    setLoading(true);
    setApiFailed(false);
    try {
      const data = await adminApi.getUsers();
      setUsers(data);
    } catch (err) {
      console.error('Failed to fetch admin users:', err);
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="Headquarters Admin Console"
        subtitle="Manage users, security authorization, and monitor active background tasks"
        onRefresh={fetchAdminData}
        isRefreshing={loading}
      />
      <div className="flex-1 p-6 space-y-8 overflow-y-auto max-w-[1600px] mx-auto w-full">
        {/* Developer / Dev Ops Utilities Section */}
        <div className="bg-[#070d19]/60 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
          <h2 className="text-base font-bold text-white mb-4 flex items-center gap-2">
            <Cpu size={16} className="text-[#3b82f6]" />
            Developer Monitor Tools
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link to="/dev" className="flex items-center gap-3 p-4 rounded-xl bg-[#03060c] border border-[#0f203d] hover:border-[#3b82f6]/40 hover:bg-[#03060c]/80 transition-all group">
              <div className="w-10 h-10 rounded-lg bg-[#3b82f6]/10 flex items-center justify-center text-[#3b82f6]">
                <Cpu size={20} />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-slate-200 group-hover:text-white transition-colors">Agent Dashboard</h3>
                <p className="text-[10px] text-slate-500 mt-0.5">Pipeline status & trace logs</p>
              </div>
            </Link>
            <Link to="/dev/query" className="flex items-center gap-3 p-4 rounded-xl bg-[#03060c] border border-[#0f203d] hover:border-[#3b82f6]/40 hover:bg-[#03060c]/80 transition-all group">
              <div className="w-10 h-10 rounded-lg bg-[#3b82f6]/10 flex items-center justify-center text-[#3b82f6]">
                <Terminal size={20} />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-slate-200 group-hover:text-white transition-colors">Query Tester</h3>
                <p className="text-[10px] text-slate-500 mt-0.5">Raw NL-to-SQL endpoint testing</p>
              </div>
            </Link>
            <Link to="/dev/debug" className="flex items-center gap-3 p-4 rounded-xl bg-[#03060c] border border-[#0f203d] hover:border-[#3b82f6]/40 hover:bg-[#03060c]/80 transition-all group">
              <div className="w-10 h-10 rounded-lg bg-[#3b82f6]/10 flex items-center justify-center text-[#3b82f6]">
                <Shield size={20} />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-slate-200 group-hover:text-white transition-colors">Security Audit</h3>
                <p className="text-[10px] text-slate-500 mt-0.5">Detailed system traces & flags</p>
              </div>
            </Link>
          </div>
        </div>

        {/* User Management Section */}
        {apiFailed ? (
          <ServiceUnavailable
            serviceName="HQ Admin Management Portal"
            missingEndpoint="GET /admin/users"
            method="GET"
            requiredRole="admin"
          />
        ) : loading ? (
          <div className="flex items-center justify-center min-h-[200px]">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#0066CC]"></div>
          </div>
        ) : (
          <div className="text-slate-400 text-sm text-center">
            Managing {users.length} Active System Roles.
          </div>
        )}
      </div>
    </div>
  );
}
