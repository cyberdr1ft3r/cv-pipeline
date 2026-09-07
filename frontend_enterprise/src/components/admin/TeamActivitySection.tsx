'use client';

import React, { useMemo, useState } from 'react';
import { motion } from 'motion/react';
import {
  ArrowDown, ArrowUp, ArrowUpDown, BarChart2, Briefcase, CheckCircle2,
  Clock, Star, Target, TrendingUp, UserCheck, Users,
} from 'lucide-react';
import {
  Area, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis,
} from 'recharts';
import { AnimatedKpiCard } from '@/components/admin/AnimatedKpiCard';
import { MetricHelp } from '@/components/admin/MetricHelp';
import { RecruiterKpiCard } from '@/components/admin/RecruiterKpiCard';
import { StackedProgressBar } from '@/components/StackedProgressBar';
import { formatCount, formatHours, formatPercent, monthLabel } from '@/lib/adminFormatters';
import {
  TEAM_ACTIVITY_SECTION_HELP,
  TEAM_CHART_HELP,
  TEAM_CLIENT_FEEDBACK_HELP,
  TEAM_RECRUITING_CARDS_HELP,
  TEAM_RECRUITING_KPI_HELP,
  TEAM_RECRUITING_VIEW_HELP,
  TEAM_SOURCING_KPI_HELP,
  TEAM_SOURCING_VIEW_HELP,
  TEAM_TABLE_HELP,
  TEAM_SCORE_HELP,
  ADMIN_KPI_HELP,
} from '@/lib/adminMetricHelp';
import type { MetricHelpInfo, MetricHelpMode } from '@/lib/adminMetricHelp';
import { scoreBucketColor } from '@/lib/scoreUtils';

const TEAL = '#0f766e';
const BLUE = '#2563eb';
const GREEN = '#047857';
const RED = '#ef4444';
const AMBER = '#b45309';
const SLATE_GRID = '#d8e0ea';

const LINE_ANIM = {
  isAnimationActive: true,
  animationDuration: 1000,
  animationEasing: 'ease-out' as const,
};

const FEEDBACK_SEGMENTS = [
  { key: 'envoye_attente' as const, label: 'En attente', color: '#64748b' },
  { key: 'recrute' as const, label: 'Recrutés', color: '#047857' },
  { key: 'non_integre' as const, label: 'Non intégrés', color: '#b91c1c' },
  { key: 'rejete' as const, label: 'Rejetés', color: '#b45309' },
  { key: 'valide_client' as const, label: 'Validé client', color: '#0f766e' },
  { key: 'non_valide_client' as const, label: 'Non validé client', color: '#991b1b' },
];

export interface ClientFeedbackCounts {
  envoye_attente?: number;
  recrute?: number;
  non_integre?: number;
  rejete?: number;
  valide_client?: number;
  non_valide_client?: number;
}

export interface ScoreBucket {
  range: string;
  count: number;
}

export interface RecruitingMember {
  id: string;
  full_name: string;
  offers_created: number;
  offers_assigned: number;
  avg_matching_score: number | null;
  matching_to_format_display: string | null;
  matching_to_format_hours: number | null;
  format_to_client_display: string | null;
  format_to_client_hours: number | null;
  candidates_validated: number;
  client_feedback: ClientFeedbackCounts;
  client_feedback_compact: string;
  hired_candidates: number;
  last_active: string | null;
}

export interface SourcingMember {
  id: string;
  full_name: string;
  offers_assigned: number;
  pipelines_launched: number;
  candidates_scored: number;
  avg_candidates_matched: number | null;
  avg_score: number | null;
  offers_completed_percent: number | null;
  last_active: string | null;
}

