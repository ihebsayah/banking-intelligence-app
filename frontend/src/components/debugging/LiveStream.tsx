import React, { useEffect, useRef, useState } from 'react';

interface LiveStreamProps {
  requestId: string;
}

export const LiveStream: React.FC<LiveStreamProps> = ({ requestId }) => {
  const [messages, setMessages] = useState<any[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Connect to WebSocket on port 8099
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.hostname;
    const wsPort = '8099';
    const wsUrl = `${protocol}//${wsHost}:${wsPort}/debug/stream`;

    console.log(`Connecting to WebSocket at ${wsUrl}`);
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log('Connected to debug stream');
      setIsConnected(true);
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setMessages(prev => [...prev, data]);
        
        // Auto-scroll to bottom
        setTimeout(() => {
          if (containerRef.current) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight;
          }
        }, 0);
      } catch (err) {
        console.error('Error parsing live WS payload:', err);
      }
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    ws.current.onclose = () => {
      console.log('Disconnected from debug stream');
      setIsConnected(false);
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  return (
    <div className="live-stream flex flex-col h-full min-h-[500px]">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <span className="w-2.5 h-2.5 bg-rose-500 rounded-full animate-ping"></span>
          🔴 Live Agent Communication Stream
        </h2>
        <div className="flex gap-4 text-xs font-mono">
          <span className={`px-2 py-1 rounded border ${isConnected ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'}`}>
            ● {isConnected ? 'ACTIVE LOG STREAM' : 'DISCONNECTED'}
          </span>
          <span className="px-2 py-1 bg-slate-800 border border-slate-700 text-slate-300 rounded">
            Messages: {messages.length}
          </span>
        </div>
      </div>

      <div 
        className="stream-container flex-1 bg-slate-950 border border-slate-850 rounded-lg p-4 overflow-y-auto max-h-[500px] font-mono text-xs space-y-3"
        ref={containerRef}
      >
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 py-20 space-y-2">
            <span className="spinner w-6 h-6 border-slate-700 border-t-blue-500 rounded-full animate-spin"></span>
            <span>Awaiting incoming pipeline executions... Run a query to see events here.</span>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const agentData = msg.data || {};
            const isError = agentData.error;
            return (
              <div 
                key={idx} 
                className={`stream-message p-3 rounded-lg border transition-all ${
                  isError 
                    ? 'bg-rose-500/5 border-rose-500/20 text-rose-300' 
                    : 'bg-slate-900/50 border-slate-800/80 text-slate-300'
                }`}
              >
                <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500 font-mono">
                      {new Date().toLocaleTimeString()}
                    </span>
                    <span className="px-2 py-0.5 bg-slate-950 text-blue-400 border border-slate-800 rounded font-bold uppercase tracking-wider text-[9px]">
                      {msg.type}
                    </span>
                    <span className="text-slate-200 font-bold text-xs">
                      {agentData.agent_name || 'Agent'}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {agentData.processing_time_ms && (
                      <span className="text-[10px] bg-slate-950 px-1.5 py-0.5 rounded text-amber-400 font-bold">
                        {agentData.processing_time_ms.toFixed(1)}ms
                      </span>
                    )}
                    {agentData.confidence_score && (
                      <span className="text-[10px] bg-slate-950 px-1.5 py-0.5 rounded text-emerald-400 font-bold">
                        {(agentData.confidence_score * 100).toFixed(0)}% Conf
                      </span>
                    )}
                  </div>
                </div>
                <div className="data-payload">
                  <pre className="p-3 bg-slate-950 border border-slate-900 rounded overflow-x-auto text-[11px] text-slate-400 leading-relaxed max-h-60 overflow-y-auto">
                    {JSON.stringify(agentData, null, 2)}
                  </pre>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
