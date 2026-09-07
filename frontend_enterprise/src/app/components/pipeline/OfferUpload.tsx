'use client';

import React, { useState } from 'react';
import { motion } from 'motion/react';
import { useRouter } from 'next/navigation';
import { AlertCircle, Loader2, Upload } from 'lucide-react';
import { FileUploader } from './FileUploader';
import { usePipeline } from '@/hooks/usePipeline';

export function OfferUpload() {
  const router = useRouter();
  const { createJob, loading, error, setError } = usePipeline();

  const [cvFiles, setCvFiles] = useState<File[]>([]);
  const [offerFile, setOfferFile] = useState<File | null>(null);
  const [submissionStatus, setSubmissionStatus] = useState<string | null>(null);

  const handleCVsSelected = (files: File[]) => {
    setCvFiles(files);
    setError(null);
  };

  const handleOfferSelected = (file: File) => {
    setOfferFile(file);
    setError(null);
  };

  const handleRemoveCV = (index: number) => {
    setCvFiles((currentFiles) => currentFiles.filter((_, currentIndex) => currentIndex !== index));
  };

  const handleRemoveOffer = () => {
    setOfferFile(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    try {
      if (cvFiles.length === 0) {
        setError('Veuillez s\u00e9lectionner au moins un CV.');
        return;
      }

      if (!offerFile) {
        setError("Veuillez s\u00e9lectionner une offre d'emploi.");
        return;
      }

      setSubmissionStatus('Envoi des fichiers au serveur...');
      
      const result = await createJob(cvFiles, offerFile, true);
      
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
    <form onSubmit={handleSubmit} className="space-y-8">
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
        mode="combined"
        cvFiles={cvFiles}
        offerFile={offerFile}
        onCVsSelected={handleCVsSelected}
        onOfferSelected={handleOfferSelected}
        onRemoveCV={handleRemoveCV}
        onRemoveOffer={handleRemoveOffer}
        isLoading={loading}
      />

      <motion.button
        type="submit"
        disabled={loading || cvFiles.length === 0 || !offerFile}
        whileHover={{ y: -2, scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className="flex min-h-[72px] w-full items-center justify-center gap-3 rounded-[20px] bg-[#1f9d94] px-8 text-[20px] font-bold text-white shadow-[0_20px_60px_rgba(31,157,148,0.4)] transition-all hover:bg-[#25afa5] hover:shadow-[0_24px_80px_rgba(31,157,148,0.5)] disabled:cursor-not-allowed disabled:bg-[#1f9d94]/45 disabled:text-white/70 disabled:shadow-none"
      >
        {loading ? (
          <>
            <Loader2 className="h-6 w-6 animate-spin" />
            Traitement en cours...
          </>
        ) : (
          <>
            <Upload className="h-6 w-6" />
            Lancer le traitement
          </>
        )}
      </motion.button>
    </form>
  );
}
