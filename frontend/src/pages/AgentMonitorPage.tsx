// src/pages/AgentMonitorPage.tsx
import React from 'react';
import { AgentMonitorPanel } from '../components/AgentMonitor';
import { useAgentMonitoring } from '../hooks/useAgentMonitoring';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

// Fake sparkline data for demonstration (replace with real stats endpoint)
function generateSparkline(base: number) {
  return Array.from({ length: 20 }, (_, i) => ({
    t:  i,
    ms: Math.max(0, base + (Math.random() - 0.5) * base * 0.5),
  }));
}

export function AgentMonitorPage() {
  const { agentHealth, systemMetrics } = useAgentMonitoring();

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* System metrics row */}
      {systemMetrics && (
        <div className="grid grid-cols-2 xl:grid-cols-5 gap-4">
          {[
            { label: 'Queries Processed', value: systemMetrics.totalQueriesProcessed.toLocaleString(), color: 'text-blue-400' },
            { label: 'Avg Pipeline Time',  value: `${systemMetrics.avgPipelineTimeMs}ms`, color: 'text-amber-400' },
            { label: 'Cache Hit Rate',     value: `${Math.round(systemMetrics.cacheHitRate * 100)}%`, color: 'text-cyan-400' },
            { label: 'Error Rate',         value: `${(systemMetrics.errorRate * 100).toFixed(1)}%`, color: 'text-red-400' },
            { label: 'Uptime',             value: systemMetrics.uptime, color: 'text-emerald-400' },
          ].map(({ label, value, color }) => (
            <div key={label} className="glass-card p-4">
              <p className="text-xs text-slate-500 mb-1">{label}</p>
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Per-agent sparklines */}
      <div className="glass-card p-5">
        <div className="section-header mb-4">Response Time Trends (Simulated)</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {agentHealth.map((agent) => {
            const sparkData = generateSparkline(agent.responseTimeMs || 100);
            const color = agent.status === 'healthy' ? '#10b981'
                        : agent.status === 'slow'    ? '#f59e0b'
                        : '#ef4444';
            return (
              <div key={agent.name} className="bg-bg-tertiary rounded-lg p-3 border border-bg-border">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-semibold text-slate-300 capitalize">{agent.name.replace('_', ' ')}</p>
                  <span className="text-xs font-mono" style={{ color }}>
                    {agent.status === 'down' ? 'DOWN' : `${agent.responseTimeMs}ms`}
                  </span>
                </div>
                <ResponsiveContainer width="100%" height={50}>
                  <AreaChart data={sparkData}>
                    <defs>
                      <linearGradient id={`grad-${agent.name}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={color} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={color} stopOpacity={0}   />
                      </linearGradient>
                    </defs>
                    <Area
                      type="monotone"
                      dataKey="ms"
                      stroke={color}
                      strokeWidth={1.5}
                      fill={`url(#grad-${agent.name})`}
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            );
          })}
        </div>
      </div>

      {/* Full agent monitor panel */}
      <AgentMonitorPanel />
    </div>
  );
}
