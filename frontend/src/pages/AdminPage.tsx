// src/pages/AdminPage.tsx
import React, { useEffect, useState, useCallback, useRef } from 'react';
import { adminApi } from '../api/adminApi';
import { ServiceUnavailable } from '../components/ui/ServiceUnavailable';
import { BankingHeader } from '../components/Layout/BankingHeader';
import { Link } from 'react-router-dom';
import {
  Terminal, Shield, Cpu, Users, Settings2, ShieldCheck, Filter, Key,
  ChevronLeft, ChevronRight, RefreshCw, Plus, Search, MoreVertical,
  UserCheck, UserX, KeyRound, UserCog, Copy, CheckCircle2, X,
  Clock, Activity, AlertTriangle, Info, ChevronDown,
  Edit3, Trash2, Lock, Unlock,
} from 'lucide-react';
import type {
  AdminUserRow, RoleInfo, PermissionInfo,
  CreateUserRequest, UpdateUserRequest,
  ActivityLogEntry, PaginatedAdminUsers,
} from '../types/api';
import { formatDateTime } from '../utils/formatters';
import { clsx } from 'clsx';
import { useAuthStore } from '../stores/authStore';
import { env } from '../config/env';

// ─── Shared helpers ───────────────────────────────────────────────────────────

const ROLE_BADGE: Record<string, string> = {
  admin:      'bg-red-500/10 text-red-400 border-red-500/25',
  compliance: 'bg-amber-500/10 text-amber-400 border-amber-500/25',
  manager:    'bg-purple-500/10 text-purple-400 border-purple-500/25',
  analyst:    'bg-blue-500/10 text-blue-400 border-blue-500/25',
};
const roleBadge = (r: string) => ROLE_BADGE[r?.toLowerCase()] ?? 'bg-slate-500/10 text-slate-400 border-slate-500/25';

const statusBadge = (s: string) =>
  s?.toLowerCase() === 'active'
    ? 'bg-emerald-500/8 text-emerald-400 border-emerald-500/20'
    : 'bg-slate-500/8 text-slate-400 border-slate-500/20';

const ACTION_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  user_created:        { label: 'User Created',       color: 'text-emerald-400', icon: <UserCheck size={13} /> },
  role_changed:        { label: 'Role Changed',       color: 'text-amber-400',   icon: <UserCog size={13} /> },
  user_disabled:       { label: 'User Suspended',     color: 'text-red-400',     icon: <UserX size={13} /> },
  user_enabled:        { label: 'User Activated',     color: 'text-emerald-400', icon: <UserCheck size={13} /> },
  password_reset:      { label: 'Password Reset',     color: 'text-purple-400',  icon: <KeyRound size={13} /> },
  user_updated:        { label: 'Profile Updated',    color: 'text-blue-400',    icon: <Edit3 size={13} /> },
  role_permissions_updated: { label: 'Perms Updated', color: 'text-cyan-400',   icon: <ShieldCheck size={13} /> },
};

// ─── Toast ────────────────────────────────────────────────────────────────────

