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
    <div className="min-h-screen flex items-center justify-center bg-bg-primary px-6">
      <div className="w-full max-w-sm">
        {/* Logo + title */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600/10 mb-4">
            <Building2 size={24} className="text-blue-400" />
          </div>
          <h1 className="text-xl font-semibold text-white">Banking Intelligence</h1>
          <p className="text-sm text-slate-500 mt-1.5">Secure access to the Banking Intelligence Platform.</p>
        </div>

        {/* SSO button card */}
        <div className="bg-bg-card border border-bg-border rounded-xl p-6">
          {error && (
            <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2.5 mb-4 text-sm text-red-400">
              <AlertCircle size={14} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            onClick={() => login()}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-medium py-2.5 rounded-lg transition-colors duration-150 text-sm"
          >
            <Building2 size={16} />
            Continue with SSO
          </button>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-slate-600 mt-6">
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
    <div className="min-h-screen flex items-center justify-center bg-bg-primary px-6">
      <div className="w-full max-w-sm">
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600/10 mb-4">
            <Building2 size={24} className="text-blue-400" />
          </div>
          <h1 className="text-xl font-semibold text-white">Banking Intelligence</h1>
          <p className="text-sm text-slate-500 mt-1.5">Sign in to your account</p>
        </div>

        <div className="bg-bg-card border border-bg-border rounded-xl p-6">
          {error && (
            <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2.5 mb-4 text-sm text-red-400">
              <AlertCircle size={14} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
            <div>
              <label htmlFor="email" className="block text-xs font-medium text-slate-400 mb-1.5">Email / Username</label>
              <div className="relative">
                <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  id="email"
                  type="text"
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst_001"
                  className="input pl-9"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-medium text-slate-400 mb-1.5">Password</label>
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input pl-9"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full"
            >
              {loading ? <><Loader2 size={14} className="animate-spin" /> Signing in...</> : 'Sign In'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-600 mt-6">
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
