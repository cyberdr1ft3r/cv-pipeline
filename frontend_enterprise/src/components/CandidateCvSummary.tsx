'use client';

import React from 'react';
import { SkillBadge } from '@/components/SkillBadge';
import { SKILL_CHIP } from '@/lib/uiTokens';
import { isStructuredSkill, skillDisplayName, skillKey, type SkillLike } from '@/lib/skillUtils';

interface CvSummary {
  titre?: string;
  annees_experience?: string;
  resume?: string;
  skills?: SkillLike[];
}

export function CandidateCvSummary({ summary }: { summary: CvSummary }) {
  const hasContent =
    summary.titre ||
    summary.annees_experience ||
    summary.resume ||
    (summary.skills && summary.skills.length > 0);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-3">
      <h2 className="text-sm font-semibold text-slate-300">Résumé CV</h2>
      {!hasContent ? (
        <p className="text-slate-500 text-sm">Résumé non disponible.</p>
      ) : (
        <>
          {summary.titre && <p className="text-white text-sm font-medium">{summary.titre}</p>}
          {summary.annees_experience && (
            <p className="text-slate-400 text-sm">{summary.annees_experience}</p>
          )}
          {summary.resume && <p className="text-slate-300 text-sm leading-relaxed">{summary.resume}</p>}
          {summary.skills && summary.skills.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {summary.skills.slice(0, 12).map((s, i) =>
                isStructuredSkill(s) ? (
                  <SkillBadge key={skillKey(s, i)} skill={s} />
                ) : (
                  <span key={skillKey(s, i)} className={SKILL_CHIP}>{skillDisplayName(s)}</span>
                ),
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
