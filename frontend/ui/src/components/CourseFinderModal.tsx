import { useState } from 'react';
import { Modal } from './Modal';

interface Props {
  onClose: () => void;
  onSelectQuery: (q: string) => void;
}

const PROGRAMMES: {
  id: string;
  label: string;
  departments: { label: string; queryName: string; years: number[] }[];
}[] = [
  {
    id: 'btech',
    label: 'B.Tech (4 Years)',
    departments: [
      { label: 'Computer Science & Engineering (CSE)', queryName: 'B.Tech CSE', years: [1, 2, 3, 4] },
      { label: 'CSE (Artificial Intelligence)', queryName: 'B.Tech CSE (AI)', years: [1, 2, 3, 4] },
      { label: 'CSE (Data Science)', queryName: 'B.Tech CSE (Data Science)', years: [1, 2, 3, 4] },
      { label: 'CSE (Cybersecurity)', queryName: 'B.Tech CSE (Cybersecurity)', years: [1, 2, 3, 4] },
      { label: 'ECE (VLSI Design)', queryName: 'B.Tech ECE (VLSI Design)', years: [1, 2, 3, 4] },
    ],
  },
  {
    id: 'bba',
    label: 'BBA (3 Years / Hons.)',
    departments: [
      { label: 'BBA FinTech', queryName: 'BBA FinTech', years: [1, 2, 3] },
      { label: 'BBA with KPMG Certification', queryName: 'BBA KPMG', years: [1, 2, 3] },
      { label: 'BBA (Core / Hons.)', queryName: 'BBA', years: [1, 2, 3] },
    ],
  },
  {
    id: 'bdes',
    label: 'B.Des (4 Years)',
    departments: [
      { label: 'Product Design', queryName: 'B.Des Product Design', years: [1, 2, 3, 4] },
      { label: 'Interaction Design', queryName: 'B.Des Interaction Design', years: [1, 2, 3, 4] },
      { label: 'Interdisciplinary Design', queryName: 'B.Des Interdisciplinary Design', years: [1, 2, 3, 4] },
      { label: 'Integrated Communication Design', queryName: 'B.Des Integrated Communication Design', years: [1, 2, 3, 4] },
    ],
  },
  {
    id: 'pg',
    label: 'M.Tech / M.Des / Ph.D.',
    departments: [
      { label: 'M.Tech (CSE)', queryName: 'M.Tech CSE', years: [1, 2] },
      { label: 'M.Des', queryName: 'M.Des', years: [1, 2] },
      { label: 'Ph.D. Coursework', queryName: 'PhD', years: [1] },
    ],
  },
];

export function CourseFinderModal({ onClose, onSelectQuery }: Props) {
  const [progId, setProgId] = useState<string | null>(null);
  const [deptIdx, setDeptIdx] = useState<number | null>(null);

  const selectedProg = PROGRAMMES.find((p) => p.id === progId) ?? null;
  const selectedDept = selectedProg && deptIdx !== null ? selectedProg.departments[deptIdx] ?? null : null;

  const submitYear = (yearLabel: string) => {
    if (!selectedDept) return;
    const q =
      yearLabel === 'all'
        ? `Which courses are in ${selectedDept.queryName} (all years)?`
        : `Which courses are in ${yearLabel} of ${selectedDept.queryName}?`;
    onSelectQuery(q);
    onClose();
  };

  return (
    <Modal
      title="Explore Course Curriculum"
      description="Choose a programme, department, and year to view the semester-wise courses."
      onClose={onClose}
    >
      <div className="space-y-4 pt-1">
        {/* Step 1: Programme */}
        <div>
          <p className="mb-2 text-xs font-semibold text-slate-700 dark:text-slate-300">
            1. Choose Programme
          </p>
          <div className="flex flex-wrap gap-2">
            {PROGRAMMES.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setProgId(p.id);
                  setDeptIdx(null);
                }}
                className={`rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors ${
                  progId === p.id
                    ? 'border-blue-600 bg-blue-50 text-blue-900 dark:border-blue-500 dark:bg-blue-950/60 dark:text-blue-200'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Step 2: Department */}
        {selectedProg && (
          <div>
            <p className="mb-2 text-xs font-semibold text-slate-700 dark:text-slate-300">
              2. Choose Department / Specialisation
            </p>
            <div className="flex flex-wrap gap-2">
              {selectedProg.departments.map((d, idx) => (
                <button
                  key={d.label}
                  type="button"
                  onClick={() => setDeptIdx(idx)}
                  className={`rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors ${
                    deptIdx === idx
                      ? 'border-blue-600 bg-blue-50 text-blue-900 dark:border-blue-500 dark:bg-blue-950/60 dark:text-blue-200'
                      : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200'
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 3: Year */}
        {selectedDept && (
          <div>
            <p className="mb-2 text-xs font-semibold text-slate-700 dark:text-slate-300">
              3. Choose Year
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => submitYear('all')}
                className="rounded-xl bg-blue-800 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-blue-900"
              >
                All Years
              </button>
              {selectedDept.years.map((y) => (
                <button
                  key={y}
                  type="button"
                  onClick={() => submitYear(`Year ${y}`)}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-blue-500 hover:bg-blue-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                >
                  Year {y}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
