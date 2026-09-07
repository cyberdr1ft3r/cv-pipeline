'use client';

import React, { useCallback, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { Upload, X } from 'lucide-react';
import type { StagingFileInput } from '@/hooks/useStagingUpload';
import { profileLabelFr, seniorityLabelFr } from '@/lib/uploadLabels';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.doc'];
const KNOWN_SENIORITIES = new Set(['junior', 'confirme', 'senior', 'expert']);

function isSupportedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

function isHiddenFile(name: string): boolean {
  return name.startsWith('.') || name.startsWith('._') || name === '.DS_Store';
}

/**
 * Traverse a dropped directory and return all supported files with their
 * relative paths from the dropped root entry (root name included as prefix).
 * e.g. dropping "BusinessAnalyst" yields relativePaths like
 *   "BusinessAnalyst/Junior/cv.pdf"
 */
async function readDirectoryRecursive(
  entry: FileSystemDirectoryEntry,
  prefix: string
): Promise<{ file: File; relativePath: string }[]> {
  const results: { file: File; relativePath: string }[] = [];
  const reader = entry.createReader();

  const readBatch = (): Promise<FileSystemEntry[]> =>
    new Promise((resolve) => reader.readEntries(resolve, () => resolve([])));

  let batch = await readBatch();
  while (batch.length > 0) {
    for (const child of batch) {
      if (isHiddenFile(child.name)) continue;
      const childPath = `${prefix}/${child.name}`;
      if (child.isFile) {
        const fileEntry = child as FileSystemFileEntry;
        const file = await new Promise<File>((resolve, reject) =>
          fileEntry.file(resolve, reject)
        );
        if (isSupportedFile(file)) results.push({ file, relativePath: childPath });
      } else if (child.isDirectory) {
        const sub = await readDirectoryRecursive(child as FileSystemDirectoryEntry, childPath);
        results.push(...sub);
      }
    }
    batch = await readBatch();
  }
  return results;
}

/**
 * Parse profile and seniority from a relative path built from a dropped folder.
 *
 * Scans path segments (excluding the filename) in order for the first segment
 * matching a known profile (case-insensitive), then checks the next segment for
 * a known seniority. Works for any folder depth:
 *   "BusinessAnalyst/Junior/cv.pdf"       → profile=BusinessAnalyst seniority=Junior
 *   "CVs/DevOps/Senior/cv.pdf"            → profile=DevOps seniority=Senior
 *   "Junior/cv.pdf"                       → no profile found → pathWarning set
 *   "BusinessAnalyst/cv.pdf"              → profile=BusinessAnalyst only
 */
function parseRelativePath(
  relativePath: string,
  profiles: string[]
): { profile?: string; seniority?: string; pathWarning?: string } {
  // segments excluding the filename
  const parts = relativePath.split('/');
  const segments = parts.slice(0, -1);

  // Build case-insensitive lookup: lowercase → canonical name
  const profileLookup = new Map(profiles.map((p) => [p.toLowerCase(), p]));

  let profile: string | undefined;
  let profileIdx = -1;

  for (let i = 0; i < segments.length; i++) {
    const canonical = profileLookup.get(segments[i].toLowerCase());
    if (canonical) {
      profile = canonical;
      profileIdx = i;
      break;
    }
  }

  let seniority: string | undefined;
  if (profile !== undefined && profileIdx + 1 < segments.length) {
    const next = segments[profileIdx + 1].toLowerCase();
    if (KNOWN_SENIORITIES.has(next)) {
      seniority = next; // stored lowercase — backend normalises capitalisation
    }
  }

  const pathWarning = profile === undefined
    ? 'Profil non détecté dans le chemin — dépôt automatique'
    : undefined;

  return { profile, seniority, pathWarning };
}

interface StagingDropZoneProps {
  onFilesAdded: (files: StagingFileInput[]) => void;
  profiles: string[];
  defaultProfile?: string;
  defaultSeniority?: string;
  disabled?: boolean;
}

export function StagingDropZone({
  onFilesAdded,
  profiles,
  defaultProfile,
  defaultSeniority,
  disabled = false,
}: StagingDropZoneProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const [emptyFolderMsg, setEmptyFolderMsg] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const reducedMotion = usePrefersReducedMotion();

  const handleDragState = useCallback(
    (e: React.DragEvent, active: boolean) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled) setIsDragActive(active);
    },
    [disabled]
  );

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragActive(false);
      if (disabled) return;

      // DataTransferItemList is invalidated after the first await, so all
      // entries must be extracted synchronously before any async work.
      type Collected =
        | { kind: 'fallback'; file: File }
        | { kind: 'entry'; entry: FileSystemEntry };

      const collected: Collected[] = [];
      for (const item of Array.from(e.dataTransfer.items)) {
        if (item.kind !== 'file') continue;
        const entry = item.webkitGetAsEntry?.();
        if (!entry) {
          const file = item.getAsFile();
          if (file && !isHiddenFile(file.name) && isSupportedFile(file)) {
            collected.push({ kind: 'fallback', file });
          }
        } else {
          collected.push({ kind: 'entry', entry });
        }
      }

      const inputs: StagingFileInput[] = [];
      let hasDirectory = false;

      for (const item of collected) {
        if (item.kind === 'fallback') {
          inputs.push({ file: item.file });
          continue;
        }

        const { entry } = item;
        if (entry.isDirectory) {
          hasDirectory = true;
          const dirEntries = await readDirectoryRecursive(
            entry as FileSystemDirectoryEntry,
            entry.name // root name is the prefix — e.g. "BusinessAnalyst"
          );
          for (const { file, relativePath } of dirEntries) {
            const hints = parseRelativePath(relativePath, profiles);
            inputs.push({
              file,
              profile: hints.profile ?? defaultProfile,
              seniority: hints.seniority ?? (hints.profile || defaultProfile ? defaultSeniority : undefined),
              pathWarning: hints.pathWarning,
            });
          }
        } else {
          // Individual file dragged directly — no folder context, no hints
          const fileEntry = entry as FileSystemFileEntry;
          const file = await new Promise<File>((resolve, reject) =>
            fileEntry.file(resolve, reject)
          );
          if (!isHiddenFile(file.name) && isSupportedFile(file)) {
            inputs.push({ file, profile: defaultProfile, seniority: defaultProfile ? defaultSeniority : undefined });
          }
        }
      }

      const supportedCount = inputs.length;
      if (hasDirectory && supportedCount === 0) {
        setEmptyFolderMsg(true);
        setTimeout(() => setEmptyFolderMsg(false), 5000);
        return;
      }

      if (supportedCount > 0) {
        setEmptyFolderMsg(false);
        onFilesAdded(inputs);
      }
    },
    [defaultProfile, defaultSeniority, disabled, profiles, onFilesAdded]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = Array.from(e.target.files ?? [])
        .filter((f) => isSupportedFile(f));
      if (selected.length > 0) {
        onFilesAdded(selected.map((file) => ({
          file,
          profile: defaultProfile,
          seniority: defaultProfile ? defaultSeniority : undefined,
        })));
      }
      e.target.value = '';
    },
    [defaultProfile, defaultSeniority, onFilesAdded]
  );

  const handleClick = useCallback(() => {
    if (!disabled) fileInputRef.current?.click();
  }, [disabled]);

  return (
    <>
      <div
        onClick={handleClick}
        onDragEnter={(e) => handleDragState(e, true)}
        onDragLeave={(e) => handleDragState(e, false)}
        onDragOver={(e) => handleDragState(e, true)}
        onDrop={handleDrop}
        role="button"
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => {
          if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            handleClick();
          }
        }}
        className={[
          'group relative flex min-h-[200px] items-center justify-center overflow-hidden',
          'rounded-xl border-2 border-dashed px-6 py-10 transition-colors duration-150',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2f66ed] focus-visible:ring-offset-2',
          isDragActive
            ? 'border-[#2f66ed] bg-blue-50/60'
            : 'border-[#d8e0ea] bg-slate-50/60 hover:border-[#2f66ed]/40 hover:bg-blue-50/30',
          disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-[#2f66ed]">
            <Upload className="h-6 w-6" />
          </span>

          <div className="space-y-1">
            <p className="text-sm font-semibold text-slate-900">
              Déposez vos CVs ici ou cliquez pour sélectionner
            </p>
            <p className="text-sm text-slate-500">PDF, DOC, DOCX — fichiers ou dossiers</p>
            <p className="text-xs text-slate-400">
              Astuce : déposez un dossier <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[11px] text-slate-500">Profil/Niveau/</code> pour un classement automatique
            </p>
            {(defaultProfile || defaultSeniority) && (
              <p className="text-xs text-slate-500">
                Routage manuel actif : {defaultProfile ? profileLabelFr(defaultProfile) : 'profil auto'}
                {defaultSeniority ? ` / ${seniorityLabelFr(defaultSeniority)}` : ' / niveau auto'}
              </p>
            )}
          </div>

          {emptyFolderMsg && (
            <motion.div
              role="alert"
              initial={reducedMotion ? false : { opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex max-w-[320px] items-start gap-2 text-sm text-amber-700"
            >
              <span>Aucun fichier compatible trouvé dans ce dossier (.pdf, .docx, .doc uniquement)</span>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setEmptyFolderMsg(false); }}
                aria-label="Fermer ce message"
                className="flex-shrink-0 rounded-full p-0.5 text-amber-500 hover:bg-amber-100 hover:text-amber-700"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          )}
        </div>
      </div>

      {/* Hidden file input — triggered by clicking the drop zone */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.doc"
        multiple
        className="hidden"
        onChange={handleFileInput}
      />
    </>
  );
}
