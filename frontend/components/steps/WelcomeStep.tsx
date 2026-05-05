'use client';

import {
  ArrowRight,
  FileSearch,
  GraduationCap,
  PlayCircle,
  Shield,
  Sparkles,
} from 'lucide-react';
import clsx from 'clsx';

export function WelcomeStep({
  onNext,
  onDemo,
  demoStarting,
}: {
  onNext: () => void;
  onDemo: () => void;
  demoStarting: boolean;
}) {
  return (
    <div className="max-w-4xl mx-auto py-8 animate-fade-in-up">
      <div className="text-center">
        <p className="text-xs uppercase tracking-[0.25em] text-sage-600 font-semibold mb-4">
          New York City · Small Claims · Breach of Contract
        </p>
        <h1 className="font-serif text-5xl md:text-6xl text-ink-900 leading-[1.05] mb-6">
          Stop writing off
          <br />
          <span className="text-sage-700">unpaid invoices.</span>
        </h1>
        <p className="text-lg text-ink-900/70 leading-relaxed max-w-2xl mx-auto mb-8">
          Lawyers won't take a case under $10,000. Filing it yourself is a
          paperwork minefield. We answer the questions, look up the business
          with the State, do the math, cite the statutes, and hand you a
          court-ready packet to walk into the clerk's office with.
        </p>

        <div className="flex flex-wrap justify-center gap-3 mb-10">
          <button
            onClick={onDemo}
            disabled={demoStarting}
            className={clsx(
              'inline-flex items-center gap-2 px-7 py-3.5 rounded-xl font-semibold shadow-paper transition active:translate-y-[1px]',
              demoStarting
                ? 'bg-ink-200 text-ink-300 cursor-wait'
                : 'bg-ochre-400 hover:bg-ochre-500 text-ink-900',
            )}
          >
            <PlayCircle size={18} />
            {demoStarting ? 'Starting…' : 'Run the sample case'}
          </button>
          <button
            onClick={onNext}
            className="bg-sage-700 hover:bg-sage-800 text-ink-50 px-7 py-3.5 rounded-xl font-semibold inline-flex items-center gap-2 shadow-paper transition active:translate-y-[1px]"
          >
            Start your filing <ArrowRight size={18} />
          </button>
          <a
            href="#how"
            className="text-sage-700 hover:bg-ink-100 px-5 py-3.5 rounded-xl font-medium transition"
          >
            See how it works
          </a>
        </div>
      </div>

      <GraderBanner onDemo={onDemo} starting={demoStarting} />

      <div id="how" className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left mt-12">
        <FeatureCard
          icon={<FileSearch />}
          title="Reads your evidence"
          body="Drop in contracts, emails, invoices, screenshots. Multimodal Gemini pulls the case facts so you don't have to retype anything."
        />
        <FeatureCard
          icon={<Shield />}
          title="Looks up the business with NY State"
          body="Resolves the LLC name to its registered service-of-process address via the official NYS DOS dataset. No served defendant, no case."
        />
        <FeatureCard
          icon={<Sparkles />}
          title="Cites the rules, does the math"
          body="Validates the $10k cap (CCA § 1805) and 6-year SOL (CPLR § 213), then computes 9% statutory interest (CPLR § 5004)."
        />
      </div>

      <p className="text-xs text-ink-300 mt-12 max-w-xl mx-auto leading-relaxed text-center">
        ClaimReady generates documents and educational guidance. It is not a
        law firm and does not provide legal advice. For a complex case, see
        a licensed attorney.
      </p>
    </div>
  );
}

function GraderBanner({ onDemo, starting }: { onDemo: () => void; starting: boolean }) {
  return (
    <section
      aria-label="Grader demo"
      className="mt-4 rounded-2xl border border-ochre-400/30 bg-gradient-to-br from-ink-50 to-ochre-400/10 p-6 md:p-8 shadow-paper"
    >
      <div className="flex items-start gap-5">
        <div className="hidden sm:flex w-12 h-12 rounded-xl bg-ochre-400 text-ink-900 items-center justify-center shrink-0 shadow-sm">
          <GraduationCap size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] uppercase tracking-[0.22em] text-ochre-600 font-semibold mb-1">
            Reviewing this for class? Skip the typing.
          </p>
          <h2 className="font-serif text-2xl text-ink-900 mb-2">
            Run the full pipeline on a pre-baked scenario.
          </h2>
          <p className="text-sm text-ink-900/75 leading-relaxed mb-5 max-w-2xl">
            We've bundled a realistic case — Brooklyn freelance designer
            owed <b>$4,800</b> by an NYC marketing LLC, with a signed
            contract, an invoice, an email thread, and a follow-up note.
            One click and you'll see all four specialist agents work end-to-end:
            Extractor → Defendant lookup (NY State) → Jurisdiction check
            (RAG + statutes) → Drafter → downloadable PDF packet.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={onDemo}
              disabled={starting}
              className={clsx(
                'inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold shadow-sm transition',
                starting
                  ? 'bg-ink-200 text-ink-300 cursor-wait'
                  : 'bg-ochre-400 hover:bg-ochre-500 text-ink-900 active:translate-y-[1px]',
              )}
            >
              <PlayCircle size={18} />
              {starting ? 'Starting demo run…' : 'Run the sample case'}
            </button>
            <span className="text-xs text-ink-300">
              ~30–60 seconds · no signup · no inputs needed
            </span>
          </div>
          <ul className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-xs text-ink-900/70">
            <li>· 4 evidence files auto-loaded</li>
            <li>· Real NY DOS API call</li>
            <li>· Real RAG over 6 legal sources</li>
            <li>· Real PDF generated server-side</li>
          </ul>
        </div>
      </div>
    </section>
  );
}

function FeatureCard({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="bg-white rounded-2xl border border-ink-200 p-6 shadow-paper">
      <div className="w-10 h-10 rounded-lg bg-sage-50 text-sage-700 flex items-center justify-center mb-4">
        {icon}
      </div>
      <p className="font-serif text-lg text-ink-900 mb-2">{title}</p>
      <p className="text-sm text-ink-900/70 leading-relaxed">{body}</p>
    </div>
  );
}
