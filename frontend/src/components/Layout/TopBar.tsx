// src/components/Layout/TopBar.tsx
import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, ChevronDown, LogOut, Settings, User, Search } from 'lucide-react';
import { useAuth } from '../../auth/AuthProvider';
import { useAuthStore } from '../../stores/authStore';
import { useUIStore } from '../../stores/uiStore';
import { Avatar } from '../ui/Avatar';
import { RoleBadge } from '../ui/StatusBadge';
import { env } from '../../config/env';

export function TopBar() {
  const isKeycloak = env.AUTH_PROVIDER === 'keycloak';
  return isKeycloak ? <TopBarKeycloak /> : <TopBarLegacy />;
}

function TopBarKeycloak() {
  const { applicationUser, logout } = useAuth();
  return <TopBarShell user={applicationUser} onLogout={logout} />;
}

function TopBarLegacy() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  return <TopBarShell user={user} onLogout={() => { logout(); navigate('/login', { replace: true }); }} />;
}

interface TopBarUser {
  name: string;
  email: string;
  role: string;
}

function TopBarShell({ user, onLogout }: { user: TopBarUser | null; onLogout: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { notifications } = useUIStore();
  const unread = notifications.filter((n) => !n.read).length;
  const navigate = useNavigate();

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  return (
    <header className="h-12 border-b border-bg-border bg-bg-secondary/80 backdrop-blur-sm flex items-center justify-between px-4 flex-shrink-0">
      {/* Left: search */}
      <div className="flex-1 max-w-md">
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-colors duration-150 ${
          searchFocused ? 'border-blue-500/40 bg-bg-tertiary' : 'border-bg-border bg-bg-tertiary/50'
        }`}>
          <Search size={14} className="text-slate-500 flex-shrink-0" />
          <input
            type="text"
            placeholder="Search..."
            className="bg-transparent border-none outline-none text-sm text-slate-300 placeholder-slate-600 w-full"
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setSearchFocused(false)}
          />
        </div>
      </div>

      {/* Right: notifications + user menu */}
      <div className="flex items-center gap-2 ml-4">
        {/* Notifications */}
        <button className="relative p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-bg-hover transition-colors duration-150">
          <Bell size={16} />
          {unread > 0 && (
            <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-blue-500" />
          )}
        </button>

        {/* User menu */}
        {user && (
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-bg-hover transition-colors duration-150"
            >
              <Avatar name={user.name} size="sm" />
              <span className="text-sm text-slate-300 hidden md:inline max-w-[120px] truncate">{user.name}</span>
              <ChevronDown size={12} className={`text-slate-500 transition-transform duration-150 ${menuOpen ? 'rotate-180' : ''}`} />
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 w-64 bg-bg-card border border-bg-border rounded-xl shadow-lg py-1 z-50 animate-fade-in">
                {/* User info */}
                <div className="px-4 py-3 border-b border-bg-border">
                  <p className="text-sm font-medium text-slate-200 truncate">{user.name}</p>
                  <p className="text-xs text-slate-500 truncate mt-0.5">{user.email}</p>
                  <div className="mt-2">
                    <RoleBadge role={user.role} />
                  </div>
                </div>

                {/* Actions */}
                <div className="py-1">
                  <button
                    onClick={() => { setMenuOpen(false); navigate('/profile'); }}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-slate-400 hover:text-slate-200 hover:bg-bg-hover transition-colors"
                  >
                    <User size={14} />
                    Profile
                  </button>
                  <button
                    onClick={() => { setMenuOpen(false); navigate('/settings'); }}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-slate-400 hover:text-slate-200 hover:bg-bg-hover transition-colors"
                  >
                    <Settings size={14} />
                    Settings
                  </button>
                </div>

                {/* Sign out */}
                <div className="border-t border-bg-border py-1">
                  <button
                    onClick={() => { setMenuOpen(false); onLogout(); }}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors"
                  >
                    <LogOut size={14} />
                    Sign Out
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
