import { forwardRef } from 'react';
import { ShieldCheck } from 'lucide-react';
import { ChatComposer, type ComposerHandle } from './ChatComposer';
import { SuggestedQuestions } from './SuggestedQuestions';

interface Props {
  onSend: (t: string) => void;
  onStop: () => void;
  loading: boolean;
  offline: boolean;
}

export const WelcomeScreen = forwardRef<ComposerHandle, Props>(function WelcomeScreen(
  { onSend, onStop, loading, offline },
  ref
) {
  return (
    <div className="relative flex min-h-full flex-col items-center justify-center px-4 pb-12 pt-8 sm:px-6 lg:px-8">
      <div className="relative z-10 flex w-full max-w-3xl flex-col items-center text-center">
        {/* Verification Pill */}
        <div className="animate-rise inline-flex items-center gap-2 rounded-full border border-blue-200/80 bg-blue-50/80 dark:border-blue-900/60 dark:bg-blue-950/60 px-3.5 py-1 text-xs font-medium text-blue-900 dark:text-blue-200 shadow-subtle backdrop-blur-sm">
          <ShieldCheck size={14} className="text-teal-700 dark:text-teal-400" aria-hidden="true" />
          <span>JKLU Admission Portal · Grounded in official university records</span>
        </div>

        {/* Hero Title & Description */}
        <h1
          className="animate-rise mt-6 text-balance text-3xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-5xl lg:text-[3.25rem] leading-[1.12]"
          style={{ animationDelay: '.05s' }}
        >
          Your journey to JKLU starts here.
        </h1>

        <p
          className="animate-rise mt-4 max-w-2xl text-balance text-base leading-relaxed text-slate-600 dark:text-slate-300 sm:text-lg"
          style={{ animationDelay: '.1s' }}
        >
          Get clear answers about admissions, programmes, scholarships, fees, eligibility, campus life, and more.
        </p>

        {/* Large Hero Chat Composer */}
        <div className="animate-rise mx-auto mt-8 w-full max-w-2xl" style={{ animationDelay: '.15s' }}>
          <ChatComposer ref={ref} onSend={onSend} onStop={onStop} loading={loading} offline={offline} variant="hero" />
        </div>

        {/* Disclaimer / Accuracy Note */}
        <p className="mt-3 text-center text-xs text-slate-500 dark:text-slate-400 max-w-xl leading-normal">
          Official admissions decisions, fee structures, and scholarship criteria are governed by JKLU's formal notifications. Please verify critical details with the admissions office.
        </p>
      </div>

      {/* Suggested Questions Grid */}
      <div className="relative z-10 mt-10 w-full max-w-4xl">
        <div className="mb-3 flex items-center justify-between px-1">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Suggested Admission Topics & Questions
          </h2>
          <span className="text-xs text-slate-600 dark:text-slate-400 hidden sm:inline">
            Click any question to ask immediately
          </span>
        </div>
        <SuggestedQuestions onSelect={onSend} disabled={loading} />
      </div>
    </div>
  );
});
