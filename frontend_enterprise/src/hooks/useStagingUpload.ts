'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { friendlyHttpError } from '@/lib/uploadLabels';

// Match usePipeline.ts pattern exactly: base already includes /api/v1
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const NETWORK_ERROR_MESSAGE = 'Connexion au serveur impossible. Vérifiez votre réseau et réessayez.';

export type FileStatus = 'pending' | 'uploading' | 'uploaded' | 'error';

/** Input shape from the drop zone — carries optional routing hints from folder path. */
export interface StagingFileInput {
  file: File;
  profile?: string;      // extracted from dropped folder name, validated against CANONICAL_PROFILES
  seniority?: string;    // extracted from folder path, lowercase ("junior" | "confirme" | ...)
  pathWarning?: string;  // set when a folder was dropped but no profile could be parsed
}

export interface StagingFile {
  id: string;
  file: File;
  status: FileStatus;
  error?: string;
  stagingPath?: string;
  profile?: string;
  seniority?: string;
  pathWarning?: string;
}

interface StagingUploadState {
  profiles: string[];
  files: StagingFile[];
  uploading: boolean;
  uploadedCount: number;
  errorCount: number;
  done: boolean;
  addFiles: (incoming: StagingFileInput[]) => void;
  removeFile: (id: string) => void;
  clearFiles: () => void;
  uploadAll: () => Promise<void>;
  retryFile: (id: string) => Promise<void>;
  retryAllErrors: () => Promise<void>;
  canUpload: boolean;
}

function uid(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function dedupKey(f: StagingFileInput): string {
  return `${f.profile ?? ''}\0${f.seniority ?? ''}\0${f.file.name}`;
}

export function useStagingUpload(): StagingUploadState {
  const [profiles, setProfiles] = useState<string[]>([]);
  const [files, setFiles] = useState<StagingFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [done, setDone] = useState(false);

  // Derived from `files`, not separately tracked — a manually-incremented counter
  // drifts across batches (e.g. after a `clearFiles` or a second drop) since it has
  // no single source of truth. `files` already is that source of truth.
  const uploadedCount = useMemo(() => files.filter((f) => f.status === 'uploaded').length, [files]);
  const errorCount = useMemo(() => files.filter((f) => f.status === 'error').length, [files]);

  // Fetch canonical profiles on mount — needed by StagingDropZone for path validation
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/staging/profiles`, { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => { if (!cancelled) setProfiles(data.profiles ?? []); })
      .catch(() => {}); // non-fatal — path validation degrades gracefully
    return () => { cancelled = true; };
  }, []);

  const addFiles = useCallback((incoming: StagingFileInput[]) => {
    setFiles((prev) => {
      const existingKeys = new Set(prev.map((f) => dedupKey(f)));
      const deduped = incoming.filter((f) => !existingKeys.has(dedupKey(f)));
      const newEntries: StagingFile[] = deduped.map((f) => ({
        id: uid(),
        file: f.file,
        status: 'pending',
        profile: f.profile,
        seniority: f.seniority,
        pathWarning: f.pathWarning,
      }));
      return [...prev, ...newEntries];
    });
    setDone(false);
  }, []);

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const clearFiles = useCallback(() => {
    setFiles([]);
    setDone(false);
  }, []);

  const uploadOne = useCallback(async (entry: StagingFile): Promise<void> => {
    setFiles((prev) =>
      prev.map((f) => (f.id === entry.id ? { ...f, status: 'uploading' } : f))
    );

    const formData = new FormData();
    formData.append('file', entry.file);
    if (entry.profile) formData.append('profile', entry.profile);
    if (entry.seniority) formData.append('seniority', entry.seniority);

    try {
      const res = await fetch(`${API_BASE}/staging/upload`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail: string = body.detail ?? friendlyHttpError(res.status);
        setFiles((prev) =>
          prev.map((f) =>
            f.id === entry.id ? { ...f, status: 'error', error: detail } : f
          )
        );
        return;
      }

      const data = await res.json();
      setFiles((prev) =>
        prev.map((f) =>
          f.id === entry.id
            ? { ...f, status: 'uploaded', stagingPath: data.staging_path }
            : f
        )
      );
    } catch {
      // A thrown fetch (not an HTTP error response) is always a connectivity
      // problem — report that plainly instead of a raw browser message like
      // "Failed to fetch".
      setFiles((prev) =>
        prev.map((f) =>
          f.id === entry.id ? { ...f, status: 'error', error: NETWORK_ERROR_MESSAGE } : f
        )
      );
    }
  }, []);

  // Concurrency-limited upload: max 3 simultaneous workers sharing a queue
  const uploadAll = useCallback(async () => {
    const pending = files.filter((f) => f.status === 'pending');
    if (pending.length === 0) return;

    setUploading(true);
    setDone(false);

    const queue = [...pending];
    const MAX_CONCURRENT = 3;

    const worker = async () => {
      while (queue.length > 0) {
        const entry = queue.shift();
        if (entry) await uploadOne(entry);
      }
    };

    await Promise.all(
      Array.from({ length: Math.min(MAX_CONCURRENT, pending.length) }, worker)
    );

    setUploading(false);
    setDone(true);
  }, [files, uploadOne]);

  // Core retry step, no `uploading` bookkeeping of its own — both single-file
  // and bulk retry wrap this with their own start/stop so a bulk retry doesn't
  // flip `uploading` false between files and let a concurrent send slip in.
  const retryOne = useCallback(
    async (id: string) => {
      const entry = files.find((f) => f.id === id);
      if (!entry) return;
      setFiles((prev) =>
        prev.map((f) => (f.id === id ? { ...f, status: 'pending', error: undefined } : f))
      );
      await uploadOne({ ...entry, status: 'pending', error: undefined });
    },
    [files, uploadOne]
  );

  const retryFile = useCallback(
    async (id: string) => {
      setUploading(true);
      try {
        await retryOne(id);
      } finally {
        setUploading(false);
      }
    },
    [retryOne]
  );

  /** Retry every currently-errored file, one at a time. */
  const retryAllErrors = useCallback(async () => {
    const failedIds = files.filter((f) => f.status === 'error').map((f) => f.id);
    if (failedIds.length === 0) return;
    setUploading(true);
    try {
      for (const id of failedIds) {
        await retryOne(id);
      }
    } finally {
      setUploading(false);
    }
  }, [files, retryOne]);

  const canUpload = files.some((f) => f.status === 'pending') && !uploading;

  return {
    profiles,
    files,
    uploading,
    uploadedCount,
    errorCount,
    done,
    addFiles,
    removeFile,
    clearFiles,
    uploadAll,
    retryFile,
    retryAllErrors,
    canUpload,
  };
}

