"use client";
import { motion } from "motion/react";
import { Shield, Lock, FileCheck, Download, Trash2, Eye } from "lucide-react";
import { Navigation } from "../../components/Navigation";
import { Footer } from "../../components/Footer";
import Link from "next/link";

export default function GDPRPage() {
  const rights = [
    {
      icon: Eye,
      title: "Droit d'Accès",
      description: "Vous avez le droit de demander une copie de toutes les données personnelles que nous détenons à votre sujet. Nous fournirons ces informations dans un format structuré sous 30 jours.",
    },
    {
      icon: FileCheck,
      title: "Droit de Rectification",
      description: "Vous pouvez demander la correction de données personnelles inexactes ou incomplètes. Nous mettrons à jour vos informations rapidement après vérification.",
    },
    {
      icon: Trash2,
      title: "Droit à l'Effacement",
      description: "Aussi connu sous le nom de 'droit à l'oubli', vous pouvez demander la suppression de vos données personnelles sous certaines conditions.",
    },
    {
      icon: Lock,
      title: "Droit à la Limitation",
      description: "Vous pouvez demander que nous limitions la manière dont nous traitons vos données pendant que nous vérifions leur exactitude.",
    },
    {
      icon: Download,
      title: "Droit à la Portabilité",
      description: "Vous avez le droit de recevoir vos données dans un format structuré et couramment utilisé pour les transférer à un autre prestataire.",
    },
    {
      icon: Shield,
      title: "Droit d'Opposition",
      description: "Vous pouvez vous opposer au traitement de vos données pour le marketing direct, la recherche ou lorsque le traitement est basé sur des intérêts légitimes.",
    },
  ];

  return (
    <main className="min-h-screen bg-[#0a0e27] text-white">
      <Navigation />
      
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
        </div>

        <div className="max-w-4xl mx-auto relative z-10 text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="mb-16"
          >
            <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-6">
              <Shield className="w-8 h-8 text-indigo-400" />
            </div>
            <h1 className="text-4xl md:text-6xl font-bold mb-6">Conformité RGPD</h1>
            <p className="text-lg text-slate-400">Dernière mise à jour : 17 Avril 2026</p>
            <p className="text-slate-300 mt-4 leading-relaxed max-w-2xl mx-auto">
              IT Road Consulting s'engage pleinement à protéger vos droits à la vie privée conformément au Règlement Général sur la Protection des Données (RGPD).
            </p>
          </motion.div>

          {/* GDPR Rights Grid */}
          <div className="grid md:grid-cols-2 gap-6 text-left mb-16">
            {rights.map((right, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 hover:bg-white/10 transition-colors"
              >
                <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4">
                  <right.icon className="w-6 h-6 text-indigo-400" />
                </div>
                <h3 className="text-xl font-bold mb-3">{right.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{right.description}</p>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 mb-12 text-left"
          >
            <h2 className="text-2xl font-bold mb-4">Délégué à la Protection des Données (DPO)</h2>
            <p className="text-slate-400 mb-6">
              IT Road Consulting a nommé un DPO pour superviser la conformité au RGPD. Vous pouvez le contacter à :
            </p>
            <p className="text-slate-300">
              <strong className="text-white">Email :</strong> dpo@itroad.consulting
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-2xl p-8 text-center"
          >
            <h2 className="text-2xl font-bold mb-4">Exercer vos droits</h2>
            <p className="text-slate-300 mb-6 font-medium">
              Pour exercer vos droits, soumettez une demande via les paramètres de votre compte ou contactez notre DPO.
            </p>
            <Link
              href="/contact"
              className="inline-block px-8 py-3 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors shadow-lg shadow-indigo-500/20"
            >
              Soumettre une demande RGPD
            </Link>
          </motion.div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
