'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import Link from 'next/link';
import {
  BarChart2, Briefcase, CheckCircle2, Clock, FileText,
  FolderUp, Loader2, Play, RefreshCw, UserCheck, Users,
} from 'lucide-react';
import { AnimatedKpiCard } from '@/components/admin/AnimatedKpiCard';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';
import { sourcerOffersUrl, type SourcerDashboardBucket } from '@/lib/offerStatusRoutes';
import { SOURCER_KPI_HELP } from '@/lib/spaceMetricHelp';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

function ratioLabel(value: number, total: number, suffix: string): string {
  if (total <= 0) return '—';
  const p = Math.min(100, Math.round((value / total) * 100));
  return `${p}% ${suffix}`;
}

interface Dashboard {
  assigned_offers_count: number;
  pipelines_launched: number;
  total_cvs_matched: number;
  offers_by_status: { pending: number; running: number; completed: number; failed: number };
  recent_activity: Array<{ type: string; description: string; timestamp: string }>;
}

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
  offer_assigned:       <UserCheck className="h-4 w-4 text-teal-400 flex-shrink-0" />,
  pipeline_launched:    <Play className="h-4 w-4 text-blue-400 flex-shrink-0" />,
  pipeline_completed:   <CheckCircle2 className="h-4 w-4 text-green-400 flex-shrink-0" />,
  pipeline_failed:      <BarChart2 className="h-4 w-4 text-red-400 flex-shrink-0" />,
};

const dotColor: Record<string, string> = {
  offer_assigned: 'bg-teal-400',
  pipeline_launched: 'bg-blue-400',
  pipeline_completed: 'bg-green-400',
  pipeline_failed: 'bg-red-400',
};

const STATUS_PILLS: { key: SourcerDashboardBucket; label: string; color: string }[] = [
  { key: 'pending',   label: 'En attente', color: 'bg-amber-400/10 text-amber-400 border-amber-400/20' },
  { key: 'running',   label: 'En cours',   color: 'bg-blue-400/10 text-blue-400 border-blue-400/20' },
  { key: 'completed', label: 'Terminées',  color: 'bg-green-400/10 text-green-400 border-green-400/20' },
  { key: 'failed',    label: 'Échouées',   color: 'bg-red-400/10 text-red-400 border-red-400/20' },
];

