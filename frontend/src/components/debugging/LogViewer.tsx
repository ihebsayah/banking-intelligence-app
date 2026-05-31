import React, { useState, useMemo } from 'react';

interface LogViewerProps {
  logs: any[];
}

export const LogViewer: React.FC<LogViewerProps> = ({ logs }) => {
  const [filter, setFilter] = useState('');
  const [expandedLog, setExpandedLog] = useState<number | null>(null);

  const filtered = useMemo(() => {
    return logs.filter(log => 
      log.agent_name.toLowerCase().includes(filter.toLowerCase()) ||
      log.phase.toLowerCase().includes(filter.toLowerCase()) ||
      (log.error && log.error.toLowerCase().includes(filter.toLowerCase()))
    );
  }, [logs, filter]);

  return (
    <div className="log-viewer">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-bold text-slate-100">Raw Logs Explorer</h2>
        <span className="px-2 py-1 bg-slate-800 text-slate-300 font-mono text-xs rounded border border-slate-700">
          Showing {filtered.length} / {logs.length} entries
        </span>
      </div>
      
      <div className="log-filter mb-4">
        <input
          type="text"
          placeholder="Filter logs by agent name, phase, payload contents..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono text-sm transition-all"
        />
      </div>

      <div className="log-list space-y-3">
        {filtered.map((log, idx) => {
          const isExpanded = expandedLog === idx;
          return (
            <div 
              key={idx} 
              className={`log-entry border rounded-lg transition-all overflow-hidden ${
                log.error 
                  ? 'border-rose-500/20 bg-rose-500/5 hover:bg-rose-500/10' 
                  : 'border-slate-850 bg-slate-900/40 hover:bg-slate-900/60'
              }`}
            >
              <div 
                className="log-header p-4 flex items-center justify-between cursor-pointer select-none"
                onClick={() => setExpandedLog(isExpanded ? null : idx)}
              >
                <div className="flex items-center gap-4 flex-wrap">
                  <span className="sequence font-mono text-xs text-slate-500">#{log.sequence}</span>
                  <span className="font-bold text-slate-200 text-sm">{log.agent_name}</span>
                  <span className="phase text-[10px] uppercase font-mono px-2 py-0.5 bg-slate-800 text-slate-400 rounded">
                    {log.phase}
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  <span className="duration font-mono text-xs text-amber-400 font-semibold">
                    {log.duration_ms.toFixed(1)}ms
                  </span>
                  {log.cache_hit && (
                    <span className="cache-badge text-[10px] uppercase font-mono px-2 py-0.5 bg-cyan-500/10 text-cyan-400 rounded border border-cyan-500/20 font-bold">
                      CACHE HIT
                    </span>
                  )}
                  {log.error ? (
                    <span className="error-badge text-[10px] uppercase font-mono px-2 py-0.5 bg-rose-500/15 text-rose-400 rounded border border-rose-500/30 font-bold animate-pulse">
                      ERROR
                    </span>
                  ) : (
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded border border-emerald-500/20 font-bold">
                      SUCCESS
                    </span>
                  )}
                  <span className="text-slate-500 text-xs transition-transform duration-200">
                    {isExpanded ? '▼' : '▶'}
                  </span>
                </div>
              </div>

              {isExpanded && (
                <div className="log-details p-4 bg-slate-950/80 border-t border-slate-900 space-y-4 font-mono text-xs">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <h4 className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                        Input Parameters
                      </h4>
                      <pre className="p-3 bg-slate-900 border border-slate-800 rounded-lg overflow-auto max-h-60 text-slate-300">
                        {JSON.stringify(log.input, null, 2)}
                      </pre>
                    </div>
                    
                    <div className="space-y-1">
                      <h4 className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                        Output Response
                      </h4>
                      <pre className="p-3 bg-slate-900 border border-slate-800 rounded-lg overflow-auto max-h-60 text-slate-300">
                        {JSON.stringify(log.output, null, 2)}
                      </pre>
                    </div>
                  </div>

                  {log.error && (
                    <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-lg space-y-1">
                      <h4 className="font-semibold uppercase tracking-wider text-[10px]">
                        Error Stacktrace
                      </h4>
                      <pre className="overflow-auto max-h-40 text-slate-300">
                        {log.error}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
