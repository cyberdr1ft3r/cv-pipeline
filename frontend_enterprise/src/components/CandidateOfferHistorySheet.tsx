'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronRight, Loader2, X } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { scoreTextClass } from '@/lib/scoreUtils';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

/**
 * Offer links must stay inside the space the user is already in.
 *
 * This sheet is rendered from both /recruiter and /sourcer. It used to link
 * unconditionally to /recruiter/offers/<id>, so a sourcer clicking an offer in
 * a candidate's history was bounced by the auth middleware to /sourcer,
 * losing their place for no visible reason. Deriving the prefix from the
 * current path keeps any future call site correct too.
 */
function offerHrefFor(pathname: string | null, offerId: string): string {
  const space = pathname?.startsWith('/sourcer') ? '/sourcer' : '/recruiter';
  return `${space}/offers/${offerId}`;
}

export interface OfferHistoryEntry {
  offer_id: string;
  offer_title: string;
  offer_status: string | null;
  matching_score: number | null;
  final_score: number | null;
  decision: string;
  decision_label?: string;
  created_at: string | null;
  recruiter_id?: string | null;
  recruiter_name?: string | null;
  sourcer_name?: string | null;
}

interface Props {
  open: boolean;
  onClose: () => void;
  candidateId: string;
  candidateName: string;
  excludeOfferId: string;
}

interface CurrentUser {
  id: string;
  role: string;
}

function pct(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  const n = value <= 1 ? value * 100 : value;
  return `${n.toFixed(0)}%`;
}

const DECISION_LABELS: Record<string, string> = {
  pending: 'En attente',
  shortlisted: 'Présélectionné',
  contacted: 'Contacté',
  interviewed: 'Interviewé',
  offered: 'Offre faite',
  hired: 'Recruté',
  rejected: 'Refusé',
};

function HistoryCard({
  entry, isOwned, onClose,
}: {
  entry: OfferHistoryEntry;
  isOwned: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();
  const recruiterLabel = isOwned ? 'Moi' : (entry.recruiter_name || '—');

  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-white">{entry.offer_title}</p>
        <div className="flex items-center gap-1.5 shrink-0">
          {entry.offer_status && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-500/20 text-slate-300">
              {entry.offer_status}
            </span>
          )}
          {isOwned && <ChevronRight className="h-4 w-4 text-teal-400" />}
        </div>
      </div>
      <p className="text-xs text-slate-400">
        Score matching :{' '}
        <span className={scoreTextClass(entry.matching_score)}>{pct(entry.matching_score)}</span>
      </p>
      <p className="text-xs text-slate-400">
        Score final :{' '}
        <span className={scoreTextClass(entry.final_score)}>{pct(entry.final_score)}</span>
      </p>
      <p className="text-xs text-slate-400">
        Décision :{' '}
        <span className="text-slate-300">
          {entry.decision_label || DECISION_LABELS[entry.decision] || entry.decision}
        </span>
      </p>
      {entry.created_at && (
        <p className="text-xs text-slate-500">
          Offre créée le {new Date(entry.created_at).toLocaleDateString('fr-FR')}
        </p>
      )}
      <p className="text-xs text-slate-500">
        Recruteur :{' '}
        <span className={isOwned ? 'text-teal-400 font-medium' : 'text-slate-400'}>
          {recruiterLabel}
        </span>
      </p>
      <p className="text-xs text-slate-500">
        Sourceur : {entry.sourcer_name || 'Non assignée'}
      </p>
    </>
  );

  const cardClass =
    'rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-2 transition-colors';

  if (isOwned) {
    return (
      <Link
        href={offerHrefFor(pathname, entry.offer_id)}
        onClick={onClose}
        className={`block ${cardClass} hover:border-teal-500/30 hover:bg-white/[0.06] cursor-pointer`}
      >
        {body}
      </Link>
    );
  }

  return <div className={cardClass}>{body}</div>;
}

export function CandidateOfferHistorySheet({
  open, onClose, candidateId, candidateName, excludeOfferId,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [entries, setEntries] = useState<OfferHistoryEntry[]>([]);
  const [error, setError] = useState('');
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    if (!open) return;
    fetch(`${API_BASE}/auth/me`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(me => {
        if (me?.user_id) setCurrentUser({ id: String(me.user_id), role: me.role });
      })
      .catch(() => setCurrentUser(null));
  }, [open]);

  useEffect(() => {
    if (!open || !candidateId) return;
    setLoading(true);
    setError('');
    const params = excludeOfferId ? `?exclude_offer_id=${encodeURIComponent(excludeOfferId)}` : '';
    fetch(`${API_BASE}/candidates/${candidateId}/offer-history${params}`, { credentials: 'include' })
      .then(async r => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Erreur ${r.status}`);
        return r.json();
      })
      .then(data => {
        setEntries(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(e => {
        setError(e instanceof Error ? e.message : 'Erreur de chargement');
        setLoading(false);
      });
  }, [open, candidateId, excludeOfferId]);

  const isRecruiterViewer = currentUser?.role === 'recruiter' || currentUser?.role === 'admin';

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/50"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 320 }}
            className="fixed inset-y-0 right-0 z-50 w-full max-w-md border-l border-white/10 bg-[#0f1419] shadow-2xl flex flex-col"
          >
            <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-white/10">
              <h2 className="text-base font-semibold text-white pr-2">
                Historique des offres — {candidateName}
              </h2>
              <button
                type="button"
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-3">
              {loading && (
                <div className="flex items-center gap-2 text-sm text-slate-400">
                  <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
                </div>
              )}
              {error && <p className="text-sm text-red-300">{error}</p>}
              {!loading && !error && entries.length === 0 && (
                <p className="text-sm text-slate-500">Aucune autre offre pour ce candidat.</p>
              )}
              {entries.map(entry => {
                const isOwned = Boolean(
                  isRecruiterViewer
                  && currentUser?.id
                  && entry.recruiter_id
                  && entry.recruiter_id === currentUser.id,
                );
                return (
                  <HistoryCard
                    key={entry.offer_id}
                    entry={entry}
                    isOwned={isOwned}
                    onClose={onClose}
                  />
                );
              })}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

interface BadgeProps {
  count: number;
  onClick: () => void;
}

export function OtherOffersBadge({ count, onClick }: BadgeProps) {
  if (count <= 0) return null;
  return (
    <button
      type="button"
      onClick={e => { e.stopPropagation(); onClick(); }}
      className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/25 hover:bg-amber-500/25 transition-colors"
    >
      {count} autre{count > 1 ? 's' : ''} offre{count > 1 ? 's' : ''}
    </button>
  );
}

