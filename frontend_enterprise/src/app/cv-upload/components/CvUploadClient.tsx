'use client';

import React from 'react';
import { motion } from 'motion/react';
import { AlertTriangle, CheckCircle2, Cloud, FileUp, Link, Loader2, RefreshCw, Trash2, Upload, XCircle } from 'lucide-react';
import { useStagingUpload } from '@/hooks/useStagingUpload';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';
import { DarkSelect } from '@/components/DarkSelect';
import { friendlyHttpError, profileLabelFr } from '@/lib/uploadLabels';
import { StagingDropZone } from './StagingDropZone';
import { FileStatusList } from './FileStatusList';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const AUTO = '__auto__';
const SENIORITY_OPTIONS = [
  { value: AUTO, label: 'Niveau auto' },
  { value: 'junior', label: 'Junior' },
  { value: 'confirme', label: 'Confirmé' },
  { value: 'senior', label: 'Senior' },
  { value: 'expert', label: 'Expert' },
];
const FALLBACK_PROFILES = [
  'Backend',
  'BusinessAnalyst',
  'Cloud',
  'Cybersecurity',
  'Data',
  'DevOps',
  'ERP',
  'Frontend',
  'FullStack',
  'HR',
  'Mobile',
  'Project_Manager',
  'Testeur',
];

