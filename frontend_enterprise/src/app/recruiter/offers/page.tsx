'use client';

import React, { Suspense, useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { statusCodeFromId, statusIdFromCode } from '@/lib/offerStatusRoutes';
import { AlertCircle, CheckCircle2, Loader2, Plus, RefreshCw, UserCheck, X, XCircle } from 'lucide-react';
import { ArchiveOfferModal, DeleteOfferModal } from './OfferActionModals';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

// Tabs keyed off the authoritative status_id (ref.offer_statuses) — the legacy
// text `status` is intentionally NOT used here (it collapses 2..6 → "in_progress").
const RECRUITER_TABS = [
  { label: 'Toutes',         status_id: null },
  { label: 'Non assignée',   status_id: 1 },
  { label: 'Assignée',       status_id: 2 },
  { label: 'En cours',       status_id: 3 },
  { label: 'Matchée',        status_id: 4 },
  { label: 'Résultat final', status_id: 5 },
  { label: 'Formatée',       status_id: 6 },
  { label: 'Archivée',       status_id: 7 },
] as const;

interface Job { id: string; status: string; stage: string; }
interface Offer {
  id: string; title: string; description: string;
  experience_level: string | null;
  contract_type: { id: number; code: string; label_fr: string } | null;
  experience_range: { id: number; min_years: number | null; max_years: number | null; display: string | null } | null;
  status: string; status_id: number; status_label: string; status_code: string;
  assigned_to: string | null; session_id: string | null;
  created_at: string; updated_at: string; job: Job | null;
}
interface Sourcer { id: string; full_name: string; email: string; active_offers_count: number; }

// Badge driven by status_id + status_label. A failed linked job adds a red
// "Échoué" overlay but does NOT change the offer's status_id tab.
function StatusBadge({ offer }: { offer: Offer }) {
  const colorById: Record<number, string> = {
    1: 'text-amber-400 bg-amber-400/10',
    2: 'text-slate-300 bg-white/10',
    3: 'text-blue-400 bg-blue-400/10',
    4: 'text-teal-400 bg-teal-400/10',
    5: 'text-purple-400 bg-purple-400/10',
    6: 'text-green-400 bg-green-400/10',
    7: 'text-yellow-400 bg-yellow-400/10',
  };
  const cls = colorById[offer.status_id] || 'text-slate-400 bg-white/5';
  const failed = offer.job?.status === 'failed';
  return (
    <span className="flex items-center gap-1.5">
      <span className={`font-semibold uppercase tracking-wide text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap ${cls}`}>{offer.status_label || offer.status}</span>
      {failed && (
        <span className="font-semibold uppercase tracking-wide text-[10px] text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full flex items-center gap-1 whitespace-nowrap">
          <XCircle className="h-3 w-3" />Échoué
        </span>
      )}
    </span>
  );
}

function SourcerCardPicker({
  sourcers, selected, onSelect,
}: {
  sourcers: Sourcer[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2 max-h-56 overflow-y-auto pr-1">
      {sourcers.map(s => {
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

function AssignModal({ offer, onClose, onAssigned }: { offer: Offer; onClose: () => void; onAssigned: () => void; }) {
  const [sourcers, setSourcers] = useState<Sourcer[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [assigning, setAssigning] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch(`${API_BASE}/users/sourcers`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => setSourcers(d.sourcers || []))
      .catch(() => setError('Impossible de charger les sourceurs.'));
  }, []);

  async function handleAssign() {
    if (!selectedId) return;
    setAssigning(true);
    try {
      const res = await fetch(`${API_BASE}/offers/${offer.id}/assign`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sourcer_id: selectedId }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || `Erreur ${res.status}`);
      onAssigned();
      onClose();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setAssigning(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
        className="relative w-full max-w-lg rounded-2xl border border-white/15 bg-[#0d1528] p-6 space-y-5 shadow-2xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Assigner l&apos;offre</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white"><X className="h-5 w-5" /></button>
        </div>
        <p className="text-sm text-slate-400">Offre : <span className="text-white font-medium">{offer.title}</span></p>
        {error && <p className="text-sm text-red-400">{error}</p>}
        {sourcers.length === 0 && !error && <div className="flex justify-center py-4"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>}
        {sourcers.length > 0 && (
          <SourcerCardPicker sourcers={sourcers} selected={selectedId} onSelect={setSelectedId} />
        )}
        <div className="flex gap-3">
          <button onClick={onClose} className="flex-1 px-4 py-2 rounded-xl border border-white/10 text-slate-400 text-sm hover:text-white hover:border-white/20 transition-all">Annuler</button>
          <button onClick={handleAssign} disabled={!selectedId || assigning}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed">
            {assigning ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserCheck className="h-4 w-4" />}
            {assigning ? 'Assignation…' : 'Assigner'}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

function RecruiterOffersContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [assignTarget, setAssignTarget] = useState<Offer | null>(null);
  const [error, setError] = useState('');
  const [activeStatusId, setActiveStatusId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Offer | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<Offer | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [sourcerNames, setSourcerNames] = useState<Record<string, string>>({});

  const fetchOffers = () => {
    setLoading(true);
    Promise.all([
      fetch(`${API_BASE}/offers`, { credentials: 'include' }).then(r => r.ok ? r.json() : Promise.reject()),
      fetch(`${API_BASE}/users/sourcers`, { credentials: 'include' }).then(r => r.ok ? r.json() : { sourcers: [] }),
    ])
      .then(([offersData, sourcersData]) => {
        setOffers(offersData.offers || []);
        const names: Record<string, string> = {};
        for (const s of sourcersData.sourcers || []) {
          names[s.id] = s.full_name;
        }
        setSourcerNames(names);
        setLoading(false);
      })
      .catch(() => { setError('Impossible de charger les offres.'); setLoading(false); });
  };

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      const res = await fetch(`${API_BASE}/offers/${deleteTarget.id}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Erreur lors de la suppression');
      setOffers(prev => prev.filter(o => o.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch {
      setError('Impossible de supprimer l\'offre.');
      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  }

  const selectTab = useCallback((statusId: number | null) => {
    setActiveStatusId(statusId);
    const code = statusCodeFromId(statusId);
    const path = code ? `/recruiter/offers?status=${encodeURIComponent(code)}` : '/recruiter/offers';
    router.replace(path, { scroll: false });
  }, [router]);

  async function handleArchive() {
    if (!archiveTarget) return;
    setArchiving(true);
    try {
      const res = await fetch(`${API_BASE}/offers/${archiveTarget.id}/status`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'archived' }),
      });
      if (!res.ok) throw new Error('Erreur lors de l\'archivage');
      const updated = await res.json();
      setOffers(prev => prev.map(o => o.id === archiveTarget.id ? { ...o, ...updated, status_id: 7, status_label: 'Archivée', status: 'archived' } : o));
      setArchiveTarget(null);
      selectTab(7);
    } catch {
      setError('Impossible d\'archiver l\'offre.');
      setArchiveTarget(null);
    } finally {
      setArchiving(false);
    }
  }

  useEffect(() => { fetchOffers(); }, []);

  useEffect(() => {
    const code = searchParams.get('status');
    if (!code) return;
    const id = statusIdFromCode(code);
    if (id !== null) setActiveStatusId(id);
  }, [searchParams]);

  const filtered = activeStatusId === null ? offers : offers.filter(o => o.status_id === activeStatusId);

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-indigo-400" /></div>;

  return (
    <div className="w-full max-w-7xl space-y-6">
      <div className="mb-8 border-b border-white/10 pb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Mes Offres</h1>
            <p className="text-slate-400 mt-1">Gérez et suivez vos offres de poste</p>
          </div>
          <div className="flex gap-3">
            <button onClick={fetchOffers} className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-slate-400 hover:text-white border border-white/10 hover:border-white/20 transition-all">
              <RefreshCw className="h-4 w-4" />
            </button>
            <Link href="/recruiter/offers/new">
              <button className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-all">
                <Plus className="h-4 w-4" /> Créer une offre
              </button>
            </Link>
          </div>
        </div>
      </div>

      {/* Status tabs — keyed by status_id */}
      <div className="flex gap-1 border-b border-white/10 pb-0 overflow-x-auto">
        {RECRUITER_TABS.map(tab => {
          const count = tab.status_id === null ? offers.length : offers.filter(o => o.status_id === tab.status_id).length;
          const active = activeStatusId === tab.status_id;
          return (
            <button key={tab.label} onClick={() => selectTab(tab.status_id)}
              className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-all ${
                active ? 'border-[#1f9d94] text-[#1f9d94]' : 'border-transparent text-slate-400 hover:text-white'
              }`}>
              {tab.label} {count > 0 && <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${active ? 'bg-teal-500/20 text-teal-400' : 'bg-white/[0.07] text-slate-400'}`}>{count}</span>}
            </button>
          );
        })}
      </div>

      {error && <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm"><AlertCircle className="h-4 w-4 flex-shrink-0" />{error}</div>}

      {filtered.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center h-48 rounded-2xl border border-white/10 bg-white/[0.02] text-slate-500">
          {offers.length === 0
            ? <><p className="font-medium">Aucune offre créée</p><Link href="/recruiter/offers/new"><span className="text-sm text-indigo-400 hover:text-indigo-300 mt-2 cursor-pointer">Créer votre première offre →</span></Link></>
            : <p className="font-medium">Aucune offre dans cette catégorie</p>
          }
        </div>
      )}

      <div className="space-y-5">
      {filtered.map((offer, i) => {
        const sourcerName = offer.assigned_to ? sourcerNames[offer.assigned_to] : null;
        return (
        <Link key={offer.id} href={`/recruiter/offers/${offer.id}`} className="block">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            className="rounded-2xl border border-white/10 border-l-4 border-l-[#1f9d94] bg-white/[0.03] p-6 space-y-4 cursor-pointer hover:border-indigo-500/30 hover:bg-white/[0.06] hover:shadow-lg hover:shadow-teal-500/[0.08] transition-all duration-200">
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
                <p className="text-xs text-slate-500 mt-2">
                  {offer.assigned_to ? (
                    <span className="text-teal-400">
                      Assignée{sourcerName ? <> à <span className="text-white font-medium">{sourcerName}</span></> : ''}
                    </span>
                  ) : (
                    <span className="text-amber-400">Non assignée</span>
                  )}
                  {' · '}Créée le {new Date(offer.created_at).toLocaleDateString('fr-FR')}
                </p>
              </div>
            </div>
            <div className="flex gap-2 flex-wrap items-center">
              {!offer.assigned_to && (
                <button onClick={e => { e.preventDefault(); setAssignTarget(offer); }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-indigo-500/30 text-indigo-400 text-xs hover:bg-indigo-500/10 transition-all">
                  <UserCheck className="h-3.5 w-3.5" /> Assigner
                </button>
              )}
              {offer.status_id >= 4 && (
                <Link href={`/recruiter/offers/${offer.id}`} onClick={e => e.stopPropagation()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-green-500/10 border border-green-500/20 text-green-400 text-xs hover:bg-green-500/20 transition-all">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Voir les résultats
                </Link>
              )}
              {offer.status_id < 4 && offer.job?.status === 'running' && (
                <Link href={`/recruiter/offers/${offer.id}`} onClick={e => e.stopPropagation()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-teal-500/20 text-teal-400 text-xs hover:bg-teal-500/10 transition-all">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Voir la progression
                </Link>
              )}
              {/* Spacer pushes archive/delete to the right */}
              <div className="flex-1" />
              {/* Archive */}
              {offer.status_id !== 7 && (
                <button onClick={e => { e.preventDefault(); setArchiveTarget(offer); }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#1f9d94]/30 text-[#1f9d94] text-xs hover:bg-[#1f9d94]/10 transition-all">
                  Archiver
                </button>
              )}
              <button onClick={e => { e.preventDefault(); setDeleteTarget(offer); }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-red-500/20 text-red-400 text-xs hover:bg-red-500/10 transition-all">
                Supprimer
              </button>
            </div>
          </motion.div>
        </Link>
        );
      })}
      </div>

      <AnimatePresence>
        {assignTarget && (
          <AssignModal offer={assignTarget} onClose={() => setAssignTarget(null)} onAssigned={fetchOffers} />
        )}
      </AnimatePresence>

      {deleteTarget && (
        <DeleteOfferModal
          title={deleteTarget.title}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={handleDelete}
          loading={deleting}
        />
      )}
      {archiveTarget && (
        <ArchiveOfferModal
          title={archiveTarget.title}
          onCancel={() => setArchiveTarget(null)}
          onConfirm={handleArchive}
          loading={archiving}
        />
      )}
    </div>
  );
}

export default function RecruiterOffersPage() {
  return <Suspense fallback={null}><RecruiterOffersContent /></Suspense>;
}

