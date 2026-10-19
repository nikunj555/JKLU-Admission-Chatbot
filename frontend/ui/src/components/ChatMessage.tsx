import {
  AlertCircle,
  ExternalLink,
  HelpCircle,
  Mail,
  Phone,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { memo, useCallback, useState } from 'react';
import { mailHref, telHref } from '../lib/url';
import type { Message, Rating } from '../types';
import { BrandMark } from './BrandMark';
import { EvidenceStatus } from './EvidenceStatus';
import { FeedbackControls } from './FeedbackControls';
import { MarkdownContent } from './MarkdownContent';
import { SourcesPanel } from './SourcesPanel';

interface Props {
  message: Message;
  onRetry: (id: string) => void;
  onRate: (id: string, r: Rating) => void;
  onAsk: (q: string) => void;
  onNotify: (t: string, k?: 'info' | 'error') => void;
  busy: boolean;
}

// Curated follow-up prompts to suggest after successful responses
const DEFAULT_FOLLOW_UPS = [
  'What documents are required for admission?',
  'What scholarships are available?',
  'What is the next step to apply?',
  'What are the hostel and campus facilities?',
];

function Thinking() {
  return (
    <div role="status" aria-label="Searching official JKLU documents" className="space-y-3 py-1">
      <div className="flex items-center gap-2.5 text-sm font-medium text-slate-600">
        <span className="flex gap-1" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-2 w-2 animate-dots rounded-full bg-blue-700"
              style={{ animationDelay: `${i * 0.16}s` }}
            />
          ))}
        </span>
        <span>Searching official JKLU documents & records…</span>
      </div>
      <div className="space-y-2 pt-1" aria-hidden="true">
        <div className="skeleton h-3.5 w-[90%]" />
        <div className="skeleton h-3.5 w-[75%]" />
        <div className="skeleton h-3.5 w-[50%]" />
      </div>
    </div>
  );
}