export function CvUploadClient() {
  const [driveUrl, setDriveUrl] = React.useState('');
  const [driveProfile, setDriveProfile] = React.useState('');
  const [driveSeniority, setDriveSeniority] = React.useState('');
  const [driveImporting, setDriveImporting] = React.useState(false);
  const [driveMessage, setDriveMessage] = React.useState('');
  const [driveError, setDriveError] = React.useState('');
  const [manualProfile, setManualProfile] = React.useState('');
  const [manualSeniority, setManualSeniority] = React.useState('');

  const {
    profiles,
    files,
    uploading,
    uploadedCount,
    errorCount,
    done,
    addFiles,
    updateFileRouting,
    removeFile,
    clearFiles,
    uploadAll,
    retryFile,
    retryAllErrors,
    canUpload,
  } = useStagingUpload();
  const reducedMotion = usePrefersReducedMotion();

  const pendingCount = files.filter((f) => f.status === 'pending').length;
  const totalCount = files.length;
  const availableProfiles = profiles.length > 0 ? profiles : FALLBACK_PROFILES;
  const unclassifiedCount = files.filter((f) => f.status === 'pending' &&
    (!f.profile || !profiles.includes(f.profile) || !f.seniority)).length;

  async function importFromDrive() {
    const url = driveUrl.trim();
    if (!url || driveImporting) return;

    setDriveImporting(true);
    setDriveMessage('');
    setDriveError('');

    const payload: Record<string, unknown> = { max_files: 50 };
    if (url.includes('/folders/')) {
      payload.folder_url = url;
    } else {
      payload.file_urls = [url];
    }
    if (driveProfile) payload.profile = driveProfile;
    if (driveSeniority) payload.seniority = driveSeniority;

    try {
      const res = await fetch(`${API_BASE}/staging/google-drive/import`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail ?? friendlyHttpError(res.status));
      const importedCount = data.imported_count ?? 0;
      const failedCount = data.failed_count ?? 0;
      if (importedCount > 0) {
        setDriveMessage(`${importedCount} CV importé${importedCount > 1 ? 's' : ''}`);
      }
      if (failedCount > 0) {
        setDriveError(`${failedCount} fichier${failedCount > 1 ? 's' : ''} non importé${failedCount > 1 ? 's' : ''}`);
      }
      if (importedCount === 0 && failedCount === 0) {
        setDriveError("Aucun CV compatible trouvé à cette adresse.");
      }
      setDriveUrl('');
    } catch (err) {
      setDriveError(
        err instanceof Error ? err.message : 'Connexion au serveur impossible. Vérifiez votre réseau et réessayez.'
      );
    } finally {
      setDriveImporting(false);
    }
  }

  const profileOptions = [
    { value: AUTO, label: 'Profil auto' },
    ...availableProfiles.map((profile) => ({ value: profile, label: profileLabelFr(profile) })),
  ];
  // Manual choices must come from the live catalog, not the legacy fallback list.
  const manualProfileOptions = [
    { value: AUTO, label: 'Aucun profil par défaut' },
    ...profiles.map((profile) => ({ value: profile, label: profileLabelFr(profile) })),
  ];

  return (
    <div className="w-full max-w-7xl space-y-6">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="border-b border-[#d8e0ea] pb-6">
        <h1 className="text-3xl font-bold text-slate-950">Alimentation du vivier CV</h1>
        <p className="mt-1 max-w-2xl text-slate-600">
          Importez depuis Google Drive ou ajoutez des CVs manuellement. Le profil et le niveau
          sont à renseigner pour chaque dépôt manuel. L'import Drive conserve ses options automatiques.
        </p>
      </div>

      {/* ── Google Drive import ───────────────────────────────────────────── */}
      <div className="rounded-xl border border-[#d8e0ea] bg-white p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-blue-50 text-[#2f66ed]">
            <Cloud className="h-4 w-4" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Google Drive</h2>
            <p className="text-xs text-slate-500">Lien fichier ou dossier — 50 CVs maximum depuis l'interface</p>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[1fr_180px_150px_auto]">
          <label className="relative block">
            <span className="sr-only">Lien fichier ou dossier Google Drive</span>
            <Link className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={driveUrl}
              onChange={(e) => setDriveUrl(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') importFromDrive(); }}
              disabled={driveImporting || uploading}
              placeholder="Lien fichier ou dossier Drive"
              className="h-11 w-full rounded-xl border border-[#d8e0ea] bg-white pl-10 pr-3 text-sm text-slate-950 placeholder:text-slate-400 shadow-sm outline-none transition focus:border-[#2f66ed]/50 focus:ring-2 focus:ring-[#2f66ed]/10 disabled:opacity-60"
            />
          </label>

          <DarkSelect
            value={driveProfile || AUTO}
            onChange={(v) => {
              const next = v === AUTO ? '' : v;
              setDriveProfile(next);
              if (!next) setDriveSeniority('');
            }}
            options={profileOptions}
            disabled={driveImporting || uploading}
            ariaLabel="Profil pour l'import Google Drive"
          />

          <DarkSelect
            value={driveSeniority || AUTO}
            onChange={(v) => setDriveSeniority(v === AUTO ? '' : v)}
            options={SENIORITY_OPTIONS}
            disabled={driveImporting || uploading || !driveProfile}
            ariaLabel="Niveau pour l'import Google Drive"
          />

          <button
            type="button"
            onClick={importFromDrive}
            disabled={!driveUrl.trim() || driveImporting || uploading}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#2f66ed] px-4 text-sm font-semibold text-white shadow-[0_4px_16px_rgba(47,102,237,0.22)] transition hover:bg-[#2558d7] disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none"
          >
            {driveImporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Cloud className="h-4 w-4" />}
            Importer
          </button>
        </div>

        {(driveMessage || driveError) && (
          <div className="space-y-2">
            {driveMessage && (
              <p role="status" className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                {driveMessage}
              </p>
            )}
            {driveError && (
              <p role="alert" className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                {driveError}
              </p>
            )}
          </div>
        )}
      </div>

      {/* ── Manual upload ────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-[#d8e0ea] bg-white p-6 shadow-sm space-y-4">
        <div className="flex items-start justify-between gap-4 max-lg:flex-col">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-blue-50 text-[#2f66ed]">
              <FileUp className="h-4 w-4" />
            </span>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Dépôt manuel</h2>
              <p className="text-xs text-slate-500">Valeurs par défaut pour les nouveaux CVs ; vous pouvez modifier chaque CV dans la file d'envoi.</p>
            </div>
          </div>

          <div className="grid w-full gap-3 sm:grid-cols-2 lg:w-[360px]">
            <DarkSelect
              value={manualProfile || AUTO}
              onChange={(v) => {
                const next = v === AUTO ? '' : v;
                setManualProfile(next);
                if (!next) setManualSeniority('');
              }}
              options={manualProfileOptions}
              disabled={uploading || profiles.length === 0}
              ariaLabel="Profil par défaut du dépôt manuel"
            />

            <DarkSelect
              value={manualSeniority || AUTO}
              onChange={(v) => setManualSeniority(v === AUTO ? '' : v)}
              options={SENIORITY_OPTIONS}
              disabled={uploading || !manualProfile}
              ariaLabel="Niveau par défaut du dépôt manuel"
            />
            {!manualProfile && (
              <p className="col-span-2 -mt-1 text-xs text-slate-400">Choisissez d'abord un profil pour activer le niveau.</p>
            )}
          </div>
        </div>

        <StagingDropZone
          onFilesAdded={addFiles}
          profiles={profiles}
          defaultProfile={manualProfile || undefined}
          defaultSeniority={manualSeniority || undefined}
          disabled={uploading}
        />
        {profiles.length === 0 && (
          <p role="status" className="text-xs text-amber-700">Catalogue des profils indisponible : envoi manuel bloqué jusqu'à son chargement.</p>
        )}
      </div>

      {/* ── Queue + send — one card, so the list and the action that sends it are
           visibly one unit rather than split across containers ─────────────── */}
      {totalCount > 0 && (
        <div className="rounded-xl border border-[#d8e0ea] bg-white p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-slate-900">File d'envoi</h2>
            {!uploading && (
              <button
                type="button"
                onClick={clearFiles}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-red-600"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Vider la liste
              </button>
            )}
          </div>

          <FileStatusList
            files={files}
            onRemove={removeFile}
            onRetry={retryFile}
            onUpdateRouting={updateFileRouting}
            profiles={profiles}
            disabled={uploading}
          />

          {unclassifiedCount > 0 && (
            <p role="status" className="text-xs text-amber-700">Complétez le profil et la séniorité de {unclassifiedCount} CV avant l'envoi.</p>
          )}

          {/* Progress bar — blue segment is actual successes, red is actual
              failures, so a fully-failed batch cannot render as a full "done" bar. */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-slate-500">
              <span>{uploadedCount} / {totalCount} envoyé{uploadedCount > 1 ? 's' : ''}</span>
              {errorCount > 0 && (
                <span className="text-red-600">{errorCount} erreur{errorCount > 1 ? 's' : ''}</span>
              )}
            </div>
            <div
              role="progressbar"
              aria-label="Progression de l'envoi"
              aria-valuemin={0}
              aria-valuemax={totalCount}
              aria-valuenow={uploadedCount + errorCount}
              className="flex h-1.5 overflow-hidden rounded-full bg-slate-100"
            >
              <motion.div
                className="h-full bg-[#2f66ed]"
                initial={{ width: 0 }}
                animate={{ width: `${(uploadedCount / totalCount) * 100}%` }}
                transition={{ ease: 'easeOut', duration: 0.3 }}
              />
              <motion.div
                className="h-full bg-red-500"
                initial={{ width: 0 }}
                animate={{ width: `${(errorCount / totalCount) * 100}%` }}
                transition={{ ease: 'easeOut', duration: 0.3 }}
              />
            </div>
          </div>

          {/* Completion summary — styling and message reflect the real outcome,
              never a blanket "success" regardless of how many files failed. */}
          {done && (
            <motion.div
              role="status"
              initial={reducedMotion ? false : { opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              className={
                errorCount === 0
                  ? 'flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4'
                  : uploadedCount === 0
                  ? 'flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-5 py-4'
                  : 'flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-5 py-4'
              }
            >
              {errorCount === 0 ? (
                <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-600" />
              ) : uploadedCount === 0 ? (
                <XCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
              ) : (
                <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" />
              )}
              <p className={
                errorCount === 0 ? 'text-sm text-emerald-800'
                : uploadedCount === 0 ? 'text-sm text-red-800'
                : 'text-sm text-amber-800'
              }>
                {uploadedCount === 0
                  ? `Aucun CV n'a été envoyé (${errorCount} erreur${errorCount > 1 ? 's' : ''}). Vérifiez les fichiers en erreur ci-dessus et réessayez.`
                  : errorCount === 0
                  ? `${uploadedCount} CV${uploadedCount > 1 ? 's' : ''} envoyé${uploadedCount > 1 ? 's' : ''} avec succès. Ils seront extraits en conservant les profils et séniorités sélectionnés lorsque le traitement est actif.`
                  : `${uploadedCount} CV${uploadedCount > 1 ? 's' : ''} envoyé${uploadedCount > 1 ? 's' : ''}, ${errorCount} erreur${errorCount > 1 ? 's' : ''} à corriger ci-dessus.`}
              </p>
            </motion.div>
          )}

          <div className="flex flex-col-reverse gap-3 sm:flex-row">
            {errorCount > 0 && !uploading && (
              <button
                type="button"
                onClick={retryAllErrors}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-[#d8e0ea] bg-white px-6 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-red-300 hover:text-red-600"
              >
                <RefreshCw className="h-4 w-4" />
                Réessayer les {errorCount} en erreur
              </button>
            )}

            <button
              type="button"
              onClick={uploadAll}
              disabled={!canUpload}
              className="flex h-12 flex-1 items-center justify-center gap-2 rounded-xl bg-[#2f66ed] px-8 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(47,102,237,0.18)] transition hover:bg-[#2558d7] disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none"
            >
              {uploading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Envoi en cours…
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" />
                  {pendingCount > 0
                    ? `Envoyer ${pendingCount} CV${pendingCount > 1 ? 's' : ''}`
                    : 'Envoyer les CVs'}
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
