// src/components/QueryBuilder/index.tsx
import React, { useRef, KeyboardEvent } from 'react';
import { Play, X, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import { useQuery } from '../../hooks/useQuery';
import { PRESET_QUERIES } from '../../types/query';
import type { QueryFormat } from '../../types/query';

const CATEGORIES = Array.from(new Set(PRESET_QUERIES.map((q) => q.category)));

const FORMAT_OPTIONS: { value: QueryFormat; label: string }[] = [
  { value: 'json',  label: 'JSON' },
  { value: 'csv',   label: 'CSV'  },
  { value: 'table', label: 'Table'},
];

export function QueryBuilder() {
  const { query, format, status, setQuery, setFormat, runQuery, clearQuery } = useQuery();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [openCategory, setOpenCategory] = React.useState<string | null>('Customer Analysis');

  const isRunning = status === 'running';

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      runQuery();
    }
  };

  return (
    <div className="glass-card p-5 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap size={16} className="text-blue-400" />
          <span className="text-sm font-semibold text-slate-200">Query Input</span>
        </div>
        <div className="flex items-center gap-2">
          {FORMAT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setFormat(opt.value)}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-all duration-150 ${
                format === opt.value
                  ? 'bg-blue-600/30 text-blue-400 border border-blue-500/30'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-bg-hover'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Textarea */}
      <div className="relative">
        <textarea
          ref={textareaRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter natural language query... (⌘+Enter to run)"
          rows={3}
          className="textarea w-full"
          disabled={isRunning}
        />
        {query && (
          <button
            onClick={clearQuery}
            className="absolute top-2 right-2 p-1 text-slate-500 hover:text-slate-300 transition-colors"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* Run button */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => runQuery()}
          disabled={isRunning || !query.trim()}
          className="btn-primary flex-1"
        >
          {isRunning ? (
            <>
              <span className="spinner" />
              Running Pipeline...
            </>
          ) : (
            <>
              <Play size={14} />
              Run Query
            </>
          )}
        </button>
        <button onClick={clearQuery} className="btn-secondary">
          <X size={14} />
          Clear
        </button>
      </div>

      {/* Preset Queries */}
      <div className="border-t border-bg-border pt-4">
        <p className="label mb-2">Preset Queries</p>
        <div className="flex flex-col gap-1 max-h-64 overflow-y-auto pr-1">
          {CATEGORIES.map((cat) => (
            <div key={cat}>
              <button
                onClick={() => setOpenCategory(openCategory === cat ? null : cat)}
                className="w-full flex items-center justify-between px-2 py-1.5 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-bg-hover rounded transition-all"
              >
                <span>{cat}</span>
                {openCategory === cat ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {openCategory === cat && (
                <div className="ml-2 mt-1 flex flex-col gap-0.5 animate-fade-in">
                  {PRESET_QUERIES.filter((q) => q.category === cat).map((preset) => (
                    <button
                      key={preset.id}
                      onClick={() => {
                        setQuery(preset.query);
                        textareaRef.current?.focus();
                      }}
                      className="text-left px-3 py-1.5 text-xs text-slate-400 hover:text-blue-400 hover:bg-blue-500/5 rounded transition-all border border-transparent hover:border-blue-500/10"
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
