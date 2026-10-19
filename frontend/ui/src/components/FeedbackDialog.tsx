import { Send } from 'lucide-react';
import { useState } from 'react';
import { sendFeedback } from '../api';
import { Modal } from './Modal';

export function FeedbackDialog({
  onClose,
  onNotify,
}: {
  onClose: () => void;
  onNotify: (t: string, k?: 'info' | 'error') => void;
}) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!text.trim() || busy) return;
    setBusy(true);
    try {
      await sendFeedback({ comment: text.trim().slice(0, 500) });
      onNotify('Thank you! Your feedback helps improve the JKLU assistant.');
      onClose();
    } catch {
      onNotify('Could not send feedback. Is the server running?', 'error');
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Send Feedback"
      description="Help us improve admission guidance, source citations, or reporting."
      onClose={onClose}
    >
      <label htmlFor="fb" className="sr-only">
        Your feedback
      </label>
      <textarea
        id="fb"
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={500}
        rows={4}
        placeholder="For example: what questions did you find most helpful or what details were missing?"
        className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800 p-3.5 text-xs text-slate-800 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:border-blue-600 focus:bg-white dark:focus:bg-slate-900 focus:outline-none"
      />
      <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
        Feedback is saved locally to improve responses. Please do not submit personal admission documents or sensitive details.
      </p>
      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={submit}
          disabled={!text.trim() || busy}
          className="inline-flex items-center gap-1.5 rounded-xl bg-blue-800 px-4 py-2 text-xs font-semibold text-white shadow-subtle hover:bg-blue-900 disabled:opacity-40 transition-colors"
        >
          <Send size={13} aria-hidden="true" />
          <span>{busy ? 'Sending…' : 'Submit Feedback'}</span>
        </button>
      </div>
    </Modal>
  );
}
