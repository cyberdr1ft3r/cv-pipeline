'use client';

import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle } from 'lucide-react';

export interface UnreliabilityFlagInfo {
  id?: string;
  reason: string;
  flagged_by_name?: string | null;
  offer_title?: string | null;
  created_at?: string | null;
}

function formatFlagDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

interface Props {
  flag: UnreliabilityFlagInfo | null | undefined;
  candidateId: string;
  canResolve?: boolean;
  onResolved?: () => void;
  apiBase?: string;
}

export function UnreliabilityFlagIndicator({
  flag,
  candidateId,
  canResolve = false,
  onResolved,
  apiBase = process.env.NEXT_PUBLIC_API_URL || '/api/v1',
}: Props) {
  const [open, setOpen] = useState(false);
  const [resolveReason, setResolveReason] = useState('');
  const [resolving, setResolving] = useState(false);
  const popupRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  if (!flag?.reason) return null;

  async function handleResolve() {
    if (!flag?.id || !resolveReason.trim()) return;
    setResolving(true);
    try {
      const res = await fetch(
        `${apiBase}/candidates/${candidateId}/unreliability-flag/${flag.id}/resolve`,
        {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ resolved_reason: resolveReason.trim() }),
        },
      );
      if (res.ok) {
        setOpen(false);
        setResolveReason('');
        onResolved?.();
      }
    } finally {
      setResolving(false);
    }
  }

  return (
    <span className="relative inline-flex" ref={popupRef}>
      <button
        type="button"
        onClick={e => { e.stopPropagation(); setOpen(v => !v); }}
        title="Signalé comme non fiable"
        className="text-red-400 hover:text-red-300 transition-colors flex-shrink-0"
        aria-label="Signalé comme non fiable"
      >
        <AlertTriangle className="h-4 w-4" />
      </button>
      {open && (
        <div
          className="absolute left-0 top-full z-50 mt-1 w-72 rounded-xl border border-red-500/30 bg-[#1a1f2e] p-4 shadow-xl text-left"
          onClick={e => e.stopPropagation()}
        >
          <p className="text-sm font-semibold text-red-300 mb-2">⚠️ Candidat signalé</p>
          <div className="space-y-1.5 text-xs text-slate-300">
            <p><span className="text-slate-500">Raison :</span> {flag.reason}</p>
            {flag.flagged_by_name && (
              <p><span className="text-slate-500">Signalé par :</span> {flag.flagged_by_name}</p>
            )}
            {flag.offer_title && (
              <p><span className="text-slate-500">Offre concernée :</span> {flag.offer_title}</p>
            )}
            <p><span className="text-slate-500">Date :</span> {formatFlagDate(flag.created_at)}</p>
          </div>
          {canResolve && flag.id && (
            <div className="mt-3 space-y-2 border-t border-white/10 pt-3">
              <textarea
                value={resolveReason}
                onChange={e => setResolveReason(e.target.value)}
                placeholder="Raison de résolution…"
                rows={2}
                className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1.5 text-xs text-white placeholder:text-slate-500 focus:border-[#1f9d94]/50 focus:outline-none resize-none"
              />
              <button
                type="button"
                onClick={handleResolve}
                disabled={!resolveReason.trim() || resolving}
                className="w-full px-3 py-1.5 rounded-lg bg-[#1f9d94] hover:bg-[#25afa5] text-white text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {resolving ? 'Résolution…' : 'Résoudre ce signalement'}
              </button>
            </div>
          )}
        </div>
      )}
    </span>
  );
}

interface ActiveFlagSectionProps {
  flag: UnreliabilityFlagInfo;
  candidateId: string;
  canResolve?: boolean;
  onResolved?: () => void;
  apiBase?: string;
}

export function ActiveUnreliabilitySection({
  flag,
  candidateId,
  canResolve = true,
  onResolved,
  apiBase,
}: ActiveFlagSectionProps) {
  const [resolveReason, setResolveReason] = useState('');
  const [resolving, setResolving] = useState(false);
  const base = apiBase || process.env.NEXT_PUBLIC_API_URL || '/api/v1';

  async function handleResolve() {
    if (!flag.id || !resolveReason.trim()) return;
    setResolving(true);
    try {
      const res = await fetch(
        `${base}/candidates/${candidateId}/unreliability-flag/${flag.id}/resolve`,
        {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ resolved_reason: resolveReason.trim() }),
        },
      );
      if (res.ok) onResolved?.();
    } finally {
      setResolving(false);
    }
  }

  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 space-y-3">
      <p className="text-sm font-semibold text-red-300">⚠️ Signalement actif</p>
      <p className="text-sm text-slate-300">{flag.reason}</p>
      <p className="text-xs text-slate-500">
        Signalé par {flag.flagged_by_name || '—'} le {formatFlagDate(flag.created_at)}
      </p>
      {flag.offer_title && (
        <p className="text-xs text-slate-500">Offre : {flag.offer_title}</p>
      )}
      {canResolve && flag.id && (
        <div className="space-y-2 pt-1">
          <textarea
            value={resolveReason}
            onChange={e => setResolveReason(e.target.value)}
            placeholder="Raison de résolution…"
            rows={2}
            className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-[#1f9d94]/50 focus:outline-none resize-none"
          />
          <button
            type="button"
            onClick={handleResolve}
            disabled={!resolveReason.trim() || resolving}
            className="px-4 py-2 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {resolving ? 'Résolution…' : 'Résoudre'}
          </button>
        </div>
      )}
    </div>
  );
}

