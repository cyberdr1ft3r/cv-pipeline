"use client";
import { motion } from "motion/react";
import { Target, Users, Lightbulb, Award } from "lucide-react";
import { ImageWithFallback } from "../components/ui/ImageWithFallback";
import { Navigation } from "../components/Navigation";
import { Footer } from "../components/Footer";
import Link from "next/link";

export default function AboutPage() {
  const values = [
    {
      icon: Target,
      title: "Mission de Sens",
      description: "Nous avons pour mission d'éliminer les biais et l'inefficacité dans le recrutement grâce à une technologie intelligente.",
    },
    {
      icon: Users,
      title: "L'Humain d'Abord",
      description: "Nous croyons que la technologie doit au service de l'humain et non le remplacer. Notre IA optimise la prise de décision humaine.",
    },
    {
      icon: Lightbulb,
      title: "Innovation",
      description: "Nous repoussons les limites de l'IA et de l'apprentissage automatique pour résoudre les défis réels du recrutement.",
    },
    {
      icon: Award,
      title: "Excellence",
      description: "Nous nous engageons à fournir une qualité, une sécurité et un support de niveau entreprise dans tout ce que nous faisons.",
    },
  ];

  const team = [
    {
      name: "Sarah Chen",
      role: "CEO & Co-Fondatrice",
      image: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=400&h=400&fit=crop",
    },
    {
      name: "Marcus Johnson",
      role: "CTO & Co-Fondateur",
      image: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=400&h=400&fit=crop",
    },
    {
      name: "Priya Sharma",
      role: "Directrice IA",
      image: "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=400&h=400&fit=crop",
    },
    {
      name: "David Kim",
      role: "VP Produit",
      image: "https://images.unsplash.com/photo-1519345182560-3f2917c472ef?w=400&h=400&fit=crop",
    },
  ];

  const stats = [
    { value: "2019", label: "Année de Fondation" },
    { value: "500+", label: "Clients Entreprise" },
    { value: "50M+", label: "CVs Analysés" },
    { value: "150+", label: "Membres d'Équipe" },
  ];

  return (
    <main className="min-h-screen bg-[#0a0e27] text-white">
      <Navigation />
      
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-10 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-10 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
        </div>

        <div className="max-w-7xl mx-auto relative z-10 text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="max-w-4xl mx-auto mb-20"
          >
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-indigo-100 to-purple-300 bg-clip-text text-transparent">
              Transformer le Recrutement avec l'IA
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed">
              IT Road Consulting est né d'une conviction simple : trouver le bon talent ne devrait pas être un jeu de hasard. Nous construisons des outils intelligents qui aident les entreprises à prendre de meilleures décisions de recrutement, plus rapidement.
            </p>
          </motion.div>

          {/* Stats Grid */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-6"
          >
            {stats.map((stat, index) => (
              <div
                key={index}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 text-center hover:bg-white/10 transition-colors"
              >
                <div className="text-4xl font-bold text-indigo-400 mb-2">{stat.value}</div>
                <div className="text-sm text-slate-400">{stat.label}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Story Section */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
            >
              <h2 className="text-4xl md:text-5xl font-bold mb-6 text-white">Notre Histoire</h2>
              <div className="space-y-4 text-slate-300 leading-relaxed">
                <p>
                  IT Road Consulting a été fondé en 2019 par d'anciens recruteurs et ingénieurs en IA qui ont personnellement vécu les inefficacités du recrutement moderne. Passer des heures à trier manuellement des CV, voir de grands candidats passer à travers les mailles du filet et observer des biais s'immiscer dans les décisions — ils savaient qu'il devait y avoir une meilleure méthode.
                </p>
                <p>
                  Aujourd'hui, nous sommes une équipe de plus de 150 personnes passionnées réparties entre l'Europe et l'Asie. Nous avons traité plus de 50 millions de CV et aidé plus de 500 entreprises à recruter plus intelligemment.
                </p>
                <p>
                  Notre technologie combine les dernières avancées en traitement du langage naturel et apprentissage automatique avec des années d'expertise en recrutement pour offrir une plateforme à la fois puissante et intuitive.
                </p>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
            >
              <ImageWithFallback
                src="https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=800&h=600&fit=crop"
                alt="Équipe IT Road Consulting"
                className="rounded-2xl shadow-2xl"
              />
            </motion.div>
          </div>
        </div>
      </section>

      {/* Values Section */}
      <section className="py-20 px-6 bg-white/[0.02]">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">Nos Valeurs</h2>
            <p className="text-xl text-slate-400 max-w-3xl mx-auto">
              Ces principes guident tout ce que nous faisons, du développement de produits au support client.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {values.map((value, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 text-center"
              >
                <div className="w-14 h-14 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-6">
                  <value.icon className="w-7 h-7 text-indigo-400" />
                </div>
                <h3 className="text-xl font-bold mb-3">{value.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{value.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Team Section */}
      <section className="py-20 px-6 font-bold">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6 text-white">Notre Leadership</h2>
            <p className="text-xl text-slate-400 max-w-3xl mx-auto">
              Des leaders expérimentés issus de la tech, de l'IA et du recrutement.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {team.map((member, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="text-center"
              >
                <div className="mb-6 relative group overflow-hidden rounded-2xl">
                  <ImageWithFallback
                    src={member.image}
                    alt={member.name}
                    className="w-full aspect-square object-cover"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-indigo-600/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <h3 className="text-xl font-bold mb-2 text-white">{member.name}</h3>
                <p className="text-slate-400 font-medium">{member.role}</p>
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
            <h2 className="text-4xl md:text-5xl font-bold mb-6">Rejoignez l'aventure</h2>
            <p className="text-xl text-slate-300 mb-8 max-w-2xl mx-auto">
              Nous recherchons toujours des talents qui partagent notre passion pour la transformation du recrutement.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/contact"
                className="px-8 py-4 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors shadow-lg shadow-indigo-500/30"
              >
                Nous Contacter
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
