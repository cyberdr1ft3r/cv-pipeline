'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useParams, useRouter } from 'next/navigation';
import {
  AlertCircle, ArrowLeft, CheckCircle2, ChevronDown, Info,
  Briefcase, Clock, Loader2, MapPin, Play, RefreshCw, Star, User, Users, XCircle,
} from 'lucide-react';
import { SkillBadge } from '@/components/SkillBadge';
import { OfferAppearanceNotes } from '@/components/OfferScopedNote';
import { CandidateOfferHistorySheet, OtherOffersBadge } from '@/components/CandidateOfferHistorySheet';
import { DarkSelect } from '@/components/DarkSelect';
import { UnreliabilityFlagIndicator, type UnreliabilityFlagInfo } from '@/components/UnreliabilityFlagIndicator';
import { type StructuredSkill } from '@/lib/skillUtils';
import {
  formatScoredLabel,
  formatScoringGapWarning,
  hasScoringGap,
  scoredCount,
} from '@/lib/pipelineCounts';
import { scoreTextClass } from '@/lib/scoreUtils';
import { appendCvLimit, cvLimitFieldError } from '@/lib/cvLimit';
import { CvLimitField } from '@/components/CvLimitField';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

interface OfferDetail {
  id: string; title: string; description: string;
  skills: StructuredSkill[];
  experience_level: string | null;
  location: string | null; salary_range: string | null;
  contract_type: { id: number; code: string; label_fr: string } | null;
  experience_range: { id: number; min_years: number | null; max_years: number | null; display: string | null } | null;
  status: string; status_id: number | null; status_code: string | null; status_label: string | null;
  session_id: string | null;
  offer_sftp_path: string | null;
  created_at: string; recruiter_name: string | null;
  job: {
    id: string; status: string; stage: string;
    cv_count: number; matched_count?: number | null;
    created_at: string;
  } | null;
}

interface MatchingCandidate {
  rank: number;
  candidateName: string | null;
  candidateId: string | null;
  matchScore: number | null;
  experience: string;
  skills: string[];
  summary: string | null;
  skillsMatch: number | null;
  experienceMatch: number | null;
  educationMatch: number | null;
}

interface JobProgress { status: string; stage: string; progress?: Record<string, number>; }

interface OfferAppearance {
  id: string;
  candidate_id: string;
  full_name: string;
  rank: number | null;
  matching_score: number | null;
  matching_status?: { code: string; label_fr: string };
  unreliability_flag?: UnreliabilityFlagInfo | null;
  sourcer_note: string | null;
  recruiter_note: string | null;
  other_offers_count?: number;
}

interface RefStatusRow {
  code: string;
  label_fr: string;
}

function formatScore(score: number | null | undefined): string {
  if (typeof score !== 'number' || Number.isNaN(score)) return '--';
  const normalized = score <= 1 ? score * 100 : score;
  return `${normalized.toFixed(0)}%`;
}

function scoreColor(score: number | null): string {
  return scoreTextClass(score);
}

function normalizeFormatName(name: string): string {
  return name.toLowerCase().replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
}

const PROGRESS_STAGES: Record<string, string> = {
  preparing_inputs: 'Préparation des fichiers', running_pipeline: 'Extraction et appariement',
  running_final: 'Scoring final', running_format: 'Formatage des CVs',
  matching_complete: 'Matching terminé', final_complete: 'Finalisation', format_complete: 'Terminé',
};

function PipelineStatusBadge({ jobStatus }: { jobStatus?: string }) {
  if (jobStatus === 'running')   return <span className="text-sm font-medium px-3 py-1 rounded-full text-blue-400 bg-blue-400/10 flex items-center gap-1"><Loader2 className="h-3.5 w-3.5 animate-spin" />En cours</span>;
  if (jobStatus === 'succeeded' || jobStatus === 'completed') return <span className="text-sm font-medium px-3 py-1 rounded-full text-green-400 bg-green-400/10 flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" />Terminée</span>;
  if (jobStatus === 'failed')    return <span className="text-sm font-medium px-3 py-1 rounded-full text-red-400 bg-red-400/10 flex items-center gap-1"><XCircle className="h-3.5 w-3.5" />Échouée</span>;
  return <span className="text-sm font-medium px-3 py-1 rounded-full text-amber-400 bg-amber-400/10">En attente</span>;
}

