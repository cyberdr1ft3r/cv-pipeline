'use client';

import React from 'react';
import { CircleHelp } from 'lucide-react';
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/app/components/ui/tooltip';
import {
  Popover, PopoverContent, PopoverTrigger,
} from '@/app/components/ui/popover';
import type { MetricHelpInfo, MetricHelpMode } from '@/lib/adminMetricHelp';

const PANEL_CLASS =
  'max-w-[260px] space-y-2 bg-[#0d1528] border border-white/10 text-slate-300 shadow-xl';

interface Props {
  info: MetricHelpInfo;
  mode?: MetricHelpMode;
  className?: string;
}

function HelpBody({ info }: { info: MetricHelpInfo }) {
  return (
    <>
      <p className="text-xs leading-relaxed">{info.summary}</p>
      {info.formula && (
        <p className="text-[11px] text-teal-400/90 font-mono leading-snug border-t border-white/10 pt-2">
          {info.formula}
        </p>
      )}
      {info.detail && (
        <p className="text-[11px] text-slate-500 leading-relaxed">{info.detail}</p>
      )}
    </>
  );
}

function HelpIcon({ className }: { className?: string }) {
  return (
    <CircleHelp
      className={`h-3.5 w-3.5 text-slate-500 hover:text-slate-300 transition-colors shrink-0 ${className ?? ''}`}
      aria-hidden
    />
  );
}

export function MetricHelp({ info, mode = 'hover', className }: Props) {
  const trigger = (
    <button
      type="button"
      className={`inline-flex items-center justify-center rounded-full p-0.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-teal-400/50 ${className ?? ''}`}
      aria-label="Plus d'informations"
    >
      <HelpIcon />
    </button>
  );

  if (mode === 'click') {
    return (
      <Popover>
        <PopoverTrigger asChild>{trigger}</PopoverTrigger>
        <PopoverContent className={PANEL_CLASS} side="top" align="start">
          <HelpBody info={info} />
        </PopoverContent>
      </Popover>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{trigger}</TooltipTrigger>
      <TooltipContent
        side="top"
        className={`${PANEL_CLASS} px-3 py-2.5 text-xs`}
        sideOffset={6}
      >
        <HelpBody info={info} />
      </TooltipContent>
    </Tooltip>
  );
}
