'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'motion/react';
import {
  ArrowDown, ArrowUp, ArrowUpDown, Briefcase, Clock,
  RefreshCw, Star, Target, TrendingUp, UserCheck, Users,
} from 'lucide-react';
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis,
} from 'recharts';
import { AnimatedKpiCard } from '@/components/admin/AnimatedKpiCard';
import { TeamActivitySection, type TeamActivityData } from '@/components/admin/TeamActivitySection';
import { GapBarCell } from '@/components/admin/GapBarCell';
import { MetricHelp } from '@/components/admin/MetricHelp';
import { DateRangeFilter, DateRange } from '@/components/DateRangeFilter';
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/app/components/ui/tooltip';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';
import {
  formatCount, formatHours, formatPercent, monthLabel,
} from '@/lib/adminFormatters';
import {
  ADMIN_FUNNEL_HELP, ADMIN_KPI_HELP, SKILLS_GAP_HELP, STAGE_HELP,
} from '@/lib/adminMetricHelp';
import type { MetricHelpInfo, MetricHelpMode } from '@/lib/adminMetricHelp';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const TEAL = '#0f766e';
const BLUE = '#2563eb';
const GREEN = '#047857';
const PURPLE = '#7c3aed';
const AMBER = '#b45309';
const SLATE_GRID = '#d8e0ea';

interface Insights {
  period: { from: string | null; to: string; label: string };
  business_kpis: {
    total_offers: number;
    offers_by_status: Record<string, number>;
    avg_time_to_match_hours: number | null;
    hired_candidates: number;
    total_missions_in_progress: number;
  };
  recruitment_efficiency: {
    funnel: {
      offers_created: number;
      offers_assigned: number;
      offers_matched: number;
      candidates_evaluated: number;
      candidates_shortlisted: number;
      hired: number;
    };
    conversion_offer_to_match_percent: number | null;
    conversion_match_to_hire_percent: number | null;
    avg_candidates_per_matched_offer: number | null;
    avg_matching_score: number | null;
    avg_time_to_match_hours: number | null;
    outcomes_by_month: {
      month: string;
      offers_matched: number;
      candidates_evaluated: number;
      hired: number;
    }[];
  };
  team_activity: TeamActivityData;
  candidate_pipeline: {
    total_candidates: number;
    candidates_by_profile: { profile: string; label_fr: string; count: number }[];
    candidates_by_seniority: { seniority: string; label_fr: string; count: number }[];
    top_skills_in_demand: {
      skill: string; category: string | null;
      offer_count: number; candidate_count: number;
    }[];
    skills_gap: {
      skill: string; offer_demand: number;
      candidate_supply: number; gap: number;
    }[];
    new_candidates_by_month: { month: string; count: number }[];
  };
}

const STAGE_PILLS: { key: string; label: string; color: string }[] = [
  { key: 'open',         label: 'Ouverte',        color: 'bg-slate-100 text-slate-700 border-slate-200' },
  { key: 'assigned',     label: 'Assignée',       color: 'bg-teal-50 text-teal-700 border-teal-200' },
  { key: 'in_progress',  label: 'En cours',       color: 'bg-blue-50 text-blue-700 border-blue-200' },
  { key: 'matched',      label: 'Matchée',        color: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
  { key: 'final_result', label: 'Résultat final', color: 'bg-purple-50 text-purple-700 border-purple-200' },
  { key: 'formatted',    label: 'Formatée',       color: 'bg-cyan-50 text-cyan-700 border-cyan-200' },
  { key: 'archived',     label: 'Archivée',       color: 'bg-amber-50 text-amber-700 border-amber-200' },
];

const SENIORITY_COLORS = [TEAL, BLUE, PURPLE, AMBER, '#64748b'];

const LINE_BAR_ANIM = {
  isAnimationActive: true,
  animationDuration: 1000,
  animationEasing: 'ease-out' as const,
};

const PIE_ANIM = {
  isAnimationActive: true,
  animationBegin: 200,
  animationDuration: 800,
};

const SECTION_VIEW = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-100px' },
  transition: { duration: 0.5, ease: 'easeOut' as const },
};

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function Section({
  title, children, reducedMotion,
}: {
  title: string; children: React.ReactNode; reducedMotion: boolean;
}) {
  return (
    <motion.section
      className="space-y-4"
      initial={reducedMotion ? false : SECTION_VIEW.initial}
      whileInView={SECTION_VIEW.whileInView}
      viewport={SECTION_VIEW.viewport}
      transition={SECTION_VIEW.transition}
    >
      <h2 className="border-b border-[#d8e0ea] pb-2 text-xl font-semibold text-slate-950">{title}</h2>
      {children}
    </motion.section>
  );
}

