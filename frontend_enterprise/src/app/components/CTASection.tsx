import { motion } from "motion/react";
import { useInView } from "motion/react";
import { useRef } from "react";
import { ArrowRight, Sparkles } from "lucide-react";

export function CTASection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.5 });

  return (
    <section className="relative py-32 overflow-hidden">
      {/* Background Elements */}
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-[#6366f1]/20 rounded-full blur-[150px]" />
      </div>

      {/* Grid Pattern */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.03)_1px,transparent_1px)] bg-[size:64px_64px]" />

      <div ref={ref} className="relative max-w-5xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 30 }}
          transition={{ duration: 0.8 }}
          className="relative"
        >
          {/* Glassmorphic Container */}
          <div className="bg-gradient-to-br from-[#111827]/80 to-[#1e293b]/80 backdrop-blur-xl border border-white/10 rounded-3xl p-12 md:p-16 shadow-2xl shadow-indigo-500/20">
            {/* Decorative Gradient Orbs */}
            <div className="absolute top-0 left-0 w-40 h-40 bg-gradient-to-br from-[#6366f1]/30 to-transparent rounded-full blur-3xl" />
            <div className="absolute bottom-0 right-0 w-40 h-40 bg-gradient-to-br from-[#818cf8]/30 to-transparent rounded-full blur-3xl" />

            <div className="relative text-center">
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={
                  isInView ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.9 }
                }
                transition={{ duration: 0.6, delay: 0.2 }}
                className="inline-flex items-center gap-2 px-4 py-2 bg-[#0a0e27]/50 border border-white/10 rounded-full mb-6"
              >
                <Sparkles className="w-4 h-4 text-[#818cf8]" />
                <span className="text-sm text-slate-300">
                  Rejoignez +500 Entreprises
                </span>
              </motion.div>

              <motion.h2
                initial={{ opacity: 0, y: 20 }}
                animate={
                  isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }
                }
                transition={{ duration: 0.6, delay: 0.3 }}
                className="text-4xl md:text-5xl font-bold mb-6"
              >
                <span className="bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
                  Prêt à Transformer votre
                </span>
                <br />
                <span className="bg-gradient-to-r from-[#6366f1] to-[#818cf8] bg-clip-text text-transparent">
                  Processus de Recrutement ?
                </span>
              </motion.h2>

              <motion.p
                initial={{ opacity: 0, y: 20 }}
                animate={
                  isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }
                }
                transition={{ duration: 0.6, delay: 0.4 }}
                className="text-xl text-slate-400 max-w-2xl mx-auto mb-10"
              >
                Commencez votre essai gratuit de 14 jours. Sans engagement. 
                Découvrez la puissance de l'IA pour la détection de talents dès aujourd'hui.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={
                  isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }
                }
                transition={{ duration: 0.6, delay: 0.5 }}
                className="flex flex-col sm:flex-row items-center justify-center gap-4"
              >
                <motion.button
                  whileHover={{ scale: 1.05, y: -2 }}
                  whileTap={{ scale: 0.95 }}
                  className="group px-10 py-5 bg-gradient-to-r from-[#6366f1] to-[#818cf8] text-white font-bold rounded-xl shadow-2xl shadow-indigo-500/50 hover:shadow-indigo-500/70 transition-all flex items-center gap-2"
                >
                  Essai Gratuit
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.05, y: -2 }}
                  whileTap={{ scale: 0.95 }}
                  className="px-10 py-5 bg-[#0a0e27]/50 backdrop-blur-sm border border-white/20 text-white font-bold rounded-xl hover:bg-[#111827]/50 transition-all"
                >
                  Réserver une Démo
                </motion.button>
              </motion.div>

              {/* Trust Badges */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={isInView ? { opacity: 1 } : { opacity: 0 }}
                transition={{ duration: 0.6, delay: 0.7 }}
                className="mt-12 flex flex-wrap items-center justify-center gap-6 text-sm text-slate-500"
              >
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-green-500 rounded-full" />
                  <span>Essai gratuit de 14 jours</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-green-500 rounded-full" />
                  <span>Sans carte de crédit</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-green-500 rounded-full" />
                  <span>Annulation à tout moment</span>
                </div>
              </motion.div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
