'use client';

import { StepShell } from '@/components/StepShell';
import { Field, FieldGrid } from '@/components/Field';
import type { IntakeForm } from '@/lib/types';

export function DefendantStep({
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
  return (
    <StepShell
      step={3}
      totalSteps={totalSteps}
      kicker="Step 3 of 8"
      title="Who owes you the money?"
      helpText={
        <>
          We'll look this LLC or corporation up against the official New
          York Department of State registry to find its legal name and
          service-of-process address. <b>Critical:</b> if we get this
          wrong, the defendant won't be served and your case will be
          dismissed.
        </>
      }
      onBack={onBack}
      onNext={onNext}
      nextDisabled={!intake.defendant.name}
    >
      <FieldGrid>
        <Field
          label="Business name (as you know it)"
          required
          hint="The agent will check the canonical name with NY State."
          span="full"
        >
          <input
            value={intake.defendant.name}
            onChange={(e) =>
              setIntake((p) => ({ ...p, defendant: { ...p.defendant, name: e.target.value } }))
            }
            placeholder="Vanguard Marketing LLC"
          />
        </Field>
      </FieldGrid>
    </StepShell>
  );
}
