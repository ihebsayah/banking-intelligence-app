// src/pages/Assistant.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import {
  Bot, User, Send, History, X, Sparkles, TrendingUp, AlertTriangle,
  CheckCircle2, Loader2, Table2, BarChart2, Braces, Download, Clock, ScanSearch,
} from 'lucide-react';
import { queryApi, SUGGESTED_QUERIES } from '../api/queryApi';
import { useBankingQueryStore } from '../stores/bankingQueryStore';
import { useAuthStore } from '../stores/authStore';
import { RoleBadge } from '../components/ui/StatusBadge';
import type { QueryResult, Insight, QueryResultRow, PipelineStep } from '../types/insights';

/* ─────────────────────── types ─────────────────────── */
type TabKey = 'table' | 'chart' | 'json' | 'csv';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: Date;
  result?: QueryResult;
  isLoading?: boolean;
  isError?: boolean;
}

interface HistoryItem {
  query_id?: string;
  query_text: string;
  row_count?: number;
  execution_time_ms?: number;
}

/* ─────────────────────── helpers ─────────────────────── */
const tint = (color: string, amount = 10) =>
  `color-mix(in srgb, ${color} ${amount}%, transparent)`;

const CATEGORY_COLORS: Record<string, string> = {
  Customer:    '#3b82f6',
  Risk:        '#ef4444',
  Revenue:     '#10b981',
  Operations:  '#f59e0b',
  Compliance:  '#8b5cf6',
};

const TREND_ICON: Record<string, React.ReactNode> = {
  up: <TrendingUp size={14} />,
  down: <TrendingUp size={14} className="rotate-180" />,
  stable: <span aria-hidden>→</span>,
};
const TREND_COLOR: Record<string, string> = { up: 'var(--accent-green)', down: 'var(--accent-red)', stable: 'var(--text-muted)' };

