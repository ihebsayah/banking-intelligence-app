// src/components/AiAssistantPanel.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { X, Send, Bot, User } from 'lucide-react';
import { useUIStore } from '../stores/uiStore';
import { queryApi } from '../api/queryApi';
import { useBankingQueryStore } from '../stores/bankingQueryStore';
import { useAuthStore } from '../stores/authStore';
import type { QueryResult } from '../types/insights';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: Date;
  result?: QueryResult;
  isLoading?: boolean;
  isError?: boolean;
}

function formatMs(ms: number) {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`;
}

export function AiAssistantPanel() {
  const { aiPanelOpen, setAiPanelOpen } = useUIStore();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Hi! I can help you query banking data in natural language. Try asking about customers, risk, revenue, or compliance.',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const { isQuerying, setQuerying } = useBankingQueryStore();
  const { user } = useAuthStore();
  const userRole = user?.role ?? 'analyst';
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  }, [messages]);

  useEffect(() => {
    if (aiPanelOpen) setTimeout(() => inputRef.current?.focus(), 100);
  }, [aiPanelOpen]);

  const handleSubmit = useCallback(async (text: string) => {
    const q = text.trim();
    if (!q || isQuerying) return;

    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', text: q, timestamp: new Date() };
    const loadingMsg: Message = { id: crypto.randomUUID(), role: 'assistant', text: '', timestamp: new Date(), isLoading: true };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setInput('');
    setQuerying(true);

    try {
      const result = await queryApi.submitQuery(q, userRole);
      const summary = result.insights?.summary
        ? `${result.row_count} records in ${formatMs(result.execution_time_ms)}. ${result.insights.summary.slice(0, 120)}...`
        : `${result.row_count} records in ${formatMs(result.execution_time_ms)}.`;
      const assistantMsg: Message = { id: crypto.randomUUID(), role: 'assistant', text: summary, timestamp: new Date(), result };
      setMessages((prev) => prev.map((m) => m.isLoading ? assistantMsg : m));
    } catch (err: any) {
      const errMsg = err.response?.data?.detail ?? err.message ?? 'Query failed.';
      const errorMsg: Message = { id: crypto.randomUUID(), role: 'assistant', text: `Error: ${errMsg}`, timestamp: new Date(), isError: true };
      setMessages((prev) => prev.map((m) => m.isLoading ? errorMsg : m));
    } finally {
      setQuerying(false);
    }
  }, [isQuerying, userRole, setQuerying]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(input);
    }
  };

  if (!aiPanelOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-[400px] flex flex-col border-l shadow-2xl animate-fade-in"
      style={{ background: 'var(--bg-secondary)', borderColor: 'var(--bg-border)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--bg-border)' }}>
        <div className="flex items-center gap-2">
          <Bot size={16} style={{ color: 'var(--accent-blue)' }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>AI Assistant</span>
        </div>
        <button onClick={() => setAiPanelOpen(false)} className="p-1.5 rounded-lg transition-colors"
          style={{ color: 'var(--text-muted)' }}>
          <X size={16} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'assistant' && (
              <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                style={{ background: 'rgba(37,99,235,0.1)' }}>
                <Bot size={12} style={{ color: 'var(--accent-blue)' }} />
              </div>
            )}
            <div className={`max-w-[85%] rounded-xl px-3 py-2.5 text-sm ${msg.role === 'user' ? '' : ''}`}
              style={{
                background: msg.role === 'user' ? 'var(--accent-blue)' : 'var(--bg-card)',
                color: msg.role === 'user' ? '#ffffff' : msg.isError ? 'var(--accent-red)' : 'var(--text-secondary)',
                border: msg.role === 'assistant' ? '1px solid var(--bg-border)' : undefined,
              }}>
              {msg.isLoading ? (
                <div className="flex gap-1 py-1">
                  <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--text-subtle)' }} />
                  <span className="w-1.5 h-1.5 rounded-full animate-pulse [animation-delay:0.2s]" style={{ background: 'var(--text-subtle)' }} />
                  <span className="w-1.5 h-1.5 rounded-full animate-pulse [animation-delay:0.4s]" style={{ background: 'var(--text-subtle)' }} />
                </div>
              ) : (
                <p className="leading-relaxed">{msg.text}</p>
              )}
              {msg.result && (
                <div className="mt-2 pt-2 border-t text-xs font-mono" style={{ borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                  {msg.result.row_count} rows | {msg.result.source} | {msg.result.data_freshness}
                </div>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                style={{ background: 'var(--bg-tertiary)' }}>
                <User size={12} style={{ color: 'var(--text-muted)' }} />
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t" style={{ borderColor: 'var(--bg-border)' }}>
        <div className="flex items-end gap-2 rounded-xl border px-3 py-2"
          style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)' }}>
          <textarea
            ref={inputRef}
            className="flex-1 bg-transparent text-sm outline-none resize-none"
            placeholder="Ask about banking data..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isQuerying}
            style={{ color: 'var(--text-primary)' }}
          />
          <button
            onClick={() => handleSubmit(input)}
            disabled={isQuerying || !input.trim()}
            className="p-1.5 rounded-lg transition-colors disabled:opacity-30"
            style={{ color: 'var(--accent-blue)' }}
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
