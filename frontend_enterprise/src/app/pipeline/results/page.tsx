'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, BarChart3, ChevronDown, Loader2 } from 'lucide-react';
import { PipelineShell } from '@/app/components/pipeline/PipelineShell';
import { usePipeline } from '@/hooks/usePipeline';

type PipelineJob = {
  job_id: string;
  session_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  stage: string;
  error_message?: string | null;
  offer_filename?: string | null;
};

type JobStatusResponse = {
  job: PipelineJob;
};

type MatchingCandidate = {
  rank: number;
  candidateName: string;
  matchScore: number | null;
  experience: string;
  skills: string[];
  summary: string;
  skillsMatch: number | null;
  experienceMatch: number | null;
  educationMatch: number | null;
};

type MatchingResultsResponse = {
  jobId: string;
  sessionId: string;
  totalCandidates: number;
  results: MatchingCandidate[];
};

function ScoreCell({ score }: { score: number | null }) {
  const text = formatScore(score);
  const colorClass = getScoreColor(score);
  return (
    <span className={`text-center text-sm font-semibold ${colorClass}`}>
      {text}
    </span>
  );
}

function getScoreColor(score: number | null): string {
  if (score === null || score === undefined) {
    return 'text-slate-500';
  }
  if (score >= 70) {
    return 'text-cyan-300';
  }
  if (score >= 40) {
    return 'text-yellow-400';
  }
  return 'text-red-400';
}

function formatScore(score: number | null | undefined): string {
  if (typeof score !== 'number' || Number.isNaN(score)) {
    return '--';
  }
  const normalized = score <= 1 ? score * 100 : score;
  return `${normalized.toFixed(0)}%`;
}

function MatchingResultsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobId = searchParams.get('jobId');
  const { getJobStatus, getMatchingResults } = usePipeline();

  const [results, setResults] = useState<MatchingCandidate[]>([]);
  const [totalCandidates, setTotalCandidates] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [jobStage, setJobStage] = useState<string>('');

  useEffect(() => {
    if (!jobId) {
      setError("Aucun identifiant de traitement n'a ete fourni.");
      setLoading(false);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const checkJobAndFetch = async () => {
      try {
        const statusPayload = (await getJobStatus(jobId)) as JobStatusResponse;
        if (cancelled) {
          return;
        }

        const job = statusPayload.job;
        setJobStage(job.stage);

        if (job.status === 'failed') {
          setError(job.error_message || 'Le traitement a echoue.');
          setLoading(false);
          return;
        }

        if (job.stage === 'matching_complete') {
          const payload = (await getMatchingResults(jobId)) as MatchingResultsResponse;
          if (cancelled) {
            return;
          }
          setResults(payload.results || []);
          setTotalCandidates(payload.totalCandidates || 0);
          setError(null);
          setLoading(false);
          return;
        }

        if (job.stage === 'final_complete' || job.stage === 'format_complete') {
          const payload = (await getMatchingResults(jobId)) as MatchingResultsResponse;
          if (cancelled) {
            return;
          }
          setResults(payload.results || []);
          setTotalCandidates(payload.totalCandidates || 0);
          setError(null);
          setLoading(false);
          return;
        }

        if (job.status === 'queued' || job.status === 'running') {
          setError(null);
          setLoading(false);
          timer = setTimeout(checkJobAndFetch, 2000);
          return;
        }

        setError("Les resultats ne sont pas encore disponibles.");
        setLoading(false);
      } catch (fetchError) {
        if (cancelled) {
          return;
        }
        const message = fetchError instanceof Error ? fetchError.message : 'Erreur inconnue';
        setError(message);
        setLoading(false);
      }
    };

    void checkJobAndFetch();

    return () => {
      cancelled = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [jobId, getJobStatus, getMatchingResults]);

  const sortedResults = useMemo(
    () =>
      [...results].sort((a, b) => {
        const aRank = a.rank ?? Number.MAX_SAFE_INTEGER;
        const bRank = b.rank ?? Number.MAX_SAFE_INTEGER;
        return aRank - bRank;
      }),
    [results]
  );

  const handleRunFinalScoring = () => {
    if (!jobId) {
      return;
    }
    router.push(`/pipeline/test-upload?jobId=${jobId}`);
  };

  const handleGoToFormatting = () => {
    if (!jobId) {
      return;
    }
    router.push(`/pipeline/template-select?jobId=${jobId}`);
  };

  if (loading) {
    return (
      <PipelineShell>
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-cyan-300" />
          <p className="text-lg text-slate-200">Chargement des resultats...</p>
        </div>
      </PipelineShell>
    );
  }

  const isProcessing = jobStage && !['matching_complete', 'final_complete', 'format_complete'].includes(jobStage);

  if (isProcessing && !error) {
    return (
      <PipelineShell>
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 text-center">
          <Loader2 className="h-12 w-12 animate-spin text-cyan-300" />
          <div className="space-y-4">
            <h1 className="text-[42px] font-semibold tracking-[-0.05em] text-white">
              {'Traitement en cours...'}
            </h1>
            <p className="text-lg text-slate-300">
              {jobStage === 'preparing_inputs' && "Preparation des fichiers"}
              {jobStage === 'running_pipeline' && "Extraction et appariement en cours"}
              {!jobStage && "En attente du traitement"}
            </p>
            <p className="text-sm text-slate-400">
              Les resultats d'appariement seront disponibles une fois le traitement termine.
            </p>
          </div>
        </div>
      </PipelineShell>
    );
  }

  if (error) {
    return (
      <PipelineShell>
        <div className="mx-auto mt-10 max-w-[820px] rounded-[28px] border border-red-400/20 bg-red-500/10 px-6 py-5">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
            <div>
              <p className="font-semibold text-red-100">Impossible de charger les resultats</p>
              <p className="mt-1 text-sm text-red-100/85">{error}</p>
            </div>
          </div>
        </div>
      </PipelineShell>
    );
  }

  return (
    <PipelineShell>
      <div className="mx-auto max-w-[1120px] space-y-6">
        <section className="space-y-3">
          <h1 className="text-[36px] font-semibold tracking-[-0.05em] text-white md:text-[42px]">
            {'Resultats d\'appariement'}
          </h1>
          <p className="text-[16px] text-slate-300">
            {totalCandidates} candidat{totalCandidates !== 1 ? 's' : ''} classifie{totalCandidates !== 1 ? 's' : ''} par score de matching
          </p>
        </section>

        <section className="overflow-hidden rounded-[26px] border border-white/10 bg-[#1b213a]/88 shadow-[0_20px_80px_rgba(2,8,23,0.28)]">
          <div className="overflow-x-auto">
            <div className="min-w-[900px]">
              <div className="grid grid-cols-[100px_minmax(200px,1fr)_140px_120px_120px_120px] border-b border-white/8 bg-white/[0.04] px-4 py-4 text-sm font-semibold uppercase tracking-[0.02em] text-slate-300">
                <span>Rang</span>
                <span>Candidat</span>
                <span className="text-center">Score global</span>
                <span className="text-center">Competences</span>
                <span className="text-center">Experience</span>
                <span className="text-center">Education</span>
              </div>

              {sortedResults.map((candidate) => (
                <div
                  key={`${candidate.rank}-${candidate.candidateName}`}
                  className="grid grid-cols-[100px_minmax(200px,1fr)_140px_120px_120px_120px] items-center border-b border-white/6 px-4 py-4 last:border-b-0"
                >
                  <div>
                    <span className="flex h-10 w-10 items-center justify-center rounded-[12px] border border-cyan-400/35 bg-cyan-400/10 text-[20px] font-semibold leading-none text-cyan-300">
                      {candidate.rank}
                    </span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-lg font-semibold text-white">{candidate.candidateName}</p>
                    <p className="text-sm text-slate-400 line-clamp-2">{candidate.summary}</p>
                  </div>
                  <p className="text-center text-xl font-semibold text-cyan-300">
                    {formatScore(candidate.matchScore)}
                  </p>
                  <div className="flex justify-center">
                    <ScoreCell score={candidate.skillsMatch} />
                  </div>
                  <div className="flex justify-center">
                    <ScoreCell score={candidate.experienceMatch} />
                  </div>
                  <div className="flex justify-center">
                    <ScoreCell score={candidate.educationMatch} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          <button
            type="button"
            onClick={() => router.push(`/pipeline/progress?jobId=${jobId}`)}
            className="flex h-[56px] items-center justify-center rounded-[14px] border border-white/10 bg-transparent px-6 text-[17px] font-semibold text-white transition-colors hover:bg-white/[0.03]"
          >
            {'← Retour'}
          </button>

          <button
            type="button"
            onClick={handleRunFinalScoring}
            className="flex h-[56px] items-center justify-center gap-3 rounded-[14px] bg-[#1f9d94] px-6 text-[17px] font-semibold text-white shadow-[0_18px_45px_rgba(31,157,148,0.28)] transition-all hover:bg-[#25afa5]"
          >
            <BarChart3 className="h-5 w-5" />
            {'Scoring final'}
          </button>

          <button
            type="button"
            onClick={handleGoToFormatting}
            className="flex h-[56px] items-center justify-center rounded-[14px] border border-white/10 bg-transparent px-6 text-[17px] font-semibold text-white transition-colors hover:bg-white/[0.03]"
          >
            {'Formater les CV'}
            <ChevronDown className="h-5 w-5 rotate-[-90deg]" />
          </button>
        </section>
      </div>
    </PipelineShell>
  );
}

export default function MatchingResultsPage() {
  return <Suspense fallback={null}><MatchingResultsContent /></Suspense>;
}
