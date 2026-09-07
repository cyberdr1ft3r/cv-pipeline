'use client';

import React from 'react';
import Link from 'next/link';
import { DarkSelect, DarkSelectOption } from '@/components/DarkSelect';
import { formatScorePct, scoreBadgeClass } from '@/lib/scoreUtils';
import { formatSkillOverlap } from '@/lib/skillUtils';

interface Props {
  offerTitle?: string;
  offerHref?: string;
  offerCreatedAt?: string | null;
  recruiterName?: string | null;
  recruiterOwned?: boolean;
  rank?: number | null;
  matchingScore?: number | null;
  finalScore?: number | null;
  decision?: string;
  decisionLabel?: string;
  decisions?: DarkSelectOption[];
  onDecisionChange?: (decision: string) => void;
  matchingStatusCode?: string;
  matchingStatusOptions?: DarkSelectOption[];
  onMatchingStatusChange?: (code: string) => void;
  selectSize?: 'sm' | 'md';
  matchingSkillsCount?: number | null;
  totalOfferSkills?: number | null;
}

function formatOfferDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR');
}

export function CandidateAppearanceRow({
  offerTitle,
  offerHref,
  offerCreatedAt,
  recruiterName,
  recruiterOwned = false,
  rank,
  matchingScore,
  finalScore,
  decision,
  decisionLabel,
  decisions,
  onDecisionChange,
  matchingStatusCode,
  matchingStatusOptions,
  onMatchingStatusChange,
  selectSize = 'md',
  matchingSkillsCount,
  totalOfferSkills,
}: Props) {
  const skillOverlap =
    matchingSkillsCount != null && totalOfferSkills != null
      ? formatSkillOverlap(matchingSkillsCount, totalOfferSkills)
      : null;

  const title = offerTitle || 'Offre';

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3 py-3 border-b border-white/[0.06] last:border-0">
      <div className="flex flex-1 min-w-0 items-start gap-3">
        {rank != null && (
          <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-teal-400/30 bg-teal-400/10 text-sm font-semibold text-teal-300">
            {rank}
          </span>
        )}
        <div className="min-w-0 flex-1">
          {offerHref ? (
            <Link
              href={offerHref}
              className="text-sm font-medium text-teal-300 hover:text-teal-200 hover:underline cursor-pointer truncate block"
            >
              {title}
            </Link>
          ) : (
            <p className="text-sm font-medium text-white truncate">{title}</p>
          )}
          {(offerCreatedAt || recruiterOwned || recruiterName) && (
            <div className="mt-1 space-y-0.5">
              {offerCreatedAt && (
                <p className="text-xs text-slate-500">
                  Créée le {formatOfferDate(offerCreatedAt)}
                </p>
              )}
              {(recruiterOwned || recruiterName) && (
                <p className="text-xs text-slate-500">
                  Recruteur :{' '}
                  <span className={recruiterOwned ? 'text-teal-400 font-medium' : 'text-slate-400'}>
                    {recruiterOwned ? 'Moi' : (recruiterName || '—')}
                  </span>
                </p>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-1.5 mt-1">
            {matchingScore != null && (
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${scoreBadgeClass(matchingScore)}`}>
                Matching {formatScorePct(matchingScore)}
              </span>
            )}
            {finalScore != null && (
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${scoreBadgeClass(finalScore)}`}>
                Final {formatScorePct(finalScore)}
              </span>
            )}
            {matchingScore == null && finalScore == null && (
              <span className="text-xs text-slate-500">Score —</span>
            )}
            {skillOverlap && (
              <span className="text-xs text-indigo-300 bg-indigo-400/10 border border-indigo-400/20 px-2 py-0.5 rounded-full">
                {skillOverlap}
              </span>
            )}
          </div>
        </div>
      </div>
      {onMatchingStatusChange && matchingStatusOptions ? (
        <DarkSelect
          value={matchingStatusCode || 'en_attente'}
          onChange={onMatchingStatusChange}
          options={matchingStatusOptions}
          size={selectSize}
          className={selectSize === 'sm' ? 'min-w-[130px]' : 'min-w-[160px]'}
        />
      ) : onDecisionChange && decisions ? (
        <DarkSelect
          value={decision || 'pending'}
          onChange={onDecisionChange}
          options={decisions}
          size={selectSize}
          className={selectSize === 'sm' ? 'min-w-[130px]' : 'min-w-[160px]'}
        />
      ) : (
        (decisionLabel || decision) && (
          <span className="text-xs text-slate-400 shrink-0">{decisionLabel || decision}</span>
        )
      )}
    </div>
  );
}
