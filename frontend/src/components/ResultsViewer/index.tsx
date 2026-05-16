// src/components/ResultsViewer/index.tsx
import React, { useState, useMemo } from 'react';
import { Download, Copy, Table, FileJson, FileText, Info, ChevronUp, ChevronDown } from 'lucide-react';
import { useQueryStore } from '../../stores/queryStore';
import type { TabId, SortConfig } from '../../types/results';

function jsonToCsv(data: unknown[]): string {
  if (!data?.length) return '';
  const keys = Object.keys(data[0] as Record<string, unknown>);
  const header = keys.join(',');
  const rows = data.map((row) =>
    keys.map((k) => {
      const v = (row as Record<string, unknown>)[k];
      const s = v === null || v === undefined ? '' : String(v);
      return s.includes(',') || s.includes('"') || s.includes('\n')
        ? `"${s.replace(/"/g, '""')}"`
        : s;
    }).join(',')
  );
  return [header, ...rows].join('\n');
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  });
}

function downloadFile(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

interface TableViewProps { data: unknown[] }
function TableView({ data }: TableViewProps) {
  const [sort, setSort] = useState<SortConfig | null>(null);
  const [filterText, setFilterText] = useState('');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;

  const columns = useMemo(() => {
    if (!data?.length) return [];
    return Object.keys(data[0] as Record<string, unknown>);
  }, [data]);

  const filtered = useMemo(() => {
    if (!filterText) return data;
    const f = filterText.toLowerCase();
    return data.filter((row) =>
      Object.values(row as Record<string, unknown>).some((v) => String(v ?? '').toLowerCase().includes(f))
    );
  }, [data, filterText]);

  const sorted = useMemo(() => {
    if (!sort) return filtered;
    return [...filtered].sort((a, b) => {
      const av = (a as Record<string, unknown>)[sort.key];
      const bv = (b as Record<string, unknown>)[sort.key];
      const cmp = String(av ?? '') < String(bv ?? '') ? -1 : String(av ?? '') > String(bv ?? '') ? 1 : 0;
      return sort.direction === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sort]);

  const pages      = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const pageData   = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const toggleSort = (col: string) => {
    if (sort?.key === col) {
      setSort(sort.direction === 'asc' ? { key: col, direction: 'desc' } : null);
    } else {
      setSort({ key: col, direction: 'asc' });
    }
    setPage(0);
  };

  if (!data?.length) return <p className="text-slate-500 text-sm text-center py-8">No data</p>;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <input
          className="input max-w-xs text-xs"
          placeholder="Filter rows..."
          value={filterText}
          onChange={(e) => { setFilterText(e.target.value); setPage(0); }}
        />
        <span className="text-xs text-slate-500 ml-auto">
          {filtered.length} / {data.length} rows
        </span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-bg-border">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>
                  <button
                    onClick={() => toggleSort(col)}
                    className="flex items-center gap-1 hover:text-slate-200 transition-colors"
                  >
                    {col}
                    {sort?.key === col ? (
                      sort.direction === 'asc' ? <ChevronUp size={10} /> : <ChevronDown size={10} />
                    ) : null}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageData.map((row, i) => (
              <tr key={i}>
                {columns.map((col) => {
                  const v = (row as Record<string, unknown>)[col];
                  const display = v === null || v === undefined ? <span className="text-slate-600">—</span>
                                : typeof v === 'boolean' ? <span className={v ? 'text-emerald-400' : 'text-red-400'}>{String(v)}</span>
                                : <span>{String(v)}</span>;
                  return <td key={col}>{display}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center gap-2 justify-center">
          <button className="btn-ghost text-xs px-2 py-1" onClick={() => setPage(0)} disabled={page === 0}>«</button>
          <button className="btn-ghost text-xs px-2 py-1" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>‹</button>
          <span className="text-xs text-slate-500">{page + 1} / {pages}</span>
          <button className="btn-ghost text-xs px-2 py-1" onClick={() => setPage(p => Math.min(pages - 1, p + 1))} disabled={page >= pages - 1}>›</button>
          <button className="btn-ghost text-xs px-2 py-1" onClick={() => setPage(pages - 1)} disabled={page >= pages - 1}>»</button>
        </div>
      )}
    </div>
  );
}

export function ResultsViewer() {
  const { activeResult, status } = useQueryStore();
  const [activeTab, setActiveTab] = useState<TabId>('table');
  const [copied, setCopied] = useState(false);

  const data = activeResult?.results ?? [];
  const meta = activeResult?.metadata;

  if (status === 'idle') {
    return (
      <div className="glass-card p-5 flex flex-col items-center justify-center py-16 gap-3">
        <Table size={32} className="text-slate-700" />
        <p className="text-sm text-slate-500">Results appear here after running a query</p>
      </div>
    );
  }

  if (status === 'running') {
    return (
      <div className="glass-card p-5 flex flex-col items-center justify-center py-16 gap-3">
        <span className="spinner" style={{ width: 28, height: 28, borderWidth: 3 }} />
        <p className="text-sm text-slate-400 animate-pulse">Executing pipeline...</p>
      </div>
    );
  }

  if (activeResult?.status === 'error') {
    return (
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-3">
          <span className="status-dot-red" />
          <span className="text-sm font-semibold text-red-400">Query Error</span>
        </div>
        <div className="code-block text-red-300">{activeResult.error}</div>
      </div>
    );
  }

  const jsonStr = JSON.stringify(data, null, 2);
  const csvStr  = jsonToCsv(data);

  const handleCopy = (content: string) => {
    copyToClipboard(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const tabs = [
    { id: 'table' as TabId, label: 'Table',    icon: <Table size={13} /> },
    { id: 'json'  as TabId, label: 'JSON',     icon: <FileJson size={13} /> },
    { id: 'csv'   as TabId, label: 'CSV',      icon: <FileText size={13} /> },
    { id: 'metadata' as TabId, label: 'Metadata', icon: <Info size={13} /> },
  ];

  return (
    <div className="glass-card p-5 flex flex-col gap-4">
      {/* Tabs + actions */}
      <div className="flex items-center justify-between border-b border-bg-border -mx-5 px-5 pb-0">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={activeTab === tab.id ? 'tab-active' : 'tab-inactive'}
            >
              <span className="flex items-center gap-1.5">{tab.icon}{tab.label}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 pb-2">
          {meta && (
            <span className="text-xs text-slate-500">
              {meta.rowsReturned} rows • {meta.executionTimeMs}ms
              {meta.cached && <span className="ml-1 badge-cyan">cached</span>}
            </span>
          )}
          <button
            onClick={() => handleCopy(activeTab === 'csv' ? csvStr : jsonStr)}
            className="btn-ghost text-xs px-2 py-1"
          >
            <Copy size={12} />
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            onClick={() => {
              if (activeTab === 'csv') downloadFile(csvStr, 'results.csv', 'text/csv');
              else downloadFile(jsonStr, 'results.json', 'application/json');
            }}
            className="btn-ghost text-xs px-2 py-1"
          >
            <Download size={12} />
            Export
          </button>
        </div>
      </div>

      {/* Tab content */}
      <div className="animate-fade-in">
        {activeTab === 'table' && <TableView data={data} />}

        {activeTab === 'json' && (
          <pre className="code-block max-h-96 overflow-auto text-xs leading-relaxed">
            {jsonStr}
          </pre>
        )}

        {activeTab === 'csv' && (
          <pre className="code-block max-h-96 overflow-auto text-xs leading-relaxed">
            {csvStr || 'No CSV data'}
          </pre>
        )}

        {activeTab === 'metadata' && meta && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { label: 'Rows Returned',    value: meta.rowsReturned },
              { label: 'Execution Time',   value: `${meta.executionTimeMs}ms` },
              { label: 'Pipeline Time',    value: `${meta.totalPipelineTimeMs ?? '—'}ms` },
              { label: 'Data Freshness',   value: meta.dataFreshness },
              { label: 'Source',           value: meta.source },
              { label: 'Cache Hit',        value: meta.cached ? '✓ Yes' : '✗ No' },
              { label: 'User Role',        value: meta.userRole },
              { label: 'Query ID',         value: activeResult?.id?.slice(0, 8) + '...' },
            ].map(({ label, value }) => (
              <div key={label} className="bg-bg-tertiary rounded-lg p-3 border border-bg-border">
                <p className="text-xs text-slate-500 mb-1">{label}</p>
                <p className="text-sm font-semibold text-slate-200 font-mono">{String(value)}</p>
              </div>
            ))}
            {meta.agentTimings && (
              <div className="col-span-full bg-bg-tertiary rounded-lg p-3 border border-bg-border">
                <p className="text-xs text-slate-500 mb-2">Agent Timings</p>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(meta.agentTimings).map(([agent, ms]) => (
                    <div key={agent} className="flex items-center justify-between">
                      <span className="text-xs text-slate-400">{agent}</span>
                      <span className="text-xs font-mono text-slate-300">{ms}ms</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
