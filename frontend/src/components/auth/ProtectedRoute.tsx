// src/components/auth/ProtectedRoute.tsx
import React, { useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { useAuth } from '../../auth/AuthProvider';
import { env } from '../../config/env';
import { Building2, LogOut, Mail, RefreshCw, ShieldAlert, ShieldX, ArrowLeft } from 'lucide-react';

interface Props {
  children: React.ReactNode;
  requiredRole?: string | string[];
  requiredPermission?: string | string[];
}

export function ProtectedRoute({ children, requiredRole, requiredPermission }: Props) {
  const isKeycloak = env.AUTH_PROVIDER === 'keycloak';
  if (isKeycloak) {
    return <ProtectedRouteKeycloak requiredRole={requiredRole} requiredPermission={requiredPermission}>{children}</ProtectedRouteKeycloak>;
  }
  return <ProtectedRouteLegacy requiredRole={requiredRole} requiredPermission={requiredPermission}>{children}</ProtectedRouteLegacy>;
}

// ── Shared full-screen wrappers ─────────────────────────────────────────

function AuthScreen({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center px-6" style={{ background: 'var(--bg-primary)' }}>
      <div className="w-full max-w-sm text-center">{children}</div>
    </div>
  );
}

function AuthLogo() {
  return (
    <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-5"
      style={{ background: 'rgba(37,99,235,0.08)' }}>
      <Building2 size={28} style={{ color: 'var(--accent-blue)' }} />
    </div>
  );
}

// ── Keycloak protected route ────────────────────────────────────────────

function ProtectedRouteKeycloak({ children, requiredRole, requiredPermission }: { children: React.ReactNode; requiredRole?: string | string[]; requiredPermission?: string | string[] }) {
  const { phase, applicationUser, error, logout, login, hasPermission } = useAuth();

  if (phase === 'bootstrapping' || phase === 'loading-user') {
    return (
      <AuthScreen>
        <AuthLogo />
        <h1 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Banking Intelligence</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
          {phase === 'bootstrapping' ? 'Connecting securely...' : 'Loading your workspace...'}
        </p>
        <div className="flex justify-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <span key={i} className="w-2 h-2 rounded-full animate-pulse"
              style={{ background: 'var(--accent-blue)', animationDelay: `${i * 0.2}s` }} />
          ))}
        </div>
      </AuthScreen>
    );
  }

  // Fire login() once when phase requires redirect — not on every render.
  // expired uses force=true (prompt:'login') so Keycloak shows credentials
  // instead of bouncing silently back via an alive SSO session → loop.
  useEffect(() => {
    if (phase === 'unauthenticated') login();
    if (phase === 'expired') login(true);
  }, [phase, login]);

  if (phase === 'unauthenticated') {
    return (
      <AuthScreen>
        <AuthLogo />
        <h1 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Banking Intelligence</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>Redirecting to secure login...</p>
      </AuthScreen>
    );
  }

  if (phase === 'expired') {
    return (
      <AuthScreen>
        <AuthLogo />
        <h1 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Session Expired</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>Your session has expired. Redirecting to login...</p>
      </AuthScreen>
    );
  }

  if (phase === 'unlinked') {
    return (
      <AuthScreen>
        <AuthLogo />
        <h1 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Account Not Linked</h1>
        <p className="text-sm mb-6 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
          Your identity has been verified, but no Banking Intelligence account is linked to it. Contact your administrator.
        </p>
        <div className="flex flex-col gap-2">
          <button onClick={logout} className="btn-secondary w-full"><LogOut size={14} />Sign Out</button>
          <a href="mailto:admin@banking-intelligence.com" className="btn-ghost w-full text-sm"><Mail size={14} />Contact Administrator</a>
        </div>
      </AuthScreen>
    );
  }

  if (phase === 'forbidden') {
    return (
      <AuthScreen>
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-5"
          style={{ background: 'rgba(220,38,38,0.08)' }}>
          <ShieldAlert size={28} style={{ color: 'var(--accent-red)' }} />
        </div>
        <h1 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Access Suspended</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>Your account is currently inactive. Contact your administrator.</p>
        <button onClick={logout} className="btn-secondary w-full"><LogOut size={14} />Sign Out</button>
      </AuthScreen>
    );
  }

  if (phase === 'error') {
    return (
      <AuthScreen>
        <AuthLogo />
        <h1 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Service Unavailable</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>{error}</p>
        <button onClick={() => window.location.reload()} className="btn-primary w-full">
          <RefreshCw size={14} />Retry
        </button>
      </AuthScreen>
    );
  }

  if (requiredPermission) {
    const perms = Array.isArray(requiredPermission) ? requiredPermission : [requiredPermission];
    if (perms.length > 0 && !perms.some((p) => hasPermission(p))) {
      return <Navigate to="/unauthorized" state={{ requiredPermission, from: window.location.pathname }} replace />;
    }
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

function ProtectedRouteLegacy({ children, requiredRole, requiredPermission }: { children: React.ReactNode; requiredRole?: string | string[]; requiredPermission?: string | string[] }) {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requiredPermission) {
    const perms = Array.isArray(requiredPermission) ? requiredPermission : [requiredPermission];
    if (perms.length > 0 && !perms.some((p) => user?.permissions?.includes(p))) {
      return <Navigate to="/unauthorized" state={{ requiredPermission, from: window.location.pathname }} replace />;
    }
  }

  if (requiredRole) {
    const roles = Array.isArray(requiredRole) ? requiredRole : [requiredRole];
    if (!user || !roles.includes(user.role)) {
      return <Navigate to="/unauthorized" state={{ requiredRole, from: window.location.pathname }} replace />;
    }
  }

  return <>{children}</>;
}
