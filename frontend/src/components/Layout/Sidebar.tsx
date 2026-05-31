// src/components/Layout/Sidebar.tsx
import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, FlaskConical, Activity, Gauge, Settings,
  Cpu, Wifi, WifiOff, Shield, Bug
} from 'lucide-react';
import { useAgentStore } from '../../stores/agentStore';
import { useQueryStore } from '../../stores/queryStore';

const NAV_ITEMS = [
  { to: '/dev',         icon: LayoutDashboard, label: 'Dashboard'   },
  { to: '/dev/query',   icon: FlaskConical,    label: 'Query Tester' },
  { to: '/dev/agents',  icon: Activity,        label: 'Agent Monitor' },
  { to: '/dev/performance', icon: Gauge,       label: 'Performance'  },
  { to: '/dev/debug',   icon: Bug,             label: 'Debugger'     },
  { to: '/dev/settings',icon: Settings,        label: 'Settings'     },
];


export function Sidebar() {
  const location       = useLocation();
  const wsConnected    = useAgentStore((s) => s.wsConnected);
  const agentHealth    = useAgentStore((s) => s.agentHealth);
  const queryStatus    = useQueryStore((s) => s.status);

  const healthList   = Object.values(agentHealth);
  const healthyCount = healthList.filter((a) => a.status === 'healthy').length;
  const downCount    = healthList.filter((a) => a.status === 'down').length;
  const totalAgents  = 9;

  return (
    <aside className="flex flex-col w-56 flex-shrink-0 bg-bg-secondary border-r border-bg-border h-screen sticky top-0">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-bg-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
            <Shield size={16} className="text-blue-400" />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-100 leading-tight">BankingAI</p>
            <p className="text-[10px] text-slate-500">Dev Dashboard</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => {
          const active = to === '/dev'
            ? location.pathname === '/dev' || location.pathname === '/dev/'
            : location.pathname.startsWith(to);
          return (
            <NavLink
              key={to}
              to={to}
              className={active ? 'nav-item-active block' : 'nav-item-inactive block'}
            >
              <Icon size={16} />
              <span>{label}</span>
            </NavLink>
          );
        })}

        {/* Business Portal Toggle */}
        <div className="pt-4 mt-4 border-t border-bg-border">
          <NavLink
            to="/dashboard"
            className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-slate-400 hover:bg-bg-hover hover:text-slate-200 transition-all text-xs font-semibold"
          >
            <LayoutDashboard size={14} className="text-blue-400" />
            <span>Business Portal</span>
          </NavLink>
        </div>
      </nav>

      {/* Status footer */}
      <div className="px-3 pb-4 space-y-2">
        {/* Agent health pill */}
        <div className="bg-bg-tertiary rounded-lg px-3 py-2 border border-bg-border">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5">
              <Cpu size={12} className="text-slate-500" />
              <span className="text-xs text-slate-500">Agents</span>
            </div>
            <span className="text-xs font-semibold text-slate-300">{healthyCount}/{totalAgents}</span>
          </div>
          <div className="h-1.5 bg-bg-border rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                downCount > 3 ? 'bg-red-500' : downCount > 0 ? 'bg-amber-500' : 'bg-emerald-500'
              }`}
              style={{ width: healthList.length ? `${(healthyCount / totalAgents) * 100}%` : '0%' }}
            />
          </div>
        </div>

        {/* WS status */}
        <div className="flex items-center gap-2 px-2 py-1">
          {wsConnected
            ? <><Wifi size={12} className="text-emerald-400" /><span className="text-xs text-emerald-400">WebSocket Live</span></>
            : <><WifiOff size={12} className="text-slate-500" /><span className="text-xs text-slate-500">WebSocket Off</span></>
          }
        </div>

        {/* Pipeline status */}
        {queryStatus === 'running' && (
          <div className="flex items-center gap-2 px-2 py-1 bg-blue-600/10 rounded border border-blue-500/20">
            <span className="spinner" style={{ width: 10, height: 10 }} />
            <span className="text-xs text-blue-400">Pipeline running...</span>
          </div>
        )}
      </div>
    </aside>
  );
}
