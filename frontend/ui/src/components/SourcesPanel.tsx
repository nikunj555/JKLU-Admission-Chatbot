import { BookOpen, ChevronDown, ExternalLink, FileText } from 'lucide-react';
import { CATEGORY_LABEL } from '../lib/format';
import { safeOfficialUrl } from '../lib/url';
import type { Source } from '../types';

interface Props {
  id: string;
  sources: Source[];
  open: boolean;
  onToggle: () => void;
  highlight: number | null;
}

function pageLabel(s: Source): string | null {
  if (!s.page) return null;
  return s.page_end && s.page_end !== s.page ? `pp. ${s.page}–${s.page_end}` : `p. ${s.page}`;
}

export function SourcesPanel({ id, sources, open, onToggle, highlight }: Props) {
  if (!sources.length) return null;

  const years = sources
    .map((s) => /^(20\d{2})/.exec(s.academic_year ?? '')?.[1])
    .filter(Boolean)
    .map(Number);
  const newest = years.length ? Math.max(...years) : null;

  return (
    <section
      aria-label="Official references and sources"
      className="rounded-2xl border border-slate-200 bg-slate-50/80 dark:border-slate-800 dark:bg-slate-900/60 shadow-subtle overflow-hidden"
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={`${id}-list`}
        className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-sm text-slate-700 transition-colors hover:bg-slate-100/70 dark:hover:bg-slate-800/60"
      >
        <span className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
          <BookOpen size={16} className="text-blue-700 dark:text-blue-400" aria-hidden="true" />
          <span>Official References</span>
          <span className="rounded-full bg-blue-100 dark:bg-blue-950 px-2 py-0.5 text-xs font-semibold text-blue-900 dark:text-blue-300">
            {sources.length}
          </span>
        </span>
        <ChevronDown
          size={16}
          aria-hidden="true"
          className={`text-slate-500 dark:text-slate-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${
          open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
        }`}
      >
        <div className="overflow-hidden">
          <ol id={`${id}-list`} className="space-y-2 px-3 pb-3 pt-1">
            {sources.map((s) => {
              const href = safeOfficialUrl(s.url);
              const local = !href && (s.url ?? '').startsWith('manual:');
              const campusLocal = !href && (s.url ?? '').startsWith('campus:');
              const year = /^(20\d{2})/.exec(s.academic_year ?? '')?.[1];
              const outdated = newest && year && Number(year) < newest;
              const meta = [
                s.category ? CATEGORY_LABEL[s.category] ?? s.category : null,
                pageLabel(s),
                s.academic_year,
              ].filter(Boolean);

              return (
                <li
                  key={s.n}
                  id={`${id}-src-${s.n}`}
                  className={`rounded-xl border p-3 transition-colors duration-300 ${
                    highlight === s.n
                      ? 'border-blue-400 bg-blue-50 dark:border-blue-500 dark:bg-blue-950/70 shadow-subtle'
                      : 'border-slate-200/90 bg-white dark:border-slate-800 dark:bg-slate-900 hover:border-slate-300 dark:hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-blue-100 dark:bg-blue-950 font-mono text-[11px] font-bold text-blue-800 dark:text-blue-300">
                      {s.n}
                    </span>
                    <div className="min-w-0 flex-1 space-y-1">
                      <p className="text-sm font-semibold text-slate-900 dark:text-white">
                        {href ? (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-blue-700 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300 hover:underline"
                          >
                            <span>{s.title}</span>
                            <ExternalLink size={13} aria-hidden="true" className="shrink-0" />
                          </a>
                        ) : (
                          s.title
                        )}
                      </p>

                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                        {meta.map((m, i) => (
                          <span key={i} className="rounded bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 text-slate-600 dark:text-slate-300 font-medium">
                            {m}
                          </span>
                        ))}
                        {outdated && (
                          <span className="rounded-full border border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950 px-2 py-0.5 text-[11px] font-semibold text-amber-800 dark:text-amber-300">
                            may be historical
                          </span>
                        )}
                      </div>

                      {href ? (
                        <p className="break-all font-mono text-[11.5px] text-slate-400 dark:text-slate-500">
                          {href}
                        </p>
                      ) : local || campusLocal ? (
                        <p className="flex items-center gap-1.5 text-[11.5px] text-slate-500 dark:text-slate-400">
                          <FileText size={12} aria-hidden="true" />
                          <span>Official verified university document</span>
                        </p>
                      ) : null}

                      {s.snippet && (
                        <p className="line-clamp-3 text-xs leading-relaxed text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/80 rounded-lg p-2 border border-slate-100 dark:border-slate-800">
                          "{s.snippet}"
                        </p>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}
