'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Brain, Search, Scale, Building2, FileSignature,
  CheckCircle2, AlertCircle, Loader2, Wrench,
  ChevronDown, ChevronUp, type LucideIcon,
} from 'lucide-react';
import clsx from 'clsx';
import type { AgentEvent } from '@/lib/types';

interface Props {
  events: AgentEvent[];
  isRunning: boolean;
}

// ── Step definitions ──────────────────────────────────────────────────────────

interface StepDef {
  key: string;
  icon: LucideIcon;
  label: string;
  description: string;
  agentNames: string[];
  toolNames: string[];
  toolLabels: Record<string, string>;
}

const STEPS: StepDef[] = [
  {
    key: 'planner',
    icon: Brain,
    label: 'Planner',
    description: 'Decides the order of operations and hands off to each specialist in sequence.',
    agentNames: ['planner'],
    toolNames: [],
    toolLabels: {},
  },
  {
    key: 'extractor',
    icon: Search,
    label: 'Evidence Extractor',
    description: 'Uses Gemini vision to read every uploaded file — contracts, invoices, emails, notes — and pulls structured case facts.',
    agentNames: ['extractor'],
    toolNames: [],
    toolLabels: {},
  },
  {
    key: 'defendant',
    icon: Building2,
    label: 'Defendant Resolver',
    description: 'Searches the NY Department of State Active Corporations database by name to find the official entity and service-of-process address.',
    agentNames: ['defendant', 'defendantresolver'],
    toolNames: ['lookup_ny_business'],
    toolLabels: {
      lookup_ny_business: 'Searching NY DOS Active Corporations…',
    },
  },
  {
    key: 'jurisdiction',
    icon: Scale,
    label: 'Jurisdiction Checker',
    description: 'Validates the $10 k cap (CCA § 1805), 6-year SOL (CPLR § 213), and venue, then computes 9% statutory interest (CPLR § 5004).',
    agentNames: ['jurisdiction', 'jurisdictionchecker'],
    toolNames: ['validate_jurisdiction', 'compute_damages', 'search_legal_kb'],
    toolLabels: {
      validate_jurisdiction: 'Checking monetary cap, statute of limitations & venue…',
      compute_damages: 'Computing principal + 9% pre-judgment interest…',
      search_legal_kb: 'Searching legal knowledge base for statute citations…',
    },
  },
  {
    key: 'drafter',
    icon: FileSignature,
    label: 'Drafter',
    description: 'Reviews the final CaseFacts and flags any missing fields before the PDF is rendered.',
    agentNames: ['drafter'],
    toolNames: [],
    toolLabels: {},
  },
];

// ── Feed entry ────────────────────────────────────────────────────────────────

interface FeedEntry {
  id: string;
  stepKey: string;
  kind: 'handoff' | 'tool_call' | 'tool_result' | 'fact' | 'done' | 'error';
  headline: string;
  detail?: string;
}

type StepStatus = 'queued' | 'running' | 'done' | 'error';

interface StepState {
  status: StepStatus;
  activeTool?: string;
  toolsDone: string[];
}

// ── Derive state from event stream ────────────────────────────────────────────

