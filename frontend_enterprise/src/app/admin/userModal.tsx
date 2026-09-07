'use client';

import React, { useState } from 'react';
import { motion } from 'motion/react';
import { Loader2, Pencil, UserPlus } from 'lucide-react';

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: 'sourcer' | 'recruiter' | 'admin';
  is_active: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export const ROLE_LABELS: Record<string, string> = {
  recruiter: 'Recruteur',
  sourcer: 'Sourceur',
  admin: 'Administrateur',
};

export const ROLE_LABELS_PLURAL: Record<string, string> = {
  recruiter: 'Recruteurs',
  sourcer: 'Sourceurs',
  admin: 'Admins',
};

export const ROLE_BADGE: Record<string, string> = {
  recruiter: 'bg-blue-50 text-blue-700 border-blue-200',
  sourcer: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  admin: 'bg-purple-50 text-purple-700 border-purple-200',
};

export const AVATAR_GRADIENT: Record<string, string> = {
  recruiter: 'bg-blue-50 text-blue-700 border-blue-100',
  sourcer: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  admin: 'bg-purple-50 text-purple-700 border-purple-100',
};

export function initials(name: string) {
  return name.split(' ').slice(0, 2).map(w => w[0]?.toUpperCase() ?? '').join('');
}

export function relTime(iso: string | null): string {
  if (!iso) return 'Jamais';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 2) return "à l'instant";
  if (mins < 60) return `il y a ${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `il y a ${hrs} h`;
  if (hrs < 48) return 'hier';
  return new Date(iso).toLocaleDateString('fr-FR');
}

export function fullDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' });
}

export const inputClass = 'w-full rounded-lg border border-[#d8e0ea] bg-white px-4 py-3 text-sm text-slate-950 placeholder:text-slate-400 shadow-sm transition-all focus:border-[#2f66ed]/60 focus:outline-none focus:ring-2 focus:ring-[#2f66ed]/10';
export const labelClass = 'text-xs font-semibold uppercase tracking-wide text-slate-500';
// Create / edit user modal.
// â”€â”€ Create / Edit user modal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export function UserModal({
  mode, user, isSelf, onClose, onSaved,
}: {
  mode: 'create' | 'edit';
  user?: AdminUser;
  isSelf?: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [role, setRole] = useState<string>(user?.role ?? 'sourcer');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [isActive, setIsActive] = useState(user?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailValid = (e: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e.trim());

  async function handleSave() {
    setError(null);
    if (!fullName.trim()) { setError('Le nom complet est requis.'); return; }
    if (!email.trim()) { setError("L'email est requis."); return; }
    if (!emailValid(email)) { setError("Format d'email invalide."); return; }
    if (mode === 'create') {
      if (password.length < 8) { setError('Le mot de passe doit contenir au moins 8 caractères.'); return; }
      if (password !== confirm) { setError('Les mots de passe ne correspondent pas.'); return; }
    }
    setSaving(true);
    try {
      let res: Response;
      if (mode === 'create') {
        res = await fetch(`${API_BASE}/admin/users`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email.trim(), full_name: fullName.trim(), role, password }),
        });
      } else {
        res = await fetch(`${API_BASE}/admin/users/${user!.id}`, {
          method: 'PATCH',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ full_name: fullName.trim(), email: email.trim(), role, is_active: isActive }),
        });
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Une erreur est survenue.");
      }
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Une erreur est survenue.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative w-full max-w-lg rounded-xl border border-[#d8e0ea] bg-white p-6 shadow-2xl shadow-slate-950/20"
      >
        <h2 className="text-lg font-semibold text-slate-950">
          {mode === 'create' ? 'Nouvel utilisateur' : "Modifier l'utilisateur"}
        </h2>

        <div className="mt-5 space-y-4">
          <div className="space-y-1.5">
            <label className={labelClass}>Nom complet</label>
            <input className={inputClass} value={fullName} onChange={e => setFullName(e.target.value)} placeholder="Jean Dupont" />
          </div>

          <div className="space-y-1.5">
            <label className={labelClass}>Email</label>
            <input
              className={isSelf && mode === 'edit' ? `${inputClass} opacity-60 cursor-not-allowed` : inputClass}
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="jean.dupont@itroad.com"
              disabled={isSelf && mode === 'edit'}
            />
            {isSelf && mode === 'edit' && <p className="text-xs text-slate-500">Vous ne pouvez pas modifier votre propre email.</p>}
          </div>

          <div className="space-y-1.5">
            <label className={labelClass}>Rôle</label>
            <select
              value={role}
              onChange={e => setRole(e.target.value)}
              className={inputClass}
            >
              <option value="sourcer">Sourceur</option>
              <option value="recruiter">Recruteur</option>
              <option value="admin">Administrateur</option>
            </select>
          </div>

          {mode === 'create' ? (
            <>
              <div className="space-y-1.5">
                <label className={labelClass}>Mot de passe</label>
                <input className={inputClass} type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
              </div>
              <div className="space-y-1.5">
                <label className={labelClass}>Confirmer le mot de passe</label>
                <input className={inputClass} type="password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="••••••••" />
              </div>
            </>
          ) : (
            <label className="flex items-center gap-3 cursor-pointer select-none">
              <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)} className="h-4 w-4 accent-[#2f66ed]" />
              <span className="text-sm text-slate-700">Compte actif</span>
            </label>
          )}

          {error && <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        </div>

        <div className="mt-6 flex gap-3">
          <button onClick={onClose} className="flex-1 rounded-lg border border-[#d8e0ea] bg-white px-4 py-2.5 text-sm font-semibold text-slate-600 transition-all hover:border-slate-300 hover:bg-slate-50 hover:text-slate-950">
            Annuler
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-[#2f66ed] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(47,102,237,0.18)] transition-all hover:bg-[#2458d8] disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : (mode === 'create' ? <UserPlus className="h-4 w-4" /> : <Pencil className="h-4 w-4" />)}
            {mode === 'create' ? 'Créer' : 'Enregistrer'}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

