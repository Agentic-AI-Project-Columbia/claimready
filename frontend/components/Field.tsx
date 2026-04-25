'use client';

import clsx from 'clsx';

interface FieldProps {
  label: string;
  hint?: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
  span?: 'full' | 'half';
}

export function Field({ label, hint, required, error, children, span = 'full' }: FieldProps) {
  return (
    <div className={clsx(span === 'half' ? 'sm:col-span-1' : 'sm:col-span-2')}>
      <label>
        {label}
        {required && <span className="text-ochre-500 ml-1">*</span>}
      </label>
      {children}
      {hint && !error && <p className="mt-1.5 text-xs text-ink-300">{hint}</p>}
      {error && <p className="mt-1.5 text-xs text-ochre-600">{error}</p>}
    </div>
  );
}

export function FieldGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-5">{children}</div>;
}
