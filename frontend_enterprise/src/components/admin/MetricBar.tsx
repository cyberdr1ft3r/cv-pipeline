'use client';

import React from 'react';
import { motion } from 'motion/react';

interface Props {
  /** Raw numeric value for this recruiter (null = no data). */
  value: number | null;
  /** Team max for the same metric — drives relative bar length. */
  max: number;
  /** Formatted value shown on the right (e.g. "7h 58min", "7"). */
  displayLabel: string;
  /** Metric label shown on the left. */
  label: string;
  /** Bar fill color. */
  color: string;
  index?: number;
  reducedMotion?: boolean;
  /** Reset key so the grow animation replays on date filter change. */
  animKey?: number | string;
}

/**
 * Horizontal bar where width = value / teamMax. Used in RecruiterKpiCard
 * to compare a single recruiter against the team's best on a metric.
 */
export function MetricBar({
  value, max, displayLabel, label, color,
  index = 0, reducedMotion = false, animKey,
}: Props) {
  const hasData = value !== null && value !== undefined && !Number.isNaN(value);
  const pct = hasData && max > 0
    ? Math.max(2, Math.min(100, (value / max) * 100))
    : 0;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-slate-600">{label}</span>
        <span className={`text-xs font-semibold tabular-nums ${hasData ? 'text-slate-900' : 'text-slate-600'}`}>
          {hasData ? displayLabel : '—'}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
        {hasData && (
          <motion.div
            key={animKey}
            className="h-full rounded-full origin-left"
            style={{ backgroundColor: color, width: `${pct}%` }}
            initial={reducedMotion ? false : { scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{
              duration: reducedMotion ? 0 : 0.6,
              ease: 'easeOut',
              delay: reducedMotion ? 0 : index * 0.06,
            }}
          />
        )}
      </div>
    </div>
  );
}


