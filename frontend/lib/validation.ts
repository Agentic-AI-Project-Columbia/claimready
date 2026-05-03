import type { IntakeForm } from './types';

export const NYC_SMALL_CLAIMS_CAP = 10_000;
export const SOL_YEARS = 6;

export type FieldErrors = Record<string, string>;

export function validatePlaintiff(intake: IntakeForm): FieldErrors {
  const e: FieldErrors = {};
  if (!intake.plaintiff.name.trim()) e['plaintiff.name'] = 'Name is required.';
  if (!intake.plaintiff.address.trim()) e['plaintiff.address'] = 'Address is required.';
  if (intake.plaintiff.zip_code && !/^\d{5}(-\d{4})?$/.test(intake.plaintiff.zip_code))
    e['plaintiff.zip_code'] = 'Enter a valid 5-digit ZIP code.';
  if (intake.plaintiff.email && !intake.plaintiff.email.includes('@'))
    e['plaintiff.email'] = 'Enter a valid email address.';
  return e;
}

export function validateContract(intake: IntakeForm): FieldErrors {
  const e: FieldErrors = {};
  if (!intake.contract.scope_of_work.trim()) e['contract.scope'] = 'Scope of work is required.';
  if (!intake.contract.agreed_amount || intake.contract.agreed_amount <= 0)
    e['contract.amount'] = 'Agreed amount must be greater than zero.';
  else if (intake.contract.agreed_amount > NYC_SMALL_CLAIMS_CAP)
    e['contract.amount'] = `NYC small claims cap is $${NYC_SMALL_CLAIMS_CAP.toLocaleString()}. File in Civil Court for larger amounts.`;
  if (intake.contract.date_formed) {
    const d = new Date(intake.contract.date_formed);
    if (d > new Date()) e['contract.date'] = 'Contract date cannot be in the future.';
  }
  return e;
}

export function validateBreach(intake: IntakeForm): FieldErrors {
  const e: FieldErrors = {};
  if (!intake.breach.date) {
    e['breach.date'] = 'Breach date is required.';
  } else {
    const d = new Date(intake.breach.date);
    if (d > new Date()) e['breach.date'] = 'Breach date cannot be in the future.';
    const cutoff = new Date();
    cutoff.setFullYear(cutoff.getFullYear() - SOL_YEARS);
    if (d < cutoff) e['breach.date'] = `Breach is older than the ${SOL_YEARS}-year statute of limitations (CPLR § 213).`;
  }
  if (!intake.breach.amount_owed || intake.breach.amount_owed <= 0)
    e['breach.amount'] = 'Unpaid amount must be greater than zero.';
  else if (intake.breach.amount_owed > NYC_SMALL_CLAIMS_CAP)
    e['breach.amount'] = `Exceeds the $${NYC_SMALL_CLAIMS_CAP.toLocaleString()} NYC small claims cap.`;
  if (!intake.venue.borough) e['venue.borough'] = 'Select a borough to file in.';
  return e;
}
