// src/components/PipelineVisualizer/index.tsx
import React, { useState } from 'react';
import { CheckCircle, XCircle, Clock, ChevronDown, ChevronUp, ArrowDown } from 'lucide-react';
import { useQueryStore } from '../../stores/queryStore';
import { PIPELINE_STEP_META } from '../../types/query';
import type { PipelineStep, PipelineStepName } from '../../types/query';

const ORDERED_STEPS: PipelineStepName[] = [
  'intent', 'schema', 'entity_resolution', 'sql', 'validation', 'execution',
];

interface StepCardProps {
  step: PipelineStep;
  isActive: boolean;
  index: number;
}

function JsonTree({ data, depth = 0 }: { data: unknown; depth?: number }) {
  const [collapsed, setCollapsed] = useState(depth > 1);
  if (data === null)    return <span className="json-null">null</span>;
  if (data === undefined) return <span className="json-null">undefined</span>;
  if (typeof data === 'boolean') return <span className="json-bool">{String(data)}</span>;
  if (typeof data === 'number')  return <span className="json-number">{data}</span>;
  if (typeof data === 'string')  return <span className="json-string">"{data}"</span>;

  if (Array.isArray(data)) {
    if (data.length === 0) return <span className="json-null">[]</span>;
    return (
      <span>
        <button onClick={() => setCollapsed(!collapsed)} className="text-slate-500 hover:text-slate-300 text-xs">
          {collapsed ? `[...${data.length}]` : '['}
        </button>
        {!collapsed && (
          <div style={{ paddingLeft: `${(depth + 1) * 12}px` }}>
            {data.slice(0, 20).map((item, i) => (
              <div key={i}>
                <JsonTree data={item} depth={depth + 1} />
                {i < data.length - 1 && <span className="text-slate-600">,</span>}
              </div>
            ))}
            {data.length > 20 && <div className="text-slate-500">...{data.length - 20} more</div>}
            <span>]</span>
          </div>
        )}
      </span>
    );
  }

  if (typeof data === 'object') {
    const entries = Object.entries(data as Record<string, unknown>);
    if (entries.length === 0) return <span className="json-null">{'{}'}</span>;
    return (
      <span>
        <button onClick={() => setCollapsed(!collapsed)} className="text-slate-500 hover:text-slate-300 text-xs">
          {collapsed ? `{...}` : '{'}
        </button>
        {!collapsed && (
          <div style={{ paddingLeft: `${(depth + 1) * 12}px` }}>
            {entries.map(([k, v], i) => (
              <div key={k}>
                <span className="json-key">"{k}"</span>
                <span className="text-slate-500">: </span>
                <JsonTree data={v} depth={depth + 1} />
                {i < entries.length - 1 && <span className="text-slate-600">,</span>}
              </div>
            ))}
            <span>{'}'}</span>
          </div>
        )}
      </span>
    );
  }

  return <span className="text-slate-400">{String(data)}</span>;
}

function StepCard({ step, isActive, index }: StepCardProps) {
  const [expanded, setExpanded] = useState(false);
  const meta = PIPELINE_STEP_META[step.name as PipelineStepName];
  const color = meta?.color ?? '#6b7280';

  const statusIcon = step.status === 'running'
    ? <span className="spinner" />
    : step.status === 'success'
    ? <CheckCircle size={16} className="text-emerald-400" />
    : step.status === 'error'
    ? <XCircle size={16} className="text-red-400" />
    : <Clock size={16} className="text-slate-500" />;

  const cardClass = step.status === 'running'  ? 'pipeline-step pipeline-step-active step-running'
                  : step.status === 'success'  ? 'pipeline-step pipeline-step-success'
                  : step.status === 'error'    ? 'pipeline-step pipeline-step-error'
                  : 'pipeline-step';

  return (
    <div className={cardClass}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3"
      >
        {/* Color bar */}
        <div className="w-1 h-10 rounded-full flex-shrink-0" style={{ background: color }} />

        {/* Step info */}
        <div className="flex-1 text-left min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-300">{String(index + 1).padStart(2, '0')}</span>
            <span className="text-sm font-semibold text-slate-200">{meta?.displayName ?? step.displayName}</span>
            {step.status === 'success' && step.durationMs && (
              <span className="ml-auto text-xs text-slate-500">{step.durationMs}ms</span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">{meta?.description}</p>
        </div>

        {/* Status */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {statusIcon}
          {(step.request || step.response || step.error) && (
            expanded ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />
          )}
        </div>
      </button>

      {/* Expanded Detail */}
      {expanded && (step.request || step.response || step.error) && (
        <div className="mt-3 border-t border-bg-border pt-3 space-y-3 animate-slide-up">
          {Boolean(step.request) && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">← Request</p>
              <div className="code-block max-h-40 text-xs">
                <JsonTree data={step.request} />
              </div>
            </div>
          )}
          {Boolean(step.response) && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">→ Response</p>
              <div className="code-block max-h-40 text-xs">
                <JsonTree data={step.response} />
              </div>
            </div>
          )}
          {step.error && (
            <div>
              <p className="text-xs font-semibold text-red-500 mb-1">✗ Error</p>
              <div className="code-block max-h-32 text-xs text-red-400">{step.error}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function PipelineVisualizer() {
  const { activeResult, status, pipelineSteps: storePipelineSteps } = useQueryStore();

  const steps = activeResult?.pipelineSteps ?? storePipelineSteps;

  // Build display steps — merge pipeline meta with actual result
  const displaySteps: PipelineStep[] = ORDERED_STEPS.map((name) => {
    const found = steps.find((s) => s.name === name);
    if (found) return found;
    const meta = PIPELINE_STEP_META[name];
    return {
      name,
      displayName: meta.displayName,
      status:      status === 'idle' ? 'pending' : 'pending',
    };
  });

  return (
    <div className="glass-card p-5">
      <div className="section-header mb-4">
        <ArrowDown size={16} className="text-blue-400" />
        <span>Pipeline Execution Flow</span>
        {status === 'running' && (
          <span className="ml-auto badge-blue">Running</span>
        )}
        {status === 'success' && activeResult?.metadata?.totalPipelineTimeMs && (
          <span className="ml-auto text-xs text-slate-500">
            Total: {activeResult.metadata.totalPipelineTimeMs}ms
          </span>
        )}
      </div>

      {status === 'idle' ? (
        <div className="flex flex-col items-center justify-center py-10 text-center gap-3">
          <div className="w-12 h-12 rounded-full bg-bg-tertiary border border-bg-border flex items-center justify-center">
            <ArrowDown size={20} className="text-slate-600" />
          </div>
          <p className="text-sm text-slate-500">Run a query to see the pipeline</p>
          <p className="text-xs text-slate-600">Intent → Schema → Entity → SQL → Validate → Execute</p>
        </div>
      ) : (
        <div className="flex flex-col gap-0">
          {displaySteps.map((step, i) => (
            <React.Fragment key={step.name}>
              <StepCard step={step} isActive={step.status === 'running'} index={i} />
              {i < displaySteps.length - 1 && (
                <div className="pipeline-connector" />
              )}
            </React.Fragment>
          ))}
        </div>
      )}
    </div>
  );
}
