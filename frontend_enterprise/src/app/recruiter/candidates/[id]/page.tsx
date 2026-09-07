'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { CandidateNotesList } from '@/components/CandidateNotesList';
import { CandidateCvSummary } from '@/components/CandidateCvSummary';
import { CandidateAppearanceRow } from '@/components/CandidateAppearanceRow';
import { ActiveUnreliabilitySection, UnreliabilityFlagIndicator, type UnreliabilityFlagInfo } from '@/components/UnreliabilityFlagIndicator';
import { CARD_CLASS, INPUT_CLASS } from '@/lib/uiTokens';
import type { SkillLike } from '@/lib/skillUtils';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

const NOTE_TYPES = [
  { id: 'general', label: 'Générale' },
  { id: 'behavioral', label: 'Comportementale' },
  { id: 'availability', label: 'Disponibilité' },
  { id: 'interview', label: 'Entretien' },
  { id: 'technical', label: 'Technique' },
  { id: 'salary', label: 'Salaire' },
];

interface Candidate {
  full_name: string;
  profile?: string | null;
  profile_label_fr?: string | null;
  seniority?: string | null;
  seniority_label_fr?: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  open_to_work?: boolean;
  availability_date?: string | null;
  current_salary?: number | null;
  expected_salary?: number | null;
  onboarded?: boolean;
  onboarding_date?: string | null;
}

interface Appearance {
  id: string;
  offer_id?: string;
  offer_title?: string;
  offer_created_at?: string | null;
  recruiter_id?: string | null;
  recruiter_name?: string | null;
  rank?: number | null;
  matching_score?: number | null;
  final_score?: number | null;
  matching_status?: { code: string; label_fr: string };
  matching_skills_count?: number | null;
  total_offer_skills?: number | null;
  unreliability_flag?: UnreliabilityFlagInfo | null;
}

interface CandidateDetail {
  candidate: Candidate;
  notes: Array<{ id: string; author_id?: string | null; author_name: string; author_role?: string; note_type: string; content: string }>;
  offer_appearances: Appearance[];
  cv_summary: { annees_experience?: string; skills?: SkillLike[]; titre?: string; resume?: string };
  unreliability_flag?: UnreliabilityFlagInfo | null;
}

