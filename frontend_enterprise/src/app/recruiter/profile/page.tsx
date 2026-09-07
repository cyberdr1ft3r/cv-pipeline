'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { CheckCircle2, Eye, EyeOff, Loader2, Lock, User } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

function roleLabel(role: string): string {
  if (role === 'recruiter') return 'Recruteur';
  if (role === 'sourcer') return 'Sourceur';
  if (role === 'admin') return 'Administrateur';
  return role;
}

function PwdInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const [show, setShow] = useState(false);
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{label}</label>
      <div className="relative">
        <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" />
        <input
          type={show ? 'text' : 'password'}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-full pl-10 pr-11 py-3 rounded-xl border border-white/10 bg-white/[0.05] text-white text-sm placeholder-slate-500 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/30 transition-all"
        />
        <button type="button" onClick={() => setShow(v => !v)} tabIndex={-1}
          className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors">
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

const sectionClass = "rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-5";
const inputClass = "w-full px-4 py-3 rounded-xl border border-white/10 bg-white/[0.05] text-white text-sm focus:outline-none focus:border-teal-500/50 transition-all";
const inputReadOnlyClass = "w-full px-4 py-3 rounded-xl border border-white/[0.07] bg-white/[0.02] text-slate-500 text-sm cursor-not-allowed";

export default function ProfilePage() {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('');
  const [fullName, setFullName] = useState('');
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [profileError, setProfileError] = useState('');

  const [curPwd, setCurPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');
  const [pwdLoading, setPwdLoading] = useState(false);
  const [pwdSuccess, setPwdSuccess] = useState(false);
  const [pwdError, setPwdError] = useState('');

  useEffect(() => {
    fetch(`${API_BASE}/auth/me`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) { setEmail(d.email); setRole(d.role); setFullName(d.full_name); }
      });
  }, []);

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setProfileError(''); setProfileSuccess(false); setProfileLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/profile`, {
        method: 'PATCH', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Erreur ${res.status}`);
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch (err: unknown) {
      setProfileError(err instanceof Error ? err.message : String(err));
    } finally { setProfileLoading(false); }
  }

  async function changePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwdError(''); setPwdSuccess(false); setPwdLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/password`, {
        method: 'PATCH', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: curPwd, new_password: newPwd, confirm_password: confirmPwd }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Erreur ${res.status}`);
      setPwdSuccess(true); setCurPwd(''); setNewPwd(''); setConfirmPwd('');
      setTimeout(() => setPwdSuccess(false), 3000);
    } catch (err: unknown) {
      setPwdError(err instanceof Error ? err.message : String(err));
    } finally { setPwdLoading(false); }
  }

  const btnClass = "flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-[#1f9d94] hover:bg-[#25afa5] text-white text-sm font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_4px_16px_rgba(31,157,148,0.3)]";

  return (
    <div className="max-w-5xl space-y-6">
      <div className="mb-8 border-b border-white/10 pb-6">
        <h1 className="text-3xl font-bold text-white">Mon Profil</h1>
        <p className="text-slate-400 mt-1">Gérez vos informations personnelles et votre mot de passe</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

      {/* Section 1 — Informations personnelles */}
      <form onSubmit={saveProfile} className={sectionClass}>
        <div className="flex items-center gap-2">
          <User className="h-5 w-5 text-teal-400" />
          <h2 className="font-semibold text-white">Informations personnelles</h2>
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Nom complet</label>
          <input value={fullName} onChange={e => setFullName(e.target.value)} className={inputClass} />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Email (non modifiable)</label>
          <input value={email} readOnly className={inputReadOnlyClass} />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Rôle</label>
          <input value={roleLabel(role)} readOnly className={inputReadOnlyClass} />
        </div>

        {profileError && <p className="text-sm text-red-400">{profileError}</p>}
        {profileSuccess && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="flex items-center gap-2 text-sm text-green-400">
            <CheckCircle2 className="h-4 w-4" /> Modifications enregistrées
          </motion.div>
        )}

        <motion.button type="submit" disabled={profileLoading} whileHover={{ y: -1 }} className={btnClass}>
          {profileLoading ? <><Loader2 className="h-4 w-4 animate-spin" />Enregistrement…</> : 'Enregistrer les modifications'}
        </motion.button>
      </form>

      {/* Section 2 — Mot de passe */}
      <form onSubmit={changePassword} className={sectionClass}>
        <div className="flex items-center gap-2">
          <Lock className="h-5 w-5 text-teal-400" />
          <h2 className="font-semibold text-white">Changer le mot de passe</h2>
        </div>

        <PwdInput label="Mot de passe actuel" value={curPwd} onChange={setCurPwd} />
        <PwdInput label="Nouveau mot de passe" value={newPwd} onChange={setNewPwd} />
        <PwdInput label="Confirmer le nouveau mot de passe" value={confirmPwd} onChange={setConfirmPwd} />

        {pwdError && <p className="text-sm text-red-400">{pwdError}</p>}
        {pwdSuccess && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="flex items-center gap-2 text-sm text-green-400">
            <CheckCircle2 className="h-4 w-4" /> Mot de passe mis à jour avec succès
          </motion.div>
        )}

        <motion.button type="submit" disabled={pwdLoading || !curPwd || !newPwd || !confirmPwd}
          whileHover={!pwdLoading ? { y: -1 } : {}} className={btnClass}>
          {pwdLoading ? <><Loader2 className="h-4 w-4 animate-spin" />Mise à jour…</> : 'Changer le mot de passe'}
        </motion.button>
      </form>

      </div>
    </div>
  );
}

