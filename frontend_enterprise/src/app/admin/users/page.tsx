'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence } from 'motion/react';
import {
  Loader2, Pencil, Plus, Power, Search, Trash2,
} from 'lucide-react';
import {
  API_BASE, AdminUser, ROLE_LABELS, ROLE_BADGE, AVATAR_GRADIENT,
  initials, relTime, UserModal,
} from '../userModal';

const ROLE_FILTER_OPTIONS = [
  { value: 'all', label: 'Tous les rôles' },
  { value: 'sourcer', label: 'Sourceur' },
  { value: 'recruiter', label: 'Recruteur' },
  { value: 'admin', label: 'Administrateur' },
];

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [meId, setMeId] = useState<string>('');

  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');

  const [modal, setModal] = useState<{ mode: 'create' | 'edit'; user?: AdminUser } | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  function fetchUsers() {
    setLoading(true);
    Promise.all([
      fetch(`${API_BASE}/auth/me`, { credentials: 'include' }).then(r => r.ok ? r.json() : null),
      fetch(`${API_BASE}/admin/users`, { credentials: 'include' }).then(r => r.ok ? r.json() : Promise.reject()),
    ]).then(([me, data]) => {
      if (me) setMeId(me.user_id);
      setUsers(data.users ?? []);
      setLoading(false);
    }).catch(() => { setError('Impossible de charger les utilisateurs.'); setLoading(false); });
  }

  useEffect(() => { fetchUsers(); }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return users.filter(u => {
      if (roleFilter !== 'all' && u.role !== roleFilter) return false;
      if (q && !u.full_name.toLowerCase().includes(q) && !u.email.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [users, search, roleFilter]);

  async function toggleActive(u: AdminUser) {
    setBusyId(u.id);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/admin/users/${u.id}`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !u.is_active }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Erreur lors de la mise à jour.');
      }
      fetchUsers();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de la mise à jour.');
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(id: string) {
    setBusyId(id);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/admin/users/${id}`, { method: 'DELETE', credentials: 'include' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Erreur lors de la suppression.');
      }
      setDeleteConfirmId(null);
      fetchUsers();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de la suppression.');
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="w-full max-w-7xl space-y-6">
      <div className="flex items-center justify-between gap-4 border-b border-[#d8e0ea] pb-6">
        <div>
          <h1 className="text-3xl font-bold text-slate-950">Utilisateurs</h1>
          <p className="mt-1 text-slate-600">Gérez les comptes et les rôles de la plateforme</p>
        </div>
        <button
          onClick={() => setModal({ mode: 'create' })}
          className="flex flex-shrink-0 items-center gap-2 rounded-lg bg-[#2f66ed] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(47,102,237,0.18)] transition-all hover:bg-[#2458d8]"
        >
          <Plus className="h-4 w-4" />
          Nouvel utilisateur
        </button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Rechercher par nom ou email…"
            className="w-full rounded-lg border border-[#d8e0ea] bg-white py-2.5 pl-10 pr-4 text-sm text-slate-950 shadow-sm placeholder:text-slate-400 transition-all focus:border-[#2f66ed]/60 focus:outline-none focus:ring-2 focus:ring-[#2f66ed]/10"
          />
        </div>
        <select
          value={roleFilter}
          onChange={e => setRoleFilter(e.target.value)}
          className="w-full rounded-lg border border-[#d8e0ea] bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm transition-all focus:border-[#2f66ed]/60 focus:outline-none focus:ring-2 focus:ring-[#2f66ed]/10 sm:w-auto sm:min-w-[180px]"
        >
          {ROLE_FILTER_OPTIONS.map(option => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </div>

      {error && <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-[#2f66ed]" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-[#d8e0ea] bg-white p-8 text-center text-slate-500 shadow-sm">
          Aucun utilisateur ne correspond à votre recherche.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[#d8e0ea] bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#e5ebf2] bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th className="px-6 py-3">Utilisateur</th>
                  <th className="px-6 py-3">Rôle</th>
                  <th className="px-6 py-3">Statut</th>
                  <th className="px-6 py-3">Dernière connexion</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e5ebf2]">
                {filtered.map(u => {
                  const isSelf = u.id === meId;
                  return (
                    <tr key={u.id} className="transition-colors hover:bg-blue-50/45">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full border ${AVATAR_GRADIENT[u.role] ?? 'border-slate-200 bg-slate-50 text-slate-700'}`}>
                            <span className="text-xs font-bold">{initials(u.full_name)}</span>
                          </div>
                          <div className="min-w-0">
                            <p className="truncate font-medium text-slate-950">
                              {u.full_name}
                              {isSelf && <span className="ml-2 text-xs text-slate-500">(vous)</span>}
                            </p>
                            <p className="truncate text-xs text-slate-500">{u.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${ROLE_BADGE[u.role] ?? 'border-slate-200 bg-slate-50 text-slate-700'}`}>
                          {ROLE_LABELS[u.role] ?? u.role}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {u.is_active ? (
                          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Actif
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                            <span className="h-1.5 w-1.5 rounded-full bg-slate-400" /> Inactif
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-slate-600">{relTime(u.last_login_at)}</td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => setModal({ mode: 'edit', user: u })}
                            title="Modifier"
                            className="rounded-lg border border-[#d8e0ea] p-2 text-slate-500 transition-all hover:border-[#2f66ed]/40 hover:bg-blue-50 hover:text-[#2f66ed]"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => toggleActive(u)}
                            disabled={isSelf || busyId === u.id}
                            title={isSelf ? 'Action impossible sur votre compte' : (u.is_active ? 'Désactiver' : 'Activer')}
                            className={`rounded-lg border p-2 transition-all disabled:cursor-not-allowed disabled:opacity-40 ${
                              u.is_active
                                ? 'border-amber-200 text-amber-600 hover:bg-amber-50'
                                : 'border-emerald-200 text-emerald-600 hover:bg-emerald-50'
                            }`}
                          >
                            {busyId === u.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Power className="h-3.5 w-3.5" />}
                          </button>
                          {deleteConfirmId === u.id ? (
                            <span className="flex items-center gap-1.5">
                              <span className="text-xs text-red-600">Confirmer ?</span>
                              <button
                                onClick={() => handleDelete(u.id)}
                                disabled={busyId === u.id}
                                className="rounded-lg bg-red-600 px-2.5 py-1 text-xs text-white transition-all hover:bg-red-500 disabled:opacity-50"
                              >
                                {busyId === u.id ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Oui'}
                              </button>
                              <button
                                onClick={() => setDeleteConfirmId(null)}
                                className="rounded-lg border border-[#d8e0ea] px-2.5 py-1 text-xs text-slate-600 transition-all hover:bg-slate-50 hover:text-slate-950"
                              >
                                Non
                              </button>
                            </span>
                          ) : (
                            <button
                              onClick={() => setDeleteConfirmId(u.id)}
                              disabled={isSelf}
                              title={isSelf ? 'Vous ne pouvez pas vous supprimer' : 'Supprimer'}
                              className="rounded-lg border border-red-200 p-2 text-red-600 transition-all hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <AnimatePresence>
        {modal && (
          <UserModal
            mode={modal.mode}
            user={modal.user}
            isSelf={modal.user?.id === meId}
            onClose={() => setModal(null)}
            onSaved={() => { setModal(null); fetchUsers(); }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

