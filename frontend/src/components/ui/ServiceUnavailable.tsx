// src/components/ui/ServiceUnavailable.tsx
import React from 'react';
import { AlertCircle, Terminal, HelpCircle } from 'lucide-react';

interface Props {
  serviceName: string;
  missingEndpoint: string;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  requiredRole?: string;
}

export function ServiceUnavailable({ serviceName, missingEndpoint, method = 'GET', requiredRole }: Props) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center min-h-[400px] bg-[#070d19]/60 border border-[#0f2244] rounded-2xl backdrop-blur-md max-w-xl mx-auto my-12 shadow-[0_12px_40px_rgba(0,0,0,0.5)]">
      <div className="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-6 shadow-[0_0_24px_rgba(245,158,11,0.15)] animate-pulse">
        <AlertCircle size={28} className="text-amber-500" />
      </div>

      <h2 className="text-xl font-bold text-white tracking-tight mb-2">Service Not Available</h2>
      <p className="text-sm text-slate-400 max-w-sm mb-6 leading-relaxed">
        The <span className="text-slate-200 font-semibold">{serviceName}</span> service is scheduled for deployment. High-fidelity connection will establish once the backend API is live.
      </p>

      {/* API Gap Trace Container */}
      <div className="w-full bg-[#03060c] border border-[#0f203d] rounded-xl p-4 text-left font-mono mb-6">
        <div className="flex items-center gap-2 text-xs text-slate-500 mb-2 border-b border-[#0f203d] pb-2">
          <Terminal size={12} />
          <span>API GAP TRACE</span>
        </div>
        <div className="flex flex-col gap-1.5 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-600 w-16">Method:</span>
            <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 font-semibold">{method}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-600 w-16">Endpoint:</span>
            <span className="text-emerald-400 select-all">{missingEndpoint}</span>
          </div>
          {requiredRole && (
            <div className="flex items-center gap-2">
              <span className="text-slate-600 w-16">RBAC:</span>
              <span className="text-purple-400 capitalize">{requiredRole}</span>
            </div>
          )}
          <div className="flex items-center gap-2">
            <span className="text-slate-600 w-16">Status:</span>
            <span className="text-amber-400 font-medium">Pending Backend Integration</span>
          </div>
        </div>
      </div>

      {/* Info Badge */}
      <div className="flex items-start gap-2 text-left bg-[#0a1528] border border-[#102a54] rounded-lg p-3 text-[11px] text-slate-500">
        <HelpCircle size={14} className="text-[#3b82f6] flex-shrink-0 mt-0.5" />
        <span>
          Real-time banking database tables exist, but backend endpoints must be generated to serve this interface. Check <code className="text-slate-400 font-mono font-semibold">FRONTEND_API_GAPS.md</code> in the repository root for specifications.
        </span>
      </div>
    </div>
  );
}
