/** Mirrors the real backend contract (jklu/agent.py -> JKLUAgent.ask). */
export type ChatStatus = 'answer' | 'clarify' | 'escalate' | 'smalltalk';

export interface Source {
  n: number;
  title: string;
  url: string | null;
  category?: string | null;
  page?: number | null;
  page_end?: number | null;
  section?: string | null;
  academic_year?: string | null;
  source_type?: string | null;
  snippet?: string;
}
export interface Suggestion { label: string; question: string }
export interface Contact { office: string; phone: string | null; email: string | null }

export interface ChatResponse {
  status: ChatStatus;
  answer: string;
  clarification?: string | null;
  reason?: string;
  sources: Source[];
  suggestions: Suggestion[];
  contacts: Contact[];
  contact_page?: string | null;
  request_id?: string;
  latency_ms?: number;
  provider?: string | null;
  query_used?: string;
}

export interface ChatRequest {
  question: string;
  category: string | null;
  top_k: number;
  history: { role: 'user' | 'assistant'; content: string }[];
}

export type MessageState = 'ok' | 'pending' | 'error' | 'cancelled';
export type Rating = 'up' | 'down';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: number;
  state: MessageState;
  response?: ChatResponse;
  /** The user question that produced this assistant message (for retry). */
  question?: string;
  error?: string;
  rating?: Rating | null;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
}

export interface Health { status: string; chunks: number; retrieval: string | null; llm_provider: string | null; error?: string | null }
export interface CategoryInfo { name: string; chunks: number }

export interface Settings {
  topK: number;
  topic: string;      // '' = all topics
  theme: 'light' | 'dark' | 'system';
}