export interface TeamActivityData {
  total_recruiters: number;
  total_sourcers: number;
  recruiting_team: {
    aggregated: {
      total_offers_created: number;
      total_offers_assigned: number;
      avg_matching_to_format_hours: number | null;
      avg_matching_to_format_display: string | null;
      avg_format_to_client_hours: number | null;
      avg_format_to_client_display: string | null;
      candidates_validated: number;
      client_feedback: ClientFeedbackCounts;
      avg_matching_score: number | null;
    };
    charts: {
      offers_by_month: { month: string; created: number; assigned: number }[];
      pipeline_to_client_trend: {
        month: string;
        matching_to_format_hours: number | null;
        format_to_client_hours: number | null;
      }[];
      score_distribution: ScoreBucket[];
    };
    members: RecruitingMember[];
  };
  sourcing_team: {
    aggregated: {
      total_offers_assigned: number;
      total_pipelines_launched: number;
      pipelines_success_rate_percent: number | null;
      total_candidates_scored: number;
      avg_candidates_per_pipeline: number | null;
      avg_matching_score: number | null;
      offers_pending_launch: number;
    };
    charts: {
      pipelines_by_month: {
        month: string; launched: number; succeeded: number; failed: number;
      }[];
      candidates_scored_by_month: { month: string; count: number }[];
      score_distribution: ScoreBucket[];
    };
    members: SourcingMember[];
  };
}

type TeamView = 'recruiting' | 'sourcing';
type SortDir = 'asc' | 'desc';

function ChartSectionTitle({
  title, help,
}: {
  title: string;
  help?: MetricHelpInfo & { mode?: MetricHelpMode };
}) {
  return (
    <div className="flex items-center gap-1.5 mb-2">
      <h3 className="text-sm font-medium text-slate-700">{title}</h3>
      {help && <MetricHelp info={help} mode={help.mode ?? 'click'} />}
    </div>
  );
}

function ViewIntro({
  text, help,
}: {
  text: string;
  help: MetricHelpInfo & { mode?: MetricHelpMode };
}) {
  return (
    <p className="text-sm text-slate-600 flex items-start gap-1.5 -mt-2">
      <span className="flex-1">{text}</span>
      <MetricHelp info={help} mode={help.mode} className="mt-0.5" />
    </p>
  );
}

function TableHeaderLabel({
  label, help,
}: {
  label: string;
  help?: MetricHelpInfo & { mode?: MetricHelpMode };
}) {
  return (
    <th className="px-4 py-3 text-left">
      <div className="flex items-center gap-1">
        <span className="text-xs text-slate-600">{label}</span>
        {help && <MetricHelp info={help} mode={help.mode ?? 'hover'} />}
      </div>
    </th>
  );
}

function ChartTooltip({
  active, payload, label, valueFormatter,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
  valueFormatter?: (v: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const fmt = valueFormatter ?? formatCount;
  return (
    <div className="rounded-lg border border-[#d8e0ea] bg-[#0d1528] px-3 py-2 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }} className="font-medium">
          {p.name}: {fmt(p.value)}
        </p>
      ))}
    </div>
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

function SortHeader({
  label, col, sortCol, sortDir, onSort, help,
}: {
  label: string; col: string; sortCol: string; sortDir: SortDir;
  onSort: (c: string) => void;
  help?: MetricHelpInfo & { mode?: MetricHelpMode };
}) {
  const active = sortCol === col;
  const Icon = active ? (sortDir === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;
  return (
    <th className="px-4 py-3 text-left">
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onSort(col)}
          className="flex items-center gap-1 text-xs font-semibold text-[#2563eb] uppercase tracking-wide hover:text-[#1d4ed8]"
        >
          {label} <Icon className="h-3 w-3" />
        </button>
        {help && <MetricHelp info={help} mode={help.mode ?? 'hover'} />}
      </div>
    </th>
  );
}

function useSortable<T>(
  rows: T[],
  defaultCol: keyof T & string,
  resetKey: string,
) {
  const [col, setCol] = useState(defaultCol);
  const [dir, setDir] = useState<SortDir>('desc');
  const toggle = (c: string) => {
    if (c === col) setDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setCol(c as keyof T & string); setDir('desc'); }
  };
  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[col]; const bv = b[col];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'number' && typeof bv === 'number') {
        return dir === 'asc' ? av - bv : bv - av;
      }
      const as = String(av); const bs = String(bv);
      return dir === 'asc' ? as.localeCompare(bs) : bs.localeCompare(as);
    });
    return copy;
  }, [rows, col, dir, resetKey]);
  return { col, dir, toggle, sorted };
}

