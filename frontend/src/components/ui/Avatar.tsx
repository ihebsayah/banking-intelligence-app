import { clsx } from 'clsx';

interface Props {
  name: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizes = {
  sm: 'w-6 h-6 text-[10px]',
  md: 'w-8 h-8 text-xs',
  lg: 'w-10 h-10 text-sm',
};

export function Avatar({ name, size = 'md', className }: Props) {
  const initial = name?.charAt(0)?.toUpperCase() ?? '?';
  return (
    <div className={clsx(
      'rounded-full flex items-center justify-center font-semibold flex-shrink-0',
      sizes[size],
      className,
    )} style={{ background: 'rgba(37,99,235,0.1)', color: 'var(--accent-blue)' }}>
      {initial}
    </div>
  );
}
