'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'motion/react';
import {
  BarChart2, Briefcase, CheckCircle, LogIn, Pencil, Play, Power, Loader2,
  Trash2, UserMinus, UserPlus, Users, XCircle,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

interface ActivityEvent {
  type: string;
  description: string;
  user: string | null;
  timestamp: string;
}

const FILTERS = [
  { key: 'all', label: 'Tout' },
  { key: 'offers', label: 'Offres' },
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'users', label: 'Utilisateurs' },
] as const;

const CATEGORY: Record<string, string> = {
  user_created: 'users',
  user_updated: 'users',
  user_deactivated: 'users',
  user_reactivated: 'users',
  user_deleted: 'users',
  user_login: 'users',
  offer_created: 'offers',
  offer_assigned: 'offers',
  offer_deleted: 'offers',
  pipeline_launched: 'pipeline',
  pipeline_completed: 'pipeline',
  pipeline_failed: 'pipeline',
};

function typeIcon(type: string) {
  switch (type) {
    case 'user_created': return <UserPlus className="h-4 w-4 text-emerald-600" />;
    case 'user_updated': return <Pencil className="h-4 w-4 text-slate-600" />;
    case 'user_deactivated': return <UserMinus className="h-4 w-4 text-amber-600" />;
    case 'user_reactivated': return <Power className="h-4 w-4 text-emerald-600" />;
    case 'user_deleted': return <Trash2 className="h-4 w-4 text-red-600" />;
    case 'user_login': return <LogIn className="h-4 w-4 text-slate-600" />;
    case 'offer_created': return <Briefcase className="h-4 w-4 text-blue-600" />;
    case 'offer_assigned': return <Users className="h-4 w-4 text-indigo-600" />;
    case 'offer_deleted': return <Trash2 className="h-4 w-4 text-red-600" />;
    case 'pipeline_launched': return <Play className="h-4 w-4 text-blue-600" />;
    case 'pipeline_completed': return <CheckCircle className="h-4 w-4 text-emerald-600" />;
    case 'pipeline_failed': return <XCircle className="h-4 w-4 text-red-600" />;
    default: return <BarChart2 className="h-4 w-4 text-slate-600" />;
  }
}

function relTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 2) return "à l'instant";
  if (mins < 60) return `il y a ${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `il y a ${hrs} h`;
  if (hrs < 48) return 'hier';
  return new Date(iso).toLocaleDateString('fr-FR');
}

function fullDate(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export default function AdminActivityPage() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    fetch(`${API_BASE}/admin/activity`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => { setEvents(d.events ?? []); setLoading(false); })
      .catch(() => { setError("Impossible de charger le journal d'activité."); setLoading(false); });
  }, []);

  const filtered = useMemo(() => {
    if (filter === 'all') return events;
    return events.filter(e => CATEGORY[e.type] === filter);
  }, [events, filter]);

  return (
    <div className="w-full max-w-5xl space-y-6">
      <div className="border-b border-[#d8e0ea] pb-6">
        <h1 className="text-3xl font-bold text-slate-950">Activité</h1>
        <p className="mt-1 text-slate-600">Journal des événements système</p>
      </div>

      {/* Type filter tabs */}
      <div className="flex gap-1 overflow-x-auto border-b border-[#d8e0ea]">
        {FILTERS.map(f => {
          const active = filter === f.key;
          const count = f.key === 'all' ? events.length : events.filter(e => CATEGORY[e.type] === f.key).length;
          return (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-all ${
                active ? 'border-[#2f66ed] text-[#2f66ed]' : 'border-transparent text-slate-600 hover:text-slate-950'
              }`}
            >
              {f.label}
              {count > 0 && (
                <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs ${active ? 'bg-[#2f66ed] text-white' : 'bg-slate-100 text-slate-600'}`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {error && <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-[#2f66ed]" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-[#d8e0ea] bg-white p-8 text-center text-slate-500 shadow-sm">
          Aucun événement à afficher.
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="overflow-hidden rounded-xl border border-[#d8e0ea] bg-white shadow-sm"
        >
          <ul className="divide-y divide-[#e5ebf2]">
            {filtered.map((e, i) => (
              <li key={i} className="flex items-center gap-4 px-6 py-4 transition-colors hover:bg-blue-50/45">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-[#d8e0ea] bg-slate-50">
                  {typeIcon(e.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="truncate text-sm font-medium text-slate-800">{e.description}</p>
                  {e.user && <p className="text-xs text-slate-500 truncate">Par {e.user}</p>}
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-xs font-medium text-slate-700">{relTime(e.timestamp)}</p>
                  <p className="text-[11px] text-slate-500">{fullDate(e.timestamp)}</p>
                </div>
              </li>
            ))}
          </ul>
        </motion.div>
      )}
    </div>
  );
}

