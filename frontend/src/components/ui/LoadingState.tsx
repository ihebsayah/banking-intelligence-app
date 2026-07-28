import { Building2 } from 'lucide-react';

interface Props {
  message?: string;
}

export function LoadingState({ message = 'Loading...' }: Props) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
      <div className="w-10 h-10 rounded-xl bg-blue-600/10 flex items-center justify-center">
        <Building2 size={20} className="text-blue-400" />
      </div>
      <div className="flex flex-col items-center gap-2">
        <div className="flex gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse [animation-delay:0.2s]" />
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse [animation-delay:0.4s]" />
        </div>
        <p className="text-sm text-slate-500">{message}</p>
      </div>
    </div>
  );
}
