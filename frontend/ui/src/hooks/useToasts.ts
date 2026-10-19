import { useCallback, useState } from 'react';
import { uid } from '../lib/format';

export interface Toast { id: string; text: string; kind: 'info' | 'error' }

export function useToasts() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = useCallback((id: string) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const push = useCallback((text: string, kind: 'info' | 'error' = 'info') => {
    const id = uid();
    setToasts((t) => [...t.slice(-2), { id, text, kind }]);
    setTimeout(() => dismiss(id), 4200);
  }, [dismiss]);
  return { toasts, push, dismiss };
}
