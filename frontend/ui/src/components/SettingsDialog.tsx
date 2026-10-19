import { Laptop, Moon, Sun, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { CATEGORY_LABEL } from '../lib/format';
import type { CategoryInfo, Health, Settings } from '../types';
import { Modal } from './Modal';

interface Props {
  settings: Settings;
  onChange: (p: Partial<Settings>) => void;
  categories: CategoryInfo[];
  health: Health | null;
  online: boolean | null;
  conversationCount: number;
  onClearAll: () => void;
  onClose: () => void;
}

export function SettingsDialog({
  settings,
  onChange,
  categories,
  health,
  online,
  conversationCount,
  onClearAll,
  onClose,
}: Props) {
  const [confirm, setConfirm] = useState(false);
  const row = 'flex items-center justify-between gap-4 py-3.5';

  return (
    <Modal title="Preferences & System Status" description="Settings are stored in this browser only." onClose={onClose}>
      <div className="divide-y divide-slate-100 dark:divide-slate-800">
        {/* Appearance Section */}
        <div className="space-y-3 pb-4">
          <label className="text-sm font-semibold text-slate-900 dark:text-white block">
            Appearance
          </label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { id: 'light', label: 'Light', Icon: Sun },
              { id: 'dark', label: 'Dark', Icon: Moon },
              { id: 'system', label: 'System', Icon: Laptop },
            ].map(({ id, label, Icon }) => {
              const active = settings.theme === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => onChange({ theme: id as 'light' | 'dark' | 'system' })}
                  className={`flex flex-col items-center justify-center gap-1.5 rounded-xl border p-2.5 text-xs font-medium transition-all ${
                    active
                      ? 'border-blue-600 bg-blue-50/90 font-semibold text-blue-900 shadow-sm dark:border-blue-500 dark:bg-blue-950/70 dark:text-blue-200'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-800/60 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:border-slate-700'
                  }`}
                >
                  <Icon size={18} className={active ? 'text-blue-700 dark:text-blue-400' : 'text-slate-500 dark:text-slate-400'} />
                  <span>{label}</span>
                </button>
              );
            })}
          </div>

        </div>

        {/* Retrieval Parameters */}
        <div className="space-y-2 py-4">
          <div className="flex items-center justify-between text-sm">
            <label htmlFor="set-k" className="font-medium text-slate-800 dark:text-slate-200">
              Passages to retrieve
            </label>
            <span className="rounded-md border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800 px-2 py-0.5 font-mono text-xs font-semibold text-blue-800 dark:text-blue-300">
              {settings.topK}
            </span>
          </div>
          <input
            id="set-k"
            type="range"
            min={3}
            max={8}
            value={settings.topK}
            onChange={(e) => onChange({ topK: Number(e.target.value) })}
            className="w-full accent-blue-700"
          />
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Fewer passages provide concise answers; more passages cover broad topics.
          </p>
        </div>

        <div className={row}>
          <label htmlFor="set-topic" className="text-sm font-medium text-slate-800 dark:text-slate-200">
            Limit search topic
          </label>
          <select
            id="set-topic"
            value={settings.topic}
            onChange={(e) => onChange({ topic: e.target.value })}
            className="w-48 rounded-xl border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800 px-3 py-1.5 text-xs text-slate-800 dark:text-slate-200 focus:border-blue-600 focus:bg-white dark:focus:bg-slate-900 focus:outline-none"
          >
            <option value="">All topics</option>
            {categories.map((c) => (
              <option key={c.name} value={c.name} disabled={!c.chunks}>
                {CATEGORY_LABEL[c.name] ?? c.name} ({c.chunks})
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2 py-4 text-sm">
          <p className="font-semibold text-slate-900 dark:text-white">Knowledge Base Status</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-xs text-slate-600 dark:text-slate-400">
            <dt className="font-medium text-slate-500 dark:text-slate-400">Server status</dt>
            <dd className={online ? 'text-emerald-700 dark:text-emerald-400 font-semibold' : online === false ? 'text-rose-700 dark:text-rose-400 font-semibold' : ''}>
              {online === null ? 'checking…' : online ? 'online & verified' : 'offline'}
            </dd>
            <dt className="font-medium text-slate-500 dark:text-slate-400">Indexed passages</dt>
            <dd className="font-mono text-slate-800 dark:text-slate-200 font-medium">
              {health?.chunks?.toLocaleString() ?? '–'}
            </dd>
            <dt className="font-medium text-slate-500 dark:text-slate-400">Retrieval engine</dt>
            <dd className="text-slate-800 dark:text-slate-200">
              {health?.retrieval === 'semantic+bm25'
                ? 'Semantic (MiniLM) + BM25 Lexical'
                : health?.retrieval ?? '–'}
            </dd>
            <dt className="font-medium text-slate-500 dark:text-slate-400">Answer mode</dt>
            <dd className="text-slate-800 dark:text-slate-200">
              {health?.llm_provider && health.llm_provider !== 'none'
                ? `AI-grounded (${health.llm_provider})`
                : 'Direct official document extraction'}
            </dd>
          </dl>
        </div>

        <div className="pt-4">
          {!confirm ? (
            <button
              type="button"
              disabled={conversationCount === 0}
              onClick={() => setConfirm(true)}
              className="inline-flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:border-rose-900/60 dark:bg-rose-950/50 px-3.5 py-2 text-xs font-semibold text-rose-700 dark:text-rose-300 transition-colors hover:bg-rose-100 dark:hover:bg-rose-900/60 disabled:opacity-40"
            >
              <Trash2 size={13} aria-hidden="true" />
              <span>Clear all chat history ({conversationCount})</span>
            </button>
          ) : (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-rose-800 dark:text-rose-300">
                Are you sure? All stored conversations will be permanently deleted from this browser.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    onClearAll();
                    setConfirm(false);
                    onClose();
                  }}
                  className="rounded-xl bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white shadow-subtle hover:bg-rose-700"
                >
                  Yes, delete all
                </button>
                <button
                  type="button"
                  onClick={() => setConfirm(false)}
                  className="rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
