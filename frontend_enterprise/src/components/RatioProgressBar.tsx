'use client';

import React from 'react';
import { motion } from 'motion/react';

export type RatioColorScheme = 'positive' | 'neutral' | 'warning';

const FILL_GRADIENT: Record<RatioColorScheme, string> = {
  positive: 'bg-gradient-to-r from-teal-500 to-green-500',
  neutral: 'bg-gradient-to-r from-blue-500 to-teal-500',
  warning: 'bg-gradient-to-r from-amber-500 to-red-500',
};

interface Props {
  value: number;
  total: number;
  label?: string;
  colorScheme: RatioColorScheme;
  reducedMotion?: boolean;
  animKey?: number;
  index?: number;
}

function pct(value: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(100, Math.round((value / total) * 100));
}

export function RatioProgressBar({
  value,
  total,
  label,
  colorScheme,
  reducedMotion = false,
  animKey = 0,
  index = 0,
}: Props) {
  const percent = pct(value, total);
  const displayLabel = total <= 0
    ? '—'
    : label ?? `${percent}%`;

  return (
    <div className="space-y-1.5">
      <div className="h-1 w-full rounded-full bg-white/10 overflow-hidden">
        {total > 0 && (
          <motion.div
            key={`${animKey}-${index}-${value}-${total}`}
            className={`h-full rounded-full origin-left ${FILL_GRADIENT[colorScheme]}`}
            style={{ width: `${percent}%` }}
            initial={reducedMotion ? false : { scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{
              duration: reducedMotion ? 0 : 0.6,
              ease: 'easeOut',
              delay: reducedMotion ? 0 : 0.15 + index * 0.05,
            }}
          />
        )}
      </div>
      <p className="text-xs text-slate-500 tabular-nums">{displayLabel}</p>
    </div>
  );
}
