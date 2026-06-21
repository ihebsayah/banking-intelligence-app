// src/components/Layout/BankingSidebar.tsx
import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  Building2, 
  LayoutDashboard, 
  GitBranch, 
  Bot, 
  Settings, 
  LogOut, 
  ChevronLeft, 
  ChevronRight, 
  Bell,
  BarChart3,
  ShieldAlert,
  Scale,
  FileText,
  Settings2,
  User,
  Shield
} from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useUIStore } from '../../stores/uiStore';
import { clsx } from 'clsx';

const NAV_ITEMS = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard', roles: ['analyst', 'manager', 'compliance', 'admin'] },
  { to: '/branches',   icon: GitBranch,        label: 'Branches', roles: ['analyst', 'manager', 'compliance', 'admin'] },
  { to: '/assistant',  icon: Bot,              label: 'AI Assistant', roles: ['analyst', 'manager', 'compliance', 'admin'] },
  { to: '/kpi',             icon: BarChart3,   label: 'KPI Analytics',   roles: ['analyst', 'manager', 'compliance', 'admin'] },
  { to: '/kpi-governance',  icon: Shield,      label: 'KPI Governance',  roles: ['analyst', 'manager', 'compliance', 'admin'] },
  { to: '/risk',       icon: ShieldAlert,      label: 'Risk Monitor', roles: ['analyst', 'manager', 'compliance', 'admin'] },
  { to: '/compliance', icon: Scale,            label: 'Compliance', roles: ['compliance', 'manager', 'admin'] },
  { to: '/reports',    icon: FileText,         label: 'Reports', roles: ['manager', 'admin'] },
  { to: '/admin',      icon: Settings2,        label: 'Admin Portal', roles: ['admin'] },
  { to: '/profile',    icon: User,             label: 'User Profile', roles: ['analyst', 'manager', 'compliance', 'admin'] },
  { to: '/settings',   icon: Settings,         label: 'Settings', roles: ['analyst', 'manager', 'compliance', 'admin'] },
];

export function BankingSidebar() {
  const { user, logout } = useAuthStore();
  const { sidebarCollapsed, toggleSidebar, notifications } = useUIStore();
  const navigate = useNavigate();
  const unread = notifications.filter((n) => !n.read).length;

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  // Filter items by user role
  const userRole = user?.role ?? 'analyst';
  const visibleNavItems = NAV_ITEMS.filter(item => item.roles.includes(userRole));

  return (
    <aside className={clsx(
      'flex flex-col h-screen bg-[#06101e] border-r border-[#0f2040] transition-all duration-300 flex-shrink-0',
      sidebarCollapsed ? 'w-[68px]' : 'w-[220px]'
    )}>
      {/* Logo */}
      <div className={clsx('flex items-center h-16 border-b border-[#0f2040] px-4 flex-shrink-0', sidebarCollapsed && 'justify-center px-0')}>
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#0066CC] to-[#003366] flex items-center justify-center flex-shrink-0 shadow-[0_0_16px_rgba(0,102,204,0.3)]">
          <Building2 size={16} className="text-white" />
        </div>
        {!sidebarCollapsed && (
          <div className="ml-3 overflow-hidden">
            <p className="text-sm font-bold text-white leading-tight whitespace-nowrap">Banking Intel</p>
            <p className="text-[10px] text-slate-500 whitespace-nowrap">HQ Platform</p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {visibleNavItems.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} className={({ isActive }) => clsx(
            'flex items-center gap-3 rounded-lg transition-all duration-200 text-sm font-medium group relative',
            sidebarCollapsed ? 'justify-center p-2.5' : 'px-3 py-2.5',
            isActive
              ? 'bg-[#0066CC]/15 text-[#4d9fff] border border-[#0066CC]/20'
              : 'text-slate-400 hover:bg-[#0a1a30] hover:text-slate-200'
          )}>
            <Icon size={17} className="flex-shrink-0" />
            {!sidebarCollapsed && <span className="truncate">{label}</span>}
            {/* Tooltip on collapsed */}
            {sidebarCollapsed && (
              <div className="absolute left-full ml-2 px-2 py-1 bg-[#0d1f3c] border border-[#1e3459] rounded text-xs text-white whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                {label}
              </div>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom: user + collapse */}
      <div className="border-t border-[#0f2040] p-3 space-y-2 flex-shrink-0">
        {/* Notifications */}
        <button className={clsx(
          'flex items-center gap-3 w-full rounded-lg px-3 py-2 text-slate-400 hover:bg-[#0a1a30] hover:text-slate-200 transition-all duration-200 text-sm relative',
          sidebarCollapsed && 'justify-center px-0'
        )}>
          <Bell size={16} className="flex-shrink-0" />
          {!sidebarCollapsed && <span className="flex-1 text-left">Notifications</span>}
          {unread > 0 && (
            <span className="bg-[#0066CC] text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1">
              {unread}
            </span>
          )}
        </button>

        {/* User Card */}
        {!sidebarCollapsed && user && (
          <div className="flex flex-col gap-1.5 px-3 py-2 rounded-lg bg-[#0a1628] border border-[#0f2040]">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#0066CC] to-[#003366] flex items-center justify-center flex-shrink-0 text-[11px] font-bold text-white">
                {user.name?.charAt(0).toUpperCase() ?? 'A'}
              </div>
              <div className="flex-1 overflow-hidden">
                <p className="text-xs font-medium text-slate-200 truncate">{user.name}</p>
                <p className="text-[10px] text-slate-500 truncate capitalize">{user.role}</p>
              </div>
            </div>
            <div className="flex items-center justify-between mt-1 pt-1 border-t border-[#0f2040]/50">
              <span className={clsx(
                'text-[9px] font-semibold px-1.5 py-0.5 rounded border capitalize',
                user.role === 'admin' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                user.role === 'compliance' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                user.role === 'manager' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                'bg-blue-500/10 text-blue-400 border-blue-500/20'
              )}>
                {user.role}
              </span>
              <span className="text-[9px] text-slate-650 font-mono">ID: {user.user_id.slice(0, 8)}</span>
            </div>
          </div>
        )}

        {/* Developer Monitor for Admins Only */}
        {!sidebarCollapsed && user?.role === 'admin' && (
          <NavLink
            to="/dev"
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-slate-500 hover:bg-[#0066CC]/15 hover:text-[#4d9fff] transition-all duration-200 text-xs"
          >
            <Settings size={14} className="flex-shrink-0" />
            <span className="truncate">Developer Monitor</span>
          </NavLink>
        )}

        {/* Logout */}
        <button
          onClick={handleLogout}
          className={clsx(
            'flex items-center gap-3 w-full rounded-lg px-3 py-2 text-slate-500 hover:bg-red-500/10 hover:text-red-400 transition-all duration-200 text-sm',
            sidebarCollapsed && 'justify-center px-0'
          )}
        >
          <LogOut size={16} className="flex-shrink-0" />
          {!sidebarCollapsed && 'Logout'}
        </button>

        {/* Collapse toggle */}
        <button
          onClick={toggleSidebar}
          className={clsx(
            'flex items-center gap-3 w-full rounded-lg px-3 py-2 text-slate-600 hover:bg-[#0a1a30] hover:text-slate-400 transition-all duration-200 text-sm',
            sidebarCollapsed && 'justify-center px-0'
          )}
        >
          {sidebarCollapsed ? <ChevronRight size={14} /> : <><ChevronLeft size={14} /><span className="text-xs">Collapse</span></>}
        </button>
      </div>
    </aside>
  );
}
