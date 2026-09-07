'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { motion } from 'motion/react';
import { Eye, EyeOff, Loader2, Lock, Mail } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || 'Email ou mot de passe incorrect.');
        setPassword('');
        setLoading(false);
        return;
      }

      const user = await res.json();
      setLoading(false);
      const destination =
        user.role === 'admin' ? '/admin'
        : user.role === 'recruiter' ? '/recruiter'
        : '/sourcer';
      router.push(destination);
    } catch {
      setError("Impossible de contacter le serveur. Verifiez que l'API est demarree.");
      setLoading(false);
    }
  }

  const inputClass =
    'h-12 w-full rounded-lg border border-[#d8e0ea] bg-white pl-10 pr-4 text-sm text-slate-950 placeholder:text-slate-400 outline-none transition focus:border-[#2f66ed]/60 focus:ring-2 focus:ring-[#2f66ed]/15';

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#08111f] px-5 py-10 text-slate-950">
      <motion.section
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-[400px]"
      >
        <div className="mb-8 flex flex-col items-center text-center">
          <Image
            src="/IT-Group.png"
            alt="IT Road Consulting"
            width={170}
            height={54}
            priority
            className="h-14 w-auto object-contain brightness-0 invert"
          />
          <p className="mt-4 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
            Powered by IT Road
          </p>
        </div>

        <div className="rounded-xl border border-white/10 bg-white p-6 shadow-[0_22px_60px_rgba(0,0,0,0.24)] sm:p-7">

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-700">Email professionnel</label>
                  <div className="relative">
                    <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      placeholder="vous@itroad.com"
                      className={inputClass}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-700">Mot de passe</label>
                  <div className="relative">
                    <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      type={showPwd ? 'text' : 'password'}
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      placeholder="Mot de passe"
                      className={`${inputClass} pr-11`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd(v => !v)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 transition hover:text-slate-800"
                      tabIndex={-1}
                      aria-label={showPwd ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                    >
                      {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700"
                  >
                    {error}
                  </motion.div>
                )}

                <motion.button
                  type="submit"
                  disabled={loading}
                  whileTap={!loading ? { scale: 0.99 } : {}}
                  className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#2f66ed] text-sm font-semibold text-white shadow-[0_10px_24px_rgba(47,102,237,0.22)] transition hover:bg-[#2558d7] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Connexion...
                    </>
                  ) : (
                    'Se connecter'
                  )}
                </motion.button>
              </form>
        </div>
      </motion.section>
    </main>
  );
}