function ScoreDistributionChart({
  data, chartKey, reducedMotion,
}: {
  data: ScoreBucket[]; chartKey: string; reducedMotion: boolean;
}) {
  const chartData = data.map(d => ({ range: d.range, count: d.count }));
  const hasData = chartData.some(d => d.count > 0);
  if (!hasData) {
    return <p className="text-sm text-slate-600 p-4">Aucun score sur la période.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height="90%">
      <BarChart key={chartKey} data={chartData} layout="vertical" margin={{ left: 4, right: 16, top: 4 }}>
        <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} allowDecimals={false} />
        <YAxis type="category" dataKey="range" width={72} tick={{ fill: '#94a3b8', fontSize: 10 }} />
        <RechartsTooltip content={<ChartTooltip />} />
        <Bar dataKey="count" name="Candidats" radius={[0, 4, 4, 0]} {...(reducedMotion ? {} : LINE_ANIM)}>
          {chartData.map(entry => (
            <Cell key={entry.range} fill={scoreBucketColor(entry.range)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function TeamToggle({
  view, onChange, reducedMotion,
}: {
  view: TeamView; onChange: (v: TeamView) => void; reducedMotion: boolean;
}) {
  const tabs: { id: TeamView; label: string }[] = [
    { id: 'recruiting', label: 'Équipe Recrutement' },
    { id: 'sourcing', label: 'Équipe Sourcing' },
  ];
  return (
    <div className="inline-flex rounded-xl border border-[#d8e0ea] bg-white p-1 relative">
      {tabs.map(tab => {
        const active = view === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`relative z-10 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              active ? 'text-white' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {active && !reducedMotion && (
              <motion.span
                layoutId="team-activity-toggle"
                className="absolute inset-0 rounded-lg bg-[#2f66ed] border border-[#2f66ed]"
                transition={{ type: 'spring', stiffness: 400, damping: 30, duration: 0.3 }}
              />
            )}
            {active && reducedMotion && (
              <span className="absolute inset-0 rounded-lg bg-[#2f66ed] border border-[#2f66ed]" />
            )}
            <span className="relative">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function RecruitingView({
  team, animKey, toggleKey, reducedMotion,
}: {
  team: TeamActivityData['recruiting_team'];
  animKey: number;
  toggleKey: number;
  reducedMotion: boolean;
}) {
  const agg = team.aggregated;
  const kpiKey = animKey * 100 + toggleKey;
  const chartKey = `rec-${animKey}-${toggleKey}`;
  const recSort = useSortable(team.members, 'offers_created', chartKey);

  const offersChart = useMemo(() =>
    team.charts.offers_by_month.map(r => ({
      month: monthLabel(r.month),
      créées: r.created,
      assignées: r.assigned,
    })), [team.charts.offers_by_month]);

  const trendChart = useMemo(() =>
    team.charts.pipeline_to_client_trend.map(r => ({
      month: monthLabel(r.month),
      'Matching→Format': r.matching_to_format_hours ?? 0,
      'Format→Client': r.format_to_client_hours ?? 0,
    })), [team.charts.pipeline_to_client_trend]);

  const feedbackSegments = FEEDBACK_SEGMENTS.map(seg => ({
    label: seg.label,
    count: Number(agg.client_feedback[seg.key] ?? 0),
    color: seg.color,
  }));

  const members = recSort.sorted;

  const teamMaxHours = useMemo(() => ({
    m2f: Math.max(0, ...team.members.map(m => m.matching_to_format_hours ?? 0)),
    f2c: Math.max(0, ...team.members.map(m => m.format_to_client_hours ?? 0)),
  }), [team.members]);

  const maxValidated = useMemo(
    () => Math.max(1, ...team.members.map(m => m.candidates_validated ?? 0)),
    [team.members],
  );

  const recruiterCards = useMemo(() =>
    members.map(m => ({
      id: m.id,
      name: m.full_name,
      matchingToFormat: { display: m.matching_to_format_display, hours: m.matching_to_format_hours },
      formatToClient: { display: m.format_to_client_display, hours: m.format_to_client_hours },
      validated: m.candidates_validated ?? 0,
      feedbackSegments: FEEDBACK_SEGMENTS.map(seg => ({
        label: seg.label,
        count: Number(m.client_feedback?.[seg.key] ?? 0),
        color: seg.color,
      })),
    })), [members]);

  const delayChart = useMemo(() =>
    members.map(m => ({
      name: m.full_name,
      'Matching→Format': m.matching_to_format_hours ?? 0,
      'Format→Client': m.format_to_client_hours ?? 0,
    })), [members]);

  const validatedChart = useMemo(() =>
    [...members]
      .sort((a, b) => (b.candidates_validated ?? 0) - (a.candidates_validated ?? 0))
      .map(m => ({ name: m.full_name, validés: m.candidates_validated ?? 0 })),
    [members]);

  const feedbackChart = useMemo(() =>
    members.map(m => {
      const row: Record<string, string | number> = { name: m.full_name };
      FEEDBACK_SEGMENTS.forEach(seg => {
        row[seg.label] = Number(m.client_feedback?.[seg.key] ?? 0);
      });
      return row;
    }), [members]);

  const hasMembers = members.length > 0;

  return (
    <div className="space-y-6">
      <ViewIntro
        text="Performance agrégée de l'équipe recrutement : création d'offres, qualité des matchings, délais jusqu'au client."
        help={TEAM_RECRUITING_VIEW_HELP}
      />
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <AnimatedKpiCard label="Offres créées" rawValue={agg.total_offers_created} type="count" icon={Briefcase} border="border-[#2f66ed]" index={0} animKey={kpiKey} reducedMotion={reducedMotion} help={TEAM_RECRUITING_KPI_HELP.offers_created} />
        <AnimatedKpiCard label="Score moyen" rawValue={agg.avg_matching_score} type="percent" icon={Star} border="border-purple-500" index={1} animKey={kpiKey} reducedMotion={reducedMotion} help={TEAM_RECRUITING_KPI_HELP.avg_matching_score} />
        <AnimatedKpiCard label="Matching→Format" type="dash" displayText={agg.avg_matching_to_format_display ?? '—'} icon={Clock} border="border-amber-500" index={2} animKey={kpiKey} reducedMotion={reducedMotion} help={TEAM_RECRUITING_KPI_HELP.matching_to_format} />
        <AnimatedKpiCard label="Format→Client" type="dash" displayText={agg.avg_format_to_client_display ?? '—'} icon={TrendingUp} border="border-cyan-500" index={3} animKey={kpiKey} reducedMotion={reducedMotion} help={TEAM_RECRUITING_KPI_HELP.format_to_client} />
        <AnimatedKpiCard label="Candidats validés" rawValue={agg.candidates_validated} type="count" icon={UserCheck} border="border-green-500" index={4} animKey={kpiKey} reducedMotion={reducedMotion} help={TEAM_RECRUITING_KPI_HELP.candidates_validated} />
      </div>

      <div className="rounded-2xl border border-[#d8e0ea] bg-white p-6 space-y-3">
        <div className="flex items-center gap-2">
          <BarChart2 className="h-4 w-4 text-purple-700" />
          <h3 className="text-sm font-semibold text-slate-700">Retour client</h3>
          <MetricHelp info={TEAM_CLIENT_FEEDBACK_HELP} mode={TEAM_CLIENT_FEEDBACK_HELP.mode} />
        </div>
        <StackedProgressBar segments={feedbackSegments} reducedMotion={reducedMotion} />
      </div>

      <div className="grid lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 rounded-2xl border border-[#d8e0ea] bg-white p-4 h-72">
          <ChartSectionTitle title="Offres par mois" help={TEAM_CHART_HELP.offers_by_month} />
          {offersChart.length === 0 ? (
            <p className="text-sm text-slate-600">Aucune offre sur la période.</p>
          ) : (
            <ResponsiveContainer width="100%" height="90%">
              <LineChart key={`${chartKey}-offers`} data={offersChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} allowDecimals={false} />
                <RechartsTooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
                <Line type="monotone" dataKey="créées" name="Offres créées" stroke={TEAL} strokeWidth={2} dot={{ r: 3 }} {...(reducedMotion ? {} : LINE_ANIM)} />
                <Line type="monotone" dataKey="assignées" name="Assignées" stroke={BLUE} strokeWidth={2} dot={{ r: 3 }} {...(reducedMotion ? {} : LINE_ANIM)} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="lg:col-span-2 rounded-2xl border border-[#d8e0ea] bg-white p-4 h-72">
          <ChartSectionTitle title="Distribution des scores" help={TEAM_CHART_HELP.score_distribution_recruiting} />
          <ScoreDistributionChart data={team.charts.score_distribution} chartKey={`${chartKey}-scores`} reducedMotion={reducedMotion} />
        </div>
      </div>

      <div className="rounded-2xl border border-[#d8e0ea] bg-white p-4 h-72">
        <ChartSectionTitle title="Délais pipeline → client (heures)" help={TEAM_CHART_HELP.pipeline_to_client_trend} />
        {trendChart.length === 0 ? (
          <p className="text-sm text-slate-600">Aucune donnée sur la période.</p>
        ) : (
          <ResponsiveContainer width="100%" height="90%">
            <LineChart key={`${chartKey}-trend`} data={trendChart} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis yAxisId="left" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <RechartsTooltip content={<ChartTooltip valueFormatter={v => formatHours(v)} />} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
              <Line yAxisId="left" type="monotone" dataKey="Matching→Format" stroke={TEAL} strokeWidth={2} dot={{ r: 3 }} {...(reducedMotion ? {} : LINE_ANIM)} />
              <Line yAxisId="right" type="monotone" dataKey="Format→Client" stroke={GREEN} strokeWidth={2} dot={{ r: 3 }} {...(reducedMotion ? {} : LINE_ANIM)} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Row 1 — simplified table */}
      <div className="rounded-2xl border border-[#d8e0ea] overflow-hidden">
        <div className="px-4 py-3 border-b border-[#d8e0ea] bg-blue-50">
          <h3 className="text-sm font-semibold text-[#2563eb]">Par recruteur</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <SortHeader label="Nom" col="full_name" sortCol={recSort.col} sortDir={recSort.dir} onSort={recSort.toggle} />
                <SortHeader label="Créées" col="offers_created" sortCol={recSort.col} sortDir={recSort.dir} onSort={recSort.toggle} help={TEAM_RECRUITING_KPI_HELP.offers_created} />
                <SortHeader label="Score" col="avg_matching_score" sortCol={recSort.col} sortDir={recSort.dir} onSort={recSort.toggle} help={TEAM_RECRUITING_KPI_HELP.avg_matching_score} />
                <SortHeader label="Recrutés" col="hired_candidates" sortCol={recSort.col} sortDir={recSort.dir} onSort={recSort.toggle} help={ADMIN_KPI_HELP.hired} />
                <TableHeaderLabel label="Dernière activité" help={TEAM_TABLE_HELP.rec_last_active} />
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5ebf2]">
              {!hasMembers && (
                <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-600">Aucun recruteur</td></tr>
              )}
              {members.map((r, i) => (
                <AnimatedTableRow key={r.id} index={i} reducedMotion={reducedMotion} className="hover:bg-white">
                  <td className="px-4 py-3 text-slate-900 font-medium">{r.full_name}</td>
                  <td className="px-4 py-3 text-slate-600">{r.offers_created}</td>
                  <td className="px-4 py-3 text-slate-600">{formatPercent(r.avg_matching_score)}</td>
                  <td className="px-4 py-3 text-emerald-700">{r.hired_candidates}</td>
                  <td className="px-4 py-3 text-slate-600 text-xs">{r.last_active ?? '—'}</td>
                </AnimatedTableRow>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Row 2 — per-recruiter comparison cards */}
      {hasMembers && (
        <div>
          <ChartSectionTitle title="Délais & validations par recruteur" help={TEAM_RECRUITING_CARDS_HELP} />
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {recruiterCards.map((card, i) => (
              <RecruiterKpiCard
                key={card.id}
                data={card}
                teamMaxHours={teamMaxHours}
                maxValidated={maxValidated}
                index={i}
                reducedMotion={reducedMotion}
                animKey={chartKey}
              />
            ))}
          </div>
        </div>
      )}

      {/* Row 3 — comparison charts */}
      {hasMembers && (
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="rounded-2xl border border-[#d8e0ea] bg-white p-4 h-80">
            <ChartSectionTitle title="M→F et F→Client par recruteur" help={TEAM_CHART_HELP.pipeline_to_client_trend} />
            <ResponsiveContainer width="100%" height="90%">
              <BarChart key={`${chartKey}-delays`} data={delayChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} interval={0} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <RechartsTooltip content={<ChartTooltip valueFormatter={v => formatHours(v)} />} />
                <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
                <Bar dataKey="Matching→Format" fill={TEAL} radius={[4, 4, 0, 0]} {...(reducedMotion ? {} : LINE_ANIM)} />
                <Bar dataKey="Format→Client" fill={BLUE} radius={[4, 4, 0, 0]} {...(reducedMotion ? {} : LINE_ANIM)} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="rounded-2xl border border-[#d8e0ea] bg-white p-4 h-80">
            <ChartSectionTitle title="Candidats validés par recruteur" help={TEAM_RECRUITING_KPI_HELP.candidates_validated} />
            <ResponsiveContainer width="100%" height="90%">
              <BarChart key={`${chartKey}-validated`} data={validatedChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="validatedGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={GREEN} stopOpacity={0.95} />
                    <stop offset="95%" stopColor={GREEN} stopOpacity={0.4} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} interval={0} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} allowDecimals={false} />
                <RechartsTooltip content={<ChartTooltip />} />
                <Bar dataKey="validés" name="Candidats validés" fill="url(#validatedGradient)" radius={[4, 4, 0, 0]} {...(reducedMotion ? {} : LINE_ANIM)} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Row 4 — retour client stacked chart */}
      {hasMembers && (
        <div className="rounded-2xl border border-[#d8e0ea] bg-white p-4 h-80">
          <ChartSectionTitle title="Retour client par recruteur" help={TEAM_CLIENT_FEEDBACK_HELP} />
          <ResponsiveContainer width="100%" height="88%">
            <BarChart key={`${chartKey}-feedback`} data={feedbackChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} interval={0} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} allowDecimals={false} />
              <RechartsTooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
              {FEEDBACK_SEGMENTS.map(seg => (
                <Bar key={seg.key} dataKey={seg.label} stackId="feedback" fill={seg.color} {...(reducedMotion ? {} : LINE_ANIM)} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function SourcingView({
  team, animKey, toggleKey, reducedMotion,
}: {
  team: TeamActivityData['sourcing_team'];
  animKey: number;
  toggleKey: number;
  reducedMotion: boolean;
}) {
  const agg = team.aggregated;
  const kpiKey = animKey * 100 + toggleKey;
  const chartKey = `src-${animKey}-${toggleKey}`;
  const srcSort = useSortable(team.members, 'pipelines_launched', chartKey);

  const pipelinesChart = useMemo(() =>
    team.charts.pipelines_by_month.map(r => ({
      month: monthLabel(r.month),
      Lancés: r.launched,
      Réussis: r.succeeded,
      Échoués: r.failed,
    })), [team.charts.pipelines_by_month]);

  const scoredChart = useMemo(() =>
    team.charts.candidates_scored_by_month.map(r => ({
      month: monthLabel(r.month),
      count: r.count,
    })), [team.charts.candidates_scored_by_month]);

  return (
    <div className="space-y-6">
      <ViewIntro
        text="Performance agrégée de l'équipe sourcing : volume de pipelines, fiabilité technique et productivité de scoring."
        help={TEAM_SOURCING_VIEW_HELP}
      />
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <AnimatedKpiCard label="Offres assignées" rawValue={agg.total_offers_assigned} type="count" icon={Briefcase} border="border-[#2f66ed]" index={0} animKey={kpiKey} reducedMotion={reducedMotion} help={TEAM_SOURCING_KPI_HELP.offers_assigned} />
        <AnimatedKpiCard label="Pipelines lancés" rawValue={agg.total_pipelines_launched} type="count" icon={Target} border="border-blue-500" index={1} animKey={kpiKey} reducedMotion={reducedMotion} help={TEAM_SOURCING_KPI_HELP.pipelines_launched} />
        <AnimatedKpiCard label="Taux de succès" rawValue={agg.pipelines_success_rate_percent} type="percent" icon={CheckCircle2} border="border-green-500" index={2} animKey={kpiKey} reducedMotion={reducedMotion} help={TEAM_SOURCING_KPI_HELP.success_rate} />
        <AnimatedKpiCard label="Candidats scorés" rawValue={agg.total_candidates_scored} type="count" icon={Users} border="border-purple-500" index={3} animKey={kpiKey} reducedMotion={reducedMotion} help={TEAM_SOURCING_KPI_HELP.candidates_scored} />
        <AnimatedKpiCard label="Score moyen" rawValue={agg.avg_matching_score} type="percent" icon={Star} border="border-amber-500" index={4} animKey={kpiKey} reducedMotion={reducedMotion} help={TEAM_SOURCING_KPI_HELP.avg_matching_score} sub={agg.avg_candidates_per_pipeline != null ? `${agg.avg_candidates_per_pipeline} / pipeline` : undefined} />
      </div>

      <div className="grid lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 rounded-2xl border border-[#d8e0ea] bg-white p-4 h-72">
          <ChartSectionTitle title="Pipelines par mois" help={TEAM_CHART_HELP.pipelines_by_month} />
          {pipelinesChart.length === 0 ? (
            <p className="text-sm text-slate-600">Aucun pipeline sur la période.</p>
          ) : (
            <ResponsiveContainer width="100%" height="90%">
              <BarChart key={`${chartKey}-pipelines`} data={pipelinesChart} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} allowDecimals={false} />
                <RechartsTooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
                <Bar dataKey="Lancés" fill={TEAL} radius={[4, 4, 0, 0]} {...(reducedMotion ? {} : LINE_ANIM)} />
                <Bar dataKey="Réussis" fill={GREEN} radius={[4, 4, 0, 0]} {...(reducedMotion ? {} : LINE_ANIM)} />
                <Bar dataKey="Échoués" fill={RED} radius={[4, 4, 0, 0]} {...(reducedMotion ? {} : LINE_ANIM)} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="lg:col-span-2 rounded-2xl border border-[#d8e0ea] bg-white p-4 h-72">
          <ChartSectionTitle title="Distribution des scores" help={TEAM_CHART_HELP.score_distribution_sourcing} />
          <ScoreDistributionChart data={team.charts.score_distribution} chartKey={`${chartKey}-scores`} reducedMotion={reducedMotion} />
        </div>
      </div>

      <div className="rounded-2xl border border-[#d8e0ea] bg-white p-4 h-64">
        <ChartSectionTitle title="Candidats scorés par mois" help={TEAM_CHART_HELP.candidates_scored_by_month} />
        {scoredChart.length === 0 ? (
          <p className="text-sm text-slate-600">Aucun candidat scoré.</p>
        ) : (
          <ResponsiveContainer width="100%" height="90%">
            <LineChart key={`${chartKey}-scored`} data={scoredChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="scoredGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={TEAL} stopOpacity={0.35} />
                  <stop offset="95%" stopColor={TEAL} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={SLATE_GRID} strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} allowDecimals={false} />
              <RechartsTooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="count" name="Candidats scorés" stroke={TEAL} fill="url(#scoredGradient)" strokeWidth={2} {...(reducedMotion ? {} : LINE_ANIM)} />
              <Line type="monotone" dataKey="count" stroke={TEAL} strokeWidth={2} dot={{ r: 4, fill: TEAL }} {...(reducedMotion ? {} : LINE_ANIM)} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="rounded-2xl border border-[#d8e0ea] overflow-hidden">
        <div className="px-4 py-3 border-b border-[#d8e0ea] bg-blue-50">
          <h3 className="text-sm font-semibold text-blue-700">Par sourceur</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <SortHeader label="Nom" col="full_name" sortCol={srcSort.col} sortDir={srcSort.dir} onSort={srcSort.toggle} />
                <SortHeader label="Assignées" col="offers_assigned" sortCol={srcSort.col} sortDir={srcSort.dir} onSort={srcSort.toggle} help={TEAM_SOURCING_KPI_HELP.offers_assigned} />
                <SortHeader label="Pipelines" col="pipelines_launched" sortCol={srcSort.col} sortDir={srcSort.dir} onSort={srcSort.toggle} help={TEAM_SOURCING_KPI_HELP.pipelines_launched} />
                <SortHeader label="Moy. candidats" col="avg_candidates_matched" sortCol={srcSort.col} sortDir={srcSort.dir} onSort={srcSort.toggle} help={TEAM_TABLE_HELP.src_avg_candidates_matched} />
                <SortHeader label="Score" col="avg_score" sortCol={srcSort.col} sortDir={srcSort.dir} onSort={srcSort.toggle} help={TEAM_SCORE_HELP} />
                <SortHeader label="% traitées" col="offers_completed_percent" sortCol={srcSort.col} sortDir={srcSort.dir} onSort={srcSort.toggle} help={TEAM_TABLE_HELP.src_offers_completed} />
                <TableHeaderLabel label="Dernière activité" help={TEAM_TABLE_HELP.src_last_active} />
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5ebf2]">
              {srcSort.sorted.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-600">Aucun sourceur</td></tr>
              )}
              {srcSort.sorted.map((s, i) => (
                <AnimatedTableRow key={s.id} index={i} reducedMotion={reducedMotion} className="hover:bg-white">
                  <td className="px-4 py-3 text-slate-900 font-medium">{s.full_name}</td>
                  <td className="px-4 py-3 text-slate-600">{s.offers_assigned}</td>
                  <td className="px-4 py-3 text-slate-600">{s.pipelines_launched}</td>
                  <td className="px-4 py-3 text-slate-600">{s.avg_candidates_matched ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-600">{formatPercent(s.avg_score)}</td>
                  <td className="px-4 py-3 text-slate-600">{formatPercent(s.offers_completed_percent)}</td>
                  <td className="px-4 py-3 text-slate-600 text-xs">{s.last_active ?? '—'}</td>
                </AnimatedTableRow>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

interface Props {
  team: TeamActivityData;
  animKey: number;
  reducedMotion: boolean;
}

export function TeamActivitySection({ team, animKey, reducedMotion }: Props) {
  const [view, setView] = useState<TeamView>('recruiting');
  const [toggleKey, setToggleKey] = useState(0);

  const handleToggle = (v: TeamView) => {
    if (v !== view) {
      setView(v);
      setToggleKey(k => k + 1);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-1.5 text-sm text-slate-600">
          <span>
            {team.total_recruiters} recruteur{team.total_recruiters > 1 ? 's' : ''} · {team.total_sourcers} sourceur{team.total_sourcers > 1 ? 's' : ''}
          </span>
          <MetricHelp info={TEAM_ACTIVITY_SECTION_HELP} mode={TEAM_ACTIVITY_SECTION_HELP.mode} />
        </div>
        <TeamToggle view={view} onChange={handleToggle} reducedMotion={reducedMotion} />
      </div>

      <motion.div
        key={`${view}-${toggleKey}`}
        initial={reducedMotion ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: reducedMotion ? 0 : 0.3 }}
      >
        {view === 'recruiting' ? (
          <RecruitingView
            team={team.recruiting_team}
            animKey={animKey}
            toggleKey={toggleKey}
            reducedMotion={reducedMotion}
          />
        ) : (
          <SourcingView
            team={team.sourcing_team}
            animKey={animKey}
            toggleKey={toggleKey}
            reducedMotion={reducedMotion}
          />
        )}
      </motion.div>
    </div>
  );
}



