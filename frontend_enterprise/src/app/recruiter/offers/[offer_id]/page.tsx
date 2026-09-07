'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { useParams, useRouter } from 'next/navigation';
import {
  AlertCircle, ArrowLeft, Loader2,
  Briefcase, Clock, MapPin, Star, Users,
} from 'lucide-react';
import RecruiterPipelinePanel from './RecruiterPipelinePanel';
import { ArchiveOfferModal, DeleteOfferModal } from '../OfferActionModals';
import { SkillBadge } from '@/components/SkillBadge';
import { type StructuredSkill } from '@/lib/skillUtils';

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
  created_at: string; assigned_to: string | null;
  assigned_sourcer: { full_name: string; email: string } | null;
  job: { id: string; status: string; stage: string; cv_count: number; created_at: string } | null;
}
interface Sourcer { id: string; full_name: string; email: string; active_offers_count: number; }

function SourcerCardPicker({
  sourcers, selected, onSelect, excludeEmail,
}: {
  sourcers: Sourcer[];
  selected: string;
  onSelect: (id: string) => void;
  excludeEmail?: string;
}) {
  const list = excludeEmail ? sourcers.filter(s => s.email !== excludeEmail) : sourcers;
  return (
    <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
      {list.map(s => {
        const initials = s.full_name.split(' ').slice(0, 2).map((w: string) => w[0]?.toUpperCase() ?? '').join('');
        const sel = selected === s.id;
        return (
          <button type="button" key={s.id} onClick={() => onSelect(sel ? '' : s.id)}
            className={`flex flex-col items-start gap-1.5 p-3 rounded-xl border text-left transition-all duration-150 ${
              sel
                ? 'border-[#1f9d94]/60 bg-[#1f9d94]/10 text-white'
                : 'border-white/10 bg-white/[0.02] text-slate-400 hover:border-white/20 hover:text-white'
            }`}>
            <div className="flex items-center gap-2 w-full min-w-0">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] font-bold ${sel ? 'bg-[#1f9d94]/30 text-[#1f9d94]' : 'bg-white/10 text-slate-400'}`}>
                {initials}
              </div>
              <span className="text-xs font-medium truncate leading-tight">{s.full_name}</span>
            </div>
            {s.active_offers_count > 0 ? (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full leading-tight ${sel ? 'bg-[#1f9d94]/20 text-[#1f9d94]' : 'bg-white/[0.07] text-slate-500'}`}>
                {s.active_offers_count} offre{s.active_offers_count > 1 ? 's' : ''} en cours
              </span>
            ) : (
              <span className="text-[10px] text-slate-600 leading-tight">Disponible</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// Badge driven by the authoritative status_id (ref.offer_statuses), with the
// French label_fr surfaced via status_label. Falls back to legacy text.
function StatusBadge({ offer }: { offer: OfferDetail }) {
  const colorById: Record<number, string> = {
    1: 'text-slate-300 bg-white/10',
    2: 'text-indigo-400 bg-indigo-400/10',
    3: 'text-teal-400 bg-teal-400/10',
    4: 'text-green-400 bg-green-400/10',
    5: 'text-cyan-300 bg-cyan-400/10',
    6: 'text-emerald-300 bg-emerald-400/10',
    7: 'text-amber-400 bg-amber-400/10',
  };
  const legacyLabels: Record<string, string> = { open: 'Ouverte', in_progress: 'En cours', closed: 'Clôturée', archived: 'Archivée' };
  const cls = (offer.status_id && colorById[offer.status_id]) || 'text-slate-400 bg-white/5';
  const label = offer.status_label || legacyLabels[offer.status] || offer.status;
  return <span className={`text-sm font-medium px-3 py-1 rounded-full ${cls}`}>{label}</span>;
}

function relDate(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `il y a ${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `il y a ${hrs} h`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return 'hier';
  return new Date(iso).toLocaleDateString('fr-FR');
}

export default function OfferDetailPage() {
  const { offer_id } = useParams<{ offer_id: string }>();
  const router = useRouter();
  const [offer, setOffer] = useState<OfferDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [sourcers, setSourcers] = useState<Sourcer[]>([]);
  const [selectedSourcer, setSelectedSourcer] = useState('');
  const [assigning, setAssigning] = useState(false);
  const [error, setError] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [archiving, setArchiving] = useState(false);

  // `silent` refreshes (triggered by the pipeline panel after a stage advances)
  // must NOT flip `loading` back to true: doing so unmounts RecruiterPipelinePanel
  // (which lives behind the `if (loading)` guard), resetting its internal fetch
  // guards and causing an infinite refetch/remount loop. Only the initial load
  // and explicit user actions toggle the full-page spinner.
  const fetchOffer = (silent = false) => {
    if (!silent) setLoading(true);
    fetch(`${API_BASE}/offers/${offer_id}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(d => { setOffer(d); if (!silent) setLoading(false); })
      .catch(() => { if (!silent) { setError('Offre introuvable ou accès refusé.'); setLoading(false); } });
  };

  useEffect(() => { fetchOffer(); }, [offer_id]);

  useEffect(() => {
    fetch(`${API_BASE}/users/sourcers`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setSourcers(d.sourcers || []));
  }, []);

  async function handleAssign() {
    if (!selectedSourcer) return;
    setAssigning(true);
    try {
      const res = await fetch(`${API_BASE}/offers/${offer_id}/assign`, {
        method: 'PATCH', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sourcer_id: selectedSourcer }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail);
      fetchOffer();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setAssigning(false); }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      const res = await fetch(`${API_BASE}/offers/${offer_id}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Erreur lors de la suppression');
      router.push('/recruiter/offers');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur lors de la suppression');
      setShowDeleteConfirm(false);
    } finally {
      setDeleting(false);
    }
  }

  async function handleArchive() {
    setArchiving(true);
    try {
      const res = await fetch(`${API_BASE}/offers/${offer_id}/status`, {
        method: 'PATCH', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'archived' }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail);
      setShowArchiveConfirm(false);
      fetchOffer(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Impossible d\'archiver l\'offre.');
      setShowArchiveConfirm(false);
    } finally {
      setArchiving(false);
    }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-indigo-400" /></div>;
  if (!offer) return (
    <div className="space-y-4">
      <button onClick={() => router.push('/recruiter/offers')} className="flex items-center gap-2 text-slate-400 hover:text-white text-sm"><ArrowLeft className="h-4 w-4" />Retour</button>
      <p className="text-red-400">{error || 'Offre introuvable.'}</p>
    </div>
  );

  const section = "rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-4";
  // Reassignment is only allowed before the sourcer launches the pipeline
  // (status_id 1 Ouverte / 2 Assignée). From status_id 3 (En cours) onward it is locked.
  const reassignLocked = (offer.status_id ?? 0) >= 3;

  return (
    <div className="w-full max-w-5xl space-y-6">
      {/* Back */}
      <button onClick={() => router.push('/recruiter/offers')}
        className="flex items-center gap-2 text-slate-400 hover:text-white text-sm transition-colors">
        <ArrowLeft className="h-4 w-4" /> Mes Offres
      </button>

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <h1 className="text-2xl font-bold">{offer.title}</h1>
          <StatusBadge offer={offer} />
        </div>
        <p className="text-slate-400 text-sm">Créée {relDate(offer.created_at)}</p>
      </motion.div>

      {error && <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3"><AlertCircle className="h-4 w-4 flex-shrink-0" />{error}</div>}

      {/* Description + details */}
      <div className="grid sm:grid-cols-2 gap-4">
        <div className={section}>
          <h2 className="text-sm font-semibold text-slate-300">Description</h2>
          <p className="text-slate-400 text-sm leading-relaxed">{offer.description || 'Aucune description disponible.'}</p>
        </div>
        <div className={section}>
          <h2 className="text-sm font-semibold text-slate-300">Détails</h2>
          <dl className="space-y-2 text-sm">
            {offer.experience_level && <div className="flex items-center gap-2 text-slate-400"><Star className="h-3.5 w-3.5" />{offer.experience_level}</div>}
            {offer.contract_type && <div className="flex items-center gap-2 text-slate-400"><Briefcase className="h-3.5 w-3.5" />{offer.contract_type.label_fr || offer.contract_type.code}</div>}
            {offer.experience_range?.display && <div className="flex items-center gap-2 text-slate-400"><Clock className="h-3.5 w-3.5" />{offer.experience_range.display}</div>}
            {offer.location && <div className="flex items-center gap-2 text-slate-400"><MapPin className="h-3.5 w-3.5" />{offer.location}</div>}
            {offer.salary_range && <div className="flex items-center gap-2 text-slate-400"><span className="text-xs">€</span>{offer.salary_range}</div>}
            {!offer.experience_level && !offer.contract_type && !offer.experience_range?.display && !offer.location && !offer.salary_range && <p className="text-slate-500 text-xs">Aucun détail spécifié</p>}
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

      {/* Assignation */}
      <div className={section}>
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-slate-400" />
          <h2 className="text-sm font-semibold text-slate-300">Assignation</h2>
        </div>
        {offer.assigned_sourcer ? (
          <div className="space-y-3">
            <p className="text-sm text-white">Assignée à <span className="text-teal-400 font-medium">{offer.assigned_sourcer.full_name}</span></p>
            {reassignLocked ? (
              <div className="flex items-start gap-2 text-sm text-slate-400 bg-white/[0.03] border border-white/10 rounded-xl px-4 py-3">
                <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5 text-amber-400" />
                <span>Le pipeline a déjà été lancé par le sourceur : la réassignation n&apos;est plus possible.</span>
              </div>
            ) : (
              <div className="space-y-3">
                <SourcerCardPicker
                  sourcers={sourcers}
                  selected={selectedSourcer}
                  onSelect={setSelectedSourcer}
                  excludeEmail={offer.assigned_sourcer?.email}
                />
                {selectedSourcer && (
                  <button onClick={handleAssign} disabled={assigning}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm disabled:opacity-50 transition-all">
                    {assigning ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Réassigner'}
                  </button>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-slate-400">Non assignée — sélectionnez un sourceur :</p>
            <SourcerCardPicker
              sourcers={sourcers}
              selected={selectedSourcer}
              onSelect={setSelectedSourcer}
            />
            {selectedSourcer && (
              <button onClick={handleAssign} disabled={assigning}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm disabled:opacity-50 transition-all">
                {assigning ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Assigner'}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Pipeline — matching results, final scoring & formatting, all in-space */}
      <RecruiterPipelinePanel
        offerId={offer_id}
        job={offer.job}
        statusId={offer.status_id}
        onStageAdvance={() => fetchOffer(true)}
        sourcerName={offer.assigned_sourcer?.full_name}
      />

      {/* Actions */}
      <div className="flex gap-3 flex-wrap">
        {offer.status_id !== 7 && offer.status !== 'archived' && (
          <button onClick={() => setShowArchiveConfirm(true)}
            className="px-4 py-2.5 rounded-xl border border-[#1f9d94]/30 text-[#1f9d94] text-sm hover:bg-[#1f9d94]/10 transition-all">
            Archiver
          </button>
        )}
        <button onClick={() => setShowDeleteConfirm(true)}
          className="px-4 py-2.5 rounded-xl border border-red-500/20 text-red-400 text-sm hover:bg-red-500/10 transition-all">
          Supprimer l&apos;offre
        </button>
      </div>

      {showDeleteConfirm && (
        <DeleteOfferModal
          title={offer.title}
          onCancel={() => setShowDeleteConfirm(false)}
          onConfirm={handleDelete}
          loading={deleting}
        />
      )}
      {showArchiveConfirm && (
        <ArchiveOfferModal
          title={offer.title}
          onCancel={() => setShowArchiveConfirm(false)}
          onConfirm={handleArchive}
          loading={archiving}
        />
      )}
    </div>
  );
}

