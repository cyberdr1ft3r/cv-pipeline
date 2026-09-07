'use client';

import React from 'react';
import { cvLimitFieldError } from '@/lib/cvLimit';

interface CvLimitFieldProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  id?: string;
  className?: string;
}

/** Optional cap on how many CVs the matcher scores (empty = no limit). */
export function CvLimitField({ value, onChange, disabled, id = 'cv-limit', className = '' }: CvLimitFieldProps) {
  const error = cvLimitFieldError(value);

  return (
    <div className={`space-y-1 ${className}`}>
      <label htmlFor={id} className="block text-xs text-slate-400">
        Limite de CVs à scorer <span className="text-slate-500">(optionnel)</span>
      </label>
      <input
        id={id}
        type="number"
        min={1}
        step={1}
        inputMode="numeric"
        placeholder="Tous les CVs du vivier"
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        className="w-full max-w-[220px] rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:border-[#1f9d94]/50 focus:outline-none focus:ring-1 focus:ring-[#1f9d94]/30 disabled:opacity-50"
      />
      {error ? (
        <p className="text-xs text-red-400">{error}</p>
      ) : (
        <p className="text-[11px] text-slate-500">
          Réduit le temps de matching sur les offres avec beaucoup de CVs.
        </p>
      )}
    </div>
  );
}
