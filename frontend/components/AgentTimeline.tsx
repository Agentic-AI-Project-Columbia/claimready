'use client';

import {
  Brain,
  Search,
  Scale,
  Building2,
  FileSignature,
  CheckCircle2,
  AlertCircle,
  Loader2,
  type LucideIcon,
} from 'lucide-react';
import clsx from 'clsx';
import type { AgentEvent } from '@/lib/types';

interface Props {
  events: AgentEvent[];
  isRunning: boolean;
}

interface RailItem {
  key: string;
  icon: LucideIcon;
  label: string;
  detail?: string;
  status: 'queued' | 'running' | 'done' | 'error';
}

/** Map raw stream events into the user-friendly rail of "what the agent is doing." */
function summarize(events: AgentEvent[], isRunning: boolean): RailItem[] {
  const items: RailItem[] = [
    { key: 'planner', icon: Brain, label: 'Planner orchestrating', status: 'queued' },
    { key: 'extractor', icon: Search, label: 'Reading your evidence', status: 'queued' },
    { key: 'defendant', icon: Building2, label: 'Looking up the business with NY State', status: 'queued' },
    { key: 'jurisdiction', icon: Scale, label: 'Verifying jurisdiction & computing damages', status: 'queued' },
    { key: 'drafter', icon: FileSignature, label: 'Drafting your packet', status: 'queued' },
  ];

  const byKey = (k: string) => items.find((i) => i.key === k)!;

  // Mark the planner as running as soon as the websocket opens.
  if (events.length > 0 || isRunning) byKey('planner').status = 'running';

  for (const ev of events) {
    const name = (ev.name || ev.agent || ev.to_agent || '').toLowerCase();
    const tool = (ev.tool_name || '').toLowerCase();

    if (name.includes('extract')) advance(byKey('extractor'), ev);
    if (name.includes('defendant') || tool.includes('lookup_ny_business'))
      advance(byKey('defendant'), ev);
    if (name.includes('jurisdiction') || tool.includes('validate_jurisdiction') || tool.includes('compute_damages') || tool.includes('search_legal_kb'))
      advance(byKey('jurisdiction'), ev);
    if (name.includes('drafter')) advance(byKey('drafter'), ev);

    if (ev.type === 'done') {
      items.forEach((i) => {
        if (i.status === 'running' || i.status === 'queued') i.status = 'done';
      });
    }
    if (ev.type === 'error') {
      items.forEach((i) => {
        if (i.status === 'running') i.status = 'error';
      });
    }
  }

  // If the run is still going, keep the most-recent "running" so user sees motion.
  return items;
}

function advance(item: RailItem, ev: AgentEvent) {
  if (item.status === 'queued') item.status = 'running';
  if (ev.type === 'tool_result' || ev.type === 'agent_completed') item.status = 'done';
  if (ev.preview) item.detail = ev.preview.slice(0, 90);
}

export function AgentTimeline({ events, isRunning }: Props) {
  const items = summarize(events, isRunning);
  return (
    <div className="space-y-3">
      {items.map((item, i) => {
        const Icon = item.icon;
        const isRunning = item.status === 'running';
        const isDone = item.status === 'done';
        const isError = item.status === 'error';
        return (
          <div
            key={item.key}
            className={clsx(
              'flex items-start gap-4 p-4 rounded-xl border transition',
              isRunning && 'bg-sage-50 border-sage-100 animate-pulse-soft',
              isDone && 'bg-white border-ink-200',
              isError && 'bg-ochre-400/10 border-ochre-400/30',
              !isRunning && !isDone && !isError && 'bg-ink-50 border-ink-200/60',
            )}
          >
            <div
              className={clsx(
                'w-10 h-10 rounded-full flex items-center justify-center shrink-0',
                isRunning && 'bg-sage-700 text-ink-50',
                isDone && 'bg-sage-100 text-sage-700',
                isError && 'bg-ochre-400 text-ink-900',
                !isRunning && !isDone && !isError && 'bg-ink-100 text-ink-300',
              )}
            >
              {isRunning ? (
                <Loader2 size={18} className="animate-spin" />
              ) : isDone ? (
                <CheckCircle2 size={18} />
              ) : isError ? (
                <AlertCircle size={18} />
              ) : (
                <Icon size={18} />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p
                className={clsx(
                  'font-medium text-sm',
                  isRunning && 'text-sage-800',
                  isDone && 'text-ink-900',
                  isError && 'text-ochre-600',
                  !isRunning && !isDone && !isError && 'text-ink-300',
                )}
              >
                {item.label}
              </p>
              {item.detail && (
                <p className="text-xs text-ink-300 mt-1 font-mono truncate">{item.detail}</p>
              )}
            </div>
            <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-300">
              {item.status}
            </span>
          </div>
        );
      })}
    </div>
  );
}
