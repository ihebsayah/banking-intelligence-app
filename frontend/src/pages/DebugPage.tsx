import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DebugDashboard } from '../components/debugging/DebugDashboard';

export function DebugPage() {
  const [searchParams] = useSearchParams();
  const [requestId, setRequestId] = useState(searchParams.get('request_id') || '');
  const [inputValue, setInputValue] = useState(requestId);

  useEffect(() => {
    const id = searchParams.get('request_id');
    if (id) {
      setRequestId(id);
      setInputValue(id);
    }
  }, [searchParams]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setRequestId(inputValue.trim());
  };

  return (
    <div className="min-h-screen bg-[#040711]">
      {/* Request ID Selector bar */}
      <div className="bg-[#070b1e] border-b border-[#131a35] px-6 py-4">
        <div className="max-w-4xl">
          <p className="text-xs text-slate-500 font-mono mb-2 uppercase tracking-widest">
            Agent Debug Session
          </p>
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Paste request_id here (e.g. req-1a2b3c4d)..."
              className="flex-1 px-4 py-2.5 bg-[#090d22] border border-[#1e293b] rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500/60 font-mono text-sm transition-all"
            />
            <button
              type="submit"
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm rounded-lg transition-all shrink-0"
            >
              Inspect
            </button>
          </form>
          {!requestId && (
            <p className="text-xs text-slate-600 font-mono mt-2">
              Execute a query through the API to get a request_id, then paste it above.
              The response payload includes <code className="text-emerald-600">request_id</code> and{' '}
              <code className="text-emerald-600">debug_url</code>.
            </p>
          )}
        </div>
      </div>

      {/* Main Dashboard */}
      {requestId ? (
        <DebugDashboard requestId={requestId} />
      ) : (
        <DebugWelcome />
      )}
    </div>
  );
}

function DebugWelcome() {
  const agents = [
    { name: 'Intent Agent', port: 8002, color: '#3b82f6' },
    { name: 'Schema Agent', port: 8003, color: '#10b981' },
    { name: 'Entity Resolution', port: 8004, color: '#8b5cf6' },
    { name: 'SQL Agent', port: 8005, color: '#f59e0b' },
    { name: 'Validation Agent', port: 8006, color: '#06b6d4' },
    { name: 'Execution Agent', port: 8007, color: '#ec4899' },
    { name: 'Audit Agent', port: 8008, color: '#64748b' },
    { name: 'Insights Agent', port: 8010, color: '#84cc16' },
    { name: 'Compliance Agent', port: 8011, color: '#f97316' },
  ];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="text-center py-16">
        <div className="text-7xl mb-4">🔍</div>
        <h2 className="text-2xl font-extrabold text-slate-100 mb-2">Agent Debugging Dashboard</h2>
        <p className="text-slate-500 text-sm font-mono max-w-lg mx-auto">
          Complete visibility into every agent call in your banking intelligence pipeline.
          Enter a request ID above to start inspecting.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 mt-4">
        <div className="bg-[#090d22] border border-[#131a35] rounded-xl p-6">
          <h3 className="text-sm font-bold text-slate-300 mb-4 uppercase tracking-widest">Monitored Pipeline</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {agents.map((agent) => (
              <div
                key={agent.port}
                className="flex items-center gap-3 p-3 bg-[#040711] rounded-lg border border-[#0f172a] hover:border-[#1e293b] transition-all"
              >
                <div
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: agent.color, boxShadow: `0 0 8px ${agent.color}55` }}
                />
                <div>
                  <p className="text-xs font-bold text-slate-300">{agent.name}</p>
                  <p className="text-[10px] text-slate-600 font-mono">:{agent.port}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-[#090d22] border border-[#131a35] rounded-xl p-6">
          <h3 className="text-sm font-bold text-slate-300 mb-4 uppercase tracking-widest">How to Use</h3>
          <ol className="space-y-3 text-xs font-mono text-slate-400">
            <li className="flex gap-3">
              <span className="shrink-0 w-5 h-5 rounded-full bg-blue-600/20 text-blue-400 flex items-center justify-center font-bold text-[10px]">1</span>
              <span>Run a query via <code className="text-emerald-400 bg-emerald-950/30 px-1 rounded">POST /api/query</code> on the main gateway (port 8000)</span>
            </li>
            <li className="flex gap-3">
              <span className="shrink-0 w-5 h-5 rounded-full bg-blue-600/20 text-blue-400 flex items-center justify-center font-bold text-[10px]">2</span>
              <span>Copy the <code className="text-emerald-400 bg-emerald-950/30 px-1 rounded">request_id</code> from the response payload</span>
            </li>
            <li className="flex gap-3">
              <span className="shrink-0 w-5 h-5 rounded-full bg-blue-600/20 text-blue-400 flex items-center justify-center font-bold text-[10px]">3</span>
              <span>Paste it above and click <strong className="text-slate-300">Inspect</strong></span>
            </li>
            <li className="flex gap-3">
              <span className="shrink-0 w-5 h-5 rounded-full bg-blue-600/20 text-blue-400 flex items-center justify-center font-bold text-[10px]">4</span>
              <span>Explore Timeline, Logs, Performance, and Live stream tabs</span>
            </li>
          </ol>
        </div>
      </div>
    </div>
  );
}
