'use client';

import React from 'react';
import { Slider } from '@/app/components/ui/slider';

interface Props {
  scoreDraft: [number, number];
  scoreFilterActive: boolean;
  onDraftChange: (range: [number, number]) => void;
  onCommit: (range: [number, number]) => void;
  onReset: () => void;
}

export function CandidateScoreRangeFilter({
  scoreDraft,
  scoreFilterActive,
  onDraftChange,
  onCommit,
  onReset,
}: Props) {
  return (
    <div className="flex h-10 shrink-0 items-center gap-2 rounded-lg border border-[#d8e0ea] bg-white px-3 shadow-sm sm:w-48">
      <span className="w-7 tabular-nums text-[11px] text-slate-500">{scoreDraft[0]}%</span>
      <Slider
        value={scoreDraft}
        onValueChange={(v) => onDraftChange([v[0], v[1]])}
        onValueCommit={(v) => onCommit([v[0], v[1]])}
        min={0}
        max={100}
        step={1}
        className="flex-1 [&_[data-slot=slider-track]]:h-1 [&_[data-slot=slider-track]]:bg-slate-200 [&_[data-slot=slider-range]]:bg-[#2f66ed] [&_[data-slot=slider-thumb]]:size-3 [&_[data-slot=slider-thumb]]:border-[#2f66ed] [&_[data-slot=slider-thumb]]:bg-white"
      />
      <span className="w-8 text-right tabular-nums text-[11px] text-slate-500">{scoreDraft[1]}%</span>
      {scoreFilterActive && (
        <button
          type="button"
          title="Réinitialiser"
          onClick={onReset}
          className="text-xs leading-none text-slate-500 hover:text-[#2f66ed]"
        >
          ×
        </button>
      )}
    </div>
  );
}
