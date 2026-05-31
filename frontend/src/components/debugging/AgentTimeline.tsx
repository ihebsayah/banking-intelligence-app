import React from 'react';

interface Log {
  sequence: number;
  agent_name: string;
  phase: string;
  duration_ms: number;
  confidence: number;
  error: string | null;
}

interface AgentTimelineProps {
  logs: Log[];
}

export const AgentTimeline: React.FC<AgentTimelineProps> = ({ logs }) => {
  const maxDuration = Math.max(...logs.map(l => l.duration_ms), 1);
  const totalDuration = logs.reduce((sum, l) => sum + l.duration_ms, 0);

  return (
    <div className="agent-timeline">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-slate-100">Agent Execution Timeline</h2>
        <div className="flex gap-4">
          <div className="px-4 py-2 bg-slate-900 border border-slate-800 rounded-lg">
            <span className="text-xs text-slate-500 block">Total Time</span>
            <strong className="text-sm text-blue-400 font-mono">{totalDuration.toFixed(2)}ms</strong>
          </div>
          <div className="px-4 py-2 bg-slate-900 border border-slate-800 rounded-lg">
            <span className="text-xs text-slate-500 block">Executed Agents</span>
            <strong className="text-sm text-blue-400 font-mono">{logs.length} / 9</strong>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {logs.map((log, idx) => {
          const percentage = (log.duration_ms / maxDuration) * 100;
          const statusClass = log.error ? 'error' : 'success';

          return (
            <div key={idx} className="timeline-item group">
              <div className="flex justify-between items-center mb-1.5 text-xs">
                <div className="flex items-center gap-2">
                  <span className={`status-indicator ${statusClass}`}></span>
                  <span className="font-bold text-slate-200">{log.agent_name}</span>
                  <span className="px-1.5 py-0.5 bg-slate-800 text-slate-400 rounded text-[10px] uppercase font-mono">
                    {log.phase}
                  </span>
                </div>
                <div className="text-slate-400 font-mono">
                  {log.duration_ms.toFixed(2)}ms
                </div>
              </div>
              
              <div className="timeline-bar-container">
                <div 
                  className={`timeline-bar ${statusClass}`}
                  style={{ width: `${Math.max(percentage, 5)}%` }}
                >
                  <span className="confidence pr-2">
                    {(log.confidence * 100).toFixed(0)}% Conf
                  </span>
                </div>
              </div>
              
              {log.error && (
                <div className="mt-1 text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2 py-1 rounded font-mono">
                  {log.error}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex gap-4 mt-6 pt-4 border-t border-slate-800 text-xs">
        <div className="flex items-center gap-2 text-slate-400">
          <span className="status-indicator success"></span>
          <span>Successful Agent</span>
        </div>
        <div className="flex items-center gap-2 text-slate-400">
          <span className="status-indicator error"></span>
          <span>Failed Agent</span>
        </div>
      </div>
    </div>
  );
};
