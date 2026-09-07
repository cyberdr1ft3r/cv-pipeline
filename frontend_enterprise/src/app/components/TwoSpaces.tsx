import { motion } from "motion/react";
import { useInView } from "motion/react";
import { useRef } from "react";
import {
  Users,
  Briefcase,
  FileUp,
  GitBranch,
  Database,
  Star,
  TrendingUp,
  FileCheck,
} from "lucide-react";

const spaces = [
  {
    title: "Intelligence de Sourcing",
    subtitle: "Pour les Équipes de Sourcing",
    icon: Users,
    gradient: "from-[#6366f1] to-[#818cf8]",
    features: [
      {
        icon: Database,
        title: "Gestion de Comptes",
        description: "Gérez vos comptes clients avec des portails dédiés",
      },
      {
        icon: Briefcase,
        title: "Suivi de Postes",
        description: "Suivez tous les postes ouverts sur plusieurs clients",
      },
      {
        icon: FileUp,
        title: "Import Massif de CV",
        description: "Téléchargez des CV en PDF, DOCX et formats scannés",
      },
      {
        icon: GitBranch,
        title: "Organisation du Pipeline",
        description: "Organisez les candidats par rôle, statut et priorité",
      },
    ],
  },
  {
    title: "Centre de Commandement",
    subtitle: "Pour les Recruteurs",
    icon: Star,
    gradient: "from-[#818cf8] to-[#a78bfa]",
    features: [
      {
        icon: FileCheck,
        title: "Import de Fiches de Poste",
        description: "Téléchargez vos descriptions de poste et définissez les exigences",
      },
      {
        icon: TrendingUp,
        title: "Matching IA",
        description: "Recevez des classements et des scores de matching par IA",
      },
      {
        icon: Star,
        title: "Résultats de Tests",
        description: "Consultez les évaluations techniques et de compétences",
      },
      {
        icon: Users,
        title: "Accès aux Profils",
        description: "Accédez instantanément à des profils de candidats formatés",
      },
    ],
  },
];

interface SpaceCardProps {
  space: typeof spaces[0];
  index: number;
}

function SpaceCard({ space, index }: SpaceCardProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.3 });
  const Icon = space.icon;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 50 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 50 }}
      transition={{ duration: 0.6, delay: index * 0.2 }}
      className="relative group"
    >
      <div className="h-full bg-[#111827]/50 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:border-white/20 transition-all duration-300 hover:shadow-2xl hover:shadow-indigo-500/10">
        {/* Gradient Background */}
        <div
          className={`absolute inset-0 bg-gradient-to-br ${space.gradient} opacity-5 rounded-2xl group-hover:opacity-10 transition-opacity`}
        />

        <div className="relative">
          {/* Header */}
          <div className="flex items-start gap-4 mb-8">
            <div
              className={`w-16 h-16 bg-gradient-to-br ${space.gradient} rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/30 group-hover:scale-110 transition-transform`}
            >
              <Icon className="w-8 h-8 text-white" />
            </div>
            <div>
              <p className="text-sm text-slate-400 mb-1">{space.subtitle}</p>
              <h3 className="text-2xl font-semibold text-white">
                {space.title}
              </h3>
            </div>
          </div>

          {/* Features Grid */}
          <div className="space-y-4">
            {space.features.map((feature, idx) => {
              const FeatureIcon = feature.icon;
              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -20 }}
                  animate={
                    isInView ? { opacity: 1, x: 0 } : { opacity: 0, x: -20 }
                  }
                  transition={{ duration: 0.4, delay: index * 0.2 + idx * 0.1 }}
                  className="flex items-start gap-3 p-4 bg-[#0a0e27]/30 rounded-xl border border-white/5 hover:border-white/10 transition-all group/item"
                >
                  <div className="w-10 h-10 bg-[#1e293b] rounded-lg flex items-center justify-center flex-shrink-0 group-hover/item:bg-[#334155] transition-colors">
                    <FeatureIcon className="w-5 h-5 text-slate-400 group-hover/item:text-[#818cf8] transition-colors" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-white mb-1">
                      {feature.title}
                    </h4>
                    <p className="text-sm text-slate-400">
                      {feature.description}
                    </p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export function TwoSpaces() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.2 });

  return (
    <section className="relative py-32 overflow-hidden">
      {/* Background Elements */}
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-96 bg-[#6366f1]/10 rounded-full blur-[120px]" />
      </div>

      <div ref={ref} className="relative max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-[#1e293b]/50 backdrop-blur-sm border border-white/10 rounded-full mb-6">
            <span className="text-sm text-[#818cf8]">Deux Espaces de Travail Puissants</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            <span className="bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
              Conçu pour Toute Votre Équipe
            </span>
          </h2>
          <p className="text-xl text-slate-400 max-w-2xl mx-auto">
            Des environnements spécialisés pour les sourceurs et les recruteurs, unis par l'automatisation intelligente.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {spaces.map((space, index) => (
            <SpaceCard key={index} space={space} index={index} />
          ))}
        </div>
      </div>
    </section>
  );
}
