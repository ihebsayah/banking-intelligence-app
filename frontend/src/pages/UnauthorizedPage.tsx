// src/pages/UnauthorizedPage.tsx
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ShieldX, ArrowLeft } from 'lucide-react';
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
  const requiredRoles = requiredRole
    ? Array.isArray(requiredRole) ? requiredRole : [requiredRole]
    : null;

  return (
    <div className="min-h-screen flex items-center justify-center px-6" style={{ background: 'var(--bg-primary)' }}>
      <div className="w-full max-w-sm text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-5"
          style={{ background: 'rgba(220,38,38,0.08)' }}>
          <ShieldX size={28} style={{ color: 'var(--accent-red)' }} />
        </div>

        <h1 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Access Denied</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
          Your current role does not grant access to this resource.
        </p>

        <div className="rounded-xl p-4 mb-6 text-left space-y-3 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
          <div className="flex items-center justify-between text-sm">
            <span style={{ color: 'var(--text-muted)' }}>Your role</span>
            <span className="font-medium capitalize" style={{ color: 'var(--text-primary)' }}>{currentRole}</span>
          </div>
          {requiredRoles && (
            <div className="flex items-center justify-between text-sm">
              <span style={{ color: 'var(--text-muted)' }}>Required</span>
              <span className="font-medium capitalize" style={{ color: 'var(--text-primary)' }}>{requiredRoles.join(', ')}</span>
            </div>
          )}
          <div className="flex items-center justify-between text-sm">
            <span style={{ color: 'var(--text-muted)' }}>Path</span>
            <span className="font-mono text-xs truncate max-w-[180px]" style={{ color: 'var(--text-secondary)' }}>{from}</span>
          </div>
        </div>

        <div className="flex gap-2">
          <button onClick={() => navigate(-1)} className="btn-secondary flex-1">
            <ArrowLeft size={14} />Go Back
          </button>
          <button onClick={() => navigate('/dashboard')} className="btn-primary flex-1">
            Dashboard
          </button>
        </div>

        <p className="text-[10px] mt-6" style={{ color: 'var(--text-subtle)' }}>
          Banking Intelligence Platform
        </p>
      </div>
    </div>
  );
}
