// src/components/Layout/BankingSidebar.tsx
import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  Building2,
  Settings2,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useAuth } from '../../auth/AuthProvider';
import { useUIStore } from '../../stores/uiStore';
import { usePermissions } from '../../lib/permissions';
import { NAV_GROUPS, BOTTOM_NAV_ITEMS } from '../../lib/navigation';
import { env } from '../../config/env';
import { Avatar } from '../ui/Avatar';
import { clsx } from 'clsx';

interface SidebarUser {
  name: string;
  role: string;
}

function SidebarShell({ user, onLogout }: { user: SidebarUser | null; onLogout: () => void }) {
  const { sidebarCollapsed, toggleSidebar } = useUIStore();
  const { canAccess, userRole } = usePermissions();

  const visibleGroups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) =>
      canAccess({
        requiredPermissions: item.requiredPermissions,
        requiredRoles: item.requiredRoles,
      })
    ),
  })).filter((group) => group.items.length > 0);

  return (
    <aside className={clsx(
      'flex flex-col h-screen border-r transition-all duration-200 flex-shrink-0',
      sidebarCollapsed ? 'w-[56px]' : 'w-[220px]',
    )} style={{ background: 'var(--bg-secondary)', borderColor: 'var(--bg-border)' }}>
      {/* Logo */}
      <div className={clsx('flex items-center h-12 border-b px-3 flex-shrink-0', sidebarCollapsed && 'justify-center px-0')}
        style={{ borderColor: 'var(--bg-border)' }}>
        <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: 'rgba(37,99,235,0.1)' }}>
          <Building2 size={15} style={{ color: 'var(--accent-blue)' }} />
        </div>
        {!sidebarCollapsed && (
          <span className="ml-2.5 text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
            Banking Intel
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-4 overflow-y-auto">
        {visibleGroups.map((group) => (
          <div key={group.id} className="space-y-0.5">
            {!sidebarCollapsed && group.title && (
              <p className="px-2.5 pb-1 text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-subtle)' }}>
                {group.title}
              </p>
            )}
            {group.items.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) => clsx(
                  'flex items-center gap-2.5 rounded-lg transition-colors duration-150 text-sm font-medium group relative',
                  sidebarCollapsed ? 'justify-center p-2' : 'px-2.5 py-2',
                )}
                style={({ isActive }) => ({
                  background: isActive ? 'rgba(37,99,235,0.1)' : undefined,
                  color: isActive ? 'var(--accent-blue)' : 'var(--text-muted)',
                })}
              >
                {({ isActive }) => (
                  <>
                    <Icon size={16} className="flex-shrink-0" />
                    {!sidebarCollapsed && <span className="truncate">{label}</span>}
                    {sidebarCollapsed && (
                      <div className="absolute left-full ml-2 px-2 py-1 rounded text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 border"
                        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}>
                        {label}
                      </div>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="border-t p-2 space-y-0.5 flex-shrink-0" style={{ borderColor: 'var(--bg-border)' }}>
        {/* Bottom nav items (Profile, Settings) */}
        {BOTTOM_NAV_ITEMS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => clsx(
              'flex items-center gap-2.5 rounded-lg transition-colors duration-150 text-sm',
              sidebarCollapsed ? 'justify-center p-2' : 'px-2.5 py-2',
            )}
            style={({ isActive }) => ({
              background: isActive ? 'rgba(37,99,235,0.1)' : undefined,
              color: isActive ? 'var(--accent-blue)' : 'var(--text-subtle)',
            })}
          >
            {!sidebarCollapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}

        {/* Dev monitor (admin only) */}
        {!sidebarCollapsed && userRole === 'admin' && (
          <NavLink
            to="/dev"
            className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 transition-colors duration-150 text-xs"
            style={{ color: 'var(--text-subtle)' }}
          >
            <Settings2 size={13} className="flex-shrink-0" />
            <span className="truncate">Dev Monitor</span>
          </NavLink>
        )}

        {/* User info */}
        {user && (
          <div className={clsx('flex items-center gap-2 px-2.5 py-2 rounded-lg', sidebarCollapsed && 'justify-center px-0')}>
            <Avatar name={user.name} size="sm" />
            {!sidebarCollapsed && (
              <div className="flex-1 overflow-hidden">
                <p className="text-xs font-medium truncate" style={{ color: 'var(--text-primary)' }}>{user.name}</p>
                <p className="text-[10px] truncate capitalize" style={{ color: 'var(--text-subtle)' }}>{user.role}</p>
              </div>
            )}
          </div>
        )}

        {/* Sign out */}
        <button
          onClick={onLogout}
          className={clsx(
            'flex items-center gap-2.5 w-full rounded-lg transition-colors duration-150 text-sm',
            sidebarCollapsed ? 'justify-center p-2' : 'px-2.5 py-2',
          )}
          style={{ color: 'var(--text-subtle)' }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent-red)'; e.currentTarget.style.background = 'rgba(220,38,38,0.08)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-subtle)'; e.currentTarget.style.background = 'transparent'; }}
        >
          {!sidebarCollapsed && 'Sign Out'}
        </button>

        {/* Collapse toggle */}
        <button
          onClick={toggleSidebar}
          className={clsx(
            'flex items-center gap-2.5 w-full rounded-lg transition-colors duration-150 text-xs',
            sidebarCollapsed ? 'justify-center p-2' : 'px-2.5 py-2',
          )}
          style={{ color: 'var(--text-subtle)' }}
        >
          {sidebarCollapsed ? <ChevronsRight size={14} /> : <><ChevronsLeft size={14} /><span>Collapse</span></>}
        </button>
      </div>
    </aside>
  );
}

function BankingSidebarKeycloak() {
  const { applicationUser, logout } = useAuth();
  return <SidebarShell user={applicationUser} onLogout={logout} />;
}

function BankingSidebarLegacy() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  return <SidebarShell user={user} onLogout={() => { logout(); navigate('/login', { replace: true }); }} />;
}

export function BankingSidebar() {
  const isKeycloak = env.AUTH_PROVIDER === 'keycloak';
  return isKeycloak ? <BankingSidebarKeycloak /> : <BankingSidebarLegacy />;
}

