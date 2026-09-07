import { motion } from "motion/react";
import { Sparkles, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";

export function Hero() {
  const router = useRouter();

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20">
      {/* Animated Background Elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#6366f1]/20 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-[#818cf8]/20 rounded-full blur-[120px] animate-pulse delay-700" />
      </div>

      {/* Grid Pattern Overlay */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.03)_1px,transparent_1px)] bg-[size:64px_64px]" />

      <div className="relative max-w-7xl mx-auto px-6 py-32 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#1e293b]/50 backdrop-blur-sm border border-white/10 rounded-full mb-8"
        >
          <Sparkles className="w-4 h-4 text-[#818cf8]" />
          <span className="text-sm text-slate-300">
            Propulsé par une IA de Nouvelle Génération
          </span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.1 }}
          className="text-5xl md:text-7xl font-bold mb-6 leading-tight"
        >
          <span className="bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent">
            Découverte Intelligente
          </span>
          <br />
          <span className="bg-gradient-to-r from-[#6366f1] to-[#818cf8] bg-clip-text text-transparent">
            de Talents
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="text-xl text-slate-400 max-w-3xl mx-auto mb-12 leading-relaxed"
        >
          Transformez votre processus de recrutement avec l'extraction de CV par IA 
          et le matching intelligent. Analysez PDF, DOCX et documents scannés 
          avec une précision de niveau entreprise.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <motion.button
            whileHover={{ scale: 1.05, y: -2 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => router.push('/pipeline')}
            className="group px-8 py-4 bg-gradient-to-r from-[#6366f1] to-[#818cf8] text-white font-semibold rounded-xl shadow-2xl shadow-indigo-500/50 hover:shadow-indigo-500/70 transition-all flex items-center gap-2"
          >
            Lancer le traitement
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05, y: -2 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => {
              document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
            }}
            className="px-8 py-4 bg-[#1e293b]/50 backdrop-blur-sm border border-white/10 text-white font-semibold rounded-xl hover:bg-[#334155]/50 transition-all"
          >
            En savoir plus
          </motion.button>
        </motion.div>

        {/* Trust Indicators */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.5 }}
          className="mt-20 flex flex-wrap items-center justify-center gap-8 text-slate-500"
        >
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-sm">Certifié SOC 2</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-sm">Conforme au RGPD</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-sm">Prêt pour l'entreprise</span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
