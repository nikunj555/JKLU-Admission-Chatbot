import { useEffect, useRef } from 'react';
import type { Message, Rating } from '../types';
import { ChatComposer, type ComposerHandle } from './ChatComposer';
import { ChatMessage } from './ChatMessage';
import { forwardRef } from 'react';

interface Props {
  messages: Message[];
  loading: boolean;
  offline: boolean;
  onSend: (t: string) => void;
  onStop: () => void;
  onRetry: (id: string) => void;
  onRate: (id: string, r: Rating) => void;
  onNotify: (t: string, k?: 'info' | 'error') => void;
}

export const ChatWindow = forwardRef<ComposerHandle, Props>(function ChatWindow(
  { messages, loading, offline, onSend, onStop, onRetry, onRate, onNotify },
  ref
) {
  const scroller = useRef<HTMLDivElement>(null);
  const last = messages[messages.length - 1];
  const sig = last ? `${last.id}:${last.state}` : '';

  useEffect(() => {
    const el = scroller.current;
    if (!el || !last) return;
    const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
    if (last.role === 'assistant' && last.state !== 'pending') {
      // Long answers: bring the START of the new answer into view, not the end
      el.querySelector(`[data-msg-id="${last.id}"]`)?.scrollIntoView({ behavior, block: 'start' });
    } else {
      el.scrollTo({ top: el.scrollHeight, behavior });
    }
  }, [sig]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-slate-50 dark:bg-transparent">
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-4 pt-4 sm:px-6 lg:px-8">
        <div
          role="log"
          aria-live="polite"
          aria-relevant="additions text"
          aria-label="Conversation"
          className="mx-auto max-w-3xl space-y-6 pb-8"
        >
          {messages.map((m) => (
            <ChatMessage
              key={m.id}
              message={m}
              onRetry={onRetry}
              onRate={onRate}
              onAsk={onSend}
              onNotify={onNotify}
              busy={loading}
            />
          ))}
        </div>
      </div>

      {/* Docked Chat Input */}
      <div
        className="shrink-0 bg-gradient-to-t from-slate-50 via-slate-50/95 to-slate-50/30 dark:from-slate-950 dark:via-slate-950/95 dark:to-transparent px-4 pb-4 pt-3 sm:px-6 lg:px-8 border-t border-slate-200/60 dark:border-slate-800"
        style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom))' }}
      >
        <div className="mx-auto max-w-3xl">
          <ChatComposer
            ref={ref}
            onSend={onSend}
            onStop={onStop}
            loading={loading}
            offline={offline}
            variant="dock"
          />
        </div>
      </div>
    </div>
  );
});
