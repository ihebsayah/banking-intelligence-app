// src/components/Layout/Header.tsx
import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Bell, LogIn, LogOut, User, Key } from 'lucide-react';
import { useQueryStore } from '../../stores/queryStore';
import { login } from '../../api/queries';

const PAGE_TITLES: Record<string, { title: string; sub: string }> = {
  '/':            { title: 'Dashboard',      sub: 'System overview & quick stats' },
  '/query':       { title: 'Query Tester',   sub: 'Test full pipeline with natural language' },
  '/agents':      { title: 'Agent Monitor',  sub: 'Real-time agent health & communication logs' },
  '/performance': { title: 'Performance',    sub: 'Load testing & performance metrics' },
  '/settings':    { title: 'Settings',       sub: 'API, WebSocket & display configuration' },
};

export function Header() {
  const location  = useLocation();
  const { authToken, userRole, userId, setAuth, clearAuth } = useQueryStore();
  const [showLogin, setShowLogin] = useState(false);
  const [loginForm, setLoginForm] = useState({ username: 'analyst_001', password: 'password' });
  const [loginError, setLoginError] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);

  const page = PAGE_TITLES[location.pathname] ?? PAGE_TITLES['/'];

  const handleLogin = async () => {
    setLoggingIn(true);
    setLoginError('');
    try {
      const result = await login(loginForm.username, loginForm.password);
      setAuth(result.token, result.role, result.userId);
      setShowLogin(false);
    } catch {
      setLoginError('Invalid credentials. Try analyst_001 / password');
    } finally {
      setLoggingIn(false);
    }
  };

  return (
    <header className="header-gradient flex items-center justify-between px-6 py-3 flex-shrink-0">
      <div>
        <h1 className="text-lg font-bold text-slate-100">{page.title}</h1>
        <p className="text-xs text-slate-500">{page.sub}</p>
      </div>

      <div className="flex items-center gap-3">
        {authToken ? (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-bg-tertiary border border-bg-border rounded-lg px-3 py-1.5">
              <User size={13} className="text-slate-400" />
              <span className="text-xs text-slate-300">{userId}</span>
              <span className="badge-blue text-[10px]">{userRole}</span>
            </div>
            <button onClick={clearAuth} className="btn-ghost text-xs px-2 py-1.5">
              <LogOut size={13} /> Logout
            </button>
          </div>
        ) : (
          <button onClick={() => setShowLogin(true)} className="btn-primary text-xs px-3 py-1.5">
            <LogIn size={13} /> Login
          </button>
        )}
      </div>

      {/* Login modal */}
      {showLogin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowLogin(false)}>
          <div className="glass-card-static p-6 w-80 animate-slide-up" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 mb-4">
              <Key size={16} className="text-blue-400" />
              <h3 className="text-base font-semibold text-slate-200">API Authentication</h3>
            </div>
            <p className="text-xs text-slate-500 mb-4">Login to get JWT for API requests</p>
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); handleLogin(); }}>
              <div>
                <label className="label">Username</label>
                <input
                  className="input"
                  value={loginForm.username}
                  onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
                  placeholder="analyst_001"
                />
              </div>
              <div>
                <label className="label">Password</label>
                <input
                  type="password"
                  className="input"
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                  placeholder="password"
                />
              </div>
              {loginError && <p className="text-xs text-red-400">{loginError}</p>}
              <div className="bg-bg-tertiary rounded-lg p-2 border border-bg-border">
                <p className="text-[10px] text-slate-500 font-mono">
                  analyst_001, analyst_002, compliance_001, manager_001<br/>password: "password"
                </p>
              </div>
              <div className="flex gap-2 pt-1">
                <button type="button" onClick={() => setShowLogin(false)} className="btn-secondary flex-1">Cancel</button>
                <button type="submit" disabled={loggingIn} className="btn-primary flex-1">
                  {loggingIn ? <><span className="spinner" /> Logging in...</> : 'Login'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </header>
  );
}
