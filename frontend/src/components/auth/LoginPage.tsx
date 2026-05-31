// src/components/auth/LoginPage.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Lock, Mail, Building2, AlertCircle, Loader2 } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { authApi } from '../../api/auth';

export function LoginPage() {
  const navigate = useNavigate();
  const { setUser, setError, error } = useAuthStore();
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading]   = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) { setError('Please enter your email and password.'); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.login({ email, password });
      setUser(res.user, res.access_token);
      if (remember) localStorage.setItem('banking_remember', email);
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      // Backend returns detail as { error: string, message: string }
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

  // Dev shortcut: fill in a valid backend mock user
  function useDemoLogin() {
    setEmail('analyst_001');
    setPassword('password');
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-[#040711]">
      {/* Animated background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-[#0a3d8a]/20 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-[#003366]/15 rounded-full blur-[120px] animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[#001a4d]/10 rounded-full blur-[150px]" />
        {/* Grid pattern */}
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: 'linear-gradient(rgba(59,130,246,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.5) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }} />
      </div>

      <div className="relative z-10 w-full max-w-md px-6">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-[#0066CC] to-[#003366] mb-4 shadow-[0_0_40px_rgba(0,102,204,0.4)]">
            <Building2 size={30} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Banking Intelligence</h1>
          <p className="text-slate-400 text-sm mt-1">Agent Dashboard · Headquarters</p>
        </div>

        {/* Card */}
        <div className="bg-[#0a1628]/80 border border-[#1a2d4e] rounded-2xl p-8 shadow-[0_24px_64px_rgba(0,0,0,0.6)] backdrop-blur-xl">
          <h2 className="text-lg font-semibold text-white mb-6">Sign in to your account</h2>

          {error && (
            <div className="flex items-center gap-2.5 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 mb-5 text-sm text-red-400">
              <AlertCircle size={15} className="flex-shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-xs font-medium text-slate-400 mb-1.5">Email / Username</label>
              <div className="relative">
                <Mail size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  id="email"
                  type="text"
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst_001"
                  className="w-full bg-[#0d1f3c] border border-[#1e3459] rounded-lg pl-10 pr-4 py-3 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-[#0066CC]/60 focus:ring-1 focus:ring-[#0066CC]/20 transition-all"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-xs font-medium text-slate-400 mb-1.5">Password</label>
              <div className="relative">
                <Lock size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  id="password"
                  type={showPass ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-[#0d1f3c] border border-[#1e3459] rounded-lg pl-10 pr-10 py-3 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-[#0066CC]/60 focus:ring-1 focus:ring-[#0066CC]/20 transition-all"
                />
                <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors">
                  {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* Remember + Forgot */}
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="w-4 h-4 rounded border-[#1e3459] bg-[#0d1f3c] accent-[#0066CC]"
                />
                <span className="text-sm text-slate-400">Stay signed in</span>
              </label>
              <button type="button" className="text-sm text-[#4d9fff] hover:text-[#66b3ff] transition-colors">
                Forgot password?
              </button>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-[#0066CC] hover:bg-[#0077ee] disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-lg transition-all duration-200 shadow-[0_0_24px_rgba(0,102,204,0.3)] hover:shadow-[0_0_32px_rgba(0,102,204,0.5)] mt-2"
            >
              {loading ? <><Loader2 size={16} className="animate-spin" /> Authenticating...</> : 'Sign In'}
            </button>
          </form>

          {/* Dev demo */}
          <div className="mt-5 pt-5 border-t border-[#1a2d4e]">
            <button
              onClick={useDemoLogin}
              className="w-full text-center text-xs text-slate-600 hover:text-slate-400 transition-colors"
            >
              Use demo credentials (development)
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-slate-700 mt-6">
          © 2025 Banking Intelligence Platform. All rights reserved.
        </p>
      </div>
    </div>
  );
}
