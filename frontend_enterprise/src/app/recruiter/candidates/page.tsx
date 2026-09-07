'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { motion } from 'motion/react';
import Link from 'next/link';
import { Loader2, Search, Users } from 'lucide-react';
import { CandidateScoreRangeFilter } from '@/components/CandidateScoreRangeFilter';
import { DarkSelect } from '@/components/DarkSelect';
import { formatScorePct, scoreTextClass } from '@/lib/scoreUtils';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const PAGE_SIZE = 20;

const SENIORITIES = ['Junior', 'Confirme', 'Senior', 'Expert'];

const AVAILABILITY_OPTIONS = [
  { value: '__all__', label: 'Disponibilité — tous' },
  { value: 'true', label: 'Ouvert aux offres' },
  { value: 'false', label: 'Non disponible' },
];

interface Candidate {
  id: string;
  full_name: string;
  profile: string | null;
  profile_label_fr?: string | null;
  seniority: string | null;
  seniority_label_fr?: string | null;
  email: string | null;
  open_to_work: boolean;
  expected_salary: number | null;
  latest_score: number | null;
  latest_decision: string | null;
  latest_decision_label: string | null;
  annees_experience: string | null;
  top_skills: string[];
}

function initials(name: string): string {
  return name.split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('');
}

function decisionBadgeClass(decision?: string | null): string {
  switch (decision) {
    case 'shortlisted':
      return 'border-blue-200 bg-blue-50 text-blue-700';
    case 'contacted':
      return 'border-cyan-200 bg-cyan-50 text-cyan-700';
    case 'interviewed':
      return 'border-purple-200 bg-purple-50 text-purple-700';
    case 'offered':
      return 'border-amber-200 bg-amber-50 text-amber-800';
    case 'hired':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    case 'rejected':
      return 'border-red-200 bg-red-50 text-red-700';
    default:
      return 'border-slate-200 bg-slate-50 text-slate-700';
  }
}

