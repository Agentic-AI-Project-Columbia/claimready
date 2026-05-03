'use client';

import { ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';
import clsx from 'clsx';

interface StepShellProps {
  step: number;
  totalSteps: number;
  title: string;
  kicker?: string;
  helpText?: React.ReactNode;
  onBack?: () => void;
  onNext?: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  onStepClick?: (step: number) => void;
  onAutofill?: () => void;
  children: React.ReactNode;
}

export function StepShell({
  step,
  totalSteps,
  title,
  kicker,
  helpText,
  onBack,
  onNext,
  nextLabel = 'Continue',
  nextDisabled = false,
  onStepClick,
  onAutofill,
  children,
}: StepShellProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_320px] gap-10">
      {/* LEFT — progress rail */}
      <aside className="hidden lg:block">
        <ProgressRail step={step} totalSteps={totalSteps} onStepClick={onStepClick} />
      </aside>

      {/* CENTER — the actual form */}
      <main className="min-w-0">
        {kicker && (
          <p className="text-xs uppercase tracking-[0.2em] text-sage-600 font-medium mb-2">
            {kicker}
          </p>
        )}
        <h1 className="font-serif text-3xl md:text-4xl text-ink-900 leading-tight mb-8">
          {title}
        </h1>
        <div className="bg-white rounded-2xl shadow-paper p-8 md:p-10 animate-fade-in-up">
          {children}
        </div>
        <div className="flex justify-between items-center mt-8">
          <button
            onClick={onBack}
            disabled={!onBack}
            className={clsx(
              'flex items-center gap-1 text-sm font-medium px-4 py-2 rounded-lg transition',
              onBack
                ? 'text-sage-700 hover:bg-ink-100'
                : 'text-ink-300 cursor-not-allowed',
            )}
          >
            <ChevronLeft size={16} /> Back
          </button>
          {onAutofill && (
            <button
              onClick={onAutofill}
              type="button"
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-ochre-400/40 text-ochre-600 hover:bg-ochre-400/10 transition"
            >
              <Sparkles size={14} /> Fill demo data
            </button>
          )}
          {onNext && (
            <button
              onClick={onNext}
              disabled={nextDisabled}
              className={clsx(
                'flex items-center gap-2 text-sm font-semibold px-6 py-3 rounded-xl transition shadow-sm',
                nextDisabled
                  ? 'bg-ink-200 text-ink-300 cursor-not-allowed'
                  : 'bg-sage-700 text-ink-50 hover:bg-sage-800 active:translate-y-[1px]',
              )}
            >
              {nextLabel} <ChevronRight size={16} />
            </button>
          )}
        </div>
      </main>

      {/* RIGHT — help / context */}
      <aside className="hidden lg:block">
        {helpText && (
          <div className="sticky top-8 bg-ink-100/60 border border-ink-200/70 rounded-xl p-5 text-sm text-ink-900/80 leading-relaxed">
            <p className="font-semibold text-sage-700 mb-2 text-xs uppercase tracking-wider">
              Why we ask
            </p>
            {helpText}
          </div>
        )}
      </aside>
    </div>
  );
}

function ProgressRail({
  step,
  totalSteps,
  onStepClick,
}: {
  step: number;
  totalSteps: number;
  onStepClick?: (step: number) => void;
}) {
  const labels = [
    'Welcome',
    'About you',
    'About the business',
    'The agreement',
    'What went wrong',
    'Your evidence',
    'Review',
    'Generate',
  ];
  return (
    <div className="sticky top-8">
      <p className="text-xs uppercase tracking-[0.2em] text-sage-600 font-medium mb-4">
        Filing steps
      </p>
      <ol className="space-y-1">
        {labels.slice(0, totalSteps).map((label, i) => {
          const idx = i + 1;
          const isDone = idx < step;
          const isCurrent = idx === step;
          return (
            <li key={label}>
              <button
                type="button"
                onClick={() => onStepClick?.(idx)}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition w-full text-left',
                  onStepClick && 'cursor-pointer',
                  isCurrent && 'bg-sage-700 text-ink-50 font-semibold hover:bg-sage-800',
                  isDone && 'text-sage-700 hover:bg-ink-100',
                  !isDone && !isCurrent && 'text-ink-300 hover:text-ink-600 hover:bg-ink-100',
                )}
              >
                <span
                  className={clsx(
                    'w-6 h-6 flex items-center justify-center rounded-full text-[11px] font-semibold',
                    isCurrent && 'bg-ochre-400 text-ink-900',
                    isDone && 'bg-sage-100 text-sage-700',
                    !isDone && !isCurrent && 'bg-ink-100 text-ink-300',
                  )}
                >
                  {isDone ? '✓' : idx}
                </span>
                <span>{label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
