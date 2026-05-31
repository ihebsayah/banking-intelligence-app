import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

interface PerformanceMetricsProps {
  stats: any;
}

export const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({ stats }) => {
  const colors = [
    '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899',
    '#14b8a6', '#f97316', '#06b6d4', '#84cc16', '#ef4444'
  ];

  const breakdownData = stats.agent_breakdown || [];

  return (
    <div className="performance-metrics">
      <h2 className="text-xl font-bold text-slate-100 mb-6">System Performance Breakdown</h2>

      <div className="metrics-grid">
        <div className="metric-card">
          <h3>Total Pipeline Duration</h3>
          <div className="metric-value text-blue-400 font-mono">
            {stats.total_time_ms.toFixed(1)}ms
          </div>
        </div>

        <div className="metric-card">
          <h3>Agents Contacted</h3>
          <div className="metric-value text-emerald-400 font-mono">
            {stats.total_agents}
          </div>
        </div>

        <div className="metric-card">
          <h3>Cache Hits</h3>
          <div className="metric-value text-cyan-400 font-mono">
            {stats.cache_hits}
          </div>
        </div>

        <div className="metric-card">
          <h3>Encountered Errors</h3>
          <div className={`metric-value font-mono ${stats.error_count > 0 ? 'text-rose-500 animate-pulse' : 'text-slate-500'}`}>
            {stats.error_count}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 flex flex-col justify-center items-center h-[360px]">
          <h3 className="text-sm font-bold text-slate-400 mb-4 self-start">Time Share per Agent</h3>
          {breakdownData.length > 0 ? (
            <ResponsiveContainer width="100%" height="90%">
              <PieChart>
                <Pie
                  data={breakdownData}
                  dataKey="time_ms"
                  nameKey="agent"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  innerRadius={60}
                  paddingAngle={4}
                  label={({ agent, percentage }) => `${agent} (${percentage.toFixed(0)}%)`}
                  labelLine={false}
                >
                  {breakdownData.map((_: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={colors[index % colors.length]} stroke="#0f172a" strokeWidth={2} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }}
                  itemStyle={{ color: '#e2e8f0' }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-sm text-slate-500 font-mono">No timing data available</div>
          )}
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 overflow-hidden flex flex-col justify-between">
          <h3 className="text-sm font-bold text-slate-400 mb-4">Detailed Timings Table</h3>
          <div className="overflow-x-auto flex-1">
            <table className="breakdown-table w-full text-left border-collapse text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500">
                  <th className="pb-3 pr-2">Agent Target</th>
                  <th className="pb-3 pr-2 text-right">Timing (ms)</th>
                  <th className="pb-3 pr-2 text-right">Percentage</th>
                  <th className="pb-3 text-right">Confidence Level</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50 text-slate-300">
                {breakdownData.map((item: any, idx: number) => (
                  <tr key={idx} className="hover:bg-slate-950/40">
                    <td className="py-2.5 flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colors[idx % colors.length] }}></span>
                      <span className="font-semibold text-slate-200">{item.agent}</span>
                    </td>
                    <td className="py-2.5 text-right font-mono text-slate-300">{item.time_ms.toFixed(1)}ms</td>
                    <td className="py-2.5 text-right font-mono text-blue-400 font-semibold">{item.percentage.toFixed(1)}%</td>
                    <td className="py-2.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <span className="font-mono text-slate-400">{(item.confidence * 100).toFixed(0)}%</span>
                        <div className="confidence-bar w-16">
                          <div 
                            className="confidence-fill"
                            style={{ width: `${item.confidence * 100}%` }}
                          ></div>
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
