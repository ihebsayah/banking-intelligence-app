import React, { useState, useEffect } from 'react';
import { AgentTimeline } from './AgentTimeline';
import { LogViewer } from './LogViewer';
import { PerformanceMetrics } from './PerformanceMetrics';
import { LiveStream } from './LiveStream';
import './DebugDashboard.css';

interface DebugDashboardProps {
  requestId: string;
}

export const DebugDashboard: React.FC<DebugDashboardProps> = ({ requestId }) => {
  const [activeTab, setActiveTab] = useState<'timeline' | 'logs' | 'metrics' | 'stream'>('timeline');
  const [logs, setLogs] = useState<any[]>([]);
  const [statistics, setStatistics] = useState<any>(null);
  const [isLive, setIsLive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const fetchData = async () => {
    if (!requestId || requestId === 'none') return;
    setLoading(true);
    setError(null);
    try {
      const [logsRes, statsRes] = await Promise.all([
        fetch(`http://localhost:8099/debug/logs/${requestId}`),
        fetch(`http://localhost:8099/debug/statistics/${requestId}`)
      ]);

      if (!logsRes.ok || !statsRes.ok) throw new Error('Failed to fetch debug data');

      const logsData = await logsRes.json();
      const statsData = await statsRes.json();

      setLogs(logsData.logs || []);
      setStatistics(statsData);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err.message || 'Unable to reach debug service');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [requestId]);

  // Auto-refresh in live mode
  useEffect(() => {
    if (!isLive) return;
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, [isLive, requestId]);

  type TabKey = 'timeline' | 'logs' | 'metrics' | 'stream';

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'timeline', label: '⏱ Timeline' },
    { key: 'logs', label: '📋 Logs' },
    { key: 'metrics', label: '📊 Performance' },
    ...(isLive ? [{ key: 'stream' as TabKey, label: '🔴 Live Stream' }] : []),
  ];

  return (
    <div className="debug-dashboard">
      {/* Header */}
      <header className="debug-header">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1>🔍 Agent Communication Debugger</h1>
            <div className="request-info mt-2">
              <code>Request ID: {requestId}</code>
              {lastRefreshed && (
                <span className="text-slate-500 text-xs font-mono">
                  Last updated: {lastRefreshed.toLocaleTimeString()}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={fetchData}
              disabled={loading}
              className="px-4 py-2 bg-blue-600/15 hover:bg-blue-600/25 border border-blue-600/30 text-blue-400 rounded-lg text-xs font-bold transition-all"
            >
              {loading ? '↻ Refreshing...' : '↻ Refresh'}
            </button>
            <label className="live-stream-toggle">
              <input
                type="checkbox"
                checked={isLive}
                onChange={(e) => {
                  setIsLive(e.target.checked);
                  if (e.target.checked) setActiveTab('stream');
                }}
              />
              <span className={`text-xs font-bold ${isLive ? 'text-rose-400' : 'text-slate-500'}`}>
                {isLive ? '🔴 LIVE' : 'Live Mode'}
              </span>
            </label>
          </div>
        </div>

        {/* Agent Pipeline Summary Pills */}
        {logs.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {logs.map((log, idx) => (
              <div
                key={idx}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border transition-all ${
                  log.error
                    ? 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                    : 'bg-emerald-500/8 border-emerald-500/15 text-emerald-400'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${log.error ? 'bg-rose-500' : 'bg-emerald-500'}`}></span>
                {log.agent_name}
                <span className="text-slate-500">·</span>
                <span className="font-bold">{log.duration_ms?.toFixed(0)}ms</span>
              </div>
            ))}
          </div>
        )}
      </header>

      {/* Error banner */}
      {error && (
        <div className="mx-6 mt-4 p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-lg text-sm font-mono">
          ⚠ {error} — Check that the debug service is running on port 8099.
        </div>
      )}

      {/* Tabs */}
      <nav className="debug-tabs">
        {tabs.map(tab => (
          <button
            key={tab.key}
            className={`tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Content */}
      <main className="debug-content">
        {activeTab === 'timeline' && (
          logs.length > 0
            ? <AgentTimeline logs={logs} />
            : <EmptyState loading={loading} message="No agent execution data for this request yet." />
        )}
        {activeTab === 'logs' && (
          logs.length > 0
            ? <LogViewer logs={logs} />
            : <EmptyState loading={loading} message="No logs found for this request." />
        )}
        {activeTab === 'metrics' && statistics && statistics.total_agents > 0 && (
          <PerformanceMetrics stats={statistics} />
        )}
        {activeTab === 'metrics' && (!statistics || statistics.total_agents === 0) && (
          <EmptyState loading={loading} message="No performance metrics available yet." />
        )}
        {activeTab === 'stream' && isLive && (
          <LiveStream requestId={requestId} />
        )}
      </main>
    </div>
  );
};

function EmptyState({ loading, message }: { loading: boolean; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-32 gap-4 text-slate-500">
      {loading ? (
        <>
          <div className="w-8 h-8 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin"></div>
          <span className="text-sm font-mono">Fetching debug data...</span>
        </>
      ) : (
        <>
          <span className="text-5xl opacity-30">🔍</span>
          <span className="text-sm font-mono text-center max-w-sm">{message}</span>
          <span className="text-xs text-slate-600 font-mono">Run a query through the API to populate trace data.</span>
        </>
      )}
    </div>
  );
}
