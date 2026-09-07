'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, Download, Loader2 } from 'lucide-react';
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

function DownloadIcon() {
  return (
    <div className="mx-auto flex h-[108px] w-[108px] items-center justify-center rounded-full border border-cyan-400/75 bg-cyan-400/10 shadow-[0_0_0_1px_rgba(34,211,238,0.1)]">
      <div className="flex h-[48px] w-[48px] items-center justify-center rounded-full border border-cyan-300 bg-transparent">
        <Download className="h-7 w-7 text-cyan-300" />
      </div>
    </div>
  );
}

function normalizeErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }

  return 'Erreur inconnue';
}

export default function PipelineFormatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobId = searchParams.get('jobId');
  const { getArtifactDownloadUrl, getJobStatus, runFormatPhase } = usePipeline();

  const [loading, setLoading] = useState(true);
  const [formatting, setFormatting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('classic');
  const hasTriggeredFormatting = useRef(false);

  useEffect(() => {
    if (!jobId) {
      setError("Aucun identifiant de traitement n'a \u00e9t\u00e9 fourni.");
      setLoading(false);
      return;
    }

    // Get template and limit from URL params
    const template = searchParams.get('template') || 'classic';
    setSelectedTemplate(template);

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const checkFormattingState = async () => {
      try {
        const payload = (await getJobStatus(jobId)) as JobStatusResponse;
        if (cancelled) {
          return;
        }

      const stage = payload.job.stage;
      const status = payload.job.status;

      if (status === 'failed') {
          setError("Le formatage n'a pas pu \u00eatre termin\u00e9.");
          setFormatting(false);
          setLoading(false);
          return;
        }

        if (stage === 'format_complete') {
          setFormatting(false);
          setError(null);
          setLoading(false);
          return;
        }

        // If already running format, just poll
        if (stage === 'running_format') {
          if (!cancelled) {
            setFormatting(true);
            setLoading(false);
            timer = setTimeout(checkFormattingState, 2000);
          }
          return;
        }

        // Only trigger format phase once from matching_complete or final_complete
        if ((stage === 'matching_complete' || stage === 'final_complete') && !hasTriggeredFormatting.current) {
          hasTriggeredFormatting.current = true;
          setFormatting(true);
          setLoading(false);
          const limit = searchParams.get('limit');
          await runFormatPhase(jobId, template, limit ? parseInt(limit) : undefined);
          if (!cancelled) {
            timer = setTimeout(checkFormattingState, 2000);
          }
          return;
        }

        if (!cancelled) {
          setFormatting(true);
          setLoading(false);
          timer = setTimeout(checkFormattingState, 2000);
        }
      } catch (statusError) {
        if (!cancelled) {
          setError(normalizeErrorMessage(statusError));
          setFormatting(false);
          setLoading(false);
        }
      }
    };

    void checkFormattingState();

    return () => {
      cancelled = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [getJobStatus, jobId, router, runFormatPhase, searchParams]);

const handleDownload = () => {
    if (!jobId) {
      return;
    }

    window.open(getArtifactDownloadUrl(jobId, 'formatted_zip'), '_blank', 'noopener,noreferrer');
  };

  return (
    <PipelineShell>
      <div className="mx-auto max-w-[1120px] space-y-14">
        {loading ? (
          <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
            <Loader2 className="h-8 w-8 animate-spin text-cyan-300" />
            <p className="text-lg text-slate-200">{'Chargement du formatage...'}</p>
          </div>
        ) : formatting ? (
          <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 text-center">
            <Loader2 className="h-16 w-16 animate-spin text-cyan-400" />
            <p className="text-xl font-medium text-cyan-300">
              {'Formatage des CVs...'}
            </p>
          </div>
        ) : error ? (
          <div className="mx-auto mt-10 max-w-[820px] rounded-[28px] border border-red-400/20 bg-red-500/10 px-6 py-5">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
              <div>
                <p className="font-semibold text-red-100">{'Impossible de finaliser le formatage'}</p>
                <p className="mt-1 text-sm text-red-100/85">{error}</p>
              </div>
            </div>
          </div>
        ) : (
          <>
            <section className="space-y-3">
              <div className="space-y-3">
                <h1 className="text-[36px] font-semibold tracking-[-0.05em] text-white md:text-[42px]">
                  {'Formater et exporter les CV'}
                </h1>
                <p className="text-[16px] text-slate-200">
                  {'S\u00e9lectionnez un mod\u00e8le et t\u00e9l\u00e9chargez vos CV de candidats format\u00e9s'}
                </p>
              </div>
            </section>

            <section className="pt-2 text-center">
              <DownloadIcon />
              <div className="mx-auto mt-8 max-w-[760px] space-y-3">
                <h2 className="text-[36px] font-semibold tracking-[-0.05em] text-white md:text-[42px]">
                  {'Formatage termin\u00e9 !'}
                </h2>
                <p className="text-[16px] text-slate-200">
                  {'Vos CV format\u00e9s sont pr\u00eats pour le t\u00e9l\u00e9chargement'}
                </p>
              </div>
            </section>

            <section className="rounded-[26px] border border-white/10 bg-[#1b213a]/88 px-8 py-10 text-center shadow-[0_20px_80px_rgba(2,8,23,0.28)]">
              <p className="text-[16px] text-slate-300">
                {'Mod\u00e8le : '}
                <span className="font-semibold text-cyan-300">{selectedTemplate.charAt(0).toUpperCase() + selectedTemplate.slice(1)}</span>
              </p>
              <p className="mt-6 text-[16px] text-slate-400">
                {'Tous les CV ont \u00e9t\u00e9 format\u00e9s et regroup\u00e9s dans une archive ZIP.'}
              </p>
            </section>

            <section className="sticky bottom-6 z-10 grid gap-4 md:grid-cols-2">
              <button
                type="button"
                onClick={handleDownload}
                className="flex h-[56px] w-full items-center justify-center gap-3 rounded-[14px] bg-[#1f9d94] px-6 text-[17px] font-semibold text-white shadow-[0_18px_45px_rgba(31,157,148,0.28)] transition-all hover:bg-[#25afa5]"
              >
                <Download className="h-5 w-5" />
                {'T\u00e9l\u00e9charger les CV format\u00e9s (ZIP)'}
              </button>

              <button
                type="button"
                onClick={() => router.push('/pipeline')}
                className="flex h-[56px] w-full items-center justify-center rounded-[14px] border border-white/10 bg-transparent px-6 text-[17px] font-semibold text-white transition-colors hover:bg-white/[0.03]"
              >
                {'\u2190 Nouveau traitement'}
              </button>
            </section>
          </>
        )}
      </div>
    </PipelineShell>
  );
}
