'use client';

import { useState } from 'react';
import { StepShell } from '@/components/StepShell';
import { Field, FieldGrid } from '@/components/Field';
import type { IntakeForm } from '@/lib/types';
import { validateContract, type FieldErrors } from '@/lib/validation';

export function ContractStep({
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
    const e = validateContract(intake);
    setErrors(e);
    if (Object.keys(e).length === 0) onNext();
  }

  return (
    <StepShell
      step={4}
      totalSteps={totalSteps}
      kicker="Step 4 of 8"
      title="What did you agree to do?"
      helpText={
        <>
          The court needs the bones of your contract: when you formed it,
          what you were going to do, and how much you were going to be
          paid. A written agreement is best, but verbal contracts and
          email threads count too.
        </>
      }
      onBack={onBack}
      onNext={handleNext}
      nextDisabled={!intake.contract.scope_of_work || !intake.contract.agreed_amount}
    >
      <FieldGrid>
        <Field label="Date the agreement was formed" span="half" error={errors['contract.date']}>
          <input
            type="date"
            value={intake.contract.date_formed ?? ''}
            onChange={(e) =>
              setIntake((p) => ({ ...p, contract: { ...p.contract, date_formed: e.target.value } }))
            }
          />
        </Field>
        <Field label="Agreed amount (USD)" required span="half" error={errors['contract.amount']}>
          <input
            type="number"
            min={0}
            step="0.01"
            value={intake.contract.agreed_amount || ''}
            onChange={(e) =>
              setIntake((p) => ({
                ...p,
                contract: { ...p.contract, agreed_amount: parseFloat(e.target.value || '0') },
              }))
            }
            placeholder="4800.00"
          />
        </Field>
        <Field
          label="What you agreed to do"
          required
          hint="Plain English. The judge will read this verbatim."
          span="full"
          error={errors['contract.scope']}
        >
          <textarea
            rows={3}
            value={intake.contract.scope_of_work}
            onChange={(e) =>
              setIntake((p) => ({ ...p, contract: { ...p.contract, scope_of_work: e.target.value } }))
            }
            placeholder="Graphic-design services for Vanguard Marketing's Spring 2025 product launch — 12 illustrations + brand guidelines."
          />
        </Field>
        <Field label="Payment terms" span="full" hint="e.g. Net 30, 50% on signing, etc.">
          <input
            value={intake.contract.payment_terms ?? ''}
            onChange={(e) =>
              setIntake((p) => ({ ...p, contract: { ...p.contract, payment_terms: e.target.value } }))
            }
            placeholder="Net 30 from delivery."
          />
        </Field>
      </FieldGrid>
    </StepShell>
  );
}
