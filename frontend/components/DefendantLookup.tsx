'use client';

import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, AlertTriangle, Loader2, Search } from 'lucide-react';
import clsx from 'clsx';

import { searchDOS, type DosMatch } from '@/lib/api';

interface Props {
  value: string;
  onChange: (name: string) => void;
  onPick?: (match: DosMatch) => void;
  placeholder?: string;
}

type State =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'verified'; match: DosMatch }
  | { kind: 'choices'; matches: DosMatch[] }
  | { kind: 'empty' }
  | { kind: 'error'; message: string };

const DEBOUNCE_MS = 450;

export function DefendantLookup({ value, onChange, onPick, placeholder }: Props) {
  const [state, setState] = useState<State>({ kind: 'idle' });
  const [pickedName, setPickedName] = useState<string | null>(null);
  const reqIdRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    const trimmed = value.trim();
    if (trimmed.length < 3) {
      setState({ kind: 'idle' });
      return;
    }
    // If user already picked a match and the input still equals the picked name,
    // keep showing the verified state instead of re-searching.
    if (pickedName && trimmed === pickedName) {
      return;
    }

    timerRef.current = setTimeout(async () => {
      const reqId = ++reqIdRef.current;
      setState({ kind: 'loading' });
      try {
        const { matches } = await searchDOS(trimmed);
        if (reqId !== reqIdRef.current) return; // stale response
        if (matches.length === 0) {
          setState({ kind: 'empty' });
        } else if (matches.length === 1) {
          setState({ kind: 'verified', match: matches[0] });
        } else {
          setState({ kind: 'choices', matches });
        }
      } catch (e: any) {
        if (reqId !== reqIdRef.current) return;
        setState({ kind: 'error', message: e?.message ?? String(e) });
      }
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [value, pickedName]);

  function handlePick(m: DosMatch) {
    onChange(m.current_entity_name);
    setPickedName(m.current_entity_name);
    setState({ kind: 'verified', match: m });
    onPick?.(m);
  }

  return (
    <div className="space-y-2">
      <div className="relative">
        <input
          value={value}
          onChange={(e) => {
            setPickedName(null);
            onChange(e.target.value);
          }}
          placeholder={placeholder ?? 'Vanguard Marketing LLC'}
          className="pr-10"
        />
        <span className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-ink-300">
          {state.kind === 'loading' && <Loader2 size={16} className="animate-spin" />}
          {state.kind === 'verified' && <CheckCircle2 size={18} className="text-sage-700" />}
          {state.kind === 'empty' && <AlertTriangle size={18} className="text-ochre-500" />}
          {state.kind === 'idle' && <Search size={16} />}
        </span>
      </div>

      {state.kind === 'verified' && (
        <div className="flex items-start gap-2 rounded-lg bg-sage-50 border border-sage-700/20 px-3 py-2 text-xs leading-relaxed">
          <CheckCircle2 size={14} className="text-sage-700 shrink-0 mt-[2px]" />
          <div className="text-ink-900/80 min-w-0">
            <p className="font-semibold text-sage-700">
              Verified · {state.match.current_entity_name}
            </p>
            <p className="text-ink-300 mt-0.5">
              DOS #{state.match.dos_id} · {state.match.county || state.match.jurisdiction}
            </p>
            {state.match.service_address && (
              <p className="text-ink-700 mt-0.5">
                Service of process: {state.match.service_address}
              </p>
            )}
          </div>
        </div>
      )}

      {state.kind === 'choices' && (
        <div className="rounded-lg border border-ink-200 bg-white shadow-sink overflow-hidden">
          <p className="px-3 py-2 text-[11px] uppercase tracking-wider text-ink-300 font-semibold border-b border-ink-200/60 bg-ink-50/50">
            {state.matches.length} matches — pick the right one
          </p>
          <ul className="divide-y divide-ink-200/60">
            {state.matches.map((m) => (
              <li key={m.dos_id}>
                <button
                  type="button"
                  onClick={() => handlePick(m)}
                  className="w-full text-left px-3 py-2.5 hover:bg-sage-50 transition"
                >
                  <p className="text-sm font-medium text-ink-900">{m.current_entity_name}</p>
                  <p className="text-xs text-ink-300 mt-0.5">
                    DOS #{m.dos_id} · {m.entity_type} · {m.county || m.jurisdiction}
                  </p>
                  {m.service_address && (
                    <p className="text-xs text-ink-700 mt-0.5 truncate">{m.service_address}</p>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {state.kind === 'empty' && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg bg-ochre-400/10 border border-ochre-400/40 px-3 py-2 text-xs leading-relaxed"
        >
          <AlertTriangle size={14} className="text-ochre-600 shrink-0 mt-[2px]" />
          <div className="text-ink-900/80">
            <p className="font-semibold text-ochre-600">No NY State match found</p>
            <p className="mt-0.5">
              The legal name may be slightly different from what's on the contract. Try the
              full registered name (e.g. include "LLC" or "Inc."). If you can't find a
              match, you can still proceed — the agent will flag this case so you can
              verify the entity before filing.
            </p>
          </div>
        </div>
      )}

      {state.kind === 'error' && (
        <p className="text-xs text-ochre-600">
          NY State registry is temporarily unavailable: {state.message}
        </p>
      )}
    </div>
  );
}
