'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, BarChart3, Check, Download, Eye, Loader2 } from 'lucide-react';
import { PipelineShell } from '@/app/components/pipeline/PipelineShell';
import { usePipeline } from '@/hooks/usePipeline';

type PipelineJob = {
  job_id: string;
  session_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  stage: string;
  error_message?: string | null;
  offer_filename?: string | null;
  cv_count?: number;
  started_at?: string | null;
  completed_at?: string | null;
};

type JobStatusResponse = {
  job: PipelineJob;
  progress: {
    extraction: number;
    matching: number;
    final: number;
    format: number;
  };
};

type MatchingResultsResponse = {
  totalCandidates: number;
};

function formatDuration(job: PipelineJob | null) {
  if (!job?.started_at || !job.completed_at) {
    return '< 5';
  }

  const start = new Date(job.started_at).getTime();
  const end = new Date(job.completed_at).getTime();

  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
    return '< 5';
  }

  const minutes = Math.ceil((end - start) / 60000);
  return minutes < 5 ? '< 5' : `${minutes}`;
}

function CompletionIcon() {
  return (
    <div className="mx-auto flex h-[108px] w-[108px] items-center justify-center rounded-full border border-cyan-400/75 bg-cyan-400/10 shadow-[0_0_0_1px_rgba(34,211,238,0.1)]">
      <div className="flex h-[48px] w-[48px] items-center justify-center rounded-full border border-cyan-300 bg-transparent">
        <Check className="h-7 w-7 text-cyan-300" />
      </div>
    </div>
  );
}