function AnimatedTableRow({
  index, reducedMotion, children, className,
}: {
  index: number; reducedMotion: boolean; children: React.ReactNode; className?: string;
}) {
  return (
    <motion.tr
      className={className}
      initial={reducedMotion ? false : { opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, delay: reducedMotion ? 0 : index * 0.05, ease: 'easeOut' }}
    >
      {children}
    </motion.tr>
  );
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[#d8e0ea] bg-white px-3 py-2 text-xs shadow-xl">
      <p className="text-slate-600 mb-1">{label}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }} className="font-medium">
          {p.name}: {formatCount(p.value)}
        </p>
      ))}
    </div>
  );
}

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-slate-200 ${className ?? ''}`} />;
}

type SortDir = 'asc' | 'desc';

function SortHeader({ label, col, sortCol, sortDir, onSort, help }: {
  label: string; col: string; sortCol: string; sortDir: SortDir;
  onSort: (c: string) => void;
  help?: MetricHelpInfo & { mode?: MetricHelpMode };
}) {
  const active = sortCol === col;
  const Icon = active ? (sortDir === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;
  return (
    <th className="px-4 py-3 text-left">
      <div className="flex items-center gap-1">
        <button type="button" onClick={() => onSort(col)} className="flex items-center gap-1 text-xs font-semibold text-[#2563eb] uppercase tracking-wide hover:text-[#1d4ed8]">
          {label} <Icon className="h-3 w-3" />
        </button>
        {help && <MetricHelp info={help} mode={help.mode} />}
      </div>
    </th>
  );
}

function FunnelMetric({
  label, children, help,
}: {
  label: string;
  children: React.ReactNode;
  help: MetricHelpInfo & { mode?: MetricHelpMode };
}) {
  return (
    <div>
      <div className="flex items-center gap-1">
        <p className="text-xs text-slate-600">{label}</p>
        <MetricHelp info={help} mode={help.mode} />
      </div>
      {children}
    </div>
  );
}

function useSortable<T extends Record<string, unknown>>(rows: T[], defaultCol: string) {
  const [col, setCol] = useState(defaultCol);
  const [dir, setDir] = useState<SortDir>('desc');
  const toggle = (c: string) => {
    if (c === col) setDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setCol(c); setDir('desc'); }
  };
  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => {
      const av = a[col]; const bv = b[col];
      if (av === bv) return 0;
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      const cmp = av < bv ? -1 : 1;
      return dir === 'asc' ? cmp : -cmp;
    });
  }, [rows, col, dir]);
  return { sorted, col, dir, toggle };
}

export default function AdminCeoDashboardPage() {
  const [data, setData] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<DateRange>({ from: '', to: todayIso() });
  const [animKey, setAnimKey] = useState(0);
  const reducedMotion = usePrefersReducedMotion();
  const hadDataRef = useRef(false);

  const fetchInsights = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (range.from) params.set('date_from', range.from);
    if (range.to) params.set('date_to', range.to);
    fetch(`${API_BASE}/admin/insights?${params}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(payload => {
        setData(payload);
        setAnimKey(k => k + 1);
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [range]);

  useEffect(() => { fetchInsights(); }, [fetchInsights]);

  const refetching = loading && hadDataRef.current;
  useEffect(() => {
    if (data) hadDataRef.current = true;
  }, [data]);

  const biz = data?.business_kpis;
  const recruit = data?.recruitment_efficiency;
  const team = data?.team_activity;
  const cand = data?.candidate_pipeline;

  const outcomesChart = useMemo(() =>
    (recruit?.outcomes_by_month ?? []).map(r => ({
      month: monthLabel(r.month),
      matched: r.offers_matched,
      evaluated: r.candidates_evaluated,
      hired: r.hired,
    })), [recruit]);

  const funnelChart = useMemo(() => {
    const f = recruit?.funnel;
    if (!f) return [];
    return [
      { step: 'Offres créées', count: f.offers_created, fill: TEAL },
      { step: 'Assignées', count: f.offers_assigned, fill: BLUE },
      { step: 'Matchées', count: f.offers_matched, fill: PURPLE },
      { step: 'Candidats évalués', count: f.candidates_evaluated, fill: '#818cf8' },
      { step: 'Présélectionnés', count: f.candidates_shortlisted, fill: AMBER },
      { step: 'Recrutés', count: f.hired, fill: GREEN },
    ].filter(row => row.count > 0);
  }, [recruit]);

  const profileChart = useMemo(() =>
    (cand?.candidates_by_profile ?? []).map(r => ({
      name: r.label_fr,
      count: r.count,
    })), [cand]);

  const seniorityChart = useMemo(() =>
    (cand?.candidates_by_seniority ?? []).map(r => ({
      name: r.label_fr,
      value: r.count,
    })), [cand]);

  const skillsChart = useMemo(() =>
    (cand?.top_skills_in_demand ?? []).map(r => ({
      skill: r.skill,
      demande: r.offer_count,
      disponibilite: r.candidate_count,
    })), [cand]);

  const newCandChart = useMemo(() =>
    (cand?.new_candidates_by_month ?? []).map(r => ({
      month: monthLabel(r.month),
      count: r.count,
    })), [cand]);

  const maxSkillGap = Math.max(...(cand?.skills_gap ?? []).map(g => g.gap), 1);

  return (
    <div className="relative w-full max-w-[1480px] space-y-8">
      {refetching && !reducedMotion && (
        <div className="fixed top-0 left-0 right-0 z-50 h-0.5 overflow-hidden pointer-events-none">
          <motion.div
            className="h-full w-1/3 bg-[#2f66ed]"
            animate={{ x: ['-100%', '400%'] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
          />
        </div>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase text-[#2f66ed]">Admin console</p>
          <h1 className="mt-2 text-4xl font-semibold text-slate-950">Pilotage plateforme</h1>
          <p className="mt-2 text-lg text-slate-600">Vue d&apos;ensemble de la plateforme et des performances opérationnelles.</p>
        </div>
        <button type="button" onClick={fetchInsights}
          className="flex items-center gap-2 rounded-lg border border-[#d8e0ea] bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:border-[#2f66ed]/40 hover:text-[#2f66ed]">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Actualiser
        </button>
      </div>

      <DateRangeFilter
        value={range}
        onChange={setRange}
        onApply={fetchInsights}
        loading={loading}
        periodLabel={data?.period.label}
      />

      {loading && !data && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
          </div>
          <Skeleton className="h-64" />
          <Skeleton className="h-80" />
        </div>
      )}

      {!loading && !data && (
        <div className="admin-light-card rounded-xl p-8 text-center text-slate-600">
          Impossible de charger les insights.
        </div>
      )}

      {data && (
        <motion.div
          className="space-y-8"
          animate={{ opacity: refetching ? 0.5 : 1 }}
          transition={{ duration: 0.3 }}
        >
          {/* Section 1 — Business KPIs */}
          <Section title="Indicateurs business" reducedMotion={reducedMotion}>
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
              <AnimatedKpiCard label="Offres totales" rawValue={biz?.total_offers} type="count" icon={Briefcase} border="border-[#2f66ed]" sub={`${biz?.total_missions_in_progress ?? 0} missions en cours`} index={0} animKey={animKey} reducedMotion={reducedMotion} help={ADMIN_KPI_HELP.total_offers} />
              <AnimatedKpiCard label="Offres matchées" rawValue={recruit?.funnel?.offers_matched} type="count" icon={TrendingUp} border="border-blue-500" sub={recruit?.conversion_offer_to_match_percent != null ? `${formatPercent(recruit.conversion_offer_to_match_percent)} des offres` : undefined} index={1} animKey={animKey} reducedMotion={reducedMotion} help={ADMIN_KPI_HELP.offers_matched} />
              <AnimatedKpiCard label="Score moyen" rawValue={recruit?.avg_matching_score} type="percent" icon={Star} border="border-purple-500" index={2} animKey={animKey} reducedMotion={reducedMotion} help={ADMIN_KPI_HELP.avg_matching_score} />
              <AnimatedKpiCard label="Délai moyen" rawValue={biz?.avg_time_to_match_hours} type="hours" icon={Clock} border="border-amber-500" sub="jusqu'au matching" index={3} animKey={animKey} reducedMotion={reducedMotion} help={ADMIN_KPI_HELP.avg_time_to_match} />
              <AnimatedKpiCard label="Recrutés" rawValue={biz?.hired_candidates} type="count" icon={UserCheck} border="border-green-500" index={4} animKey={animKey} reducedMotion={reducedMotion} help={ADMIN_KPI_HELP.hired} />
            </div>
            <div className="flex flex-wrap gap-2">
              {STAGE_PILLS.map(({ key, label, color }) => {
                const n = biz?.offers_by_status?.[key] ?? 0;
                  const hint = STAGE_HELP[key];
                  const pill = (
                    <motion.span
                      whileHover={reducedMotion ? undefined : { scale: 1.05 }}
                      transition={{ duration: 0.15 }}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-medium cursor-default ${color}`}
                    >
                      {label} <span className="font-bold">{n}</span>
                    </motion.span>
                  );
                  return hint ? (
                    <Tooltip key={key}>
                      <TooltipTrigger asChild>{pill}</TooltipTrigger>
                      <TooltipContent side="top" className="max-w-[220px] border border-[#d8e0ea] bg-white px-3 py-2 text-xs text-slate-700 shadow-xl" sideOffset={6}>
                        {hint}
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    <span key={key}>{pill}</span>
                  );
              })}
            </div>
          </Section>

          {/* Section 2 — Recruitment efficiency */}
          <Section title="Efficacité du recrutement" reducedMotion={reducedMotion}>
            <p className="text-sm text-slate-600 -mt-2">
              Du besoin exprimé à l&apos;embauche — indicateurs orientés résultats, pas technique pipeline.
            </p>
            <div className="grid lg:grid-cols-5 gap-4">
              <div className="admin-light-card lg:col-span-3 h-80 rounded-xl p-5">
                <h3 className="text-sm font-medium text-slate-700 mb-2">Résultats mensuels</h3>
                {outcomesChart.length === 0 ? (
                  <p className="text-sm text-slate-600 p-4">Aucun résultat sur la période.</p>
                ) : (
                  <ResponsiveContainer width="100%" height="90%">
                    <LineChart key={`outcomes-${animKey}`} data={outcomesChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                      <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" />
                      <XAxis dataKey="month" tick={{ fill: '#64748b', fontSize: 11 }} />
                      <YAxis tick={{ fill: '#64748b', fontSize: 11 }} allowDecimals={false} />
                      <RechartsTooltip content={<ChartTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 12, color: '#64748b' }} />
                      <Line type="monotone" dataKey="matched" name="Offres matchées" stroke={TEAL} strokeWidth={2} dot={{ r: 3 }} {...LINE_BAR_ANIM} />
                      <Line type="monotone" dataKey="evaluated" name="Candidats évalués" stroke={BLUE} strokeWidth={2} dot={{ r: 3 }} {...LINE_BAR_ANIM} />
                      <Line type="monotone" dataKey="hired" name="Recrutés" stroke={GREEN} strokeWidth={2} dot={{ r: 3 }} {...LINE_BAR_ANIM} />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
              <div className="admin-light-card lg:col-span-2 flex h-80 flex-col rounded-xl p-5">
                <h3 className="text-sm font-medium text-slate-700 mb-3">Entonnoir de recrutement</h3>
                {funnelChart.length === 0 ? (
                  <p className="text-sm text-slate-600 flex-1 flex items-center justify-center">Pas encore de données.</p>
                ) : (
                  <ResponsiveContainer width="100%" height="55%" className="flex-shrink-0">
                    <BarChart key={`funnel-${animKey}`} data={funnelChart} layout="vertical" margin={{ left: 4, right: 12 }}>
                      <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} allowDecimals={false} />
                      <YAxis type="category" dataKey="step" width={108} tick={{ fill: '#64748b', fontSize: 10 }} />
                      <RechartsTooltip content={<ChartTooltip />} />
                      <Bar dataKey="count" name="Volume" radius={[0, 4, 4, 0]} {...LINE_BAR_ANIM}>
                        {funnelChart.map((row, i) => <Cell key={i} fill={row.fill} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
                <div className="mt-auto pt-4 grid grid-cols-2 gap-3 border-t border-[#d8e0ea]">
                  <FunnelMetric label="Offre → matching" help={ADMIN_FUNNEL_HELP.offer_to_match}>
                    <p className="text-lg font-bold text-teal-700">{formatPercent(recruit?.conversion_offer_to_match_percent)}</p>
                  </FunnelMetric>
                  <FunnelMetric label="Matching → embauche" help={ADMIN_FUNNEL_HELP.match_to_hire}>
                    <p className="text-lg font-bold text-emerald-700">{formatPercent(recruit?.conversion_match_to_hire_percent)}</p>
                  </FunnelMetric>
                  <FunnelMetric label="Délai moyen" help={ADMIN_FUNNEL_HELP.avg_delay}>
                    <p className="text-sm font-semibold text-slate-900">{formatHours(recruit?.avg_time_to_match_hours)}</p>
                  </FunnelMetric>
                  <FunnelMetric label="Candidats / offre" help={ADMIN_FUNNEL_HELP.candidates_per_offer}>
                    <p className="text-sm font-semibold text-slate-900">
                      {recruit?.avg_candidates_per_matched_offer?.toFixed(1) ?? '—'}
                    </p>
                  </FunnelMetric>
                </div>
              </div>
            </div>
          </Section>

          {/* Section 3 — Team Activity */}
          <Section title="Activité d'équipe" reducedMotion={reducedMotion}>
            {team && (
              <TeamActivitySection team={team} animKey={animKey} reducedMotion={reducedMotion} />
            )}
          </Section>

          {/* Section 4 — Candidate Pipeline */}
          <Section title="Pipeline candidats" reducedMotion={reducedMotion}>
            <AnimatedKpiCard label="Candidats total" rawValue={cand?.total_candidates} type="count" icon={Users} border="border-[#2f66ed]" index={0} animKey={animKey} reducedMotion={reducedMotion} />
            <div className="grid lg:grid-cols-2 gap-4">
              <div className="admin-light-card h-80 rounded-xl p-5">
                <h3 className="text-sm font-medium text-slate-700 mb-2">Candidats par profil</h3>
                {profileChart.length === 0 ? (
                  <p className="text-sm text-slate-600">Aucun candidat.</p>
                ) : (
                  <ResponsiveContainer width="100%" height="90%">
                    <BarChart key={`profile-${animKey}`} data={profileChart} layout="vertical" margin={{ left: 8, right: 16 }}>
                      <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} />
                      <YAxis type="category" dataKey="name" width={120} tick={{ fill: '#64748b', fontSize: 10 }} />
                      <RechartsTooltip content={<ChartTooltip />} />
                      <Bar dataKey="count" name="Candidats" fill={TEAL} radius={[0, 4, 4, 0]} {...LINE_BAR_ANIM} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
              <div className="admin-light-card flex h-80 flex-col rounded-xl p-5">
                <h3 className="text-sm font-medium text-slate-700 mb-2">Répartition par séniorité</h3>
                {seniorityChart.length === 0 ? (
                  <p className="text-sm text-slate-600">Aucune donnée.</p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart key={`seniority-${animKey}`}>
                      <Pie data={seniorityChart} dataKey="value" nameKey="name" innerRadius={48} outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false} {...PIE_ANIM}>
                        {seniorityChart.map((_, i) => (
                          <Cell key={i} fill={SENIORITY_COLORS[i % SENIORITY_COLORS.length]} />
                        ))}
                      </Pie>
                      <RechartsTooltip formatter={(v: number) => formatCount(v)} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
            <div className="grid lg:grid-cols-2 gap-4">
              <div className="admin-light-card h-80 rounded-xl p-5">
                <h3 className="text-sm font-medium text-slate-700 mb-2">Compétences les plus demandées</h3>
                {skillsChart.length === 0 ? (
                  <p className="text-sm text-slate-600">Aucune compétence.</p>
                ) : (
                  <ResponsiveContainer width="100%" height="90%">
                    <BarChart key={`skills-${animKey}`} data={skillsChart} layout="vertical" margin={{ left: 4, right: 16 }}>
                      <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} />
                      <YAxis type="category" dataKey="skill" width={88} tick={{ fill: '#64748b', fontSize: 10 }} />
                      <RechartsTooltip content={<ChartTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 11, color: '#64748b' }} />
                      <Bar dataKey="demande" name="Demande (offres)" fill={AMBER} radius={[0, 4, 4, 0]} {...LINE_BAR_ANIM} />
                      <Bar dataKey="disponibilite" name="Disponibilité" fill={TEAL} radius={[0, 4, 4, 0]} {...LINE_BAR_ANIM} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
              <div className="admin-light-card overflow-hidden rounded-xl">
                <div className="px-4 py-3 border-b border-[#d8e0ea]">
                  <h3 className="text-sm font-medium text-slate-700 flex items-center gap-2">
                    <Target className="h-4 w-4 text-amber-700" /> Gaps de compétences
                  </h3>
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-slate-50">
                    <tr className="text-xs text-slate-600 uppercase">
                      <th className="px-4 py-2 text-left">Compétence</th>
                      <th className="px-4 py-2 text-right">Demande</th>
                      <th className="px-4 py-2 text-right">Dispo.</th>
                      <th className="px-4 py-2 text-right">
                        <div className="flex items-center justify-end gap-1">
                          Gap
                          <MetricHelp info={SKILLS_GAP_HELP} mode={SKILLS_GAP_HELP.mode} />
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#e5ebf2]">
                    {(cand?.skills_gap ?? []).length === 0 && (
                      <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-600">Aucun gap identifié</td></tr>
                    )}
                    {(cand?.skills_gap ?? []).map((g, i) => (
                      <AnimatedTableRow key={g.skill} index={i} reducedMotion={reducedMotion}>
                        <td className="px-4 py-2.5 text-slate-900">{g.skill}</td>
                        <td className="px-4 py-2.5 text-right text-slate-600">{g.offer_demand}</td>
                        <td className="px-4 py-2.5 text-right text-slate-600">{g.candidate_supply}</td>
                        <GapBarCell gap={g.gap} maxGap={maxSkillGap} reducedMotion={reducedMotion} />
                      </AnimatedTableRow>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="admin-light-card h-56 rounded-xl p-5">
              <h3 className="text-sm font-medium text-slate-700 mb-2">Nouveaux candidats par mois</h3>
              {newCandChart.length === 0 ? (
                <p className="text-sm text-slate-600">Aucun nouveau candidat.</p>
              ) : (
                <ResponsiveContainer width="100%" height="85%">
                  <LineChart key={`newcand-${animKey}`} data={newCandChart}>
                    <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" />
                    <XAxis dataKey="month" tick={{ fill: '#64748b', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#64748b', fontSize: 11 }} allowDecimals={false} />
                    <RechartsTooltip content={<ChartTooltip />} />
                    <Line type="monotone" dataKey="count" name="Nouveaux" stroke={TEAL} strokeWidth={2} dot={{ r: 4, fill: TEAL }} {...LINE_BAR_ANIM} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </Section>
        </motion.div>
      )}
    </div>
  );
}


