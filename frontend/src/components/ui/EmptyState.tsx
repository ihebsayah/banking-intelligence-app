import { clsx } from 'clsx';

interface Props {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: Props) {
  return (
    <div className={clsx('flex flex-col items-center justify-center py-16 px-6 gap-3', className)}>
      {icon && (
        <div className="w-10 h-10 rounded-xl bg-slate-500/10 flex items-center justify-center text-slate-500">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-medium text-slate-300">{title}</h3>
      {description && <p className="text-sm text-slate-500 max-w-sm text-center">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
