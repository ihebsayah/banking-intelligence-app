// src/hooks/useWebSocket.ts
import { useEffect, useRef, useCallback } from 'react';
import { useAgentStore } from '../stores/agentStore';
import type { AgentLogEntry } from '../types/agent';

interface WSMessage {
  type: 'agent_log' | 'health_update' | 'query_event' | 'ping';
  payload?: unknown;
}

export function useWebSocket() {
  const wsRef    = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { wsUrl, setWsConnected, addLog, setAgentHealth } = useAgentStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        retryRef.current = 0;
      };

      ws.onclose = () => {
        setWsConnected(false);
        // Exponential backoff, max 30s
        const delay = Math.min(1000 * 2 ** retryRef.current, 30_000);
        retryRef.current += 1;
        timerRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data as string);
          if (msg.type === 'agent_log' && msg.payload) {
            addLog(msg.payload as AgentLogEntry);
          } else if (msg.type === 'health_update' && msg.payload) {
            setAgentHealth(msg.payload as Parameters<typeof setAgentHealth>[0]);
          }
        } catch {
          // ignore malformed messages
        }
      };
    } catch {
      // WebSocket not available or URL invalid — silent fail
      setWsConnected(false);
    }
  }, [wsUrl, setWsConnected, addLog, setAgentHealth]);

  const disconnect = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  useEffect(() => {
    connect();
    return disconnect;
  }, [connect, disconnect]);

  return { connect, disconnect };
}