function formatMs(ms: number) {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`;
}

function formatNumber(v: unknown): string {
  if (v == null) return '—';

  let numVal: number | null = null;
  if (typeof v === 'number') {
    numVal = v;
  } else if (typeof v === 'string' && v.trim() !== '') {
    const parsed = Number(v);
    if (!isNaN(parsed) && !v.includes('-') && !v.includes(':') && !/^[A-Za-z]+_?\d+$/.test(v)) {
      numVal = parsed;
    }
  }

  if (numVal !== null) {
    if (numVal > 1_000_000) return `$${(numVal / 1_000_000).toFixed(1)}M`;
    if (numVal > 1_000)     return numVal.toLocaleString();
    return String(v);
  }

  return String(v);
}

function toCSV(rows: QueryResultRow[]): string {
  if (!rows.length) return '';
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(','), ...rows.map(r => headers.map(h => `"${r[h] ?? ''}"`).join(','))];
  return lines.join('\n');
}

function downloadCSV(rows: QueryResultRow[], filename = 'export.csv') {
  const blob = new Blob([toCSV(rows)], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

/* ─────────────────────── pipeline trace (real data) ─────────────────────── */
const AGENT_ICONS: Record<string, string> = {
  intent: '🧠', schema: '🗂️', entity_resolution: '🔗',
  sql: '⚙️', validation: '🛡️', compliance: '⚖️',
  execution: '🗄️', insights: '💡', audit: '📝',
};

function PipelineTrace({ steps, requestId }: { steps?: PipelineStep[]; requestId?: string }) {
  const navigate = useNavigate();
  const [visible, setVisible] = useState(false);
  useEffect(() => { const t = setTimeout(() => setVisible(true), 50); return () => clearTimeout(t); }, []);

  if (!steps || steps.length === 0) return null;

  const totalMs = steps.reduce((sum, s) => {
    const ms = (s.response as { execution_time_ms?: number })?.execution_time_ms ?? 0;
    return sum + (typeof ms === 'number' ? ms : 0);
  }, 0) || 1;

  return (
    <div className="rounded-xl border p-4 mt-3" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
      <div className="flex items-center justify-between gap-3 mb-3">
        <span className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5" style={{ color: 'var(--text-muted)' }}>
          <span aria-hidden>🔬</span> Agent Pipeline Trace
        </span>
        {requestId && (
          <button
            onClick={() => navigate(`/dev/debug?request_id=${requestId}`)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-mono border transition-colors hover:opacity-80"
            style={{ background: tint('var(--accent-blue)', 12), borderColor: tint('var(--accent-blue)', 30), color: 'var(--accent-blue)' }}
            title="Open full debug dashboard"
          >
            <ScanSearch size={12} />
            Debug Trace
          </button>
        )}
      </div>
      <div className="space-y-3">
        {steps.map((s, i) => {
          const ms = (s.response as { execution_time_ms?: number })?.execution_time_ms;
          const pct = ms != null ? Math.max(Math.round((ms / totalMs) * 100), 6) : 6;
          const isError = s.status === 'error';
          return (
            <div key={i} className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-md flex items-center justify-center text-sm flex-shrink-0"
                style={{ background: tint(isError ? 'var(--accent-red)' : 'var(--accent-blue)', 10) }}>
                <span aria-hidden>{AGENT_ICONS[s.agent] ?? '⚡'}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs font-medium truncate" style={{ color: isError ? 'var(--accent-red)' : 'var(--text-secondary)' }}>
                    {s.agent.replace(/_/g, ' ')}
                    {isError && <span className="ml-1.5 font-semibold">✗ error</span>}
                  </span>
                  <span className="text-[10px] font-mono flex-shrink-0" style={{ color: 'var(--text-subtle)' }}>
                    {ms != null ? `${ms.toFixed(0)}ms` : '—'}
                  </span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-tertiary)' }}>
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: visible ? `${pct}%` : '0%',
                      background: isError ? 'var(--accent-red)' : 'var(--accent-blue)',
                    }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {requestId && (
        <div className="text-right mt-3">
          <code className="text-[10px] font-mono" style={{ color: 'var(--text-subtle)' }}>{requestId}</code>
        </div>
      )}
    </div>
  );
}

function CategoryChips({ onSelect }: { onSelect: (q: string) => void }) {
  const categories = Array.from(new Set(SUGGESTED_QUERIES.map(q => q.category)));
  const [active, setActive] = useState<string>(categories[0]);
  const filtered = SUGGESTED_QUERIES.filter(q => q.category === active);

  return (
    <div className="border-b px-4 sm:px-6 py-3 flex-shrink-0"
      style={{ background: 'var(--bg-secondary)', borderColor: 'var(--bg-border)' }}>
      <div className="max-w-3xl mx-auto w-full">
        <div className="flex flex-wrap items-center gap-1.5 mb-2" role="group" aria-label="Suggested query categories">
          {categories.map(cat => {
            const isActive = active === cat;
            return (
              <button
                key={cat}
                aria-pressed={isActive}
                className="px-3 py-1 rounded-full text-xs font-medium border transition-colors"
                style={isActive
                  ? { borderColor: CATEGORY_COLORS[cat], color: CATEGORY_COLORS[cat], background: tint(CATEGORY_COLORS[cat], 10) }
                  : { borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}
                onClick={() => setActive(cat)}
              >
                {cat}
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {filtered.map(q => (
            <button
              key={q.query}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors hover:opacity-80"
              style={{ borderColor: tint(CATEGORY_COLORS[q.category], 35), background: tint(CATEGORY_COLORS[q.category], 6), color: 'var(--text-secondary)' }}
              onClick={() => onSelect(q.query)}
              title={q.query}
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: CATEGORY_COLORS[q.category] }} />
              {q.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function InsightsPanel({ insight, valueCol }: { insight: Insight; valueCol?: string }) {
  const isMonetary = valueCol ? [
    'balance', 'available_balance', 'amount', 'revenue', 'fee', 'limit', 'credit_limit'
  ].includes(valueCol.toLowerCase()) : false;

  const formatMetricValue = (key: string, val: string | number) => {
    if (val == null) return '—';
    const num = Number(val);
    if (isNaN(num)) return String(val);

    const keyLower = key.toLowerCase();

    if (keyLower.includes('pct') || keyLower.includes('percent') || keyLower.includes('growth') || keyLower.includes('rate') || keyLower.includes('ratio')) {
      const displayVal = num < 1.0 && num > 0 ? num * 100 : num;
      return `${displayVal.toFixed(1)}%`;
    }

    if (isMonetary && (keyLower.includes('sum') || keyLower.includes('average') || keyLower.includes('avg') || keyLower.includes('balance') || keyLower.includes('amount') || keyLower.includes('fee') || keyLower.includes('revenue') || keyLower.includes('margin'))) {
      if (num >= 1_000_000) return `$${(num / 1_000_000).toFixed(1)}M`;
      if (num >= 1_000) return `$${Math.round(num).toLocaleString()}`;
      return `$${num.toFixed(2)}`;
    }

    return num.toLocaleString();
  };

  const formatTrendValue = (label: string, val: string) => {
    const num = Number(val);
    if (isNaN(num)) return val;
    const labelLower = label.toLowerCase();
    if (labelLower.includes('pct') || labelLower.includes('percent') || labelLower.includes('growth') || labelLower.includes('rate') || labelLower.includes('ratio')) {
      const displayVal = num < 1.0 && num > 0 ? num * 100 : num;
      return `${displayVal > 0 ? '+' : ''}${displayVal.toFixed(1)}%`;
    }
    return val;
  };

  return (
    <div className="rounded-xl border p-4 mt-3" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
      <div className="flex items-center justify-between gap-3 mb-3">
        <span className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5" style={{ color: 'var(--text-muted)' }}>
          <Sparkles size={13} style={{ color: 'var(--accent-purple)' }} />
          Executive Insights
        </span>
        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border flex-shrink-0"
          style={{ background: tint('var(--accent-purple)', 10), borderColor: tint('var(--accent-purple)', 25), color: 'var(--accent-purple)' }}>
          Confidence: {Math.round(insight.confidence * 100)}%
        </span>
      </div>

      <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>{insight.summary}</p>

      {Object.keys(insight.key_metrics).length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-4">
          {Object.entries(insight.key_metrics).map(([k, v]) => (
            <div key={k} className="rounded-lg border p-3" style={{ background: 'var(--bg-secondary)', borderColor: 'var(--bg-border)' }}>
              <div className="text-base font-bold truncate" style={{ color: 'var(--text-primary)' }}>{formatMetricValue(k, v)}</div>
              <div className="text-[10px] uppercase tracking-wider mt-0.5 truncate" style={{ color: 'var(--text-muted)' }}>{k.replace(/_/g, ' ')}</div>
            </div>
          ))}
        </div>
      )}

      {insight.trends.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>Trends</div>
          <div className="space-y-1.5">
            {insight.trends.map((t, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="w-4 h-4 flex items-center justify-center" style={{ color: TREND_COLOR[t.direction] }}>
                  {TREND_ICON[t.direction]}
                </span>
                <span className="flex-1 min-w-0 truncate" style={{ color: 'var(--text-secondary)' }}>{t.label.replace(/_/g, ' ')}</span>
                <span className="font-mono text-xs flex-shrink-0" style={{ color: TREND_COLOR[t.direction] }}>
                  {formatTrendValue(t.label, t.value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {insight.anomalies.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: 'var(--accent-red)' }}>
            <AlertTriangle size={12} /> Anomalies
          </div>
          <div className="space-y-1.5">
            {insight.anomalies.map((a, i) => (
              <div key={i} className="rounded-lg border px-3 py-2 text-xs"
                style={{ background: tint('var(--accent-red)', 5), borderColor: tint('var(--accent-red)', 20), color: 'var(--text-secondary)' }}>
                {a}
              </div>
            ))}
          </div>
        </div>
      )}

      {insight.recommendations.length > 0 && (
        <div>
          <div className="text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: 'var(--accent-green)' }}>
            <CheckCircle2 size={12} /> Recommendations
          </div>
          <div className="space-y-1.5">
            {insight.recommendations.map((r, i) => (
              <div key={i} className="rounded-lg border px-3 py-2 text-xs"
                style={{ background: tint('var(--accent-green)', 5), borderColor: tint('var(--accent-green)', 20), color: 'var(--text-secondary)' }}>
                {r}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ResultViewer({ result }: { result: QueryResult }) {
  const [tab, setTab] = useState<TabKey>('table');
  const rows = result.results;
  const cols = rows.length ? Object.keys(rows[0]) : [];

  const numericCols = cols.filter(c => {
    const val = rows[0]?.[c];
    if (typeof val === 'number') return true;
    if (typeof val === 'string' && val.trim() !== '') {
      const cleaned = val.replace(/[$,]/g, '').trim();
      const parsed = Number(cleaned);
      return !isNaN(parsed) && !val.includes('-') && !val.includes(':') && !/^[A-Za-z]+_?\d+$/.test(val);
    }
    return false;
  });

  const numericPriority = [
    'balance', 'available_balance', 'amount', 'revenue', 'fee',
    'limit', 'credit_limit', 'risk_score', 'interest_rate', 'rate'
  ];
  const sortedNumericCols = [...numericCols].sort((a, b) => {
    const idxA = numericPriority.indexOf(a.toLowerCase());
    const idxB = numericPriority.indexOf(b.toLowerCase());
    const priorityA = idxA === -1 ? 999 : idxA;
    const priorityB = idxB === -1 ? 999 : idxB;
    return priorityA - priorityB;
  });
  const valueCol = sortedNumericCols[0] ?? cols[1];

  const labelPriority = [
    'name', 'label', 'title', 'branch', 'branch_name', 'region', 'city', 'segment', 'category', 'type', 'status'
  ];
  const possibleLabelCols = cols.filter(c => c !== valueCol && !c.toLowerCase().endsWith('id') && c.toLowerCase() !== 'id');
  const sortedLabelCols = [...possibleLabelCols].sort((a, b) => {
    const idxA = labelPriority.indexOf(a.toLowerCase());
    const idxB = labelPriority.indexOf(b.toLowerCase());
    const priorityA = idxA === -1 ? 999 : idxA;
    const priorityB = idxB === -1 ? 999 : idxB;
    return priorityA - priorityB;
  });
  const labelCol = sortedLabelCols[0] ?? cols.find(c => c !== valueCol) ?? cols[0];

  const chartData = rows.slice(0, 12).map(r => {
    const rawVal = r[valueCol];
    let val = 0;
    if (typeof rawVal === 'number') {
      val = rawVal;
    } else if (typeof rawVal === 'string') {
      const cleaned = rawVal.replace(/[$,]/g, '').trim();
      val = Number(cleaned);
      if (isNaN(val)) val = 0;
    }
    return {
      name: String(r[labelCol] ?? '').slice(0, 18),
      value: val,
    };
  });

  const CHART_COLORS = ['#3b82f6','#06b6d4','#8b5cf6','#10b981','#f59e0b','#ef4444',
                        '#ec4899','#6366f1','#14b8a6','#f97316','#a855f7','#22c55e'];

  const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: 'table', label: 'Table', icon: <Table2 size={12} /> },
    { key: 'chart', label: 'Chart', icon: <BarChart2 size={12} /> },
    { key: 'json', label: 'Raw', icon: <Braces size={12} /> },
    { key: 'csv', label: 'CSV', icon: <Download size={12} /> },
  ];

  return (
    <div className="rounded-xl border mt-3 overflow-hidden" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
      {/* Meta bar */}
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--bg-border)' }}>
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold border"
          style={{ background: tint('var(--accent-blue)', 10), borderColor: tint('var(--accent-blue)', 25), color: 'var(--accent-blue)' }}>
          {result.row_count} rows
        </span>
        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono border"
          style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
          <Clock size={10} /> {formatMs(result.execution_time_ms)}
        </span>
        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border"
          style={{ background: tint('var(--accent-green)', 10), borderColor: tint('var(--accent-green)', 25), color: 'var(--accent-green)' }}>
          {result.source}
        </span>
        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border"
          style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
          {result.data_freshness}
        </span>
        <div className="flex-1" />
        <div role="tablist" aria-label="Result view" className="flex items-center gap-1 flex-wrap">
          {TABS.map(t => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors"
              style={tab === t.key
                ? { background: tint('var(--accent-blue)', 12), color: 'var(--accent-blue)', borderColor: tint('var(--accent-blue)', 30) }
                : { color: 'var(--text-muted)', borderColor: 'var(--bg-border)' }}
              onClick={() => {
                if (t.key === 'csv') { downloadCSV(rows, 'query_result.csv'); return; }
                setTab(t.key);
              }}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'table' && (
        <div role="tabpanel" className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse min-w-full">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--bg-border)' }}>
                {cols.map(c => (
                  <th key={c} className="px-3 py-2.5 font-semibold uppercase tracking-wider whitespace-nowrap" style={{ color: 'var(--text-muted)' }}>
                    {c.replace(/_/g,' ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b transition-colors" style={{ borderColor: 'var(--bg-border)' }}>
                  {cols.map(c => (
                    <td key={c} className="px-3 py-2.5 whitespace-nowrap font-mono" style={{ color: 'var(--text-secondary)' }}>
                      {formatNumber(r[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'chart' && (
        <div role="tabpanel" className="px-3 py-2">
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                <XAxis
                  dataKey="name"
                  tick={{ fill: 'var(--text-subtle)', fontSize: 11 }}
                  angle={-35}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis tick={{ fill: 'var(--text-subtle)', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--bg-border)', borderRadius: 8 }}
                  labelStyle={{ color: 'var(--text-primary)' }}
                  itemStyle={{ color: 'var(--accent-blue)' }}
                />
                <Bar dataKey="value" radius={[4,4,0,0]}>
                  {chartData.map((_, idx) => (
                    <Cell key={idx} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="text-center text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
            {valueCol?.replace(/_/g,' ')} by {labelCol?.replace(/_/g,' ')}
          </div>
        </div>
      )}

      {tab === 'json' && (
        <div role="tabpanel" className="p-3 overflow-x-auto">
          <pre className="rounded-lg p-3 text-[11px] font-mono overflow-x-auto" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
            {JSON.stringify(rows.slice(0, 20), null, 2)}
          </pre>
        </div>
      )}

      {result.insights && <InsightsPanel insight={result.insights} valueCol={valueCol} />}
      <PipelineTrace steps={result.pipeline_steps} requestId={result.request_id} />
    </div>
  );
}

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';

  const bubbleStyle = msg.isError
    ? { background: tint('var(--accent-red)', 8), borderColor: tint('var(--accent-red)', 25), color: 'var(--accent-red)' }
    : isUser
      ? { background: 'var(--accent-blue)', color: '#ffffff', borderColor: 'transparent' }
      : { background: 'var(--bg-card)', color: 'var(--text-secondary)', borderColor: 'var(--bg-border)' };

  return (
    <div className={`flex gap-2.5 ${isUser ? 'justify-end' : ''}`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
          style={{ background: tint('var(--accent-blue)', 10) }}>
          <Bot size={14} style={{ color: 'var(--accent-blue)' }} />
        </div>
      )}
      <div className={`flex flex-col max-w-[85%] sm:max-w-[75%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`rounded-xl px-3.5 py-2.5 text-sm leading-relaxed border break-words ${msg.isLoading ? '' : ''}`} style={bubbleStyle}>
          {msg.isLoading ? (
            <div role="status" aria-label="Assistant is typing" className="flex gap-1 py-1">
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--text-subtle)' }} />
              <span className="w-1.5 h-1.5 rounded-full animate-pulse [animation-delay:0.2s]" style={{ background: 'var(--text-subtle)' }} />
              <span className="w-1.5 h-1.5 rounded-full animate-pulse [animation-delay:0.4s]" style={{ background: 'var(--text-subtle)' }} />
            </div>
          ) : (
            <>
              {msg.text && <p>{msg.text}</p>}
              {msg.result && <ResultViewer result={msg.result} />}
            </>
          )}
        </div>
        <div className="text-[10px] mt-1 px-1" style={{ color: 'var(--text-subtle)' }}>
          {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
      {isUser && (
        <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
          style={{ background: 'var(--bg-tertiary)' }}>
          <User size={14} style={{ color: 'var(--text-muted)' }} />
        </div>
      )}
    </div>
  );
}

