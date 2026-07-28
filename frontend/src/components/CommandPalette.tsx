// src/components/CommandPalette.tsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, LayoutDashboard, GitBranch, Bot, BarChart3, ShieldAlert,
  Scale, FileText, Settings2, Shield, User, Settings, Command,
} from 'lucide-react';
import { useUIStore } from '../stores/uiStore';

interface CommandItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  action: () => void;
  category: string;
}

export function CommandPalette() {
  const { commandPaletteOpen, setCommandPaletteOpen } = useUIStore();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const commands: CommandItem[] = [
    { id: 'dashboard',  label: 'Dashboard',       icon: <LayoutDashboard size={15} />, action: () => navigate('/dashboard'),       category: 'Navigate' },
    { id: 'branches',   label: 'Branches',        icon: <GitBranch size={15} />,       action: () => navigate('/branches'),        category: 'Navigate' },
    { id: 'assistant',  label: 'AI Assistant',     icon: <Bot size={15} />,             action: () => navigate('/assistant'),        category: 'Navigate' },
    { id: 'kpi',        label: 'KPI Analytics',    icon: <BarChart3 size={15} />,       action: () => navigate('/kpi'),             category: 'Navigate' },
    { id: 'kpi-gov',    label: 'KPI Governance',   icon: <Shield size={15} />,          action: () => navigate('/kpi-governance'),  category: 'Navigate' },
    { id: 'risk',       label: 'Risk Monitor',     icon: <ShieldAlert size={15} />,     action: () => navigate('/risk'),            category: 'Navigate' },
    { id: 'compliance', label: 'Compliance',       icon: <Scale size={15} />,           action: () => navigate('/compliance'),      category: 'Navigate' },
    { id: 'reports',    label: 'Reports',          icon: <FileText size={15} />,        action: () => navigate('/reports'),         category: 'Navigate' },
    { id: 'admin',      label: 'Admin',            icon: <Settings2 size={15} />,       action: () => navigate('/admin'),           category: 'Navigate' },
    { id: 'profile',    label: 'Profile',          icon: <User size={15} />,            action: () => navigate('/profile'),         category: 'Navigate' },
    { id: 'settings',   label: 'Settings',         icon: <Settings size={15} />,        action: () => navigate('/settings'),        category: 'Navigate' },
  ];

  const filtered = query
    ? commands.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()))
    : commands;

  useEffect(() => {
    if (commandPaletteOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [commandPaletteOpen]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(!commandPaletteOpen);
      }
      if (e.key === 'Escape' && commandPaletteOpen) {
        setCommandPaletteOpen(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [commandPaletteOpen, setCommandPaletteOpen]);

  const executeCommand = useCallback((cmd: CommandItem) => {
    cmd.action();
    setCommandPaletteOpen(false);
  }, [setCommandPaletteOpen]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      executeCommand(filtered[selectedIndex]);
    }
  };

  if (!commandPaletteOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
      onClick={() => setCommandPaletteOpen(false)}>
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)' }} />
      <div className="relative w-full max-w-md rounded-xl shadow-2xl border overflow-hidden animate-fade-in"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
        onClick={(e) => e.stopPropagation()}>
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: 'var(--bg-border)' }}>
          <Command size={16} style={{ color: 'var(--text-subtle)' }} />
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command or navigate..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: 'var(--text-primary)' }}
          />
          <kbd className="text-[10px] px-1.5 py-0.5 rounded border font-mono"
            style={{ color: 'var(--text-subtle)', borderColor: 'var(--bg-border)', background: 'var(--bg-tertiary)' }}>
            esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-64 overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-subtle)' }}>
              No results found.
            </div>
          ) : (
            filtered.map((cmd, idx) => (
              <button
                key={cmd.id}
                onClick={() => executeCommand(cmd)}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors text-left"
                style={{
                  background: idx === selectedIndex ? 'var(--bg-hover)' : undefined,
                  color: 'var(--text-secondary)',
                }}
                onMouseEnter={() => setSelectedIndex(idx)}
              >
                <span style={{ color: 'var(--text-muted)' }}>{cmd.icon}</span>
                <span className="flex-1">{cmd.label}</span>
                <span className="text-[10px] font-mono" style={{ color: 'var(--text-subtle)' }}>{cmd.category}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
