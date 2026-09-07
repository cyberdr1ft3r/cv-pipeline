'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  AlertCircle, CheckCircle2, ChevronDown, Download, FileText,
  Loader2, Lock, Play, RefreshCw, Upload, XCircle,
} from 'lucide-react';
import { DarkSelect } from '@/components/DarkSelect';
import { OfferAppearanceNotes } from '@/components/OfferScopedNote';
import { CandidateOfferHistorySheet, OtherOffersBadge } from '@/components/CandidateOfferHistorySheet';
import { UnreliabilityFlagIndicator, type UnreliabilityFlagInfo } from '@/components/UnreliabilityFlagIndicator';
import { scoreTextClass } from '@/lib/scoreUtils';
import { SKILL_CHIP } from '@/lib/uiTokens';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const SFTP_ERROR_MSG =
  'Stockage SFTP temporairement inaccessible. Réessayez dans quelques instants.';
const SYNC_ERROR_MSG =
  'Résultats en cours de synchronisation. Réessayez dans quelques instants.';

const SFTP_DETAIL_MARKERS = ['Stockage SFTP', 'SFTP inaccessible'];

async function responseDetail(r: Response): Promise<string> {
  try {
    const body = await r.json();
    const d = body?.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) {
      return d.map((x: { msg?: string }) => x?.msg ?? String(x)).join('; ');
    }
  } catch {
    /* ignore */
  }
  return '';
}

function isSftpFetchError(status: number, detail: string): boolean {
  if (status === 503) return true;
  return SFTP_DETAIL_MARKERS.some(m => detail.includes(m));
}

export interface PanelJob {
  id: string;
  status: string;
  stage: string;
  cv_count?: number;
}

interface MatchingCandidate {
  rank: number;
  candidateName: string | null;
  candidateId?: string | null;
  matchScore: number | null;
  experience: string;
  skills: string[];
  summary: string | null;
  skillsMatch: number | null;
  experienceMatch: number | null;
  educationMatch: number | null;
}

interface PhaseStatus {
  code: string;
  label_fr: string;
}

interface OfferAppearance {
  id: string;
  candidate_id: string;
  full_name: string;
  rank: number | null;
  matching_score: number | null;
  decision?: string;
  decision_label?: string;
  matching_status?: PhaseStatus;
  final_status?: PhaseStatus;
  format_status?: PhaseStatus;
  unreliability_flag?: UnreliabilityFlagInfo | null;
  sourcer_note?: string | null;
  recruiter_note?: string | null;
  other_offers_count?: number;
}

interface RefStatusRow {
  code: string;
  label_fr: string;
  triggers_flag?: boolean;
}

const MATCHING_BADGE: Record<string, string> = {
  en_attente: 'bg-slate-500/20 text-slate-300',
  preselectionne: 'bg-blue-400/20 text-blue-300',
  contacte: 'bg-cyan-400/20 text-cyan-300',
};

interface FinalRow {
  candidate_name: string;
  overall_score: number | null;
  test_score: number | null;
  final_score: number | null;
  rank: number | null;
}

const TEMPLATES = [
  { id: 'classic', name: 'Classic', description: 'Traditionnel et professionnel' },
  { id: 'minimal', name: 'Minimal', description: 'Épuré et moderne' },
  { id: 'modern', name: 'Modern', description: 'Contemporain et dynamique' },
];

function pct(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--';
  const n = value <= 1 ? value * 100 : value;
  return `${n.toFixed(0)}%`;
}

function scoreColor(score: number | null): string {
  return scoreTextClass(score);
}

