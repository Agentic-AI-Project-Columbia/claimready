'use client';

import { useMemo } from 'react';
import { Download, GraduationCap } from 'lucide-react';
import { AgentTimeline } from '@/components/AgentTimeline';
import { BACKEND_URL, pdfURL } from '@/lib/api';
import type { AgentEvent } from '@/lib/types';

export function RunStep({
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
        {isDemo ? 'Demo run · Building the packet' : 'Step 8 of 8 · Building your packet'}
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
