export type JobStage = string;
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export interface PhaseProgress {
  value: number;
  label: string;
  detail: string;
}

export interface PhaseConfig {
  label: string;
  labelQueued: string;
  labelInProgress: string;
  labelComplete: string;
}

export const EXTRACTION_MATCHING_CONFIG: PhaseConfig = {
  label: 'Extraction et traitement',
  labelQueued: 'En attente...',
  labelInProgress: 'Traitement en cours...',
  labelComplete: 'Termine',
};

export const FINAL_SCORING_CONFIG: PhaseConfig = {
  label: 'Scoring final',
  labelQueued: 'En attente...',
  labelInProgress: 'Calcul en cours...',
  labelComplete: 'Termine',
};

export const FORMATTING_CONFIG: PhaseConfig = {
  label: 'Formatage des CVs',
  labelQueued: 'En attente...',
  labelInProgress: 'Generation en cours...',
  labelComplete: 'Termine',
};

export interface JobProgressResponse {
  extraction: number;
  matching: number;
  final: number;
  format: number;
  details: {
    extraction: string;
    matching: string;
    final: string;
    format: string;
  };
}

const animationState: Record<string, { current: number; target: number; lastUpdate: number }> = {};

export function animateProgress(
  phase: 'extraction' | 'matching' | 'final' | 'format',
  targetValue: number
): number {
  const key = phase;
  const now = Date.now();

  if (!animationState[key]) {
    animationState[key] = {
      current: 1,
      target: targetValue,
      lastUpdate: now,
    };
  }

  const state = animationState[key];

  if (targetValue !== state.target) {
    state.target = targetValue;
    state.lastUpdate = now;
  }

  const elapsed = now - state.lastUpdate;
  const animationDuration = 3000;

  if (elapsed > animationDuration || state.target === 100) {
    state.current = state.target;
  } else {
    const progress = Math.min(elapsed / animationDuration, 1);
    const easedProgress = 1 - Math.pow(1 - progress, 3);
    const startValue = phase === 'extraction' && targetValue === 100 ? state.current : state.current;

    if (targetValue > startValue) {
      state.current = startValue + (targetValue - startValue) * easedProgress;
    }
  }

  return Math.max(1, Math.min(100, Math.round(state.current)));
}

export function resetProgressAnimation(phase: 'extraction' | 'matching' | 'final' | 'format') {
  delete animationState[phase];
}

export function getPhaseProgress(
  apiProgress: number,
  apiDetail: string,
  status: JobStatus,
  config: PhaseConfig
): PhaseProgress {
  if (status === 'failed') {
    return { value: 0, label: config.label, detail: 'Erreur' };
  }

  if (status === 'queued') {
    return { value: 1, label: config.label, detail: config.labelQueued };
  }

  if (apiProgress >= 100) {
    return { value: 100, label: config.labelComplete, detail: config.labelComplete };
  }

  const animatedValue = animateProgress(config.label === 'Extraction et traitement' ? 'extraction' : config.label === 'Scoring final' ? 'final' : 'format', apiProgress);

  let detail = apiDetail || config.labelInProgress;
  if (detail === "") {
    if (animatedValue < 20) {
      detail = "Initialisation...";
    } else if (animatedValue < 50) {
      detail = "Traitement en cours...";
    } else if (animatedValue < 80) {
      detail = "Traitement avance...";
    } else {
      detail = "Finalisation...";
    }
  }

  return { value: animatedValue, label: config.label, detail };
}

export function getExtractionMatchingProgress(
  progressData: JobProgressResponse | null,
  status: JobStatus
): PhaseProgress {
  return getPhaseProgress(
    progressData?.extraction ?? 1,
    progressData?.details?.extraction ?? '',
    status,
    EXTRACTION_MATCHING_CONFIG
  );
}

export function getMatchingProgress(
  progressData: JobProgressResponse | null,
  status: JobStatus
): PhaseProgress {
  return getPhaseProgress(
    progressData?.matching ?? 0,
    progressData?.details?.matching ?? '',
    status,
    EXTRACTION_MATCHING_CONFIG
  );
}

export function getFinalScoringProgress(
  progressData: JobProgressResponse | null,
  status: JobStatus
): PhaseProgress {
  return getPhaseProgress(
    progressData?.final ?? 1,
    progressData?.details?.final ?? '',
    status,
    FINAL_SCORING_CONFIG
  );
}

export function getFormattingProgress(
  progressData: JobProgressResponse | null,
  status: JobStatus
): PhaseProgress {
  return getPhaseProgress(
    progressData?.format ?? 1,
    progressData?.details?.format ?? '',
    status,
    FORMATTING_CONFIG
  );
}