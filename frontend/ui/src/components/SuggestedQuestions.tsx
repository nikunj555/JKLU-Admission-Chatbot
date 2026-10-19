import {
  Award,
  BookOpen,
  Building2,
  CalendarDays,
  FileCheck2,
  GraduationCap,
  PhoneCall,
  Sparkles,
  Users,
} from 'lucide-react';
import { useState } from 'react';

export interface CategoryGroup {
  id: string;
  name: string;
  icon: typeof GraduationCap;
  questions: string[];
}

export const ADMISSION_CATEGORIES: CategoryGroup[] = [
  {
    id: 'admissions',
    name: 'Admissions & Eligibility',
    icon: GraduationCap,
    questions: [
      'What is the admission process for B.Tech CSE?',
      'What are the eligibility criteria for B.Tech?',
      'What documents are required for admission?',
    ],
  },
  {
    id: 'programmes',
    name: 'Programmes & Specializations',
    icon: BookOpen,
    questions: [
      'What undergraduate and postgraduate programmes are offered at JKLU?',
      'What specializations are available in B.Tech Computer Science?',
    ],
  },
  {
    id: 'fees',
    name: 'Fees & Scholarships',
    icon: Award,
    questions: [
      'What scholarships are available for B.Tech students?',
      'What are the tuition fees and other charges?',
    ],
  },
  {
    id: 'dates',
    name: 'Dates & Deadlines',
    icon: CalendarDays,
    questions: [
      'What are the important admission deadlines?',
      'When does the academic calendar or semester start?',
    ],
  },
  {
    id: 'faculty',
    name: 'Faculty & Departments',
    icon: Users,
    questions: [
      'Who are the faculty members in the CSE department?',
      'Who teaches artificial intelligence and machine learning at JKLU?',
    ],
  },
  {
    id: 'hostel',
    name: 'Hostel & Campus Life',
    icon: Building2,
    questions: [
      'What hostel facilities are available?',
      'What are the hostel rules, curfews, and dining facilities?',
    ],
  },
  {
    id: 'application',
    name: 'Application Process',
    icon: FileCheck2,
    questions: [
      'How can I apply to JKLU?',
      'What is the step-by-step registration checklist for admitted students?',
    ],
  },
  {
    id: 'contact',
    name: 'Contact & Official Resources',
    icon: PhoneCall,
    questions: [
      'How do I contact the JKLU admissions office?',
      'What are the official helpline numbers and email addresses?',
    ],
  },
];

interface Props {
  onSelect: (q: string) => void;
  disabled: boolean;
}

export function SuggestedQuestions({ onSelect, disabled }: Props) {
  const [activeCategory, setActiveCategory] = useState<string>('all');

  const filtered =
    activeCategory === 'all'
      ? ADMISSION_CATEGORIES
      : ADMISSION_CATEGORIES.filter((c) => c.id === activeCategory);

  return (
    <div className="w-full space-y-4">
      {/* Category Filter Tabs */}
      <div
        className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-1 scrollbar-none"
        role="tablist"
        aria-label="Filter admission topics"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeCategory === 'all'}
          onClick={() => setActiveCategory('all')}
          className={`shrink-0 rounded-full px-3.5 py-1.5 text-xs font-medium transition-all ${
            activeCategory === 'all'
              ? 'bg-blue-900 text-white shadow-subtle dark:bg-blue-600'
              : 'border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 text-slate-600 hover:border-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
          }`}
        >
          All Topics
        </button>
        {ADMISSION_CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            type="button"
            role="tab"
            aria-selected={activeCategory === cat.id}
            onClick={() => setActiveCategory(cat.id)}
            className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
              activeCategory === cat.id
                ? 'bg-blue-900 text-white shadow-subtle dark:bg-blue-600'
                : 'border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 text-slate-600 hover:border-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
            }`}
          >
            {cat.name}
          </button>
        ))}
      </div>

      {/* Question Cards Grid */}
      <div className="grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Suggested questions">
        {filtered.flatMap((cat) =>
          cat.questions.map((q) => {
            const Icon = cat.icon;
            return (
              <button
                key={q}
                type="button"
                disabled={disabled}
                onClick={() => onSelect(q)}
                className="group flex flex-col justify-between text-left rounded-2xl border border-slate-200/90 bg-white/95 dark:border-slate-800 dark:bg-slate-900/90 p-4 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-500 hover:shadow-pop backdrop-blur-sm disabled:cursor-not-allowed disabled:opacity-50"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50 text-blue-800 dark:bg-blue-950/80 dark:text-blue-300 transition-colors group-hover:bg-blue-100 dark:group-hover:bg-blue-900/60">
                      <Icon size={14} aria-hidden="true" />
                    </span>
                    <span className="text-[11px] font-semibold tracking-wide uppercase text-slate-600 dark:text-slate-400">
                      {cat.name.split('&')[0].trim()}
                    </span>
                  </div>
                  <p className="text-[14.5px] font-medium leading-snug text-slate-900 dark:text-slate-100 group-hover:text-blue-900 dark:group-hover:text-blue-300">
                    {q}
                  </p>
                </div>
                <div className="mt-3 flex items-center gap-1 text-[12px] font-medium text-blue-800 dark:text-blue-400 opacity-0 transition-opacity group-hover:opacity-100">
                  <Sparkles size={12} aria-hidden="true" />
                  <span>Ask Assistant</span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
