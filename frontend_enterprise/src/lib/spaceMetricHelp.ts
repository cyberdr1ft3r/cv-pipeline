import type { MetricHelpInfo, MetricHelpMode } from '@/lib/adminMetricHelp';

type HelpEntry = MetricHelpInfo & { mode: MetricHelpMode };

/** Tooltips for the recruiter dashboard KPI cards. */
export const RECRUITER_KPI_HELP = {
  offers_created: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Nombre total d\'offres que vous avez créées, tous statuts confondus.',
  },
  pipelines_completed: {
    mode: 'click' as MetricHelpMode,
    summary: 'Pipelines de sourcing terminés sur vos offres.',
    formula: 'Taux affiché = pipelines terminés ÷ offres totales × 100',
    detail: 'Le sous-titre indique les pipelines en cours et échoués éventuels.',
  },
  candidates_scored: {
    mode: 'click' as MetricHelpMode,
    summary: 'Nombre de CV passés au scoring IA sur vos offres.',
    detail: 'Le sous-titre « profils distincts » dédoublonne les candidats vus sur plusieurs offres.',
  },
  avg_matching_score: {
    mode: 'click' as MetricHelpMode,
    summary: 'Score moyen d\'adéquation candidat-offre (0 à 100 %).',
    formula: 'Moyenne des scores IA sur les apparitions de vos offres',
    detail: 'Mesure la qualité du sourcing reçu, pas un taux de conversion.',
  },
  shortlisted: {
    mode: 'click' as MetricHelpMode,
    summary: 'Candidats que vous avez marqués « présélectionné ».',
    formula: 'Taux affiché = présélectionnés ÷ candidats scorés × 100',
  },
  in_process: {
    mode: 'click' as MetricHelpMode,
    summary: 'Candidats en cours de traitement : contactés, interviewés ou en phase d\'offre.',
    formula: 'Taux affiché = en process ÷ candidats scorés × 100',
  },
  hired: {
    mode: 'click' as MetricHelpMode,
    summary: 'Candidats recrutés (embauches confirmées) issus de vos offres.',
    formula: 'Taux affiché = recrutés ÷ candidats scorés × 100',
  },
  matching_to_format: {
    mode: 'click' as MetricHelpMode,
    summary: 'Délai moyen entre le matching d\'une offre et la fin du formatage des candidats.',
    detail: 'Mesure votre réactivité à préparer les dossiers une fois le sourcing disponible.',
  },
  format_to_client: {
    mode: 'click' as MetricHelpMode,
    summary: 'Délai moyen entre la fin du formatage et le premier envoi du candidat au client.',
    formula: 'Premier passage au statut « Envoyé au client » − fin du formatage',
    detail: 'Lu depuis l\'historique des statuts : la valeur est conservée même si le candidat évolue ensuite (recruté, validé client, …).',
  },
  candidates_validated: {
    mode: 'click' as MetricHelpMode,
    summary: 'Candidats sélectionnés ou validés (offre faite, recruté, validé client, ou validé final).',
    formula: 'Taux affiché = validés ÷ candidats scorés × 100',
  },
  client_feedback: {
    mode: 'click' as MetricHelpMode,
    summary: 'Répartition des retours client sur les candidats envoyés.',
    detail: 'En attente = envoyés sans retour. Recrutés / non intégrés / rejetés = décisions client. Validé / non validé client = arbitrage final.',
  },
} satisfies Record<string, HelpEntry>;

/** Tooltips for the sourcer dashboard KPI cards. */
export const SOURCER_KPI_HELP = {
  offers_assigned: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Offres qui vous sont assignées et en cours de traitement.',
  },
  pipelines_launched: {
    mode: 'click' as MetricHelpMode,
    summary: 'Nombre total de pipelines de sourcing que vous avez lancés.',
    formula: 'Taux affiché = pipelines lancés ÷ offres assignées × 100',
  },
  candidates_scored: {
    mode: 'click' as MetricHelpMode,
    summary: 'CV passés au scoring IA sur l\'ensemble de vos pipelines terminés.',
    formula: 'Taux affiché = offres matchées ÷ offres assignées × 100',
    detail: 'Volume de CV traités (un même profil peut apparaître sur plusieurs offres).',
  },
  pending: {
    mode: 'click' as MetricHelpMode,
    summary: 'Offres assignées sans pipeline lancé, en attente de traitement.',
    formula: 'Taux affiché = en attente ÷ offres assignées × 100',
  },
} satisfies Record<string, HelpEntry>;
