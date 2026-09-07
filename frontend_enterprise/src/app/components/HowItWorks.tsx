import { motion } from "motion/react";
import { useInView } from "motion/react";
import { useRef } from "react";
import { Upload, Brain, CheckCircle } from "lucide-react";

const steps = [
  {
    icon: Upload,
    number: "01",
    title: "Import des Documents",
    description:
      "Téléchargez les CV des candidats au format PDF, DOCX ou images scannés. Notre système gère les imports massifs avec une organisation parfaite.",
    color: "from-[#6366f1] to-[#818cf8]",
  },
  {
    icon: Brain,
    number: "02",
    title: "L'IA bati les Profils",
    description:
      "L'apprentissage automatique avancé extrait, normalise et structure toutes les données des candidats : compétences, expérience, éducation.",
    color: "from-[#818cf8] to-[#a78bfa]",
  },
  {
    icon: CheckCircle,
    number: "03",
    title: "Analyse avec Précision",
    description:
      "Accédez aux candidats classés, aux résultats de tests techniques et aux profils formatés. Exportez vers votre ATS ou gérez tout via notre plateforme.",
    color: "from-[#a78bfa] to-[#c4b5fd]",
  },
];

interface StepCardProps {
  step: typeof steps[0];
  index: number;
}

function StepCard({ step, index }: StepCardProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.5 });
  const Icon = step.icon;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, x: index % 2 === 0 ? -50 : 50 }}
      animate={
        isInView
          ? { opacity: 1, x: 0 }
          : { opacity: 0, x: index % 2 === 0 ? -50 : 50 }
      }
      transition={{ duration: 0.6, delay: index * 0.2 }}
      className="relative"
    >
      {/* Connecting Line */}
      {index < steps.length - 1 && (
        <div className="hidden lg:block absolute top-24 left-full w-full h-0.5 bg-gradient-to-r from-[#6366f1]/50 to-transparent z-0" />
      )}

      <div className="relative bg-[#111827]/50 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:border-white/20 transition-all duration-300 hover:shadow-2xl hover:shadow-indigo-500/10 group">
        {/* Number Badge */}
        <div className="absolute -top-4 -right-4 w-16 h-16 bg-gradient-to-br from-[#0a0e27] to-[#111827] border border-white/10 rounded-full flex items-center justify-center shadow-xl">
          <span className={`text-2xl font-bold bg-gradient-to-br ${step.color} bg-clip-text text-transparent`}>
            {step.number}
          </span>
        </div>

        {/* Icon */}
        <div
          className={`w-16 h-16 bg-gradient-to-br ${step.color} rounded-xl flex items-center justify-center mb-6 shadow-lg shadow-indigo-500/30 group-hover:scale-110 transition-transform`}
        >
          <Icon className="w-8 h-8 text-white" />
        </div>

        {/* Content */}
        <h3 className="text-2xl font-semibold text-white mb-4">{step.title}</h3>
        <p className="text-slate-400 leading-relaxed">{step.description}</p>

        {/* Gradient Orb */}
        <div
          className={`absolute bottom-0 right-0 w-32 h-32 bg-gradient-to-br ${step.color} opacity-10 blur-3xl rounded-full group-hover:opacity-20 transition-opacity`}
        />
      </div>
    </motion.div>
  );
}

export function HowItWorks() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.2 });

  return (
    <section className="relative py-32 overflow-hidden">
      {/* Background Elements */}
      <div className="absolute inset-0">
        <div className="absolute top-1/3 right-0 w-96 h-96 bg-[#818cf8]/10 rounded-full blur-[120px]" />
      </div>

      <div ref={ref} className="relative max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-20"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-[#1e293b]/50 backdrop-blur-sm border border-white/10 rounded-full mb-6">
            <span className="text-sm text-[#818cf8]">Processus Simple en 3 Étapes</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            <span className="bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
              Comment ça Marche
            </span>
          </h2>
          <p className="text-xl text-slate-400 max-w-2xl mx-auto">
            De l'importation aux résultats en quelques minutes. Notre IA gère la complexité pour que vous vous concentriez sur l'humain.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-6">
          {steps.map((step, index) => (
            <StepCard key={index} step={step} index={index} />
          ))}
        </div>

        {/* Bottom CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
          transition={{ duration: 0.6, delay: 0.8 }}
          className="text-center mt-16"
        >
          <motion.button
            whileHover={{ scale: 1.05, y: -2 }}
            whileTap={{ scale: 0.95 }}
            className="px-8 py-4 bg-gradient-to-r from-[#6366f1] to-[#818cf8] text-white rounded-xl shadow-2xl shadow-indigo-500/50 hover:shadow-indigo-500/70 transition-all"
          >
            See It In Action
          </motion.button>
        </motion.div>
      </div>
    </section>
  );
}
