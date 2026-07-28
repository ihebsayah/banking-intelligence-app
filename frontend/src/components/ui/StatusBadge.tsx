import { clsx } from 'clsx';

type Variant = 'blue' | 'green' | 'red' | 'yellow' | 'purple' | 'gray';

const variantStyles: Record<Variant, { bg: string; color: string; border: string }> = {
  blue:   { bg: 'rgba(37,99,235,0.1)',   color: 'var(--accent-blue)',  border: 'rgba(37,99,235,0.2)' },
  green:  { bg: 'rgba(22,163,74,0.1)',   color: 'var(--accent-green)', border: 'rgba(22,163,74,0.2)' },
  red:    { bg: 'rgba(220,38,38,0.1)',   color: 'var(--accent-red)',   border: 'rgba(220,38,38,0.2)' },
  yellow: { bg: 'rgba(217,119,6,0.1)',   color: 'var(--accent-amber)', border: 'rgba(217,119,6,0.2)' },
  purple: { bg: 'rgba(124,58,237,0.1)',  color: 'var(--accent-purple)',border: 'rgba(124,58,237,0.2)' },
  gray:   { bg: 'var(--bg-tertiary)',     color: 'var(--text-muted)',   border: 'var(--bg-border)' },
};

interface Props {
  variant?: Variant;
  children: React.ReactNode;
  className?: string;
}

export function StatusBadge({ variant = 'gray', children, className }: Props) {
  const s = variantStyles[variant];
  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border', className)}
      style={{ background: s.bg, color: s.color, borderColor: s.border }}>
      {children}
    </span>
  );
}

const roleVariant: Record<string, Variant> = {
  admin: 'red',
  compliance: 'yellow',
  manager: 'purple',
  analyst: 'blue',
};

export function RoleBadge({ role, className }: { role: string; className?: string }) {
  return (
    <StatusBadge variant={roleVariant[role] ?? 'gray'} className={className}>
      {role}
    </StatusBadge>
  );
}
