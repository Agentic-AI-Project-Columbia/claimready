'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Scale,
  Sparkles,
  Download,
  FileSearch,
  Shield,
  GraduationCap,
  PlayCircle,
} from 'lucide-react';
import clsx from 'clsx';

import { StepShell } from '@/components/StepShell';
import { Field, FieldGrid } from '@/components/Field';
import { EvidenceUpload, type PreviewFile } from '@/components/EvidenceUpload';
import { AgentTimeline } from '@/components/AgentTimeline';
import {
  BACKEND_URL,
  caseEventsURL,
  createCase,
  pdfURL,
  runDemo,
  uploadEvidence,
} from '@/lib/api';
import { emptyIntake, type AgentEvent, type IntakeForm } from '@/lib/types';

const TOTAL_STEPS = 8;

export default function Page() {
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState<'wizard' | 'demo'>('wizard');
  const [intake, setIntake] = useState<IntakeForm>(emptyIntake);
  const [files, setFiles] = useState<PreviewFile[]>([]);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoStarting, setDemoStarting] = useState(false);

  const next = () => setStep((s) => Math.min(s + 1, TOTAL_STEPS));
  const back = () => setStep((s) => Math.max(s - 1, 1));

  function attachWebSocket(case_id: string) {
    const ws = new WebSocket(caseEventsURL(case_id));
    ws.onmessage = (m) => {
      try {
        const payload = JSON.parse(m.data) as AgentEvent;
        setEvents((prev) => [...prev, payload]);
        if (payload.type === 'done') setDone(true);
        if (payload.type === 'error') {
          setError(payload.message ?? 'Unknown error');
          setDone(true);
        }
      } catch {}
    };
    ws.onerror = () => setError('Lost connection to backend');
  }

  async function startDemoRun() {
    if (demoStarting || caseId) return;
    setDemoStarting(true);
    try {
      const { case_id } = await runDemo();
      setMode('demo');
      setCaseId(case_id);
      attachWebSocket(case_id);
      setStep(TOTAL_STEPS);
    } catch (e: any) {
      setError(e?.message ?? String(e));
      setStep(TOTAL_STEPS);
    } finally {
      setDemoStarting(false);
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // STEP 8 — kick off the wizard run when we land on it (skip if demo)
  // ──────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (step !== TOTAL_STEPS || caseId || mode === 'demo') return;
    (async () => {
      try {
        const { case_id } = await createCase(intake);
        setCaseId(case_id);
        attachWebSocket(case_id);
        if (files.length > 0) {
          await uploadEvidence(case_id, files.map((f) => f.file));
        }
      } catch (e: any) {
        setError(e?.message ?? String(e));
      }
    })();
  }, [step, caseId, intake, files, mode]);

  // ──────────────────────────────────────────────────────────────────────
  // Step content
  // ──────────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-7xl mx-auto px-6 py-12">
      <Header />

      {step === 1 && (
        <Welcome onNext={next} onDemo={startDemoRun} demoStarting={demoStarting} />
      )}

      {step === 2 && (
        <StepShell
          step={2}
          totalSteps={TOTAL_STEPS}
          kicker="Step 2 of 7"
          title="Tell us about you, the plaintiff."
          helpText={
            <>
              You're filing this case in your own name (<i>pro se</i>). The
              court needs your address to send mail and your phone or email
              for the trial date.
            </>
          }
          onBack={back}
          onNext={next}
          nextDisabled={!intake.plaintiff.name || !intake.plaintiff.address}
        >
          <FieldGrid>
            <Field label="Full legal name" required span="full">
              <input
                value={intake.plaintiff.name}
                onChange={(e) => setIntake((p) => ({ ...p, plaintiff: { ...p.plaintiff, name: e.target.value } }))}
                placeholder="Jane Q. Doe"
              />
            </Field>
            <Field label="Street address" required span="full">
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
            <Field label="ZIP code" span="half">
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
            <Field label="Email" span="half">
              <input
                value={intake.plaintiff.email}
                onChange={(e) => setIntake((p) => ({ ...p, plaintiff: { ...p.plaintiff, email: e.target.value } }))}
                placeholder="jane@example.com"
              />
            </Field>
          </FieldGrid>
        </StepShell>
      )}

      {step === 3 && (
        <StepShell
          step={3}
          totalSteps={TOTAL_STEPS}
          kicker="Step 3 of 7"
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
          onBack={back}
          onNext={next}
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
                placeholder="Acme Widgets LLC"
              />
            </Field>
          </FieldGrid>
        </StepShell>
      )}

      {step === 4 && (
        <StepShell
          step={4}
          totalSteps={TOTAL_STEPS}
          kicker="Step 4 of 7"
          title="What did you agree to do?"
          helpText={
            <>
              The court needs the bones of your contract: when you formed it,
              what you were going to do, and how much you were going to be
              paid. A written agreement is best, but verbal contracts and
              email threads count too.
            </>
          }
          onBack={back}
          onNext={next}
          nextDisabled={!intake.contract.scope_of_work || !intake.contract.agreed_amount}
        >
          <FieldGrid>
            <Field label="Date the agreement was formed" span="half">
              <input
                type="date"
                value={intake.contract.date_formed ?? ''}
                onChange={(e) =>
                  setIntake((p) => ({ ...p, contract: { ...p.contract, date_formed: e.target.value } }))
                }
              />
            </Field>
            <Field label="Agreed amount (USD)" required span="half">
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
            >
              <textarea
                rows={3}
                value={intake.contract.scope_of_work}
                onChange={(e) =>
                  setIntake((p) => ({ ...p, contract: { ...p.contract, scope_of_work: e.target.value } }))
                }
                placeholder="Graphic-design services for Acme's Spring 2025 product launch — 12 illustrations + brand guidelines."
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
      )}

      {step === 5 && (
        <StepShell
          step={5}
          totalSteps={TOTAL_STEPS}
          kicker="Step 5 of 7"
          title="What went wrong?"
          helpText={
            <>
              Most small-claims cases against businesses are non-payment.
              The "date of breach" is the day after payment was due and not
              made — this clock matters because of the 6-year statute of
              limitations (CPLR § 213(2)).
            </>
          }
          onBack={back}
          onNext={next}
          nextDisabled={!intake.breach.date || !intake.breach.amount_owed || !intake.venue.borough}
        >
          <FieldGrid>
            <Field label="Date of breach (payment first overdue)" required span="half">
              <input
                type="date"
                value={intake.breach.date ?? ''}
                onChange={(e) =>
                  setIntake((p) => ({ ...p, breach: { ...p.breach, date: e.target.value } }))
                }
              />
            </Field>
            <Field label="Amount unpaid (USD)" required span="half">
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
              <input
                value={intake.venue.basis}
                onChange={(e) =>
                  setIntake((p) => ({ ...p, venue: { ...p.venue, basis: e.target.value } }))
                }
                placeholder="The defendant has its principal place of business at … in Brooklyn."
              />
            </Field>
          </FieldGrid>
        </StepShell>
      )}

      {step === 6 && (
        <StepShell
          step={6}
          totalSteps={TOTAL_STEPS}
          kicker="Step 6 of 7"
          title="Show us your evidence."
          helpText={
            <>
              The agent reads everything you upload — contracts, invoices,
              email threads, screenshots — and pulls the facts that support
              your claim. The more you give it, the stronger your packet.
              Originals stay on your machine; we only use the extracted text.
            </>
          }
          onBack={back}
          onNext={next}
        >
          <EvidenceUpload files={files} onChange={setFiles} />
        </StepShell>
      )}

      {step === 7 && (
        <ReviewStep
          intake={intake}
          fileCount={files.length}
          onBack={back}
          onNext={next}
        />
      )}

      {step === 8 && (
        <RunStep
          caseId={caseId}
          events={events}
          done={done}
          error={error}
          isDemo={mode === 'demo'}
        />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
//                              Top header                                     //
// --------------------------------------------------------------------------- //

function Header() {
  return (
    <header className="flex items-center justify-between mb-12">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-sage-700 text-ink-50 flex items-center justify-center shadow-sm">
          <Scale size={20} />
        </div>
        <div>
          <p className="font-serif text-xl text-ink-900 leading-none">Quietcase</p>
          <p className="text-[11px] uppercase tracking-[0.2em] text-sage-600 mt-1">
            Small claims, filed right
          </p>
        </div>
      </div>
      <a
        href="https://ww2.nycourts.gov/courts/nyc/smallclaims/general.shtml"
        target="_blank"
        rel="noreferrer"
        className="text-xs text-ink-300 hover:text-sage-700 transition"
      >
        NYC Small Claims rules ↗
      </a>
    </header>
  );
}

// --------------------------------------------------------------------------- //
//                            Welcome (Step 1)                                 //
// --------------------------------------------------------------------------- //

function Welcome({
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

      {/* ─── Grader / one-click demo banner ─── */}
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
        Quietcase generates documents and educational guidance. It is not a
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
            One click and you'll see all four agents work end-to-end:
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

// --------------------------------------------------------------------------- //
//                              Review (Step 7)                                //
// --------------------------------------------------------------------------- //

function ReviewStep({
  intake,
  fileCount,
  onBack,
  onNext,
}: {
  intake: IntakeForm;
  fileCount: number;
  onBack: () => void;
  onNext: () => void;
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
      totalSteps={TOTAL_STEPS}
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

// --------------------------------------------------------------------------- //
//                              Run (Step 8)                                   //
// --------------------------------------------------------------------------- //

function RunStep({
  caseId,
  events,
  done,
  error,
  isDemo,
}: {
  caseId: string | null;
  events: AgentEvent[];
  done: boolean;
  error: string | null;
  isDemo: boolean;
}) {
  const downloadHref = useMemo(() => (caseId ? pdfURL(caseId) : '#'), [caseId]);

  return (
    <div className="max-w-4xl mx-auto animate-fade-in-up">
      {isDemo && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-ochre-400/30 bg-ochre-400/10 px-4 py-3 text-sm text-ink-900/80">
          <GraduationCap size={18} className="text-ochre-600 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold text-ochre-600 mb-0.5">Demo mode</p>
            <p>
              Running the bundled scenario: <i>Brooklyn freelance designer
              owed $4,800 by a NYC marketing LLC.</i> Four evidence files
              (contract, invoice, email thread, follow-up note) were
              uploaded for you. The agents below are doing real work — real
              NY DOS API call, real RAG over the legal corpus, real PDF
              generation.
            </p>
          </div>
        </div>
      )}
      <p className="text-xs uppercase tracking-[0.2em] text-sage-600 font-semibold mb-3">
        {isDemo ? 'Demo run · Building the packet' : 'Step 8 of 7 · Building your packet'}
      </p>
      <h1 className="font-serif text-3xl md:text-4xl text-ink-900 leading-tight mb-2">
        {done && !error
          ? 'Your packet is ready.'
          : error
          ? 'Something interrupted the build.'
          : 'The agents are working on your case.'}
      </h1>
      <p className="text-ink-900/70 mb-10 max-w-2xl">
        {done && !error
          ? 'Download the PDF below. It contains your demand letter, a court-ready Statement of Claim, an exhibit index, and a one-page filing guide for your borough.'
          : error
          ? error
          : 'This usually takes 30–60 seconds. Each step is a separate specialist agent — you can watch them hand off below.'}
      </p>

      <div className="bg-white rounded-2xl shadow-paper p-6 md:p-8">
        <AgentTimeline events={events} isRunning={!done} />
      </div>

      {done && !error && (
        <div className="mt-8 flex flex-col sm:flex-row items-center gap-4 bg-sage-700 text-ink-50 rounded-2xl p-6 md:p-8 shadow-paper">
          <div className="flex-1 min-w-0">
            <p className="font-serif text-xl mb-1">Your court-ready packet</p>
            <p className="text-sm text-ink-50/80">
              Statement of Claim + demand letter + exhibit index + borough
              filing instructions. Print two copies.
            </p>
          </div>
          <a
            href={downloadHref}
            target="_blank"
            rel="noreferrer"
            className="bg-ochre-400 hover:bg-ochre-500 text-ink-900 px-6 py-3 rounded-xl font-semibold inline-flex items-center gap-2 shadow-sm transition active:translate-y-[1px] shrink-0"
          >
            <Download size={18} /> Download PDF
          </a>
        </div>
      )}

      {!caseId && !error && (
        <p className="text-sm text-ink-300 mt-6 text-center">
          Connecting to <span className="font-mono">{BACKEND_URL}</span>…
        </p>
      )}
    </div>
  );
}
