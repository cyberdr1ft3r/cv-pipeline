'use client';

import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { CheckCircle2, FileText, Loader2, RefreshCw, X, XCircle } from 'lucide-react';
import type { StagingFile } from '@/hooks/useStagingUpload';
import { profileLabelFr, seniorityLabelFr } from '@/lib/uploadLabels';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

/** Speaks the routing outcome in plain French, not a raw filesystem path — the
 * profile/seniority hint is stable for the file's whole lifecycle (set once in
 * addFiles), so there's no need to parse the server's absolute staging path. */
function routingLabel(f: StagingFile): string {
  if (f.profile && f.seniority) return `Classé dans : ${profileLabelFr(f.profile)} · ${seniorityLabelFr(f.seniority)}`;
  if (f.profile) return `Classé dans : ${profileLabelFr(f.profile)}`;
  return 'Profil détecté automatiquement au traitement';
}

interface FileStatusListProps {
  files: StagingFile[];
  onRemove: (id: string) => void;
  onRetry: (id: string) => void;
  disabled?: boolean;
}

const STATUS_BADGE: Record<
  StagingFile['status'],
  { label: string; classes: string; icon: React.ReactNode }
> = {
  pending: {
    label: 'En attente',
    classes: 'border-slate-200 bg-slate-50 text-slate-600',
    icon: null,
  },
  uploading: {
    label: 'En cours',
    classes: 'border-blue-200 bg-blue-50 text-blue-700',
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  uploaded: {
    label: 'Envoyé',
    classes: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    icon: <CheckCircle2 className="h-3 w-3" />,
  },
  error: {
    label: 'Erreur',
    classes: 'border-red-200 bg-red-50 text-red-700',
    icon: <XCircle className="h-3 w-3" />,
  },
};

export function FileStatusList({ files, onRemove, onRetry, disabled = false }: FileStatusListProps) {
  const reducedMotion = usePrefersReducedMotion();
  if (files.length === 0) return null;

  return (
    <div className="space-y-2">
      <p aria-live="polite" className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {files.length} fichier{files.length > 1 ? 's' : ''} —{' '}
        {formatBytes(files.reduce((a, f) => a + f.file.size, 0))}
      </p>

      <AnimatePresence initial={false}>
        {files.map((entry) => {
          const badge = STATUS_BADGE[entry.status];
          const label = routingLabel(entry);
          const hasProfile = !!(entry.profile);

          return (
            <motion.div
              key={entry.id}
              initial={reducedMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reducedMotion ? { opacity: 0 } : { opacity: 0, x: -12, transition: { duration: 0.15 } }}
              className="rounded-xl border border-[#d8e0ea] bg-white px-4 py-3 shadow-sm"
            >
              <div className="flex items-center gap-3">
                {/* File icon */}
                <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-blue-50 text-[#2f66ed]">
                  <FileText className="h-4 w-4" />
                </span>

                {/* Name + routing */}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-900">{entry.file.name}</p>
                  <p className={`text-xs ${hasProfile ? 'text-[#2f66ed]' : 'text-slate-500'}`}>
                    {label}
                  </p>
                </div>

                {/* Status badge */}
                <span
                  className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${badge.classes}`}
                >
                  {badge.icon}
                  {badge.label}
                </span>

                {/* Retry button (errors only) */}
                {entry.status === 'error' && (
                  <button
                    type="button"
                    onClick={() => onRetry(entry.id)}
                    disabled={disabled}
                    title="Réessayer"
                    aria-label={`Réessayer l'envoi de ${entry.file.name}`}
                    className="rounded-full p-1.5 text-slate-400 transition-colors hover:bg-blue-50 hover:text-[#2f66ed] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </button>
                )}

                {/* Remove button (pending only) */}
                {entry.status === 'pending' && (
                  <button
                    type="button"
                    onClick={() => onRemove(entry.id)}
                    disabled={disabled}
                    title={`Retirer ${entry.file.name}`}
                    aria-label={`Retirer ${entry.file.name}`}
                    className="rounded-full p-1.5 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>

              {/* Path warning (amber) — folder dropped but profile not parseable */}
              {entry.pathWarning && (
                <p className="mt-1 pl-12 text-xs text-amber-700">{entry.pathWarning}</p>
              )}

              {/* Inline error message */}
              {entry.status === 'error' && entry.error && (
                <p role="alert" className="mt-1 pl-12 text-xs text-red-600">{entry.error}</p>
              )}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
