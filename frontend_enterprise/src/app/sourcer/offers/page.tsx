'use client';

import React, { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation'; // kept for potential future use
import { statusIdFromCode } from '@/lib/offerStatusRoutes';
import {
  AlertCircle, CheckCircle2, Clock, Loader2,
  Play, RefreshCw, XCircle,
} from 'lucide-react';
import { PipelineMatchCountBadge } from '@/components/PipelineMatchCountBadge';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

// Fix 1 (Action 223): exactly 4 tabs keyed off the authoritative status_id.
// A sourcer never sees status_id=1 (open) — offers are filtered server-side to
// those assigned to them (status_id 2-4), so there is no "Ouverte" tab.
const TABS = [
  { label: 'Toutes',   statusId: null },
  { label: 'Assignée', statusId: 2 },
  { label: 'En cours', statusId: 3 },
  { label: 'Matchée',  statusId: 4 },
] as const;

// French labels sourced from ref.offer_statuses.label_fr (ids 2-4).
const STATUS_LABEL: Record<number, string> = { 2: 'Assignée', 3: 'En cours', 4: 'Matchée' };

interface Job {
  id: string; status: string; stage: string;
  cv_count?: number; matched_count?: number | null;
  error_message?: string | null;
}
interface Offer {
  id: string; title: string; description: string;
  experience_level: string | null;
  contract_type: { id: number; code: string; label_fr: string } | null;
  experience_range: { id: number; min_years: number | null; max_years: number | null; display: string | null } | null;
  status: string;
  status_id: number | null; status_code: string | null; status_label: string | null;
  session_id: string | null; offer_sftp_path: string | null;
  updated_at: string; job: Job | null;
}
interface JobProgress {
  status?: string;
  stage?: string;
  extraction?: number;
  matching?: number;
  final?: number;
  format?: number;
  progress?: Record<string, number>;
}

// Card action/badge state. Tabs use the raw status_id; this only refines how a
// card renders (a failed linked job is surfaced even though the offer stays at
// status_id=3 = in_progress).
type CardState = 'assigned' | 'running' | 'failed' | 'matched';
function cardState(offer: Offer): CardState {
  if (offer.job?.status === 'failed') return 'failed';
  if (offer.status_id === 4) return 'matched';
  if (offer.status_id === 3) return 'running';
  return 'assigned'; // status_id === 2
}

function StatusBadge({ offer }: { offer: Offer }) {
  const state = cardState(offer);
  if (state === 'failed')   return <span className="text-[10px] font-semibold uppercase tracking-wide text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full whitespace-nowrap">Échouée</span>;
  if (state === 'matched')  return <span className="text-[10px] font-semibold uppercase tracking-wide text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full flex items-center gap-1 whitespace-nowrap"><CheckCircle2 className="h-2.5 w-2.5" />{STATUS_LABEL[4]}</span>;
  if (state === 'running')  return <span className="text-[10px] font-semibold uppercase tracking-wide text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded-full flex items-center gap-1 whitespace-nowrap"><Loader2 className="h-2.5 w-2.5 animate-spin" />{STATUS_LABEL[3]}</span>;
  return <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded-full whitespace-nowrap">{STATUS_LABEL[2]}</span>;
}

/** Mini progress bar for running jobs. Polls /jobs/{id}/progress every 5s. */
function InlineProgress({ jobId }: { jobId: string }) {
  const [prog, setProg] = useState<JobProgress | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = () => {
      fetch(`${API_BASE}/jobs/${jobId}/progress`, { credentials: 'include' })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d) setProg(d); })
        .catch(() => null);
    };
    poll();
    timerRef.current = setInterval(poll, 5000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [jobId]);

  const STAGES: Record<string, string> = {
    preparing_inputs: 'Préparation', running_pipeline: 'Pipeline IA',
    running_final: 'Résultats finaux', running_format: 'Formatage',
    matching_complete: 'Matching terminé', final_complete: 'Finalisation',
  };
  const stageFr = prog?.stage ? (STAGES[prog.stage] || prog.stage) : 'En cours…';
  const phaseProgress = prog?.progress ?? {
    extraction: prog?.extraction ?? 0,
    matching: prog?.matching ?? 0,
    final: prog?.final ?? 0,
    format: prog?.format ?? 0,
  };
  const pct = Math.round(
    Object.values(phaseProgress).reduce((a, b) => a + b, 0) / Math.max(Object.keys(phaseProgress).length, 1),
  );

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs text-slate-400">
        <span>{stageFr}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-1 bg-white/10 rounded-full overflow-hidden">
        <div className="h-full bg-[#1f9d94] rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function SourcerOffersContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeStatusId, setActiveStatusId] = useState<number | null>(null);
  const [showFailedOnly, setShowFailedOnly] = useState(false);
  const [launching, setLaunching] = useState<string | null>(null);
  const [error, setError] = useState('');

  const fetchOffers = useCallback((silent = false) => {
    if (!silent) setLoading(true);
    fetch(`${API_BASE}/my-offers`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(d => { setOffers(d.offers || []); setLoading(false); })
      .catch(() => { if (!silent) setError('Impossible de charger les offres.'); setLoading(false); });
  }, []);

  useEffect(() => { fetchOffers(); }, [fetchOffers]);

  useEffect(() => {
    const code = searchParams.get('status');
    if (!code) {
      setShowFailedOnly(false);
      return;
    }
    if (code === 'failed') {
      setShowFailedOnly(true);
      setActiveStatusId(null);
      return;
    }
    setShowFailedOnly(false);
    const id = statusIdFromCode(code);
    if (id !== null) setActiveStatusId(id);
  }, [searchParams]);

  // Fix 6: auto-refresh so status_id transitions (in_progress → matched) surface
  // in the tabs without a manual reload.
  useEffect(() => {
    const t = setInterval(() => fetchOffers(true), 8000);
    return () => clearInterval(t);
  }, [fetchOffers]);

  async function launchOffer(offer: Offer) {
    if (launching === offer.id) return;
    if (!offer.offer_sftp_path) {
      setError(`L'offre "${offer.title}" n'a pas de fichier associé et ne peut pas être relancée.`);
      return;
    }
    setLaunching(offer.id);
    setError('');
    try {
      const fd = new FormData();
      fd.append('offer_sftp_path', offer.offer_sftp_path);
      if (offer.session_id) fd.append('preset_session_id', offer.session_id);
      fd.append('linked_offer_id', offer.id);
      fd.append('offer_only', 'true');
      const res = await fetch(`${API_BASE}/jobs`, { method: 'POST', credentials: 'include', body: fd });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Erreur ${res.status}`);
      // Stay in the sourcer space — InlineProgress shows progress directly on the card.
      // Launch sets the offer to status_id=3, so jump to the "En cours" tab.
      setShowFailedOnly(false);
      setActiveStatusId(3);
      setTimeout(() => fetchOffers(), 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors du lancement');
    } finally {
      setLaunching(null);
    }
  }

  const filtered = showFailedOnly
    ? offers.filter(o => o.job?.status === 'failed')
    : activeStatusId === null
      ? offers
      : offers.filter(o => o.status_id === activeStatusId);

  return (
    <div className="w-full max-w-7xl space-y-6">
      {/* Header */}
      <div className="admin-light-card rounded-xl p-5 sm:p-6 flex items-center justify-between flex-wrap gap-4">
        <div>
          <p className="text-xs font-semibold uppercase text-[#2f66ed]">Espace sourcing</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">Mes offres assignées</h1>
          <p className="mt-1 text-sm text-slate-400">Gérez les offres, lancez les pipelines et suivez les résultats.</p>
        </div>
        <button onClick={() => fetchOffers()} className="flex items-center gap-2 rounded-lg border border-[#d8e0ea] bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition-all hover:border-[#2f66ed]/40 hover:text-[#2f66ed]">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Actualiser
        </button>
      </div>

      {error && <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm"><AlertCircle className="h-4 w-4 flex-shrink-0" />{error}</div>}

      {/* Tabs */}
      <div className="admin-light-card flex gap-1 overflow-x-auto rounded-lg p-1">
        {TABS.map(tab => {
          const count = tab.statusId === null ? offers.length : offers.filter(o => o.status_id === tab.statusId).length;
          const active = activeStatusId === tab.statusId;
          return (
            <button key={tab.label} onClick={() => { setShowFailedOnly(false); setActiveStatusId(tab.statusId); }}
              className={`rounded-md px-4 py-2.5 text-sm font-semibold whitespace-nowrap transition-all ${active ? 'bg-[#2f66ed] text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'}`}>
              {tab.label}
              {count > 0 && <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${active ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500'}`}>{count}</span>}
            </button>
          );
        })}
      </div>

      {loading && <div className="flex justify-center h-32"><Loader2 className="h-8 w-8 animate-spin text-[#1f9d94] mt-10" /></div>}

      {!loading && filtered.length === 0 && (
        <div className="admin-light-card flex h-48 flex-col items-center justify-center rounded-xl text-slate-500">
          <Clock className="h-10 w-10 mb-3 opacity-40" />
          <p className="font-medium">Aucune offre dans cette catégorie</p>
        </div>
      )}

      {/* Offer cards */}
      <div className="p-2 space-y-4 px-2">
        {filtered.map((offer, i) => {
          const state = cardState(offer);
          return (
            <Link key={offer.id} href={`/sourcer/offers/${offer.id}`}>
              <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
                className="mx-2 cursor-pointer space-y-4 rounded-lg border border-[#d8e0ea] border-l-4 border-l-[#1f9d94] bg-white p-5 shadow-sm transition-all duration-300 hover:border-[#2f66ed]/40 hover:shadow-md">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 className="text-lg font-semibold">{offer.title}</h2>
                      <StatusBadge offer={offer} />
                      {offer.experience_level && <span className="text-xs text-slate-400 bg-white/5 px-2 py-0.5 rounded-full">{offer.experience_level}</span>}
                      {offer.contract_type && <span className="text-xs text-slate-400 bg-white/5 px-2 py-0.5 rounded-full">{offer.contract_type.label_fr || offer.contract_type.code}</span>}
                      {offer.experience_range?.display && <span className="text-xs text-slate-400 bg-white/5 px-2 py-0.5 rounded-full">{offer.experience_range.display}</span>}
                    </div>
                    <p className="text-slate-400 text-sm mt-1 line-clamp-2">{offer.description}</p>
                    <p className="text-xs text-slate-500 mt-1">Assignée le {new Date(offer.updated_at).toLocaleDateString('fr-FR')}</p>
                  </div>
                </div>

                {state === 'running' && offer.job && <InlineProgress jobId={offer.job.id} />}

                <div className="flex gap-3 flex-wrap" onClick={e => e.preventDefault()}>
                  {state === 'assigned' && offer.offer_sftp_path && (
                    <button onClick={() => launchOffer(offer)} disabled={launching === offer.id}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium transition-all disabled:opacity-60 disabled:cursor-not-allowed shadow-[0_4px_16px_rgba(31,157,148,0.3)]">
                      {launching === offer.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                      {launching === offer.id ? 'Lancement…' : 'Lancer l\'offre'}
                    </button>
                  )}
                  {state === 'running' && offer.job && (
                    <Link href={`/sourcer/offers/${offer.id}`} onClick={e => e.stopPropagation()}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl border border-blue-500/20 text-blue-400 text-sm hover:bg-blue-500/10 transition-all">
                      <Loader2 className="h-4 w-4 animate-spin" /> Voir la progression
                    </Link>
                  )}
                  {state === 'matched' && (
                    <div className="flex items-center gap-3 flex-wrap">
                      {offer.job && <PipelineMatchCountBadge job={offer.job} />}
                      <Link href={`/sourcer/offers/${offer.id}`} onClick={e => e.stopPropagation()}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-green-500/10 border border-green-500/20 text-green-400 text-sm hover:bg-green-500/20 transition-all">
                        <CheckCircle2 className="h-4 w-4" /> Voir les résultats
                      </Link>
                      {offer.offer_sftp_path && (
                        <button onClick={() => launchOffer(offer)} disabled={launching === offer.id}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-500/20 text-slate-400 text-xs hover:text-white hover:border-white/20 transition-all disabled:opacity-50">
                          <RefreshCw className={`h-3.5 w-3.5 ${launching === offer.id ? 'animate-spin' : ''}`} />
                          {launching === offer.id ? 'Relance en cours…' : 'Relancer le matching'}
                        </button>
                      )}
                    </div>
                  )}
                  {state === 'failed' && (
                    <div className="flex items-center gap-3">
                      <span className="flex items-center gap-1.5 text-xs text-red-400 bg-red-400/10 px-2.5 py-1 rounded-full">
                        <XCircle className="h-3.5 w-3.5" /> Échec du pipeline
                      </span>
                      {offer.offer_sftp_path && (
                        <button onClick={() => launchOffer(offer)} disabled={launching === offer.id}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-500/20 text-slate-400 text-xs hover:text-white hover:border-white/20 transition-all disabled:opacity-50">
                          <RefreshCw className={`h-3.5 w-3.5 ${launching === offer.id ? 'animate-spin' : ''}`} />
                          {launching === offer.id ? 'Relance en cours…' : 'Relancer'}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </motion.div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export default function SourcerOffersPage() {
  return <Suspense fallback={null}><SourcerOffersContent /></Suspense>;
}

