// src/pages/Assistant.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { bankingApi, SUGGESTED_QUERIES, getMockQueryResult } from '../api/banking';
import { useBankingQueryStore } from '../stores/bankingQueryStore';
import { useAuthStore } from '../stores/authStore';
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
}

/* ─────────────────────── helpers ─────────────────────── */
const CATEGORY_COLORS: Record<string, string> = {
  Customer:    '#3b82f6',
  Risk:        '#ef4444',
  Revenue:     '#10b981',
  Operations:  '#f59e0b',
  Compliance:  '#8b5cf6',
};

const TREND_ICON: Record<string, string> = { up: '↑', down: '↓', stable: '→' };
const TREND_COLOR: Record<string, string> = { up: '#10b981', down: '#ef4444', stable: '#64748b' };

function formatMs(ms: number) {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`;
}

function formatNumber(v: unknown): string {
  if (v == null) return '—';
  
  let numVal: number | null = null;
  if (typeof v === 'number') {
    numVal = v;
  } else if (typeof v === 'string' && v.trim() !== '') {
    // Check if it's a valid numeric string, excluding dates, hours, and IDs
    const parsed = Number(v);
    if (!isNaN(parsed) && !v.includes('-') && !v.includes(':') && !/^[A-Za-z]+_?\d+$/.test(v)) {
      numVal = parsed;
    }
  }

  if (numVal !== null) {
    if (numVal > 1_000_000) return `$${(numVal / 1_000_000).toFixed(1)}M`;
    if (numVal > 1_000)     return numVal.toLocaleString();
    return String(v); // preserve decimals if it was originally formatted
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
    const ms = (s.response as any)?.execution_time_ms ?? 0;
    return sum + (typeof ms === 'number' ? ms : 0);
  }, 0) || 1;

  return (
    <div className={`pipeline-trace${visible ? ' visible' : ''}`}>
      <div className="pipeline-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>🔬 Agent Pipeline Trace</span>
        {requestId && (
          <button
            onClick={() => navigate(`/debug?request_id=${requestId}`)}
            style={{
              fontSize: '11px', fontFamily: 'monospace', padding: '3px 10px',
              background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.3)',
              borderRadius: '6px', color: '#60a5fa', cursor: 'pointer', transition: 'all 0.2s',
            }}
            title="Open full debug dashboard"
          >
            🔍 Debug Trace →
          </button>
        )}
      </div>
      <div className="pipeline-steps">
        {steps.map((s, i) => {
          const ms = (s.response as any)?.execution_time_ms;
          const pct = ms != null ? Math.max(Math.round((ms / totalMs) * 100), 6) : 6;
          const isError = s.status === 'error';
          return (
            <div key={i} className="pipeline-step">
              <div className="pipeline-step-icon">{AGENT_ICONS[s.agent] ?? '⚡'}</div>
              <div className="pipeline-step-body">
                <div className="pipeline-step-label" style={{ color: isError ? '#f87171' : undefined }}>
                  {s.agent.replace(/_/g, ' ')}
                  {isError && <span style={{ marginLeft: 6, fontSize: 10 }}>✗ error</span>}
                </div>
                <div className="pipeline-step-bar-wrap">
                  <div
                    className="pipeline-step-bar"
                    style={{
                      width: `${pct}%`,
                      animationDelay: `${i * 80}ms`,
                      background: isError ? '#ef4444' : undefined,
                    }}
                  />
                </div>
              </div>
              <div className="pipeline-step-ms">
                {ms != null ? `${ms.toFixed(0)}ms` : '—'}
              </div>
            </div>
          );
        })}
      </div>
      {requestId && (
        <div style={{ textAlign: 'right', marginTop: 8 }}>
          <code style={{ fontSize: 10, color: '#475569', fontFamily: 'monospace' }}>
            {requestId}
          </code>
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
    <div className="assistant-chips-panel">
      <div className="assistant-chip-categories">
        {categories.map(cat => (
          <button
            key={cat}
            className={`chip-cat-btn${active === cat ? ' active' : ''}`}
            style={active === cat ? { borderColor: CATEGORY_COLORS[cat], color: CATEGORY_COLORS[cat] } : {}}
            onClick={() => setActive(cat)}
          >
            {cat}
          </button>
        ))}
      </div>
      <div className="assistant-chip-queries">
        {filtered.map(q => (
          <button
            key={q.query}
            className="chip-query-btn"
            onClick={() => onSelect(q.query)}
            title={q.query}
          >
            <span className="chip-dot" style={{ background: CATEGORY_COLORS[q.category] }} />
            {q.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function InsightsPanel({ insight }: { insight: Insight }) {
  return (
    <div className="insights-panel">
      <div className="insights-header">
        <span>💡 Executive Insights</span>
        <span className="insights-confidence">Confidence: {Math.round(insight.confidence * 100)}%</span>
      </div>

      <p className="insights-summary">{insight.summary}</p>

      {Object.keys(insight.key_metrics).length > 0 && (
        <div className="insights-metrics-grid">
          {Object.entries(insight.key_metrics).map(([k, v]) => (
            <div key={k} className="insights-metric-card">
              <div className="insights-metric-val">{v}</div>
              <div className="insights-metric-key">{k.replace(/_/g, ' ')}</div>
            </div>
          ))}
        </div>
      )}

      {insight.trends.length > 0 && (
        <div className="insights-section">
          <div className="insights-section-title">Trends</div>
          {insight.trends.map((t, i) => (
            <div key={i} className="insights-trend-row">
              <span className="trend-icon" style={{ color: TREND_COLOR[t.direction] }}>
                {TREND_ICON[t.direction]}
              </span>
              <span className="trend-label">{t.label}</span>
              <span className="trend-value" style={{ color: TREND_COLOR[t.direction] }}>{t.value}</span>
            </div>
          ))}
        </div>
      )}

      {insight.anomalies.length > 0 && (
        <div className="insights-section">
          <div className="insights-section-title">⚠️ Anomalies</div>
          {insight.anomalies.map((a, i) => (
            <div key={i} className="insights-anomaly">{a}</div>
          ))}
        </div>
      )}

      {insight.recommendations.length > 0 && (
        <div className="insights-section">
          <div className="insights-section-title">✅ Recommendations</div>
          {insight.recommendations.map((r, i) => (
            <div key={i} className="insights-rec">{r}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function ResultViewer({ result }: { result: QueryResult }) {
  const [tab, setTab] = useState<TabKey>('table');
  const rows = result.results;
  const cols = rows.length ? Object.keys(rows[0]) : [];

  // pick numeric col for chart (supporting actual numbers and numeric strings)
  const numericCols = cols.filter(c => {
    const val = rows[0]?.[c];
    if (typeof val === 'number') return true;
    if (typeof val === 'string' && val.trim() !== '') {
      const parsed = Number(val);
      return !isNaN(parsed) && !val.includes('-') && !val.includes(':') && !/^[A-Za-z]+_?\d+$/.test(val);
    }
    return false;
  });
  const labelCol = cols.find(c => typeof rows[0]?.[c] === 'string' && isNaN(Number(rows[0]?.[c]))) ?? cols[0];
  const valueCol = numericCols[0] ?? cols[1];

  const chartData = rows.slice(0, 12).map(r => ({
    name: String(r[labelCol] ?? '').slice(0, 18),
    value: Number(r[valueCol] ?? 0),
  }));

  const CHART_COLORS = ['#3b82f6','#06b6d4','#8b5cf6','#10b981','#f59e0b','#ef4444',
                        '#ec4899','#6366f1','#14b8a6','#f97316','#a855f7','#22c55e'];

  return (
    <div className="result-viewer">
      {/* meta bar */}
      <div className="result-meta-bar">
        <span className="rmb-badge rows">{result.row_count} rows</span>
        <span className="rmb-badge time">⏱ {formatMs(result.execution_time_ms)}</span>
        <span className="rmb-badge source">{result.source}</span>
        <span className="rmb-badge fresh">{result.data_freshness}</span>
        <div style={{ flex: 1 }} />
        <div className="result-tabs">
          {(['table','chart','json','csv'] as TabKey[]).map(t => (
            <button key={t} className={`rtab${tab===t?' active':''}`} onClick={() => {
              if (t === 'csv') { downloadCSV(rows, 'query_result.csv'); return; }
              setTab(t);
            }}>
              {t === 'table' ? '⊞ Table' : t === 'chart' ? '📊 Chart' : t === 'json' ? '{ } JSON' : '⬇ CSV'}
            </button>
          ))}
        </div>
      </div>

      {/* table */}
      {tab === 'table' && (
        <div className="result-table-wrap">
          <table className="result-table">
            <thead>
              <tr>{cols.map(c => <th key={c}>{c.replace(/_/g,' ')}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  {cols.map(c => <td key={c}>{formatNumber(r[c])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* chart */}
      {tab === 'chart' && (
        <div className="result-chart-wrap">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey="name"
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                angle={-35}
                textAnchor="end"
                interval={0}
              />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#0f1629', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 8 }}
                labelStyle={{ color: '#e2e8f0' }}
                itemStyle={{ color: '#60a5fa' }}
              />
              <Bar dataKey="value" radius={[4,4,0,0]}>
                {chartData.map((_, idx) => (
                  <Cell key={idx} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="chart-axis-label">
            {valueCol?.replace(/_/g,' ')} by {labelCol?.replace(/_/g,' ')}
          </div>
        </div>
      )}

      {/* json */}
      {tab === 'json' && (
        <div className="result-json-wrap">
          <pre className="result-json">{JSON.stringify(rows.slice(0, 20), null, 2)}</pre>
        </div>
      )}

      {/* insights */}
      {result.insights && <InsightsPanel insight={result.insights} />}

      {/* pipeline trace — real agent data */}
      <PipelineTrace steps={result.pipeline_steps} requestId={result.request_id} />
    </div>
  );
}

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`chat-bubble-wrap ${isUser ? 'user' : 'assistant'}`}>
      {!isUser && (
        <div className="chat-avatar assistant-avatar">🤖</div>
      )}
      <div className={`chat-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
        {msg.isLoading ? (
          <div className="typing-indicator">
            <span /><span /><span />
          </div>
        ) : (
          <>
            <p className="bubble-text">{msg.text}</p>
            {msg.result && <ResultViewer result={msg.result} />}
          </>
        )}
        <div className="bubble-time">
          {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
      {isUser && (
        <div className="chat-avatar user-avatar">👤</div>
      )}
    </div>
  );
}

