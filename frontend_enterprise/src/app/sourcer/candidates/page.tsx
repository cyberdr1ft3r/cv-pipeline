'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { motion } from 'motion/react';
import Link from 'next/link';
import { FolderUp, Loader2, Search, Users } from 'lucide-react';
import { DarkSelect } from '@/components/DarkSelect';
import { CandidateScoreRangeFilter } from '@/components/CandidateScoreRangeFilter';
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
  latest_score: number | null;
  annees_experience: string | null;
  top_skills: string[];
}

function initials(name: string): string {
  return name.split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('');
}

function seniorityBadgeClass(value?: string | null): string {
  const normalized = (value || '').toLowerCase();
  if (normalized.includes('junior')) return 'border-blue-200 bg-blue-50 text-blue-700';
  if (normalized.includes('confirm')) return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (normalized.includes('senior')) return 'border-amber-200 bg-amber-50 text-amber-800';
  if (normalized.includes('expert')) return 'border-purple-200 bg-purple-50 text-purple-700';
  return 'border-slate-200 bg-slate-50 text-slate-700';
}

export default function SourcerCandidatesPage() {
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
      <div className="mb-8 border-b border-[#d8e0ea] pb-6 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-950">Vivier</h1>
          <p className="text-slate-600 mt-1">Suivez les candidats du vivier et leur disponibilité</p>
        </div>
        <Link href="/sourcer/upload">
          <button
            type="button"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#2f66ed] hover:bg-[#2558d7] text-white text-sm font-medium transition-all shadow-[0_4px_16px_rgba(47,102,237,0.22)]"
          >
            <FolderUp className="h-4 w-4" />
            Déposer des CVs
          </button>
        </Link>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
        <div className="relative flex-1 min-w-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Rechercher par nom ou email…"
            className="w-full h-10 pl-10 pr-4 rounded-xl border border-[#d8e0ea] bg-white text-sm text-slate-950 placeholder:text-slate-400 shadow-sm focus:border-[#2f66ed]/50 focus:outline-none focus:ring-2 focus:ring-[#2f66ed]/10"
          />
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
        <button
          onClick={() => setProfileFilter('')}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${!profileFilter ? 'bg-[#2f66ed] text-white shadow-sm' : 'border border-[#d8e0ea] bg-white text-slate-600 hover:border-[#2f66ed]/40 hover:text-[#2f66ed]'}`}
        >Tous profils</button>
        {profiles.map(p => (
          <button key={p} onClick={() => setProfileFilter(p === profileFilter ? '' : p)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${profileFilter === p ? 'bg-[#2f66ed] text-white shadow-sm' : 'border border-[#d8e0ea] bg-white text-slate-600 hover:border-[#2f66ed]/40 hover:text-[#2f66ed]'}`}
          >{p}</button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <button onClick={() => setSeniorityFilter('')}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${!seniorityFilter ? 'bg-slate-900 text-white shadow-sm' : 'border border-[#d8e0ea] bg-white text-slate-600 hover:border-[#2f66ed]/40 hover:text-[#2f66ed]'}`}
        >Toutes séniorités</button>
        {SENIORITIES.map(s => (
          <button key={s} onClick={() => setSeniorityFilter(s === seniorityFilter ? '' : s)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${seniorityFilter === s ? 'bg-slate-900 text-white shadow-sm' : 'border border-[#d8e0ea] bg-white text-slate-600 hover:border-[#2f66ed]/40 hover:text-[#2f66ed]'}`}
          >{s}</button>
        ))}
      </div>

      {loading && (
        <div className="flex justify-center h-48"><Loader2 className="h-8 w-8 animate-spin text-[#1f9d94] mt-12" /></div>
      )}

      {!loading && candidates.length === 0 && (
        <div className="flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-[#d8e0ea] bg-white px-6 py-10 text-center text-slate-500 shadow-sm">
          <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-[#2f66ed]">
            <Users className="h-6 w-6" />
          </span>
          <p className="font-semibold text-slate-800">Aucun candidat trouvé</p>
          <p className="mt-1 max-w-md text-sm text-slate-500">Déposez des CVs pour alimenter le vivier, ou ajustez les filtres de recherche.</p>
          <Link href="/sourcer/upload" className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[#2f66ed] px-4 py-2 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(47,102,237,0.18)] transition hover:bg-[#2458d8]">
            <FolderUp className="h-4 w-4" />
            Déposer des CVs
          </Link>
        </div>
      )}

      {!loading && candidates.length > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {candidates.map((c, i) => (
            <motion.div key={c.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
              <Link href={`/sourcer/candidates/${c.id}`}>
                <div className="group relative overflow-hidden rounded-xl border border-[#d8e0ea] bg-white p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-[#2f66ed]/45 hover:shadow-[0_14px_34px_rgba(15,23,42,0.10)] cursor-pointer space-y-3">
                  <span className="absolute inset-y-0 left-0 w-1 bg-[#2f66ed] opacity-80" />
                  <div className="flex items-start gap-3">
                    <div className="w-11 h-11 rounded-xl border border-blue-100 bg-blue-50 flex items-center justify-center text-sm font-bold text-[#2f66ed] flex-shrink-0">
                      {initials(c.full_name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-slate-950 truncate">{c.full_name}</p>
                      <p className="text-xs text-slate-500 truncate">{c.email || '—'}</p>
                    </div>
                    <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 mt-1 ring-4 ${c.open_to_work ? 'bg-emerald-500 ring-emerald-100' : 'bg-slate-400 ring-slate-100'}`} title={c.open_to_work ? 'Ouvert' : 'Fermé'} />
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {c.profile && <span className="text-xs px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50 text-slate-700">{c.profile_label_fr || c.profile}</span>}
                    {c.seniority && <span className={`text-xs px-2 py-0.5 rounded-full border ${seniorityBadgeClass(c.seniority_label_fr || c.seniority)}`}>{c.seniority_label_fr || c.seniority}</span>}
                  </div>
                  {c.annees_experience && <p className="text-xs text-slate-500">{c.annees_experience}</p>}
                  {c.top_skills?.length > 0 && (
                    <div className="flex flex-wrap gap-1">{c.top_skills.map(s => (
                      <span key={s} className="text-[10px] rounded-full border border-blue-100 bg-blue-50 px-1.5 py-0.5 font-medium text-[#2f66ed]">{s}</span>
                    ))}</div>
                  )}
                  {typeof c.latest_score === 'number' && (
                    <p className={`text-xs font-medium ${scoreTextClass(c.latest_score)}`}>
                      Dernier score : {formatScorePct(c.latest_score)}
                    </p>
                  )}
                </div>
              </Link>
            </motion.div>
          ))}
        </motion.div>
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

