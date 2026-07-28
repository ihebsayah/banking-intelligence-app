// src/components/ui/ServiceUnavailable.tsx
import React from 'react';
import { AlertCircle } from 'lucide-react';

interface Props {
  serviceName: string;
  missingEndpoint: string;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  requiredRole?: string;
}

export function ServiceUnavailable({ serviceName, missingEndpoint, method = 'GET', requiredRole }: Props) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center min-h-[300px] max-w-lg mx-auto">
      <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
        style={{ background: 'rgba(217,119,6,0.1)' }}>
        <AlertCircle size={20} style={{ color: 'var(--accent-amber)' }} />
      </div>

      <h2 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Service Not Available</h2>
      <p className="text-sm max-w-sm mb-4" style={{ color: 'var(--text-muted)' }}>
        The <span style={{ color: 'var(--text-secondary)' }}>{serviceName}</span> service is not yet available.
      </p>

      <div className="w-full rounded-lg p-3 text-left font-mono text-xs space-y-1.5 border"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
        <div className="flex gap-2">
          <span style={{ color: 'var(--text-subtle)' }} className="w-14">Method:</span>
          <span style={{ color: 'var(--accent-blue)' }}>{method}</span>
        </div>
        <div className="flex gap-2">
          <span style={{ color: 'var(--text-subtle)' }} className="w-14">Endpoint:</span>
          <span style={{ color: 'var(--accent-green)' }}>{missingEndpoint}</span>
        </div>
        {requiredRole && (
          <div className="flex gap-2">
            <span style={{ color: 'var(--text-subtle)' }} className="w-14">RBAC:</span>
            <span className="capitalize" style={{ color: 'var(--accent-purple)' }}>{requiredRole}</span>
          </div>
        )}
      </div>
    </div>
  );
}
