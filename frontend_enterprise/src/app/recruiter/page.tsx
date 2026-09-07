'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import Link from 'next/link';
import {
  BarChart2, Briefcase, CheckCircle2, Clock, FileText,
  Loader2, Play, PlusCircle, RefreshCw, Star, TrendingUp,
  UserCheck, Users, UserPlus, XCircle,
} from 'lucide-react';
import { AnimatedKpiCard } from '@/components/admin/AnimatedKpiCard';
import { ClientFeedbackKpiCard } from '@/components/ClientFeedbackKpiCard';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';
import { recruiterOffersUrl } from '@/lib/offerStatusRoutes';
import { RECRUITER_KPI_HELP } from '@/lib/spaceMetricHelp';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

function ratioLabel(value: number, total: number, suffix: string): string {
  if (total <= 0) return '—';
  const p = Math.min(100, Math.round((value / total) * 100));
  return `${p}% ${suffix}`;
}

interface Dashboard {
  offers_by_stage: Record<string, number>;
  total_offers: number;
  pipelines_launched: number;
  pipelines_completed: number;
  pipelines_running: number;
  pipelines_failed: number;
  total_cvs_scored: number;
  average_matching_score: number | null;
  unassigned_offers_count: number;
  candidates_seen: number;
  candidates_shortlisted: number;
  candidates_in_process: number;
  candidates_hired: number;
  top_sourcer: {
    full_name: string;
    completed_pipelines: number;
    assignment_count?: number;
  } | null;
  recent_activity: Array<{
    type: string;
    description: string;
    timestamp: string;
  }>;
}

interface RecruiterKpis {
  avg_matching_to_format_hours: number | null;
  avg_matching_to_format_display: string | null;
  avg_format_to_client_hours: number | null;
  avg_format_to_client_display: string | null;
  candidates_selected_validated: number;
  client_feedback: {
    envoye_attente: number;
    recrute: number;
    non_integre: number;
    rejete: number;
    valide_client: number;
    non_valide_client: number;
    total_with_feedback: number;
  };
  client_feedback_display: string;
}

const STAGE_CHIPS: { key: string; label: string; color: string }[] = [
  { key: 'open',         label: 'Ouverte',        color: 'bg-slate-400/10 text-slate-300 border-slate-400/20' },
  { key: 'assigned',     label: 'Assignée',       color: 'bg-teal-400/10 text-teal-400 border-teal-400/20' },
  { key: 'in_progress',  label: 'En cours',       color: 'bg-blue-400/10 text-blue-400 border-blue-400/20' },
  { key: 'matched',      label: 'Matchée',        color: 'bg-indigo-400/10 text-indigo-400 border-indigo-400/20' },
  { key: 'final_result', label: 'Résultat final', color: 'bg-purple-400/10 text-purple-400 border-purple-400/20' },
  { key: 'formatted',    label: 'Formatée',       color: 'bg-cyan-400/10 text-cyan-400 border-cyan-400/20' },
  { key: 'archived',     label: 'Archivée',       color: 'bg-amber-400/10 text-amber-400 border-amber-400/20' },
];

const SECTION_VIEW = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-100px' },
  transition: { duration: 0.5, ease: 'easeOut' as const },
};

const CARD_REVEAL = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, ease: 'easeOut' as const },
};

function relTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 2) return "à l'instant";
  if (mins < 60) return `il y a ${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `il y a ${hrs} h`;
  if (hrs < 48) return 'hier';
  return new Date(iso).toLocaleDateString('fr-FR');
}

function Section({
  children, reducedMotion, className,
}: {
  children: React.ReactNode; reducedMotion: boolean; className?: string;
}) {
  return (
    <motion.section
      className={className}
      initial={reducedMotion ? false : SECTION_VIEW.initial}
      whileInView={SECTION_VIEW.whileInView}
      viewport={SECTION_VIEW.viewport}
      transition={SECTION_VIEW.transition}
    >
      {children}
    </motion.section>
  );
}

function AnimatedFeedRow({
  index, reducedMotion, children,
}: {
  index: number; reducedMotion: boolean; children: React.ReactNode;
}) {
  return (
    <motion.li
      className="flex items-center gap-4 px-6 py-4 hover:bg-slate-50 transition-colors"
      initial={reducedMotion ? false : { opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, delay: reducedMotion ? 0 : index * 0.05, ease: 'easeOut' }}
    >
      {children}
    </motion.li>
  );
}

const activityIcon: Record<string, React.ReactNode> = {
  offer_created:    <FileText className="h-4 w-4 text-indigo-400 flex-shrink-0" />,
  offer_assigned:   <UserCheck className="h-4 w-4 text-teal-400 flex-shrink-0" />,
  offer_archived:   <FileText className="h-4 w-4 text-amber-400 flex-shrink-0" />,
  offer_deleted:    <XCircle className="h-4 w-4 text-red-400 flex-shrink-0" />,
  pipeline_completed: <CheckCircle2 className="h-4 w-4 text-green-400 flex-shrink-0" />,
  pipeline_failed:  <XCircle className="h-4 w-4 text-red-400 flex-shrink-0" />,
};

const dotColor: Record<string, string> = {
  offer_created: 'bg-indigo-400',
  offer_assigned: 'bg-teal-400',
  offer_archived: 'bg-amber-400',
  offer_deleted: 'bg-red-400',
  pipeline_completed: 'bg-green-400',
  pipeline_failed: 'bg-red-400',
};

function DashboardActionFooter({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <div className="flex flex-wrap gap-3 pt-2">
      <Link href="/recruiter/offers/new" className="flex-1 min-w-[140px]">
        <motion.span
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-semibold transition-all cursor-pointer"
          animate={reducedMotion ? undefined : { scale: [1, 1.02, 1] }}
          transition={{ delay: 1, duration: 0.4 }}
        >
          <PlusCircle className="h-4 w-4" /> Créer une offre
        </motion.span>
      </Link>
      <Link href="/recruiter/offers" className="flex-1 min-w-[140px]">
        <motion.span
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg border border-[#d8e0ea] bg-white text-slate-700 hover:border-[#2f66ed]/40 hover:text-[#2f66ed] text-sm transition-all cursor-pointer"
          animate={reducedMotion ? undefined : { scale: [1, 1.02, 1] }}
          transition={{ delay: 1, duration: 0.4 }}
        >
          <Briefcase className="h-4 w-4" /> Mes offres
        </motion.span>
      </Link>
      <Link href="/recruiter/candidates" className="flex-1 min-w-[140px]">
        <span className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg border border-[#d8e0ea] bg-white text-slate-700 hover:border-[#2f66ed]/40 hover:text-[#2f66ed] text-sm transition-all cursor-pointer">
          <Users className="h-4 w-4" /> Candidats
        </span>
      </Link>
    </div>
  );
}

export default function RecruiterDashboardPage() {
  const [userName, setUserName] = useState('');
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [kpis, setKpis] = useState<RecruiterKpis | null>(null);
  const [loading, setLoading] = useState(true);
  const [animKey, setAnimKey] = useState(0);
  const reducedMotion = usePrefersReducedMotion();

  const fetchData = () => {
    setLoading(true);
    Promise.all([
      fetch(`${API_BASE}/auth/me`, { credentials: 'include' }).then(r => r.ok ? r.json() : null),
      fetch(`${API_BASE}/recruiter/dashboard`, { credentials: 'include' }).then(r => r.ok ? r.json() : null),
      fetch(`${API_BASE}/recruiter/kpis`, { credentials: 'include' }).then(r => r.ok ? r.json() : null),
    ]).then(([me, dashboard, kpiData]) => {
      if (me) setUserName(me.full_name);
      setDash(dashboard);
      setKpis(kpiData);
      if (dashboard || kpiData) setAnimKey(k => k + 1);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, []);

  const stage = dash?.offers_by_stage ?? {};

  return (
    <div className="w-full max-w-7xl space-y-7">
      <div className="flex items-center justify-between">
        <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase text-[#2f66ed]">Espace recruteur</p>
          <h1 className="mt-2 text-4xl font-semibold text-slate-950">Tableau de bord</h1>
          <p className="mt-2 text-lg text-slate-600">Vue d&apos;ensemble de votre activité de recrutement</p>
        </div>
        <button onClick={fetchData}
          className="flex items-center gap-2 rounded-lg border border-[#d8e0ea] bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:border-[#2f66ed]/40 hover:text-[#2f66ed]">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Actualiser
        </button>
        </div>
      </div>

      {userName && (
        <p className="text-sm text-slate-600">
          Bonjour, <span className="font-semibold text-slate-950">{userName}</span> 
        </p>
      )}

      {loading && (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
        </div>
      )}

      {!loading && !dash && (
        <div className="admin-light-card rounded-xl p-8 text-center text-slate-500">
          <p className="font-medium">Aucune donnée disponible</p>
          <p className="text-sm mt-1">Créez votre première offre pour commencer</p>
          <Link href="/recruiter/offers/new">
            <button className="mt-4 px-4 py-2 rounded-lg bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm transition-all">
              Créer une offre
            </button>
          </Link>
        </div>
      )}

      {!loading && dash && (
        <>
          <Section reducedMotion={reducedMotion} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <AnimatedKpiCard
              label="Offres créées"
              rawValue={dash.total_offers}
              type="count"
              icon={Briefcase}
              border="border-[#1f9d94]"
              index={0}
              animKey={animKey}
              reducedMotion={reducedMotion}
              variant="space"
              help={RECRUITER_KPI_HELP.offers_created}
              sub={
                dash.unassigned_offers_count > 0
                  ? <span><span className="text-amber-400">{dash.unassigned_offers_count}</span> sans assignation</span>
                  : 'Toutes assignées'
              }
            />
            <AnimatedKpiCard
              label="Pipelines terminés"
              rawValue={dash.pipelines_completed}
              type="count"
              icon={CheckCircle2}
              border="border-green-500"
              index={1}
              animKey={animKey}
              reducedMotion={reducedMotion}
              variant="space"
              help={RECRUITER_KPI_HELP.pipelines_completed}
              ratio={{
                value: dash.pipelines_completed,
                total: dash.total_offers,
                label: ratioLabel(dash.pipelines_completed, dash.total_offers, 'des offres traitées'),
                colorScheme: 'positive',
              }}
              sub={
                dash.pipelines_running > 0
                  ? <span><span className="text-blue-400">{dash.pipelines_running}</span> en cours{dash.pipelines_failed > 0 ? <>, <span className="text-red-400">{dash.pipelines_failed}</span> échoué{dash.pipelines_failed > 1 ? 's' : ''}</> : null}</span>
                  : dash.pipelines_launched > 0 ? `${dash.pipelines_launched} lancé${dash.pipelines_launched > 1 ? 's' : ''}` : 'Aucun pipeline'
              }
            />
            <AnimatedKpiCard
              label="Candidats scorés"
              rawValue={dash.total_cvs_scored}
              type="count"
              icon={Users}
              border="border-blue-500"
              index={2}
              animKey={animKey}
              reducedMotion={reducedMotion}
              variant="space"
              help={RECRUITER_KPI_HELP.candidates_scored}
              sub={
                dash.candidates_seen > 0
                  ? <span><span className="text-slate-300">{dash.candidates_seen}</span> profil{dash.candidates_seen > 1 ? 's' : ''} distinct{dash.candidates_seen > 1 ? 's' : ''}</span>
                  : 'Disponible après matching'
              }
            />
            <AnimatedKpiCard
              label="Score moyen"
              rawValue={dash.average_matching_score}
              type="percent"
              icon={Star}
              border="border-purple-500"
              index={3}
              animKey={animKey}
              reducedMotion={reducedMotion}
              variant="space"
              help={RECRUITER_KPI_HELP.avg_matching_score}
              sub={dash.average_matching_score === null ? 'Basé sur les apparitions' : 'Moyenne des scores IA'}
            />
          </Section>

          <Section reducedMotion={reducedMotion} className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <AnimatedKpiCard
              label="Présélectionnés"
              rawValue={dash.candidates_shortlisted}
              type="count"
              icon={UserPlus}
              border="border-blue-400"
              index={4}
              animKey={animKey}
              reducedMotion={reducedMotion}
              variant="space"
              help={RECRUITER_KPI_HELP.shortlisted}
              ratio={{
                value: dash.candidates_shortlisted,
                total: dash.total_cvs_scored,
                label: ratioLabel(dash.candidates_shortlisted, dash.total_cvs_scored, 'des candidats scorés'),
                colorScheme: 'positive',
              }}
              sub="statut présélectionné"
            />
            <AnimatedKpiCard
              label="En process"
              rawValue={dash.candidates_in_process}
              type="count"
              icon={Play}
              border="border-cyan-500"
              index={5}
              animKey={animKey}
              reducedMotion={reducedMotion}
              variant="space"
              help={RECRUITER_KPI_HELP.in_process}
              ratio={{
                value: dash.candidates_in_process,
                total: dash.total_cvs_scored,
                label: ratioLabel(dash.candidates_in_process, dash.total_cvs_scored, 'en cours de traitement'),
                colorScheme: 'neutral',
              }}
              sub="contactés · interviewés"
            />
            <AnimatedKpiCard
              label="Candidats validés"
              rawValue={kpis?.candidates_selected_validated ?? null}
              type="count"
              icon={UserCheck}
              border="border-emerald-500"
              index={6}
              animKey={animKey}
              reducedMotion={reducedMotion}
              variant="space"
              help={RECRUITER_KPI_HELP.candidates_validated}
              ratio={{
                value: kpis?.candidates_selected_validated ?? 0,
                total: dash.total_cvs_scored,
                label: ratioLabel(kpis?.candidates_selected_validated ?? 0, dash.total_cvs_scored, 'validés'),
                colorScheme: 'positive',
              }}
              sub="sélectionnés ou validés"
            />
          </Section>

          {kpis && (
            <Section reducedMotion={reducedMotion} className="space-y-3">
              <h2 className="text-base font-semibold text-slate-950">Indicateurs de performance</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <AnimatedKpiCard
                  label="Matching → Formatage"
                  type="dash"
                  displayText={kpis.avg_matching_to_format_display ?? '—'}
                  icon={Clock}
                  border="border-amber-500"
                  index={7}
                  animKey={animKey}
                  reducedMotion={reducedMotion}
                  variant="space"
                  help={RECRUITER_KPI_HELP.matching_to_format}
                  sub="délai moyen par offre"
                />
                <AnimatedKpiCard
                  label="Formatage → Envoi client"
                  type="dash"
                  displayText={kpis.avg_format_to_client_display ?? '—'}
                  icon={TrendingUp}
                  border="border-cyan-500"
                  index={8}
                  animKey={animKey}
                  reducedMotion={reducedMotion}
                  variant="space"
                  help={RECRUITER_KPI_HELP.format_to_client}
                  sub="après formatage terminé"
                />
                <AnimatedKpiCard
                  label="Recrutés"
                  rawValue={dash.candidates_hired}
                  type="count"
                  icon={UserCheck}
                  border="border-emerald-500"
                  index={9}
                  animKey={animKey}
                  reducedMotion={reducedMotion}
                  variant="space"
                  help={RECRUITER_KPI_HELP.hired}
                  ratio={{
                    value: dash.candidates_hired,
                    total: dash.total_cvs_scored,
                    label: ratioLabel(dash.candidates_hired, dash.total_cvs_scored, 'taux de recrutement'),
                    colorScheme: 'positive',
                  }}
                  sub="embauches confirmées"
                />
                <ClientFeedbackKpiCard
                  feedback={kpis.client_feedback}
                  index={10}
                  reducedMotion={reducedMotion}
                  help={RECRUITER_KPI_HELP.client_feedback}
                />
              </div>
            </Section>
          )}

          <Section reducedMotion={reducedMotion} className="grid lg:grid-cols-3 gap-4">
            <motion.div
              className="lg:col-span-2 admin-light-card rounded-xl p-6"
              initial={reducedMotion ? false : CARD_REVEAL.initial}
              animate={CARD_REVEAL.animate}
              transition={{ ...CARD_REVEAL.transition, delay: reducedMotion ? 0 : 0.7 }}
            >
              <h2 className="text-base font-semibold text-slate-950 mb-4">Cycle de vie des offres</h2>
              <div className="flex flex-wrap gap-3">
                {STAGE_CHIPS.map(({ key, label, color }) => {
                  const count = stage[key] ?? 0;
                  return (
                    <Link key={key} href={recruiterOffersUrl(key)}>
                      <motion.span
                        whileHover={reducedMotion ? undefined : { scale: 1.05 }}
                        transition={{ duration: 0.15 }}
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-medium cursor-pointer ${color}`}
                      >
                        {label} <span className="font-bold">{count}</span>
                      </motion.span>
                    </Link>
                  );
                })}
              </div>
            </motion.div>

            <motion.div
              className="admin-light-card rounded-xl p-6 space-y-4"
              initial={reducedMotion ? false : CARD_REVEAL.initial}
              animate={CARD_REVEAL.animate}
              transition={{ ...CARD_REVEAL.transition, delay: reducedMotion ? 0 : 0.8 }}
            >
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-green-400" />
                <h2 className="text-base font-semibold text-slate-950">Top sourceur</h2>
              </div>
              {dash.top_sourcer ? (
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-teal-500/20 flex items-center justify-center">
                    <span className="text-teal-400 font-bold text-sm">
                      {dash.top_sourcer.full_name.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <p className="font-semibold text-slate-950 text-sm">{dash.top_sourcer.full_name}</p>
                    <p className="text-xs text-slate-400">
                      {dash.top_sourcer.completed_pipelines > 0
                        ? `${dash.top_sourcer.completed_pipelines} pipeline${dash.top_sourcer.completed_pipelines > 1 ? 's' : ''} terminé${dash.top_sourcer.completed_pipelines > 1 ? 's' : ''}`
                        : `${dash.top_sourcer.assignment_count ?? 0} offre${(dash.top_sourcer.assignment_count ?? 0) > 1 ? 's' : ''} assignée${(dash.top_sourcer.assignment_count ?? 0) > 1 ? 's' : ''}`}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-slate-500 text-sm">Aucun sourceur assigné</p>
              )}
              {dash.unassigned_offers_count > 0 && (
                <Link href={recruiterOffersUrl('open')}>
                  <p className="text-xs text-amber-400 hover:text-amber-300 transition-colors">
                    {dash.unassigned_offers_count} offre{dash.unassigned_offers_count > 1 ? 's' : ''} à assigner →
                  </p>
                </Link>
              )}
            </motion.div>
          </Section>

          <div className="admin-light-card overflow-hidden rounded-xl">
            <div className="border-b border-[#d8e0ea] px-6 py-4">
              <h2 className="text-base font-semibold text-slate-950">Activité récente</h2>
            </div>
            {dash.recent_activity.length > 0 ? (
              <ul className="divide-y divide-[#e5ebf2]">
                {dash.recent_activity.map((item, i) => (
                  <AnimatedFeedRow key={i} index={i} reducedMotion={reducedMotion}>
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColor[item.type] || 'bg-slate-400'}`} />
                    {activityIcon[item.type] ?? <BarChart2 className="h-4 w-4 text-slate-400 flex-shrink-0" />}
                    <p className="flex-1 text-sm text-slate-600 min-w-0 truncate">{item.description}</p>
                    <span className="text-xs text-slate-500 flex-shrink-0">{relTime(item.timestamp)}</span>
                  </AnimatedFeedRow>
                ))}
              </ul>
            ) : (
              <div className="px-6 py-8 text-center text-slate-500 flex flex-col items-center gap-2">
                <Clock className="h-8 w-8 opacity-30" />
                <p className="text-sm font-medium">Aucune activité récente</p>
              </div>
            )}
          </div>

          <DashboardActionFooter reducedMotion={reducedMotion} />
        </>
      )}
    </div>
  );
}

