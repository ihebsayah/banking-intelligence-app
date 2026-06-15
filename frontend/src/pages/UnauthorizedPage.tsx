// src/pages/UnauthorizedPage.tsx
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ShieldX, ArrowLeft, Lock, ChevronRight } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';

interface LocationState {
  requiredRole?: string | string[];
  from?: string;
}

export function UnauthorizedPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuthStore();
  const state = location.state as LocationState | null;

  const requiredRole = state?.requiredRole;
  const from = state?.from ?? '/dashboard';
  const currentRole = user?.role ?? 'unauthenticated';

  const roleColors: Record<string, string> = {
    admin:      'text-red-400 bg-red-500/10 border-red-500/20',
    compliance: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    manager:    'text-purple-400 bg-purple-500/10 border-purple-500/20',
    analyst:    'text-blue-400 bg-blue-500/10 border-blue-500/20',
    unauthenticated: 'text-slate-400 bg-slate-500/10 border-slate-500/20',
  };

  const requiredRoles = requiredRole
    ? Array.isArray(requiredRole) ? requiredRole : [requiredRole]
    : null;

  return (
    <div className="min-h-screen bg-[#040711] flex items-center justify-center px-6">
      {/* Background grid */}
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.03]"
        style={{
          backgroundImage: 'linear-gradient(#0066CC 1px, transparent 1px), linear-gradient(90deg, #0066CC 1px, transparent 1px)',
          backgroundSize: '60px 60px',
        }}
      />

      {/* Glow */}
      <div className="pointer-events-none fixed top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-red-600/5 rounded-full blur-3xl" />

      <div className="relative z-10 max-w-lg w-full">

        {/* Icon block */}
        <div className="flex justify-center mb-8">
          <div className="relative">
            <div className="w-24 h-24 rounded-2xl bg-red-500/8 border border-red-500/20 flex items-center justify-center">
              <ShieldX size={42} className="text-red-400" />
            </div>
            <div className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-500 border-2 border-[#040711] flex items-center justify-center">
              <span className="text-[9px] font-black text-white">!</span>
            </div>
          </div>
        </div>

        {/* Code + Title */}
        <div className="text-center mb-8">
          <p className="font-mono text-xs text-red-400/70 tracking-[0.3em] uppercase mb-3">HTTP 403 — Access Denied</p>
          <h1 className="text-3xl font-black text-white mb-3 tracking-tight">Insufficient Privileges</h1>
          <p className="text-slate-400 text-sm leading-relaxed">
            Your current role does not grant access to this resource.
            Contact your system administrator to request elevated permissions.
          </p>
        </div>

        {/* Access details card */}
        <div className="bg-[#070d19]/80 border border-[#0f2244] rounded-2xl p-6 mb-6 space-y-4 backdrop-blur-md">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
            <Lock size={12} />
            Access Control Details
          </h2>

          <div className="space-y-3">
            {/* Current role */}
            <div className="flex items-center justify-between py-2.5 border-b border-[#0f2244]">
              <span className="text-xs text-slate-400">Your current role</span>
              <span className={`px-2 py-0.5 rounded border text-[11px] font-bold uppercase tracking-wider ${roleColors[currentRole] ?? roleColors.analyst}`}>
                {currentRole}
              </span>
            </div>

            {/* Required role(s) */}
            {requiredRoles && (
              <div className="flex items-center justify-between py-2.5 border-b border-[#0f2244]">
                <span className="text-xs text-slate-400">Required role(s)</span>
                <div className="flex gap-1.5 flex-wrap justify-end">
                  {requiredRoles.map((r) => (
                    <span key={r} className={`px-2 py-0.5 rounded border text-[11px] font-bold uppercase tracking-wider ${roleColors[r] ?? roleColors.analyst}`}>
                      {r}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Missing permission */}
            <div className="flex items-center justify-between py-2.5">
              <span className="text-xs text-slate-400">Attempted path</span>
              <span className="font-mono text-[11px] text-slate-400 bg-[#03060c] px-2 py-1 rounded border border-[#0f203d] max-w-[220px] truncate">
                {from}
              </span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={() => navigate(-1)}
            className="flex-1 flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-[#070d19] border border-[#0f2244] hover:border-[#1a3a6e] text-slate-300 text-sm font-semibold transition-all hover:text-white"
          >
            <ArrowLeft size={16} />
            Go Back
          </button>
          <button
            onClick={() => navigate('/dashboard')}
            className="flex-1 flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-[#0066CC] hover:bg-[#0052a3] text-white text-sm font-semibold transition-all shadow-lg shadow-[#0066CC]/20 hover:shadow-[#0066CC]/35"
          >
            Return to Dashboard
            <ChevronRight size={16} />
          </button>
        </div>

        {/* Footer note */}
        <p className="text-center text-[10px] text-slate-600 mt-6">
          Banking Intelligence Platform · Role-Governed Access Control · Event logged
        </p>
      </div>
    </div>
  );
}
