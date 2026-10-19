/**
 * DEV-ONLY mock backend (VITE_USE_MOCK=true). Used to work on the UI without the RAG server.
 * Every response is explicitly labelled and is NOT real JKLU information.
 */
import type { ChatRequest, ChatResponse } from '../types';

const TAG = '**[MOCK DATA: placeholder text, not real JKLU information]**';
const wait = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => { clearTimeout(t); reject(new DOMException('aborted', 'AbortError')); });
  });

export async function mockChat(req: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  try { await wait(900, signal); } catch { const { ApiError } = await import('../api'); throw new ApiError('aborted', 'Request cancelled.'); }
  const q = req.question.toLowerCase();
  const base = { sources: [], suggestions: [], contacts: [], contact_page: null, request_id: 'mock-' + Date.now(), latency_ms: 900, provider: 'mock' };
  if (q.trim().split(/\s+/).length <= 2) {
    return { ...base, status: 'clarify', answer: 'Could you tell me which fee you mean?', clarification: 'Which topic do you mean? (mock)',
      suggestions: [{ label: 'Tuition fee', question: 'What is the tuition fee?' }, { label: 'Hostel fee', question: 'What is the hostel fee?' }] };
  }
  if (q.includes('2030') || q.includes('football')) {
    return { ...base, status: 'escalate', answer: `${TAG}\n\nI couldn't verify this. Please contact the university.`,
      contacts: [{ office: 'Example office (mock)', phone: '+00 000 000 0000', email: 'example@example.invalid' }] };
  }
  return {
    ...base, status: 'answer',
    answer: `${TAG}\n\nThis is a sample answer used while designing the interface [1].\n\n| Item | Example |\n|---|---|\n| Column A | Value A |\n| Column B | Value B |\n\n- First point [1]\n- Second point [2]`,
    sources: [
      { n: 1, title: 'Example source (mock)', url: null, category: 'general', page: 3, academic_year: '2026-27', snippet: 'Placeholder passage used only in mock mode.' },
      { n: 2, title: 'Another example source (mock)', url: null, category: 'general', snippet: 'Second placeholder passage.' },
    ],
  };
}
