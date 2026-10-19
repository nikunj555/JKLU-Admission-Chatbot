import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, chat, sendFeedback } from '../api';
import { uid } from '../lib/format';
import { clearConversations, loadConversations, saveConversations } from '../lib/storage';
import type { ChatResponse, ChatStatus, Conversation, Message, Rating, Settings } from '../types';

/** The text a user sees (and copies) for a response. */
export function visibleText(res: ChatResponse): string {
  if (res.status === 'clarify') return res.clarification || res.answer;
  if (res.status === 'escalate') {
    const lines = [res.answer.split('\n\n')[0] ?? ''];
    res.contacts.forEach((c) => lines.push(`${c.office}: ${[c.phone, c.email].filter(Boolean).join(' | ')}`));
    if (res.contact_page) lines.push(res.contact_page);
    return lines.join('\n');
  }
  return res.answer;
}

function buildHistory(messages: Message[]): { role: 'user' | 'assistant'; content: string }[] {
  return messages
    .filter((m) => m.state === 'ok' && m.content.trim())
    .slice(-8)
    .map((m) => ({ role: m.role, content: m.content.slice(0, 1500) }));
}
const makeTitle = (q: string) => (q.length > 54 ? q.slice(0, 52).trimEnd() + '…' : q);

export function useChat(settings: Settings, notify: (text: string, kind?: 'info' | 'error') => void) {
  const [conversations, setConversations] = useState<Conversation[]>(() => loadConversations());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastResult, setLastResult] = useState<{ status: ChatStatus; nonce: number } | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const loadingRef = useRef(false);
  const convRef = useRef(conversations);
  const activeRef = useRef(activeId);
  const settingsRef = useRef(settings);
  convRef.current = conversations;
  activeRef.current = activeId;
  settingsRef.current = settings;

  useEffect(() => {
    saveConversations(conversations.map((c) => ({ ...c, messages: c.messages.filter((m) => m.state !== 'pending') })));
  }, [conversations]);

  const patchMessage = useCallback((convId: string, msgId: string, patch: Partial<Message>) => {
    setConversations((prev) => prev.map((c) => (c.id !== convId ? c : {
      ...c, updatedAt: Date.now(), messages: c.messages.map((m) => (m.id === msgId ? { ...m, ...patch } : m)),
    })));
  }, []);

  const run = useCallback(async (convId: string, pendingId: string, question: string, history: ReturnType<typeof buildHistory>) => {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    loadingRef.current = true;
    setLoading(true);
    try {
      const s = settingsRef.current;
      const res = await chat({ question, category: s.topic || null, top_k: s.topK, history }, ctrl.signal);
      patchMessage(convId, pendingId, { state: 'ok', content: visibleText(res), response: res, error: undefined, rating: null });
      setLastResult({ status: res.status, nonce: Date.now() });
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError('network', 'Something went wrong. Please try again.');
      patchMessage(convId, pendingId, { state: err.kind === 'aborted' ? 'cancelled' : 'error', content: '', error: err.message });
      setLastResult(null);
    } finally {
      loadingRef.current = false;
      abortRef.current = null;
      setLoading(false);
    }
  }, [patchMessage]);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const send = useCallback((raw: string) => {
    const text = raw.trim().slice(0, 600);
    if (!text || loadingRef.current) return;
    const now = Date.now();
    const isNew = !activeRef.current;
    const convId = activeRef.current ?? uid();
    const existing = convRef.current.find((c) => c.id === convId);
    const history = buildHistory(existing?.messages ?? []);
    const userMsg: Message = { id: uid(), role: 'user', content: text, createdAt: now, state: 'ok' };
    const pending: Message = { id: uid(), role: 'assistant', content: '', createdAt: now, state: 'pending', question: text };
    setConversations((prev) => isNew
      ? [{ id: convId, title: makeTitle(text), createdAt: now, updatedAt: now, messages: [userMsg, pending] }, ...prev]
      : prev.map((c) => (c.id === convId ? { ...c, updatedAt: now, messages: [...c.messages, userMsg, pending] } : c)));
    setActiveId(convId);
    void run(convId, pending.id, text, history);
  }, [run]);

  const retry = useCallback((messageId: string) => {
    if (loadingRef.current) return;
    const convId = activeRef.current;
    const conv = convRef.current.find((c) => c.id === convId);
    const idx = conv?.messages.findIndex((m) => m.id === messageId) ?? -1;
    if (!conv || idx < 0) return;
    const msg = conv.messages[idx];
    const question = msg.question ?? conv.messages[idx - 1]?.content ?? '';
    if (!question) return;
    const history = buildHistory(conv.messages.slice(0, Math.max(0, idx - 1)));
    patchMessage(conv.id, msg.id, { state: 'pending', error: undefined, content: '' });
    void run(conv.id, msg.id, question, history);
  }, [patchMessage, run]);

  const newChat = useCallback(() => { stop(); setActiveId(null); setLastResult(null); }, [stop]);
  const select = useCallback((id: string) => { stop(); setActiveId(id); setLastResult(null); }, [stop]);
  const remove = useCallback((id: string) => {
    if (activeRef.current === id) { stop(); setActiveId(null); }
    setConversations((prev) => prev.filter((c) => c.id !== id));
  }, [stop]);
  const clearAll = useCallback(() => { stop(); setActiveId(null); setConversations([]); clearConversations(); }, [stop]);

  const rate = useCallback((messageId: string, rating: Rating) => {
    const convId = activeRef.current;
    const conv = convRef.current.find((c) => c.id === convId);
    const msg = conv?.messages.find((m) => m.id === messageId);
    if (!conv || !msg) return;
    const next = msg.rating === rating ? null : rating;
    patchMessage(conv.id, msg.id, { rating: next });
    if (next) {
      sendFeedback({ request_id: msg.response?.request_id, rating: next, question: msg.question, status: msg.response?.status })
        .then(() => notify('Thanks for the feedback.'))
        .catch(() => notify('Could not send feedback right now.', 'error'));
    }
  }, [notify, patchMessage]);

  const active = conversations.find((c) => c.id === activeId) ?? null;
  return { conversations, active, activeId, loading, lastResult, send, retry, stop, newChat, select, remove, clearAll, rate };
}
