import { useCallback, useEffect, useState } from 'react';
import { getCategories, getHealth } from '../api';
import type { CategoryInfo, Health } from '../types';

export function useHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [online, setOnline] = useState<boolean | null>(null);

  const refresh = useCallback(async () => {
    try {
      const h = await getHealth();
      setHealth(h);
      setOnline(h.status === 'ok');
      if (h.status === 'ok') setCategories(await getCategories().catch(() => []));
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => { void refresh(); }, 30_000);
    return () => clearInterval(t);
  }, [refresh]);

  return { health, categories, online, refresh };
}
