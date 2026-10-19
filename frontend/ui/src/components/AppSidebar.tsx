import {
  Award,
  BookOpen,
  Building2,
  CalendarDays,
  FileCheck2,
  GraduationCap,
  MessageCircleHeart,
  MessageSquarePlus,
  MessageSquareText,
  Search,
  Settings as Cog,
  Trash2,
  Users,
  Wallet,
  X,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { relativeTime } from '../lib/format';
import type { Conversation } from '../types';
import { BrandMark } from './BrandMark';

export const QUICK_ACCESS_TOPICS = [
  { Icon: GraduationCap, label: 'Admissions', q: 'What is the admission process for JKLU?' },
  { Icon: BookOpen, label: 'Courses', q: 'What programmes and courses are offered at JKLU?' },
  { Icon: FileCheck2, label: 'Eligibility', q: 'What are the eligibility criteria for B.Tech and other programmes?' },
  { Icon: Wallet, label: 'Fees', q: 'What is the complete fee structure and tuition fees?' },
  { Icon: Award, label: 'Scholarships', q: 'What merit scholarships and financial aid are available?' },
  { Icon: CalendarDays, label: 'Important dates', q: 'What are the important admission deadlines and academic dates?' },
  { Icon: Users, label: 'Faculty', q: 'Who are the faculty members in the CSE department at JKLU?' },
  { Icon: Building2, label: 'Campus life', q: 'What are the hostel and campus facilities like?' },
];

interface Props {
  open: boolean;
  conversations: Conversation[];
  activeId: string | null;
  busy: boolean;
  onClose: () => void;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onAsk: (q: string) => void;
  onSettings: () => void;
  onFeedback: () => void;
}

export function AppSidebar({
  open,
  conversations,
  activeId,
  busy,
  onClose,
  onNew,
  onSelect,
  onDelete,
  onAsk,
  onSettings,
  onFeedback,
}: Props) {
  const [query, setQuery] = useState('');

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);
    return q
      ? list.filter(
          (c) =>
            c.title.toLowerCase().includes(q) ||
            c.messages.some((m) => m.content.toLowerCase().includes(q))
        )
      : list;
  }, [conversations, query]);

  const closeIfMobile = () => {
    if (window.innerWidth < 768) onClose();
  };

  const inertProps = open ? {} : ({ inert: '' } as object);

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 animate-fade bg-slate-900/40 backdrop-blur-sm md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        aria-label="Sidebar navigation"
        {...inertProps}
        className={`fixed inset-y-0 left-0 z-40 flex w-[19rem] max-w-[85vw] shrink-0 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 transition-transform duration-300 ease-out md:static md:z-20 ${
          open ? 'translate-x-0 md:ml-0' : '-translate-x-full md:translate-x-0 md:-ml-[19rem]'
        }`}
      >
        {/* Brand Header */}
        <div className="flex items-center justify-between px-5 pb-3.5 pt-5 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <BrandMark size={32} />
            <div className="leading-tight">
              <p className="text-[15px] font-bold tracking-tight text-slate-900 dark:text-white">
                JKLU Assistant
              </p>
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Admissions Portal
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn-icon h-8 w-8 md:hidden dark:text-slate-400 dark:hover:text-white"
            aria-label="Close sidebar"
          >
            <X size={18} />
          </button>
        </div>

        {/* Action Buttons */}
        <div className="space-y-2.5 px-4 pt-3">
          <button
            type="button"
            onClick={() => {
              onNew();
              closeIfMobile();
            }}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-800 px-4 py-2.5 text-xs font-semibold text-white shadow-subtle transition-all hover:bg-blue-900 active:scale-98"
          >
            <MessageSquarePlus size={16} aria-hidden="true" />
            <span>New Chat</span>
          </button>

          <div className="relative">
            <Search
              size={14}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <label htmlFor="conv-search" className="sr-only">
              Search conversations
            </label>
            <input
              id="conv-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search conversations…"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/80 py-2 pl-9 pr-3 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:border-blue-600 focus:bg-white dark:focus:bg-slate-800 focus:outline-none"
            />
          </div>
        </div>

        {/* Scrollable Navigation: Quick Access & Recent Chats */}
        <nav
          aria-label="Quick access and conversations"
          className="mt-3 min-h-0 flex-1 space-y-5 overflow-y-auto px-3 pb-3"
        >
          {/* Quick Access Admission Shortcuts */}
          <section aria-label="Quick-access admission topics">
            <h2 className="px-2 pb-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
              Admission Quick-Access
            </h2>
            <ul className="space-y-0.5">
              {QUICK_ACCESS_TOPICS.map(({ Icon, label, q }) => (
                <li key={label}>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      onAsk(q);
                      closeIfMobile();
                    }}
                    className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-1.5 text-left text-xs font-medium text-slate-700 dark:text-slate-300 transition-colors hover:bg-blue-50 dark:hover:bg-slate-800 hover:text-blue-900 dark:hover:text-blue-300 disabled:opacity-50"
                  >
                    <Icon size={14} className="text-blue-700 dark:text-blue-400 shrink-0" aria-hidden="true" />
                    <span className="truncate">{label}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          {/* Recent Conversations */}
          <section aria-label="Recent conversations">
            <h2 className="px-2 pb-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
              Recent Chats
            </h2>
            {shown.length === 0 ? (
              <p className="px-2 py-2 text-xs text-slate-600 dark:text-slate-400">
                {query ? 'No matching conversations.' : 'Your chat history will appear here.'}
              </p>
            ) : (
              <ul className="space-y-1">
                {shown.map((c) => (
                  <li
                    key={c.id}
                    className={`group relative rounded-xl transition-colors ${
                      c.id === activeId ? 'bg-blue-50 dark:bg-blue-950/60 font-medium' : 'hover:bg-slate-100 dark:hover:bg-slate-800/60'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        onSelect(c.id);
                        closeIfMobile();
                      }}
                      aria-current={c.id === activeId ? 'true' : undefined}
                      className="flex w-full items-start gap-2.5 rounded-xl px-2.5 py-2 pr-8 text-left"
                    >
                      <MessageSquareText
                        size={14}
                        className={`mt-0.5 shrink-0 ${
                          c.id === activeId ? 'text-blue-800 dark:text-blue-400' : 'text-slate-500 dark:text-slate-400'
                        }`}
                        aria-hidden="true"
                      />
                      <span className="min-w-0">
                        <span
                          className={`block truncate text-xs ${
                            c.id === activeId ? 'text-blue-950 dark:text-blue-200 font-semibold' : 'text-slate-800 dark:text-slate-200'
                          }`}
                        >
                          {c.title}
                        </span>
                        <span className="block text-[10.5px] text-slate-600 dark:text-slate-400">
                          {relativeTime(c.updatedAt)}
                        </span>
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(c.id)}
                      aria-label={`Delete conversation: ${c.title}`}
                      className="btn-icon absolute right-1.5 top-2 h-6 w-6 opacity-0 focus-visible:opacity-100 group-hover:opacity-100 hover:text-rose-600 dark:hover:text-rose-400 dark:text-slate-400"
                    >
                      <Trash2 size={13} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </nav>

        {/* Footer Actions */}
        <div className="border-t border-slate-200 dark:border-slate-800 p-3 flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
          <button
            type="button"
            onClick={onSettings}
            className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors"
          >
            <Cog size={14} />
            <span>Settings</span>
          </button>
          <button
            type="button"
            onClick={onFeedback}
            className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors"
          >
            <MessageCircleHeart size={14} />
            <span>Feedback</span>
          </button>
        </div>
      </aside>
    </>
  );
}
