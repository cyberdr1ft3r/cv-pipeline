'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Download,
  FileText,
  Loader2,
  RefreshCw,
  Sparkles,
  Upload,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

type CvAlignmentPageProps = {
  spaceLabel: string;
};

type AlignmentStatus = {
  alignment_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  progress?: number;
  stage_label?: string;
  filename?: string;
  download_url?: string;
  offer_filename?: string;
  cv_filename?: string;
  offer_chars?: number;
  cv_chars?: number;
  error?: string;
  created_at?: string;
  updated_at?: string;
};

function isActive(status?: AlignmentStatus | null) {
  return status?.status === 'queued' || status?.status === 'running';
}

function statusLabel(status: AlignmentStatus['status']) {
  if (status === 'succeeded') return 'Prêt';
  if (status === 'failed') return 'Échec';
  if (status === 'queued') return 'En attente';
  return 'En cours';
}

function statusClasses(status: AlignmentStatus['status']) {
  if (status === 'succeeded') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (status === 'failed') return 'border-red-200 bg-red-50 text-red-700';
  if (status === 'queued') return 'border-slate-200 bg-slate-50 text-slate-700';
  return 'border-blue-200 bg-blue-50 text-blue-700';
}

function formatDate(value?: string) {
  if (!value) return 'Date inconnue';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Date inconnue';
  return date.toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function friendlyAlignmentError(error?: string) {
  const message = error || '';
  const lowered = message.toLowerCase();
  if (
    lowered.includes('more credits') ||
    lowered.includes('402') ||
    lowered.includes('crédits openrouter') ||
    lowered.includes('credits openrouter')
  ) {
    return "Crédits OpenRouter insuffisants pour générer ce CV. Ajoutez des crédits ou utilisez un modèle moins coûteux, puis relancez.";
  }
  if (lowered.includes('json valide') || lowered.includes('valid json')) {
    return "Le modèle n'a pas retourné un format exploitable. Relancez avec un CV plus court ou un modèle plus fiable.";
  }
  if (lowered.includes('timed out') || lowered.includes('timeout')) {
    return "L'alignement prend plus de temps que prévu. Réessayez avec un CV plus court ou un modèle plus rapide.";
  }
  return message || "Erreur lors de l'alignement du CV.";
}

export default function CvAlignmentPage({ spaceLabel }: CvAlignmentPageProps) {
  const [offerFile, setOfferFile] = useState<File | null>(null);
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeAlignmentId, setActiveAlignmentId] = useState<string | null>(null);
  const [activeAlignment, setActiveAlignment] = useState<AlignmentStatus | null>(null);
  const [recent, setRecent] = useState<AlignmentStatus[]>([]);
  const [loadingRecent, setLoadingRecent] = useState(false);

  const canSubmit = Boolean(offerFile && cvFile && !submitting);
  const progress = Math.max(0, Math.min(100, activeAlignment?.progress ?? (isActive(activeAlignment) ? 10 : 0)));
  const activeIsDone = activeAlignment?.status === 'succeeded';

  const refreshRecent = useCallback(async () => {
    setLoadingRecent(true);
    try {
      const res = await fetch(`${API_BASE}/cv-alignments/recent?limit=5`, {
        credentials: 'include',
        cache: 'no-store',
      });
      const data = await res.json().catch(() => null);
      if (res.ok) setRecent(data?.alignments ?? []);
    } finally {
      setLoadingRecent(false);
    }
  }, []);

  const refreshActive = useCallback(async (alignmentId: string) => {
    const res = await fetch(`${API_BASE}/cv-alignments/${alignmentId}`, {
      credentials: 'include',
      cache: 'no-store',
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.detail || "Erreur lors de l'alignement du CV.");
    setActiveAlignment(data);
    return data as AlignmentStatus;
  }, []);

  useEffect(() => {
    void refreshRecent();
  }, [refreshRecent]);

  useEffect(() => {
    if (!activeAlignmentId) return;
    let cancelled = false;
    const alignmentId = activeAlignmentId;

    async function tick() {
      try {
        const status = await refreshActive(alignmentId);
        await refreshRecent();
        if (!cancelled && isActive(status)) {
          window.setTimeout(tick, 2500);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Erreur temporaire lors de la vérification du statut.");
        }
      }
    }

    void tick();
    return () => {
      cancelled = true;
    };
  }, [activeAlignmentId, refreshActive, refreshRecent]);

  async function submitAlignment() {
    if (!offerFile || !cvFile) return;
    setSubmitting(true);
    setError(null);
    setActiveAlignment(null);

    try {
      const fd = new FormData();
      fd.append('offer_file', offerFile);
      fd.append('cv_file', cvFile);
      fd.append('language', 'fr');

      const res = await fetch(`${API_BASE}/cv-alignments`, {
        method: 'POST',
        credentials: 'include',
        body: fd,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.detail || "Erreur lors de l'alignement du CV.");
      }

      const queued: AlignmentStatus = {
        alignment_id: data.alignment_id,
        status: data.status ?? 'queued',
        progress: data.progress ?? 5,
        stage_label: data.stage_label ?? 'En attente',
        offer_filename: offerFile.name,
        cv_filename: cvFile.name,
        created_at: new Date().toISOString(),
      };
      setActiveAlignment(queued);
      setActiveAlignmentId(data.alignment_id);
      await refreshRecent();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors de l'alignement du CV.");
    } finally {
      setSubmitting(false);
    }
  }

  function openDownload(downloadUrl?: string) {
    if (!downloadUrl) return;
    window.open(downloadUrl, '_blank', 'noopener,noreferrer');
  }

  const activeCard = useMemo(() => {
    if (!activeAlignment) return null;
    return (
      <div className={`mt-5 rounded-lg border px-4 py-4 ${statusClasses(activeAlignment.status)}`}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {isActive(activeAlignment) && <Loader2 className="h-4 w-4 animate-spin" />}
              {activeAlignment.status === 'succeeded' && <CheckCircle2 className="h-4 w-4" />}
              {activeAlignment.status === 'failed' && <AlertCircle className="h-4 w-4" />}
              <p className="font-semibold">{statusLabel(activeAlignment.status)}</p>
            </div>
            <p className="mt-1 truncate text-sm">
              {activeAlignment.cv_filename || activeAlignment.filename || 'CV aligné'}
            </p>
            <p className="mt-1 text-xs opacity-80">
              {activeAlignment.stage_label || (isActive(activeAlignment) ? 'Traitement en cours' : '')}
            </p>
          </div>
          {activeIsDone && (
            <button
              onClick={() => openDownload(activeAlignment.download_url)}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-700 sm:w-auto"
            >
              <Download className="h-4 w-4" />
              Télécharger
            </button>
          )}
        </div>
        {isActive(activeAlignment) && (
          <div className="mt-4">
            <div className="mb-1 flex items-center justify-between text-xs">
              <span>Progression</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/70">
              <div className="h-full rounded-full bg-[#2f66ed] transition-all" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-2 text-xs opacity-80">
              Vous pouvez quitter cette page. Le CV restera disponible dans les derniers CV alignés.
            </p>
          </div>
        )}
        {activeAlignment.status === 'failed' && activeAlignment.error && (
          <p className="mt-3 text-sm">{friendlyAlignmentError(activeAlignment.error)}</p>
        )}
      </div>
    );
  }, [activeAlignment, activeIsDone, progress]);

  return (
    <div className="mx-auto max-w-6xl space-y-5 sm:space-y-7">
      <section className="rounded-lg border border-[#d8e0ea] bg-white p-5 sm:p-8">
        <p className="text-sm font-semibold uppercase tracking-wide text-[#2f66ed]">{spaceLabel}</p>
        <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <h1 className="text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">Aligner un CV</h1>
            <p className="mt-2 max-w-2xl text-slate-600">
              Adaptez un CV précis à une offre sans passer par la CVthèque ni le pipeline de matching.
            </p>
          </div>
          <div className="inline-flex w-fit max-w-full items-center gap-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700">
            <Sparkles className="h-4 w-4" />
            <span className="min-w-0">Sans invention de contenu</span>
          </div>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <FileDrop label="Offre ou description de poste" helper="PDF, DOCX ou TXT" file={offerFile} onChange={setOfferFile} />
        <FileDrop label="CV à aligner" helper="PDF, DOCX ou TXT" file={cvFile} onChange={setCvFile} />
      </section>

      <section className="rounded-lg border border-[#d8e0ea] bg-white p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Génération</h2>
            <p className="mt-1 text-sm text-slate-600">
              Le CV sera reformulé et réorganisé pour mieux refléter l&apos;offre, uniquement à partir des éléments existants.
            </p>
          </div>
          <button
            onClick={submitAlignment}
            disabled={!canSubmit}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#2f66ed] px-5 py-3 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(47,102,237,0.22)] transition hover:bg-[#2458d8] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {submitting ? 'Démarrage...' : 'Aligner le CV'}
          </button>
        </div>

        {error && (
          <div className="mt-5 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {activeCard}
      </section>

      <section className="rounded-lg border border-[#d8e0ea] bg-white p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Derniers CV alignés</h2>
            <p className="mt-1 text-sm text-slate-600">Les 5 dernières générations restent accessibles ici.</p>
          </div>
          <button
            type="button"
            onClick={refreshRecent}
            className="inline-flex items-center gap-2 rounded-lg border border-[#d8e0ea] bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-[#2f66ed]/40 hover:text-[#2f66ed]"
          >
            <RefreshCw className={`h-4 w-4 ${loadingRecent ? 'animate-spin' : ''}`} />
            Actualiser
          </button>
        </div>

        <div className="mt-5 space-y-3">
          {recent.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[#d8e0ea] bg-slate-50 px-4 py-6 text-center text-sm text-slate-600">
              Aucun CV aligné pour le moment.
            </div>
          ) : (
            recent.map(item => (
              <div key={item.alignment_id} className="flex flex-col gap-3 rounded-lg border border-[#e5ebf2] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate font-medium text-slate-950">{item.cv_filename || item.filename || 'CV aligné'}</p>
                    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusClasses(item.status)}`}>
                      {statusLabel(item.status)}
                    </span>
                  </div>
                  <p className="mt-1 truncate text-sm text-slate-600">
                    Offre : {item.offer_filename || 'Non renseignée'}
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <Clock className="h-3.5 w-3.5" />
                    <span>{formatDate(item.created_at || item.updated_at)}</span>
                    {isActive(item) && <span>{item.progress ?? 10}% · {item.stage_label || 'Traitement en cours'}</span>}
                    {item.status === 'failed' && item.error && <span className="text-red-600">{friendlyAlignmentError(item.error)}</span>}
                  </div>
                  {isActive(item) && (
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full rounded-full bg-[#2f66ed]" style={{ width: `${Math.max(5, Math.min(100, item.progress ?? 10))}%` }} />
                    </div>
                  )}
                </div>
                {item.status === 'succeeded' && item.download_url && (
                  <button
                    onClick={() => openDownload(item.download_url)}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 sm:w-auto"
                  >
                    <Download className="h-4 w-4" />
                    Télécharger
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function FileDrop({
  label,
  helper,
  file,
  onChange,
}: {
  label: string;
  helper: string;
  file: File | null;
  onChange: (file: File | null) => void;
}) {
  const inputId = label.replace(/\W+/g, '-').toLowerCase();

  return (
    <label htmlFor={inputId} className="block cursor-pointer rounded-lg border border-[#d8e0ea] bg-white p-5 transition hover:border-[#2f66ed] sm:p-6">
      <input
        id={inputId}
        type="file"
        accept=".pdf,.docx,.txt"
        className="hidden"
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-[#2f66ed]">
          {file ? <FileText className="h-5 w-5" /> : <Upload className="h-5 w-5" />}
        </span>
        <div className="min-w-0 max-w-full">
          <p className="font-semibold text-slate-950">{label}</p>
          <p className="mt-1 text-sm text-slate-600">{helper}</p>
          {file && (
            <p className="mt-4 truncate rounded-lg bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700">
              {file.name}
            </p>
          )}
        </div>
      </div>
    </label>
  );
}
