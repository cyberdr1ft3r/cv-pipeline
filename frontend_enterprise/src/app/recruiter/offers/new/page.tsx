'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  Brain,
  CheckCircle2,
  FileText,
  Loader2,
  Upload,
  X,
} from 'lucide-react';
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

const ACCEPTED_EXTS = [
  '.txt', '.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.xlsx', '.xls', '.xlsm',
];
const ACCEPTED_MIME = ACCEPTED_EXTS.join(',');
const FORMAT_HINT =
  'TXT, PDF, Word (DOC, DOCX), Images (JPG, PNG), Excel (XLSX, XLS, XLSM)';

interface Sourcer {
  id: string;
  full_name: string;
  email: string;
  active_offers_count: number;
}

interface ContractType {
  id: number;
  code: string;
  label_fr: string;
}

function isValidExt(filename: string): boolean {
  const ext = '.' + filename.split('.').pop()?.toLowerCase();
  return ACCEPTED_EXTS.includes(ext);
}

export default function NewOfferPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [sourcers, setSourcers] = useState<Sourcer[]>([]);
  const [contractTypes, setContractTypes] = useState<ContractType[]>([]);
  const [selectedContractTypeId, setSelectedContractTypeId] = useState('1');
  const [previewing, setPreviewing] = useState(false);
  const [selectedSourcerId, setSelectedSourcerId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/users/sourcers`, { credentials: 'include' })
        .then(r => r.ok ? r.json() : Promise.reject()),
      fetch(`${API_BASE}/ref/contract-types`, { credentials: 'include' })
        .then(r => r.ok ? r.json() : Promise.reject()),
    ])
      .then(([sourcersData, refData]) => {
        setSourcers(sourcersData.sourcers || []);
        setContractTypes(refData.contract_types || []);
      })
      .catch(() => null);
  }, []);

  async function previewMetadata(f: File) {
    setPreviewing(true);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await fetch(`${API_BASE}/offers/preview-metadata`, {
        method: 'POST',
        credentials: 'include',
        body: fd,
      });
      if (res.ok) {
        const data = await res.json();
        if (data.contract_type?.id) {
          setSelectedContractTypeId(String(data.contract_type.id));
        }
      }
    } catch {
      // Preview is best-effort — recruiter can still submit with default CDI
    } finally {
      setPreviewing(false);
    }
  }

  function acceptFile(f: File) {
    if (!isValidExt(f.name)) {
      setError(`Format non supporté : .${f.name.split('.').pop()}. Acceptés : ${ACCEPTED_EXTS.join(', ')}`);
      return;
    }
    setError('');
    setFile(f);
    void previewMetadata(f);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) acceptFile(f);
  }

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) acceptFile(f);
    e.target.value = '';
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError('');
    setSubmitting(true);

    try {
      const fd = new FormData();
      fd.append('file', file);
      if (selectedSourcerId) fd.append('sourcer_id', selectedSourcerId);
      if (selectedContractTypeId) fd.append('contract_type_id', selectedContractTypeId);

      const res = await fetch(`${API_BASE}/offers`, {
        method: 'POST',
        credentials: 'include',
        body: fd,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Erreur ${res.status}`);
      }

      setSuccess(true);
      setTimeout(() => router.push('/recruiter/offers'), 1200);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="mb-8 border-b border-[#d8e0ea] pb-6">
        <h1 className="text-3xl font-bold text-slate-950">Nouvelle Offre</h1>
        <p className="mt-1 text-slate-600">Créez une nouvelle offre de poste</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">

        {/* Drop zone */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
            Fichier de poste <span className="text-red-600">*</span>
          </label>

          <motion.div
            whileHover={!file && !submitting ? { y: -2 } : {}}
            onClick={() => !submitting && fileInputRef.current?.click()}
            onDragEnter={e => { e.preventDefault(); if (!submitting) setIsDragging(true); }}
            onDragLeave={e => { e.preventDefault(); setIsDragging(false); }}
            onDragOver={e => { e.preventDefault(); if (!submitting) setIsDragging(true); }}
            onDrop={!submitting ? handleDrop : undefined}
            className={[
              'relative flex min-h-[160px] items-center justify-center rounded-2xl border border-dashed px-6 py-8 transition-all duration-200',
              isDragging
                ? 'border-[#2f66ed]/70 bg-blue-50'
                : file
                  ? 'border-emerald-300 bg-emerald-50 cursor-default'
                  : 'border-[#d8e0ea] bg-white hover:border-[#2f66ed]/50 hover:bg-blue-50/40 cursor-pointer',
              submitting ? 'opacity-60 cursor-not-allowed' : '',
            ].join(' ')}
          >
            {file ? (
              <div className="flex items-center gap-4 w-full">
                <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center flex-shrink-0">
                  <FileText className="h-6 w-6 text-emerald-700" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-slate-950 font-medium truncate">{file.name}</p>
                  <p className="text-slate-600 text-xs mt-0.5">{(file.size / 1024).toFixed(0)} Ko</p>
                </div>
                {!submitting && (
                  <button
                    type="button"
                    onClick={e => { e.stopPropagation(); setFile(null); setError(''); }}
                    className="text-slate-500 hover:text-slate-900 transition-colors flex-shrink-0"
                  >
                    <X className="h-5 w-5" />
                  </button>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 text-center">
                <div className="w-12 h-12 rounded-xl border border-[#d8e0ea] bg-slate-50 flex items-center justify-center">
                  <Upload className="h-6 w-6 text-slate-600" />
                </div>
                <div>
                  <p className="text-slate-950 font-medium">Déposez votre fiche de poste ici</p>
                  <p className="text-slate-600 text-sm mt-0.5">{FORMAT_HINT}</p>
                </div>
                <span className="text-xs text-[#2f66ed] font-medium border border-[#2f66ed]/20 px-3 py-1 rounded-full bg-blue-50">
                  Parcourir
                </span>
              </div>
            )}
          </motion.div>

          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_MIME}
            className="hidden"
            onChange={handleFileInput}
          />
        </div>

        {/* Contract type */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
            Type de contrat
          </label>
          <select
            value={selectedContractTypeId}
            onChange={e => setSelectedContractTypeId(e.target.value)}
            disabled={submitting}
            className="w-full rounded-lg border border-[#d8e0ea] bg-white px-4 py-3 text-sm text-slate-950 shadow-sm transition-all focus:border-[#2f66ed]/60 focus:outline-none focus:ring-2 focus:ring-[#2f66ed]/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {contractTypes.length === 0 && <option value="1">CDI</option>}
            {contractTypes.map(ct => (
              <option key={ct.id} value={String(ct.id)}>{ct.label_fr || ct.code}</option>
            ))}
          </select>
          <p className="text-xs text-slate-600">
            {previewing
              ? 'Analyse du fichier en cours…'
              : file
                ? 'Détecté automatiquement — vous pouvez modifier'
                : 'Par défaut : CDI'}
          </p>
        </div>

        {/* Sourcer card picker */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
            Assigner à un sourcer{' '}
            <span className="normal-case font-normal text-slate-600">(optionnel)</span>
          </label>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {/* "Aucun" option */}
            <button
              type="button"
              disabled={submitting}
              onClick={() => setSelectedSourcerId('')}
              className={`flex flex-col items-center justify-center gap-1 p-3 rounded-xl border text-center transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed ${
                selectedSourcerId === ''
                  ? 'border-[#2f66ed]/40 bg-blue-50 text-[#2f66ed] shadow-sm'
                  : 'border-[#d8e0ea] bg-white text-slate-600 hover:border-[#2f66ed]/35 hover:bg-blue-50/40 hover:text-slate-950'
              }`}
            >
              <span className="text-xs font-medium leading-tight">Aucun</span>
              <span className={`text-[10px] leading-tight ${selectedSourcerId === '' ? 'text-blue-700' : 'text-slate-500'}`}>Sans assignation</span>
            </button>

            {/* Sourcer cards */}
            {sourcers.map(s => {
              const initials = s.full_name.split(' ').slice(0, 2).map((w: string) => w[0]?.toUpperCase() ?? '').join('');
              const selected = selectedSourcerId === s.id;
              return (
                <button
                  key={s.id}
                  type="button"
                  disabled={submitting}
                  onClick={() => setSelectedSourcerId(selected ? '' : s.id)}
                  className={`flex flex-col items-start gap-1.5 p-3 rounded-xl border text-left transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed ${
                    selected
                      ? 'border-[#2f66ed] bg-blue-50 text-slate-950 shadow-sm ring-2 ring-[#2f66ed]/10'
                      : 'border-[#d8e0ea] bg-white text-slate-700 hover:border-[#2f66ed]/35 hover:bg-blue-50/40 hover:text-slate-950'
                  }`}
                >
                  <div className="flex items-center gap-2 w-full min-w-0">
                    {/* Avatar */}
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] font-bold ${selected ? 'bg-[#2f66ed] text-white' : 'bg-slate-100 text-slate-600'}`}>
                      {initials}
                    </div>
                    <span className="text-xs font-medium truncate leading-tight">{s.full_name}</span>
                  </div>
                  {s.active_offers_count > 0 && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full leading-tight ${selected ? 'bg-white text-blue-700' : 'bg-slate-100 text-slate-600'}`}>
                      {s.active_offers_count} offre{s.active_offers_count > 1 ? 's' : ''} en cours
                    </span>
                  )}
                  {s.active_offers_count === 0 && (
                    <span className={`text-[10px] leading-tight ${selected ? 'text-blue-700' : 'text-slate-500'}`}>Disponible</span>
                  )}
                </button>
              );
            })}
          </div>

          {selectedSourcerId && (
            <p className="text-xs text-[#2f66ed]">
              L&apos;offre sera directement assignée et visible dans l&apos;espace sourcing.
            </p>
          )}
        </div>

        {/* Error */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-start gap-2 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
          >
            <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            {error}
          </motion.div>
        )}

        {/* Success */}
        {success && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700"
          >
            <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
            Offre créée avec succès ! Redirection…
          </motion.div>
        )}

        {/* Buttons */}
        <div className="flex gap-3 pt-1">
          <button
            type="button"
            onClick={() => router.push('/recruiter/offers')}
            disabled={submitting}
            className="flex-1 px-4 py-3 rounded-xl border border-[#d8e0ea] bg-white text-slate-700 text-sm hover:border-[#2f66ed]/35 hover:text-[#2f66ed] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Annuler
          </button>

          <motion.button
            type="submit"
            disabled={!file || submitting || success}
            whileHover={file && !submitting ? { y: -1 } : {}}
            whileTap={file && !submitting ? { scale: 0.98 } : {}}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-[#2f66ed] hover:bg-[#2458d8] text-white text-sm font-semibold transition-all disabled:opacity-45 disabled:cursor-not-allowed shadow-[0_10px_24px_rgba(47,102,237,0.18)]"
          >
            {submitting ? (
              <><Brain className="h-4 w-4 animate-pulse" />Extraction en cours…</>
            ) : (
              <>Créer l&apos;offre</>
            )}
          </motion.button>
        </div>

        {/* Info note */}
        <p className={`text-xs text-center flex items-center justify-center gap-1.5 transition-colors ${submitting ? 'text-[#2f66ed]' : 'text-slate-600'}`}>
          {submitting
            ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Le fichier est déposé, l&apos;IA analyse la fiche de poste…</>
            : <><Brain className="h-3.5 w-3.5" />Les informations seront extraites automatiquement par l&apos;IA (5–30 s)</>
          }
        </p>
      </form>
    </div>
  );
}

