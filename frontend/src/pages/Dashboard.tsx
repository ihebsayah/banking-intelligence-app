// src/pages/Dashboard.tsx
import React from 'react';
import {
  Activity, Cpu, Zap, TrendingUp, Clock, CheckCircle, XCircle,
  BarChart2, History, ArrowRight
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAgentMonitoring } from '../hooks/useAgentMonitoring';
import { useQueryStore } from '../stores/queryStore';
import { AGENT_REGISTRY } from '../types/agent';
import { format } from 'date-fns';

function MetricCard({ icon: Icon, label, value, sub, color = 'blue' }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string; color?: string;
}) {
  const colorMap: Record<string, string> = {
    blue:   'text-blue-400 bg-blue-500/10 border-blue-500/20',
    green:  'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    yellow: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    red:    'text-red-400 bg-red-500/10 border-red-500/20',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
    cyan:   'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
  };
  const cls = colorMap[color] ?? colorMap.blue;

  return (
    <div className="glass-card p-5 flex items-center gap-4">
      <div className={`w-10 h-10 rounded-xl border flex items-center justify-center flex-shrink-0 ${cls}`}>
        <Icon size={18} />
      </div>
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className="text-xl font-bold text-slate-100">{value}</p>
        {sub && <p className="text-xs text-slate-600 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

export function Dashboard() {
  const { agentHealth, systemMetrics } = useAgentMonitoring();
  const { history } = useQueryStore();

  const healthy = agentHealth.filter((a) => a.status === 'healthy').length;
  const slow    = agentHealth.filter((a) => a.status === 'slow').length;
  const down    = agentHealth.filter((a) => a.status === 'down').length;

  const recentSuccess = history.filter((h) => h.status === 'success').length;
  const recentError   = history.filter((h) => h.status === 'error').length;

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Hero */}
      <div className="glass-card p-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-600/10 to-purple-600/5 pointer-events-none" />
        <div className="relative">
          <div className="flex items-center gap-2 mb-1">
            <span className="badge-blue">v0.5 · Week 5 MVP</span>
            <span className="badge-green">System Active</span>
          </div>
          <h2 className="text-2xl font-bold text-slate-100 mb-1">
            Banking Intelligence System
          </h2>
          <p className="text-sm text-slate-400 max-w-xl">
            9-agent NL→SQL pipeline · Developer monitoring dashboard · Real-time agent communication
          </p>
          <div className="flex gap-3 mt-4">
            <Link to="/query" className="btn-primary">
              <Zap size={14} /> Run Query
            </Link>
            <Link to="/agents" className="btn-secondary">
              <Activity size={14} /> Monitor Agents
            </Link>
          </div>
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard icon={Cpu}       label="Healthy Agents"  value={`${healthy}/9`}  sub={`${slow} slow · ${down} down`}     color="green"  />
        <MetricCard icon={Zap}       label="Queries Run"     value={history.length}  sub="this session"                       color="blue"   />
        <MetricCard icon={CheckCircle} label="Successes"     value={recentSuccess}   sub={`${recentError} errors`}            color="green"  />
        <MetricCard icon={TrendingUp} label="Cache Hit Rate" value={systemMetrics ? `${Math.round(systemMetrics.cacheHitRate * 100)}%` : '—'} sub="across all queries" color="purple" />
      </div>

      {/* Agent status grid + recent queries */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Agent status */}
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="section-header mb-0">
              <Cpu size={16} className="text-blue-400" />
              <span>Agent Status</span>
            </div>
            <Link to="/agents" className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
              View all <ArrowRight size={11} />
            </Link>
          </div>
          <div className="space-y-2">
            {AGENT_REGISTRY.map((info) => {
              const health = agentHealth.find((h) => h.name === info.name);
              const status = health?.status ?? 'unknown';
              const ms     = health?.responseTimeMs;
              return (
                <div key={info.name} className="flex items-center gap-3 py-1.5 px-2 hover:bg-bg-hover rounded-lg transition-colors">
                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: info.color }} />
                  <span className="text-sm text-slate-300 flex-1">{info.displayName}</span>
                  <span className="text-xs text-slate-500 font-mono">:{info.port}</span>
                  {ms != null && status !== 'down' && (
                    <span className={`text-xs font-mono ${ms < 100 ? 'text-emerald-400' : ms < 500 ? 'text-amber-400' : 'text-red-400'}`}>
                      {ms}ms
                    </span>
                  )}
                  <span className={`badge text-[10px] ${
                    status === 'healthy' ? 'badge-green'
                    : status === 'slow'  ? 'badge-yellow'
                    : status === 'down'  ? 'badge-red'
                    : 'badge-gray'
                  }`}>
                    <span className={
                      status === 'healthy' ? 'status-dot-green'
                      : status === 'slow'  ? 'status-dot-yellow'
                      : status === 'down'  ? 'status-dot-red'
                      : 'status-dot-gray'
                    } />
                    {status}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent queries */}
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="section-header mb-0">
              <History size={16} className="text-blue-400" />
              <span>Recent Queries</span>
            </div>
            <Link to="/query" className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
              New query <ArrowRight size={11} />
            </Link>
          </div>
          {history.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 gap-2">
              <BarChart2 size={28} className="text-slate-700" />
              <p className="text-sm text-slate-500">No queries yet this session</p>
              <Link to="/query" className="btn-primary text-xs mt-2">Run your first query</Link>
            </div>
          ) : (
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {history.slice(0, 10).map((h) => (
                <div key={h.id} className="flex items-start gap-3 py-2 px-2 hover:bg-bg-hover rounded-lg transition-colors">
                  {h.status === 'success'
                    ? <CheckCircle size={14} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                    : <XCircle    size={14} className="text-red-400 mt-0.5 flex-shrink-0" />
                  }
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-slate-300 truncate">{h.query}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[10px] text-slate-600">
                        {h.completedAt ? format(new Date(h.completedAt), 'HH:mm:ss') : ''}
                      </span>
                      {h.metadata?.rowsReturned != null && (
                        <span className="text-[10px] text-slate-600">{h.metadata.rowsReturned} rows</span>
                      )}
                      {h.metadata?.executionTimeMs && (
                        <span className="text-[10px] text-slate-600">{h.metadata.executionTimeMs}ms</span>
                      )}
                    </div>
                  </div>
                  <span className={`badge text-[10px] flex-shrink-0 ${h.format === 'json' ? 'badge-blue' : h.format === 'csv' ? 'badge-cyan' : 'badge-purple'}`}>
                    {h.format}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
