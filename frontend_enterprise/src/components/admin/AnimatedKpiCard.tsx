'use client';

import React from 'react';
import { motion } from 'motion/react';
import { MetricHelp } from '@/components/admin/MetricHelp';
import { RatioProgressBar, type RatioColorScheme } from '@/components/RatioProgressBar';
import { useCountUp } from '@/hooks/useCountUp';
import { formatCount, formatHours, formatPercent } from '@/lib/adminFormatters';
import type { MetricHelpInfo, MetricHelpMode } from '@/lib/adminMetricHelp';

export interface KpiRatio {
  value: number;
  total: number;
  label: string;
  colorScheme: RatioColorScheme;
}

export type KpiDisplayType = 'count' | 'percent' | 'hours' | 'decimal' | 'dash';

interface Props {
  label: string;
  rawValue?: number | null | undefined;
  type: KpiDisplayType;
  displayText?: string;
  sub?: React.ReactNode;
  icon: React.ElementType;
  border: string;
  index: number;
  animKey: number;
  reducedMotion: boolean;
  variant?: 'admin' | 'space';
  help?: MetricHelpInfo & { mode?: MetricHelpMode };
  ratio?: KpiRatio;
}

const CARD_MOTION = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, ease: 'easeOut' as const },
};

function displayValue(
  type: KpiDisplayType,
  raw: number | null | undefined,
  animated: number,
): string {
  if (raw === null || raw === undefined) return '—';
  switch (type) {
    case 'count':
      return formatCount(animated);
    case 'percent':
      return formatPercent(animated);
    case 'hours':
      return formatHours(animated);
    case 'decimal':
      return animated.toFixed(1);
    default:
      return '—';
  }
}

export function AnimatedKpiCard({
  label, rawValue, type, displayText, sub, icon: Icon, border, index, animKey, reducedMotion,
  variant = 'admin', help, ratio,
}: Props) {
  const useText = displayText !== undefined && displayText !== null;
  const target = rawValue ?? 0;
  const decimals = type === 'percent' ? 1 : type === 'decimal' ? 1 : type === 'hours' ? 1 : 0;
  const enabled = !useText && !reducedMotion && rawValue !== null && rawValue !== undefined && type !== 'dash';

  const animated = useCountUp(
    type === 'dash' ? 0 : target,
    { duration: 1500, decimals, enabled, resetKey: animKey },
  );

  const value = useText
    ? (displayText || '—')
    : type === 'dash' || rawValue === null || rawValue === undefined
      ? '—'
      : displayValue(type, rawValue, reducedMotion ? target : animated);

  const isSpace = variant === 'space';
  const cardClass = isSpace
    ? `admin-light-card rounded-xl border-t-0 p-5 space-y-3`
    : `admin-light-card rounded-xl border-t-0 p-5 space-y-3`;
  const labelClass = 'text-xs font-semibold text-slate-600 uppercase';
  const valueClass = 'font-semibold text-slate-950 tabular-nums text-3xl';
  const iconWrapClass = 'w-9 h-9 rounded-lg bg-[#e9f0ff] flex items-center justify-center';
  const iconClass = 'h-4 w-4 text-[#2f66ed]';

  return (
    <motion.div
      className={cardClass}
      initial={reducedMotion ? false : CARD_MOTION.initial}
      animate={CARD_MOTION.animate}
      transition={{ ...CARD_MOTION.transition, delay: reducedMotion ? 0 : index * 0.1 }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 min-w-0">
          <p className={labelClass}>{label}</p>
          {help && <MetricHelp info={help} mode={help.mode} />}
        </div>
        <div className={iconWrapClass}>
          <Icon className={iconClass} />
        </div>
      </div>
      <p className={valueClass}>{value}</p>
      {ratio && (
        <RatioProgressBar
          value={ratio.value}
          total={ratio.total}
          label={ratio.label}
          colorScheme={ratio.colorScheme}
          reducedMotion={reducedMotion}
          animKey={animKey}
          index={index}
        />
      )}
      {sub && (
        isSpace
          ? <div className="text-xs text-slate-600">{sub}</div>
          : <p className="text-xs text-slate-600">{sub}</p>
      )}
    </motion.div>
  );
}

