// src/components/PerformanceChart/index.tsx
import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from 'recharts';
import { useQueryStore } from '../../stores/queryStore';
import { PIPELINE_STEP_META } from '../../types/query';
import type { PipelineStepName } from '../../types/query';

const COLORS: Record<string, string> = {
  intent:            '#3b82f6',
  schema:            '#8b5cf6',
  entity_resolution: '#06b6d4',
  sql:               '#10b981',
  validation:        '#f59e0b',
  execution:         '#ef4444',
};

const CustomTooltip = ({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) => {
  if (active && payload?.length) {
    return (
      <div className="glass-card-static px-3 py-2">
        <p className="text-xs text-slate-400">{label}</p>
        <p className="text-sm font-semibold text-slate-200">{payload[0].value}ms</p>
      </div>
    );
  }
  return null;
};

export function PerformanceChart() {
  const { activeResult } = useQueryStore();

  const steps = activeResult?.pipelineSteps ?? [];
  const data  = steps
    .filter((s) => s.durationMs != null && s.status === 'success')
    .map((s) => ({
      name:      PIPELINE_STEP_META[s.name as PipelineStepName]?.displayName ?? s.displayName,
      key:       s.name,
      duration:  s.durationMs!,
    }));

  const total = data.reduce((sum, d) => sum + d.duration, 0);
  const meta  = activeResult?.metadata;

  if (!data.length) {
    return (
      <div className="glass-card p-5 flex flex-col items-center justify-center py-10 gap-2">
        <p className="text-sm text-slate-500">No timing data — run a query first</p>
      </div>
    );
  }

  return (
    <div className="glass-card p-5 flex flex-col gap-4">
      <div className="section-header">
        <span>Performance Breakdown</span>
        <span className="ml-auto text-xs text-slate-500">
          Pipeline: {meta?.totalPipelineTimeMs ?? total}ms
        </span>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} barCategoryGap="30%">
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: '#6b7280', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#6b7280', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            unit="ms"
            width={40}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Bar dataKey="duration" radius={[4, 4, 0, 0]}>
            {data.map((entry) => (
              <Cell key={entry.key} fill={COLORS[entry.key] ?? '#6b7280'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-bg-tertiary rounded-lg p-3 border border-bg-border">
          <p className="text-xs text-slate-500">Total Pipeline</p>
          <p className="text-base font-bold text-slate-200 mt-0.5">{meta?.totalPipelineTimeMs ?? total}ms</p>
        </div>
        <div className="bg-bg-tertiary rounded-lg p-3 border border-bg-border">
          <p className="text-xs text-slate-500">Slowest Step</p>
          <p className="text-base font-bold text-amber-400 mt-0.5">
            {data.sort((a, b) => b.duration - a.duration)[0]?.duration}ms
          </p>
        </div>
        <div className="bg-bg-tertiary rounded-lg p-3 border border-bg-border">
          <p className="text-xs text-slate-500">Cached</p>
          <p className={`text-base font-bold mt-0.5 ${meta?.cached ? 'text-emerald-400' : 'text-slate-400'}`}>
            {meta?.cached ? '✓ Yes' : '✗ No'}
          </p>
        </div>
      </div>

      {/* Per-step bar */}
      {data.map((d) => {
        const pct = Math.round((d.duration / total) * 100);
        return (
          <div key={d.key} className="flex items-center gap-3">
            <div className="w-24 text-right text-xs text-slate-500 truncate">{d.name}</div>
            <div className="flex-1 h-2 bg-bg-tertiary rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, background: COLORS[d.key] ?? '#6b7280' }}
              />
            </div>
            <div className="w-14 text-xs font-mono text-slate-400">{d.duration}ms</div>
            <div className="w-8 text-xs text-slate-600">{pct}%</div>
          </div>
        );
      })}
    </div>
  );
}
