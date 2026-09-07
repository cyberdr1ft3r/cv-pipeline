'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'motion/react';
import { ChevronDown, Loader } from 'lucide-react';
import { useApi } from '@/hooks/useApi';

interface SessionSelectorProps {
  onSessionSelected: (sessionId: string) => void;
}

interface Session {
  session_id: string;
  created_date: string;
  cv_count?: number;
}

function formatSessionDate(value: string) {
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

export function SessionSelector({ onSessionSelected }: SessionSelectorProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const { get } = useApi();

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        setIsLoading(true);
        const data = await get('/sessions');
        setSessions(data.sessions || []);
      } catch (error) {
        console.error('Failed to load sessions:', error);
        setSessions([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSessions();
  }, [get]);

  const selectedSession = useMemo(
    () => sessions.find((session) => session.session_id === selectedId) || null,
    [selectedId, sessions]
  );

  const handleSelect = (sessionId: string) => {
    setSelectedId(sessionId);
    onSessionSelected(sessionId);
    setIsOpen(false);
  };

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <h2 className="text-[22px] font-semibold tracking-[-0.02em] text-white">
          {'S\u00e9lectionner la session de CVs'}
        </h2>
        <p className="text-base text-slate-300">
          {'Choisissez un lot de CVs d\u00e9j\u00e0 extrait pour lancer un nouvel appairage.'}
        </p>
      </div>

      <div className="relative">
        <motion.button
          type="button"
          onClick={() => setIsOpen((currentValue) => !currentValue)}
          whileHover={{ y: -1 }}
          className="flex min-h-[84px] w-full items-center justify-between rounded-[28px] border border-white/18 bg-[#1a2240]/78 px-6 text-left transition-all hover:border-cyan-400/45 hover:bg-[#1d2949]/88"
        >
          <div className="min-w-0 space-y-1">
            <p className="text-sm uppercase tracking-[0.18em] text-cyan-300/80">Session CV</p>

            {isLoading ? (
              <div className="flex items-center gap-3 text-white">
                <Loader className="h-4 w-4 animate-spin text-cyan-300" />
                <span>Chargement des sessions...</span>
              </div>
            ) : selectedSession ? (
              <>
                <p className="truncate text-base font-semibold text-white">
                  {selectedSession.session_id}
                </p>
                <p className="text-sm text-slate-400">
                  {formatSessionDate(selectedSession.created_date)}
                  {selectedSession.cv_count ? ` \u2022 ${selectedSession.cv_count} CVs` : ''}
                </p>
              </>
            ) : (
              <>
                <p className="text-base font-semibold text-white">
                  Choisir une session existante
                </p>
                <p className="text-sm text-slate-400">
                  {"Les CVs s\u00e9lectionn\u00e9s seront r\u00e9utilis\u00e9s avec la nouvelle offre."}
                </p>
              </>
            )}
          </div>

          <ChevronDown
            className={`h-5 w-5 flex-shrink-0 text-cyan-300 transition-transform ${
              isOpen ? 'rotate-180' : ''
            }`}
          />
        </motion.button>

        {isOpen && !isLoading && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="absolute left-0 right-0 top-full z-30 mt-3 overflow-hidden rounded-[24px] border border-white/12 bg-[#121b37] shadow-[0_24px_80px_rgba(2,8,23,0.55)]"
          >
            {sessions.length === 0 ? (
              <div className="px-6 py-5 text-sm text-slate-300">
                Aucune session disponible pour le moment.
              </div>
            ) : (
              sessions.map((session) => {
                const isSelected = session.session_id === selectedId;

                return (
                  <motion.button
                    key={session.session_id}
                    type="button"
                    onClick={() => handleSelect(session.session_id)}
                    whileHover={{ x: 2 }}
                    className={`flex w-full items-center justify-between gap-4 border-b border-white/6 px-6 py-4 text-left transition-colors last:border-b-0 ${
                      isSelected ? 'bg-cyan-400/8' : 'hover:bg-white/5'
                    }`}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white">
                        {session.session_id}
                      </p>
                      <p className="text-xs text-slate-400">
                        {formatSessionDate(session.created_date)}
                      </p>
                    </div>

                    {typeof session.cv_count === 'number' && (
                      <span className="rounded-full border border-cyan-400/18 bg-cyan-400/10 px-3 py-1 text-xs font-medium text-cyan-200">
                        {session.cv_count} CVs
                      </span>
                    )}
                  </motion.button>
                );
              })
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
}
