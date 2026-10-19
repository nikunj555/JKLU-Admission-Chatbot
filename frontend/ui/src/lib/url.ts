/** Only official JKLU hosts are rendered as clickable links. Everything else is shown as plain text. */
const OFFICIAL_DOMAINS = ['jklu.edu.in'];

export function safeOfficialUrl(raw?: string | null): string | null {
  if (!raw) return null;
  try {
    const u = new URL(raw);
    if (u.protocol !== 'https:' && u.protocol !== 'http:') return null;
    const host = u.hostname.toLowerCase();
    if (OFFICIAL_DOMAINS.some((d) => host === d || host.endsWith('.' + d))) return u.toString();
  } catch {
    /* not a URL */
  }
  return null;
}

export function telHref(phone: string): string {
  return 'tel:' + phone.replace(/[^+\d]/g, '');
}
export function mailHref(email: string): string | null {
  const first = email.split(',')[0]?.trim() ?? '';
  return /^[^\s@<>"]+@[^\s@<>"]+\.[^\s@<>"]+$/.test(first) ? 'mailto:' + first : null;
}
