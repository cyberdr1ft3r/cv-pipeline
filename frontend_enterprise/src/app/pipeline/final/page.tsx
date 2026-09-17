'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, Check, Loader2 } from 'lucide-react';
import { PipelineShell } from '@/app/components/pipeline/PipelineShell';
import { usePipeline } from '@/hooks/usePipeline';

type PipelineJob = {
  job_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  stage: string;
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

type FinalRow = {
  candidate_name: string;
  overall_score: number | null;
  test_score: number | null;
  final_score: number | null;
  rank: number | null;
};

type FinalResultsResponse = {
  session_id: string;
  rows: FinalRow[];
};

function CompletionIcon() {
  return (
    <div className="mx-auto flex h-[108px] w-[108px] items-center justify-center rounded-full border border-cyan-400/75 bg-cyan-400/10 shadow-[0_0_0_1px_rgba(34,211,238,0.1)]">
      <div className="flex h-[48px] w-[48px] items-center justify-center rounded-full border border-cyan-300 bg-transparent">
        <Check className="h-7 w-7 text-cyan-300" />
      </div>
    </div>
  );
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--';
  }

  const normalized = value <= 1 ? value * 100 : value;
  return `${normalized.toFixed(1)}%`;
}

function normalizeErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }

  return 'Erreur inconnue';
}

function PipelineFinalContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobId = searchParams.get('jobId');
  const { getFinalResults, getJobStatus } = usePipeline();

  const [rows, setRows] = useState<FinalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [waitingForResults, setWaitingForResults] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setError("Aucun identifiant de traitement n'a \u00e9t\u00e9 fourni.");
      setLoading(false);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const pollUntilReady = async () => {
      try {
        const finalPayload = (await getFinalResults(jobId)) as FinalResultsResponse;
        if (cancelled) {
          return;
        }

        setRows(finalPayload.rows || []);
        setWaitingForResults(false);
        setError(null);
        setLoading(false);
        return;
      } catch (finalError) {
        const message = normalizeErrorMessage(finalError);
        const isNotFound = message.includes('404') || message.toLowerCase().includes('not found');

        if (!isNotFound) {
          if (!cancelled) {
            setError(message);
            setWaitingForResults(false);
            setLoading(false);
          }
          return;
        }
      }

      try {
        const statusPayload = (await getJobStatus(jobId)) as JobStatusResponse;
        if (cancelled) {
          return;
        }

        const stage = statusPayload.job.stage;
        const status = statusPayload.job.status;

        if (status === 'failed') {
          setError("Le scoring final n'a pas pu \u00eatre calcul\u00e9.");
          setWaitingForResults(false);
          setLoading(false);
          return;
        }

        if (stage === 'format_complete') {
          router.replace(`/pipeline/format?jobId=${jobId}`);
          return;
        }

        if (!cancelled) {
          setWaitingForResults(true);
          setLoading(false);
          timer = setTimeout(pollUntilReady, 2000);
        }
      } catch (statusError) {
        if (!cancelled) {
          setError(normalizeErrorMessage(statusError));
          setWaitingForResults(false);
          setLoading(false);
        }
      }
    };

  void pollUntilReady();

  return () => {
    cancelled = true;
    if (timer) {
      clearTimeout(timer);
    }
  };
}, [getFinalResults, getJobStatus, jobId, router]);

