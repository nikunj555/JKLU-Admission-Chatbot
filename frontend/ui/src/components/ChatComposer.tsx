import { ArrowUp, Square } from 'lucide-react';
import { forwardRef, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState } from 'react';

export interface ComposerHandle {
  focus: () => void;
}

interface Props {
  onSend: (text: string) => void;
  onStop: () => void;
  loading: boolean;
  offline: boolean;
  variant: 'hero' | 'dock';
}

const MAX = 600;

export const ChatComposer = forwardRef<ComposerHandle, Props>(function ChatComposer(
  { onSend, onStop, loading, offline, variant },
  ref
) {
  const [value, setValue] = useState('');
  const area = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    focus: () => area.current?.focus(),
  }));

  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 180) + 'px';
  }, [value]);

  useEffect(() => {
    if (!loading) area.current?.focus({ preventScroll: true });
  }, [loading]);

  const canSend = value.trim().length > 0 && !loading;

  function submit() {
    if (!canSend) return;
    onSend(value);
    setValue('');
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="w-full"
      aria-label="Ask a question"
    >
      <div
        className={`rounded-2xl border transition-all duration-200 bg-white/95 dark:bg-slate-900/90 backdrop-blur-sm ${
          variant === 'hero'
            ? 'p-2 sm:p-2.5 shadow-pop border-slate-300 dark:border-slate-700 focus-within:border-blue-600 dark:focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-100 dark:focus-within:ring-blue-950/60'
            : 'p-1.5 sm:p-2 shadow-card border-slate-200 dark:border-slate-800 focus-within:border-blue-600 dark:focus-within:border-blue-500 focus-within:ring-3 focus-within:ring-blue-100 dark:focus-within:ring-blue-950/60'
        }`}
      >
        <div className="flex items-end gap-2">
          <label htmlFor="composer" className="sr-only">
            Ask an admission question
          </label>
          <textarea
            id="composer"
            ref={area}
            rows={1}
            maxLength={MAX}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={
              offline
                ? 'The assistant server is offline. You can still type; send once it is back.'
                : 'Ask about admissions, eligibility, fees, scholarships, hostel, faculty…'
            }
            className={`max-h-44 min-h-[46px] flex-1 resize-none bg-transparent px-3.5 py-2.5 text-[15px] leading-6 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none ${
              variant === 'hero' ? 'sm:text-[16px]' : ''
            }`}
          />

          {loading ? (
            <button
              type="button"
              onClick={onStop}
              className="mb-1 mr-1 inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-300 bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 px-3 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-200"
              aria-label="Stop and cancel this request"
            >
              <Square size={12} fill="currentColor" aria-hidden="true" />
              <span>Stop</span>
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              aria-label="Send question"
              title="Send (Enter)"
              className="mb-1 mr-1 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-800 text-white shadow-subtle transition-all hover:bg-blue-900 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-blue-800"
            >
              <ArrowUp size={18} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between px-2 text-xs text-slate-600 dark:text-slate-400">
        <span>
          <kbd className="font-mono rounded bg-slate-100 dark:bg-slate-800 px-1 py-0.5 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300">Enter</kbd> to send{' '}
          <span className="hidden sm:inline">
            · <kbd className="font-mono rounded bg-slate-100 dark:bg-slate-800 px-1 py-0.5 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300">Shift+Enter</kbd> for a new line
          </span>
        </span>
        <span className={value.length > MAX - 80 ? 'text-amber-600 font-medium' : ''} aria-live="polite">
          {value.length > MAX - 80 ? `${value.length}/${MAX}` : ''}
        </span>
      </div>
    </form>
  );
});
