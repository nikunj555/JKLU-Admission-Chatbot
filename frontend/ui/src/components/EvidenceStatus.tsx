import { AlertTriangle, CircleHelp, ShieldCheck, Sparkles } from 'lucide-react';
import type { ChatStatus } from '../types';

/** Honest evidence indicator driven only by the backend status. */
export function EvidenceStatus({ status, sourceCount }: { status: ChatStatus; sourceCount: number }) {
  const map = {
    smalltalk: {
      label: 'Assistant Introduction',
      Icon: Sparkles,
      cls: 'text-blue-800 border-blue-200 bg-blue-50 dark:text-blue-200 dark:border-blue-900 dark:bg-blue-950/60',
    },
    answer: {
      label: 'Verified official information',
      Icon: ShieldCheck,
      cls: 'text-emerald-800 border-emerald-200 bg-emerald-50 dark:text-emerald-200 dark:border-emerald-900 dark:bg-emerald-950/60',
    },
    clarify: {
      label: 'More details needed',
      Icon: CircleHelp,
      cls: 'text-amber-800 border-amber-200 bg-amber-50 dark:text-amber-200 dark:border-amber-900 dark:bg-amber-950/60',
    },
    escalate: {
      label: 'Not verified in university records',
      Icon: AlertTriangle,
      cls: 'text-rose-800 border-rose-200 bg-rose-50 dark:text-rose-200 dark:border-rose-900 dark:bg-rose-950/60',
    },
  } as const;

  const conf = map[status] || map.smalltalk;
  const { label, Icon, cls } = conf;

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold shadow-subtle ${cls}`}>
      <Icon size={13} aria-hidden="true" />
      <span>{label}</span>
      {status === 'answer' && sourceCount > 0 && (
        <span className="font-normal text-emerald-950 dark:text-emerald-200">
          · {sourceCount} {sourceCount === 1 ? 'official reference' : 'official references'}
        </span>
      )}
    </span>
  );
}
