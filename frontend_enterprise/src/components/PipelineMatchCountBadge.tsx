'use client';

import React from 'react';
import {
  type PipelineJobCounts,
  formatLoadedLabel,
  formatScoredLabel,
  scoredCount,
} from '@/lib/pipelineCounts';

interface Props {
  job: PipelineJobCounts;
  className?: string;
}

/** Compact badge: scored count primary; loaded count when higher (partial scoring). */
export function PipelineMatchCountBadge({ job, className = '' }: Props) {
  const loaded = job.cv_count ?? 0;
  const scored = scoredCount(job);

  if (scored > 0) {
    return (
      <span className={`inline-flex flex-wrap items-center gap-1.5 text-xs ${className}`}>
        <span className="text-green-400 bg-green-400/10 px-2.5 py-1 rounded-full">
          {formatScoredLabel(scored)}
        </span>
        {loaded > scored && (
          <span className="text-slate-400 bg-white/[0.04] px-2 py-0.5 rounded-full">
            {formatLoadedLabel(loaded)}
          </span>
        )}
      </span>
    );
  }

  if (loaded > 0) {
    return (
      <span className={`text-xs text-slate-400 bg-white/[0.04] px-2.5 py-1 rounded-full ${className}`}>
        {formatLoadedLabel(loaded)}
      </span>
    );
  }

  return null;
}
