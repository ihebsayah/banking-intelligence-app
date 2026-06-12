// src/pages/ProfilePage.tsx
import React, { useEffect, useState } from 'react';
import { profileApi } from '../api/profileApi';
import { useAuthStore } from '../stores/authStore';
import { BankingHeader } from '../components/Layout/BankingHeader';
import { User, Shield, Key, Landmark, Clock, FileKey } from 'lucide-react';
import type { AdminUser } from '../types/api';

export function ProfilePage() {
  const { user } = useAuthStore();
  const [profile, setProfile] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [usingTokenFallback, setUsingTokenFallback] = useState(false);

  useEffect(() => {
    const fetchProfile = async () => {
      setLoading(true);
      try {
        const data = await profileApi.getProfile();
        setProfile(data);
        setUsingTokenFallback(false);
      } catch (err) {
        console.warn('GET /auth/me not available. Falling back to local JWT payload.', err);
        setUsingTokenFallback(true);
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, []);

  const displayUser = usingTokenFallback ? user : profile;

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="Institutional User Profile"
        subtitle="Review security access level, authorized organizational scope, and system credentials"
        isRefreshing={loading}
      />
      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1000px] mx-auto w-full">
        {usingTokenFallback && (
          <div className="flex items-center gap-2 bg-blue-500/5 border border-blue-500/10 rounded-xl px-4 py-3 text-xs text-slate-400">
            <span>Profile retrieved via offline JWT token validation. endpoint: <code className="text-slate-350 font-mono">GET /auth/me</code> is pending integration.</span>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center min-h-[300px]">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#0066CC]"></div>
          </div>
        ) : displayUser ? (
          <div className="bg-[#070d19]/60 border border-[#0f2244] rounded-2xl p-8 backdrop-blur-md shadow-[0_12px_40px_rgba(0,0,0,0.5)]">
            <div className="flex items-center gap-4 border-b border-[#0f2244] pb-6 mb-6">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#0066CC] to-[#003366] flex items-center justify-center text-xl font-bold text-white shadow-[0_0_16px_rgba(0,102,204,0.3)]">
                {displayUser.name?.charAt(0).toUpperCase() ?? displayUser.user_id.charAt(0).toUpperCase() ?? 'U'}
              </div>
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">{displayUser.name ?? displayUser.user_id}</h2>
                <p className="text-sm text-slate-400 font-mono mt-0.5">{displayUser.email}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Role Card */}
              <div className="flex items-center gap-4 p-4 rounded-xl bg-[#03060c] border border-[#0f203d]">
                <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-400">
                  <Shield size={20} />
                </div>
                <div>
                  <h3 className="text-xs text-slate-500 font-medium">Authorized RBAC Role</h3>
                  <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded border capitalize mt-1 ${
                    displayUser.role === 'admin' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                    displayUser.role === 'compliance' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                    displayUser.role === 'manager' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                    'bg-blue-500/10 text-blue-400 border-blue-500/20'
                  }`}>
                    {displayUser.role}
                  </span>
                </div>
              </div>

              {/* Bank Card */}
              <div className="flex items-center gap-4 p-4 rounded-xl bg-[#03060c] border border-[#0f203d]">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400">
                  <Landmark size={20} />
                </div>
                <div>
                  <h3 className="text-xs text-slate-500 font-medium">Organizational Scope</h3>
                  <p className="text-sm font-semibold text-slate-200 mt-1 uppercase">{displayUser.bank_id}</p>
                </div>
              </div>

              {/* User ID Card */}
              <div className="flex items-center gap-4 p-4 rounded-xl bg-[#03060c] border border-[#0f203d]">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                  <Key size={20} />
                </div>
                <div>
                  <h3 className="text-xs text-slate-500 font-medium">System Identifier</h3>
                  <p className="text-sm font-semibold text-slate-250 mt-1 font-mono">{displayUser.user_id}</p>
                </div>
              </div>

              {/* Login Time Card */}
              <div className="flex items-center gap-4 p-4 rounded-xl bg-[#03060c] border border-[#0f203d]">
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center text-amber-400">
                  <Clock size={20} />
                </div>
                <div>
                  <h3 className="text-xs text-slate-500 font-medium">Last Login Timestamp</h3>
                  <p className="text-xs font-semibold text-slate-300 mt-1 font-mono">
                    {displayUser.last_login ? new Date(displayUser.last_login).toLocaleString() : 'Just now'}
                  </p>
                </div>
              </div>
            </div>

            {/* JWT payload info */}
            <div className="mt-8 pt-6 border-t border-[#0f2244] flex items-center gap-2.5 text-[11px] text-slate-500">
              <FileKey size={14} className="text-[#0066CC]" />
              <span>Token expires automatically based on compliance session lifetime policies. Do not share credentials.</span>
            </div>
          </div>
        ) : (
          <div className="text-center text-slate-500 py-12">Failed to load user session info.</div>
        )}
      </div>
    </div>
  );
}
