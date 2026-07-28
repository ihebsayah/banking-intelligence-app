import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  title?: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}

export function ErrorState({ title = 'Something went wrong', message, onRetry, retryLabel = 'Retry' }: Props) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[300px] gap-4 px-6">
      <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
        <AlertTriangle size={20} className="text-red-400" />
      </div>
      <div className="text-center">
        <h3 className="text-sm font-semibold text-slate-200 mb-1">{title}</h3>
        <p className="text-sm text-slate-500 max-w-sm">{message}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="btn-secondary text-sm">
          <RefreshCw size={14} />
          {retryLabel}
        </button>
      )}
    </div>
  );
}
