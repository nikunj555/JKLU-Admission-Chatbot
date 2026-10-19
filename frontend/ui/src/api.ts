import type { CategoryInfo, ChatRequest, ChatResponse, ChatStatus, Contact, Health, Source, Suggestion } from './types';

const BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '').replace(/\/$/, '');
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
const CHAT_TIMEOUT_MS = 90_000;

export type ApiErrorKind = 'network' | 'timeout' | 'http' | 'invalid' | 'aborted';
export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;
  constructor(kind: ApiErrorKind, message: string, status?: number) {
    super(message);
    this.kind = kind;
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 15_000, external?: AbortSignal): Promise<T> {
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; ctrl.abort(); }, timeoutMs);
  const onAbort = () => ctrl.abort();
  external?.addEventListener('abort', onAbort);
  try {
    const res = await fetch(BASE + path, {
      ...init,
      signal: ctrl.signal,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...(init.headers ?? {}) },
    });
    if (!res.ok) {
      let detail = '';
      try { detail = ((await res.json()) as { detail?: unknown }).detail?.toString() ?? ''; } catch { /* no body */ }
      throw new ApiError('http', detail || `The server responded with an error (${res.status}).`, res.status);
    }
    try {
      return (await res.json()) as T;
    } catch {
      throw new ApiError('invalid', 'The server returned an unreadable response.');
    }
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (timedOut) throw new ApiError('timeout', 'The request took too long. Please try again.');
    if (e instanceof DOMException && e.name === 'AbortError') throw new ApiError('aborted', 'Request cancelled.');
    throw new ApiError('network', 'Cannot reach the assistant server. Make sure it is running (python run.py).');
  } finally {
    clearTimeout(timer);
    external?.removeEventListener('abort', onAbort);
  }
}

/* ---------------------------------------------------------------- validation */
const STATUSES: ChatStatus[] = ['answer', 'clarify', 'escalate', 'smalltalk'];
const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null;
const str = (v: unknown): string | null => (typeof v === 'string' ? v : null);
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

export function parseChatResponse(data: unknown): ChatResponse {
  if (!isObj(data) || typeof data.answer !== 'string' || !STATUSES.includes(data.status as ChatStatus)) {
    throw new ApiError('invalid', 'The server returned an unexpected response format.');
  }
  const sources: Source[] = (Array.isArray(data.sources) ? data.sources : []).filter(isObj).map((s, i) => ({
    n: num(s.n) ?? i + 1,
    title: str(s.title) ?? 'Untitled source',
    url: str(s.url),
    category: str(s.category),
    page: num(s.page),
    page_end: num(s.page_end),
    section: str(s.section),
    academic_year: str(s.academic_year),
    source_type: str(s.source_type),
    snippet: str(s.snippet) ?? undefined,
  }));
  const suggestions: Suggestion[] = (Array.isArray(data.suggestions) ? data.suggestions : []).filter(isObj)
    .map((s) => ({ label: str(s.label) ?? '', question: str(s.question) ?? '' })).filter((s) => s.label && s.question);
  const contacts: Contact[] = (Array.isArray(data.contacts) ? data.contacts : []).filter(isObj)
    .map((c) => ({ office: str(c.office) ?? '', phone: str(c.phone), email: str(c.email) })).filter((c) => c.office);
  return {
    status: data.status as ChatStatus,
    answer: data.answer,
    clarification: str(data.clarification),
    reason: str(data.reason) ?? undefined,
    sources, suggestions, contacts,
    contact_page: str(data.contact_page),
    request_id: str(data.request_id) ?? undefined,
    latency_ms: num(data.latency_ms) ?? undefined,
    provider: str(data.provider),
    query_used: str(data.query_used) ?? undefined,
  };
}

/* ----------------------------------------------------------------- endpoints */
export async function chat(payload: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  if (USE_MOCK) {
    const { mockChat } = await import('./mock/mockApi'); // never bundled when VITE_USE_MOCK is not "true"
    return mockChat(payload, signal);
  }
  return parseChatResponse(await request<unknown>('/api/chat', { method: 'POST', body: JSON.stringify(payload) }, CHAT_TIMEOUT_MS, signal));
}

export async function getHealth(): Promise<Health> {
  if (USE_MOCK) return { status: 'ok', chunks: 0, retrieval: 'mock', llm_provider: 'mock' };
  const h = await request<Partial<Health>>('/api/health');
  return { status: String(h.status ?? 'unavailable'), chunks: Number(h.chunks ?? 0), retrieval: h.retrieval ?? null, llm_provider: h.llm_provider ?? null, error: h.error ?? null };
}

export async function getCategories(): Promise<CategoryInfo[]> {
  if (USE_MOCK) return [];
  const r = await request<{ categories?: CategoryInfo[] }>('/api/categories');
  return (r.categories ?? []).filter((c) => typeof c.name === 'string');
}

export interface FeedbackPayload { request_id?: string; rating?: 'up' | 'down' | null; comment?: string; question?: string; status?: string }
export async function sendFeedback(p: FeedbackPayload): Promise<void> {
  if (USE_MOCK) return;
  await request<unknown>('/api/feedback', { method: 'POST', body: JSON.stringify(p) });
}
