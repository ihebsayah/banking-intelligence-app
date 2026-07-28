// src/pages/Settings.tsx
import React, { useState } from 'react';
import { CheckCircle, XCircle, RefreshCw, Save, Trash2, Download } from 'lucide-react';
import { useConfigStore } from '../stores/configStore';
import { useAgentStore } from '../stores/agentStore';
import { checkHealth } from '../api/queries';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glass-card p-5">
      <h3 className="text-sm font-semibold mb-4 pb-3 border-b border-bg-border" style={{ color: 'var(--text-secondary)' }}>{title}</h3>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function Toggle({ label, sub, value, onChange }: {
  label: string; sub?: string; value: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</p>
        {sub && <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{sub}</p>}
      </div>
      <button
        onClick={() => onChange(!value)}
        className="relative w-10 h-6 rounded-full transition-colors duration-200"
        style={{ background: value ? 'var(--accent-blue)' : 'var(--bg-border)' }}
      >
        <span
          className={`absolute top-1 left-1 w-4 h-4 rounded-full shadow transition-transform duration-200 ${value ? 'translate-x-4' : 'translate-x-0'}`}
          style={{ background: 'var(--text-primary)' }}
        />
      </button>
    </div>
  );
}

export function Settings() {
  const config = useConfigStore();
  const { clearLogs, communicationLogs } = useAgentStore();
  const [apiStatus, setApiStatus] = useState<'idle' | 'checking' | 'ok' | 'fail'>('idle');
  const [saved, setSaved] = useState(false);

  const testConnection = async () => {
    setApiStatus('checking');
    const ok = await checkHealth();
    setApiStatus(ok ? 'ok' : 'fail');
    setTimeout(() => setApiStatus('idle'), 3000);
  };

  const exportLogs = () => {
    const blob = new Blob([JSON.stringify(communicationLogs, null, 2)], { type: 'application/json' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `agent-logs-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="p-6 space-y-6 animate-fade-in max-w-3xl">
      {/* API Connection */}
      <Section title="API Connection">
        <div>
          <label className="label">API Base URL</label>
          <input
            className="input"
            value={config.apiUrl}
            onChange={(e) => config.setApiUrl(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Timeout (ms)</label>
            <input
              type="number"
              className="input"
              value={config.requestTimeoutMs}
              onChange={(e) => config.setTimeout(+e.target.value)}
            />
          </div>
          <div>
            <label className="label">Max Retries</label>
            <input
              type="number"
              className="input"
              value={config.maxRetries}
              onChange={(e) => config.setMaxRetries(+e.target.value)}
            />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={testConnection} disabled={apiStatus === 'checking'} className="btn-secondary">
            {apiStatus === 'checking' ? <><span className="spinner" /> Checking...</> : <><RefreshCw size={13} /> Test Connection</>}
          </button>
          {apiStatus === 'ok'   && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle size={13}/> Connected</span>}
          {apiStatus === 'fail' && <span className="flex items-center gap-1 text-xs text-red-400"><XCircle size={13}/> Cannot reach API</span>}
        </div>
      </Section>

      {/* WebSocket */}
      <Section title="WebSocket Settings">
        <div>
          <label className="label">WebSocket URL</label>
          <input
            className="input"
            value={config.wsUrl}
            onChange={(e) => config.setWsUrl(e.target.value)}
          />
        </div>
        <Toggle
          label="Auto-reconnect"
          sub="Reconnect with exponential backoff on disconnect"
          value={true}
          onChange={() => {}}
        />
        <div>
          <label className="label">Health Refresh Interval (ms)</label>
          <select
            className="select"
            value={config.healthRefreshMs}
            onChange={(e) => config.setHealthRefreshMs(+e.target.value)}
          >
            <option value={2000}>2 seconds</option>
            <option value={5000}>5 seconds</option>
            <option value={10000}>10 seconds</option>
            <option value={30000}>30 seconds</option>
          </select>
        </div>
        <Toggle
          label="Auto-refresh Agent Health"
          sub="Poll agent health status automatically"
          value={config.autoRefreshHealth}
          onChange={config.setAutoRefreshHealth}
        />
      </Section>

      {/* Display */}
      <Section title="Display Settings">
        <div>
          <label className="label">Default Result Format</label>
          <select
            className="select"
            value={config.defaultFormat}
            onChange={(e) => config.setDefaultFormat(e.target.value as typeof config.defaultFormat)}
          >
            <option value="json">JSON</option>
            <option value="csv">CSV</option>
            <option value="table">Table</option>
          </select>
        </div>
        <div>
          <label className="label">Log Retention (entries)</label>
          <select
            className="select"
            value={config.logRetention}
            onChange={(e) => config.setLogRetention(+e.target.value as typeof config.logRetention)}
          >
            <option value={100}>100 entries</option>
            <option value={500}>500 entries</option>
            <option value={1000}>1,000 entries</option>
            <option value={5000}>5,000 entries</option>
          </select>
        </div>
        <Toggle label="Show Timestamps"     value={config.showTimestamps}     onChange={config.setShowTimestamps} />
        <Toggle label="Show Execution Times" value={config.showExecutionTimes} onChange={config.setShowExecutionTimes} />
      </Section>

      {/* Debug */}
      <Section title="Debug Mode">
        <Toggle label="Enable Debug Logging"  sub="Verbose logging in browser console"  value={config.debugMode}         onChange={config.setDebugMode} />
        <Toggle label="Show Raw API Responses" sub="Include raw JSON in results viewer"  value={config.showRawResponses}  onChange={config.setShowRawResponses} />
        <Toggle label="Show Timings"           sub="Display execution times everywhere"  value={config.showTimings}       onChange={config.setShowTimings} />
        <div className="flex items-center gap-3 pt-2">
          <button onClick={exportLogs} className="btn-secondary text-xs">
            <Download size={13} /> Export Logs ({communicationLogs.length})
          </button>
          <button onClick={clearLogs} className="btn-danger text-xs">
            <Trash2 size={13} /> Clear Logs
          </button>
        </div>
      </Section>

      {/* Save / Reset */}
      <div className="flex items-center gap-3">
        <button onClick={handleSave} className="btn-primary">
          {saved ? <><CheckCircle size={14} /> Saved!</> : <><Save size={14} /> Save Settings</>}
        </button>
        <button onClick={config.resetToDefaults} className="btn-secondary">
          Reset to Defaults
        </button>
      </div>
    </div>
  );
}