/** Normalize candidate name for appearance lookup (accents, apostrophes, underscores). */
function normalizePersonName(name: string): string {
  return name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[_\-]+/g, ' ')
    .replace(/[''`´]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

/** Normalize candidate name for matching formatted_cv filename stems (underscore â†” space). */
function normalizeFormatName(name: string): string {
  return normalizePersonName(name.replace(/_/g, ' '));
}

function isFormattedCandidate(name: string, formattedStems: string[]): boolean {
  const norm = normalizeFormatName(name);
  return formattedStems.some(stem => normalizeFormatName(stem) === norm);
}

// Stages that precede any displayable result (extraction + matching). While the job
// is in one of these, the panel shows a single dynamic progress message.
const EARLY_STAGES = ['preparing_inputs', 'running_transformer', 'running_ingestor', 'running_pipeline'];

// French message for the active early phase, driven by the polled job.stage.
function earlyPhaseLabel(stage: string, status: string): string {
  if (status === 'queued' || stage === '') return 'Pipeline en file d\u2019attente\u2026';
  switch (stage) {
    case 'preparing_inputs': return 'Pr\u00e9paration des fichiers\u2026';
    case 'running_transformer': return 'Extraction des donn\u00e9es des CVs\u2026';
    case 'running_ingestor': return 'Analyse et indexation des CVs\u2026';
    case 'running_pipeline': return 'Matching des candidats en cours\u2026';
    default: return 'Traitement en cours\u2026';
  }
}

/**
 * In-space recruiter pipeline panel — surfaces matching results, the final scoring
 * table and CV formatting without ever leaving the recruiter space (Action 224).
 * All work is driven by the existing /jobs/{id}/{matching,final,format} endpoints;
 * stage detection polls the offer's job.stage (final_complete / format_complete).
 */
export default function RecruiterPipelinePanel({
  offerId, job, statusId, onStageAdvance, sourcerName, recruiterName,
}: {
  offerId: string;
  job: PanelJob | null;
  statusId: number | null;
  onStageAdvance?: () => void;
  sourcerName?: string;
  recruiterName?: string;
}) {
  const [stage, setStage] = useState<string>(job?.stage || '');
  const [status, setStatus] = useState<string>(job?.status || '');

  // Matching
  const [matching, setMatching] = useState<MatchingCandidate[]>([]);
  const [matchingLoading, setMatchingLoading] = useState(false);
  const [matchingError, setMatchingError] = useState('');
  const [matchingCountdown, setMatchingCountdown] = useState(0);
  const matchingAutoRetried = useRef(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [matchingSectionOpen, setMatchingSectionOpen] = useState(true);
  const fetchedMatchingFor = useRef<string | null>(null);
  const [appearances, setAppearances] = useState<OfferAppearance[]>([]);
  const fetchedAppearancesFor = useRef<string | null>(null);
  const [selectedForFinal, setSelectedForFinal] = useState<string[]>([]);
  const initializedFinalSelection = useRef<string | null>(null);
  const [historyCandidate, setHistoryCandidate] = useState<{ id: string; name: string } | null>(null);
  const [matchingStatuses, setMatchingStatuses] = useState<RefStatusRow[]>([]);
  const [finalStatuses, setFinalStatuses] = useState<RefStatusRow[]>([]);
  const [formatStatuses, setFormatStatuses] = useState<RefStatusRow[]>([]);
  const [nonIntegreDraft, setNonIntegreDraft] = useState<{ appearanceId: string; reason: string } | null>(null);
  const [nonIntegreSaving, setNonIntegreSaving] = useState(false);

  // Final
  const [finalRows, setFinalRows] = useState<FinalRow[]>([]);
  const [finalRunning, setFinalRunning] = useState(false);
  const [testsFile, setTestsFile] = useState<File | null>(null);
  const [finalError, setFinalError] = useState('');
  const [finalFetchError, setFinalFetchError] = useState('');
  const [finalCountdown, setFinalCountdown] = useState(0);
  const finalAutoRetried = useRef(false);
  const fetchedFinalFor = useRef<string | null>(null);
  const [relaunchOpen, setRelaunchOpen] = useState(false);
  const [relaunchStep, setRelaunchStep] = useState<'file' | 'select' | 'confirm'>('file');
  const [finalSectionOpen, setFinalSectionOpen] = useState(true);
  const finalRelaunchPending = useRef(false);
  const relaunchSawRunning = useRef(false);

  // Format
  const MAX_SELECT = 10;
  const [template, setTemplate] = useState('classic');
  const [limitMode, setLimitMode] = useState<'all' | 'number' | 'manual'>('all');
  const [limitNumber, setLimitNumber] = useState(3);
  const [selectedCandidates, setSelectedCandidates] = useState<string[]>([]);
  const [formatRunning, setFormatRunning] = useState(false);
  const [formatError, setFormatError] = useState('');
  const [formatStaleAfterRelaunch, setFormatStaleAfterRelaunch] = useState(false);
  const formatWasCompleted = useRef(false);
  const [formattedCandidateStems, setFormattedCandidateStems] = useState<string[] | null>(null);

  const jobId = job?.id;

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/ref/matching-statuses`, { credentials: 'include' }).then(r => r.ok ? r.json() : null),
      fetch(`${API_BASE}/ref/final-statuses`, { credentials: 'include' }).then(r => r.ok ? r.json() : null),
      fetch(`${API_BASE}/ref/format-statuses`, { credentials: 'include' }).then(r => r.ok ? r.json() : null),
    ]).then(([m, f, fmt]) => {
      if (m?.matching_statuses) setMatchingStatuses(m.matching_statuses);
      if (f?.final_statuses) setFinalStatuses(f.final_statuses);
      if (fmt?.format_statuses) setFormatStatuses(fmt.format_statuses);
    }).catch(() => null);
  }, []);

  useEffect(() => {
    setStage(job?.stage || '');
    setStatus(job?.status || '');
  }, [job?.stage, job?.status]);

  useEffect(() => {
    matchingAutoRetried.current = false;
    finalAutoRetried.current = false;
    setMatchingError('');
    setFinalFetchError('');
    setMatchingCountdown(0);
    setFinalCountdown(0);
    initializedFinalSelection.current = null;
    setSelectedForFinal([]);
    setRelaunchOpen(false);
    setRelaunchStep('file');
    setTestsFile(null);
    finalRelaunchPending.current = false;
    relaunchSawRunning.current = false;
    formatWasCompleted.current = false;
    setFormatStaleAfterRelaunch(false);
    setFormattedCandidateStems(null);
  }, [jobId]);

  useEffect(() => {
    if (stage === 'format_complete') {
      formatWasCompleted.current = true;
      setFormatStaleAfterRelaunch(false);
    }
  }, [stage]);

  useEffect(() => {
    const prefetchStages = ['final_complete', 'running_format', 'format_complete'];
    if (!jobId || !prefetchStages.includes(stage)) {
      if (stage !== 'format_complete') setFormattedCandidateStems(null);
      return;
    }
    let cancelled = false;
    fetch(`${API_BASE}/jobs/${jobId}/formatted-candidates`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!cancelled) {
          setFormattedCandidateStems(Array.isArray(d?.candidates) ? d.candidates : []);
        }
      })
      .catch(() => { if (!cancelled) setFormattedCandidateStems([]); });
    return () => { cancelled = true; };
  }, [jobId, stage]);

  // Matching is done from matching_complete onward (including while final/format run).
  const matchingDone = status === 'succeeded' || status === 'completed'
    || ['matching_complete', 'running_final', 'final_complete', 'running_format', 'format_complete'].includes(stage);
  // Final scoring is done from final_complete onward (including while formatting runs).
  const finalDone = ['final_complete', 'running_format', 'format_complete'].includes(stage);
  const isRunningFinal = finalRunning || stage === 'running_final';
  const isRunningFormat = formatRunning || stage === 'running_format';
  const sid = statusId ?? 0;

  // Poll while the job is in any non-terminal (running/queued) state OR a recruiter
  // just triggered a phase — so the UI auto-advances through every stage (extraction →
  // matching → final → format) without a manual refresh.
  const isPolling = status === 'running' || status === 'queued' || finalRunning || formatRunning;

  // Poll the offer's job stage while a phase is active.
  const pollStage = useCallback(() => {
    if (!offerId) return;
    fetch(`${API_BASE}/offers/${offerId}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d?.job) return;
        setStage(d.job.stage || '');
        setStatus(d.job.status || '');
        if (['final_complete', 'format_complete'].includes(d.job.stage)) setFinalRunning(false);
        if (d.job.stage === 'format_complete' || d.job.status === 'failed') setFormatRunning(false);
        if (d.job.status === 'failed') setFinalRunning(false);
      })
      .catch(() => null);
  }, [offerId]);

  useEffect(() => {
    if (!isPolling) return;
    const t = setInterval(pollStage, 3000);
    return () => clearInterval(t);
  }, [isPolling, pollStage]);

  const fetchMatching = useCallback(() => {
    if (!jobId || !matchingDone) return;
    setMatchingLoading(true);
    setMatchingError('');
    fetch(`${API_BASE}/jobs/${jobId}/matching`, { credentials: 'include' })
      .then(async r => {
        if (!r.ok) {
          const detail = await responseDetail(r);
          if (isSftpFetchError(r.status, detail)) throw { type: 'sftp' as const };
          if (r.status === 404) throw { type: 'sync' as const };
          throw new Error(`Erreur ${r.status}`);
        }
        return r.json();
      })
      .then(d => {
        setMatching(d.results || []);
        fetchedMatchingFor.current = jobId;
        setMatchingLoading(false);
      })
      .catch(err => {
        setMatchingLoading(false);
        fetchedMatchingFor.current = null;
        if (err && typeof err === 'object' && 'type' in err) {
          if (err.type === 'sftp') {
            setMatchingError(SFTP_ERROR_MSG);
            if (!matchingAutoRetried.current) {
              matchingAutoRetried.current = true;
              setMatchingCountdown(10);
            }
          } else if (err.type === 'sync') {
            setMatchingError(SYNC_ERROR_MSG);
            if (!matchingAutoRetried.current) {
              matchingAutoRetried.current = true;
              setMatchingCountdown(10);
            }
          }
        }
      });
  }, [jobId, matchingDone]);

  useEffect(() => {
    if (!jobId || !matchingDone || fetchedMatchingFor.current === jobId) return;
    fetchMatching();
  }, [jobId, matchingDone, fetchMatching]);

  useEffect(() => {
    if (matchingCountdown <= 0) return;
    const timer = setInterval(() => {
      setMatchingCountdown(prev => {
        if (prev <= 1) {
          fetchMatching();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [matchingCountdown, fetchMatching]);

  useEffect(() => {
    if (!offerId || !matchingDone) return;
    fetch(`${API_BASE}/offers/${offerId}/appearances`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(d => setAppearances(d.candidates || []))
      .catch(() => null);
  }, [offerId, matchingDone, matching.length]);

  useEffect(() => {
    if (!jobId || matching.length === 0) return;
    if (initializedFinalSelection.current === jobId) return;
    initializedFinalSelection.current = jobId;
    setSelectedForFinal(
      matching
        .map(c => c.candidateName)
        .filter((n): n is string => Boolean(n)),
    );
  }, [jobId, matching]);

  function findAppearance(c: MatchingCandidate): OfferAppearance | undefined {
    if (c.candidateId) {
      const byId = appearances.find(a => a.candidate_id === c.candidateId);
      if (byId) return byId;
    }
    const rank = Number(c.rank);
    const byRank = appearances.find(a => Number(a.rank) === rank);
    if (byRank) return byRank;
    const name = normalizePersonName(c.candidateName || '');
    if (!name) return undefined;
    return appearances.find(a => normalizePersonName(a.full_name || '') === name);
  }

  function findAppearanceByName(name: string, rank?: number | null): OfferAppearance | undefined {
    const norm = normalizePersonName(name);
    if (!norm) return undefined;
    const matches = appearances.filter(a => normalizePersonName(a.full_name || '') === norm);
    if (matches.length === 1) return matches[0];
    if (rank != null) {
      const byRank = matches.find(a => Number(a.rank) === Number(rank));
      if (byRank) return byRank;
    }
    return matches[0];
  }

  function syncCandidateFlag(candidateId: string, flag: UnreliabilityFlagInfo | null | undefined) {
    if (!flag) return;
    setAppearances(prev => prev.map(a =>
      a.candidate_id === candidateId ? { ...a, unreliability_flag: flag } : a,
    ));
  }

  function patchAppearanceLocal(appearanceId: string, patch: Partial<OfferAppearance>) {
    setAppearances(prev => prev.map(a => a.id === appearanceId ? { ...a, ...patch } : a));
  }

  async function updatePhaseStatus(
    appearanceId: string,
    phase: 'matching' | 'final' | 'format',
    statusCode: string,
    flagReason?: string,
  ) {
    const body: Record<string, string> = { phase, status_code: statusCode };
    if (flagReason) body.flag_reason = flagReason;
    const res = await fetch(`${API_BASE}/candidates/appearances/${appearanceId}/status`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.ok) {
      const d = await res.json();
      const updated = d.appearance as OfferAppearance;
      patchAppearanceLocal(appearanceId, updated);
      if (updated.candidate_id && updated.unreliability_flag) {
        syncCandidateFlag(updated.candidate_id, updated.unreliability_flag);
      }
    }
  }

  function handleFormatStatusChange(appearanceId: string, statusCode: string) {
    if (statusCode === 'non_integre') {
      setNonIntegreDraft({ appearanceId, reason: '' });
      return;
    }
    setNonIntegreDraft(null);
    updatePhaseStatus(appearanceId, 'format', statusCode);
  }

  async function saveNonIntegreFlag() {
    if (!nonIntegreDraft?.reason.trim()) return;
    setNonIntegreSaving(true);
    try {
      await updatePhaseStatus(
        nonIntegreDraft.appearanceId,
        'format',
        'non_integre',
        nonIntegreDraft.reason.trim(),
      );
      setNonIntegreDraft(null);
    } finally {
      setNonIntegreSaving(false);
    }
  }

  function refreshAppearances() {
    if (!offerId) return;
    fetch(`${API_BASE}/offers/${offerId}/appearances`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(d => setAppearances(d.candidates || []))
      .catch(() => null);
  }

  function updateAppearanceNote(appearanceId: string, field: 'sourcer_note' | 'recruiter_note', note: string) {
    setAppearances(prev => prev.map(a => a.id === appearanceId ? { ...a, [field]: note } : a));
  }

  function toggleFinalCandidate(name: string) {
    setSelectedForFinal(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name],
    );
  }

  function selectAllForFinal() {
    setSelectedForFinal(
      matching.map(c => c.candidateName).filter((n): n is string => Boolean(n)),
    );
  }

  function deselectAllForFinal() {
    setSelectedForFinal([]);
  }

  const fetchFinal = useCallback(() => {
    if (!jobId || !finalDone) return;
    setFinalFetchError('');
    fetch(`${API_BASE}/jobs/${jobId}/final?_=${Date.now()}`, { credentials: 'include' })
      .then(async r => {
        if (!r.ok) {
          const detail = await responseDetail(r);
          if (isSftpFetchError(r.status, detail)) throw { type: 'sftp' as const };
          if (r.status === 404) throw { type: 'sync' as const };
          throw new Error(`Erreur ${r.status}`);
        }
        return r.json();
      })
      .then(d => {
        setFinalRows(d.rows || []);
        fetchedFinalFor.current = jobId;
        onStageAdvance?.();
      })
      .catch(err => {
        fetchedFinalFor.current = null;
        if (err && typeof err === 'object' && 'type' in err) {
          if (err.type === 'sftp') {
            setFinalFetchError(SFTP_ERROR_MSG);
            if (!finalAutoRetried.current) {
              finalAutoRetried.current = true;
              setFinalCountdown(10);
            }
          } else if (err.type === 'sync') {
            setFinalFetchError(SYNC_ERROR_MSG);
            if (!finalAutoRetried.current) {
              finalAutoRetried.current = true;
              setFinalCountdown(10);
            }
          }
        }
      });
  }, [jobId, finalDone, onStageAdvance]);

  useEffect(() => {
    if (!jobId || !finalDone) return;
    if (fetchedFinalFor.current === jobId) return;
    fetchFinal();
  }, [jobId, finalDone, fetchFinal]);

  useEffect(() => {
    if (!finalRelaunchPending.current) return;
    if (stage === 'running_final') {
      relaunchSawRunning.current = true;
      return;
    }
    if (!relaunchSawRunning.current || stage !== 'final_complete') return;
    const hadFormattedCvs = formatWasCompleted.current;
    finalRelaunchPending.current = false;
    relaunchSawRunning.current = false;
    fetchedFinalFor.current = null;
    if (hadFormattedCvs) setFormatStaleAfterRelaunch(true);
    fetchFinal();
    setRelaunchOpen(false);
    setRelaunchStep('file');
    setTestsFile(null);
    setFinalRunning(false);
    setFormatRunning(false);
    setSelectedCandidates([]);
    setFormatError('');
    onStageAdvance?.();
  }, [stage, fetchFinal, onStageAdvance]);

  useEffect(() => {
    if (finalCountdown <= 0) return;
    const timer = setInterval(() => {
      setFinalCountdown(prev => {
        if (prev <= 1) {
          fetchFinal();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [finalCountdown, fetchFinal]);

  function seedRelaunchSelection() {
    const matchingNames = matching
      .map(c => c.candidateName)
      .filter((n): n is string => Boolean(n));
    const previousFinalNames = finalRows
      .map(r => r.candidate_name)
      .filter((n): n is string => Boolean(n));
    const seeded = matchingNames.filter(m =>
      previousFinalNames.some(p => p.toLowerCase() === m.toLowerCase()),
    );
    setSelectedForFinal(seeded.length > 0 ? seeded : previousFinalNames);
  }

  function openRelaunchPanel() {
    seedRelaunchSelection();
    setFinalError('');
    setRelaunchStep('file');
    setRelaunchOpen(true);
    setFinalSectionOpen(true);
  }

  function closeRelaunchPanel() {
    setRelaunchOpen(false);
    setRelaunchStep('file');
    setTestsFile(null);
    setFinalError('');
  }

  async function runFinal(options?: { isRelaunch?: boolean }) {
    if (!jobId) return;
    const candidates = selectedForFinal;
    if (candidates.length === 0) {
      setFinalError('Sélectionnez au moins un candidat');
      return;
    }
    setFinalError('');
    setFinalRunning(true);
    if (options?.isRelaunch) {
      finalRelaunchPending.current = true;
      relaunchSawRunning.current = false;
      setStage('running_final');
    }
    try {
      const fd = new FormData();
      if (testsFile) fd.append('tests_file', testsFile, testsFile.name);
      fd.append('candidates', JSON.stringify(candidates));
      const res = await fetch(`${API_BASE}/jobs/${jobId}/final`, { method: 'POST', credentials: 'include', body: fd });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Erreur ${res.status}`);
      fetchedFinalFor.current = null;
      setFinalRows([]);
      pollStage();
      setTimeout(pollStage, 1500);
      setTimeout(pollStage, 4000);
    } catch (e: unknown) {
      setFinalError(e instanceof Error ? e.message : 'Erreur lors du scoring final');
      setFinalRunning(false);
      finalRelaunchPending.current = false;
      relaunchSawRunning.current = false;
    }
  }

  async function runFormat() {
    if (!jobId) return;
    if (limitMode === 'manual' && selectedCandidates.length === 0) {
      setFormatError('Sélectionnez au moins un candidat à formater.');
      return;
    }
    setFormatError('');
    setFormatRunning(true);
    try {
      const fd = new FormData();
      fd.append('template', template);
      if (limitMode === 'number' && limitNumber > 0) {
        fd.append('limit', String(limitNumber));
      } else if (limitMode === 'manual') {
        fd.append('candidates', JSON.stringify(selectedCandidates.slice(0, MAX_SELECT)));
      }
      const res = await fetch(`${API_BASE}/jobs/${jobId}/format`, { method: 'POST', credentials: 'include', body: fd });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Erreur ${res.status}`);
      setTimeout(pollStage, 1500);
    } catch (e: unknown) {
      setFormatError(e instanceof Error ? e.message : 'Erreur lors du formatage');
      setFormatRunning(false);
    }
  }

  function toggleCandidate(name: string) {
    setSelectedCandidates(prev => {
      if (prev.includes(name)) return prev.filter(n => n !== name);
      if (prev.length >= MAX_SELECT) return prev;
      return [...prev, name];
    });
  }

  function downloadZip() {
    if (!jobId) return;
    window.open(`${API_BASE}/jobs/${jobId}/download/formatted_zip`, '_blank', 'noopener,noreferrer');
  }

  function cancelReformat() {
    if (!formatWasCompleted.current) return;
    setFormatError('');
    setFormatRunning(false);
    setSelectedCandidates([]);
    setStage('format_complete');
  }

  const card = 'rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-4';
  const sortedFinal = [...finalRows].sort((a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9));
  const offerArchived = sid === 7;
  const formatLocked = sid === 4;
  // Stage is authoritative — status_id can lag after a final relaunch (still 6 while stage is final_complete).
  const formatCompleted = stage === 'format_complete';
  const showFormatCompleted = formatCompleted || (offerArchived && formatWasCompleted.current);
  const formattedFinalRows = showFormatCompleted && formattedCandidateStems !== null
    ? sortedFinal.filter(row => isFormattedCandidate(row.candidate_name, formattedCandidateStems))
    : [];
  const formatOutdated = formatStaleAfterRelaunch;
  const formatActive = (finalDone || sid >= 5) && !formatCompleted && !isRunningFinal && !formatLocked;
  const showFormatActive = formatActive && !offerArchived;
  const finalReadOnly = (finalDone || finalRows.length > 0) && !relaunchOpen;
  const finalCtaActive = sid === 4 && !finalDone && !isRunningFinal;
  const canRelaunchFinal = (finalDone || finalRows.length > 0) && !isRunningFinal && !!jobId;
  const relaunchInputId = `tests-relaunch-${jobId}`;
  const matchingSummaryMode = sid >= 5;
  const candidateCount = matching.length || job?.cv_count || 0;
  const sortedMatching = [...matching].sort((a, b) => a.rank - b.rank);
  const finalSelectionCount = selectedForFinal.length;

  // â”€â”€ No job â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  if (!job) {
    return <div className={card}><h2 className="text-sm font-semibold text-slate-300">Pipeline</h2>
      <p className="text-slate-500 text-sm">Aucun pipeline lancé. Le sourceur assigné doit lancer le matching.</p></div>;
  }
  // â”€â”€ Failed â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  if (status === 'failed') {
    return <div className={card}><h2 className="text-sm font-semibold text-slate-300">Pipeline</h2>
      <div className="flex items-center gap-2 text-red-400"><XCircle className="h-5 w-5" /><span className="text-sm">Échec du pipeline. Vérifiez les journaux ou relancez le traitement.</span></div></div>;
  }
  // â”€â”€ Early phase (extraction / matching) — dynamic message, auto-updates â”€â”€â”€â”€â”€â”€
  if ((status === 'running' || status === 'queued') && (stage === '' || EARLY_STAGES.includes(stage))) {
    return <div className={card}><h2 className="text-sm font-semibold text-slate-300">Pipeline</h2>
      <div className="flex items-center gap-3"><Loader2 className="h-5 w-5 animate-spin text-teal-400" />
        <span className="text-sm text-teal-400">{earlyPhaseLabel(stage, status)} Les résultats s&apos;afficheront ici automatiquement.</span></div></div>;
  }

  return (
    <div className="space-y-6">
      {/* â”€â”€ Matching results â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div className={card}>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <h2 className="text-sm font-semibold text-slate-300">Résultats du matching</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-green-400 bg-green-400/10 px-2.5 py-1 rounded-full">
              {candidateCount} candidat{candidateCount > 1 ? 's' : ''} analysé{candidateCount > 1 ? 's' : ''}
            </span>
            {matchingSummaryMode && (
              <button
                type="button"
                onClick={() => setMatchingSectionOpen(v => !v)}
                className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors"
              >
                {matchingSectionOpen ? 'Réduire' : 'Afficher'}
                <ChevronDown className={`h-3.5 w-3.5 transition-transform ${matchingSectionOpen ? 'rotate-180' : ''}`} />
              </button>
            )}
          </div>
        </div>

        {matchingSummaryMode && !matchingSectionOpen && !matchingLoading && (
          <p className="text-slate-500 text-sm">
            {candidateCount} candidat{candidateCount > 1 ? 's' : ''} classé{candidateCount > 1 ? 's' : ''} par le matching — cliquez sur « Afficher » pour voir le détail.
          </p>
        )}

        {matchingLoading && <div className="flex items-center gap-2 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Chargement…</div>}
        {matchingError && (
          <div className="flex flex-col gap-2 text-sm text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <span>{matchingError}</span>
            </div>
            {matchingCountdown > 0 && (
              <p className="text-xs text-amber-200/80 pl-6">Nouvelle tentative dans {matchingCountdown}s…</p>
            )}
            <button
              type="button"
              onClick={() => { setMatchingCountdown(0); fetchMatching(); }}
              className="self-start ml-6 text-xs font-medium text-amber-200 hover:text-white transition-colors underline"
            >
              Réessayer
            </button>
          </div>
        )}
        {(!matchingSummaryMode || matchingSectionOpen) && !matchingLoading && !matchingError && matching.length === 0 && (
          <p className="text-slate-500 text-sm">Aucun résultat de matching disponible.</p>
        )}

        {(!matchingSummaryMode || matchingSectionOpen) && !matchingLoading && matching.length > 0 && (
          <>
          <div className="rounded-xl border border-white/10 overflow-hidden divide-y divide-white/[0.06]">
            {sortedMatching.map(c => {
              const open = expanded === c.rank;
              const app = findAppearance(c);
              const matchingCode = app?.matching_status?.code || 'en_attente';
              const matchingLabel = app?.matching_status?.label_fr || 'En attente';
              const name = c.candidateName || '';
              const checkedForFinal = name ? selectedForFinal.includes(name) : false;
              const matchingOptions = matchingStatuses.map(s => ({ value: s.code, label: s.label_fr }));
              return (
                <div key={`${c.rank}-${c.candidateName}`}>
                  <div className="px-4 py-3 hover:bg-white/[0.03] transition-colors">
                    <div className="grid items-center gap-3" style={{ gridTemplateColumns: finalCtaActive && name ? 'auto 1fr auto auto' : '1fr auto auto' }}>
                      {finalCtaActive && name && (
                        <button
                          type="button"
                          onClick={() => toggleFinalCandidate(name)}
                          className="flex-shrink-0"
                          aria-label={checkedForFinal ? 'Désélectionner' : 'Sélectionner'}
                        >
                          <span className={`flex h-5 w-5 items-center justify-center rounded-md border ${checkedForFinal ? 'border-[#1f9d94] bg-[#1f9d94] text-white' : 'border-white/20'}`}>
                            {checkedForFinal && <CheckCircle2 className="h-4 w-4" />}
                          </span>
                        </button>
                      )}
                      <button onClick={() => setExpanded(open ? null : c.rank)}
                        className="flex items-center gap-4 min-w-0 text-left">
                        <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-teal-400/30 bg-teal-400/10 text-base font-semibold text-teal-300">{c.rank}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="text-sm font-semibold text-white truncate">{c.candidateName || 'Candidat'}</p>
                            {app?.unreliability_flag && (
                              <UnreliabilityFlagIndicator
                                flag={app.unreliability_flag}
                                candidateId={app.candidate_id}
                                canResolve
                                onResolved={refreshAppearances}
                              />
                            )}
                            <span className={`text-[10px] px-2 py-0.5 rounded-full ${MATCHING_BADGE[matchingCode] || MATCHING_BADGE.en_attente}`}>{matchingLabel}</span>
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
                      <span className={`text-lg font-bold tabular-nums ${scoreColor(c.matchScore)}`}>{pct(c.matchScore)}</span>
                      {app && matchingOptions.length > 0 ? (
                        <DarkSelect
                          value={matchingCode}
                          onChange={v => updatePhaseStatus(app.id, 'matching', v)}
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
                      <div className={`mt-3 ${finalCtaActive && name ? 'pl-8' : ''} pr-4`}>
                        <OfferAppearanceNotes
                          appearanceId={app.id}
                          sourcerNote={app.sourcer_note}
                          recruiterNote={app.recruiter_note}
                          viewerRole="recruiter"
                          sourcerName={sourcerName || 'Sourceur'}
                          recruiterName={recruiterName || 'Recruteur'}
                          onSaved={(field, note) => updateAppearanceNote(app.id, field, note)}
                        />
                      </div>
                    )}
                  </div>
                  <AnimatePresence initial={false}>
                    {open && (
                      <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                        <div className="px-4 pb-4 pt-1 space-y-3 bg-white/[0.02]">
                          <div className="grid grid-cols-3 gap-2">
                            {[['Compétences', c.skillsMatch], ['Expérience', c.experienceMatch], ['Formation', c.educationMatch]].map(([label, sc]) => (
                              <div key={label as string} className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-center">
                                <p className="text-[10px] uppercase tracking-wide text-slate-500">{label as string}</p>
                                <p className={`text-sm font-semibold ${scoreColor(sc as number | null)}`}>{pct(sc as number | null)}</p>
                              </div>
                            ))}
                          </div>
                          {c.summary && <div><p className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">Recommandation</p><p className="text-sm text-slate-300 leading-relaxed">{c.summary}</p></div>}
                          {c.skills.length > 0 && (
                            <div><p className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">Compétences</p>
                              <div className="flex flex-wrap gap-1.5">{c.skills.map(s => <span key={s} className={SKILL_CHIP}>{s}</span>)}</div></div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>

          {finalCtaActive && (
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
              <div>
                <p className="text-sm font-semibold text-slate-300">Sélection pour le résultat final</p>
                <p className="text-xs text-slate-500 mt-1">
                  {finalSelectionCount}/{sortedMatching.length} candidat{sortedMatching.length > 1 ? 's' : ''} sélectionné{finalSelectionCount > 1 ? 's' : ''}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <button type="button" onClick={selectAllForFinal}
                  className="px-3 py-1.5 rounded-lg border border-white/10 text-xs text-slate-400 hover:text-white transition-colors">
                  Tout sélectionner
                </button>
                <button type="button" onClick={deselectAllForFinal}
                  className="px-3 py-1.5 rounded-lg border border-white/10 text-xs text-slate-400 hover:text-white transition-colors">
                  Tout désélectionner
                </button>
              </div>
            </div>
          )}
          </>
        )}
      </div>

      {/* â”€â”€ Résultat final â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div className={card}>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <h2 className="text-sm font-semibold text-slate-300">Résultat final</h2>
          <div className="flex items-center gap-2 flex-wrap">
            {sortedFinal.length > 0 && !relaunchOpen && (
              <span className="text-xs text-emerald-400 bg-emerald-400/10 px-2.5 py-1 rounded-full">
                {sortedFinal.length} candidat{sortedFinal.length > 1 ? 's' : ''} classé{sortedFinal.length > 1 ? 's' : ''}
              </span>
            )}
            {canRelaunchFinal && !relaunchOpen && (
              <button
                type="button"
                onClick={openRelaunchPanel}
                className="flex items-center gap-1.5 text-xs font-medium text-teal-300 bg-teal-500/10 border border-teal-500/25 px-2.5 py-1 rounded-full hover:bg-teal-500/20 transition-colors"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Relancer
              </button>
            )}
            {finalDone && !relaunchOpen && (
              <button
                type="button"
                onClick={() => setFinalSectionOpen(v => !v)}
                className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors"
              >
                {finalSectionOpen ? 'Réduire' : 'Afficher'}
                <ChevronDown className={`h-3.5 w-3.5 transition-transform ${finalSectionOpen ? 'rotate-180' : ''}`} />
              </button>
            )}
          </div>
        </div>

        {finalDone && !finalSectionOpen && !relaunchOpen && !isRunningFinal && (
          <p className="text-slate-500 text-sm">
            {sortedFinal.length} candidat{sortedFinal.length > 1 ? 's' : ''} au classement final
            {sortedFinal.some(r => r.test_score != null) ? ' (scores de tests inclus)' : ''}
            {' '}— cliquez sur « Afficher » pour le détail.
          </p>
        )}

        {isRunningFinal && (finalDone || relaunchOpen || finalRows.length > 0) ? (
          <div className="flex items-center gap-3 py-4">
            <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
            <span className="text-sm text-cyan-300">Recalcul du scoring final…</span>
          </div>
        ) : relaunchOpen ? (
          <div className="space-y-4 rounded-xl border border-teal-500/20 bg-teal-500/5 p-4">
            {relaunchStep === 'file' && (
              <>
                <p className="text-sm text-slate-300">
                  Recalcul du classement final. Vous pouvez joindre un nouveau fichier CoderPad / CSV (optionnel),
                  puis choisir les candidats à inclure.
                </p>
                {finalError && (
                  <div className="flex items-center gap-2 text-sm text-red-300 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />{finalError}
                  </div>
                )}
                <div className="space-y-2">
                  <input
                    id={relaunchInputId}
                    type="file"
                    accept=".csv,.xlsx,.xls,.txt"
                    className="sr-only"
                    onChange={e => { setTestsFile(e.target.files?.[0] || null); setFinalError(''); }}
                  />
                  <label
                    htmlFor={relaunchInputId}
                    className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm cursor-pointer transition-all w-fit ${
                      testsFile
                        ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                        : 'border-white/15 text-slate-400 hover:border-white/25 hover:text-white'
                    }`}
                  >
                    <Upload className="h-4 w-4 shrink-0" />
                    {testsFile ? testsFile.name : 'Choisir le fichier CoderPad / CSV (optionnel)'}
                  </label>
                  {!testsFile && (
                    <p className="text-xs text-slate-500">
                      Sans fichier, seuls les scores de matching seront utilisés (colonne Test : --).
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    type="button"
                    onClick={closeRelaunchPanel}
                    className="px-4 py-2 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white transition-colors"
                  >
                    Annuler
                  </button>
                  <button
                    type="button"
                    onClick={() => { setFinalError(''); setRelaunchStep('select'); }}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium transition-all"
                  >
                    Continuer
                  </button>
                </div>
              </>
            )}
            {relaunchStep === 'select' && (
              <>
                <div>
                  <p className="text-sm font-medium text-white">Sélection des candidats</p>
                  <p className="text-xs text-slate-500 mt-1">
                    {finalSelectionCount}/{sortedMatching.length} candidat{sortedMatching.length > 1 ? 's' : ''} sélectionné{finalSelectionCount > 1 ? 's' : ''} pour le recalcul
                  </p>
                </div>
                {finalError && (
                  <div className="flex items-center gap-2 text-sm text-red-300 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />{finalError}
                  </div>
                )}
                <div className="flex items-center gap-2 flex-wrap">
                  <button type="button" onClick={selectAllForFinal}
                    className="px-3 py-1.5 rounded-lg border border-white/10 text-xs text-slate-400 hover:text-white transition-colors">
                    Tout sélectionner
                  </button>
                  <button type="button" onClick={deselectAllForFinal}
                    className="px-3 py-1.5 rounded-lg border border-white/10 text-xs text-slate-400 hover:text-white transition-colors">
                    Tout désélectionner
                  </button>
                </div>
                <div className="max-h-72 overflow-y-auto rounded-xl border border-white/10 divide-y divide-white/[0.06]">
                  {sortedMatching.map(c => {
                    const name = c.candidateName || '';
                    const checked = name ? selectedForFinal.includes(name) : false;
                    return (
                      <div key={`relaunch-${c.rank}-${name}`} className="flex items-center gap-3 px-3 py-2.5 hover:bg-white/[0.03]">
                        {name ? (
                          <button
                            type="button"
                            onClick={() => toggleFinalCandidate(name)}
                            className="flex-shrink-0"
                            aria-label={checked ? 'Désélectionner' : 'Sélectionner'}
                          >
                            <span className={`flex h-5 w-5 items-center justify-center rounded-md border ${checked ? 'border-[#1f9d94] bg-[#1f9d94] text-white' : 'border-white/20'}`}>
                              {checked && <CheckCircle2 className="h-4 w-4" />}
                            </span>
                          </button>
                        ) : (
                          <span className="h-5 w-5 flex-shrink-0" />
                        )}
                        <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md border border-teal-400/30 bg-teal-400/10 text-xs font-semibold text-teal-300">{c.rank}</span>
                        <span className="flex-1 min-w-0 text-sm font-medium text-white truncate">{c.candidateName || 'Candidat'}</span>
                        <span className={`text-sm font-semibold ${scoreColor(c.matchScore)}`}>{pct(c.matchScore)}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => { setFinalError(''); setRelaunchStep('file'); }}
                    className="px-4 py-2 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white transition-colors"
                  >
                    Retour
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (finalSelectionCount === 0) {
                        setFinalError('Sélectionnez au moins un candidat');
                        return;
                      }
                      setFinalError('');
                      setRelaunchStep('confirm');
                    }}
                    disabled={finalSelectionCount === 0}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Continuer
                  </button>
                </div>
              </>
            )}
            {relaunchStep === 'confirm' && (
              <>
                <p className="text-sm font-medium text-white">Confirmer le recalcul</p>
                <p className="text-sm text-slate-400">
                  {testsFile ? (
                    <>
                      Le classement de{' '}
                      <span className="text-white font-medium">{finalSelectionCount}</span>
                      {' '}candidat{finalSelectionCount > 1 ? 's' : ''} sera recalculé en combinant le matching avec{' '}
                      <span className="text-teal-300">{testsFile.name}</span>.
                    </>
                  ) : (
                    <>
                      Le classement de{' '}
                      <span className="text-white font-medium">{finalSelectionCount}</span>
                      {' '}candidat{finalSelectionCount > 1 ? 's' : ''} sera recalculé à partir du matching uniquement (sans scores de tests).
                    </>
                  )}
                </p>
                {(formatCompleted || formatWasCompleted.current) && (
                  <div className="flex items-start gap-2 text-sm text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2">
                    <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                    <span>Des CVs ont déjà été formatés — le nouveau classement peut les rendre incohérents.</span>
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setRelaunchStep('select')}
                    className="px-4 py-2 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white transition-colors"
                  >
                    Retour
                  </button>
                  <button
                    type="button"
                    onClick={() => runFinal({ isRelaunch: true })}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium transition-all"
                  >
                    <RefreshCw className="h-4 w-4" />
                    Confirmer le recalcul
                  </button>
                </div>
              </>
            )}
          </div>
        ) : finalReadOnly && finalSectionOpen ? (
          <div className="space-y-4">
            {finalFetchError && sortedFinal.length === 0 && (
              <div className="flex flex-col gap-2 text-sm text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2">
                <div className="flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                  <span>{finalFetchError}</span>
                </div>
                {finalCountdown > 0 && (
                  <p className="text-xs text-amber-200/80 pl-6">Nouvelle tentative dans {finalCountdown}s…</p>
                )}
                <button
                  type="button"
                  onClick={() => { setFinalCountdown(0); fetchFinal(); }}
                  className="self-start ml-6 text-xs font-medium text-amber-200 hover:text-white transition-colors underline"
                >
                  Réessayer
                </button>
              </div>
            )}
            <div className="flex items-center gap-2 text-emerald-300">
              <CheckCircle2 className="h-5 w-5" />
              <span className="text-sm">
                Scoring final calculé ({sortedFinal.length} candidat{sortedFinal.length > 1 ? 's' : ''})
                {sortedFinal.some(r => r.test_score == null) && sortedFinal.length > 0 && (
                  <span className="text-slate-500"> — certains scores test manquants</span>
                )}
              </span>
            </div>
            {sortedFinal.length > 0 && <div className="rounded-xl border border-white/10 overflow-hidden">
              <div className="grid grid-cols-[56px_1fr_90px_90px_90px_minmax(130px,1fr)] bg-white/[0.04] px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                <span>Rang</span><span>Candidat</span><span className="text-center">Global</span><span className="text-center">Test</span><span className="text-center">Final</span>
                {sid >= 5 && <span>Statut final</span>}
              </div>
              {sortedFinal.map(row => {
                const app = findAppearanceByName(row.candidate_name, row.rank);
                const finalCode = app?.final_status?.code || 'en_attente';
                const finalOptions = finalStatuses.map(s => ({ value: s.code, label: s.label_fr }));
                return (
                <div key={`${row.rank}-${row.candidate_name}`} className="grid items-center border-t border-white/[0.06] px-3 py-2.5 gap-2" style={{ gridTemplateColumns: sid >= 5 ? '56px 1fr 90px 90px 90px minmax(130px,1fr)' : '56px 1fr 90px 90px 90px' }}>
                  <span className="flex h-7 w-7 items-center justify-center rounded-md border border-cyan-400/30 bg-cyan-400/10 text-sm font-semibold text-cyan-300">{row.rank ?? '-'}</span>
                  <span className="text-sm font-medium text-white truncate pr-2 flex items-center gap-1.5 min-w-0">
                    <span className="truncate">{row.candidate_name}</span>
                    {app?.unreliability_flag && (
                      <UnreliabilityFlagIndicator
                        flag={app.unreliability_flag}
                        candidateId={app.candidate_id}
                        canResolve
                        onResolved={refreshAppearances}
                      />
                    )}
                  </span>
                  <span className={`text-center text-sm font-semibold ${scoreColor(row.overall_score)}`}>{pct(row.overall_score)}</span>
                  <span className={`text-center text-sm font-semibold ${scoreColor(row.test_score)}`}>{pct(row.test_score)}</span>
                  <span className={`text-center text-sm font-semibold ${scoreColor(row.final_score)}`}>{pct(row.final_score)}</span>
                  {sid >= 5 && app && finalOptions.length > 0 && (
                    <DarkSelect
                      value={finalCode}
                      onChange={v => updatePhaseStatus(app.id, 'final', v)}
                      options={finalOptions}
                      size="sm"
                      className="min-w-[130px]"
                    />
                  )}
                </div>
                );
              })}
            </div>}
          </div>
        ) : isRunningFinal ? (
          <div className="flex items-center gap-3"><Loader2 className="h-5 w-5 animate-spin text-cyan-400" /><span className="text-sm text-cyan-300">Calcul du scoring final…</span></div>
        ) : sid >= 5 && !finalDone ? (
          <p className="text-slate-500 text-sm">
            Le scoring final n&apos;a pas encore été généré par le sourceur.
          </p>
        ) : finalCtaActive ? (
          <div className="space-y-3">
            <p className="text-slate-400 text-sm">Générez le classement final. Vous pouvez joindre un fichier de scores de tests (optionnel).</p>
            <div className="flex items-start gap-2 text-sm text-teal-300 bg-teal-500/10 border border-teal-500/20 rounded-xl px-3 py-2.5">
              <span className="text-teal-400 font-medium flex-shrink-0">→</span>
              <span>
                <span className="font-medium">Étape suivante :</span> Générez le résultat final pour classer les candidats et débloquer le formatage des CVs.
              </span>
            </div>
            {finalError && <div className="flex items-center gap-2 text-sm text-red-300 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2"><AlertCircle className="h-4 w-4 flex-shrink-0" />{finalError}</div>}
            <div className="space-y-2">
              <input
                id={`tests-file-${jobId}`}
                type="file"
                accept=".csv,.xlsx,.xls,.txt"
                className="sr-only"
                onChange={e => setTestsFile(e.target.files?.[0] || null)}
              />
              <label
                htmlFor={`tests-file-${jobId}`}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border text-sm cursor-pointer transition-all w-fit border-white/10 text-slate-400 hover:border-white/20 hover:text-white"
              >
                <Upload className="h-4 w-4 shrink-0" />
                {testsFile ? testsFile.name : 'Joindre les scores de tests (optionnel)'}
              </label>
              {testsFile ? (
                <p className="text-xs text-emerald-400">
                  Fichier prêt — il sera envoyé lors du clic sur « Générer ».
                </p>
              ) : (
                <p className="text-xs text-slate-500">
                  Sans fichier, seuls les scores de matching seront utilisés (colonne Test : --).
                </p>
              )}
            </div>
            <button onClick={() => runFinal()}
              disabled={finalSelectionCount === 0}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium transition-all shadow-[0_4px_16px_rgba(31,157,148,0.3)] disabled:opacity-50 disabled:cursor-not-allowed">
              <Play className="h-4 w-4" />
              {finalSelectionCount === 0
                ? 'Sélectionnez au moins un candidat'
                : `Générer pour ${finalSelectionCount} candidat${finalSelectionCount > 1 ? 's' : ''} sélectionné${finalSelectionCount > 1 ? 's' : ''}`}
            </button>
          </div>
        ) : (
          <p className="text-slate-500 text-sm">Le scoring final sera disponible une fois le matching terminé.</p>
        )}
      </div>

      {/* â”€â”€ Formatage â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div className={`${card} ${formatLocked || isRunningFinal ? 'opacity-50 border-dashed' : ''}`}>
        <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          {formatLocked && <Lock className="h-4 w-4 text-slate-500" />}
          Formatage des CVs
        </h2>

        {formatLocked ? (
          <div className="space-y-2 text-sm text-slate-500">
            <p>Disponible après la génération du résultat final.</p>
            <p>Complétez l&apos;étape « Résultat final » pour débloquer le formatage.</p>
          </div>
        ) : isRunningFinal ? (
          <div className="space-y-2 text-sm text-slate-500">
            <p>Disponible après la mise à jour du résultat final.</p>
            <p>Le recalcul du scoring est en cours — le formatage sera débloqué une fois le nouveau classement prêt.</p>
            {formatWasCompleted.current && (
              <p>Les CVs précédemment formatés devront être régénérés.</p>
            )}
          </div>
        ) : showFormatCompleted ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-green-400"><CheckCircle2 className="h-5 w-5" /><span className="text-sm">Formatage terminé — CVs prêts au téléchargement.</span></div>
            <button onClick={downloadZip}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium transition-all shadow-[0_4px_16px_rgba(31,157,148,0.3)]">
              <Download className="h-4 w-4" /> Télécharger les CV formatés (ZIP)
            </button>
            {sid >= 6 && showFormatCompleted && formatStatuses.length > 0 && (
              formattedCandidateStems === null ? (
                <p className="text-xs text-slate-500 px-1">Chargement des candidats formatés…</p>
              ) : formattedFinalRows.length > 0 ? (
              <div className="rounded-xl border border-white/10 overflow-hidden divide-y divide-white/[0.06]">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 px-3 py-2 bg-white/[0.04]">Statut format / client</p>
                {formattedFinalRows.map(row => {
                  const app = findAppearanceByName(row.candidate_name, row.rank);
                  if (!app) return null;
                  const formatCode = app.format_status?.code || 'en_attente';
                  const formatOptions = formatStatuses.map(s => ({ value: s.code, label: s.label_fr }));
                  const showNonIntegreForm = nonIntegreDraft?.appearanceId === app.id;
                  return (
                    <div key={`fmt-${row.rank}-${row.candidate_name}`} className="px-3 py-3 space-y-2">
                      <div className="flex items-center gap-3 flex-wrap">
                        <span className="text-sm font-medium text-white flex-1 min-w-0 truncate flex items-center gap-1.5">
                          {row.candidate_name}
                          {app.unreliability_flag && (
                            <UnreliabilityFlagIndicator
                              flag={app.unreliability_flag}
                              candidateId={app.candidate_id}
                              canResolve
                              onResolved={refreshAppearances}
                            />
                          )}
                        </span>
                        <DarkSelect
                          value={showNonIntegreForm ? 'non_integre' : formatCode}
                          onChange={v => handleFormatStatusChange(app.id, v)}
                          options={formatOptions}
                          size="sm"
                          className="min-w-[160px]"
                        />
                      </div>
                      {showNonIntegreForm && (
                        <div className="space-y-2 pl-0 sm:pl-4">
                          <label className="text-xs text-slate-400 block">
                            Raison (visible aux autres recruteurs) *
                          </label>
                          <textarea
                            value={nonIntegreDraft.reason}
                            onChange={e => setNonIntegreDraft({ appearanceId: app.id, reason: e.target.value })}
                            rows={2}
                            className="w-full rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-[#1f9d94]/50 focus:outline-none resize-none"
                          />
                          <button
                            type="button"
                            onClick={saveNonIntegreFlag}
                            disabled={!nonIntegreDraft.reason.trim() || nonIntegreSaving}
                            className="px-4 py-1.5 rounded-lg bg-[#1f9d94] hover:bg-[#25afa5] text-white text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            {nonIntegreSaving ? 'Enregistrement…' : 'Enregistrer'}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              ) : null
            )}
            {!offerArchived && (
              <button
                type="button"
                onClick={() => { setFormatRunning(false); setFormatError(''); setStage('final_complete'); }}
                className="block text-xs text-slate-400 hover:text-white transition-colors"
              >
                Reformater avec un autre modèle
              </button>
            )}
          </div>
        ) : isRunningFormat ? (
          <div className="flex items-center gap-3"><Loader2 className="h-5 w-5 animate-spin text-cyan-400" /><span className="text-sm text-cyan-300">Formatage des CVs…</span></div>
        ) : showFormatActive ? (
          <div className="space-y-4">
            {formatOutdated && (
              <div className="flex items-start gap-2 text-sm text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2">
                <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                <span>Le classement final a été recalculé — relancez le formatage pour générer des CVs alignés sur le nouveau classement.</span>
              </div>
            )}
            <p className="text-slate-400 text-sm">Choisissez un modèle puis lancez le formatage des CVs des candidats.</p>
            {formatError && <div className="flex items-center gap-2 text-sm text-red-300 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2"><AlertCircle className="h-4 w-4 flex-shrink-0" />{formatError}</div>}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {TEMPLATES.map(t => (
                <button key={t.id} onClick={() => setTemplate(t.id)}
                  className={`flex flex-col items-start gap-1.5 p-3 rounded-xl border text-left transition-all ${template === t.id ? 'border-[#1f9d94]/60 bg-[#1f9d94]/10 text-white' : 'border-white/10 bg-white/[0.02] text-slate-400 hover:border-white/20 hover:text-white'}`}>
                  <div className="flex items-center gap-2"><FileText className="h-4 w-4" /><span className="text-sm font-semibold">{t.name}</span></div>
                  <span className="text-xs text-slate-500">{t.description}</span>
                </button>
              ))}
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <button onClick={() => setLimitMode('all')} className={`px-3 py-1.5 rounded-xl text-sm font-medium transition-all ${limitMode === 'all' ? 'bg-[#1f9d94] text-white' : 'border border-white/10 text-slate-400 hover:text-white'}`}>Tous</button>
              <button onClick={() => setLimitMode('number')} className={`px-3 py-1.5 rounded-xl text-sm font-medium transition-all ${limitMode === 'number' ? 'bg-[#1f9d94] text-white' : 'border border-white/10 text-slate-400 hover:text-white'}`}>Top N</button>
              <button onClick={() => setLimitMode('manual')} className={`px-3 py-1.5 rounded-xl text-sm font-medium transition-all ${limitMode === 'manual' ? 'bg-[#1f9d94] text-white' : 'border border-white/10 text-slate-400 hover:text-white'}`}>Sélection manuelle</button>
              {limitMode === 'number' && (
                <input type="number" min={1} max={sortedFinal.length || undefined} value={limitNumber}
                  onChange={e => setLimitNumber(Math.min(sortedFinal.length || Infinity, Math.max(1, parseInt(e.target.value) || 1)))}
                  className="h-9 w-20 rounded-xl border border-white/10 bg-white/[0.02] px-3 text-sm text-white focus:border-[#1f9d94]/50 focus:outline-none" />
              )}
              {limitMode === 'number' && sortedFinal.length > 0 && (
                <span className="text-xs text-slate-500">sur {sortedFinal.length} candidat{sortedFinal.length > 1 ? 's' : ''}</span>
              )}
            </div>

            {limitMode === 'manual' && (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs text-slate-400">Cliquez pour sélectionner les candidats à formater.</p>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${selectedCandidates.length >= MAX_SELECT ? 'text-amber-300 bg-amber-400/10' : 'text-slate-400 bg-white/[0.05]'}`}>
                    {selectedCandidates.length}/{MAX_SELECT} candidats sélectionnés
                  </span>
                </div>
                {sortedFinal.length === 0 ? (
                  <p className="text-slate-500 text-sm">Aucun candidat final disponible.</p>
                ) : (
                  <div className="rounded-xl border border-white/10 overflow-hidden divide-y divide-white/[0.06] max-h-72 overflow-y-auto">
                    {sortedFinal.map(row => {
                      const name = row.candidate_name;
                      const checked = selectedCandidates.includes(name);
                      const atLimit = !checked && selectedCandidates.length >= MAX_SELECT;
                      return (
                        <button key={`${row.rank}-${name}`} type="button" onClick={() => toggleCandidate(name)} disabled={atLimit}
                          className={`w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors ${checked ? 'bg-[#1f9d94]/10' : atLimit ? 'opacity-40 cursor-not-allowed' : 'hover:bg-white/[0.03]'}`}>
                          <span className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md border ${checked ? 'border-[#1f9d94] bg-[#1f9d94] text-white' : 'border-white/20'}`}>
                            {checked && <CheckCircle2 className="h-4 w-4" />}
                          </span>
                          <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md border border-cyan-400/30 bg-cyan-400/10 text-xs font-semibold text-cyan-300">{row.rank ?? '-'}</span>
                          <span className="flex-1 min-w-0 text-sm font-medium text-white truncate">{name}</span>
                          <span className={`text-sm font-semibold ${scoreColor(row.final_score)}`}>{pct(row.final_score)}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            <div className="flex flex-wrap gap-2 pt-1">
              {formatWasCompleted.current && (
                <button
                  type="button"
                  onClick={cancelReformat}
                  className="px-5 py-2.5 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white hover:border-white/20 transition-all"
                >
                  Annuler
                </button>
              )}
              <button
                type="button"
                onClick={runFormat}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium transition-all shadow-[0_4px_16px_rgba(31,157,148,0.3)]"
              >
                <FileText className="h-4 w-4" /> Lancer le formatage
              </button>
            </div>
          </div>
        ) : offerArchived ? (
          <p className="text-slate-500 text-sm">Offre archivée — le formatage n&apos;est plus disponible.</p>
        ) : null}
      </div>

      <CandidateOfferHistorySheet
        open={historyCandidate !== null}
        onClose={() => setHistoryCandidate(null)}
        candidateId={historyCandidate?.id || ''}
        candidateName={historyCandidate?.name || ''}
        excludeOfferId={offerId}
      />
    </div>
  );
}

