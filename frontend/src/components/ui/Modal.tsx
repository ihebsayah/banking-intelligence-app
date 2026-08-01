// src/components/ui/Modal.tsx
import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

interface Props {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

export function Modal({ open, title, onClose, children, footer }: Props) {
  const titleId = useRef(`modal-${Math.random().toString(36).slice(2)}`).current;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      style={{ background: 'rgba(2,6,23,0.6)', backdropFilter: 'blur(2px)' }}
    >
      <div
        className="w-full max-w-md rounded-2xl border shadow-2xl"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'var(--bg-border)' }}>
          <h2 id={titleId} className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
            {title}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 rounded-lg transition-colors"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.background = 'transparent'; }}
          >
            <X size={16} />
          </button>
        </div>
        <div className="px-5 py-4 max-h-[60vh] overflow-y-auto">{children}</div>
        {footer && (
          <div className="flex items-center justify-end gap-2 px-5 py-4 border-t" style={{ borderColor: 'var(--bg-border)' }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