export default function SourcerDashboardPage() {
  const [userName, setUserName] = useState('');
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [animKey, setAnimKey] = useState(0);
  const reducedMotion = usePrefersReducedMotion();

  const fetchData = () => {
    setLoading(true);
    Promise.all([
      fetch(`${API_BASE}/auth/me`, { credentials: 'include' }).then(r => r.ok ? r.json() : null),
      fetch(`${API_BASE}/sourcer/dashboard`, { credentials: 'include' }).then(r => r.ok ? r.json() : null),
    ]).then(([me, dashboard]) => {
      if (me) setUserName(me.full_name);
      setDash(dashboard);
      if (dashboard) setAnimKey(k => k + 1);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, []);

  const s = dash?.offers_by_status ?? { pending: 0, running: 0, completed: 0, failed: 0 };

  return (
    <div className="w-full max-w-7xl space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="mt-2 text-4xl font-semibold text-slate-950">Tableau de bord</h1>
          <p className="mt-2 text-lg text-slate-600">Voici l&apos;état de vos missions de sourcing</p>
        </div>
        <button onClick={fetchData} className="flex items-center gap-2 rounded-lg border border-[#d8e0ea] bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:border-[#2f66ed]/40 hover:text-[#2f66ed]">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Actualiser
        </button>
      </div>

      {userName && <p className="text-sm text-slate-600">Bonjour, <span className="font-semibold text-slate-950">{userName}</span> </p>}

      {loading && <div className="flex justify-center h-48"><Loader2 className="h-8 w-8 animate-spin text-[#1f9d94] mt-16" /></div>}

      {!loading && !dash && (
        <div className="admin-light-card rounded-xl p-8 text-center text-slate-500">
          <p>Aucune donnée disponible. Attendez qu&apos;une offre vous soit assignée.</p>
          <Link href="/sourcer/offers"><button className="mt-4 px-4 py-2 rounded-lg border border-[#d8e0ea] bg-white text-sm font-semibold text-slate-700 transition-all hover:border-[#2f66ed]/40 hover:text-[#2f66ed]">Voir mes offres</button></Link>
        </div>
      )}

      {!loading && dash && (
        <>
          <Section reducedMotion={reducedMotion} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <AnimatedKpiCard label="Offres assignées" rawValue={dash.assigned_offers_count} type="count" icon={Briefcase} border="border-[#1f9d94]" index={0} animKey={animKey} reducedMotion={reducedMotion} variant="space" help={SOURCER_KPI_HELP.offers_assigned} sub="offres en cours" />
            <AnimatedKpiCard
              label="Pipelines lancés"
              rawValue={dash.pipelines_launched}
              type="count"
              icon={Play}
              border="border-blue-500"
              index={1}
              animKey={animKey}
              reducedMotion={reducedMotion}
              variant="space"
              help={SOURCER_KPI_HELP.pipelines_launched}
              ratio={{
                value: dash.pipelines_launched,
                total: dash.assigned_offers_count,
                label: ratioLabel(dash.pipelines_launched, dash.assigned_offers_count, 'des offres traitées'),
                colorScheme: 'positive',
              }}
              sub="total lancés"
            />
            <AnimatedKpiCard
              label="Candidats scorés"
              rawValue={dash.total_cvs_matched}
              type="count"
              icon={Users}
              border="border-purple-500"
              index={2}
              animKey={animKey}
              reducedMotion={reducedMotion}
              variant="space"
              help={SOURCER_KPI_HELP.candidates_scored}
              ratio={{
                value: s.completed,
                total: dash.assigned_offers_count,
                label: ratioLabel(s.completed, dash.assigned_offers_count, 'offres matchées'),
                colorScheme: 'positive',
              }}
              sub="tous pipelines terminés"
            />
            <AnimatedKpiCard
              label="En attente"
              rawValue={s.pending}
              type="count"
              icon={Clock}
              border="border-amber-500"
              index={3}
              animKey={animKey}
              reducedMotion={reducedMotion}
              variant="space"
              help={SOURCER_KPI_HELP.pending}
              ratio={{
                value: s.pending,
                total: dash.assigned_offers_count,
                label: ratioLabel(s.pending, dash.assigned_offers_count, 'en attente de lancement'),
                colorScheme: 'warning',
              }}
              sub="sans pipeline"
            />
          </Section>

          <Section reducedMotion={reducedMotion}>
            <motion.div
              className="admin-light-card rounded-xl p-6"
              initial={reducedMotion ? false : CARD_REVEAL.initial}
              animate={CARD_REVEAL.animate}
              transition={{ ...CARD_REVEAL.transition, delay: reducedMotion ? 0 : 0.4 }}
            >
              <h2 className="text-base font-semibold text-slate-950 mb-4">Statut des offres</h2>
              <div className="flex flex-wrap gap-3">
                {STATUS_PILLS.map(({ key, label, color }) => (
                  <Link key={key} href={sourcerOffersUrl(key)}>
                    <motion.span
                      whileHover={reducedMotion ? undefined : { scale: 1.05 }}
                      transition={{ duration: 0.15 }}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-medium cursor-pointer ${color}`}
                    >
                      {label} <span className="font-bold">{s[key]}</span>
                    </motion.span>
                  </Link>
                ))}
              </div>
            </motion.div>
          </Section>

          {dash.recent_activity.length > 0 ? (
            <Section reducedMotion={reducedMotion}
              className="admin-light-card overflow-hidden rounded-xl">
              <div className="border-b border-[#d8e0ea] px-6 py-4">
                <h2 className="text-base font-semibold text-slate-950">Activité récente</h2>
              </div>
              <ul className="divide-y divide-[#e5ebf2]">
                {dash.recent_activity.map((item, i) => (
                  <AnimatedFeedRow key={i} index={i} reducedMotion={reducedMotion}>
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColor[item.type] || 'bg-slate-400'}`} />
                    {activityIcon[item.type] ?? <FileText className="h-4 w-4 text-slate-400 flex-shrink-0" />}
                    <p className="flex-1 truncate text-sm text-slate-700">{item.description}</p>
                    <span className="text-xs text-slate-500 flex-shrink-0">{relTime(item.timestamp)}</span>
                  </AnimatedFeedRow>
                ))}
              </ul>
            </Section>
          ) : (
            <Section reducedMotion={reducedMotion}
              className="admin-light-card rounded-xl p-8 text-center text-slate-500 flex flex-col items-center gap-2">
              <Clock className="h-8 w-8 opacity-30" />
              <p className="text-sm font-medium">Aucune activité récente</p>
            </Section>
          )}

          <Section reducedMotion={reducedMotion} className="flex gap-3">
            <Link href="/sourcer/offers" className="flex-1">
              <button className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-semibold transition-all">
                <Briefcase className="h-4 w-4" /> Voir mes offres
              </button>
            </Link>
            <Link href="/sourcer/upload" className="flex-1">
              <button className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg border border-[#d8e0ea] bg-white text-slate-700 hover:border-[#2f66ed]/40 hover:text-[#2f66ed] text-sm transition-all">
                <FolderUp className="h-4 w-4" /> Déposer des CVs
              </button>
            </Link>
          </Section>
        </>
      )}
    </div>
  );
}

