'use client';

import React, { useState } from 'react';
import { motion } from 'motion/react';
import { useRouter } from 'next/navigation';
import { AlertCircle, Loader2, Database } from 'lucide-react';
import { Navigation } from '@/app/components/Navigation';
import { FileUploader } from '@/app/components/pipeline/FileUploader';
import { usePipeline } from '@/hooks/usePipeline';

export default function OfferOnlyPage() {
  const router = useRouter();
  const { createJobOfferOnly, loading, error, setError } = usePipeline();

  const [offerFile, setOfferFile] = useState<File | null>(null);
  const [submissionStatus, setSubmissionStatus] = useState<string | null>(null);

  const handleOfferSelected = (file: File) => {
    setOfferFile(file);
    setError(null);
  };

  const handleRemoveOffer = () => {
    setOfferFile(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    try {
      if (!offerFile) {
        setError("Veuillez s\u00e9lectionner une offre d'emploi.");
        return;
      }

      setSubmissionStatus('Analyse de l\'offre et chargement des CVs depuis la base...');

      const result = await createJobOfferOnly(offerFile);
      setSubmissionStatus('Traitement demarre! Redirection...');
      router.push(`/pipeline/progress?jobId=${result.job_id}`);
    } catch (submissionError) {
      setSubmissionStatus(null);
      const message = submissionError instanceof Error ? submissionError.message : 'Une erreur est survenue lors de la soumission. Veuillez reessayer.';
      setError(message);
      console.error('Submission error:', submissionError);
    }
  };

  return (
    <main className="min-h-screen bg-[#0a1026] text-white">
      <div className="relative isolate min-h-screen overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(115deg,#0b1028_18%,#0d1430_48%,#081227_100%)]" />
        <div className="absolute inset-x-0 top-0 h-[104px] border-b border-white/8 bg-[#0d1228]/96" />
        <div className="absolute left-[-12%] top-[220px] h-[560px] w-[560px] rounded-full bg-[radial-gradient(circle,rgba(18,124,141,0.28)_0%,rgba(18,124,141,0.14)_34%,rgba(10,16,38,0)_72%)] blur-2xl" />
        <div className="absolute right-[-18%] top-[140px] h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle,rgba(36,108,163,0.18)_0%,rgba(36,108,163,0.08)_40%,rgba(10,16,38,0)_74%)] blur-3xl" />

        <Navigation />

        <section className="relative px-6 pb-24 pt-32 md:px-10 lg:pt-40">
          <div className="mx-auto max-w-[1040px]">
            <div className="max-w-[960px] space-y-14">
              <header className="max-w-[860px] space-y-5">
                <h1 className="text-[46px] font-semibold tracking-[-0.04em] text-white sm:text-[56px] lg:text-[60px]">
                  {'T\u00e9l\u00e9charger votre offre'}
                </h1>
                <p className="max-w-[840px] text-xl leading-9 text-slate-200/92">
                  {
                    "Le syst\u00e8me analysera automatiquement votre offre et s\u00e9lectionnera les CVs correspondants depuis notre base de donn\u00e9es"
                  }
                </p>
              </header>

              <div className="flex items-center gap-3 rounded-[20px] border border-cyan-400/25 bg-cyan-500/10 px-5 py-4">
                <Database className="h-5 w-5 flex-shrink-0 text-cyan-300" />
                <p className="text-sm text-cyan-100">
                  Les CVs seront charg\u00e9s automatiquement depuis notre base SFTP en fonction du profil et du niveau d'exp\u00e9rience d\u00e9tect\u00e9s dans l'offre
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-10">
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -12 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-start gap-3 rounded-[20px] border border-red-400/25 bg-red-500/10 px-5 py-4"
                  >
                    <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
                    <p className="text-sm text-red-100">{error}</p>
                  </motion.div>
                )}

                {submissionStatus && !error && (
                  <motion.div
                    initial={{ opacity: 0, y: -12 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center gap-3 rounded-[20px] border border-cyan-400/25 bg-cyan-500/10 px-5 py-4"
                  >
                    <Loader2 className="h-5 w-5 animate-spin text-cyan-300" />
                    <p className="text-sm text-cyan-100">{submissionStatus}</p>
                  </motion.div>
                )}

                <FileUploader
                  mode="offer"
                  offerFile={offerFile}
                  onOfferSelected={handleOfferSelected}
                  onRemoveOffer={handleRemoveOffer}
                  isLoading={loading}
                />

                <motion.button
                  type="submit"
                  disabled={loading || !offerFile}
                  whileHover={{ y: -1 }}
                  whileTap={{ scale: 0.99 }}
                  className="flex min-h-[62px] w-full items-center justify-center rounded-[20px] bg-[#1f9d94] px-6 text-lg font-semibold text-white shadow-[0_18px_45px_rgba(31,157,148,0.28)] transition-all hover:bg-[#25afa5] disabled:cursor-not-allowed disabled:bg-[#1f9d94]/45 disabled:text-white/70 disabled:shadow-none"
                >
                  {loading ? 'Traitement en cours...' : 'Lancer le traitement'}
                </motion.button>
              </form>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
