// src/components/auth/ProtectedRoute.tsx
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { useAuth } from '../../auth/AuthProvider';
import { env } from '../../config/env';
import { Building2, LogOut, Mail, RefreshCw, ShieldAlert } from 'lucide-react';

interface Props {
  children: React.ReactNode;
  requiredRole?: string | string[];
}

export function ProtectedRoute({ children, requiredRole }: Props) {
  const isKeycloak = env.AUTH_PROVIDER === 'keycloak';
  if (isKeycloak) {
    return <ProtectedRouteKeycloak requiredRole={requiredRole}>{children}</ProtectedRouteKeycloak>;
  }
  return <ProtectedRouteLegacy requiredRole={requiredRole}>{children}</ProtectedRouteLegacy>;
}

// ── Shared full-screen wrappers ─────────────────────────────────────────

function AuthScreen({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center px-6">
      <div className="w-full max-w-sm text-center">{children}</div>
    </div>
  );
}

function AuthLogo() {
  return (
    <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600/10 mb-4">
      <Building2 size={24} className="text-blue-400" />
    </div>
  );
}

// ── Keycloak protected route ────────────────────────────────────────────

function ProtectedRouteKeycloak({ children, requiredRole }: { children: React.ReactNode; requiredRole?: string | string[] }) {
  const { phase, applicationUser, logout, login } = useAuth();

  if (phase === 'bootstrapping' || phase === 'loading-user') {
    return (
      <AuthScreen>
        <AuthLogo />
        <h1 className="text-lg font-semibold text-white mb-1">Banking Intelligence</h1>
        <p className="text-sm text-slate-500 mb-6">
          {phase === 'bootstrapping' ? 'Connecting securely...' : 'Loading your workspace...'}
        </p>
        <div className="flex justify-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse [animation-delay:0.2s]" />
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse [animation-delay:0.4s]" />
        </div>
      </AuthScreen>
    );
  }

  if (phase === 'unauthenticated') {
    return <Navigate to="/login" replace />;
  }

  if (phase === 'expired') {
    return (
      <AuthScreen>
        <AuthLogo />
        <h1 className="text-lg font-semibold text-white mb-2">Session Expired</h1>
        <p className="text-sm text-slate-500 mb-6">Your secure session has expired.</p>
        <button onClick={login} className="btn-primary w-full">
          Sign in again
        </button>
      </AuthScreen>
    );
  }

  if (phase === 'unlinked') {
    return (
      <AuthScreen>
        <AuthLogo />
        <h1 className="text-lg font-semibold text-white mb-2">Account Not Linked</h1>
        <p className="text-sm text-slate-500 mb-6 leading-relaxed">
          Your identity has been verified successfully. However your organisation has not linked your account to Banking Intelligence.
          Please contact your administrator.
        </p>
        <div className="flex flex-col gap-2">
          <button onClick={logout} className="btn-secondary w-full">
            <LogOut size={14} />
            Sign Out
          </button>
          <a href="mailto:admin@banking-intelligence.com" className="btn-ghost w-full text-sm">
            <Mail size={14} />
            Contact Administrator
          </a>
        </div>
      </AuthScreen>
    );
  }

  if (phase === 'forbidden') {
    return (
      <AuthScreen>
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-red-500/10 mb-4">
          <ShieldAlert size={24} className="text-red-400" />
        </div>
        <h1 className="text-lg font-semibold text-white mb-2">Access Suspended</h1>
        <p className="text-sm text-slate-500 mb-6">Your account is currently inactive. Contact your administrator.</p>
        <button onClick={logout} className="btn-secondary w-full">
          <LogOut size={14} />
          Sign Out
        </button>
      </AuthScreen>
    );
  }

  if (phase === 'error') {
    return (
      <AuthScreen>
        <AuthLogo />
        <h1 className="text-lg font-semibold text-white mb-2">Unable to reach the authentication service</h1>
        <p className="text-sm text-slate-500 mb-6">The authentication service is temporarily unavailable.</p>
        <button onClick={() => window.location.reload()} className="btn-primary w-full">
          <RefreshCw size={14} />
          Retry
        </button>
      </AuthScreen>
    );
  }

  if (requiredRole && applicationUser) {
    const roles = Array.isArray(requiredRole) ? requiredRole : [requiredRole];
    if (!roles.includes(applicationUser.role)) {
      return <Navigate to="/unauthorized" state={{ requiredRole, from: window.location.pathname }} replace />;
    }
  }

  return <>{children}</>;
}

// ── Legacy protected route ──────────────────────────────────────────────

function ProtectedRouteLegacy({ children, requiredRole }: { children: React.ReactNode; requiredRole?: string | string[] }) {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requiredRole) {
    const roles = Array.isArray(requiredRole) ? requiredRole : [requiredRole];
    if (!user || !roles.includes(user.role)) {
      return <Navigate to="/unauthorized" state={{ requiredRole, from: window.location.pathname }} replace />;
    }
  }

  return <>{children}</>;
}