export default function RecruiterCandidatesPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [profileFilter, setProfileFilter] = useState('');
  const [seniorityFilter, setSeniorityFilter] = useState('');
  const [openFilter, setOpenFilter] = useState<boolean | ''>('');
  const [profiles, setProfiles] = useState<string[]>([]);
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100]);
  const [scoreDraft, setScoreDraft] = useState<[number, number]>([0, 100]);

  const scoreFilterActive = scoreRange[0] > 0 || scoreRange[1] < 100;

  const fetchCandidates = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (search.trim()) params.set('search', search.trim());
    if (profileFilter) params.set('profile', profileFilter);
    if (seniorityFilter) params.set('seniority', seniorityFilter);
    if (openFilter !== '') params.set('open_to_work', String(openFilter));
    if (scoreFilterActive) {
      params.set('score_min', String(scoreRange[0]));
      params.set('score_max', String(scoreRange[1]));
    }

    fetch(`${API_BASE}/candidates?${params}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => {
        setCandidates(d.candidates || []);
        setTotal(d.total || 0);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [offset, search, profileFilter, seniorityFilter, openFilter, scoreRange, scoreFilterActive]);

  useEffect(() => { fetchCandidates(); }, [fetchCandidates]);

  useEffect(() => {
    fetch(`${API_BASE}/staging/profiles`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setProfiles(d.profiles || []); })
      .catch(() => null);
  }, []);

  useEffect(() => { setOffset(0); }, [search, profileFilter, seniorityFilter, openFilter, scoreRange]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="w-full max-w-7xl space-y-6">
      <div className="mb-8 border-b border-[#d8e0ea] pb-6">
        <h1 className="text-3xl font-bold text-slate-950">Candidats</h1>
        <p className="text-slate-600 mt-1">CRM candidats — suivi, décisions et onboarding</p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
        <div className="relative flex-1 min-w-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Rechercher par nom ou email…"
            className="w-full h-10 pl-10 pr-4 rounded-xl border border-[#d8e0ea] bg-white text-sm text-slate-950 placeholder:text-slate-400 shadow-sm focus:border-[#2f66ed]/50 focus:outline-none focus:ring-2 focus:ring-[#2f66ed]/10" />
        </div>
        <CandidateScoreRangeFilter
          scoreDraft={scoreDraft}
          scoreFilterActive={scoreFilterActive}
          onDraftChange={setScoreDraft}
          onCommit={setScoreRange}
          onReset={() => {
            setScoreRange([0, 100]);
            setScoreDraft([0, 100]);
          }}
        />
        <DarkSelect
          value={openFilter === '' ? '__all__' : String(openFilter)}
          onChange={v => setOpenFilter(v === '__all__' ? '' : v === 'true')}
          options={AVAILABILITY_OPTIONS}
          className="w-full sm:w-auto sm:min-w-[200px] shrink-0"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <button onClick={() => setProfileFilter('')}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${!profileFilter ? 'bg-[#2f66ed] text-white shadow-sm' : 'border border-[#d8e0ea] bg-white text-slate-600 hover:border-[#2f66ed]/40 hover:text-[#2f66ed]'}`}>Tous profils</button>
        {profiles.map(p => (
          <button key={p} onClick={() => setProfileFilter(p === profileFilter ? '' : p)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${profileFilter === p ? 'bg-[#2f66ed] text-white shadow-sm' : 'border border-[#d8e0ea] bg-white text-slate-600 hover:border-[#2f66ed]/40 hover:text-[#2f66ed]'}`}>{p}</button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <button onClick={() => setSeniorityFilter('')}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${!seniorityFilter ? 'bg-slate-900 text-white shadow-sm' : 'border border-[#d8e0ea] bg-white text-slate-600 hover:border-[#2f66ed]/40 hover:text-[#2f66ed]'}`}>Toutes séniorités</button>
        {SENIORITIES.map(s => (
          <button key={s} onClick={() => setSeniorityFilter(s === seniorityFilter ? '' : s)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${seniorityFilter === s ? 'bg-slate-900 text-white shadow-sm' : 'border border-[#d8e0ea] bg-white text-slate-600 hover:border-[#2f66ed]/40 hover:text-[#2f66ed]'}`}>{s}</button>
        ))}
      </div>

      {loading && <div className="flex justify-center h-48"><Loader2 className="h-8 w-8 animate-spin text-[#1f9d94] mt-12" /></div>}

      {!loading && candidates.length === 0 && (
        <div className="flex flex-col items-center justify-center h-48 rounded-xl border border-[#d8e0ea] bg-white text-slate-500 shadow-sm">
          <Users className="h-10 w-10 mb-3 opacity-40" />
          <p className="font-medium">Aucun candidat trouvé</p>
        </div>
      )}

      {!loading && candidates.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-[#d8e0ea] bg-white shadow-sm">
          <div className="hidden md:grid grid-cols-[1fr_120px_100px_120px_100px] gap-3 border-b border-[#e5ebf2] bg-slate-50 px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            <span>Candidat</span><span>Profil</span><span>Score</span><span>Décision</span><span>Salaire attendu</span>
          </div>
          {candidates.map(c => (
            <Link key={c.id} href={`/recruiter/candidates/${c.id}`}>
              <div className="grid grid-cols-1 md:grid-cols-[1fr_120px_100px_120px_100px] gap-3 items-center border-t border-[#e5ebf2] px-4 py-3 transition-colors hover:bg-blue-50/45 cursor-pointer">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-lg border border-blue-100 bg-blue-50 flex items-center justify-center text-xs font-bold text-[#2f66ed] flex-shrink-0">{initials(c.full_name)}</div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-950 truncate">{c.full_name}</p>
                    <p className="text-xs text-slate-500 truncate">{c.annees_experience || c.email || '—'}</p>
                  </div>
                </div>
                <span className="w-fit rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-700">{c.profile_label_fr || c.profile || '—'}</span>
                <span className={`text-sm font-medium ${scoreTextClass(c.latest_score)}`}>{formatScorePct(c.latest_score)}</span>
                <span className={`w-fit rounded-full border px-2 py-0.5 text-xs ${decisionBadgeClass(c.latest_decision)}`}>
                  {c.latest_decision_label || 'En attente'}
                </span>
                <span className="text-sm text-slate-600">{c.expected_salary != null ? `${c.expected_salary} MAD` : '—'}</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 pt-4">
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="px-4 py-2 rounded-xl text-sm border border-white/10 text-slate-400 hover:text-white disabled:opacity-30">Précédent</button>
          <span className="text-sm text-slate-500">Page {currentPage} / {totalPages}</span>
          <button disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}
            className="px-4 py-2 rounded-xl text-sm border border-white/10 text-slate-400 hover:text-white disabled:opacity-30">Suivant</button>
        </div>
      )}
    </div>
  );
}

