// src/components/investigations/CommentsTab.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, MessageSquare, Shield, Send } from 'lucide-react';
import { clsx } from 'clsx';
import { investigationsApi } from '../../api/investigationsApi';
import { parseInvestigationError } from './investigationErrors';
import { useAuth } from '../../auth/AuthProvider';
import { PERMISSIONS } from '../../lib/permissions';
import { formatDateTime } from '../../utils/formatters';
import type { Comment, CommentListResponse } from '../../types/investigations';

const PER_PAGE = 50;

export interface CommentsApiLike {
  listComments: (entityId: string, page?: number, perPage?: number) => Promise<CommentListResponse>;
  createComment: (entityId: string, content: string, isInternal: boolean) => Promise<unknown>;
}

interface Props {
  entityId: string;
  api?: CommentsApiLike;
}

export function CommentsTab({ entityId, api = investigationsApi as unknown as CommentsApiLike }: Props) {
  const { hasPermission } = useAuth();
  const canUseInternal = hasPermission(PERMISSIONS.COMMENT_VIEW_INTERNAL_CONTENT);

  const [comments, setComments] = useState<Comment[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [content, setContent] = useState('');
  const [isInternal, setIsInternal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const fetchComments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listComments(entityId, page, PER_PAGE);
      setComments(res.items);
    } catch (err) {
      setError(parseInvestigationError(err).message);
      setComments([]);
    } finally {
      setLoading(false);
    }
  }, [entityId, page, api]);

  useEffect(() => { fetchComments(); }, [fetchComments]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim() || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.createComment(entityId, content.trim(), canUseInternal && isInternal);
      setContent('');
      setIsInternal(false);
      setPage(1);
      await fetchComments();
    } catch (err) {
      setSubmitError(parseInvestigationError(err).message);
    } finally {
      setSubmitting(false);
    }
  };

  const hasNext = comments.length === PER_PAGE;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border p-5"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
        <h3 className="text-[10px] font-bold uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
          Add a comment
        </h3>
        <form onSubmit={submit} className="space-y-3">
          <label htmlFor="comment-content" className="sr-only">Comment text</label>
          <textarea
            id="comment-content"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={3}
            placeholder="Write a comment…"
            className="w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] resize-none"
            style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
          />
          <div className="flex items-center justify-between gap-3 flex-wrap">
            {canUseInternal ? (
              <label className="flex items-center gap-2 text-xs cursor-pointer" style={{ color: 'var(--text-secondary)' }}>
                <input
                  type="checkbox"
                  checked={isInternal}
                  onChange={(e) => setIsInternal(e.target.checked)}
                  className="accent-[var(--accent-blue)]"
                />
                Internal comment (visible to compliance only)
              </label>
            ) : (
              <span className="text-[10px]" style={{ color: 'var(--text-subtle)' }}>
                Comments are visible to the investigation team.
              </span>
            )}
            <button
              type="submit"
              disabled={submitting || !content.trim()}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
              style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
            >
              <Send size={13} /> {submitting ? 'Posting…' : 'Post Comment'}
            </button>
          </div>
          {submitError && (
            <div role="alert" className="px-3 py-2 rounded-lg border text-xs"
              style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
              {submitError}
            </div>
          )}
        </form>
      </div>

      {error ? (
        <div className="rounded-2xl border p-8 text-center text-sm" style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
          {error}
        </div>
      ) : loading && comments.length === 0 ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-16 border rounded-xl animate-pulse"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }} />
          ))}
        </div>
      ) : comments.length === 0 ? (
        <div className="rounded-2xl border p-10 flex flex-col items-center gap-3 text-center"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
          <MessageSquare size={24} style={{ color: 'var(--text-muted)' }} />
          <p className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>No comments yet</p>
        </div>
      ) : (
        <div className="rounded-2xl border divide-y divide-[var(--bg-border)]"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
          {comments.map((c) => (
            <div key={c.comment_id} className="p-4">
              <div className="flex items-center gap-2 flex-wrap mb-1.5">
                <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>{c.author_id}</span>
                <span className="font-mono text-[10px]" style={{ color: 'var(--text-subtle)' }}>{formatDateTime(c.created_at)}</span>
                {c.is_internal && (
                  <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] border"
                    style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}>
                    <Shield size={10} /> Internal
                  </span>
                )}
                {c.is_redacted && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] border"
                    style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
                    Redacted
                  </span>
                )}
              </div>
              <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                {c.content ?? 'Internal comment — content restricted in this view.'}
              </p>
            </div>
          ))}

          <div className="flex items-center justify-between border-t px-5 py-3.5"
            style={{ borderColor: 'var(--bg-border)' }}>
            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              Page {page} · {comments.length} comment{comments.length === 1 ? '' : 's'} shown
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                aria-label="Previous comments page"
                className={clsx('p-1.5 rounded-lg border transition-all', page === 1 && 'opacity-30 pointer-events-none')}
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}
              >
                <ChevronLeft size={14} />
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!hasNext}
                aria-label="Next comments page"
                className={clsx('p-1.5 rounded-lg border transition-all', !hasNext && 'opacity-30 pointer-events-none')}
                style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)', color: 'var(--text-muted)' }}
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
