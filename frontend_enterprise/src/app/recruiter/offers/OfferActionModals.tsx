'use client';

import React from 'react';
import { AlertTriangle, Archive, Loader2 } from 'lucide-react';

interface BaseProps {
  title: string;
  onCancel: () => void;
}

interface DeleteModalProps extends BaseProps {
  onConfirm: () => void;
  loading: boolean;
}

interface ArchiveModalProps extends BaseProps {
  onConfirm: () => void;
  loading: boolean;
}

export function DeleteOfferModal({ title, onCancel, onConfirm, loading }: DeleteModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative w-full max-w-md rounded-2xl border border-white/15 bg-[#0d1528] p-6 space-y-5 shadow-2xl">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-500/15 flex items-center justify-center">
            <AlertTriangle className="h-5 w-5 text-red-400" />
          </div>
          <div className="space-y-2 min-w-0">
            <h2 className="text-lg font-semibold text-white">Supprimer l&apos;offre</h2>
            <p className="text-sm text-slate-400 leading-relaxed">
              Êtes-vous sûr de vouloir supprimer l&apos;offre{' '}
              <span className="text-white font-medium">&ldquo;{title}&rdquo;</span> ? Cette action est irréversible.
              Tous les fichiers associés seront supprimés.
            </p>
          </div>
        </div>
        <div className="flex gap-3">
          <button onClick={onCancel} disabled={loading}
            className="flex-1 px-4 py-2.5 rounded-xl border border-white/10 text-slate-400 text-sm hover:text-white hover:border-white/20 transition-all disabled:opacity-50">
            Annuler
          </button>
          <button onClick={onConfirm} disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-sm font-medium transition-all disabled:opacity-50">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Supprimer définitivement'}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ArchiveOfferModal({ title, onCancel, onConfirm, loading }: ArchiveModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative w-full max-w-md rounded-2xl border border-white/15 bg-[#0d1528] p-6 space-y-5 shadow-2xl">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-[#1f9d94]/15 flex items-center justify-center">
            <Archive className="h-5 w-5 text-[#1f9d94]" />
          </div>
          <div className="space-y-2 min-w-0">
            <h2 className="text-lg font-semibold text-white">Archiver l&apos;offre</h2>
            <p className="text-sm text-slate-400 leading-relaxed">
              Archiver l&apos;offre{' '}
              <span className="text-white font-medium">&ldquo;{title}&rdquo;</span> ?
              Les fichiers seront conservés mais l&apos;offre ne sera plus active.
            </p>
          </div>
        </div>
        <div className="flex gap-3">
          <button onClick={onCancel} disabled={loading}
            className="flex-1 px-4 py-2.5 rounded-xl border border-white/10 text-slate-400 text-sm hover:text-white hover:border-white/20 transition-all disabled:opacity-50">
            Annuler
          </button>
          <button onClick={onConfirm} disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium transition-all disabled:opacity-50">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Archiver'}
          </button>
        </div>
      </div>
    </div>
  );
}
