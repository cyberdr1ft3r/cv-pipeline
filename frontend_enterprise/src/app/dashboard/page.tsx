"use client";
import { motion } from "motion/react";
import { FileText, Brain, TrendingUp, Target, Sparkles, CheckCircle } from "lucide-react";
import { ImageWithFallback } from "../components/ui/ImageWithFallback";
import { Navigation } from "../components/Navigation";
import { Footer } from "../components/Footer";

export default function DashboardPage() {
  const features = [
    {
      icon: FileText,
      title: "Analyse de Fiches de Poste",
      description: "Téléchargez des descriptions de poste dans n'importe quel format. Notre IA extrait automatiquement les exigences, les compétences et les critères.",
    },
    {
      icon: Brain,
      title: "Matching Propulsé par l'IA",
      description: "L'apprentissage automatique avancé classe les candidats par score de pertinence, mettant instantanément en évidence les forces et les lacunes.",
    },
    {
      icon: TrendingUp,
      title: "Classements Intelligents",
      description: "Obtenez des listes de candidats classés avec des répartitions détaillées des correspondances, des chevauchements de compétences et de l'expérience.",
    },
    {
      icon: Target,
      title: "Filtrage de Précision",
      description: "Filtrez par compétences, lieu, expérience, éducation et critères personnalisés pour trouver votre candidat idéal.",
    },
    {
      icon: Sparkles,
      title: "Aperçus des Candidats",
      description: "Consultez des profils de candidats complets avec des résumés générés par l'IA et une analyse de corrélation.",
    },
    {
      icon: CheckCircle,
      title: "Automatisation du Workflow",
      description: "Automatisez la sélection, la présélection et la communication. Concentrez-vous sur les entretiens, pas sur l'administration.",
    },
  ];

  const stats = [
    { value: "95%", label: "Précision du Matching" },
    { value: "5min", label: "Temps de Matching Moyen" },
    { value: "80%", label: "Temps Gagné" },
    { value: "1000+", label: "Candidats Analysés / Jour" },
  ];

  const benefits = [
    "Réduisez le temps de recrutement de 60%",
    "Éliminez les biais inconscients grâce à l'IA",
    "Accédez à des profils de candidats à 360°",
    "Intégrez vos outils ATS existants",
    "Collaboration en temps réel pour les équipes",
    "Sécurité de niveau entreprise",
  ];

  return (
    <main className="min-h-screen bg-[#0a0e27] text-white">
      <Navigation />
      
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        {/* Animated Background */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 right-10 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
          <div className="absolute bottom-20 left-10 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
        </div>

        <div className="max-w-7xl mx-auto relative z-10 text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="max-w-4xl mx-auto mb-16"
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/10 border border-purple-500/20 mb-6 font-medium text-purple-400 text-sm">
              Centre de Commandement IT Road
            </div>
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-purple-100 to-purple-300 bg-clip-text text-transparent">
              Centre de Commandement du Recruteur
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed max-w-2xl mx-auto">
              Optimisez vos processus. Téléchargez vos descriptions de poste et recevez instantanément des correspondances de candidats classées par IA avec une précision inégalée.
            </p>
          </motion.div>

          {/* Stats Grid */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-20"
          >
            {stats.map((stat, index) => (
              <div
                key={index}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 text-center hover:bg-white/10 transition-colors"
              >
                <div className="text-4xl font-bold text-purple-400 mb-2">{stat.value}</div>
                <div className="text-sm text-slate-400 font-medium">{stat.label}</div>
              </div>
            ))}
          </motion.div>

          {/* Hero Image / Dashboard Preview */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="relative rounded-3xl overflow-hidden border border-white/10 backdrop-blur-xl bg-white/5 p-4 md:p-8"
          >
            <ImageWithFallback
              src="https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1200&h=600&fit=crop"
              alt="Dashboard IT Road Consulting"
              className="w-full h-auto rounded-xl shadow-2xl"
            />
          </motion.div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Recrutement Propulsé par <span className="text-purple-400">l'IA</span>
            </h2>
            <p className="text-xl text-slate-400 max-w-3xl mx-auto">
              Associez les candidats aux rôles avec une précision inédite grâce à l'apprentissage automatique avancé.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 hover:bg-white/10 transition-all group"
              >
                <div className="w-14 h-14 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <feature.icon className="w-7 h-7 text-purple-400" />
                </div>
                <h3 className="text-2xl font-bold mb-4">{feature.title}</h3>
                <p className="text-slate-400 leading-relaxed">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Benefits Section */}
      <section className="py-20 px-6 bg-white/[0.02]">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
            >
              <h2 className="text-4xl md:text-5xl font-bold mb-6">
                Pourquoi les recruteurs choisissent IT Road
              </h2>
              <p className="text-xl text-slate-400 mb-8">
                Des entreprises leader au startups en forte croissance, les recruteurs font confiance à IT Road Consulting pour recruter mieux et plus vite.
              </p>
              <div className="space-y-4">
                {benefits.map((benefit, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, x: -20 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6, delay: index * 0.1 }}
                    className="flex items-center gap-3"
                  >
                    <div className="w-6 h-6 rounded-full bg-purple-500/20 border border-purple-500/40 flex items-center justify-center flex-shrink-0">
                      <CheckCircle className="w-4 h-4 text-purple-400" />
                    </div>
                    <span className="text-lg text-slate-300">{benefit}</span>
                  </motion.div>
                ))}
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
              className="relative"
            >
              <ImageWithFallback
                src="https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=800&h=600&fit=crop"
                alt="Équipe IT Road Consulting"
                className="rounded-2xl shadow-2xl"
              />
              <div className="absolute -bottom-6 -left-6 backdrop-blur-xl bg-white/10 border border-white/20 rounded-2xl p-6">
                <div className="text-4xl font-bold text-purple-400 mb-1">4.9/5</div>
                <div className="text-sm text-slate-400">Satisfaction Client</div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="backdrop-blur-xl bg-gradient-to-br from-purple-500/20 to-indigo-500/20 border border-purple-500/30 rounded-3xl p-12 text-center"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Commencez à recruter plus intelligemment
            </h2>
            <p className="text-xl text-slate-300 mb-8 max-w-2xl mx-auto">
              Découvrez comment IT Road Consulting peut transformer vos recrutements en quelques minutes.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <button className="px-8 py-4 bg-purple-600 hover:bg-purple-700 rounded-xl font-semibold transition-colors shadow-lg shadow-purple-500/30">
                Demander une Démo
              </button>
              <button className="px-8 py-4 backdrop-blur-xl bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl font-semibold transition-colors">
                Voir les Tarifs
              </button>
            </div>
          </motion.div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
