export function uid(): string {
  return (crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36));
}
export function relativeTime(ts: number): string {
  const s = Math.max(1, Math.round((Date.now() - ts) / 1000));
  if (s < 60) return 'just now';
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.round(h / 24);
  return d === 1 ? 'yesterday' : `${d} days ago`;
}
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      const ok = document.execCommand('copy');
      ta.remove();
      return ok;
    } catch { return false; }
  }
}
export const CATEGORY_LABEL: Record<string, string> = {
  admission: 'Admission', academics: 'Academics', hostel: 'Hostel', fees: 'Fees', examination: 'Examination',
  scholarships: 'Scholarships', contact: 'Contact', notices: 'Notices', general: 'General',
};
