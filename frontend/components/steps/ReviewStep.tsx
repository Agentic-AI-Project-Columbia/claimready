'use client';

import { StepShell } from '@/components/StepShell';
import type { IntakeForm } from '@/lib/types';

export function ReviewStep({
  intake,
  fileCount,
  onBack,
  onNext,
  totalSteps,
}: {
  intake: IntakeForm;
  fileCount: number;
  onBack: () => void;
  onNext: () => void;
  totalSteps: number;
}) {
  const sections: Array<{ title: string; rows: Array<[string, React.ReactNode]> }> = [
    {
      title: 'Plaintiff',
      rows: [
        ['Name', intake.plaintiff.name || '—'],
        ['Address', intake.plaintiff.address || '—'],
        ['Contact', `${intake.plaintiff.phone} · ${intake.plaintiff.email}`.replace(' · ', '').trim() || '—'],
      ],
    },
    {
      title: 'Defendant',
      rows: [['Name', intake.defendant.name || '—']],
    },
    {
      title: 'The agreement',
      rows: [
        ['Formed', intake.contract.date_formed || '—'],
        ['Scope', intake.contract.scope_of_work || '—'],
        ['Amount', `$${intake.contract.agreed_amount.toFixed(2)}`],
        ['Terms', intake.contract.payment_terms || '—'],
      ],
    },
    {
      title: 'The breach',
      rows: [
        ['Date', intake.breach.date || '—'],
        ['Amount unpaid', `$${intake.breach.amount_owed.toFixed(2)}`],
        ['Venue', intake.venue.borough || '—'],
      ],
    },
    {
      title: 'Evidence',
      rows: [['Files attached', fileCount === 0 ? 'None' : `${fileCount} file${fileCount > 1 ? 's' : ''}`]],
    },
  ];

  return (
    <StepShell
      step={7}
      totalSteps={totalSteps}
      kicker="Step 7 of 7"
      title="One last look before we generate."
      helpText={
        <>
          When you click Generate, our planner agent kicks off five
          specialists in sequence: Extractor → Defendant lookup →
          Jurisdiction check → Drafter. Watch them work in real time.
        </>
      }
      onBack={onBack}
      onNext={onNext}
      nextLabel="Generate my packet"
    >
      <div className="space-y-8">
        {sections.map((s) => (
          <div key={s.title}>
            <p className="text-xs uppercase tracking-[0.18em] text-sage-600 font-semibold mb-3">
              {s.title}
            </p>
            <dl className="divide-y divide-ink-200/70">
              {s.rows.map(([k, v]) => (
                <div key={k} className="grid grid-cols-3 py-2.5 gap-4">
                  <dt className="text-sm text-ink-300">{k}</dt>
                  <dd className="col-span-2 text-sm text-ink-900">{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </StepShell>
  );
}
