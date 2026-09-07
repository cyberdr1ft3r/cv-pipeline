'use client';

import React from 'react';
import { motion } from 'motion/react';

interface Props {
  gap: number;
  maxGap: number;
  reducedMotion: boolean;
}

export function GapBarCell({ gap, maxGap, reducedMotion }: Props) {
  const scale = maxGap > 0 ? Math.min(gap / maxGap, 1) : 0;
  const barColor = gap > 5 ? 'bg-red-600' : gap >= 2 ? 'bg-amber-600' : 'bg-slate-500';
  const textColor = gap > 5 ? 'text-red-700' : gap >= 2 ? 'text-amber-700' : 'text-slate-600';
  const duration = gap > 5 ? 0.6 : gap >= 2 ? 1.0 : 1.4;

  return (
    <td className="px-4 py-2.5 text-right">
      <div className="flex items-center justify-end gap-2">
        <div className="w-20 h-1.5 rounded-full bg-slate-100 overflow-hidden flex-shrink-0">
          <motion.div
            className={`h-full w-full rounded-full ${barColor}`}
            initial={{ scaleX: reducedMotion ? scale : 0 }}
            whileInView={{ scaleX: scale }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: reducedMotion ? 0 : duration, ease: 'easeOut' }}
            style={{ transformOrigin: 'left' }}
          />
        </div>
        <span className={`font-semibold tabular-nums min-w-[2ch] ${textColor}`}>+{gap}</span>
      </div>
    </td>
  );
}