export const ChatMessage = memo(function ChatMessage({
  message: m,
  onRetry,
  onRate,
  onAsk,
  onNotify,
  busy,
}: Props) {
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState<number | null>(null);
  const panelId = `msg-${m.id}`;

  const cite = useCallback(
    (n: number) => {
      setOpen(true);
      setHighlight(n);
      setTimeout(() => {
        document.getElementById(`${panelId}-src-${n}`)?.scrollIntoView({
          behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
          block: 'nearest',
        });
      }, 80);
      setTimeout(() => setHighlight(null), 2200);
    },
    [panelId]
  );

  if (m.role === 'user') {
    return (
      <div className="flex justify-end animate-rise" data-msg-id={m.id}>
        <div className="max-w-[85%] sm:max-w-[75%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-blue-900 dark:bg-blue-800 px-4 py-3 text-[15px] leading-relaxed text-white shadow-card">
          {m.content}
        </div>
      </div>
    );
  }

  const res = m.response;

  // Derive 2 to 3 contextual follow-up suggestions
  const followUps =
    res?.suggestions && res.suggestions.length > 0
      ? res.suggestions.slice(0, 3).map((s) => ({ label: s.label, question: s.question }))
      : DEFAULT_FOLLOW_UPS.slice(0, 3).map((q) => ({ label: q, question: q }));

  return (
    <article
      className="flex gap-3 sm:gap-4 animate-rise scroll-mt-24"
      aria-label="Assistant response"
      data-msg-id={m.id}
    >
      <div className="mt-1 shrink-0">
        <BrandMark size={32} />
      </div>

      <div className="min-w-0 flex-1 space-y-3.5">
        {m.state === 'pending' && <Thinking />}

        {(m.state === 'error' || m.state === 'cancelled') && (
          <div
            className="rounded-2xl border border-rose-200 bg-rose-50/70 p-4 shadow-subtle"
            role="alert"
          >
            <p className="flex items-center gap-2 text-sm font-semibold text-rose-800">
              <AlertCircle size={16} aria-hidden="true" />
              <span>{m.state === 'cancelled' ? 'Request cancelled' : 'Could not retrieve answer'}</span>
            </p>
            <p className="mt-1.5 text-sm text-slate-700">
              {m.state === 'cancelled'
                ? 'You stopped this request.'
                : m.error || 'A temporary connection error occurred. Please try again.'}
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() => onRetry(m.id)}
              className="mt-3 inline-flex items-center gap-2 rounded-xl border border-rose-300 bg-white px-3.5 py-1.5 text-xs font-semibold text-rose-800 shadow-subtle hover:bg-rose-50 disabled:opacity-50"
            >
              <RefreshCw size={13} aria-hidden="true" />
              <span>Retry Question</span>
            </button>
          </div>
        )}

        {m.state === 'ok' && res && (
          <div className="rounded-2xl border border-slate-200/90 bg-white dark:border-slate-800 dark:bg-slate-900 p-5 shadow-card space-y-4">
            {/* Status Pill */}
            <div className="flex items-center justify-between">
              <EvidenceStatus status={res.status} sourceCount={res.sources.length} />
              {typeof res.latency_ms === 'number' && res.latency_ms > 0 ? (
                <span className="text-[11px] text-slate-600 dark:text-slate-400 hidden sm:inline">
                  {res.latency_ms} ms
                </span>
              ) : null}
            </div>

            {/* Response Content */}
            {res.status === 'escalate' ? (
              <div className="space-y-4">
                <MarkdownContent text={res.answer.split('\n\n')[0] ?? res.answer} onCite={cite} />

                {/* Guidance to rephrase */}
                <div className="rounded-xl border border-amber-200 bg-amber-50/60 dark:border-amber-900/60 dark:bg-amber-950/40 p-3.5 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
                  <HelpCircle size={16} className="text-amber-700 dark:text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold block text-[13px]">Need help finding this?</span>
                    <span>
                      Try rephrasing with specific university terms (e.g., specific programme names like "B.Tech CSE", "scholarships", "hostel rules", or "faculty"). Alternatively, contact the admissions team directly below.
                    </span>
                  </div>
                </div>

                {/* Verified University Contacts */}
                {res.contacts.length > 0 && (
                  <ul className="grid gap-2.5 sm:grid-cols-2" aria-label="Official contacts">
                    {res.contacts.map((c) => {
                      const mail = c.email ? mailHref(c.email) : null;
                      return (
                        <li
                          key={c.office}
                          className="rounded-xl border border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/60 p-3.5 space-y-1.5"
                        >
                          <p className="text-sm font-semibold text-slate-900 dark:text-white">{c.office}</p>
                          <div className="space-y-1 text-xs">
                            {c.phone && (
                              <a
                                href={telHref(c.phone)}
                                className="flex items-center gap-1.5 text-blue-700 dark:text-blue-400 hover:underline"
                              >
                                <Phone size={13} className="text-slate-500 dark:text-slate-400" />
                                <span className="font-mono">{c.phone}</span>
                              </a>
                            )}
                            {c.email && (
                              <a
                                href={mail ?? '#'}
                                className="flex items-center gap-1.5 text-blue-700 dark:text-blue-400 hover:underline break-all"
                              >
                                <Mail size={13} className="text-slate-500 dark:text-slate-400 shrink-0" />
                                <span>{c.email}</span>
                              </a>
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}

                {/* Direct Link to Verified Admissions Portal */}
                <div className="pt-1">
                  <a
                    href="https://jklu.edu.in/admissions/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-xl bg-blue-800 px-4 py-2 text-xs font-semibold text-white shadow-subtle hover:bg-blue-900 transition-colors"
                  >
                    <span>Visit Official JKLU Admissions Portal</span>
                    <ExternalLink size={13} aria-hidden="true" />
                  </a>
                </div>
              </div>
            ) : res.status === 'clarify' ? (
              <div className="space-y-3.5">
                <MarkdownContent text={res.clarification || res.answer} onCite={cite} />
                {res.suggestions.length > 0 && (
                  <div className="space-y-2 pt-1">
                    <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Please choose an option or clarify:
                    </p>
                    <div className="flex flex-wrap gap-2" role="group" aria-label="Clarification options">
                      {res.suggestions.map((s) => (
                        <button
                          key={s.label}
                          type="button"
                          disabled={busy}
                          onClick={() => onAsk(s.question)}
                          className="chip"
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <MarkdownContent text={res.answer} onCite={cite} />
            )}

            {/* Official References Section */}
            {res.sources.length > 0 && res.status !== 'smalltalk' && (
              <SourcesPanel
                id={panelId}
                sources={res.sources}
                open={open}
                onToggle={() => setOpen((o) => !o)}
                highlight={highlight}
              />
            )}

            {/* Follow-up Suggestions & Feedback Controls */}
            {res.status !== 'smalltalk' && (
              <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                {/* Follow-up Suggestions Chips */}
                {followUps.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5" aria-label="Suggested follow-up questions">
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide mr-1">
                      <Sparkles size={11} className="text-blue-800 dark:text-blue-400" />
                      <span>Next steps:</span>
                    </span>
                    {followUps.map((fu) => (
                      <button
                        key={fu.question}
                        type="button"
                        disabled={busy}
                        onClick={() => onAsk(fu.question)}
                        className="inline-flex items-center rounded-lg border border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-800 px-2.5 py-1 text-xs text-slate-700 dark:text-slate-300 transition-colors hover:border-blue-400 hover:bg-blue-50 hover:text-blue-900 dark:hover:border-blue-500 dark:hover:bg-slate-700 dark:hover:text-white disabled:opacity-50"
                      >
                        {fu.label}
                      </button>
                    ))}
                  </div>
                )}

                {/* Actions: Copy & Rating */}
                <div className="self-end sm:self-auto">
                  <FeedbackControls
                    text={m.content}
                    rating={m.rating}
                    onRate={(r) => onRate(m.id, r)}
                    onNotify={onNotify}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </article>
  );
});
