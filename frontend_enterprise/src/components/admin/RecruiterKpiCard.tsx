'use client';

import React from 'react';
import { motion } from 'motion/react';
import { MetricBar } from '@/components/admin/MetricBar';
import { StackedProgressBar, type StackedProgressSegment } from '@/components/StackedProgressBar';

const TEAL = '#0f766e';
const BLUE = '#2563eb';
const GREEN = '#047857';

export interface RecruiterCardData {
  name: string;
  matchingToFormat: { display: string | null; hours: number | null };
  formatToClient: { display: string | null; hours: number | null };
  validated: number;
  feedbackSegments: StackedProgressSegment[];
}

interface Props {
  data: RecruiterCardData;
  teamMaxHours: { m2f: number; f2c: number };
  maxValidated: number;
  index: number;
  reducedMotion: boolean;
  animKey: number | string;
}

const CARD_MOTION = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
};

export function RecruiterKpiCard({
  data, teamMaxHours, maxValidated, index, reducedMotion, animKey,
}: Props) {
  return (
    <motion.div
      className="rounded-2xl border border-[#d8e0ea] bg-white p-5 space-y-4"
      initial={reducedMotion ? false : CARD_MOTION.initial}
      animate={CARD_MOTION.animate}
      transition={{ duration: reducedMotion ? 0 : 0.4, delay: reducedMotion ? 0 : index * 0.08, ease: 'easeOut' }}
    >
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
          <span className="text-[#2563eb] font-bold text-sm">
            {data.name.charAt(0).toUpperCase()}
          </span>
        </div>
        <h4 className="text-sm font-semibold text-slate-900 truncate">{data.name}</h4>
      </div>

      <div className="space-y-3">
        <MetricBar
          label="Matching → Format"
          value={data.matchingToFormat.hours}
          max={teamMaxHours.m2f}
          displayLabel={data.matchingToFormat.display ?? '—'}
          color={TEAL}
          index={index}
          reducedMotion={reducedMotion}
          animKey={animKey}
        />
        <MetricBar
          label="Format → Client"
          value={data.formatToClient.hours}
          max={teamMaxHours.f2c}
          displayLabel={data.formatToClient.display ?? '—'}
          color={BLUE}
          index={index}
          reducedMotion={reducedMotion}
          animKey={animKey}
        />
        <MetricBar
          label="Candidats validés"
          value={data.validated}
          max={maxValidated}
          displayLabel={String(data.validated)}
          color={GREEN}
          index={index}
          reducedMotion={reducedMotion}
          animKey={animKey}
        />
      </div>

      <div className="space-y-2 pt-1 border-t border-[#e5ebf2]">
        <span className="text-xs text-slate-600">Retour client</span>
        <StackedProgressBar segments={data.feedbackSegments} reducedMotion={reducedMotion} />
      </div>
    </motion.div>
  );
}