export default function SourcerOfferDetailPage() {
  const { offer_id } = useParams<{ offer_id: string }>();
  const router = useRouter();
  const [offer, setOffer] = useState<OfferDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [relaunching, setRelaunching] = useState(false);
  const [relaunchError, setRelaunchError] = useState('');
  const [cvLimit, setCvLimit] = useState('20');
  const [progress, setProgress] = useState<JobProgress | null>(null);
  const [results, setResults] = useState<MatchingCandidate[]>([]);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [showAllResults, setShowAllResults] = useState(false);
  const fetchedResultsFor = useRef<string | null>(null);
  const [appearances, setAppearances] = useState<OfferAppearance[]>([]);
  const fetchedAppearancesFor = useRef<string | null>(null);
  const [historyCandidate, setHistoryCandidate] = useState<{ id: string; name: string } | null>(null);
  const [matchingStatuses, setMatchingStatuses] = useState<RefStatusRow[]>([]);

  const RESULTS_PREVIEW = 10;

  useEffect(() => {
    fetch(`${API_BASE}/ref/matching-statuses`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.matching_statuses) setMatchingStatuses(d.matching_statuses); })
      .catch(() => null);
  }, []);

  const fetchOffer = useCallback((silent = false) => {
    fetch(`${API_BASE}/my-offers/${offer_id}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(d => { setOffer(d); setLoading(false); })
      .catch(() => { if (!silent) setError('Offre introuvable ou accès refusé.'); setLoading(false); });
  }, [offer_id]);

  useEffect(() => { fetchOffer(); }, [fetchOffer]);

  const jobId = offer?.job?.id;
  const jobStatusVal = offer?.job?.status;
  const isRunning = jobStatusVal === 'running' || jobStatusVal === 'queued';
  const isComplete = jobStatusVal === 'succeeded' || jobStatusVal === 'completed';

  const reloadMatchingResults = useCallback(() => {
    if (!jobId) return;
    setResultsLoading(true);
    fetch(`${API_BASE}/jobs/${jobId}/matching`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(d => { setResults(d.results || []); setResultsLoading(false); })
      .catch(() => setResultsLoading(false));
  }, [jobId]);

  // Fix 5: while the pipeline runs, poll progress + re-fetch the offer so the page
  // flips to results automatically when matching completes — no redirect needed.
  useEffect(() => {
    if (!jobId || !isRunning) return;
    const poll = () => {
      fetch(`${API_BASE}/jobs/${jobId}/progress`, { credentials: 'include' })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d) setProgress(d); })
        .catch(() => null);
      fetchOffer(true);
    };
    poll();
    const t = setInterval(poll, 4000);
    return () => clearInterval(t);
  }, [jobId, isRunning, fetchOffer]);

  // Fix 5: once matching is complete, load the ranked results inline.
  useEffect(() => {
    if (!jobId || !isComplete) return;
    if (fetchedResultsFor.current === jobId) return;
    fetchedResultsFor.current = jobId;
    setResultsLoading(true);
    fetch(`${API_BASE}/jobs/${jobId}/matching`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(d => { setResults(d.results || []); setResultsLoading(false); })
      .catch(() => { setResultsLoading(false); });
  }, [jobId, isComplete]);

  useEffect(() => {
    if (!offer_id || !isComplete) return;
    fetch(`${API_BASE}/offers/${offer_id}/appearances`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(d => setAppearances(d.candidates || []))
      .catch(() => null);
  }, [offer_id, isComplete, results.length]);

  function findAppearance(c: MatchingCandidate): OfferAppearance | undefined {
    if (c.candidateId) {
      const byId = appearances.find(a => a.candidate_id === c.candidateId);
      if (byId) return byId;
    }
    const rank = Number(c.rank);
    const byRank = appearances.find(a => Number(a.rank) === rank);
    if (byRank) return byRank;
    const name = normalizeFormatName(c.candidateName || '');
    if (!name) return undefined;
    return appearances.find(a => normalizeFormatName(a.full_name || '') === name);
  }

  function updateAppearanceNote(appearanceId: string, field: 'sourcer_note' | 'recruiter_note', note: string) {
    setAppearances(prev => prev.map(a => a.id === appearanceId ? { ...a, [field]: note } : a));
  }

  async function updateMatchingStatus(appearanceId: string, statusCode: string) {
    const res = await fetch(`${API_BASE}/candidates/appearances/${appearanceId}/status`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase: 'matching', status_code: statusCode }),
    });
    if (res.ok) {
      const d = await res.json();
      const updated = d.appearance;
      setAppearances(prev => prev.map(a => {
        if (a.id === appearanceId) return { ...a, ...updated };
        if (updated?.candidate_id && a.candidate_id === updated.candidate_id && updated.unreliability_flag) {
          return { ...a, unreliability_flag: updated.unreliability_flag };
        }
        return a;
      }));
    }
  }

  function refreshAppearances() {
    if (!offer_id) return;
    fetch(`${API_BASE}/offers/${offer_id}/appearances`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(d => setAppearances(d.candidates || []))
      .catch(() => null);
  }

  async function relaunchOffer() {
    if (relaunching) return;
    if (!offer?.offer_sftp_path) {
      // No file — go back to the failed tab
      router.push('/sourcer/offers');
      return;
    }
    const limitErr = cvLimitFieldError(cvLimit);
    if (limitErr) {
      setRelaunchError(limitErr);
      return;
    }
    setRelaunchError('');
    setRelaunching(true);
    try {
      const fd = new FormData();
      fd.append('offer_sftp_path', offer.offer_sftp_path);
      if (offer.session_id) fd.append('preset_session_id', offer.session_id);
      fd.append('linked_offer_id', offer.id);
      fd.append('offer_only', 'true');
      appendCvLimit(fd, cvLimit);
      const res = await fetch(`${API_BASE}/jobs`, { method: 'POST', credentials: 'include', body: fd });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Erreur ${res.status}`);
      // Reset inline results so the new run's data loads fresh.
      setResults([]); setExpanded(null); setShowAllResults(false);
      fetchedResultsFor.current = null; fetchedAppearancesFor.current = null; setAppearances([]);
      // Re-fetch this offer page after a short delay — new job will appear in the pipeline section
      setTimeout(() => fetchOffer(), 1500);
    } catch (e: unknown) {
      setRelaunchError(e instanceof Error ? e.message : 'Erreur lors du relancement');
    } finally {
      setRelaunching(false);
    }
  }

  if (loading) return <div className="flex justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-[#1f9d94] mt-16" /></div>;

  if (!offer) return (
    <div className="space-y-4">
      <button onClick={() => router.push('/sourcer/offers')} className="flex items-center gap-2 text-slate-400 hover:text-white text-sm">
        <ArrowLeft className="h-4 w-4" /> Retour
      </button>
      <p className="text-red-400">{error}</p>
    </div>
  );

  const section = "rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-4";
  const jobStatus = offer.job?.status;
  const jobCounts = offer.job ?? { cv_count: 0 };
  const displayedScored = scoredCount(jobCounts, results.length);
  const scoringGapMsg = formatScoringGapWarning(jobCounts, results.length);
  const showCvLimit = Boolean(offer.offer_sftp_path) && !isRunning;

  return (
    <div className="w-full max-w-4xl space-y-6">
      <button onClick={() => router.push('/sourcer/offers')} className="flex items-center gap-2 text-slate-400 hover:text-white text-sm transition-colors">
        <ArrowLeft className="h-4 w-4" /> Mes Offres Assignées
      </button>

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <h1 className="text-3xl font-bold">{offer.title}</h1>
          <PipelineStatusBadge jobStatus={jobStatus} />
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-500 flex-wrap">
          <span>Créée le {new Date(offer.created_at).toLocaleDateString('fr-FR')}</span>
          {offer.recruiter_name && (
            <span className="flex items-center gap-1">
              <User className="h-3.5 w-3.5" /> Assignée par
              <span className="text-slate-300 ml-1">{offer.recruiter_name}</span>
            </span>
          )}
        </div>
        {/* Status explanation — avoids confusion between offer status and pipeline status */}
        <div className="flex items-start gap-2 text-xs text-slate-500 bg-white/[0.02] border border-white/[0.06] rounded-xl px-3 py-2 mt-2">
          <Info className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
          <span>
            Statut de l&apos;offre : <strong className="text-slate-400">{offer.status_label || 'Ouverte'}</strong>.
            Le badge ci-dessus reflète l&apos;état du dernier pipeline — vous pouvez le relancer à tout moment.
          </span>
        </div>
      </motion.div>

      {/* Description + details */}
      <div className="grid sm:grid-cols-2 gap-4">
        <div className={section}>
          <h2 className="text-sm font-semibold text-slate-300">Description</h2>
          <p className="text-slate-400 text-sm leading-relaxed">{offer.description || 'Aucune description.'}</p>
        </div>
        <div className={section}>
          <h2 className="text-sm font-semibold text-slate-300">Détails</h2>
          <dl className="space-y-2 text-sm">
            {offer.experience_level && <div className="flex items-center gap-2 text-slate-400"><Star className="h-3.5 w-3.5" />{offer.experience_level}</div>}
            {offer.contract_type && <div className="flex items-center gap-2 text-slate-400"><Briefcase className="h-3.5 w-3.5" />{offer.contract_type.label_fr || offer.contract_type.code}</div>}
            {offer.experience_range?.display && <div className="flex items-center gap-2 text-slate-400"><Clock className="h-3.5 w-3.5" />{offer.experience_range.display}</div>}
            {offer.location && <div className="flex items-center gap-2 text-slate-400"><MapPin className="h-3.5 w-3.5" />{offer.location}</div>}
            {offer.salary_range && <div className="flex items-center gap-2 text-slate-400"><span className="text-xs">€</span>{offer.salary_range}</div>}
            {!offer.experience_level && !offer.contract_type && !offer.experience_range?.display && !offer.location && !offer.salary_range && (
              <p className="text-slate-500 text-xs">Aucun détail spécifié</p>
            )}
          </dl>
        </div>
      </div>

      {/* Skills */}
      {(offer.skills?.length ?? 0) > 0 && (
        <div className={section}>
          <h2 className="text-sm font-semibold text-slate-300">Compétences requises</h2>
          <div className="flex flex-wrap gap-2">
            {offer.skills.map(s => (
              <SkillBadge key={`${s.id}-${s.name}`} skill={s} />
            ))}
          </div>
        </div>
      )}

      {/* Pipeline */}
      <div className={section}>
        <h2 className="text-sm font-semibold text-slate-300">Pipeline</h2>

        {showCvLimit && (
          <CvLimitField
            id={`cv-limit-${offer.id}`}
            value={cvLimit}
            onChange={setCvLimit}
            disabled={relaunching}
          />
        )}

        {!offer.job ? (
          <div className="space-y-3">
            <p className="text-slate-500 text-sm">Aucun pipeline lancé pour cette offre.</p>
            {relaunchError && (
              <div className="flex items-center gap-2 text-sm text-red-300 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />{relaunchError}
              </div>
            )}
            {offer.offer_sftp_path ? (
              <button onClick={relaunchOffer} disabled={relaunching}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium transition-all disabled:opacity-60 disabled:cursor-not-allowed shadow-[0_4px_16px_rgba(31,157,148,0.3)]">
                {relaunching
                  ? <><Loader2 className="h-4 w-4 animate-spin" />Relance en cours…</>
                  : <><Play className="h-4 w-4" />Lancer l&apos;offre</>}
              </button>
            ) : (
              <p className="text-xs text-slate-500">Aucun fichier d&apos;offre associé — lancement impossible.</p>
            )}
          </div>

        ) : (jobStatus === 'running' || jobStatus === 'queued') ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
              <span className="text-sm text-blue-400">
                {progress?.stage ? (PROGRESS_STAGES[progress.stage] || 'Pipeline en cours…') : 'Pipeline en cours…'}
              </span>
            </div>
            {(() => {
              const pct = progress?.progress
                ? Math.round(Object.values(progress.progress).reduce((a, b) => a + b, 0) / Math.max(Object.keys(progress.progress).length, 1))
                : 0;
              return (
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs text-slate-400"><span>Progression</span><span>{pct}%</span></div>
                  <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-[#1f9d94] rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })()}
            <p className="text-xs text-slate-500">Les résultats du matching s&apos;afficheront ici automatiquement une fois le traitement terminé.</p>
          </div>

        ) : (jobStatus === 'succeeded' || jobStatus === 'completed') ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-2 text-green-400">
                <CheckCircle2 className="h-5 w-5" />
                <span className="text-sm">
                  {resultsLoading && results.length === 0
                    ? 'Chargement des résultats…'
                    : formatScoredLabel(displayedScored)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => { fetchedResultsFor.current = null; fetchOffer(); reloadMatchingResults(); }}
                  className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors"
                >
                  <RefreshCw className="h-3.5 w-3.5" /> Actualiser
                </button>
                {offer.offer_sftp_path && (
                  <button
                    onClick={relaunchOffer}
                    disabled={relaunching}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-500/20 text-slate-400 text-xs hover:text-white hover:border-white/20 transition-all disabled:opacity-50"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${relaunching ? 'animate-spin' : ''}`} />
                    {relaunching ? 'Relance en cours…' : 'Relancer le matching'}
                  </button>
                )}
              </div>
            </div>

            {relaunchError && (
              <div className="flex items-center gap-2 text-sm text-red-300 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />{relaunchError}
              </div>
            )}

            {!resultsLoading && hasScoringGap(jobCounts, results.length) && scoringGapMsg && (
              <div className="flex items-start gap-2 text-sm text-amber-300/90 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2">
                <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                <span>{scoringGapMsg} — relancez le matching pour réessayer.</span>
              </div>
            )}

            {resultsLoading && (
              <div className="flex items-center gap-2 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Chargement des résultats…</div>
            )}

            {!resultsLoading && results.length === 0 && (
              <p className="text-slate-500 text-sm">Aucun résultat de matching disponible.</p>
            )}

            {!resultsLoading && results.length > 0 && (() => {
              const sorted = [...results].sort((a, b) => a.rank - b.rank);
              const visible = showAllResults ? sorted : sorted.slice(0, RESULTS_PREVIEW);
              return (
              <div className="space-y-3">
              <div className="rounded-xl border border-white/10 overflow-hidden divide-y divide-white/[0.06]">
                {visible.map(c => {
                  const open = expanded === c.rank;
                  const app = findAppearance(c);
                  const matchingCode = app?.matching_status?.code || 'en_attente';
                  const matchingOptions = matchingStatuses.map(s => ({ value: s.code, label: s.label_fr }));
                  return (
                    <div key={`${c.rank}-${c.candidateName}`}>
                      <div className="px-4 py-3 hover:bg-white/[0.03] transition-colors">
                        <div className="grid items-center gap-4" style={{ gridTemplateColumns: '1fr auto auto' }}>
                        <button onClick={() => setExpanded(open ? null : c.rank)}
                          className="flex items-center gap-4 min-w-0 text-left">
                          <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-teal-400/30 bg-teal-400/10 text-base font-semibold text-teal-300">
                            {c.rank}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="text-sm font-semibold text-white truncate">{c.candidateName || 'Candidat'}</p>
                              {app?.unreliability_flag && (
                                <UnreliabilityFlagIndicator
                                  flag={app.unreliability_flag}
                                  candidateId={app.candidate_id}
                                  onResolved={refreshAppearances}
                                />
                              )}
                              {app && (
                                <OtherOffersBadge
                                  count={app.other_offers_count ?? 0}
                                  onClick={() => setHistoryCandidate({
                                    id: app.candidate_id,
                                    name: c.candidateName || app.full_name,
                                  })}
                                />
                              )}
                            </div>
                            <p className="text-xs text-slate-500 truncate">{c.experience !== 'N/A' ? `${c.experience} d'expérience` : 'Expérience N/A'}</p>
                          </div>
                        </button>
                        <span className={`text-lg font-bold tabular-nums ${scoreColor(c.matchScore)}`}>{formatScore(c.matchScore)}</span>
                        {app && matchingOptions.length > 0 ? (
                          <DarkSelect
                            value={matchingCode}
                            onChange={v => updateMatchingStatus(app.id, v)}
                            options={matchingOptions}
                            size="sm"
                            className="min-w-[130px] w-[130px] flex-shrink-0"
                            onClick={e => e.stopPropagation()}
                          />
                        ) : (
                          <button type="button" onClick={() => setExpanded(open ? null : c.rank)} className="flex-shrink-0">
                            <ChevronDown className={`h-4 w-4 text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} />
                          </button>
                        )}
                        </div>
                        {app && (
                          <div className="mt-3 pl-[52px] pr-8">
                            <OfferAppearanceNotes
                              appearanceId={app.id}
                              sourcerNote={app.sourcer_note}
                              recruiterNote={app.recruiter_note}
                              viewerRole="sourcer"
                              sourcerName="Moi"
                              recruiterName={offer.recruiter_name || 'Recruteur'}
                              onSaved={(field, note) => updateAppearanceNote(app.id, field, note)}
                            />
                          </div>
                        )}
                      </div>
                      <AnimatePresence initial={false}>
                        {open && (
                          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden">
                            <div className="px-4 pb-4 pt-1 space-y-3 bg-white/[0.02]">
                              <div className="grid grid-cols-3 gap-2">
                                {[['Compétences', c.skillsMatch], ['Expérience', c.experienceMatch], ['Formation', c.educationMatch]].map(([label, sc]) => (
                                  <div key={label as string} className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-center">
                                    <p className="text-[10px] uppercase tracking-wide text-slate-500">{label as string}</p>
                                    <p className={`text-sm font-semibold ${scoreColor(sc as number | null)}`}>{formatScore(sc as number | null)}</p>
                                  </div>
                                ))}
                              </div>
                              {c.summary && (
                                <div>
                                  <p className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">Recommandation</p>
                                  <p className="text-sm text-slate-300 leading-relaxed">{c.summary}</p>
                                </div>
                              )}
                              {c.skills.length > 0 && (
                                <div>
                                  <p className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">Compétences</p>
                                  <div className="flex flex-wrap gap-1.5">
                                    {c.skills.map(s => (
                                      <span key={s} className="text-xs text-teal-400 bg-teal-400/10 border border-teal-400/20 px-2 py-0.5 rounded-full">{s}</span>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  );
                })}
              </div>
              {sorted.length > RESULTS_PREVIEW && (
                <button onClick={() => setShowAllResults(v => !v)}
                  className="w-full text-center text-xs text-teal-400 hover:text-teal-300 py-2 border border-teal-400/20 rounded-xl hover:bg-teal-400/5 transition-colors">
                  {showAllResults ? 'Afficher moins' : `Voir tous les résultats (${sorted.length})`}
                </button>
              )}
              </div>
              );
            })()}

            <a href="/sourcer/candidates"
              className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white transition-colors">
              <Users className="h-3.5 w-3.5" /> Parcourir le vivier
            </a>
          </div>

        ) : jobStatus === 'failed' ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-red-400">
              <XCircle className="h-5 w-5 flex-shrink-0" />
              <span className="text-sm">Échec du pipeline — vous pouvez relancer sans perdre vos données.</span>
            </div>

            {relaunchError && (
              <div className="flex items-center gap-2 text-sm text-red-300 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                {relaunchError}
              </div>
            )}

            {offer.offer_sftp_path ? (
              <button
                onClick={relaunchOffer}
                disabled={relaunching}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium transition-all disabled:opacity-60 disabled:cursor-not-allowed shadow-[0_4px_16px_rgba(31,157,148,0.3)]"
              >
                {relaunching
                  ? <><Loader2 className="h-4 w-4 animate-spin" />Relance en cours…</>
                  : <><RefreshCw className="h-4 w-4" />Relancer le pipeline</>
                }
              </button>
            ) : (
              <button
                onClick={() => router.push('/sourcer/offers')}
                className="flex items-center gap-2 px-4 py-2 rounded-xl border border-white/10 text-slate-400 text-sm hover:text-white hover:border-white/20 transition-all"
              >
                <ArrowLeft className="h-4 w-4" /> Retour aux offres
              </button>
            )}
          </div>

        ) : (
          <p className="text-slate-500 text-sm capitalize">{jobStatus}</p>
        )}
      </div>

      <CandidateOfferHistorySheet
        open={historyCandidate !== null}
        onClose={() => setHistoryCandidate(null)}
        candidateId={historyCandidate?.id || ''}
        candidateName={historyCandidate?.name || ''}
        excludeOfferId={offer_id}
      />
    </div>
  );
}

