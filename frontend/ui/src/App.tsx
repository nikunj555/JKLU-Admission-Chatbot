import {
  AlertTriangle,
  MessageSquarePlus,
  PanelLeft,
  RefreshCw,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { USE_MOCK } from './api';
import { AppSidebar, QUICK_ACCESS_TOPICS } from './components/AppSidebar';
import { BrandMark } from './components/BrandMark';
import { ChatWindow } from './components/ChatWindow';
import type { ComposerHandle } from './components/ChatComposer';
import { FeedbackDialog } from './components/FeedbackDialog';
import { Modal } from './components/Modal';
import { SettingsDialog } from './components/SettingsDialog';
import { Toasts } from './components/Toasts';
import { WelcomeScreen } from './components/WelcomeScreen';
import { useChat } from './hooks/useChat';
import { useHealth } from './hooks/useHealth';
import { useSettings } from './hooks/useSettings';
import { useToasts } from './hooks/useToasts';

export default function App() {
  const { settings, update } = useSettings();
  const { toasts, push, dismiss } = useToasts();
  const chat = useChat(settings, push);
  const { health, categories, online, refresh } = useHealth();
  const composer = useRef<ComposerHandle>(null);

  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 1024);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [confirmNewChat, setConfirmNewChat] = useState(false);

  const messages = chat.active?.messages ?? [];
  const hasChat = messages.length > 0;

  // Global keyboard shortcuts: "/" focuses composer, "Escape" closes sidebar on small screens
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (
        e.key === '/' &&
        !e.ctrlKey &&
        !e.metaKey &&
        !/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) &&
        !t.isContentEditable
      ) {
        e.preventDefault();
        composer.current?.focus();
      }
      if (e.key === 'Escape' && window.innerWidth < 1024) {
        setSidebarOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const send = useCallback(
    (q: string) => {
      chat.send(q);
    },
    [chat]
  );

  const handleNewChatClick = useCallback(() => {
    if (hasChat) {
      setConfirmNewChat(true);
    } else {
      chat.newChat();
      setTimeout(() => composer.current?.focus(), 50);
    }
  }, [hasChat, chat]);

  const confirmStartNewChat = useCallback(() => {
    chat.newChat();
    setConfirmNewChat(false);
    setTimeout(() => composer.current?.focus(), 50);
  }, [chat]);

  return (
    <div className="relative h-full overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex">

      {/* Sidebar */}
      <AppSidebar
        open={sidebarOpen}
        conversations={chat.conversations}
        activeId={chat.activeId}
        busy={chat.loading}
        onClose={() => setSidebarOpen(false)}
        onNew={handleNewChatClick}
        onSelect={chat.select}
        onDelete={chat.remove}
        onAsk={send}
        onSettings={() => setSettingsOpen(true)}
        onFeedback={() => setFeedbackOpen(true)}
      />

      {/* Main Content Area */}
      <main className="relative z-10 flex min-w-0 flex-1 flex-col h-full overflow-hidden" id="main">
        {/* Compact University Top Header */}
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white/90 dark:border-slate-800 dark:bg-slate-900/90 backdrop-blur-sm px-3 sm:px-5">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setSidebarOpen((o) => !o)}
              className="btn-icon h-9 w-9 text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
              aria-label={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
              aria-expanded={sidebarOpen}
            >
              <PanelLeft size={18} />
            </button>

            <div className="flex items-center gap-2 min-w-0">
              <BrandMark size={24} />
              <div className="truncate">
                <span className="font-bold text-sm text-slate-900 dark:text-white">JKLU Admission Assistant</span>
                {hasChat && chat.active?.title && (
                  <span className="text-xs text-slate-600 dark:text-slate-400 hidden md:inline ml-2 truncate">
                    — {chat.active.title}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {hasChat && (
              <button
                type="button"
                onClick={handleNewChatClick}
                className="hidden sm:inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                title="Start a new chat"
              >
                <MessageSquarePlus size={14} className="text-blue-800 dark:text-blue-400" />
                <span>New Chat</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => void refresh()}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                online
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 dark:border-emerald-900/60 dark:bg-emerald-950/60 dark:text-emerald-300'
                  : online === false
                  ? 'border-rose-200 bg-rose-50 text-rose-800 hover:bg-rose-100 dark:border-rose-900/60 dark:bg-rose-950/60 dark:text-rose-300'
                  : 'border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-400'
              }`}
              aria-label="Knowledge base status. Click to refresh."
              title="Click to refresh status"
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  online ? 'bg-emerald-600' : online === false ? 'bg-rose-600' : 'bg-slate-400'
                }`}
                aria-hidden="true"
              />
              <span className="hidden sm:inline">
                {online === null
                  ? 'Connecting…'
                  : online
                  ? health?.chunks
                    ? `Knowledge base online · ${health.chunks.toLocaleString()} verified passages`
                    : 'Online'
                  : 'Server offline'}
              </span>
              <span className="sm:hidden">{online ? 'Online' : 'Offline'}</span>
            </button>
          </div>
        </header>

        {/* Quick-Access Strip in Active Chat */}
        {hasChat && (
          <div
            className="flex items-center gap-1.5 overflow-x-auto border-b border-slate-200 bg-slate-50/90 dark:border-slate-800 dark:bg-slate-900/90 backdrop-blur-sm px-4 py-1.5 scrollbar-none"
            aria-label="Quick admission shortcuts"
          >
            <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide shrink-0 mr-1 hidden sm:inline">
              Quick access:
            </span>
            {QUICK_ACCESS_TOPICS.map(({ label, q }) => (
              <button
                key={label}
                type="button"
                disabled={chat.loading}
                onClick={() => send(q)}
                className="shrink-0 rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-300 hover:border-blue-400 hover:bg-blue-50 hover:text-blue-900 dark:hover:border-blue-600 dark:hover:bg-slate-700 dark:hover:text-white transition-colors disabled:opacity-50"
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {/* Mock Notice */}
        {USE_MOCK && (
          <div
            role="alert"
            className="mx-4 mt-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-2 text-center text-xs text-amber-900"
          >
            Mock mode active: responses are UI placeholders.
          </div>
        )}

        {/* Server Offline Alert */}
        {online === false && !USE_MOCK && (
          <div
            role="alert"
            className="mx-4 mt-2 flex flex-wrap items-center justify-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-800"
          >
            <span className="inline-flex items-center gap-1.5 font-medium">
              <AlertTriangle size={14} aria-hidden="true" />
              Cannot reach the assistant backend. Start it with <code className="font-mono bg-white px-1 py-0.5 rounded border border-rose-200">python run.py</code>.
            </span>
            <button
              type="button"
              onClick={() => void refresh()}
              className="inline-flex items-center gap-1 rounded-lg border border-rose-300 bg-white px-2 py-0.5 font-semibold hover:bg-rose-100"
            >
              <RefreshCw size={11} aria-hidden="true" />
              <span>Retry</span>
            </button>
          </div>
        )}

        {/* Main Chat / Landing Screen */}
        {hasChat ? (
          <ChatWindow
            ref={composer}
            messages={messages}
            loading={chat.loading}
            offline={online === false}
            onSend={send}
            onStop={chat.stop}
            onRetry={chat.retry}
            onRate={chat.rate}
            onNotify={push}
          />
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <WelcomeScreen
              ref={composer}
              onSend={send}
              onStop={chat.stop}
              loading={chat.loading}
              offline={online === false}
            />
          </div>
        )}
      </main>

      {/* New Chat Confirmation Dialog */}
      {confirmNewChat && (
        <Modal
          title="Start a new chat?"
          description="Your current conversation will remain saved in Recent Chats on the sidebar."
          onClose={() => setConfirmNewChat(false)}
        >
          <div className="space-y-4 pt-2">
            <p className="text-xs text-slate-600 dark:text-slate-400">
              You can return to your previous questions anytime by selecting them from the sidebar.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmNewChat(false)}
                className="rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 px-3.5 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700"
              >
                Continue Current Chat
              </button>
              <button
                type="button"
                onClick={confirmStartNewChat}
                className="rounded-xl bg-blue-800 px-4 py-2 text-xs font-semibold text-white shadow-subtle hover:bg-blue-900"
              >
                Start New Chat
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Settings Dialog */}
      {settingsOpen && (
        <SettingsDialog
          settings={settings}
          onChange={update}
          categories={categories}
          health={health}
          online={online}
          conversationCount={chat.conversations.length}
          onClearAll={() => {
            chat.clearAll();
            push('All conversations cleared.');
          }}
          onClose={() => setSettingsOpen(false)}
        />
      )}

      {/* Feedback Dialog */}
      {feedbackOpen && (
        <FeedbackDialog onClose={() => setFeedbackOpen(false)} onNotify={push} />
      )}

      {/* Toast Notifications */}
      <Toasts toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}