function HistorySidebar({
  onSelect,
}: {
  onSelect: (q: string) => void;
}) {
  const { history, clearHistory, removeFromHistory } = useBankingQueryStore();

  if (!history.length) return (
    <div className="history-sidebar">
      <div className="history-header">Query History</div>
      <div className="history-empty">No queries yet.<br />Ask something below.</div>
    </div>
  );

  return (
    <div className="history-sidebar">
      <div className="history-header">
        <span>Query History</span>
        <button className="history-clear-btn" onClick={clearHistory}>Clear</button>
      </div>
      <div className="history-list">
        {history.map(h => (
          <div key={h.id} className="history-item" onClick={() => onSelect(h.query_text)}>
            <div className="history-item-text">{h.query_text}</div>
            <div className="history-item-meta">
              <span className={`history-status ${h.status}`}>{h.status}</span>
              <span>{h.row_count} rows</span>
              <span>{formatMs(h.execution_time_ms)}</span>
              <button className="history-del" onClick={(e) => { e.stopPropagation(); removeFromHistory(h.id); }}>×</button>
            </div>
          </div>
        ))}
      </div>
    </div>
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
  const [isMockMode, setIsMockMode] = useState(false);

  const { isQuerying, setQuerying, addToHistory } = useBankingQueryStore();
  const { user } = useAuthStore();
  const userRole = user?.role ?? 'analyst';

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 80);
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

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

    let result: QueryResult;
    let usedMock = false;

    try {
      result = await bankingApi.submitQuery(q, userRole);
    } catch {
      result = getMockQueryResult(q);
      usedMock = true;
      setIsMockMode(true);
    }

    const summary = result.insights?.summary
      ? `Found ${result.row_count} records in ${formatMs(result.execution_time_ms)}. ${result.insights.summary.slice(0, 120)}…`
      : `Query complete — ${result.row_count} records returned in ${formatMs(result.execution_time_ms)}.`;

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      text: (usedMock ? '⚠️ Preview mode (mock data). ' : '') + summary,
      timestamp: new Date(),
      result,
    };

    setMessages(prev => prev.map(m => m.isLoading ? assistantMsg : m));
    setQuerying(false);

    addToHistory({
      id: result.query_id,
      query_text: q,
      row_count: result.row_count,
      execution_time_ms: result.execution_time_ms,
      created_at: result.created_at,
      status: 'success',
    });
  }, [isQuerying, userRole, setQuerying, addToHistory]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(input);
    }
  };

  return (
    <div className="assistant-page">
      {/* ── header ── */}
      <div className="assistant-header">
        <div className="assistant-header-left">
          <div className="assistant-logo">🤖</div>
          <div>
            <h1 className="assistant-title">AI Banking Assistant</h1>
            <p className="assistant-subtitle">Natural language intelligence for banking operations</p>
          </div>
        </div>
        <div className="assistant-header-right">
          {isMockMode && (
            <span className="mock-badge">⚠️ Preview Mode</span>
          )}
          <span className="role-badge">{userRole}</span>
          <button
            className="history-toggle-btn"
            onClick={() => setShowHistory(s => !s)}
          >
            {showHistory ? '✕ History' : '🕐 History'}
          </button>
        </div>
      </div>

      {/* ── body ── */}
      <div className="assistant-body">
        {/* chat area */}
        <div className="assistant-main">
          {/* preset chips */}
          <CategoryChips onSelect={q => { setInput(q); inputRef.current?.focus(); }} />

          {/* chat messages */}
          <div className="chat-messages">
            {messages.map(msg => <ChatBubble key={msg.id} msg={msg} />)}
            <div ref={bottomRef} />
          </div>

          {/* input bar */}
          <div className="chat-input-wrap">
            <textarea
              ref={inputRef}
              className="chat-input"
              placeholder="Ask about customers, risk, revenue, compliance…  (Enter to send, Shift+Enter for newline)"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              disabled={isQuerying}
            />
            <button
              className="chat-send-btn"
              onClick={() => handleSubmit(input)}
              disabled={isQuerying || !input.trim()}
            >
              {isQuerying ? (
                <span className="send-spinner" />
              ) : (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* history sidebar */}
        {showHistory && (
          <HistorySidebar onSelect={q => { setInput(q); setShowHistory(false); inputRef.current?.focus(); }} />
        )}
      </div>
    </div>
  );
}
