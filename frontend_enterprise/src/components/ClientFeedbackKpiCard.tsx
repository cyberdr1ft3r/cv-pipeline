'use client';

import React, { useMemo } from 'react';
import { motion } from 'motion/react';
import { BarChart2 } from 'lucide-react';
import { MetricHelp } from '@/components/admin/MetricHelp';
import type { MetricHelpInfo, MetricHelpMode } from '@/lib/adminMetricHelp';

export interface ClientFeedbackCounts {
  envoye_attente?: number;
  recrute?: number;
  non_integre?: number;
  rejete?: number;
  valide_client?: number;
  non_valide_client?: number;
}

const SEGMENT_DEFS = [
  { key: 'envoye_attente' as const, label: 'En attente', color: '#64748b' },
  { key: 'recrute' as const, label: 'Recrutés', color: '#047857' },
  { key: 'non_integre' as const, label: 'Non intégrés', color: '#b91c1c' },
  { key: 'rejete' as const, label: 'Rejetés', color: '#b45309' },
  { key: 'valide_client' as const, label: 'Validé client', color: '#0f766e' },
  { key: 'non_valide_client' as const, label: 'Non validé client', color: '#991b1b' },
];

const CARD_MOTION = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, ease: 'easeOut' as const },
};

interface Props {
  feedback: ClientFeedbackCounts;
  index?: number;
  reducedMotion?: boolean;
  help?: MetricHelpInfo & { mode?: MetricHelpMode };
}

export function ClientFeedbackKpiCard({ feedback, index = 0, reducedMotion = false, help }: Props) {
  const segments = useMemo(
    () =>
      SEGMENT_DEFS.map(def => ({
        label: def.label,
        count: Number(feedback[def.key] ?? 0),
        color: def.color,
      })),
    [feedback],
  );

  const total = segments.reduce((sum, s) => sum + s.count, 0);
  const active = segments.filter(s => s.count > 0);

  return (
    <motion.div
      className="rounded-2xl border border-white/10 bg-gradient-to-br from-slate-800/50 to-slate-900/50 border-t-2 border-purple-500 p-6 space-y-4"
      initial={reducedMotion ? false : CARD_MOTION.initial}
      animate={CARD_MOTION.animate}
      transition={{ ...CARD_MOTION.transition, delay: reducedMotion ? 0 : index * 0.1 }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 min-w-0">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Retour client
          </p>
          {help && <MetricHelp info={help} mode={help.mode} />}
        </div>
        <div className="w-8 h-8 rounded-lg bg-white/[0.07] flex items-center justify-center">
          <BarChart2 className="h-4 w-4 text-slate-300" />
        </div>
      </div>

      {total === 0 ? (
        <div className="space-y-2">
          <div className="h-2.5 w-full rounded-full bg-white/10" />
          <p className="text-xs text-slate-500">Aucun retour client</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white tabular-nums">{total}</span>
            <span className="text-xs text-slate-400">
              candidat{total > 1 ? 's' : ''} avec retour
            </span>
          </div>

          <div className="h-2.5 w-full rounded-full overflow-hidden flex bg-white/5">
            {active.map((seg, i) => (
              <motion.div
                key={`bar-${seg.label}`}
                className="h-full origin-left"
                style={{ backgroundColor: seg.color, width: `${(seg.count / total) * 100}%` }}
                initial={reducedMotion ? false : { scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: reducedMotion ? 0 : 0.6, ease: 'easeOut', delay: reducedMotion ? 0 : i * 0.06 }}
                title={`${seg.label} (${seg.count})`}
              />
            ))}
          </div>

          <div className="space-y-2.5">
            {active.map((seg, i) => {
              const pct = Math.round((seg.count / total) * 100);
              return (
                <div key={`row-${seg.label}`} className="space-y-1">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                        style={{ backgroundColor: seg.color }}
                      />
                      <span className="text-slate-300">{seg.label}</span>
                    </div>
                    <span className="text-slate-400 tabular-nums flex-shrink-0">
                      <span className="text-white font-semibold">{seg.count}</span>
                      <span className="text-slate-500"> · {pct}%</span>
                    </span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
                    <motion.div
                      className="h-full rounded-full origin-left"
                      style={{ backgroundColor: seg.color, width: `${pct}%` }}
                      initial={reducedMotion ? false : { scaleX: 0 }}
                      animate={{ scaleX: 1 }}
                      transition={{ duration: reducedMotion ? 0 : 0.6, ease: 'easeOut', delay: reducedMotion ? 0 : 0.15 + i * 0.06 }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </motion.div>
  );
}
