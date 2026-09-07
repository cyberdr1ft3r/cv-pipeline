export interface MetricHelpInfo {
  summary: string;
  formula?: string;
  detail?: string;
}

export type MetricHelpMode = 'hover' | 'click';

export const ADMIN_KPI_HELP = {
  total_offers: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Nombre d\'offres créées sur la période sélectionnée, tous statuts confondus.',
  },
  offers_matched: {
    mode: 'click' as MetricHelpMode,
    summary: 'Offres ayant produit des candidats évalués par l\'IA (statut « matchée »).',
    formula: 'Taux affiché = offres matchées ÷ offres totales × 100',
    detail: 'Mesure la part des besoins qui aboutissent à un sourcing réussi. Distinct du score de qualité des candidats.',
  },
  avg_matching_score: {
    mode: 'click' as MetricHelpMode,
    summary: 'Qualité moyenne des correspondances candidat-offre, sur une échelle de 0 à 100 %.',
    formula: 'Moyenne des scores IA sur toutes les apparitions évaluées',
    detail: 'Indique l\'adéquation profil / exigences de l\'offre. Ce n\'est pas un taux de conversion ni un taux de réussite pipeline.',
  },
  avg_time_to_match: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Temps moyen entre la création d\'une offre et l\'obtention du premier matching (candidats scorés).',
  },
  hired: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Nombre de candidats marqués « recruté » (embauche confirmée) sur la période.',
  },
} satisfies Record<string, MetricHelpInfo & { mode: MetricHelpMode }>;

export const ADMIN_FUNNEL_HELP = {
  offer_to_match: {
    mode: 'click' as MetricHelpMode,
    summary: 'Part des offres créées qui atteignent le stade « matchée ».',
    formula: 'Offres matchées ÷ offres totales × 100',
    detail: 'Un taux élevé signifie que la majorité des besoins trouvent des candidats pertinents via le sourcing.',
  },
  match_to_hire: {
    mode: 'click' as MetricHelpMode,
    summary: 'Part des offres matchées qui se concluent par au moins une embauche.',
    formula: 'Recrutés ÷ offres matchées × 100',
    detail: 'Mesure l\'efficacité de la phase décisionnelle après le matching (présélection → embauche).',
  },
  avg_delay: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Délai moyen pour passer d\'une offre créée à son premier résultat de matching.',
  },
  candidates_per_offer: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Nombre moyen de candidats distincts évalués par offre matchée.',
    formula: 'Candidats évalués ÷ offres matchées',
  },
} satisfies Record<string, MetricHelpInfo & { mode: MetricHelpMode }>;

export const STAGE_HELP: Record<string, string> = {
  open: 'Offre publiée, en attente d\'assignation à un sourceur.',
  assigned: 'Offre assignée à un sourceur, pipeline pas encore lancé.',
  in_progress: 'Pipeline de sourcing en cours d\'exécution.',
  matched: 'Matching terminé — candidats scorés et disponibles pour le recruteur.',
  final_result: 'Résultat final du pipeline généré.',
  formatted: 'CVs formatés et prêts pour présentation client.',
  archived: 'Offre archivée (mission close ou annulée).',
};

export const TEAM_SCORE_HELP: MetricHelpInfo & { mode: MetricHelpMode } = {
  mode: 'click',
  summary: 'Score moyen des candidats évalués sur les offres de ce recruteur.',
  formula: 'Moyenne des scores IA (0–100 %) sur les apparitions liées à ses offres',
  detail: 'Reflet de la qualité des matchings obtenus, pas du nombre d\'embauches.',
};

export const SKILLS_GAP_HELP: MetricHelpInfo & { mode: MetricHelpMode } = {
  mode: 'click',
  summary: 'Écart entre la demande (offres) et l\'offre de compétences (candidats du vivier).',
  formula: 'Gap = demande offres − disponibilité candidats',
  detail: 'Un gap élevé (rouge) signale une compétence très demandée mais peu présente dans le vivier.',
};

