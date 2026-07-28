// src/components/auth/LoginPage.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, AlertCircle, Loader2, Lock, Mail } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { authApi } from '../../api/auth';
import { useAuth } from '../../auth/AuthProvider';
import { env } from '../../config/env';

function LoginPageKeycloak() {
  const { login } = useAuth();
  const { error } = useAuthStore();

  return (
    <div className="min-h-screen flex items-center justify-center px-6" style={{ background: 'var(--bg-primary)' }}>
      <div className="w-full max-w-sm">
        {/* Logo + title */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-5"
            style={{ background: 'rgba(37,99,235,0.08)' }}>
            <Building2 size={28} style={{ color: 'var(--accent-blue)' }} />
          </div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Banking Intelligence
          </h1>
          <p className="text-sm mt-2" style={{ color: 'var(--text-muted)' }}>
            Secure access to the Banking Intelligence Platform
          </p>
        </div>

        {/* SSO card */}
        <div className="rounded-xl p-6 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
          {error && (
            <div className="flex items-center gap-2 rounded-lg px-3 py-2.5 mb-4 text-sm"
              style={{ background: 'rgba(220,38,38,0.08)', border: '1px solid rgba(220,38,38,0.15)', color: 'var(--accent-red)' }}>
              <AlertCircle size={14} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            onClick={() => login()}
            className="w-full flex items-center justify-center gap-2 text-white font-medium py-2.5 rounded-lg transition-all duration-150 text-sm"
            style={{ background: 'var(--accent-blue)' }}
          >
            <Building2 size={16} />
            Continue with SSO
          </button>
        </div>

        <p className="text-center text-xs mt-6" style={{ color: 'var(--text-subtle)' }}>
          Authentication is managed securely by your organisation.
        </p>
      </div>
    </div>
  );
}

function LoginPageLegacy() {
  const navigate = useNavigate();
  const { setUser, setError, error } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) { setError('Please enter your email and password.'); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.login({ email, password });
      setUser(res.user, res.access_token);
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : typeof detail === 'object' && detail !== null && 'message' in detail
            ? (detail as { message: string }).message
            : 'Invalid credentials. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6" style={{ background: 'var(--bg-primary)' }}>
      <div className="w-full max-w-sm">
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-5"
            style={{ background: 'rgba(37,99,235,0.08)' }}>
            <Building2 size={28} style={{ color: 'var(--accent-blue)' }} />
          </div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Banking Intelligence
          </h1>
          <p className="text-sm mt-2" style={{ color: 'var(--text-muted)' }}>Sign in to your account</p>
        </div>

        <div className="rounded-xl p-6 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
          {error && (
            <div className="flex items-center gap-2 rounded-lg px-3 py-2.5 mb-4 text-sm"
              style={{ background: 'rgba(220,38,38,0.08)', border: '1px solid rgba(220,38,38,0.15)', color: 'var(--accent-red)' }}>
              <AlertCircle size={14} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
            <div>
              <label htmlFor="email" className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-muted)' }}>
                Email / Username
              </label>
              <div className="relative">
                <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-subtle)' }} />
                <input id="email" type="text" autoComplete="username" value={email}
                  onChange={(e) => setEmail(e.target.value)} placeholder="analyst_001" className="input pl-9" />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-muted)' }}>
                Password
              </label>
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-subtle)' }} />
                <input id="password" type="password" autoComplete="current-password" value={password}
                  onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className="input pl-9" />
              </div>
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? <><Loader2 size={14} className="animate-spin" /> Signing in...</> : 'Sign In'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs mt-6" style={{ color: 'var(--text-subtle)' }}>
          Banking Intelligence Platform
        </p>
      </div>
    </div>
  );
}

export function LoginPage() {
  const isKeycloak = env.AUTH_PROVIDER === 'keycloak';
  return isKeycloak ? <LoginPageKeycloak /> : <LoginPageLegacy />;
}
