// src/pages/PerformanceMonitor.tsx
import React, { useState } from 'react';
import { Play, BarChart2, Loader } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from 'recharts';
import { submitQuery } from '../api/queries';
import { testSQLSafety } from '../api/agents';
import { PRESET_QUERIES } from '../types/query';
import type { PerformanceTestResult } from '../types/results';

function SQLDebugger() {
  const [sql, setSql] = useState('SELECT c.customer_id, c.name, a.balance\nFROM customers c\nJOIN accounts a ON c.customer_id = a.customer_id\nWHERE a.balance > 10000\nORDER BY a.balance DESC\nLIMIT 10;');
  const [result, setResult] = useState<Awaited<ReturnType<typeof testSQLSafety>> | null>(null);
  const [testing, setTesting] = useState(false);

  const test = async () => {
    setTesting(true);
    const r = await testSQLSafety(sql);
    setResult(r);
    setTesting(false);
  };

  return (
    <div className="glass-card p-5">
      <div className="section-header mb-4">SQL Safety Debugger</div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="flex flex-col gap-3">
          <label className="label">SQL Query</label>
          <textarea
            className="textarea h-48"
            value={sql}
            onChange={(e) => setSql(e.target.value)}
          />
          <button onClick={test} disabled={testing} className="btn-primary">
            {testing ? <><span className="spinner" /> Testing...</> : <><Play size={14} /> Test SQL Safety</>}
          </button>
        </div>
        {result && (
          <div className="flex flex-col gap-3 animate-fade-in">
            <div className="grid grid-cols-2 gap-3">
              <div className={`rounded-lg p-3 border ${result.valid ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
                <p className="text-xs text-slate-500">Syntax Valid</p>
                <p className={`text-base font-bold ${result.valid ? 'text-emerald-400' : 'text-red-400'}`}>
                  {result.valid ? '✓ Valid' : '✗ Invalid'}
                </p>
              </div>
              <div className={`rounded-lg p-3 border ${result.safe ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
                <p className="text-xs text-slate-500">Safety Check</p>
                <p className={`text-base font-bold ${result.safe ? 'text-emerald-400' : 'text-red-400'}`}>
                  {result.safe ? '✓ Safe' : '✗ Unsafe'}
                </p>
              </div>
            </div>
            {result.issues.length > 0 && (
              <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
                <p className="text-xs font-semibold text-red-400 mb-2">Issues Found</p>
                {result.issues.map((issue, i) => (
                  <p key={i} className="text-xs text-red-300 font-mono">• {issue}</p>
                ))}
              </div>
            )}
            {result.safe && (
              <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3">
                <p className="text-xs text-emerald-400">✓ Query passed all safety checks</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function LoadTester() {
  const [concurrent, setConcurrent] = useState(5);
  const [selectedQuery, setSelectedQuery] = useState(PRESET_QUERIES[0].query);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PerformanceTestResult | null>(null);
  const [progress, setProgress] = useState(0);

  const run = async () => {
    setRunning(true);
    setResult(null);
    setProgress(0);

    const results: PerformanceTestResult['results'] = [];
    let completed = 0;

    const tasks = Array.from({ length: concurrent }, async (_, i) => {
      const start = Date.now();
      try {
        const r = await submitQuery({ query: selectedQuery, format: 'json' });
        const ms = Date.now() - start;
        results.push({ queryIndex: i, durationMs: ms, status: r.status === 'success' ? 'success' : 'error', cached: r.metadata?.cached ?? false });
      } catch {
        results.push({ queryIndex: i, durationMs: Date.now() - start, status: 'error', cached: false });
      }
      completed++;
      setProgress(Math.round((completed / concurrent) * 100));
    });

    await Promise.all(tasks);

    const sorted   = results.map((r) => r.durationMs).sort((a, b) => a - b);
    const p95Idx   = Math.floor(sorted.length * 0.95);
    const cached   = results.filter((r) => r.cached).length;
    const success  = results.filter((r) => r.status === 'success').length;

    setResult({
      concurrentQueries:  concurrent,
      totalTimeMs:        Math.max(...results.map((r) => r.durationMs)),
      avgResponseTimeMs:  Math.round(sorted.reduce((a, b) => a + b, 0) / sorted.length),
      minResponseTimeMs:  sorted[0],
      maxResponseTimeMs:  sorted[sorted.length - 1],
      p95ResponseTimeMs:  sorted[p95Idx] ?? sorted[sorted.length - 1],
      successCount:       success,
      errorCount:         concurrent - success,
      cacheHitRate:       cached / concurrent,
      results,
    });
    setRunning(false);
  };

  return (
    <div className="glass-card p-5">
      <div className="section-header mb-4">
        <BarChart2 size={16} className="text-blue-400" />
        Load Tester — Concurrent Queries
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Config */}
        <div className="flex flex-col gap-4">
          <div>
            <label className="label">Query</label>
            <select className="select" value={selectedQuery} onChange={(e) => setSelectedQuery(e.target.value)}>
              {PRESET_QUERIES.map((p) => (
                <option key={p.id} value={p.query}>{p.category} – {p.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Concurrent Users: {concurrent}</label>
            <input
              type="range"
              min={1} max={20} step={1}
              value={concurrent}
              onChange={(e) => setConcurrent(+e.target.value)}
              className="w-full accent-blue-500"
            />
            <div className="flex justify-between text-xs text-slate-600 mt-1"><span>1</span><span>20</span></div>
          </div>
          <button onClick={run} disabled={running} className="btn-primary">
            {running
              ? <><Loader size={14} className="animate-spin" /> Running {concurrent} queries... {progress}%</>
              : <><Play size={14} /> Run Load Test</>
            }
          </button>
          {running && (
            <div className="h-2 bg-bg-border rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 transition-all duration-300 rounded-full" style={{ width: `${progress}%` }} />
            </div>
          )}
        </div>

        {/* Results */}
        {result && (
          <div className="flex flex-col gap-3 animate-fade-in">
            <div className="grid grid-cols-2 gap-2">
              {[
                { l: 'Concurrent',  v: result.concurrentQueries },
                { l: 'Avg Time',    v: `${result.avgResponseTimeMs}ms` },
                { l: 'P95 Time',    v: `${result.p95ResponseTimeMs}ms` },
                { l: 'Min Time',    v: `${result.minResponseTimeMs}ms` },
                { l: 'Max Time',    v: `${result.maxResponseTimeMs}ms` },
                { l: 'Success',     v: `${result.successCount}/${result.concurrentQueries}` },
                { l: 'Cache Hit',   v: `${Math.round(result.cacheHitRate * 100)}%` },
                { l: 'Error Rate',  v: `${((result.errorCount / result.concurrentQueries) * 100).toFixed(0)}%` },
              ].map(({ l, v }) => (
                <div key={l} className="bg-bg-tertiary rounded p-2 border border-bg-border">
                  <p className="text-[10px] text-slate-500">{l}</p>
                  <p className="text-sm font-bold text-slate-200 font-mono">{String(v)}</p>
                </div>
              ))}
            </div>
            {/* Timeline chart */}
            <ResponsiveContainer width="100%" height={100}>
              <LineChart data={result.results.sort((a, b) => a.queryIndex - b.queryIndex)}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="queryIndex" tick={{ fontSize: 9, fill: '#6b7280' }} />
                <YAxis tick={{ fontSize: 9, fill: '#6b7280' }} unit="ms" width={40} />
                <Tooltip contentStyle={{ background: '#151b2e', border: '1px solid #1e2640', fontSize: 10 }} />
                <Line type="monotone" dataKey="durationMs" stroke="#3b82f6" dot={{ r: 2 }} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

export function PerformanceMonitor() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <SQLDebugger />
      <LoadTester />
    </div>
  );
}
