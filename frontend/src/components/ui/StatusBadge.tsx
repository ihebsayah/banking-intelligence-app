import { clsx } from 'clsx';

type Variant = 'blue' | 'green' | 'red' | 'yellow' | 'purple' | 'gray';

const variantClasses: Record<Variant, string> = {
  blue:   'bg-blue-500/10 text-blue-400 border-blue-500/20',
  green:  'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  red:    'bg-red-500/10 text-red-400 border-red-500/20',
  yellow: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  gray:   'bg-slate-500/10 text-slate-400 border-slate-500/20',
};

interface Props {
  variant?: Variant;
  children: React.ReactNode;
  className?: string;
}

export function StatusBadge({ variant = 'gray', children, className }: Props) {
  return (
    <span className={clsx(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border',
      variantClasses[variant],
      className,
    )}>
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