export default function PipelineProgressPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobId = searchParams.get('jobId');
  const { getJobStatus, getMatchingResults, runFinalPhase, getArtifactDownloadUrl } = usePipeline();

  const [job, setJob] = useState<PipelineJob | null>(null);
  const [matchingCount, setMatchingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningFinal, setRunningFinal] = useState(false);
  const [currentStage, setCurrentStage] = useState<string>('');

  const isProcessing = !loading && !error && job && (job.status === 'queued' || job.status === 'running') && !['matching_complete', 'final_complete', 'format_complete'].includes(job.stage);
  const isCompleted = !loading && !error && job && job.status === 'succeeded' && job.stage === 'matching_complete';
  const isFinalComplete = job && job.stage === 'final_complete';
  const isFormatComplete = job && job.stage === 'format_complete';

  const getCurrentPhaseName = (): string => {
    if (!job) return 'Initialisation...';

    switch (job.stage) {
      case 'preparing_inputs':
        return job.session_id === 'pending' 
          ? 'Analyse de l\'offre et chargement des CVs depuis SFTP...' 
          : 'Préparation des fichiers...';
      case 'running_pipeline':
        return 'Extraction et traitement...';
      case 'running_final':
        return 'Calcul du scoring final...';
      case 'running_format':
        return 'Formatage des CVs...';
      case 'matching_complete':
        return 'Appariement terminé';
      case 'final_complete':
        return 'Scoring final terminé';
      case 'format_complete':
        return 'Formatage terminé';
      case 'failed':
        return 'Échec du traitement...';
      default:
        return 'Traitement en cours...';
    }
  };

  useEffect(() => {
    if (!jobId) {
      setError("Aucun identifiant de traitement n'a \u00e9t\u00e9 fourni.");
      setLoading(false);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const fetchStatus = async () => {
      try {
        const payload = (await getJobStatus(jobId)) as JobStatusResponse;
        if (cancelled) {
          return;
        }

        setJob(payload.job);
        setCurrentStage(payload.job.stage);
        setError(null);
        setLoading(false);

        if (payload.job.status === 'queued' || payload.job.status === 'running') {
          timer = setTimeout(fetchStatus, 2000);
        }
      } catch (statusError) {
        if (cancelled) {
          return;
        }

        const message = statusError instanceof Error ? statusError.message : 'Erreur inconnue';
        setError(message);
        setLoading(false);
        timer = setTimeout(fetchStatus, 3000);
      }
    };

    void fetchStatus();

    return () => {
      cancelled = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [getJobStatus, jobId]);

  useEffect(() => {
    if (!jobId || !job || job.status !== 'succeeded' || job.stage === 'failed') {
      return;
    }

    if (job.stage === 'final_complete') {
      router.replace(`/pipeline/final?jobId=${jobId}`);
      return;
    }

    if (job.stage === 'format_complete') {
      router.replace(`/pipeline/format?jobId=${jobId}`);
    }
  }, [job, jobId, router]);

  useEffect(() => {
    if (!jobId || !job || job.status !== 'succeeded') {
      return;
    }

    if (!['matching_complete', 'final_complete', 'format_complete'].includes(job.stage)) {
      return;
    }

    let cancelled = false;

    const fetchMatching = async () => {
      try {
        const payload = (await getMatchingResults(jobId)) as MatchingResultsResponse;
        if (!cancelled) {
          setMatchingCount(payload.totalCandidates || 0);
        }
      } catch (matchingError) {
        if (!cancelled) {
          console.error('Matching results fetch failed:', matchingError);
        }
      }
    };

    void fetchMatching();

    return () => {
      cancelled = true;
    };
  }, [getMatchingResults, job, jobId]);

  const candidateCount = useMemo(() => {
    if (matchingCount > 0) {
      return matchingCount;
    }

    if (typeof job?.cv_count === 'number' && job.cv_count > 0) {
      return job.cv_count;
    }

    return 0;
  }, [job, matchingCount]);

  const handleViewMatchingResults = () => {
    if (!jobId) {
      return;
    }

    router.push(`/pipeline/results?jobId=${jobId}`);
  };

  const handleRunFinal = async () => {
    if (!jobId) {
      return;
    }

    // Only redirect to test-upload page, don't trigger scoring yet
    router.push(`/pipeline/test-upload?jobId=${jobId}`);
  };

  const handleGoToFormatting = () => {
    if (!jobId) {
      return;
    }

    // Go directly to template selection, skipping final scoring
    router.push(`/pipeline/template-select?jobId=${jobId}`);
  };

  const handleRetry = () => {
    if (!jobId) {
      return;
    }
    // Retry by going back to offer-only page with the same job
    router.push(`/pipeline/offer-only`);
  };

  const handleCancel = () => {
    // Go back to mode selection
    router.push(`/pipeline`);
  };

  const isFailed = !loading && job && job.status === 'failed';
  const isOfferOnlyPending = !loading && job && job.session_id === 'pending' && job.status === 'running';

  return (
    <PipelineShell>
      <div className="mx-auto max-w-[1280px]">
        {loading ? (
          <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
            <Loader2 className="h-8 w-8 animate-spin text-cyan-300" />
            <p className="text-lg text-slate-200">Chargement du traitement en cours...</p>
          </div>
        ) : error && !job ? (
          <div className="mx-auto mt-10 max-w-[820px] rounded-[28px] border border-red-400/20 bg-red-500/10 px-6 py-5">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
              <div>
                <p className="font-semibold text-red-100">Impossible de charger ce traitement</p>
                <p className="mt-1 text-sm text-red-100/85">{error}</p>
              </div>
            </div>
          </div>
        ) : isFailed ? (
          <div className="space-y-8">
            <section className="pt-2 text-center">
              <div className="mx-auto max-w-[960px] space-y-3">
                <h1 className="text-[36px] font-semibold tracking-[-0.05em] text-white md:text-[42px]">
                  {'Échec du traitement'}
                </h1>
                <p className="text-[18px] text-slate-200">
                  <span className="font-semibold text-white">{job?.offer_filename ?? 'Offre importée'}</span>
                  <span className="text-red-300">{` • Une erreur est survenue`}</span>
                </p>
              </div>
            </section>

            <section className="mx-auto max-w-[820px] rounded-[28px] border border-red-400/20 bg-red-500/10 px-6 py-5">
              <div className="flex items-start gap-3">
                <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
                <div>
                  <p className="font-semibold text-red-100">Erreur de traitement</p>
                  <p className="mt-1 text-sm text-red-100/85">
                    {job?.error_message || 'Une erreur inconnue est survenue lors du traitement.'}
                  </p>
                </div>
              </div>
            </section>

            <section className="mx-auto max-w-[820px]">
              <h2 className="text-[28px] font-semibold tracking-[-0.05em] text-white md:text-[32px] mb-6">
                {'Que souhaitez-vous faire ?'}
              </h2>

              <div className="grid gap-4 md:grid-cols-2">
                <button
                  type="button"
                  onClick={handleRetry}
                  className="flex h-[56px] items-center justify-center rounded-[20px] bg-[#1f9d94] px-6 text-lg font-semibold text-white shadow-[0_18px_45px_rgba(31,157,148,0.28)] transition-all hover:bg-[#25afa5]"
                >
                  Réessayer
                </button>

                <button
                  type="button"
                  onClick={handleCancel}
                  className="flex h-[56px] items-center justify-center rounded-[20px] border border-slate-600 bg-[#1a2138]/82 px-6 text-lg font-semibold text-slate-300 transition-all hover:bg-[#2a304a] hover:text-white"
                >
                  Annuler
                </button>
              </div>
            </section>
          </div>
        ) : isProcessing ? (
          <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 text-center">
            <Loader2 className="h-16 w-16 animate-spin text-cyan-400" />
            <div className="space-y-2">
              <p className="text-xl font-medium text-cyan-300">
                {getCurrentPhaseName()}
              </p>
              {isOfferOnlyPending && (
                <p className="text-sm text-slate-400">
                  Connexion au serveur SFTP et chargement des CVs correspondants...
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-8">
            <section className="pt-2 text-center">
              <div className="mx-auto max-w-[960px] space-y-3">
                <h1 className="text-[36px] font-semibold tracking-[-0.05em] text-white md:text-[42px]">
                  {'Traitement termin\u00e9 !'}
                </h1>
                <p className="text-[18px] text-slate-200">
                  <span className="font-semibold text-white">{job?.offer_filename ?? 'Offre import\u00e9e'}</span>
                  <span className="text-cyan-300">{` \u2022 ${candidateCount || 0} CVs trait\u00e9s avec succ\u00e8s`}</span>
                </p>
                <p className="text-[16px] text-slate-400">{'\u2713 Toutes les \u00e9tapes termin\u00e9es'}</p>
              </div>
            </section>

            <section className="space-y-6">
              <h2 className="text-[28px] font-semibold tracking-[-0.05em] text-white md:text-[32px]">
                {'R\u00e9sultats disponibles'}
              </h2>

              <div className="grid gap-5 lg:grid-cols-3">
                <div className="rounded-[18px] border border-cyan-400/25 bg-[#1b213a]/82 p-6">
                  <div className="mb-6 flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400/8 text-cyan-300">
                    <Eye className="h-5 w-5" />
                  </div>
                  <h3 className="text-[20px] font-semibold text-white">{'R\u00e9sultats d\u2019appariement'}</h3>
                  <p className="mt-3 min-h-[64px] text-[16px] leading-7 text-slate-400">
                    {'Visualisez les classements des candidats et les scores d\u2019appariement'}
                  </p>
                  <button
                    type="button"
                    onClick={handleViewMatchingResults}
                    className="mt-5 flex h-[44px] w-full items-center justify-center rounded-xl bg-[#2a304a] text-[16px] font-semibold text-cyan-300 transition-colors hover:bg-[#313752]"
                  >
                    {'Visualiser les r\u00e9sultats'}
                  </button>
                </div>

                <div className="rounded-[18px] border border-cyan-400/25 bg-[#1b213a]/82 p-6">
                  <div className="mb-6 flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400/8 text-cyan-300">
                    <BarChart3 className="h-5 w-5" />
                  </div>
                  <h3 className="text-[20px] font-semibold text-white">{'R\u00e9sultats finaux'}</h3>
                  <p className="mt-3 min-h-[64px] text-[16px] leading-7 text-slate-400">
                    {'T\u00e9l\u00e9chargez les tests et calculez les scores finaux'}
                  </p>
                  <button
                    type="button"
                    onClick={handleRunFinal}
                    disabled={runningFinal}
                    className="mt-5 flex h-[44px] w-full items-center justify-center rounded-xl bg-[#2a304a] text-[16px] font-semibold text-cyan-300 transition-colors hover:bg-[#313752] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {runningFinal ? 'Ex\u00e9cution en cours...' : 'Ex\u00e9cuter le scoring final'}
                  </button>
                </div>

                <div className="rounded-[18px] border border-cyan-400/25 bg-[#1b213a]/82 p-6">
                  <div className="mb-6 flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400/8 text-cyan-300">
                    <Download className="h-5 w-5" />
                  </div>
                  <h3 className="text-[20px] font-semibold text-white">{'CV format\u00e9s'}</h3>
                  <p className="mt-3 min-h-[64px] text-[16px] leading-7 text-slate-400">
                    {'Formatez les CV directement ou apr\u00e8s le scoring final'}
                  </p>
                  <button
                    type="button"
                    onClick={handleGoToFormatting}
                    className="mt-5 flex h-[44px] w-full items-center justify-center rounded-xl bg-[#2a304a] text-[16px] font-semibold text-cyan-300 transition-colors hover:bg-[#313752]"
                  >
                    Aller au formatage
                  </button>
                </div>
              </div>
            </section>

            <section className="space-y-6">
              <h2 className="text-[32px] font-semibold tracking-[-0.05em] text-white">
                Statistiques de traitement
              </h2>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[18px] border border-cyan-400/20 bg-[#1a2138]/82 p-6">
                  <p className="text-[16px] text-slate-400">{'Candidats trait\u00e9s'}</p>
                  <p className="mt-4 text-[48px] font-semibold tracking-[-0.04em] text-cyan-300">
                    {candidateCount || 0}
                  </p>
                </div>

                <div className="rounded-[18px] border border-cyan-400/20 bg-[#1a2138]/82 p-6">
                  <p className="text-[16px] text-slate-400">{'Dur\u00e9e du traitement'}</p>
                  <div className="mt-4 flex items-end gap-2">
                    <p className="text-[48px] font-semibold tracking-[-0.04em] text-cyan-300">
                      {formatDuration(job)}
                    </p>
                    <span className="pb-2 text-[16px] text-slate-400">min</span>
                  </div>
                </div>
              </div>
            </section>

            {error ? (
              <div className="rounded-[18px] border border-red-400/20 bg-red-500/10 px-5 py-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
                  <p className="text-sm text-red-100">{error}</p>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </PipelineShell>
  );
}