function derive(events: AgentEvent[], isRunning: boolean) {
  const states: Record<string, StepState> = {};
  for (const s of STEPS) states[s.key] = { status: 'queued', toolsDone: [] };
  const feed: FeedEntry[] = [];
  let idx = 0;
  const push = (e: Omit<FeedEntry, 'id'>) => feed.push({ id: String(idx++), ...e });

  if (events.length > 0 || isRunning) states['planner'].status = 'running';

  const stepForAgent = (name: string) =>
    STEPS.find(s => s.agentNames.some(a => name.toLowerCase().includes(a)));
  const stepForTool = (tool: string) =>
    STEPS.find(s => s.toolNames.includes(tool.toLowerCase()));

  for (const ev of events) {
    const agentName = (ev.name || ev.agent || ev.to_agent || '').toLowerCase();
    const toolName  = (ev.tool_name || '').toLowerCase();

    // ── Agent activation ──────────────────────────────────────────────────
    const activeStep = stepForAgent(agentName);
    if (activeStep && states[activeStep.key].status === 'queued') {
      states[activeStep.key].status = 'running';
      push({
        stepKey: activeStep.key,
        kind: 'handoff',
        headline: `→ ${activeStep.label} started`,
      });
    }

    // ── Tool called ───────────────────────────────────────────────────────
    if (ev.type === 'tool_called' || (toolName && ev.type?.includes('tool'))) {
      const ts = stepForTool(toolName);
      if (ts) {
        states[ts.key].activeTool = toolName;
        states[ts.key].status = 'running';

        // Format args as readable key=value pairs
        let argsStr = '';
        if (ev.args && typeof ev.args === 'object') {
          argsStr = Object.entries(ev.args)
            .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
            .join('  ·  ');
        } else if (ev.args) {
          argsStr = String(ev.args).slice(0, 200);
        }

        push({
          stepKey: ts.key,
          kind: 'tool_call',
          headline: ts.toolLabels[toolName] ?? `Calling ${toolName}`,
          detail: argsStr || undefined,
        });
      }
    }

    // ── Tool result ───────────────────────────────────────────────────────
    if (ev.type === 'tool_result' && ev.preview) {
      const ts = stepForTool(toolName) ?? stepForAgent(agentName);
      if (ts) {
        if (toolName && !states[ts.key].toolsDone.includes(toolName)) {
          states[ts.key].toolsDone.push(toolName);
        }
        states[ts.key].activeTool = undefined;
      }

      // Try to pretty-print JSON previews
      let detail = ev.preview;
      try {
        const parsed = JSON.parse(ev.preview);
        detail = JSON.stringify(parsed, null, 2).slice(0, 800);
      } catch {}

      push({
        stepKey: ts?.key ?? 'planner',
        kind: 'tool_result',
        headline: `Result from ${toolName || 'tool'}`,
        detail,
      });
    }

    // ── Agent completed ───────────────────────────────────────────────────
    if (ev.type === 'agent_completed') {
      const cs = stepForAgent(agentName);
      if (cs) {
        states[cs.key].status = 'done';
        push({ stepKey: cs.key, kind: 'handoff', headline: `✓ ${cs.label} complete` });
      }
    }

    // ── Partial facts update ──────────────────────────────────────────────
    if (ev.type === 'facts_partial' && ev.facts) {
      const f = ev.facts as any;
      const lines: string[] = [];
      if (f?.plaintiff?.name)           lines.push(`Plaintiff: ${f.plaintiff.name}`);
      if (f?.defendant?.dos_entity_name) lines.push(`Defendant (DOS): ${f.defendant.dos_entity_name}`);
      if (f?.defendant?.service_address) lines.push(`Service address: ${f.defendant.service_address}`);
      if (f?.contract?.agreed_amount)    lines.push(`Contract amount: $${Number(f.contract.agreed_amount).toLocaleString()}`);
      if (f?.damages?.principal)         lines.push(`Principal: $${Number(f.damages.principal).toLocaleString()}`);
      if (f?.damages?.interest_accrued)  lines.push(`Interest accrued: $${Number(f.damages.interest_accrued).toLocaleString()}`);
      if (f?.damages?.total_demanded)    lines.push(`Total demanded: $${Number(f.damages.total_demanded).toLocaleString()}`);
      if (f?.venue?.borough)             lines.push(`Venue: ${f.venue.borough} County`);
      if (f?.jurisdiction_check?.in_monetary_limit !== undefined)
        lines.push(`Within $10k cap: ${f.jurisdiction_check.in_monetary_limit ? 'Yes ✓' : 'No ✗'}`);
      if (f?.jurisdiction_check?.within_statute_of_limitations !== undefined)
        lines.push(`Within SOL: ${f.jurisdiction_check.within_statute_of_limitations ? 'Yes ✓' : 'No ✗'}`);

      if (lines.length) {
        push({
          stepKey: 'planner',
          kind: 'fact',
          headline: 'Case facts updated',
          detail: lines.join('\n'),
        });
      }
    }

    // ── Done ──────────────────────────────────────────────────────────────
    if (ev.type === 'done') {
      for (const s of STEPS) if (states[s.key].status !== 'error') states[s.key].status = 'done';
      const f = ev.facts as any;
      const summary: string[] = [];
      if (f?.plaintiff?.name)           summary.push(`Plaintiff: ${f.plaintiff.name}`);
      if (f?.defendant?.dos_entity_name || f?.defendant?.name)
        summary.push(`Defendant: ${f.defendant.dos_entity_name || f.defendant.name}`);
      if (f?.damages?.total_demanded)   summary.push(`Total demanded: $${Number(f.damages.total_demanded).toLocaleString()}`);
      if (f?.venue?.borough)            summary.push(`Filed in: ${f.venue.borough} County`);
      if (f?.notes?.length)             summary.push(`Notes: ${f.notes.join(' | ')}`);
      push({
        stepKey: 'drafter',
        kind: 'done',
        headline: '✅ Pipeline complete — PDF ready for download',
        detail: summary.length ? summary.join('\n') : undefined,
      });
    }

    // ── Error ─────────────────────────────────────────────────────────────
    if (ev.type === 'error') {
      for (const s of STEPS) if (states[s.key].status === 'running') states[s.key].status = 'error';
      push({
        stepKey: 'planner',
        kind: 'error',
        headline: '✗ Error',
        detail: ev.message,
      });
    }
  }

  return { states, feed };
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StepCard({ step, state }: { step: StepDef; state: StepState }) {
  const Icon = step.icon;
  const r = state.status === 'running';
  const d = state.status === 'done';
  const e = state.status === 'error';
  const q = state.status === 'queued';

  return (
    <div className={clsx(
      'rounded-xl border px-4 py-3 transition-all duration-300',
      r && 'bg-sage-50 border-sage-200 shadow-sm',
      d && 'bg-white border-ink-200',
      e && 'bg-red-50 border-red-200',
      q && 'bg-ink-50/50 border-ink-100',
    )}>
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-0.5',
          r && 'bg-sage-700 text-ink-50',
          d && 'bg-sage-100 text-sage-700',
          e && 'bg-red-100 text-red-600',
          q && 'bg-ink-100 text-ink-300',
        )}>
          {r ? <Loader2 size={14} className="animate-spin" />
             : d ? <CheckCircle2 size={14} />
             : e ? <AlertCircle size={14} />
             : <Icon size={14} />}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <p className={clsx(
              'font-semibold text-sm',
              r && 'text-sage-800', d && 'text-ink-900',
              e && 'text-red-700', q && 'text-ink-300',
            )}>
              {step.label}
            </p>
            <span className={clsx(
              'text-[10px] uppercase tracking-widest font-bold px-2 py-0.5 rounded-full shrink-0',
              r && 'bg-sage-100 text-sage-700',
              d && 'bg-green-50 text-green-700',
              e && 'bg-red-100 text-red-600',
              q && 'bg-ink-100 text-ink-300',
            )}>
              {state.status}
            </span>
          </div>

          <p className={clsx('text-xs mt-0.5 leading-relaxed', q ? 'text-ink-200' : 'text-ink-400')}>
            {step.description}
          </p>

          {/* Active tool */}
          {r && state.activeTool && step.toolLabels[state.activeTool] && (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-sage-700 font-medium">
              <Wrench size={11} className="shrink-0 animate-pulse" />
              {step.toolLabels[state.activeTool]}
            </div>
          )}

          {/* Completed tool badges */}
          {state.toolsDone.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {state.toolsDone.map(t => (
                <span key={t} className="inline-flex items-center gap-1 text-[10px] bg-sage-50 text-sage-600 border border-sage-100 px-2 py-0.5 rounded-full">
                  <CheckCircle2 size={9} /> {t.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FeedItem({ entry }: { entry: FeedEntry }) {
  const [open, setOpen] = useState(false);

  const colors: Record<FeedEntry['kind'], string> = {
    handoff:     'text-ink-300',
    tool_call:   'text-ochre-400',
    tool_result: 'text-sage-400',
    fact:        'text-sage-400',
    done:        'text-ochre-400 font-bold',
    error:       'text-red-400',
  };

  return (
    <div className="border-b border-ink-800/50 pb-2 last:border-0">
      <button
        className={clsx('w-full text-left flex items-start justify-between gap-2 text-xs', colors[entry.kind])}
        onClick={() => entry.detail && setOpen(o => !o)}
      >
        <span className="leading-relaxed">{entry.headline}</span>
        {entry.detail && (
          open ? <ChevronUp size={12} className="mt-0.5 shrink-0 text-ink-500" />
               : <ChevronDown size={12} className="mt-0.5 shrink-0 text-ink-500" />
        )}
      </button>
      {open && entry.detail && (
        <pre className="mt-1.5 text-[11px] text-ink-200 whitespace-pre-wrap break-words leading-relaxed bg-black/30 rounded p-2 overflow-auto max-h-48">
          {entry.detail}
        </pre>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function AgentTimeline({ events, isRunning }: Props) {
  const { states, feed } = derive(events, isRunning);
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [feed.length]);

  const doneCount = STEPS.filter(s => states[s.key].status === 'done').length;
  const activeStep = STEPS.find(s => states[s.key].status === 'running');

  return (
    <div className="space-y-6">

      {/* Progress bar */}
      {(isRunning || doneCount > 0) && (
        <div>
          <div className="flex justify-between text-xs text-ink-300 mb-1.5">
            <span>{activeStep ? `Running: ${activeStep.label}` : doneCount === STEPS.length ? 'All steps complete' : 'Starting…'}</span>
            <span>{doneCount} / {STEPS.length} steps done</span>
          </div>
          <div className="h-1.5 bg-ink-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-sage-700 rounded-full transition-all duration-700"
              style={{ width: `${(doneCount / STEPS.length) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Step cards */}
      <div className="space-y-2">
        {STEPS.map(step => (
          <StepCard key={step.key} step={step} state={states[step.key]} />
        ))}
      </div>

      {/* Event feed */}
      <div className="rounded-xl bg-ink-900 border border-ink-800 shadow-inner overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-ink-800">
          <p className="text-[10px] uppercase tracking-widest font-bold text-ink-200">
            Live event feed
          </p>
          <span className="text-[10px] text-ink-400">{feed.length} events</span>
        </div>
        <div ref={feedRef} className="max-h-72 overflow-auto px-4 py-3 space-y-2">
          {feed.length > 0 ? (
            feed.map(entry => <FeedItem key={entry.id} entry={entry} />)
          ) : (
            <p className="text-xs text-ink-400">Waiting for the first agent event…</p>
          )}
        </div>
      </div>

    </div>
  );
}
