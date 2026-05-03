'use client';

import { useState } from 'react';
import { StepShell } from '@/components/StepShell';
import { Field, FieldGrid } from '@/components/Field';
import type { IntakeForm } from '@/lib/types';
import { validateBreach, type FieldErrors } from '@/lib/validation';

export function BreachStep({
  intake,
  setIntake,
  onBack,
  onNext,
  totalSteps,
}: {
  intake: IntakeForm;
  setIntake: React.Dispatch<React.SetStateAction<IntakeForm>>;
  onBack: () => void;
  onNext: () => void;
  totalSteps: number;
}) {
  const [errors, setErrors] = useState<FieldErrors>({});

  function handleNext() {
    const e = validateBreach(intake);
    setErrors(e);
    if (Object.keys(e).length === 0) onNext();
  }

  return (
    <StepShell
      step={5}
      totalSteps={totalSteps}
      kicker="Step 5 of 8"
      title="What went wrong?"
      helpText={
        <>
          Most small-claims cases against businesses are non-payment.
          The "date of breach" is the day after payment was due and not
          made — this clock matters because of the 6-year statute of
          limitations (CPLR § 213(2)).
        </>
      }
      onBack={onBack}
      onNext={handleNext}
      nextDisabled={!intake.breach.date || !intake.breach.amount_owed || !intake.venue.borough}
    >
      <FieldGrid>
        <Field label="Date of breach (payment first overdue)" required span="half" error={errors['breach.date']}>
          <input
            type="date"
            value={intake.breach.date ?? ''}
            onChange={(e) =>
              setIntake((p) => ({ ...p, breach: { ...p.breach, date: e.target.value } }))
            }
          />
        </Field>
        <Field label="Amount unpaid (USD)" required span="half" error={errors['breach.amount']}>
          <input
            type="number"
            min={0}
            step="0.01"
            value={intake.breach.amount_owed || ''}
            onChange={(e) =>
              setIntake((p) => ({
                ...p,
                breach: { ...p.breach, amount_owed: parseFloat(e.target.value || '0') },
              }))
            }
            placeholder="4800.00"
          />
        </Field>
        <Field
          label="Borough you'll file in"
          required
          hint="Where the defendant does business, or where the work was done."
          span="full"
          error={errors['venue.borough']}
        >
          <select
            value={intake.venue.borough}
            onChange={(e) =>
              setIntake((p) => ({ ...p, venue: { ...p.venue, borough: e.target.value as any } }))
            }
          >
            <option value="">— select —</option>
            <option value="Manhattan">Manhattan</option>
            <option value="Brooklyn">Brooklyn</option>
            <option value="Queens">Queens</option>
            <option value="Bronx">Bronx</option>
            <option value="Staten Island">Staten Island</option>
          </select>
        </Field>
        <Field label="Why this borough is proper" span="full">
          <textarea
            rows={2}
            value={intake.venue.basis}
            onChange={(e) =>
              setIntake((p) => ({ ...p, venue: { ...p.venue, basis: e.target.value } }))
            }
            placeholder="The defendant has its principal place of business at … in Brooklyn."
          />
        </Field>
      </FieldGrid>
    </StepShell>
  );
}
