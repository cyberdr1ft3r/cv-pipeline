import { motion } from "motion/react";
import { useInView } from "motion/react";
import { useRef } from "react";
import {
  FileText,
  Target,
  BarChart3,
  Shield,
  Upload,
  Zap,
  Lock,
  TrendingUp,
} from "lucide-react";

const features = [
  {
    icon: FileText,
    title: "Extraction de CV par IA",
    description:
      "Extrayez des données structurées de PDF, DOCX et scans avec une précision supérieure à 99%. Normalisation intelligente des données.",
    gradient: "from-[#6366f1] to-[#818cf8]",
    size: "lg",
  },
  {
    icon: Target,
    title: "Matching de Candidats",
    description:
      "Scoring intelligent aligné précisément sur les exigences du poste. Classement basé sur les compétences et l'expérience.",
    gradient: "from-[#818cf8] to-[#a78bfa]",
    size: "md",
  },
  {
    icon: BarChart3,
    title: "Analyses de Compétences",
    description:
      "Visualisez les écarts de compétences et la préparation à l'embauche avec des tableaux de bord en temps réel.",
    gradient: "from-[#a78bfa] to-[#c4b5fd]",
    size: "md",
  },
  {
    icon: Shield,
    title: "Sécurité Entreprise",
    description:
      "Pipelines conformes, journaux d'audit et flux de travail sécurisés. Certifié SOC 2 Type II avec chiffrement de bout en bout.",
    gradient: "from-[#6366f1] to-[#4f46e5]",
    size: "lg",
  },
];

interface FeatureCardProps {
  feature: typeof features[0];
  index: number;
}

function FeatureCard({ feature, index }: FeatureCardProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.3 });
  const Icon = feature.icon;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 50 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 50 }}
      transition={{ duration: 0.6, delay: index * 0.1 }}
      className={`relative group ${
        feature.size === "lg" ? "md:col-span-2" : "md:col-span-1"
      }`}
    >
      <div className="h-full p-8 bg-[#111827]/50 backdrop-blur-sm border border-white/10 rounded-2xl hover:border-white/20 transition-all duration-300 hover:shadow-2xl hover:shadow-indigo-500/10">
        {/* Gradient Orb Effect */}
        <div
          className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-br ${feature.gradient} opacity-20 blur-3xl rounded-full group-hover:opacity-30 transition-opacity`}
        />

        <div className="relative">
          <div
            className={`w-14 h-14 bg-gradient-to-br ${feature.gradient} rounded-xl flex items-center justify-center mb-6 shadow-lg shadow-indigo-500/30`}
          >
            <Icon className="w-7 h-7 text-white" />
          </div>

          <h3 className="text-2xl font-semibold text-white mb-3">
            {feature.title}
          </h3>
          <p className="text-slate-400 leading-relaxed">{feature.description}</p>

          {/* Decorative Elements */}
          {feature.size === "lg" && (
            <div className="mt-6 flex gap-3">
              {[Upload, Zap, Lock, TrendingUp].slice(0, 3).map((DecorIcon, i) => (
                <div
                  key={i}
                  className="w-10 h-10 bg-[#1e293b]/50 rounded-lg flex items-center justify-center border border-white/5"
                >
                  <DecorIcon className="w-5 h-5 text-slate-500" />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export function FeatureBento() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.2 });

  return (
    <section className="relative py-32 overflow-hidden">
      {/* Background Elements */}
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-0 w-96 h-96 bg-[#6366f1]/10 rounded-full blur-[120px]" />
      </div>

      <div ref={ref} className="relative max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            <span className="bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
              Capacités de Niveau Entreprise
            </span>
          </h2>
          <p className="text-xl text-slate-400 max-w-2xl mx-auto">
            Des fonctionnalités puissantes conçues pour les équipes de recrutement modernes qui exigent précision et rapidité.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {features.map((feature, index) => (
            <FeatureCard key={index} feature={feature} index={index} />
          ))}
        </div>
      </div>
    </section>
  );
}