function HistorySidebar({
  onSelect,
  onClose,
  history,
  historyAvailable,
}: {
  onSelect: (q: string) => void;
  onClose: () => void;
  history: HistoryItem[];
  historyAvailable: boolean;
}) {
  return (
    <aside
      className="fixed inset-y-0 right-0 z-40 w-80 max-w-[85vw] border-l shadow-2xl flex flex-col lg:static lg:z-auto lg:w-64 lg:shadow-none lg:flex-shrink-0"
      style={{ background: 'var(--bg-secondary)', borderColor: 'var(--bg-border)' }}
      aria-label="Query history"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b flex-shrink-0" style={{ borderColor: 'var(--bg-border)' }}>
        <span className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5" style={{ color: 'var(--text-muted)' }}>
          <History size={12} /> Query History
        </span>
        <button onClick={onClose} className="p-1.5 rounded-lg transition-colors lg:hidden" aria-label="Close history"
          style={{ color: 'var(--text-muted)' }}>
          <X size={15} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {!historyAvailable ? (
          <div className="p-4 text-xs italic" style={{ color: 'var(--text-subtle)' }}>
            History service not available (GET /queries/history)
          </div>
        ) : !history.length ? (
          <div className="p-4 text-xs text-center" style={{ color: 'var(--text-muted)' }}>
            No queries yet.
            <br />Ask something below.
          </div>
        ) : (
          <div className="space-y-1">
            {history.map((h, idx) => (
              <button
                key={h.query_id ?? idx}
                className="w-full text-left px-3 py-2 rounded-lg transition-colors hover:opacity-90"
                style={{ background: 'var(--bg-card)' }}
                onClick={() => onSelect(h.query_text)}
              >
                <div className="text-xs truncate" style={{ color: 'var(--text-primary)' }}>{h.query_text}</div>
                <div className="flex items-center gap-2 mt-1 text-[10px]" style={{ color: 'var(--text-subtle)' }}>
                  <span className="px-1.5 py-px rounded-full font-medium"
                    style={{ background: tint('var(--accent-green)', 10), color: 'var(--accent-green)' }}>success</span>
                  {h.row_count !== undefined && <span>{h.row_count} rows</span>}
                  {h.execution_time_ms !== undefined && <span>{h.execution_time_ms}ms</span>}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

/* ─────────────────────── main page ─────────────────────── */
export function Assistant() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Hello! I\'m your Banking Intelligence Assistant. Ask me anything about customers, risk, revenue, or compliance — in plain English.',
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [showHistory, setShowHistory] = useState(false);

  const [backendHistory, setBackendHistory] = useState<HistoryItem[]>([]);
  const [historyAvailable, setHistoryAvailable] = useState(true);

  const { isQuerying, setQuerying } = useBankingQueryStore();
  const { user } = useAuthStore();
  const userRole = user?.role ?? 'analyst';

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 80);
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const hist = await queryApi.getHistory();
      setBackendHistory(hist);
      setHistoryAvailable(true);
    } catch (err) {
      console.warn('Backend history API not available.', err);
      setHistoryAvailable(false);
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleSubmit = useCallback(async (queryText: string) => {
    const q = queryText.trim();
    if (!q || isQuerying) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      text: q,
      timestamp: new Date(),
    };
    const loadingMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      text: '',
      timestamp: new Date(),
      isLoading: true,
    };

    setMessages(prev => [...prev, userMsg, loadingMsg]);
    setInput('');
    setQuerying(true);

    try {
      const result = await queryApi.submitQuery(q, userRole);

      // Clarification flow: backend couldn't resolve the query (e.g. unknown branch)
      if (result.requires_clarification && result.clarification) {
        const clarMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          text: `🔍 ${result.clarification.message}`,
          timestamp: new Date(),
          isError: false,
        };
        setMessages(prev => prev.map(m => m.isLoading ? clarMsg : m));
        return;
      }

      const summary = result.insights?.summary
        ? `Found ${result.row_count} records in ${formatMs(result.execution_time_ms)}. ${result.insights.summary.slice(0, 120)}…`
        : `Query complete — ${result.row_count} records returned in ${formatMs(result.execution_time_ms)}.`;

      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        text: summary,
        timestamp: new Date(),
        result,
      };

      setMessages(prev => prev.map(m => m.isLoading ? assistantMsg : m));

      // Refresh history after a successful query
      fetchHistory();
    } catch (err: unknown) {
      console.error('Query execution failed:', err);
      const apiError = err as { response?: { data?: { detail?: string } }; message?: string };
      const errMsg = apiError.response?.data?.detail ?? apiError.message ?? 'An error occurred while executing the query.';
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        text: `❌ Error executing query: ${errMsg}`,
        timestamp: new Date(),
        isError: true,
      };
      setMessages(prev => prev.map(m => m.isLoading ? errorMsg : m));
    } finally {
      setQuerying(false);
    }
  }, [isQuerying, userRole, setQuerying, fetchHistory]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(input);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col animate-fade-in" style={{ background: 'var(--bg-primary)' }}>
      {/* ── header ── */}
      <div className="flex items-center justify-between gap-4 px-6 py-4 border-b flex-shrink-0 flex-wrap"
        style={{ borderColor: 'var(--bg-border)', background: 'var(--bg-primary)' }}>
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ background: tint('var(--accent-blue)', 10) }}>
            <Bot size={18} style={{ color: 'var(--accent-blue)' }} />
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>AI Banking Assistant</h1>
            <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--text-muted)' }}>
              Natural language intelligence for banking operations
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <RoleBadge role={userRole} />
          <button
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border transition-colors"
            style={{ color: 'var(--text-secondary)', borderColor: 'var(--bg-border)' }}
            onClick={() => setShowHistory(s => !s)}
            aria-pressed={showHistory}
          >
            {showHistory ? <X size={12} /> : <History size={12} />}
            {showHistory ? 'Close History' : 'History'}
          </button>
        </div>
      </div>

      {/* ── body ── */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* chat area */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* preset chips */}
          <CategoryChips onSelect={q => { setInput(q); inputRef.current?.focus(); }} />

          {/* chat messages */}
          <div
            data-testid="chat-messages"
            aria-live="polite"
            aria-label="Conversation transcript"
            className="flex-1 overflow-y-auto px-4 py-6 sm:px-6"
          >
            <div className="max-w-3xl mx-auto w-full space-y-4">
              {messages.map(msg => <ChatBubble key={msg.id} msg={msg} />)}
              <div ref={bottomRef} />
            </div>
          </div>

          {/* input bar */}
          <div data-testid="chat-input" className="border-t px-4 py-3 sm:px-6 flex-shrink-0"
            style={{ borderColor: 'var(--bg-border)', background: 'var(--bg-primary)' }}>
            <div className="max-w-3xl mx-auto w-full">
              <div className="flex items-end gap-2 rounded-xl border px-3 py-2"
                style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
                <label htmlFor="assistant-input" className="sr-only">Ask a question about your banking data</label>
                <textarea
                  id="assistant-input"
                  ref={inputRef}
                  className="flex-1 bg-transparent text-sm outline-none resize-none min-h-[36px] max-h-40"
                  placeholder="Ask about customers, risk, revenue, compliance…  (Enter to send, Shift+Enter for newline)"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={2}
                  disabled={isQuerying}
                  style={{ color: 'var(--text-primary)' }}
                />
                <button
                  className="p-2 rounded-lg transition-colors disabled:opacity-30 flex-shrink-0"
                  style={{ color: 'var(--accent-blue)' }}
                  disabled={isQuerying || !input.trim()}
                  onClick={() => handleSubmit(input)}
                  aria-label="Send message"
                >
                  {isQuerying ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* history sidebar */}
        {showHistory && (
          <HistorySidebar
            onSelect={q => { setInput(q); setShowHistory(false); inputRef.current?.focus(); }}
            onClose={() => setShowHistory(false)}
            history={backendHistory}
            historyAvailable={historyAvailable}
          />
        )}
      </div>
    </div>
  );
}
