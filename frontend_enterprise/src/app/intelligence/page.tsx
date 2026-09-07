"use client";
import { motion } from "motion/react";
import { Upload, Database, Users, ChartBar, Shield, Zap } from "lucide-react";
import { ImageWithFallback } from "../components/ui/ImageWithFallback";
import { Navigation } from "../components/Navigation";
import { Footer } from "../components/Footer";
import Link from "next/link";

export default function SourcingIntelligencePage() {
  const features = [
    {
      icon: Upload,
      title: "Importation Massive de CV",
      description: "Téléchargez des centaines de CV simultanément avec une simplicité glisser-déposer. Notre IA les analyse et les catégorise instantanément.",
    },
    {
      icon: Database,
      title: "Gestion des Comptes",
      description: "Organisez les candidats par clients, projets et spécialisations. Le marquage intelligent garde votre vivier de talents structuré.",
    },
    {
      icon: Users,
      title: "Collaboration d'Équipe",
      description: "Les outils de collaboration en temps réel permettent à votre équipe de sourcing de travailler ensemble de manière fluide sur tous les comptes.",
    },
    {
      icon: ChartBar,
      title: "Analyses de Sourcing",
      description: "Suivez les métriques du pipeline, la qualité des sources et les performances de l'équipe grâce à des tableaux de bord complets.",
    },
    {
      icon: Shield,
      title: "Sécurité Entreprise",
      description: "Chiffrement de niveau bancaire, conformité SOC 2 et contrôles d'accès granulaires pour protéger les données sensibles des candidats.",
    },
    {
      icon: Zap,
      title: "Workflows Intelligents",
      description: "Automatisez les tâches répétitives avec des flux de travail intelligents. Concentrez-vous sur la recherche de talents, pas sur la gestion des données.",
    },
  ];

  const stats = [
    { value: "10x", label: "Traitement CV plus rapide" },
    { value: "500+", label: "CV par téléchargement" },
    { value: "99.8%", label: "Précision d'analyse" },
    { value: "24/7", label: "Support disponible" },
  ];

  return (
    <main className="min-h-screen bg-[#0a0e27] text-white">
      <Navigation />
      
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        {/* Animated Background */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-10 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-10 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
        </div>

        <div className="max-w-7xl mx-auto relative z-10 text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="max-w-4xl mx-auto mb-16"
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-indigo-500/10 border border-indigo-500/20 mb-6 font-medium text-indigo-400 text-sm">
              Intelligence de Sourcing IT Road
            </div>
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-indigo-100 to-indigo-300 bg-clip-text text-transparent">
              Intelligence de Sourcing
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed max-w-2xl mx-auto">
              Donnez à vos équipes de sourcing les moyens d'une gestion de CV pilotée par l'IA. Créez une base de données de talents consultable et performante.
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
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 text-center hover:bg-white/10 transition-transform"
              >
                <div className="text-4xl font-bold text-indigo-400 mb-2">{stat.value}</div>
                <div className="text-sm text-slate-400 font-medium">{stat.label}</div>
              </div>
            ))}
          </motion.div>

          {/* Feature Image */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="relative rounded-3xl overflow-hidden border border-white/10 backdrop-blur-xl bg-white/5 p-4 md:p-8"
          >
            <ImageWithFallback
              src="https://images.unsplash.com/photo-1551434678-e076c223a692?w=1200&h=600&fit=crop"
              alt="Analyse de Sourcing IT Road Consulting"
              className="w-full h-auto rounded-xl shadow-2xl"
            />
          </motion.div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Conçu pour les <span className="text-indigo-400">Équipes de Sourcing</span>
            </h2>
            <p className="text-xl text-slate-400 max-w-3xl mx-auto">
              Tout ce dont vous avez besoin pour gérer le sourcing de candidats à haut volume avec précision et rapidité.
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
                <div className="w-14 h-14 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <feature.icon className="w-7 h-7 text-indigo-400" />
                </div>
                <h3 className="text-2xl font-bold mb-4">{feature.title}</h3>
                <p className="text-slate-400 leading-relaxed">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="backdrop-blur-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-3xl p-12 text-center"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Prêt à transformer votre Sourcing ?
            </h2>
            <p className="text-xl text-slate-300 mb-8 max-w-2xl mx-auto">
              Rejoignez les entreprises leaders qui optimisent leurs viviers de talents avec IT Road.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <button className="px-8 py-4 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors shadow-lg shadow-indigo-500/30">
                Demander une Démo
              </button>
              <Link
                href="/pricing"
                className="px-8 py-4 backdrop-blur-xl bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl font-semibold transition-colors"
              >
                Voir les Tarifs
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