/** Action 293 — Activité d'équipe (CEO admin dashboard). */
export const TEAM_ACTIVITY_SECTION_HELP: MetricHelpInfo & { mode: MetricHelpMode } = {
  mode: 'click',
  summary: 'Vue consolidée des performances Recrutement et Sourcing sur la période filtrée.',
  detail: 'Basculez entre les deux équipes sans recharger les données. Les graphiques et KPIs se mettent à jour uniquement quand vous changez les dates.',
};

export const TEAM_RECRUITING_VIEW_HELP: MetricHelpInfo & { mode: MetricHelpMode } = {
  mode: 'hover',
  summary: 'Indicateurs des recruteurs : création d\'offres, qualité des matchings, délais jusqu\'à la présentation client et retours.',
};

export const TEAM_SOURCING_VIEW_HELP: MetricHelpInfo & { mode: MetricHelpMode } = {
  mode: 'hover',
  summary: 'Indicateurs des sourceurs : offres traitées, pipelines lancés, volume de candidats scorés et taux de réussite technique.',
};

export const TEAM_RECRUITING_KPI_HELP = {
  offers_created: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Nombre d\'offres créées par les recruteurs sur la période (tous statuts).',
  },
  avg_matching_score: {
    mode: 'click' as MetricHelpMode,
    summary: 'Qualité moyenne des correspondances IA sur les offres des recruteurs (0–100 %).',
    formula: 'Moyenne des scores matching/final sur les apparitions évaluées',
    detail: 'Mesure l\'adéquation profil / besoin, pas le volume ni le taux d\'embauche.',
  },
  matching_to_format: {
    mode: 'click' as MetricHelpMode,
    summary: 'Délai moyen entre la fin du matching et la fin du formatage des CVs.',
    formula: 'Moyenne(format_completed_at − matching_completed_at)',
    detail: 'Reflète la rapidité de passage du sourcing validé à des CVs prêts pour le client.',
  },
  format_to_client: {
    mode: 'click' as MetricHelpMode,
    summary: 'Délai moyen entre la fin du formatage et le premier envoi « Envoyé au client ».',
    formula: 'Moyenne(premier envoye_client − format_completed_at)',
    detail: 'Mesure la réactivité du recruteur après production des CVs formatés.',
  },
  candidates_validated: {
    mode: 'click' as MetricHelpMode,
    summary: 'Candidats marqués validés côté recruteur ou client.',
    formula: 'Statut final « validé » OU format « offre faite / recruté / validé client »',
    detail: 'Compte les décisions positives avant ou après présentation client.',
  },
} satisfies Record<string, MetricHelpInfo & { mode: MetricHelpMode }>;

export const TEAM_SOURCING_KPI_HELP = {
  offers_assigned: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Offres assignées à un sourceur sur la période (date de création de l\'offre).',
  },
  pipelines_launched: {
    mode: 'click' as MetricHelpMode,
    summary: 'Nombre de pipelines de matching lancés sur les offres sourceur.',
    detail: 'Un pipeline = une exécution du moteur IA (extraction, matching, etc.).',
  },
  success_rate: {
    mode: 'click' as MetricHelpMode,
    summary: 'Part des pipelines terminés avec succès (sans échec technique).',
    formula: 'Pipelines réussis ÷ (réussis + échoués) × 100',
    detail: 'Ne mesure pas la qualité des candidats, seulement la fiabilité d\'exécution.',
  },
  candidates_scored: {
    mode: 'click' as MetricHelpMode,
    summary: 'Total de candidats scorés par l\'IA sur les pipelines réussis.',
    formula: 'Somme des cv_count des jobs terminés avec succès',
  },
  avg_matching_score: {
    mode: 'click' as MetricHelpMode,
    summary: 'Score moyen des candidats sur les offres traitées par les sourceurs.',
    formula: 'Moyenne des scores IA (0–100 %) sur les apparitions',
    detail: 'Le sous-texte « / pipeline » indique le volume moyen de CVs scorés par pipeline réussi.',
  },
} satisfies Record<string, MetricHelpInfo & { mode: MetricHelpMode }>;

