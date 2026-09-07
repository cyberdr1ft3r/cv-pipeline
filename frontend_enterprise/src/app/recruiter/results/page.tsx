'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { motion } from 'motion/react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

interface Job { id: string; status: string; stage: string; }
interface Offer { id: string; title: string; description: string; created_at: string; job: Job | null; }

export default function RecruiterResultsPage() {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/offers`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => {
        const completed = (d.offers || []).filter((o: Offer) => o.job?.status === 'succeeded');
        setOffers(completed);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-indigo-400" /></div>;

  return (
    <div className="w-full max-w-7xl space-y-6">
      <div className="mb-8 border-b border-white/10 pb-6">
        <h1 className="text-3xl font-bold text-white">Résultats des Matchings</h1>
        <p className="text-slate-400 mt-1">Résultats des pipelines de matching IA</p>
      </div>

      {offers.length === 0 && (
        <div className="flex flex-col items-center justify-center h-48 rounded-2xl border border-white/10 bg-white/[0.02] text-slate-500">
          <p className="font-medium">Aucun résultat disponible</p>
          <p className="text-sm mt-1">Les résultats apparaîtront ici une fois les pipelines terminés.</p>
        </div>
      )}

      {offers.map((offer, i) => (
        <motion.div key={offer.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
          className="rounded-2xl border border-green-500/20 bg-green-500/[0.03] p-6 flex items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-400 flex-shrink-0" />
              <h2 className="font-semibold truncate">{offer.title}</h2>
            </div>
            <p className="text-slate-400 text-sm mt-1 line-clamp-1">{offer.description}</p>
            <p className="text-xs text-slate-500 mt-1">Terminé le {new Date(offer.created_at).toLocaleDateString('fr-FR')}</p>
          </div>
          {offer.job && (
            <Link href={`/recruiter/offers/${offer.id}`}
              className="flex-shrink-0 px-4 py-2 rounded-xl bg-green-500/10 border border-green-500/20 text-green-400 text-sm hover:bg-green-500/20 transition-all">
              Voir les résultats
            </Link>
          )}
        </motion.div>
      ))}
    </div>
  );
}