export default function RecruiterCandidateDetailPage() {
  const params = useParams();
  const id = String(params.id || '');
  const [data, setData] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [matchingStatuses, setMatchingStatuses] = useState<Array<{ code: string; label_fr: string }>>([]);

  function reload() {
    fetch(`${API_BASE}/candidates/${id}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    fetch(`${API_BASE}/auth/me`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(u => {
        if (u?.user_id) setCurrentUserId(u.user_id);
        if (u?.role === 'admin') setIsAdmin(true);
      });
    fetch(`${API_BASE}/ref/matching-statuses`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.matching_statuses) setMatchingStatuses(d.matching_statuses); })
      .catch(() => null);
  }, [id]);

  async function patch(fields: Record<string, unknown>) {
    await fetch(`${API_BASE}/candidates/${id}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fields),
    });
    reload();
  }

  async function updateMatchingStatus(appearanceId: string, statusCode: string) {
    await fetch(`${API_BASE}/candidates/appearances/${appearanceId}/status`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase: 'matching', status_code: statusCode }),
    });
    reload();
  }

  if (loading) return <div className="flex justify-center h-48"><Loader2 className="h-8 w-8 animate-spin text-[#1f9d94] mt-12" /></div>;
  if (!data) return <p className="text-slate-400">Candidat introuvable.</p>;

  const c = data.candidate;
  const matchingOptions = matchingStatuses.map(s => ({ value: s.code, label: s.label_fr }));
  const activeFlag = data.unreliability_flag;

  return (
    <div className="w-full max-w-4xl space-y-6">
      <Link href="/recruiter/candidates" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors">
        <ArrowLeft className="h-4 w-4" /> Retour aux candidats
      </Link>

      <div className={`${CARD_CLASS} space-y-4`}>
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-2xl font-bold text-white">{c.full_name}</h1>
          {activeFlag && (
            <UnreliabilityFlagIndicator flag={activeFlag} candidateId={id} canResolve onResolved={reload} />
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {(c.profile_label_fr || c.profile) && (
            <span className="text-xs px-2 py-1 rounded-full bg-teal-400/10 text-teal-300 border border-teal-400/20">
              {c.profile_label_fr || c.profile}
            </span>
          )}
          {(c.seniority_label_fr || c.seniority) && (
            <span className="text-xs px-2 py-1 rounded-full bg-white/5 text-slate-300 border border-white/10">
              {c.seniority_label_fr || c.seniority}
            </span>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-slate-400">
          {c.email && <p>Email : <span className="text-white">{c.email}</span></p>}
          {c.phone && <p>Tél. : <span className="text-white">{c.phone}</span></p>}
          {c.location && <p>Localisation : <span className="text-white">{c.location}</span></p>}
        </div>
      </div>

      {activeFlag && (
        <ActiveUnreliabilitySection flag={activeFlag} candidateId={id} canResolve onResolved={reload} />
      )}

      <div className={`${CARD_CLASS} space-y-4`}>
        <h2 className="text-sm font-semibold text-slate-300">Disponibilité</h2>
        <label className="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" checked={!!c.open_to_work} onChange={e => patch({ open_to_work: e.target.checked })}
            className="h-4 w-4 rounded accent-[#1f9d94]" />
          <span className="text-sm text-white">Ouvert aux opportunités</span>
        </label>
        <div>
          <label className="text-xs text-slate-500 block mb-1">Date de disponibilité</label>
          <input type="date" defaultValue={c.availability_date ? String(c.availability_date).slice(0, 10) : ''}
            onBlur={e => { if (e.target.value) patch({ availability_date: e.target.value }); }}
            className={INPUT_CLASS} />
        </div>
      </div>

      <div className={`${CARD_CLASS} space-y-4`}>
        <h2 className="text-sm font-semibold text-slate-300">Rémunération</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-slate-500 block mb-1">Salaire actuel (MAD)</label>
            <input type="number" defaultValue={c.current_salary != null ? Number(c.current_salary) : ''}
              onBlur={e => patch({ current_salary: e.target.value ? parseFloat(e.target.value) : null })}
              className={`w-full ${INPUT_CLASS}`} />
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Salaire attendu (MAD)</label>
            <input type="number" defaultValue={c.expected_salary != null ? Number(c.expected_salary) : ''}
              onBlur={e => patch({ expected_salary: e.target.value ? parseFloat(e.target.value) : null })}
              className={`w-full ${INPUT_CLASS}`} />
          </div>
        </div>
      </div>

      <div className={`${CARD_CLASS} space-y-4`}>
        <h2 className="text-sm font-semibold text-slate-300">Onboarding</h2>
        <label className="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" checked={!!c.onboarded} onChange={e => patch({ onboarded: e.target.checked })}
            className="h-4 w-4 rounded accent-[#1f9d94]" />
          <span className="text-sm text-white">Candidat onboardé</span>
        </label>
        <div>
          <label className="text-xs text-slate-500 block mb-1">Date d&apos;onboarding</label>
          <input type="date" defaultValue={c.onboarding_date ? String(c.onboarding_date).slice(0, 10) : ''}
            onBlur={e => { if (e.target.value) patch({ onboarding_date: e.target.value }); }}
            className={INPUT_CLASS} />
        </div>
      </div>

      <CandidateCvSummary summary={data.cv_summary || {}} />

      <div className={`${CARD_CLASS} space-y-1`}>
        <h2 className="text-sm font-semibold text-slate-300 mb-3">Apparitions sur offres</h2>
        {data.offer_appearances.length === 0 && (
          <p className="text-slate-500 text-sm">Aucune apparition.</p>
        )}
        {data.offer_appearances.map(a => {
          const isOwned = !!currentUserId
            && !!a.recruiter_id
            && String(a.recruiter_id) === String(currentUserId);
          return (
          <CandidateAppearanceRow
            key={String(a.id)}
            offerTitle={a.offer_title}
            offerHref={isOwned && a.offer_id ? `/recruiter/offers/${a.offer_id}` : undefined}
            offerCreatedAt={a.offer_created_at}
            recruiterName={a.recruiter_name}
            recruiterOwned={isOwned}
            rank={a.rank}
            matchingScore={a.matching_score}
            finalScore={a.final_score}
            matchingStatusCode={a.matching_status?.code}
            matchingStatusOptions={isOwned || isAdmin ? matchingOptions : undefined}
            onMatchingStatusChange={isOwned || isAdmin ? code => updateMatchingStatus(a.id, code) : undefined}
            matchingSkillsCount={a.matching_skills_count}
            totalOfferSkills={a.total_offer_skills}
          />
          );
        })}
      </div>

      <CandidateNotesList
        candidateId={id}
        notes={data.notes}
        noteTypes={NOTE_TYPES}
        currentUserId={currentUserId}
        isAdmin={isAdmin}
        onChanged={reload}
      />
    </div>
  );
}