export const TEAM_CLIENT_FEEDBACK_HELP: MetricHelpInfo & { mode: MetricHelpMode } = {
  mode: 'click',
  summary: 'Répartition des statuts format / client sur les candidats présentés.',
  detail: 'En attente = envoyés au client sans retour. Recrutés / non intégrés / rejetés = décisions client. Validé / non validé client = arbitrage final.',
};

export const TEAM_RECRUITING_CARDS_HELP: MetricHelpInfo & { mode: MetricHelpMode } = {
  mode: 'click',
  summary: 'Une carte par recruteur comparant délais et validations à la meilleure performance de l\'équipe.',
  detail: 'Chaque barre est relative au maximum de l\'équipe sur la période (M→F, F→Client, Candidats validés). Pour les délais, une barre plus courte = plus rapide. « Retour client » détaille la répartition des statuts pour ce recruteur. « — » signale l\'absence de données.',
};

export const TEAM_CHART_HELP = {
  offers_by_month: {
    mode: 'click' as MetricHelpMode,
    summary: 'Évolution mensuelle des offres créées vs assignées à un sourceur.',
    detail: 'L\'écart entre les deux courbes peut signaler des offres en attente d\'assignation.',
  },
  score_distribution_recruiting: {
    mode: 'click' as MetricHelpMode,
    summary: 'Répartition des candidats par tranche de score (offres recruteur).',
    detail: 'Rouge < 50 % · Ambre 50–59 % · Teal 60–79 % · Vert ≥ 80 %. Aide à juger la qualité globale du sourcing reçu.',
  },
  pipeline_to_client_trend: {
    mode: 'click' as MetricHelpMode,
    summary: 'Évolution mensuelle des délais moyens (en heures) entre phases clés.',
    formula: 'Axe gauche : matching→format · Axe droit : format→client',
    detail: 'Les deux métriques ont des échelles différentes d\'où les deux axes Y.',
  },
  pipelines_by_month: {
    mode: 'click' as MetricHelpMode,
    summary: 'Pipelines lancés, réussis et échoués par mois (équipe sourcing).',
    detail: 'Un échec = erreur technique ou interruption du job, pas un rejet candidat.',
  },
  score_distribution_sourcing: {
    mode: 'click' as MetricHelpMode,
    summary: 'Répartition des scores sur les offres traitées par les sourceurs.',
    detail: 'Même échelle de couleurs que l\'équipe recrutement (Action 272).',
  },
  candidates_scored_by_month: {
    mode: 'click' as MetricHelpMode,
    summary: 'Volume mensuel de candidats scorés (pipelines réussis uniquement).',
    detail: 'Indicateur de productivité sourcing et d\'activité sur le vivier.',
  },
} satisfies Record<string, MetricHelpInfo & { mode: MetricHelpMode }>;

export const TEAM_TABLE_HELP = {
  rec_matching_to_format: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Délai moyen matching → formatage pour ce recruteur.',
  },
  rec_format_to_client: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Délai moyen formatage → premier envoi client pour ce recruteur.',
  },
  rec_client_feedback: {
    mode: 'click' as MetricHelpMode,
    summary: 'Synthèse compacte des retours client.',
    formula: 'Format : en attente / recrutés / non intégrés / rejetés',
    detail: 'Ex. « 2/1/1 » = 2 en attente, 1 recruté, 1 non intégré, 0 rejeté.',
  },
  rec_last_active: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Dernière activité sur une offre ou dernière connexion à la plateforme.',
  },
  src_avg_candidates_matched: {
    mode: 'click' as MetricHelpMode,
    summary: 'Nombre moyen de candidats scorés par pipeline lancé pour ce sourceur.',
    formula: 'Total candidats scorés ÷ pipelines lancés',
  },
  src_offers_completed: {
    mode: 'click' as MetricHelpMode,
    summary: 'Part des offres assignées ayant atteint le stade « matchée » (status ≥ 4).',
    formula: 'Offres matchées ÷ offres assignées × 100',
  },
  src_last_active: {
    mode: 'hover' as MetricHelpMode,
    summary: 'Dernière mise à jour d\'offre assignée ou dernière connexion.',
  },
} satisfies Record<string, MetricHelpInfo & { mode: MetricHelpMode }>;
