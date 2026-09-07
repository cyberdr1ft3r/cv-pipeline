'use client';

import React from 'react';
import { motion } from 'motion/react';

export interface StackedProgressSegment {
  label: string;
  count: number;
  color: string;
}

interface Props {
  segments: StackedProgressSegment[];
  reducedMotion?: boolean;
  emptyLabel?: string;
  className?: string;
}

export function StackedProgressBar({
  segments,
  reducedMotion = false,
  emptyLabel = 'Aucun retour client',
  className = '',
}: Props) {
  const active = segments.filter(s => s.count > 0);
  const total = active.reduce((sum, s) => sum + s.count, 0);

  if (total === 0) {
    return (
      <div className={`space-y-2 ${className}`}>
        <div className="h-3 w-full rounded-full bg-white/10" />
        <p className="text-xs text-slate-500">{emptyLabel}</p>
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="h-3 w-full rounded-full overflow-hidden flex bg-white/5">
        {active.map((seg, i) => {
          const pct = (seg.count / total) * 100;
          return (
            <motion.div
              key={`${seg.label}-${i}`}
              className="h-full origin-left"
              style={{ backgroundColor: seg.color, width: `${pct}%` }}
              initial={reducedMotion ? false : { scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{
                duration: reducedMotion ? 0 : 0.6,
                ease: 'easeOut',
                delay: reducedMotion ? 0 : i * 0.08,
              }}
              title={`${seg.label} (${seg.count})`}
            />
          );
        })}
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
        {active.map((seg, i) => (
          <div key={`legend-${seg.label}-${i}`} className="flex items-center gap-2 min-w-0">
            <span
              className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
              style={{ backgroundColor: seg.color }}
            />
            <span className="text-xs text-slate-400 truncate">
              {seg.label} ({seg.count})
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
