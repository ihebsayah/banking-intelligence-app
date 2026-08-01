// src/components/Layout/TopBar.tsx
import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, LogOut, Settings, User, Moon, Sun, Monitor, Command } from 'lucide-react';
import { useAuth } from '../../auth/AuthProvider';
import { useAuthStore } from '../../stores/authStore';
import { useUIStore } from '../../stores/uiStore';
import { Avatar } from '../ui/Avatar';
import { RoleBadge } from '../ui/StatusBadge';
import { env } from '../../config/env';
import { NotificationBell } from '../notifications/NotificationBell';

export function TopBar() {
  const isKeycloak = env.AUTH_PROVIDER === 'keycloak';
  return isKeycloak ? <TopBarKeycloak /> : <TopBarLegacy />;
}

function TopBarKeycloak() {
  const { applicationUser, permissions, logout } = useAuth();
  return <TopBarShell user={applicationUser} permissions={permissions} onLogout={logout} />;
}

function TopBarLegacy() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  return <TopBarShell user={user} permissions={user?.permissions} onLogout={() => { logout(); navigate('/login', { replace: true }); }} />;
}

interface TopBarUser {
  name: string;
  email: string;
  role: string;
}

function TopBarShell({ user, permissions, onLogout }: { user: TopBarUser | null; permissions?: string[]; onLogout: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { theme, setTheme, toggleCommandPalette } = useUIStore();

  useEffect(() => {
    if (!menuOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  const cycleTheme = () => {
    const order: Array<'light' | 'dark' | 'system'> = ['light', 'dark', 'system'];
    const idx = order.indexOf(theme);
    setTheme(order[(idx + 1) % 3]);
  };

  const ThemeIcon = theme === 'dark' ? Moon : theme === 'light' ? Sun : Monitor;

  return (
    <header className="h-12 border-b flex items-center justify-between px-4 flex-shrink-0"
      style={{ borderColor: 'var(--bg-border)', background: 'var(--bg-secondary)' }}>
      {/* Left: workspace title */}
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          Banking Intelligence
        </h1>
      </div>

      {/* Right: command palette hint, theme, user menu */}
      <div className="flex items-center gap-1">
        {/* Command palette trigger */}
        <button
          onClick={toggleCommandPalette}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-colors duration-150"
          style={{ color: 'var(--text-subtle)' }}
          title="Command Palette (Ctrl+K)"
        >
          <Command size={13} />
          <span className="hidden md:inline font-mono" style={{ color: 'var(--text-subtle)' }}>⌘K</span>
        </button>

        {/* Notification bell */}
        <NotificationBell permissions={permissions} />

        {/* Theme switch */}
        <button
          onClick={cycleTheme}
          className="p-2 rounded-lg transition-colors duration-150"
          style={{ color: 'var(--text-muted)' }}
          title={`Theme: ${theme}`}
        >
          <ThemeIcon size={15} />
        </button>

        {/* User menu */}
        {user && (
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors duration-150"
              style={{ color: 'var(--text-secondary)' }}
            >
              <Avatar name={user.name} size="sm" />
              <span className="text-sm hidden md:inline max-w-[120px] truncate">{user.name}</span>
              <ChevronDown size={12} className={`transition-transform duration-150 ${menuOpen ? 'rotate-180' : ''}`}
                style={{ color: 'var(--text-subtle)' }} />
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 w-60 rounded-xl shadow-lg py-1 z-50 animate-fade-in border"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
                <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--bg-border)' }}>
                  <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{user.name}</p>
                  <p className="text-xs truncate mt-0.5" style={{ color: 'var(--text-subtle)' }}>{user.email}</p>
                  <div className="mt-2"><RoleBadge role={user.role} /></div>
                </div>

                <div className="py-1">
                  <button
                    onClick={() => { setMenuOpen(false); navigate('/profile'); }}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-sm transition-colors"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    <User size={14} />Profile
                  </button>
                  <button
                    onClick={() => { setMenuOpen(false); navigate('/settings'); }}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-sm transition-colors"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    <Settings size={14} />Settings
                  </button>
                </div>

                <div className="border-t py-1" style={{ borderColor: 'var(--bg-border)' }}>
                  <button
                    onClick={() => { setMenuOpen(false); onLogout(); }}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-sm transition-colors"
                    style={{ color: 'var(--accent-red)' }}
                  >
                    <LogOut size={14} />Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