const sortedRows = useMemo(
  () =>
    [...rows].sort((left, right) => {
      const leftRank = left.rank ?? Number.MAX_SAFE_INTEGER;
      const rightRank = right.rank ?? Number.MAX_SAFE_INTEGER;
      return leftRank - rightRank;
    }),
  [rows]
);

  return (
    <PipelineShell>
      <div className="mx-auto max-w-[1120px] space-y-14">
        {loading ? (
          <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
            <Loader2 className="h-8 w-8 animate-spin text-cyan-300" />
            <p className="text-lg text-slate-200">{'Chargement du scoring final...'}</p>
          </div>
        ) : waitingForResults ? (
          <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 text-center">
            <Loader2 className="h-16 w-16 animate-spin text-cyan-400" />
            <p className="text-xl font-medium text-cyan-300">
              {'Calcul du scoring final...'}
            </p>
          </div>
        ) : error ? (
          <div className="mx-auto mt-10 max-w-[820px] rounded-[28px] border border-red-400/20 bg-red-500/10 px-6 py-5">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
              <div>
                <p className="font-semibold text-red-100">{'Impossible de charger le scoring final'}</p>
                <p className="mt-1 text-sm text-red-100/85">{error}</p>
              </div>
            </div>
          </div>
        ) : (
          <>
            <section className="pt-2 text-center">
              <div className="mx-auto max-w-[780px] space-y-2">
                <h1 className="text-[28px] font-semibold tracking-[-0.05em] text-white md:text-[32px]">
                  {'Scoring final termin\u00e9'}
                </h1>
                <p className="text-[14px] text-slate-200">
                  {'Les classements finaux ont \u00e9t\u00e9 calcul\u00e9s'}
                </p>
              </div>
            </section>

            <section className="overflow-hidden rounded-[26px] border border-white/10 bg-[#1b213a]/88 shadow-[0_20px_80px_rgba(2,8,23,0.28)]">
              <div className="overflow-x-auto">
                <div className="min-w-[924px]">
                  <div className="grid grid-cols-[134px_minmax(240px,1fr)_220px_190px_190px] border-b border-white/8 bg-white/[0.04] px-3 py-3 text-xs font-semibold uppercase tracking-[0.02em] text-slate-300">
                    <span>Rang</span>
                    <span>Candidat</span>
                    <span className="text-center">{'Score global'}</span>
                    <span className="text-center">{'Score test'}</span>
                    <span className="text-center">{'Score final'}</span>
                  </div>

                  {sortedRows.map((row) => (
                    <div
                      key={`${row.rank ?? 'na'}-${row.candidate_name}`}
                      className="grid grid-cols-[134px_minmax(240px,1fr)_220px_190px_190px] items-center border-b border-white/6 px-3 py-3 last:border-b-0"
                    >
                      <div>
                        <span className="flex h-8 w-8 items-center justify-center rounded-[10px] border border-cyan-400/35 bg-cyan-400/10 text-[20px] font-semibold leading-none text-cyan-300">
                          {row.rank ?? '-'}
                        </span>
                      </div>
                      <p className="pr-4 text-[16px] font-semibold text-white">{row.candidate_name}</p>
                      <p className="text-center text-[18px] font-semibold text-cyan-300">
                        {formatPercent(row.overall_score)}
                      </p>
                      <p className="text-center text-[18px] font-semibold text-amber-300">
                        {formatPercent(row.test_score)}
                      </p>
                      <p className="text-center text-[18px] font-semibold text-emerald-300">
                        {formatPercent(row.final_score)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section className="grid gap-3 md:grid-cols-2">
              <button
                type="button"
                onClick={() => router.push(`/pipeline/progress?jobId=${jobId}`)}
                className="flex h-[52px] items-center justify-center rounded-[14px] border border-white/10 bg-transparent px-5 text-[16px] font-semibold text-white transition-colors hover:bg-white/[0.03]"
              >
                {'\u2190 Retour aux r\u00e9sultats'}
              </button>

              <button
                type="button"
                onClick={() => router.push(`/pipeline/template-select?jobId=${jobId}`)}
                className="flex h-[52px] items-center justify-center rounded-[14px] bg-[#1f9d94] px-5 text-[16px] font-semibold text-white shadow-[0_18px_45px_rgba(31,157,148,0.28)] transition-all hover:bg-[#25afa5]"
              >
                {'Formater les CV \u2192'}
              </button>
            </section>
          </>
        )}
      </div>
    </PipelineShell>
  );
}

export default function PipelineFinalPage() {
  return <Suspense fallback={null}><PipelineFinalContent /></Suspense>;
}
