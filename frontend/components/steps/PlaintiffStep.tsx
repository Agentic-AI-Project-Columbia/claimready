'use client';

import { useState } from 'react';
import { StepShell } from '@/components/StepShell';
import { Field, FieldGrid } from '@/components/Field';
import type { IntakeForm } from '@/lib/types';
import { validatePlaintiff, type FieldErrors } from '@/lib/validation';

export function PlaintiffStep({
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
    const e = validatePlaintiff(intake);
    setErrors(e);
    if (Object.keys(e).length === 0) onNext();
  }

  return (
    <StepShell
      step={2}
      totalSteps={totalSteps}
      kicker="Step 2 of 8"
      title="Tell us about you, the plaintiff."
      helpText={
        <>
          You're filing this case in your own name (<i>pro se</i>). The
          court needs your address to send mail and your phone or email
          for the trial date.
        </>
      }
      onBack={onBack}
      onNext={handleNext}
      nextDisabled={!intake.plaintiff.name || !intake.plaintiff.address}
    >
      <FieldGrid>
        <Field label="Full legal name" required span="full" error={errors['plaintiff.name']}>
          <input
            value={intake.plaintiff.name}
            onChange={(e) => setIntake((p) => ({ ...p, plaintiff: { ...p.plaintiff, name: e.target.value } }))}
            placeholder="Jane Q. Doe"
          />
        </Field>
        <Field label="Street address" required span="full" error={errors['plaintiff.address']}>
          <input
            value={intake.plaintiff.address}
            onChange={(e) => setIntake((p) => ({ ...p, plaintiff: { ...p.plaintiff, address: e.target.value } }))}
            placeholder="123 Smith St."
          />
        </Field>
        <Field label="City" span="half">
          <input
            value={intake.plaintiff.city}
            onChange={(e) => setIntake((p) => ({ ...p, plaintiff: { ...p.plaintiff, city: e.target.value } }))}
            placeholder="Brooklyn"
          />
        </Field>
        <Field label="ZIP code" span="half" error={errors['plaintiff.zip_code']}>
          <input
            value={intake.plaintiff.zip_code}
            onChange={(e) => setIntake((p) => ({ ...p, plaintiff: { ...p.plaintiff, zip_code: e.target.value } }))}
            placeholder="11201"
          />
        </Field>
        <Field label="Phone" span="half">
          <input
            value={intake.plaintiff.phone}
            onChange={(e) => setIntake((p) => ({ ...p, plaintiff: { ...p.plaintiff, phone: e.target.value } }))}
            placeholder="(718) 555-0100"
          />
        </Field>
        <Field label="Email" span="half" error={errors['plaintiff.email']}>
          <input
            value={intake.plaintiff.email}
            onChange={(e) => setIntake((p) => ({ ...p, plaintiff: { ...p.plaintiff, email: e.target.value } }))}
            placeholder="jane@example.com"
          />
        </Field>
      </FieldGrid>
    </StepShell>
  );
}
