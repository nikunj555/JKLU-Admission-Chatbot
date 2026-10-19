import type { Conversation, Settings } from '../types';

const CONV_KEY = 'jklu.conversations.v1';
const SET_KEY = 'jklu.settings.v1';
const MAX_CONVERSATIONS = 40;

export const DEFAULT_SETTINGS: Settings = { topK: 5, topic: '', theme: 'light' };

function read<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}
function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full or blocked: the app keeps working in memory */
  }
}

export function loadConversations(): Conversation[] {
  const data = read<Conversation[]>(CONV_KEY);
  if (!Array.isArray(data)) return [];
  return data
    .filter((c) => c && typeof c.id === 'string' && Array.isArray(c.messages))
    .map((c) => ({
      ...c,
      // a reload during a request must not leave a spinner behind
      messages: c.messages.map((m) => (m.state === 'pending' ? { ...m, state: 'cancelled' as const, content: '' } : m)),
    }));
}
export function saveConversations(list: Conversation[]): void {
  write(CONV_KEY, list.slice(0, MAX_CONVERSATIONS));
}
export function clearConversations(): void {
  try { localStorage.removeItem(CONV_KEY); } catch { /* ignore */ }
}
export function loadSettings(): Settings {
  const s = read<Partial<Settings>>(SET_KEY) ?? {};
  return {
    topK: typeof s.topK === 'number' ? Math.min(8, Math.max(3, s.topK)) : DEFAULT_SETTINGS.topK,
    topic: typeof s.topic === 'string' ? s.topic : '',
    theme: s.theme === 'dark' || s.theme === 'system' ? s.theme : 'light',
  };
}
export function saveSettings(s: Settings): void { write(SET_KEY, s); }
