import { Check, Copy, ThumbsDown, ThumbsUp } from 'lucide-react';
import { useState } from 'react';
import { copyText } from '../lib/format';
import type { Rating } from '../types';

interface Props {
  text: string;
  rating?: Rating | null;
  onRate: (r: Rating) => void;
  onNotify: (t: string, k?: 'info' | 'error') => void;
}

export function FeedbackControls({ text, rating, onRate, onNotify }: Props) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (await copyText(text)) {
      setCopied(true);
      onNotify('Answer copied to clipboard.');
      setTimeout(() => setCopied(false), 1800);
    } else {
      onNotify('Could not copy. Select the text manually.', 'error');
    }
  }

  const base =
    'inline-flex items-center justify-center h-8 w-8 rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 disabled:opacity-40';

  return (
    <div className="flex items-center gap-1 pt-1" role="group" aria-label="Answer actions">
      <button
        type="button"
        onClick={copy}
        className={base}
        aria-label="Copy answer"
        title={copied ? 'Copied' : 'Copy answer'}
      >
        {copied ? <Check size={15} className="text-emerald-600" /> : <Copy size={15} />}
      </button>
      <button
        type="button"
        onClick={() => onRate('up')}
        aria-pressed={rating === 'up'}
        className={`${base} ${rating === 'up' ? '!bg-emerald-50 !text-emerald-700 font-semibold' : ''}`}
        aria-label="Helpful"
        title="Helpful"
      >
        <ThumbsUp size={15} />
      </button>
      <button
        type="button"
        onClick={() => onRate('down')}
        aria-pressed={rating === 'down'}
        className={`${base} ${rating === 'down' ? '!bg-rose-50 !text-rose-700 font-semibold' : ''}`}
        aria-label="Not helpful"
        title="Not helpful"
      >
        <ThumbsDown size={15} />
      </button>
    </div>
  );
}
