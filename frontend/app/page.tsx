'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowRight,
  Scale,
  Sparkles,
  Download,
  FileSearch,
  Shield,
  PlayCircle,
  ChevronDown,
  ChevronUp,
  RotateCcw,
} from 'lucide-react';
import clsx from 'clsx';

import { StepShell } from '@/components/StepShell';
import { Field, FieldGrid } from '@/components/Field';
import { EvidenceUpload, SAMPLE_DRAG_MIME, type PreviewFile } from '@/components/EvidenceUpload';
import { DefendantLookup } from '@/components/DefendantLookup';
import { AgentTimeline } from '@/components/AgentTimeline';
import {
  BACKEND_URL,
  caseEventsURL,
  createCase,
  getCaseFacts,
  pdfURL,
  prepareCase,
  runDemo,
  startCase,
  uploadEvidence,
} from '@/lib/api';
import { emptyIntake, demoIntake, type AgentEvent, type IntakeForm } from '@/lib/types';

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
    let settled = false;
    let polling = false;

    async function pollUntilReady(reason: string) {
      if (polling || settled) return;
      polling = true;
      const deadline = Date.now() + 150_000;
      while (Date.now() < deadline && !settled) {
        try {
          const data = await getCaseFacts(case_id);
          if (data.status === 'done' || data.status === 'done_with_errors') {
            settled = true;
            setEvents((prev) => [
              ...prev,
              {
                type: 'done',
                facts: data.facts,
                pdf_ready: true,
                message:
                  data.status === 'done_with_errors'
                    ? `Recovered after ${reason}; fallback packet is ready.`
                    : `Recovered after ${reason}; packet is ready.`,
              },
            ]);
            setDone(true);
            setError(null);
            return;
          }
          if (data.status === 'error') {
            settled = true;
            setDone(true);
            setError('The backend could not finish this packet.');
            return;
          }
        } catch {
          // Keep polling; Cloud Run can briefly route before state is visible.
        }
        await new Promise((resolve) => setTimeout(resolve, 3000));
      }
      if (!settled) {
        setDone(true);
        setError('Lost connection before the packet was ready. Try again.');
      }
    }

    const ws = new WebSocket(caseEventsURL(case_id));
    ws.onmessage = (m) => {
      try {
        const payload = JSON.parse(m.data) as AgentEvent;
        setEvents((prev) => [...prev, payload]);
        if (payload.type === 'done') {
          settled = true;
          setDone(true);
          setError(null);
        }
        if (payload.type === 'error') {
          setEvents((prev) => [
            ...prev,
            {
              type: 'handoff',
              to_agent: 'Recovery Poller',
              message: 'Checking whether a fallback packet is available.',
            },
          ]);
          pollUntilReady('agent error');
        }
      } catch {}
    };
    ws.onerror = () => {
      setEvents((prev) => [
        ...prev,
        {
          type: 'handoff',
          to_agent: 'Recovery Poller',
          message: 'WebSocket error; checking packet status.',
        },
      ]);
      pollUntilReady('WebSocket error');
    };
    ws.onclose = () => {
      if (!settled) {
        setEvents((prev) => [
          ...prev,
          {
            type: 'handoff',
            to_agent: 'Recovery Poller',
            message: 'WebSocket closed; checking packet status.',
          },
        ]);
        pollUntilReady('WebSocket close');
      }
    };
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

  function handleRetry() {
    setCaseId(null);
    setEvents([]);
    setDone(false);
    setError(null);
    setDemoStarting(false);
    if (mode === 'demo') {
      startDemoRun();
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // STEP 8 — kick off the wizard run when we land on it (skip if demo)
  // Flow: prepare case → upload evidence → embed extracted text → start run
  // ──────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (step !== TOTAL_STEPS || caseId || mode === 'demo') return;
    (async () => {
      try {
        let enrichedIntake: Record<string, any> = { ...intake };
        if (files.length > 0) {
          const { case_id: prepId } = await prepareCase();
          const { items } = await uploadEvidence(prepId, files.map((f) => f.file));
          enrichedIntake.evidence = items;
          const { case_id } = await startCase(prepId, enrichedIntake);
          setCaseId(case_id);
          attachWebSocket(case_id);
        } else {
          const { case_id } = await createCase(enrichedIntake);
          setCaseId(case_id);
          attachWebSocket(case_id);
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
      <Header onLogoClick={() => setStep(1)} />

      {step === 1 && (
        <Welcome onNext={next} onDemo={startDemoRun} demoStarting={demoStarting} />
      )}

      {step === 2 && (
        <StepShell
          step={2}
          totalSteps={TOTAL_STEPS}
          kicker="Step 2 of 8"
          title="Tell us about you, the plaintiff."
          onStepClick={(s) => setStep(s)}
          onAutofill={() => setIntake(demoIntake)}
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
          kicker="Step 3 of 8"
          title="Who owes you the money?"
          onStepClick={(s) => setStep(s)}
          onAutofill={() => setIntake(demoIntake)}
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
              hint="As you type, we'll check NY State live and confirm the legal entity."
              span="full"
            >
              <DefendantLookup
                value={intake.defendant.name}
                onChange={(name) =>
                  setIntake((p) => ({ ...p, defendant: { ...p.defendant, name } }))
                }
                onPick={(m) =>
                  setIntake((p) => ({
                    ...p,
                    defendant: {
                      ...p.defendant,
                      name: m.current_entity_name,
                      dos_entity_name: m.current_entity_name,
                      dos_id: m.dos_id,
                      service_address: m.service_address,
                      registered_agent: m.registered_agent,
                    },
                  }))
                }
              />
            </Field>
          </FieldGrid>
        </StepShell>
      )}

      {step === 4 && (
        <StepShell
          step={4}
          totalSteps={TOTAL_STEPS}
          kicker="Step 4 of 8"
          title="What did you agree to do?"
          onStepClick={(s) => setStep(s)}
          onAutofill={() => setIntake(demoIntake)}
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
      )}

      {step === 5 && (
        <StepShell
          step={5}
          totalSteps={TOTAL_STEPS}
          kicker="Step 5 of 8"
          title="What went wrong?"
          onStepClick={(s) => setStep(s)}
          onAutofill={() => setIntake(demoIntake)}
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
      )}

      {step === 6 && (
        <StepShell
          step={6}
          totalSteps={TOTAL_STEPS}
          kicker="Step 6 of 8"
          title="Show us your evidence."
          onStepClick={(s) => setStep(s)}
          onAutofill={() => setIntake(demoIntake)}
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
          <SampleEvidencePack />
          <EvidenceUpload files={files} onChange={setFiles} />
        </StepShell>
      )}

      {step === 7 && (
        <ReviewStep
          intake={intake}
          fileCount={files.length}
          onBack={back}
          onNext={next}
          onStepClick={(s) => setStep(s)}
          onAutofill={() => setIntake(demoIntake)}
        />
      )}

      {step === 8 && (
        <RunStep
          caseId={caseId}
          events={events}
          done={done}
          error={error}
          isDemo={mode === 'demo'}
          onRetry={handleRetry}
        />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
//                              Top header                                     //
// --------------------------------------------------------------------------- //

function Header({ onLogoClick }: { onLogoClick: () => void }) {
  return (
    <header className="flex items-center justify-between mb-12">
      <button
        type="button"
        onClick={onLogoClick}
        className="flex items-center gap-3 hover:opacity-80 transition"
      >
        <div className="w-10 h-10 rounded-xl bg-sage-700 text-ink-50 flex items-center justify-center shadow-sm">
          <Scale size={20} />
        </div>
        <div className="text-left">
          <p className="font-serif text-xl text-ink-900 leading-none">ClaimReady</p>
          <p className="text-[11px] uppercase tracking-[0.2em] text-sage-600 mt-1">
            Small claims, filed right
          </p>
        </div>
      </button>
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
//                       Sample evidence pack (Step 6)                         //
// --------------------------------------------------------------------------- //

const SAMPLE_EVIDENCE = [
  { file: '01_services_agreement.txt', label: 'Services agreement', desc: 'Signed contract with scope, fee, payment terms' },
  { file: '02_invoice_2025_001.txt',   label: 'Invoice',            desc: 'Itemised line items with totals and due date' },
  { file: '03_email_thread.eml',       label: 'Email thread',       desc: 'Delivery confirmation + follow-ups' },
  { file: '04_followup_note.txt',      label: 'Follow-up log',      desc: 'Phone call attempts and dates' },
];

function SampleEvidencePack() {
  const handleDragStart = (e: React.DragEvent, file: string) => {
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData(SAMPLE_DRAG_MIME, file);
    e.dataTransfer.setData('text/plain', file);
  };

  return (
    <div className="mb-5 rounded-xl border border-ochre-400/30 bg-ochre-400/5 p-4">
      <div className="flex items-start gap-3">
        <div className="hidden sm:flex w-8 h-8 rounded-lg bg-ochre-400 text-ink-900 items-center justify-center shrink-0">
          <Download size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] uppercase tracking-widest text-ochre-600 font-semibold mb-0.5">
            Want to try the wizard end-to-end?
          </p>
          <p className="text-sm text-ink-900 mb-2">
            Drag any of these into the evidence box below, or click to download. Same files the
            one-click demo uses — they show you what good evidence looks like.
          </p>
          <div className="flex flex-wrap gap-2">
            {SAMPLE_EVIDENCE.map((s) => (
              <a
                key={s.file}
                href={`/sample-evidence/${s.file}`}
                download
                draggable
                onDragStart={(e) => handleDragStart(e, s.file)}
                title={`Drag onto the evidence box, or click to download. ${s.desc}`}
                className="text-xs font-medium px-3 py-1.5 rounded-lg bg-white border border-ochre-400/40 text-ink-900 hover:border-ochre-500 hover:bg-ochre-400/10 transition inline-flex items-center gap-1.5 cursor-grab active:cursor-grabbing select-none"
              >
                <Download size={12} /> {s.label}
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
//                              Review (Step 7)                                //
// --------------------------------------------------------------------------- //

interface MissingField {
  label: string;
  jumpTo: number;
}

function findMissingRequired(intake: IntakeForm, fileCount: number): MissingField[] {
  const missing: MissingField[] = [];
  if (!intake.plaintiff.name) missing.push({ label: 'Your full legal name', jumpTo: 2 });
  if (!intake.plaintiff.address) missing.push({ label: 'Your street address', jumpTo: 2 });
  if (!intake.defendant.name) missing.push({ label: "Defendant's business name", jumpTo: 3 });
  if (!intake.contract.scope_of_work) missing.push({ label: 'What you agreed to do', jumpTo: 4 });
  if (!intake.contract.agreed_amount || intake.contract.agreed_amount <= 0) {
    missing.push({ label: 'Agreed contract amount', jumpTo: 4 });
  }
  if (!intake.breach.date) missing.push({ label: 'Date of breach', jumpTo: 5 });
  if (!intake.breach.amount_owed || intake.breach.amount_owed <= 0) {
    missing.push({ label: 'Amount unpaid', jumpTo: 5 });
  }
  if (!intake.venue.borough) missing.push({ label: 'Borough you will file in', jumpTo: 5 });
  // Evidence is strongly recommended but not strictly required — surface as a soft warning, not a block
  return missing;
}

function ReviewStep({
  intake,
  fileCount,
  onBack,
  onNext,
  onStepClick,
  onAutofill,
}: {
  intake: IntakeForm;
  fileCount: number;
  onBack: () => void;
  onNext: () => void;
  onStepClick?: (step: number) => void;
  onAutofill?: () => void;
}) {
  const missing = findMissingRequired(intake, fileCount);
  const evidenceMissing = fileCount === 0;

  const isMissing = (v: string | number) =>
    v === '' || v === '—' || v === '$0.00';

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
      kicker="Step 7 of 8"
      title="One last look before we generate."
      onStepClick={onStepClick}
      onAutofill={onAutofill}
      helpText={
        <>
          When you click Generate, our planner agent kicks off four
          specialists in sequence: Extractor → Defendant lookup →
          Jurisdiction check → Drafter. Watch them work in real time.
        </>
      }
      onBack={onBack}
      onNext={onNext}
      nextLabel="Generate my packet"
      nextDisabled={missing.length > 0}
    >
      {missing.length > 0 && (
        <div
          role="alert"
          className="mb-6 rounded-xl border border-ochre-400/40 bg-ochre-400/10 px-4 py-3"
        >
          <p className="text-xs uppercase tracking-widest text-ochre-600 font-semibold mb-1.5">
            {missing.length} required field{missing.length > 1 ? 's' : ''} still empty
          </p>
          <p className="text-sm text-ink-900/80 mb-2">
            We can't generate the complaint until these are filled in. Click any item to jump back.
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {missing.map((m) => (
              <li key={m.label}>
                <button
                  type="button"
                  onClick={() => onStepClick?.(m.jumpTo)}
                  className="text-xs font-medium px-2.5 py-1 rounded-md bg-white border border-ochre-400/40 text-ochre-600 hover:bg-ochre-400/20 transition"
                >
                  {m.label} →
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {missing.length === 0 && evidenceMissing && (
        <div className="mb-6 rounded-xl border border-ink-200 bg-ink-50/60 px-4 py-3 text-sm text-ink-900/80">
          <p className="font-semibold text-ink-900 mb-1">No evidence attached.</p>
          <p>
            You can still generate the packet, but the Statement of Claim is much stronger when
            the agent has documents to reference. You can{' '}
            <button
              type="button"
              onClick={() => onStepClick?.(6)}
              className="underline text-sage-700 hover:text-sage-800"
            >
              go back and attach evidence
            </button>{' '}
            or proceed without it.
          </p>
        </div>
      )}

      <div className="space-y-8">
        {sections.map((s) => (
          <div key={s.title}>
            <p className="text-xs uppercase tracking-[0.18em] text-sage-600 font-semibold mb-3">
              {s.title}
            </p>
            <dl className="divide-y divide-ink-200/70">
              {s.rows.map(([k, v]) => {
                const empty = typeof v === 'string' && isMissing(v);
                return (
                  <div key={k} className="grid grid-cols-3 py-2.5 gap-4">
                    <dt className="text-sm text-ink-300">{k}</dt>
                    <dd className={clsx('col-span-2 text-sm', empty ? 'text-ochre-600 font-medium' : 'text-ink-900')}>
                      {empty ? `${v}  · missing` : v}
                    </dd>
                  </div>
                );
              })}
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

/** The hardcoded facts for the one-click demo — matches backend/demo_scenario.py */
const DEMO_CASE = {
  plaintiff: { name: 'Jane Q. Doe', address: '123 Smith Street, Brooklyn NY 11201', email: 'jane@janedoedesign.example' },
  defendant: { name: 'Vanguard Marketing LLC', note: 'NY DOS lookup will resolve the official registered address' },
  contract: {
    date: 'January 15, 2025',
    scope: '12 original illustrations + 1 brand-color guideline for Spring 2025 product launch',
    amount: '$4,800.00',
    terms: 'Net 30 from delivery',
  },
  timeline: [
    { date: 'Mar 1, 2025', event: 'All files delivered on time; invoice #2025-001 issued' },
    { date: 'Mar 3, 2025', event: 'Client confirms receipt in writing: "illustrations look fantastic"' },
    { date: 'Mar 31, 2025', event: 'Payment due — nothing received (breach date)' },
    { date: 'Apr 1, 2025', event: 'First payment reminder sent — no reply' },
    { date: 'Apr 14, 2025', event: 'Second email + phone call to Derek\'s direct line — voicemail' },
    { date: 'Apr 17, 2025', event: 'Called main line — "accounting will call back in 24h" — never did' },
    { date: 'Apr 21, 2025', event: 'Final notice email threatening small-claims filing' },
  ],
  evidence: [
    { file: '01_services_agreement.txt', desc: 'Signed contract — scope, $4,800 flat fee, Net 30, Kings County jurisdiction' },
    { file: '02_invoice_2025_001.txt', desc: 'Invoice #2025-001 — itemised line items totaling $4,800, due Mar 31' },
    { file: '03_email_thread.eml', desc: '5-email thread — delivery, client confirmation, 3× unanswered follow-ups' },
    { file: '04_followup_note.txt', desc: 'Personal log — phone call attempts, dates, amounts, SOL analysis' },
  ],
  legal: [
    'CCA § 1805 — $10,000 monetary cap ✓ ($4,800 qualifies)',
    'CPLR § 213(2) — 6-year SOL ✓ (breach Mar 31, 2025)',
    'CPLR § 5004 — 9% pre-judgment interest will be computed',
    'Venue: Kings County (Brooklyn) — contract performance + defendant location',
  ],
};

function DemoCaseBrief() {
  const [timelineOpen, setTimelineOpen] = useState(false);

  return (
    <div className="rounded-2xl border border-ochre-400/30 bg-gradient-to-br from-ochre-400/5 to-white divide-y divide-ink-200/60 text-sm">

      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4">
        <GraduationCap size={18} className="text-ochre-600 shrink-0" />
        <div>
          <p className="text-[10px] uppercase tracking-widest font-bold text-ochre-600">Demo scenario</p>
          <p className="font-serif text-base text-ink-900 leading-snug">
            Freelance designer vs. NYC LLC — $4,800 unpaid invoice
          </p>
        </div>
      </div>

      {/* Parties */}
      <div className="grid grid-cols-2 gap-4 px-5 py-4">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-ink-300 font-semibold mb-1">Plaintiff</p>
          <p className="font-medium text-ink-900">{DEMO_CASE.plaintiff.name}</p>
          <p className="text-ink-400 text-xs">{DEMO_CASE.plaintiff.address}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-ink-300 font-semibold mb-1">Defendant</p>
          <p className="font-medium text-ink-900">{DEMO_CASE.defendant.name}</p>
          <p className="text-ink-400 text-xs">{DEMO_CASE.defendant.note}</p>
        </div>
      </div>

      {/* Contract */}
      <div className="px-5 py-4 space-y-1.5">
        <p className="text-[10px] uppercase tracking-widest text-ink-300 font-semibold mb-2">The contract</p>
        <div className="grid grid-cols-3 gap-x-4 text-xs">
          <span className="text-ink-400">Signed</span>
          <span className="col-span-2 text-ink-900">{DEMO_CASE.contract.date}</span>
        </div>
        <div className="grid grid-cols-3 gap-x-4 text-xs">
          <span className="text-ink-400">Scope</span>
          <span className="col-span-2 text-ink-900">{DEMO_CASE.contract.scope}</span>
        </div>
        <div className="grid grid-cols-3 gap-x-4 text-xs">
          <span className="text-ink-400">Amount</span>
          <span className="col-span-2 font-semibold text-ink-900">{DEMO_CASE.contract.amount}</span>
        </div>
        <div className="grid grid-cols-3 gap-x-4 text-xs">
          <span className="text-ink-400">Payment</span>
          <span className="col-span-2 text-ink-900">{DEMO_CASE.contract.terms}</span>
        </div>
      </div>

      {/* Timeline toggle */}
      <div className="px-5 py-3">
        <button
          className="w-full flex items-center justify-between text-xs font-semibold text-ink-400 hover:text-ink-700 transition"
          onClick={() => setTimelineOpen(o => !o)}
        >
          <span className="uppercase tracking-widest">Case timeline ({DEMO_CASE.timeline.length} events)</span>
          {timelineOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>
        {timelineOpen && (
          <ol className="mt-3 space-y-2 border-l-2 border-ink-200 pl-4">
            {DEMO_CASE.timeline.map((t, i) => (
              <li key={i} className="text-xs relative before:absolute before:-left-[1.1rem] before:top-1.5 before:w-2 before:h-2 before:rounded-full before:bg-ink-200">
                <span className="text-ochre-600 font-semibold">{t.date}</span>
                <span className="text-ink-700 ml-2">{t.event}</span>
              </li>
            ))}
          </ol>
        )}
      </div>

      {/* Evidence */}
      <div className="px-5 py-4">
        <p className="text-[10px] uppercase tracking-widest text-ink-300 font-semibold mb-2">Evidence loaded ({DEMO_CASE.evidence.length} files)</p>
        <ul className="space-y-1.5">
          {DEMO_CASE.evidence.map((e, i) => (
            <li key={i} className="text-xs flex gap-2">
              <span className="font-mono text-sage-600 shrink-0">{e.file}</span>
              <span className="text-ink-400">{e.desc}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Legal checks */}
      <div className="px-5 py-4">
        <p className="text-[10px] uppercase tracking-widest text-ink-300 font-semibold mb-2">Legal checklist the agents will verify</p>
        <ul className="space-y-1">
          {DEMO_CASE.legal.map((l, i) => (
            <li key={i} className="text-xs text-ink-600 flex gap-1.5">
              <span className="text-sage-500 shrink-0">·</span>{l}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function RunStep({
  caseId,
  events,
  done,
  error,
  isDemo,
  onRetry,
}: {
  caseId: string | null;
  events: AgentEvent[];
  done: boolean;
  error: string | null;
  isDemo: boolean;
  onRetry?: () => void;
}) {
  const downloadHref = useMemo(() => (caseId ? pdfURL(caseId) : '#'), [caseId]);

  const [elapsed, setElapsed] = useState(0);
  const t0 = useRef(Date.now());
  useEffect(() => {
    t0.current = Date.now();
    setElapsed(0);
  }, [caseId]);
  useEffect(() => {
    if (done || error) return;
    const iv = setInterval(() => setElapsed(Math.floor((Date.now() - t0.current) / 1000)), 1000);
    return () => clearInterval(iv);
  }, [done, error]);

  return (
    <div className="max-w-6xl mx-auto animate-fade-in-up">
      <p className="text-xs uppercase tracking-[0.2em] text-sage-600 font-semibold mb-3">
        {isDemo ? 'Demo run · Building the packet' : 'Step 8 of 8 · Building your packet'}
      </p>
      <h1 className="font-serif text-3xl md:text-4xl text-ink-900 leading-tight mb-2">
        {done && !error
          ? 'Packet is ready.'
          : error
          ? 'Something interrupted the build.'
          : 'The agents are working on the case.'}
      </h1>
      <p className="text-ink-900/70 mb-8 max-w-2xl">
        {done && !error
          ? 'Download the PDF below. It contains a demand letter, court-ready Statement of Claim, exhibit index, and filing guide.'
          : error
          ? error
          : <>This takes 30–60 s. Each specialist agent runs in sequence — watch them hand off in real time on the right. <span className="font-mono text-sage-600">{elapsed}s</span></>}
      </p>

      {error && onRetry && (
        <button
          onClick={onRetry}
          className="mb-6 bg-sage-700 hover:bg-sage-800 text-ink-50 px-6 py-3 rounded-xl font-semibold inline-flex items-center gap-2 shadow-sm transition active:translate-y-[1px]"
        >
          <RotateCcw size={18} /> Try again
        </button>
      )}

      {/* Two-column layout in demo mode so the case brief sits beside the timeline */}
      <div className={clsx(isDemo ? 'grid grid-cols-1 lg:grid-cols-2 gap-6 items-start' : '')}>

        {isDemo && <DemoCaseBrief />}

        <div className="bg-white rounded-2xl shadow-paper p-6 md:p-8">
          {!isDemo && (
            <p className="text-xs uppercase tracking-widest text-ink-300 font-semibold mb-4">
              Agent pipeline
            </p>
          )}
          <AgentTimeline events={events} isRunning={!done} />
        </div>
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
