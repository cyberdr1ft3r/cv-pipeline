'use client';

import React, { useState } from 'react';
import { Calendar, Loader2 } from 'lucide-react';

export interface DateRange {
  from: string;
  to: string;
}

interface Props {
  value: DateRange;
  onChange: (range: DateRange) => void;
  onApply: () => void;
  loading?: boolean;
  periodLabel?: string;
}

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

const PRESETS: { label: string; from: string; to: string }[] = [
  { label: '7 j', from: isoDaysAgo(7), to: todayIso() },
  { label: '30 j', from: isoDaysAgo(30), to: todayIso() },
  { label: '3 m', from: isoDaysAgo(90), to: todayIso() },
  { label: '6 m', from: isoDaysAgo(180), to: todayIso() },
  { label: 'Tout', from: '', to: todayIso() },
];

export function DateRangeFilter({ value, onChange, onApply, loading, periodLabel }: Props) {
  const [draft, setDraft] = useState(value);

  function applyDraft() {
    onChange(draft);
    onApply();
  }

  function setPreset(from: string, to: string) {
    const next = { from, to };
    setDraft(next);
    onChange(next);
    onApply();
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Calendar className="h-4 w-4 text-[#1f9d94]" />
          <span>
            Période{periodLabel ? ` : ` : ''}
            {periodLabel && <span className="text-slate-200 font-medium">{periodLabel}</span>}
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map(p => (
            <button
              key={p.label}
              type="button"
              onClick={() => setPreset(p.from, p.to)}
              className="px-2.5 py-1 rounded-lg text-xs font-medium border border-white/10 text-slate-400 hover:text-white hover:border-[#1f9d94]/40 transition-all"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-500 space-y-1">
          <span>Du</span>
          <input
            type="date"
            value={draft.from}
            onChange={e => setDraft(d => ({ ...d, from: e.target.value }))}
            className="block h-9 px-3 rounded-lg border border-white/10 bg-white/[0.04] text-sm text-white focus:border-[#1f9d94]/50 focus:outline-none"
          />
        </label>
        <label className="text-xs text-slate-500 space-y-1">
          <span>Au</span>
          <input
            type="date"
            value={draft.to}
            onChange={e => setDraft(d => ({ ...d, to: e.target.value }))}
            className="block h-9 px-3 rounded-lg border border-white/10 bg-white/[0.04] text-sm text-white focus:border-[#1f9d94]/50 focus:outline-none"
          />
        </label>
        <button
          type="button"
          onClick={applyDraft}
          disabled={loading}
          className="h-9 px-4 rounded-lg bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium transition-all disabled:opacity-50 flex items-center gap-2"
        >
          {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Appliquer
        </button>
      </div>
    </div>
  );
}
