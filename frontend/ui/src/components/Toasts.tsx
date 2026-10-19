import { AlertCircle, CheckCircle2, X } from 'lucide-react';
import type { Toast } from '../hooks/useToasts';

export function Toasts({
  toasts,
  onDismiss,
}: {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}) {
  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-24 z-[80] flex flex-col items-center gap-2 px-4"
      role="status"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className="pointer-events-auto flex max-w-md animate-pop items-center gap-2.5 rounded-xl border border-slate-700 bg-slate-900 py-2.5 pl-4 pr-2 text-xs font-medium text-white shadow-pop"
        >
          {t.kind === 'error' ? (
            <AlertCircle size={15} className="shrink-0 text-rose-400" aria-hidden="true" />
          ) : (
            <CheckCircle2 size={15} className="shrink-0 text-emerald-400" aria-hidden="true" />
          )}
          <span>{t.text}</span>
          <button
            type="button"
            onClick={() => onDismiss(t.id)}
            className="inline-flex h-6 w-6 items-center justify-center rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            aria-label="Dismiss notification"
          >
            <X size={13} />
          </button>
        </div>
      ))}
    </div>
  );
}