interface ToastProps { message: string; type: 'success' | 'error' | 'info'; onClose: () => void; }
function Toast({ message, type, onClose }: ToastProps) {
  useEffect(() => { const t = setTimeout(onClose, 4500); return () => clearTimeout(t); }, [onClose]);
  const styles = {
    success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    error:   'border-red-500/30 bg-red-500/10 text-red-300',
    info:    'border-blue-500/30 bg-blue-500/10 text-blue-300',
  };
  return (
    <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-sm font-medium shadow-2xl ${styles[type]} max-w-sm`}>
      {type === 'success' && <CheckCircle2 size={16} />}
      {type === 'error'   && <AlertTriangle size={16} />}
      {type === 'info'    && <Info size={16} />}
      <span className="flex-1">{message}</span>
      <button onClick={onClose} className="opacity-60 hover:opacity-100 transition-opacity"><X size={14} /></button>
    </div>
  );
}

// ─── Modal base ───────────────────────────────────────────────────────────────

function Modal({ title, onClose, children, width = 'max-w-lg' }: {
  title: string; onClose: () => void; children: React.ReactNode; width?: string;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className={`relative z-10 w-full ${width} bg-[#070d19] border border-[#1a3a6e] rounded-2xl shadow-2xl shadow-black/50`}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#0f2244]">
          <h3 className="text-sm font-bold text-white">{title}</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-[#0f2244] text-slate-400 hover:text-white transition-all">
            <X size={16} />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

// ─── Field component ──────────────────────────────────────────────────────────

function Field({ label, children, required }: { label: string; children: React.ReactNode; required?: boolean }) {
  return (
    <div className="space-y-1.5">
      <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
        {label}{required && <span className="text-red-400 ml-1">*</span>}
      </label>
      {children}
    </div>
  );
}

const inputCls = "w-full bg-[#03060c] border border-[#0f203d] rounded-lg px-3 py-2 text-sm text-slate-200 outline-none focus:border-[#0066CC]/60 placeholder-slate-600 transition-colors";
const selectCls = `${inputCls} cursor-pointer`;
const btnPrimary = "flex items-center gap-2 px-4 py-2 rounded-lg bg-[#0066CC] hover:bg-[#0052a3] text-white text-sm font-semibold shadow-lg shadow-[#0066CC]/20 hover:shadow-[#0066CC]/35 transition-all disabled:opacity-40 disabled:pointer-events-none";
const btnGhost = "flex items-center gap-2 px-4 py-2 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-300 text-sm font-semibold hover:text-white transition-all";

// ─── Create User Modal ────────────────────────────────────────────────────────

interface CreateUserModalProps { roles: RoleInfo[]; onClose: () => void; onSuccess: (msg: string) => void; onError: (msg: string) => void; }
function CreateUserModal({ roles, onClose, onSuccess, onError }: CreateUserModalProps) {
  const [form, setForm] = useState<CreateUserRequest>({ user_id: '', email: '', name: '', role: 'analyst', bank_id: 'hq_main' });
  const [saving, setSaving] = useState(false);
  const [tempPw, setTempPw] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const set = (k: keyof CreateUserRequest) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async () => {
    if (!form.user_id || !form.email || !form.name) { onError('user_id, email and name are required'); return; }
    setSaving(true);
    try {
      const res = await adminApi.createUser(form);
      setTempPw(res.temp_password);
      onSuccess(`User "${res.user_id}" created successfully`);
    } catch (e: any) {
      onError(e?.response?.data?.detail?.message ?? e?.response?.data?.detail ?? 'Failed to create user');
      setSaving(false);
    }
  };

  const copyPw = () => {
    if (tempPw) { navigator.clipboard.writeText(tempPw); setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };

  if (tempPw) {
    return (
      <Modal title="User Created — Save Temporary Password" onClose={onClose}>
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-amber-500/8 border border-amber-500/20 flex items-start gap-3">
            <AlertTriangle size={16} className="text-amber-400 mt-0.5 shrink-0" />
            <p className="text-xs text-amber-300/90 leading-relaxed">
              This temporary password is shown <strong>only once</strong>. Share it securely with the user.
              They will be required to change it on first login.
            </p>
          </div>
          <Field label="Temporary Password">
            <div className="flex gap-2">
              <code className="flex-1 bg-[#03060c] border border-[#0f203d] rounded-lg px-3 py-2 text-sm text-emerald-400 font-mono tracking-wider select-all">
                {tempPw}
              </code>
              <button onClick={copyPw} className={btnGhost}>
                {copied ? <CheckCircle2 size={14} className="text-emerald-400" /> : <Copy size={14} />}
              </button>
            </div>
          </Field>
          <button onClick={onClose} className={`${btnPrimary} w-full justify-center`}>Done</button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title="Create New User" onClose={onClose} width="max-w-xl">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Field label="User ID" required><input value={form.user_id} onChange={set('user_id')} placeholder="analyst_002" className={inputCls} /></Field>
          <Field label="Full Name" required><input value={form.name} onChange={set('name')} placeholder="Jane Smith" className={inputCls} /></Field>
        </div>
        <Field label="Email" required><input type="email" value={form.email} onChange={set('email')} placeholder="jane@bankintel.hq" className={inputCls} /></Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Role" required>
            <select value={form.role} onChange={set('role')} className={selectCls}>
              {roles.length > 0
                ? roles.map((r) => <option key={r.role} value={r.role}>{r.label ?? r.role}</option>)
                : ['analyst', 'manager', 'compliance', 'admin'].map((r) => <option key={r} value={r}>{r}</option>)
              }
            </select>
          </Field>
          <Field label="Bank ID"><input value={form.bank_id} onChange={set('bank_id')} placeholder="hq_main" className={inputCls} /></Field>
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className={`${btnGhost} flex-1 justify-center`}>Cancel</button>
          <button onClick={submit} disabled={saving} className={`${btnPrimary} flex-1 justify-center`}>
            {saving ? <RefreshCw size={14} className="animate-spin" /> : <Plus size={14} />}
            Create User
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ─── Edit User Modal ──────────────────────────────────────────────────────────

function EditUserModal({ user, onClose, onSuccess, onError }: {
  user: AdminUserRow; onClose: () => void; onSuccess: (msg: string) => void; onError: (msg: string) => void;
}) {
  const [form, setForm] = useState<UpdateUserRequest>({ name: user.name ?? '', email: user.email, bank_id: user.bank_id });
  const [saving, setSaving] = useState(false);
  const set = (k: keyof UpdateUserRequest) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async () => {
    setSaving(true);
    try {
      await adminApi.updateUser(user.user_id, form);
      onSuccess(`User "${user.user_id}" updated`);
      onClose();
    } catch (e: any) {
      onError(e?.response?.data?.detail?.message ?? 'Failed to update user');
      setSaving(false);
    }
  };

  return (
    <Modal title={`Edit User — ${user.user_id}`} onClose={onClose}>
      <div className="space-y-4">
        <Field label="Full Name"><input value={form.name ?? ''} onChange={set('name')} className={inputCls} /></Field>
        <Field label="Email"><input type="email" value={form.email ?? ''} onChange={set('email')} className={inputCls} /></Field>
        <Field label="Bank ID"><input value={form.bank_id ?? ''} onChange={set('bank_id')} className={inputCls} /></Field>
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className={`${btnGhost} flex-1 justify-center`}>Cancel</button>
          <button onClick={submit} disabled={saving} className={`${btnPrimary} flex-1 justify-center`}>
            {saving ? <RefreshCw size={14} className="animate-spin" /> : <Edit3 size={14} />}
            Save Changes
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ─── Assign Role Modal ────────────────────────────────────────────────────────

function AssignRoleModal({ user, roles, onClose, onSuccess, onError }: {
  user: AdminUserRow; roles: RoleInfo[];
  onClose: () => void; onSuccess: (msg: string) => void; onError: (msg: string) => void;
}) {
  const [role, setRole] = useState(user.role);
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (role === user.role) { onClose(); return; }
    setSaving(true);
    try {
      await adminApi.updateUserRole(user.user_id, { role });
      onSuccess(`Role updated to "${role}" for ${user.user_id}`);
      onClose();
    } catch (e: any) {
      onError(e?.response?.data?.detail?.message ?? 'Failed to update role');
      setSaving(false);
    }
  };

  return (
    <Modal title={`Assign Role — ${user.user_id}`} onClose={onClose}>
      <div className="space-y-4">
        <div className="p-3 rounded-lg bg-[#03060c] border border-[#0f203d] text-xs text-slate-400 flex items-center gap-2">
          <Info size={12} className="shrink-0 text-blue-400" />
          Role change takes effect immediately on the user's next request.
        </div>
        <Field label="New Role">
          <select value={role} onChange={(e) => setRole(e.target.value)} className={selectCls}>
            {(roles.length > 0 ? roles.map((r) => r.role) : ['analyst', 'manager', 'compliance', 'admin']).map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </Field>
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className={`${btnGhost} flex-1 justify-center`}>Cancel</button>
          <button onClick={submit} disabled={saving || role === user.role} className={`${btnPrimary} flex-1 justify-center`}>
            {saving ? <RefreshCw size={14} className="animate-spin" /> : <UserCog size={14} />}
            Assign Role
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ─── Reset Password Modal ─────────────────────────────────────────────────────

function ResetPasswordModal({ user, onClose, onSuccess, onError }: {
  user: AdminUserRow; onClose: () => void; onSuccess: (msg: string) => void; onError: (msg: string) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [tempPw, setTempPw] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const doReset = async () => {
    setLoading(true);
    try {
      const res = await adminApi.resetPassword(user.user_id);
      setTempPw(res.temp_password);
      onSuccess(`Password reset for ${user.user_id}`);
    } catch (e: any) {
      onError(e?.response?.data?.detail?.message ?? 'Reset failed');
      setLoading(false);
    }
  };

  const copyPw = () => {
    if (tempPw) { navigator.clipboard.writeText(tempPw); setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };

  return (
    <Modal title={`Reset Password — ${user.user_id}`} onClose={onClose}>
      {!tempPw ? (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-amber-500/8 border border-amber-500/20 flex items-start gap-3">
            <AlertTriangle size={16} className="text-amber-400 mt-0.5 shrink-0" />
            <p className="text-xs text-amber-300/90 leading-relaxed">
              A new secure temporary password will be auto-generated and returned <strong>once</strong>.
              The user will be required to change it on next login.
            </p>
          </div>
          <div className="flex gap-3">
            <button onClick={onClose} className={`${btnGhost} flex-1 justify-center`}>Cancel</button>
            <button onClick={doReset} disabled={loading} className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 text-sm font-semibold transition-all disabled:opacity-40">
              {loading ? <RefreshCw size={14} className="animate-spin" /> : <KeyRound size={14} />}
              Generate New Password
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-emerald-500/8 border border-emerald-500/20 flex items-start gap-3">
            <CheckCircle2 size={16} className="text-emerald-400 mt-0.5 shrink-0" />
            <p className="text-xs text-emerald-300/90">Password reset successful. Copy and share securely.</p>
          </div>
          <Field label="Temporary Password">
            <div className="flex gap-2">
              <code className="flex-1 bg-[#03060c] border border-[#0f203d] rounded-lg px-3 py-2 text-sm text-emerald-400 font-mono tracking-wider select-all">
                {tempPw}
              </code>
              <button onClick={copyPw} className={btnGhost}>
                {copied ? <CheckCircle2 size={14} className="text-emerald-400" /> : <Copy size={14} />}
              </button>
            </div>
          </Field>
          <button onClick={onClose} className={`${btnPrimary} w-full justify-center`}>Done</button>
        </div>
      )}
    </Modal>
  );
}

// ─── Confirm Status Modal ─────────────────────────────────────────────────────

function ConfirmStatusModal({ user, onClose, onSuccess, onError }: {
  user: AdminUserRow; onClose: () => void; onSuccess: (msg: string) => void; onError: (msg: string) => void;
}) {
  const [saving, setSaving] = useState(false);
  const willSuspend = user.status === 'active';
  const newStatus = willSuspend ? 'suspended' : 'active';

  const confirm = async () => {
    setSaving(true);
    try {
      await adminApi.updateUserStatus(user.user_id, { status: newStatus });
      onSuccess(`User "${user.user_id}" ${newStatus}`);
      onClose();
    } catch (e: any) {
      onError(e?.response?.data?.detail?.message ?? e?.response?.data?.detail ?? 'Operation failed');
      setSaving(false);
    }
  };

  return (
    <Modal title={willSuspend ? 'Suspend User Account' : 'Reactivate User Account'} onClose={onClose}>
      <div className="space-y-4">
        <div className={`p-4 rounded-xl border flex items-start gap-3 ${willSuspend ? 'bg-red-500/8 border-red-500/20' : 'bg-emerald-500/8 border-emerald-500/20'}`}>
          {willSuspend
            ? <UserX size={16} className="text-red-400 mt-0.5 shrink-0" />
            : <UserCheck size={16} className="text-emerald-400 mt-0.5 shrink-0" />}
          <p className={`text-xs leading-relaxed ${willSuspend ? 'text-red-300/90' : 'text-emerald-300/90'}`}>
            {willSuspend
              ? `Suspending "${user.user_id}" will immediately revoke all platform access. Existing sessions will be invalidated on next request.`
              : `Reactivating "${user.user_id}" will restore full platform access according to their assigned role.`}
          </p>
        </div>
        <div className="flex gap-3">
          <button onClick={onClose} className={`${btnGhost} flex-1 justify-center`}>Cancel</button>
          <button
            onClick={confirm}
            disabled={saving}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all disabled:opacity-40 ${
              willSuspend
                ? 'bg-red-500/15 hover:bg-red-500/25 border border-red-500/30 text-red-300'
                : 'bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300'
            }`}
          >
            {saving ? <RefreshCw size={14} className="animate-spin" /> : willSuspend ? <Lock size={14} /> : <Unlock size={14} />}
            {willSuspend ? 'Suspend Account' : 'Reactivate Account'}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ─── Role Permission Editor ───────────────────────────────────────────────────

function RolePermissionEditor({ role, allPermissions, onClose, onSuccess, onError }: {
  role: RoleInfo; allPermissions: PermissionInfo[];
  onClose: () => void; onSuccess: (msg: string) => void; onError: (msg: string) => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set(role.permissions));
  const [saving, setSaving] = useState(false);

  const toggle = (perm: string) =>
    setSelected((s) => { const n = new Set(s); n.has(perm) ? n.delete(perm) : n.add(perm); return n; });

  const save = async () => {
    setSaving(true);
    try {
      await adminApi.updateRolePermissions(role.role, [...selected]);
      onSuccess(`Permissions updated for "${role.role}"`);
      onClose();
    } catch (e: any) {
      onError(e?.response?.data?.detail?.message ?? 'Failed to update permissions');
      setSaving(false);
    }
  };

  const grouped = allPermissions.reduce<Record<string, PermissionInfo[]>>((acc, p) => {
    const cat = p.category ?? 'other';
    (acc[cat] ??= []).push(p);
    return acc;
  }, {});

  return (
    <Modal title={`Edit Permissions — ${role.label ?? role.role}`} onClose={onClose} width="max-w-2xl">
      <div className="space-y-4">
        <div className="max-h-80 overflow-y-auto space-y-4 pr-1">
          {Object.entries(grouped).map(([cat, perms]) => (
            <div key={cat}>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">{cat}</p>
              <div className="space-y-1">
                {perms.map((p) => {
                  const key = p.permission ?? p.permission_key ?? '';
                  const on = selected.has(key);
                  return (
                    <button
                      key={key}
                      onClick={() => toggle(key)}
                      className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg border text-left transition-all ${
                        on ? 'bg-[#0066CC]/12 border-[#0066CC]/30' : 'bg-[#03060c] border-[#0f203d] hover:border-[#1a3a6e]'
                      }`}
                    >
                      <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-all ${
                        on ? 'bg-[#0066CC] border-[#0066CC]' : 'bg-transparent border-slate-600'
                      }`}>
                        {on && <CheckCircle2 size={10} className="text-white" />}
                      </div>
                      <span className="font-mono text-xs text-amber-400/90">{key}</span>
                      <span className="text-xs text-slate-500 ml-auto">{p.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-3 pt-2 border-t border-[#0f2244]">
          <button onClick={onClose} className={`${btnGhost} flex-1 justify-center`}>Cancel</button>
          <button onClick={save} disabled={saving} className={`${btnPrimary} flex-1 justify-center`}>
            {saving ? <RefreshCw size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
            Save Permissions
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ─── User Actions Menu ────────────────────────────────────────────────────────

type ModalType = 'create' | 'edit' | 'role' | 'reset' | 'status' | null;

function UserActionsMenu({ user, onAction }: { user: AdminUserRow; onAction: (type: ModalType, user: AdminUserRow) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const actions = [
    { label: 'Edit Profile',    icon: <Edit3 size={13} />,    type: 'edit' as ModalType },
    { label: 'Assign Role',     icon: <UserCog size={13} />,  type: 'role' as ModalType },
    { label: 'Reset Password',  icon: <KeyRound size={13} />, type: 'reset' as ModalType },
    { label: user.status === 'active' ? 'Suspend Account' : 'Reactivate Account',
      icon: user.status === 'active' ? <UserX size={13} /> : <UserCheck size={13} />,
      type: 'status' as ModalType,
      danger: user.status === 'active' },
  ];

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="p-1.5 rounded-lg hover:bg-[#0f2244] text-slate-500 hover:text-slate-300 transition-all"
      >
        <MoreVertical size={14} />
      </button>
      {open && (
        <div className="absolute right-0 top-8 z-30 w-48 bg-[#070d19] border border-[#1a3a6e] rounded-xl shadow-2xl shadow-black/50 overflow-hidden">
          {actions.map((a) => (
            <button
              key={a.type}
              onClick={() => { setOpen(false); onAction(a.type, user); }}
              className={clsx(
                'w-full flex items-center gap-2.5 px-3 py-2.5 text-xs font-medium transition-colors text-left',
                a.danger
                  ? 'hover:bg-red-500/10 text-red-400 hover:text-red-300'
                  : 'hover:bg-[#0f2244] text-slate-300 hover:text-white'
              )}
            >
              {a.icon}{a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Activity Timeline ────────────────────────────────────────────────────────

function ActivityTimeline({ items, loading }: { items: ActivityLogEntry[]; loading: boolean }) {
  if (loading) return (
    <div className="space-y-3 py-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex gap-4 animate-pulse">
          <div className="w-8 h-8 rounded-full bg-[#0f2244] shrink-0" />
          <div className="flex-1 space-y-1.5 pt-1">
            <div className="h-3 w-48 bg-[#0f2244] rounded" />
            <div className="h-2.5 w-72 bg-[#0a1828] rounded" />
          </div>
        </div>
      ))}
    </div>
  );

  if (items.length === 0) return (
    <div className="text-center py-16 text-slate-500 text-xs border border-dashed border-[#0f2244] rounded-xl">
      No admin activity recorded yet
    </div>
  );

  return (
    <div className="relative pl-4">
      {/* Vertical line */}
      <div className="absolute left-[19px] top-0 bottom-0 w-px bg-[#0f2244]" />
      <div className="space-y-0">
        {items.map((item, idx) => {
          const meta = ACTION_META[item.action] ?? { label: item.action, color: 'text-slate-400', icon: <Activity size={13} /> };
          return (
            <div key={item.id} className="relative flex gap-4 pb-5 group">
              {/* Dot */}
              <div className={`relative z-10 w-9 h-9 rounded-full border flex items-center justify-center shrink-0 transition-all
                bg-[#070d19] border-[#1a3a6e] group-hover:border-[#0066CC]/50 ${meta.color}`}>
                {meta.icon}
              </div>
              {/* Content */}
              <div className="flex-1 min-w-0 pt-1.5">
                <div className="flex items-baseline justify-between gap-4">
                  <span className={`text-xs font-semibold ${meta.color}`}>{meta.label}</span>
                  <span className="text-[10px] font-mono text-slate-600 shrink-0 flex items-center gap-1">
                    <Clock size={9} />{formatDateTime(item.created_at)}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5 flex flex-wrap gap-x-4 gap-y-0.5">
                  <span>By <span className="text-slate-300 font-mono">{item.actor_id}</span></span>
                  {item.target_id && <span>→ <span className="text-slate-300 font-mono">{item.target_id}</span></span>}
                  {item.detail && Object.entries(item.detail).length > 0 && (
                    <span className="font-mono text-slate-600 text-[10px] truncate max-w-xs">
                      {JSON.stringify(item.detail)}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main AdminPage ───────────────────────────────────────────────────────────

export function AdminPage() {
  const { user: currentUser } = useAuthStore();

  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [userTotal, setUserTotal] = useState(0);
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [permissions, setPermissions] = useState<PermissionInfo[]>([]);
  const [activityItems, setActivityItems] = useState<ActivityLogEntry[]>([]);
  const [activityTotal, setActivityTotal] = useState(0);

  type Tab = 'users' | 'roles' | 'permissions' | 'activity';
  const [activeTab, setActiveTab] = useState<Tab>('users');
  const [loading, setLoading] = useState(true);
  const [apiFailed, setApiFailed] = useState(false);

  // User tab state
  const [page, setPage] = useState(1);
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const pageSize = 15;

  // Activity tab
  const [activityPage, setActivityPage] = useState(1);

  // Modal state
  const [modal, setModal] = useState<ModalType>(null);
  const [selectedUser, setSelectedUser] = useState<AdminUserRow | null>(null);
  const [roleEditorTarget, setRoleEditorTarget] = useState<RoleInfo | null>(null);

  // Toast
  const [toasts, setToasts] = useState<Array<{ id: number; msg: string; type: 'success' | 'error' | 'info' }>>([]);
  const toastId = useRef(0);
  const pushToast = useCallback((msg: string, type: 'success' | 'error' | 'info' = 'success') => {
    const id = ++toastId.current;
    setToasts((t) => [...t, { id, msg, type }]);
  }, []);
  const removeToast = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const openModal = (type: ModalType, user?: AdminUserRow) => {
    setSelectedUser(user ?? null);
    setModal(type);
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    setApiFailed(false);
    try {
      if (activeTab === 'users') {
        const data: PaginatedAdminUsers = await adminApi.getUsers(page, pageSize, roleFilter || undefined, statusFilter || undefined, searchQuery || undefined);
        setUsers(data.items ?? []);
        setUserTotal(data.total ?? 0);
      } else if (activeTab === 'roles') {
        const [r, p] = await Promise.all([adminApi.getRoles(), adminApi.getPermissions()]);
        setRoles(r);
        setPermissions(p);
      } else if (activeTab === 'permissions') {
        const p = await adminApi.getPermissions();
        setPermissions(p);
        if (roles.length === 0) setRoles(await adminApi.getRoles());
      } else if (activeTab === 'activity') {
        const data = await adminApi.getActivityLog(activityPage, 50);
        setActivityItems(data.items ?? []);
        setActivityTotal(data.total ?? 0);
      }
    } catch (err) {
      console.error('Admin fetch failed:', err);
      setApiFailed(true);
    } finally {
      setLoading(false);
    }
  }, [activeTab, page, roleFilter, statusFilter, searchQuery, activityPage]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const onSuccess = (msg: string) => { pushToast(msg, 'success'); setModal(null); fetchData(); };
  const onError   = (msg: string) => pushToast(msg, 'error');

  // Search with debounce
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSearchInput = (val: string) => {
    setSearchInput(val);
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => { setSearchQuery(val); setPage(1); }, 400);
  };

  const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'users',       label: 'User Directory',         icon: <Users size={14} /> },
    { id: 'roles',       label: 'RBAC Role Matrix',        icon: <Settings2 size={14} /> },
    { id: 'permissions', label: 'Permissions Registry',    icon: <ShieldCheck size={14} /> },
    { id: 'activity',    label: 'Admin Activity',          icon: <Activity size={14} /> },
  ];

  const totalPages = Math.max(1, Math.ceil(userTotal / pageSize));

  return (
    <div className="min-h-screen bg-[#040711] flex flex-col">
      <BankingHeader
        title="Headquarters Admin Console"
        subtitle="Enterprise user governance, RBAC management, and audit trail"
        onRefresh={fetchData}
        isRefreshing={loading}
      />

      {/* Toast stack */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <Toast key={t.id} message={t.msg} type={t.type} onClose={() => removeToast(t.id)} />
        ))}
      </div>

      {/* Modals */}
      {modal === 'create' && env.AUTH_PROVIDER !== 'keycloak' && (
        <CreateUserModal roles={roles} onClose={() => setModal(null)} onSuccess={onSuccess} onError={onError} />
      )}
      {modal === 'edit' && selectedUser && (
        <EditUserModal user={selectedUser} onClose={() => setModal(null)} onSuccess={onSuccess} onError={onError} />
      )}
      {modal === 'role' && selectedUser && (
        <AssignRoleModal user={selectedUser} roles={roles} onClose={() => setModal(null)} onSuccess={onSuccess} onError={onError} />
      )}
      {modal === 'reset' && selectedUser && (
        <ResetPasswordModal user={selectedUser} onClose={() => setModal(null)} onSuccess={onSuccess} onError={onError} />
      )}
      {modal === 'status' && selectedUser && (
        <ConfirmStatusModal user={selectedUser} onClose={() => setModal(null)} onSuccess={onSuccess} onError={onError} />
      )}
      {roleEditorTarget && (
        <RolePermissionEditor
          role={roleEditorTarget}
          allPermissions={permissions}
          onClose={() => setRoleEditorTarget(null)}
          onSuccess={(m) => { pushToast(m, 'success'); setRoleEditorTarget(null); fetchData(); }}
          onError={onError}
        />
      )}

      <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1600px] mx-auto w-full font-sans">

        {/* Dev tools strip */}
        <div className="bg-[#070d19]/60 border border-[#0f2244] rounded-xl px-5 py-3 backdrop-blur-md">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <Cpu size={12} className="text-[#0066CC]" />Developer Monitor Tools
            </p>
            <div className="flex gap-3">
              {[
                { to: '/dev', label: 'Agent Dashboard', icon: <Cpu size={13} /> },
                { to: '/dev/query', label: 'Query Tester', icon: <Terminal size={13} /> },
                { to: '/dev/debug', label: 'Security Audit', icon: <Shield size={13} /> },
              ].map((lnk) => (
                <Link key={lnk.to} to={lnk.to}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#03060c] border border-[#0f203d] hover:border-[#0066CC]/40 text-slate-400 hover:text-slate-200 text-xs font-medium transition-all">
                  {lnk.icon}{lnk.label}
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex items-center justify-between border-b border-[#0f2244]">
          <div className="flex gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => { setActiveTab(tab.id); setPage(1); }}
                className={clsx(
                  'relative flex items-center gap-2 px-4 py-3 text-xs font-semibold transition-all rounded-t-lg',
                  activeTab === tab.id
                    ? 'text-[#4d9fff] bg-[#0c1930]/40'
                    : 'text-slate-500 hover:text-slate-300 hover:bg-[#070d19]'
                )}
              >
                {tab.icon}{tab.label}
                {activeTab === tab.id && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#0066CC] rounded-full" />}
              </button>
            ))}
          </div>

          {activeTab === 'users' && env.AUTH_PROVIDER === 'keycloak' && (
            <a
              href={`${env.KEYCLOAK_URL}/admin/master/console/`}
              target="_blank"
              rel="noopener noreferrer"
              className={`${btnPrimary} mb-1 inline-flex items-center gap-2`}
            >
              <Plus size={14} />Manage Users in Keycloak
            </a>
          )}
          {activeTab === 'users' && env.AUTH_PROVIDER !== 'keycloak' && (
            <button
              onClick={() => { openModal('create'); if (roles.length === 0) adminApi.getRoles().then(setRoles); }}
              className={`${btnPrimary} mb-1`}
            >
              <Plus size={14} />Create User
            </button>
          )}
        </div>

        {/* Error state */}
        {apiFailed ? (
          <div className="space-y-4">
            <ServiceUnavailable
              serviceName="HQ Admin Management Portal"
              missingEndpoint={`GET /admin/${activeTab}`}
              method="GET"
            />
            <div className="flex justify-center">
              <button onClick={fetchData} className={btnPrimary}>
                <RefreshCw size={14} className={clsx(loading && 'animate-spin')} />Retry Connection
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* ═══ USERS TAB ═══════════════════════════════════════════════════════ */}
            {activeTab === 'users' && (
              <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
                {/* Filters bar */}
                <div className="flex flex-col sm:flex-row gap-3 mb-6">
                  <div className="relative flex-1">
                    <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input
                      value={searchInput}
                      onChange={(e) => handleSearchInput(e.target.value)}
                      placeholder="Search by user ID, email, or name…"
                      className="w-full bg-[#03060c] border border-[#0f203d] rounded-lg pl-9 pr-3 py-2 text-xs text-slate-300 outline-none focus:border-[#0066CC]/50 placeholder-slate-600"
                    />
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Filter size={11} className="text-slate-600" />
                    <select value={roleFilter} onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }} className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2.5 py-2 text-xs text-slate-300 outline-none focus:border-[#0066CC]/50">
                      <option value="">All Roles</option>
                      {['analyst', 'manager', 'compliance', 'admin'].map((r) => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
                    </select>
                    <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }} className="bg-[#03060c] border border-[#0f203d] rounded-lg px-2.5 py-2 text-xs text-slate-300 outline-none focus:border-[#0066CC]/50">
                      <option value="">All Statuses</option>
                      <option value="active">Active</option>
                      <option value="suspended">Suspended</option>
                    </select>
                  </div>
                </div>

                {/* Summary row */}
                <div className="flex items-center justify-between mb-4">
                  <p className="text-xs text-slate-500">
                    <span className="font-semibold text-slate-300">{userTotal.toLocaleString()}</span> users total
                    {(roleFilter || statusFilter || searchQuery) && <span className="text-slate-600"> (filtered)</span>}
                  </p>
                  {loading && <RefreshCw size={12} className="animate-spin text-slate-500" />}
                </div>

                {/* Table */}
                {loading && users.length === 0 ? (
                  <div className="space-y-2">
                    {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-12 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />)}
                  </div>
                ) : users.length === 0 ? (
                  <div className="text-center py-16 border border-dashed border-[#0f2244] rounded-xl text-slate-500 text-xs">
                    No users match the current filters
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-[#0f2244] text-slate-500 text-[11px]">
                          <th className="pb-3 font-semibold pl-1">User</th>
                          <th className="pb-3 font-semibold">Email</th>
                          <th className="pb-3 font-semibold">Role</th>
                          <th className="pb-3 font-semibold">Bank</th>
                          <th className="pb-3 font-semibold text-center">Status</th>
                          <th className="pb-3 font-semibold text-right">Last Login</th>
                          <th className="pb-3 font-semibold text-right pr-1">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#0f2244]/40">
                        {users.map((usr) => (
                          <tr key={usr.user_id} className="hover:bg-[#0c1930]/30 transition-all group">
                            <td className="py-3.5 pl-1">
                              <div className="font-semibold text-slate-200 text-xs">{usr.name ?? usr.user_id}</div>
                              <div className="font-mono text-[10px] text-slate-500 mt-0.5">#{usr.user_id}</div>
                            </td>
                            <td className="py-3.5 font-mono text-[11px] text-slate-400">{usr.email}</td>
                            <td className="py-3.5">
                              <span className={clsx('px-1.5 py-0.5 rounded border text-[9px] font-bold uppercase tracking-wider', roleBadge(usr.role))}>
                                {usr.role}
                              </span>
                            </td>
                            <td className="py-3.5 font-mono text-[10px] text-slate-500 uppercase">{usr.bank_id}</td>
                            <td className="py-3.5 text-center">
                              <span className={clsx('px-2 py-0.5 rounded-full text-[9px] font-semibold capitalize inline-flex items-center gap-1', statusBadge(usr.status))}>
                                <span className={clsx('w-1.5 h-1.5 rounded-full', usr.status === 'active' ? 'bg-emerald-400' : 'bg-slate-500')} />
                                {usr.status}
                              </span>
                            </td>
                            <td className="py-3.5 text-right font-mono text-[10px] text-slate-600">
                              {usr.last_login ? formatDateTime(usr.last_login) : '—'}
                            </td>
                            <td className="py-3.5 text-right pr-1">
                              <UserActionsMenu user={usr} onAction={openModal} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Pagination */}
                <div className="flex items-center justify-between border-t border-[#0f2244] mt-5 pt-4">
                  <span className="text-[10px] text-slate-500">
                    Page <span className="font-semibold text-slate-300">{page}</span> of <span className="font-semibold text-slate-300">{totalPages}</span>
                    <span className="ml-2 text-slate-600">·</span>
                    <span className="ml-2">{pageSize * (page - 1) + 1}–{Math.min(pageSize * page, userTotal)} of {userTotal}</span>
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button onClick={() => setPage(1)} disabled={page === 1} className="px-2 py-1 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30 text-[10px] font-mono transition-all">1</button>
                    <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="p-1.5 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30 transition-all">
                      <ChevronLeft size={13} />
                    </button>
                    <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="p-1.5 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30 transition-all">
                      <ChevronRight size={13} />
                    </button>
                    <button onClick={() => setPage(totalPages)} disabled={page >= totalPages} className="px-2 py-1 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30 text-[10px] font-mono transition-all">{totalPages}</button>
                  </div>
                </div>
              </div>
            )}

            {/* ═══ ROLES TAB ═══════════════════════════════════════════════════════ */}
            {activeTab === 'roles' && (
              <div className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  {loading && roles.length === 0
                    ? Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} className="h-48 bg-[#070d19] border border-[#0f2244] rounded-2xl animate-pulse" />
                      ))
                    : roles.map((rInfo) => (
                        <div key={rInfo.role} className="rounded-2xl border border-[#0f2040] bg-[#070d19]/60 p-6 space-y-5 backdrop-blur-md hover:border-[#1a3a6e] transition-all">
                          {/* Role header */}
                          <div className="flex items-start justify-between">
                            <div className="space-y-1">
                              <span className={clsx('px-2 py-0.5 rounded border text-xs font-bold uppercase tracking-wider', roleBadge(rInfo.role))}>
                                {rInfo.label ?? rInfo.role}
                              </span>
                              {rInfo.description && <p className="text-[11px] text-slate-500 mt-2">{rInfo.description}</p>}
                            </div>
                            <div className="text-right">
                              <div className="text-xl font-black text-white">{rInfo.user_count}</div>
                              <div className="text-[10px] text-slate-500">users</div>
                            </div>
                          </div>

                          {/* Permission chips */}
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <label className="text-[9px] font-bold uppercase tracking-widest text-slate-500 flex items-center gap-1.5">
                                <Key size={10} />Authorized Permissions ({rInfo.permissions.length})
                              </label>
                              <button
                                onClick={() => { if (permissions.length === 0) adminApi.getPermissions().then(setPermissions); setRoleEditorTarget(rInfo); }}
                                className="text-[9px] font-semibold text-[#4d9fff] hover:text-white transition-colors flex items-center gap-1"
                              >
                                <Edit3 size={10} />Edit
                              </button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              {rInfo.permissions.map((perm) => (
                                <span key={perm} className="bg-[#03060c] text-amber-400/80 px-2 py-0.5 rounded border border-[#1a3020] font-mono text-[9px]">
                                  {perm}
                                </span>
                              ))}
                              {rInfo.permissions.length === 0 && (
                                <span className="text-[10px] text-slate-600 italic">No permissions assigned</span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))
                  }
                </div>

                {/* Permission matrix grid */}
                {roles.length > 0 && permissions.length > 0 && (
                  <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
                    <h3 className="text-xs font-bold text-slate-300 mb-5 flex items-center gap-2">
                      <ShieldCheck size={14} className="text-[#0066CC]" />
                      Permission × Role Matrix
                    </h3>
                    <div className="overflow-x-auto">
                      <table className="text-[10px] border-collapse w-full">
                        <thead>
                          <tr>
                            <th className="text-left pb-3 pr-6 font-semibold text-slate-500 w-48">Permission</th>
                            {roles.map((r) => (
                              <th key={r.role} className="pb-3 px-3 font-semibold text-center w-24">
                                <span className={clsx('px-1.5 py-0.5 rounded border text-[9px] font-bold uppercase tracking-wider', roleBadge(r.role))}>
                                  {r.role}
                                </span>
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#0f2244]/40">
                          {permissions.map((p) => {
                            const key = p.permission ?? p.permission_key ?? '';
                            return (
                              <tr key={key} className="hover:bg-[#0c1930]/20 transition-all">
                                <td className="py-2 pr-6 font-mono text-amber-400/90">{key}</td>
                                {roles.map((r) => {
                                  const has = r.permissions.includes(key);
                                  return (
                                    <td key={r.role} className="py-2 px-3 text-center">
                                      {has
                                        ? <CheckCircle2 size={13} className="text-emerald-400 mx-auto" />
                                        : <span className="text-slate-700 mx-auto block text-center">·</span>}
                                    </td>
                                  );
                                })}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ═══ PERMISSIONS TAB ═════════════════════════════════════════════════ */}
            {activeTab === 'permissions' && (
              <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
                <div className="mb-5 flex items-center gap-2">
                  <Key size={15} className="text-[#0066CC]" />
                  <div>
                    <h3 className="text-sm font-bold text-white">Permissions Capability Index</h3>
                    <p className="text-[10px] text-slate-500 mt-0.5 font-mono">
                      {permissions.length} permission tokens across {roles.length} roles
                    </p>
                  </div>
                </div>

                {loading && permissions.length === 0
                  ? <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-10 bg-[#03060c] border border-[#0f203d]/30 rounded-lg animate-pulse" />)}</div>
                  : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="border-b border-[#0f2244] text-slate-500 text-[11px]">
                            <th className="pb-3 font-semibold w-12">Category</th>
                            <th className="pb-3 font-semibold w-56 pl-3">Permission Token</th>
                            <th className="pb-3 font-semibold w-72">Scope Description</th>
                            <th className="pb-3 font-semibold">Authorized Role Carriers</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#0f2244]/40">
                          {permissions.map((perm) => {
                            const key = perm.permission ?? perm.permission_key ?? '';
                            const catColors: Record<string, string> = {
                              read:  'text-blue-400 bg-blue-500/10 border-blue-500/20',
                              admin: 'text-red-400 bg-red-500/10 border-red-500/20',
                              write: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
                            };
                            return (
                              <tr key={key} className="hover:bg-[#0c1930]/25 transition-all">
                                <td className="py-3.5">
                                  <span className={clsx('px-1.5 py-0.5 rounded border text-[8px] font-bold uppercase tracking-widest', catColors[perm.category ?? ''] ?? 'text-slate-400 bg-slate-500/10 border-slate-500/20')}>
                                    {perm.category ?? '—'}
                                  </span>
                                </td>
                                <td className="py-3.5 pl-3 font-mono text-[11px] text-amber-400/90 font-bold select-all">{key}</td>
                                <td className="py-3.5 text-slate-400 leading-relaxed max-w-xs">{perm.description}</td>
                                <td className="py-3.5">
                                  <div className="flex flex-wrap gap-1.5">
                                    {perm.roles.map((r) => (
                                      <span key={r} className={clsx('px-1.5 py-0.5 rounded border text-[8px] font-bold uppercase tracking-wider', roleBadge(r))}>
                                        {r}
                                      </span>
                                    ))}
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )
                }
              </div>
            )}

            {/* ═══ ACTIVITY TAB ════════════════════════════════════════════════════ */}
            {activeTab === 'activity' && (
              <div className="bg-[#070d19]/40 border border-[#0f2244] rounded-2xl p-6 backdrop-blur-md">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-2">
                    <Activity size={15} className="text-[#0066CC]" />
                    <div>
                      <h3 className="text-sm font-bold text-white">Admin Activity Timeline</h3>
                      <p className="text-[10px] text-slate-500 mt-0.5">
                        All administrative actions logged in <span className="font-mono">user_activity_log</span>
                        {activityTotal > 0 && <span> · {activityTotal.toLocaleString()} total events</span>}
                      </p>
                    </div>
                  </div>
                  <button onClick={fetchData} className="p-2 rounded-lg hover:bg-[#0f2244] text-slate-500 hover:text-slate-300 transition-all">
                    <RefreshCw size={13} className={clsx(loading && 'animate-spin')} />
                  </button>
                </div>

                <ActivityTimeline items={activityItems} loading={loading} />

                {/* Pagination for activity */}
                {activityTotal > 50 && (
                  <div className="flex items-center justify-between border-t border-[#0f2244] mt-5 pt-4">
                    <span className="text-[10px] text-slate-500">
                      Page <span className="font-semibold text-slate-300">{activityPage}</span> of <span className="font-semibold text-slate-300">{Math.ceil(activityTotal / 50)}</span>
                    </span>
                    <div className="flex gap-1.5">
                      <button onClick={() => setActivityPage((p) => Math.max(1, p - 1))} disabled={activityPage === 1} className="p-1.5 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30">
                        <ChevronLeft size={13} />
                      </button>
                      <button onClick={() => setActivityPage((p) => p + 1)} disabled={activityPage >= Math.ceil(activityTotal / 50)} className="p-1.5 rounded-lg bg-[#0e1d35] border border-[#1e3459] text-slate-400 hover:text-white disabled:opacity-30">
                        <ChevronRight size={13} />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
