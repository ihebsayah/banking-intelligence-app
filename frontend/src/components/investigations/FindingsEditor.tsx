// src/components/investigations/FindingsEditor.tsx
import React, { useEffect, useMemo, useState } from 'react';
import { Save, Plus, Trash2 } from 'lucide-react';
import { investigationsApi } from '../../api/investigationsApi';
import { parseInvestigationError } from './investigationErrors';
import type { FindingRef, Investigation } from '../../types/investigations';

interface Props {
  investigation: Investigation;
  editable: boolean;
  onSaved: (inv: Investigation) => void;
  onConflict: () => void;
  onDirtyChange: (dirty: boolean) => void;
}

function draftFrom(inv: Investigation) {
  return {
    findings_text: inv.findings_text ?? '',
    conclusion: inv.conclusion ?? '',
    findings_refs: (inv.findings_refs ?? []).map((r) => ({ type: r?.type ?? '', id: r?.id ?? '', description: r?.description ?? '' })),
  };
}

function refsEqual(a: FindingRef[], b: FindingRef[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((r, i) => r.type === b[i]?.type && r.id === b[i]?.id && r.description === b[i]?.description);
}

export function FindingsEditor({ investigation, editable, onSaved, onConflict, onDirtyChange }: Props) {
  const [draft, setDraft] = useState(() => draftFrom(investigation));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  // Server view is the baseline for dirty detection. If the parent refetches
  // (e.g. after a 409 conflict) do NOT clobber unsaved local edits.
  const dirty = useMemo(() => {
    const latest = draftFrom(investigation);
    return draft.findings_text !== latest.findings_text
      || draft.conclusion !== latest.conclusion
      || !refsEqual(draft.findings_refs, latest.findings_refs);
  }, [draft, investigation]);

  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);

  useEffect(() => {
    if (!saving) return;
    setSavedMsg(null);
  }, [saving]);

  const updateRef = (index: number, field: keyof FindingRef, value: string) => {
    setDraft((d) => {
      const refs = d.findings_refs.map((r, i) => (i === index ? { ...r, [field]: value } : r));
      return { ...d, findings_refs: refs };
    });
  };

  const addRef = () => {
    setDraft((d) => ({ ...d, findings_refs: [...d.findings_refs, { type: '', id: '', description: '' }] }));
  };

  const removeRef = (index: number) => {
    setDraft((d) => ({ ...d, findings_refs: d.findings_refs.filter((_, i) => i !== index) }));
  };

  const save = async () => {
    if (!editable || saving) return;
    setSaving(true);
    setError(null);
    setSavedMsg(null);
    try {
      const res = await investigationsApi.update(investigation.investigation_id, {
        findings_text: draft.findings_text,
        findings_refs: draft.findings_refs,
        conclusion: draft.conclusion,
        expected_version: investigation.version,
      });
      setDraft(draftFrom(res.investigation));
      setSavedMsg('Findings saved.');
      onSaved(res.investigation);
    } catch (err) {
      const parsed = parseInvestigationError(err);
      if (parsed.kind === 'conflict') {
        onConflict();
      } else {
        setError(parsed.message);
      }
    } finally {
      setSaving(false);
    }
  };

  const inputClass = "w-full px-3 py-1.5 border rounded-lg text-xs outline-none focus:border-[var(--accent-blue)] placeholder:text-[var(--text-subtle)] disabled:opacity-60 disabled:cursor-not-allowed";
  const labelClass = "block text-[10px] font-bold uppercase tracking-wider mb-1";

  return (
    <div className="rounded-2xl border p-5 space-y-5"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          Investigation Notebook
        </h3>
        <div className="flex items-center gap-2">
          {savedMsg && (
            <span role="status" className="text-[10px]" style={{ color: 'var(--accent-green)' }}>{savedMsg}</span>
          )}
          {editable ? (
            <button
              onClick={save}
              disabled={saving || !dirty}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold shadow-md transition-all hover:brightness-90 disabled:opacity-40 disabled:pointer-events-none"
              style={{ background: 'var(--accent-blue)', color: 'var(--text-primary)' }}
            >
              <Save size={13} /> {saving ? 'Saving…' : dirty ? 'Save Findings' : 'Saved'}
            </button>
          ) : (
            <span className="text-[10px]" style={{ color: 'var(--text-subtle)' }}>
              Read-only view
            </span>
          )}
        </div>
      </div>

      {error && (
        <div role="alert" className="px-3 py-2 rounded-lg border text-xs"
          style={{ background: 'rgba(220,38,38,0.08)', borderColor: 'rgba(220,38,38,0.2)', color: 'var(--accent-red)' }}>
          {error}
        </div>
      )}

      <div>
        <label htmlFor="findings-text" className={labelClass} style={{ color: 'var(--text-muted)' }}>
          Findings
        </label>
        <textarea
          id="findings-text"
          value={draft.findings_text}
          onChange={(e) => setDraft((d) => ({ ...d, findings_text: e.target.value }))}
          disabled={!editable}
          rows={8}
          placeholder="Record the evidence gathered and analysis performed."
          className={`${inputClass} resize-y`}
          style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
        />
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <span className={labelClass} style={{ color: 'var(--text-muted)' }}>References</span>
          {editable && (
            <button onClick={addRef}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold border transition-all hover:brightness-95"
              style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-secondary)' }}>
              <Plus size={11} /> Add reference
            </button>
          )}
        </div>
        {draft.findings_refs.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--text-subtle)' }}>No references added.</p>
        ) : (
          <div className="space-y-2">
            {draft.findings_refs.map((ref, i) => (
              <div key={i} className="flex items-start gap-2">
                <input
                  value={ref.type}
                  onChange={(e) => updateRef(i, 'type', e.target.value)}
                  disabled={!editable}
                  aria-label={`Reference ${i + 1} type`}
                  placeholder="type"
                  className={`${inputClass} w-28 flex-shrink-0`}
                  style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
                />
                <input
                  value={ref.id}
                  onChange={(e) => updateRef(i, 'id', e.target.value)}
                  disabled={!editable}
                  aria-label={`Reference ${i + 1} id`}
                  placeholder="id"
                  className={`${inputClass} flex-shrink-0 font-mono`}
                  style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
                />
                <input
                  value={ref.description}
                  onChange={(e) => updateRef(i, 'description', e.target.value)}
                  disabled={!editable}
                  aria-label={`Reference ${i + 1} description`}
                  placeholder="description"
                  className={inputClass}
                  style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
                />
                {editable && (
                  <button onClick={() => removeRef(i)} aria-label={`Remove reference ${i + 1}`}
                    className="p-1.5 rounded-lg border transition-all hover:brightness-95 flex-shrink-0"
                    style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--accent-red)' }}>
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <label htmlFor="conclusion" className={labelClass} style={{ color: 'var(--text-muted)' }}>
          Conclusion
        </label>
        <textarea
          id="conclusion"
          value={draft.conclusion}
          onChange={(e) => setDraft((d) => ({ ...d, conclusion: e.target.value }))}
          disabled={!editable}
          rows={4}
          placeholder="Final assessment and recommended disposition."
          className={`${inputClass} resize-y`}
          style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--bg-border)', color: 'var(--text-primary)' }}
        />
      </div>
    </div>
  );
}
