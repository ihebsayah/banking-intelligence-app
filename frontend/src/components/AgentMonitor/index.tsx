// src/components/AgentMonitor/index.tsx
import React, { useRef, useEffect } from 'react';
import { RefreshCw, Wifi, WifiOff, Filter, Search, Trash2 } from 'lucide-react';
import { useAgentMonitoring } from '../../hooks/useAgentMonitoring';
import { useAgentStore } from '../../stores/agentStore';
import { AGENT_REGISTRY } from '../../types/agent';
import type { AgentHealth, AgentLogEntry } from '../../types/agent';
import { format } from 'date-fns';

function StatusBadge({ status }: { status: AgentHealth['status'] }) {
  const map = {
    healthy: { cls: 'badge-green',  dot: 'status-dot-green',  label: 'Healthy' },
    slow:    { cls: 'badge-yellow', dot: 'status-dot-yellow', label: 'Slow'    },
    down:    { cls: 'badge-red',    dot: 'status-dot-red',    label: 'Down'    },
    unknown: { cls: 'badge-gray',   dot: 'status-dot-gray',   label: 'Unknown' },
  };
  const s = map[status] ?? map.unknown;
  return (
    <span className={s.cls + ' badge'}>
      <span className={s.dot} />
      {s.label}
    </span>
  );
}

function AgentCard({ agent }: { agent: AgentHealth }) {
  const info      = AGENT_REGISTRY.find((a) => a.name === agent.name);
  const cardClass = agent.status === 'healthy' ? 'agent-card-healthy'
                  : agent.status === 'slow'    ? 'agent-card-slow'
                  : agent.status === 'down'    ? 'agent-card-down'
                  : 'agent-card-unknown';

  return (
    <div className={cardClass}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className="text-sm font-semibold text-slate-200">{info?.displayName ?? agent.name}</p>
          <p className="text-xs text-slate-500">:{agent.port}</p>
        </div>
        <StatusBadge status={agent.status} />
      </div>
      <p className="text-xs text-slate-600 mb-3">{info?.description}</p>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <p className="text-xs text-slate-600">Response</p>
          <p className={`text-sm font-bold ${
            agent.status === 'down'    ? 'text-slate-600'
            : agent.responseTimeMs < 100 ? 'text-emerald-400'
            : agent.responseTimeMs < 500 ? 'text-amber-400'
            : 'text-red-400'
          }`}>
            {agent.status === 'down' ? '—' : `${agent.responseTimeMs}ms`}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-600">Last Check</p>
          <p className="text-xs text-slate-400 font-mono">
            {agent.lastCheck ? format(new Date(agent.lastCheck), 'HH:mm:ss') : '—'}
          </p>
        </div>
      </div>
      {agent.status !== 'down' && (
        <div className="mt-2 h-1 bg-bg-border rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              agent.status === 'healthy' ? 'bg-emerald-500' : 'bg-amber-500'
            }`}
            style={{ width: `${Math.min(100, agent.responseTimeMs / 5)}%` }}
          />
        </div>
      )}
    </div>
  );
}

function LogLine({ entry }: { entry: AgentLogEntry }) {
  const info = AGENT_REGISTRY.find((a) => a.name === entry.agentName);
  const dirIcon = entry.direction === 'request' ? '←' : entry.direction === 'response' ? '→' : '✗';
  const dirColor = entry.direction === 'request' ? 'text-blue-400'
                 : entry.direction === 'response' ? 'text-emerald-400'
                 : 'text-red-400';

  const ts = (() => {
    try { return format(new Date(entry.timestamp), 'HH:mm:ss.SSS'); }
    catch { return entry.timestamp; }
  })();

  const preview = (() => {
    if (!entry.data) return '';
    const s = typeof entry.data === 'string' ? entry.data : JSON.stringify(entry.data);
    return s.slice(0, 120) + (s.length > 120 ? '…' : '');
  })();

  return (
    <div className="log-entry group">
      <span className="text-slate-600 font-mono text-[10px] w-24 flex-shrink-0">{ts}</span>
      <span className="flex-shrink-0" style={{ color: info?.color ?? '#6b7280', fontSize: 10, width: 110 }}>
        {info?.displayName ?? entry.agentName}
      </span>
      <span className={`${dirColor} flex-shrink-0 font-bold w-4`}>{dirIcon}</span>
      {entry.durationMs != null && (
        <span className="text-slate-600 flex-shrink-0 w-12">{entry.durationMs}ms</span>
      )}
      <span className="text-slate-400 font-mono overflow-hidden text-ellipsis whitespace-nowrap min-w-0">
        {preview}
      </span>
    </div>
  );
}

export function AgentMonitorPanel() {
  const { agentHealth, communicationLogs, wsConnected, refreshHealth } = useAgentMonitoring();
  const { setLogFilter, setLogSearch, clearLogs, logFilter, logSearch } = useAgentStore();
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [communicationLogs.length]);

  const healthy = agentHealth.filter((a) => a.status === 'healthy').length;
  const slow    = agentHealth.filter((a) => a.status === 'slow').length;
  const down    = agentHealth.filter((a) => a.status === 'down').length;

  return (
    <div className="flex flex-col gap-5">
      {/* Health header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="status-dot-green" />
            <span className="text-xs text-slate-400">{healthy} Healthy</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="status-dot-yellow" />
            <span className="text-xs text-slate-400">{slow} Slow</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="status-dot-red" />
            <span className="text-xs text-slate-400">{down} Down</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            {wsConnected
              ? <><Wifi size={14} className="text-emerald-400" /><span className="text-xs text-emerald-400">WS Live</span></>
              : <><WifiOff size={14} className="text-slate-500" /><span className="text-xs text-slate-500">WS Off</span></>
            }
          </div>
          <button onClick={refreshHealth} className="btn-ghost text-xs px-2 py-1">
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* Agent health grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {agentHealth.length === 0
          ? Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="agent-card">
                <div className="shimmer h-4 w-24 mb-2 rounded" />
                <div className="shimmer h-3 w-16 mb-3 rounded" />
                <div className="shimmer h-8 rounded" />
              </div>
            ))
          : agentHealth.map((a) => <AgentCard key={a.name} agent={a} />)
        }
      </div>

      {/* Communication log */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="section-header mb-0">
            <span>Agent Communication Log</span>
            <span className="ml-2 badge-gray">{communicationLogs.length}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                className="input pl-6 py-1 text-xs w-40"
                placeholder="Search logs..."
                value={logSearch}
                onChange={(e) => setLogSearch(e.target.value)}
              />
            </div>
            <select
              className="select py-1 text-xs w-36"
              value={logFilter}
              onChange={(e) => setLogFilter(e.target.value)}
            >
              <option value="all">All Agents</option>
              {AGENT_REGISTRY.map((a) => (
                <option key={a.name} value={a.name}>{a.displayName}</option>
              ))}
            </select>
            <button onClick={clearLogs} className="btn-ghost text-xs px-2 py-1">
              <Trash2 size={12} /> Clear
            </button>
          </div>
        </div>
        <div className="bg-bg-primary rounded-lg border border-bg-border h-72 overflow-y-auto py-2 font-mono">
          {communicationLogs.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-xs text-slate-600">No logs yet — run a query to see agent communication</p>
            </div>
          ) : (
            <>
              {communicationLogs.map((entry) => (
                <LogLine key={entry.id} entry={entry} />
              ))}
              <div ref={logEndRef} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
