'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { FileText, Loader2, Upload } from 'lucide-react';
import { PipelineShell } from '@/app/components/pipeline/PipelineShell';
import { usePipeline } from '@/hooks/usePipeline';

export default function TestUploadPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobId = searchParams.get('jobId');
  const { getJobStatus, runFinalPhase } = usePipeline();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [jobStage, setJobStage] = useState<string>('');
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!jobId) {
      setError("Aucun identifiant de traitement n'a ete fourni.");
      setLoading(false);
      return;
    }

    let cancelled = false;

    const checkJob = async () => {
      try {
        const statusPayload = await getJobStatus(jobId);
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

        if (['final_complete', 'format_complete'].includes(job.stage)) {
          router.push(`/pipeline/final?jobId=${jobId}`);
          return;
        }

        setLoading(false);
      } catch {
        if (!cancelled) {
          setError("Impossible de verifier l'etat du traitement.");
          setLoading(false);
        }
      }
    };

    void checkJob();
  }, [jobId, getJobStatus, router]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      const ext = files[0].name.split('.').pop()?.toLowerCase();
      if (ext && ['txt', 'xlsx', 'csv'].includes(ext)) {
        setFile(files[0]);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      setFile(files[0]);
    }
  };

  const handleContinue = async () => {
    if (!jobId) {
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await runFinalPhase(jobId, file);
      router.push(`/pipeline/final?jobId=${jobId}`);
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : 'Erreur inconnue';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <PipelineShell>
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-cyan-300" />
          <p className="text-lg text-slate-200">Chargement...</p>
        </div>
      </PipelineShell>
    );
  }

  return (
    <PipelineShell>
      <div className="mx-auto max-w-[720px] space-y-10">
        <section className="space-y-5">
          <h1 className="text-[42px] font-semibold tracking-[-0.05em] text-white md:text-[52px]">
            {'Scores de tests'}
          </h1>
          <p className="text-lg text-slate-300">
            {'Vous pouvez telecharger les scores de tests pour les combiner avec les scores d\'appariement.'}
          </p>
          <p className="text-sm text-slate-400">
            {'Si vous ne telechargez pas de fichier, seuls les scores d\'appariement seront utilises.'}
          </p>
        </section>

        <section className="overflow-hidden rounded-[26px] border border-white/10 bg-[#1b213a]/88 p-8 shadow-[0_20px_80px_rgba(2,8,23,0.28)]">
          <form
            onDragEnter={handleDrag}
            className="space-y-6"
          >
            <div
              className={`relative flex flex-col items-center justify-center rounded-[16px] border-2 border-dashed p-10 transition-colors ${
                dragActive
                  ? 'border-cyan-400 bg-cyan-400/5'
                  : file
                  ? 'border-emerald-400/50 bg-emerald-400/5'
                  : 'border-white/20 bg-white/[0.02]'
              }`}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                type="file"
                accept=".txt,.xlsx,.csv"
                onChange={handleFileChange}
                className="absolute inset-0 cursor-pointer opacity-0"
              />

              {file ? (
                <div className="flex flex-col items-center gap-4 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/15">
                    <FileText className="h-7 w-7 text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-white">{file.name}</p>
                    <p className="text-sm text-slate-400">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <p className="text-sm text-cyan-300">Cliquez ou deposer pour remplacer</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-cyan-400/10">
                    <Upload className="h-7 w-7 text-cyan-400" />
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-white">
                      Deposer votre fichier ici
                    </p>
                    <p className="text-sm text-slate-400">
                      ou cliquer pour parcourir
                    </p>
                  </div>
                  <p className="text-sm text-slate-500">
                    Formats acceptes: .txt, .xlsx, .csv
                  </p>
                </div>
              )}
            </div>

            {file && (
              <button
                type="button"
                onClick={() => setFile(null)}
                className="w-full text-sm text-slate-400 hover:text-slate-300"
              >
                Supprimer le fichier
              </button>
            )}
          </form>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <button
            type="button"
            onClick={() => router.push(`/pipeline/results?jobId=${jobId}`)}
            disabled={submitting}
            className="flex h-[62px] items-center justify-center rounded-[14px] border border-white/10 bg-transparent px-6 text-[18px] font-semibold text-white transition-colors hover:bg-white/[0.03] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {'← Retour'}
          </button>

          <button
            type="button"
            onClick={handleContinue}
            disabled={submitting}
            className="flex h-[62px] items-center justify-center gap-3 rounded-[14px] bg-[#1f9d94] px-6 text-[18px] font-semibold text-white shadow-[0_18px_45px_rgba(31,157,148,0.28)] transition-all hover:bg-[#25afa5] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Traitement en cours...
              </>
            ) : (
              'Continuer'
            )}
          </button>
        </section>
      </div>
    </PipelineShell>
  );
}