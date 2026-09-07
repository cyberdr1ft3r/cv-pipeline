"use client";
import { motion } from "motion/react";
import { Shield, Lock, Eye, FileText } from "lucide-react";
import { Navigation } from "../../components/Navigation";
import { Footer } from "../../components/Footer";
import Link from "next/link";

export default function PrivacyPage() {
  const sections = [
    {
      icon: FileText,
      title: "Informations que nous collectons",
      content: [
        {
          subtitle: "Informations sur le compte",
          text: "Lorsque vous créez un compte, nous collectons votre nom, votre adresse e-mail, le nom de votre entreprise et vos informations de facturation. Ces informations sont nécessaires pour fournir nos services et communiquer avec vous.",
        },
        {
          subtitle: "Données de CV et de Candidats",
          text: "Vous téléchargez des CV et des informations sur les candidats pour utiliser nos services de matching. Nous traitons ces données uniquement pour fournir nos fonctionnalités de matching et d'analyse basées sur l'IA. Nous ne vendons ni ne partageons jamais les données des candidats avec des tiers.",
        },
        {
          subtitle: "Données d'utilisation",
          text: "Nous collectons des données sur la manière dont vous utilisez notre plateforme, notamment les fonctionnalités consultées, les requêtes de recherche et les interactions système. Cela nous aide à améliorer nos services.",
        },
      ],
    },
    {
      icon: Lock,
      title: "Comment nous utilisons vos informations",
      content: [
        {
          subtitle: "Prestation de services",
          text: "Nous utilisons vos données pour fournir, maintenir et améliorer notre plateforme de matching de CV et d'intelligence des talents.",
        },
        {
          subtitle: "Amélioration de l'IA",
          text: "Des données agrégées et anonymisées peuvent être utilisées pour entraîner et améliorer nos modèles d'IA. Nous n'utilisons jamais d'informations identifiables sur les candidats à cette fin sans consentement explicite.",
        },
      ],
    },
    {
      icon: Shield,
      title: "Protection des données et Sécurité",
      content: [
        {
          subtitle: "Chiffrement",
          text: "Toutes les données sont chiffrées en transit via TLS 1.3 et au repos à l'aide d'un chiffrement AES-256. Nos normes de chiffrement respectent ou dépassent les meilleures pratiques de l'industrie.",
        },
        {
          subtitle: "Contrôles d'accès",
          text: "Nous appliquons des contrôles d'accès stricts basés sur les rôles. Seul le personnel autorisé peut accéder à vos données, et tous les accès sont enregistrés et surveillés.",
        },
      ],
    },
    {
      icon: Eye,
      title: "Vos droits et vos choix",
      content: [
        {
          subtitle: "Accès et Portabilité",
          text: "Vous avez le droit d'accéder à vos données et de demander une copie dans un format structuré et lisible par machine.",
        },
        {
          subtitle: "Correction et Suppression",
          text: "Vous pouvez mettre à jour ou supprimer vos données à tout moment via les paramètres de votre compte ou en contactant notre équipe de support.",
        },
      ],
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

        <div className="max-w-4xl mx-auto relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-6">
              <Shield className="w-8 h-8 text-indigo-400" />
            </div>
            <h1 className="text-4xl md:text-6xl font-bold mb-6">Politique de Confidentialité</h1>
            <p className="text-lg text-slate-400">Dernière mise à jour : 17 Avril 2026</p>
          </motion.div>

          {/* Privacy Sections */}
          <div className="space-y-12">
            {sections.map((section, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8"
              >
                <div className="flex items-start gap-4 mb-6">
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0">
                    <section.icon className="w-6 h-6 text-indigo-400" />
                  </div>
                  <h2 className="text-2xl font-bold">{section.title}</h2>
                </div>

                <div className="space-y-6 md:ml-16">
                  {section.content.map((item, idx) => (
                    <div key={idx}>
                      <h3 className="text-lg font-semibold mb-2 text-indigo-300">
                        {item.subtitle}
                      </h3>
                      <p className="text-slate-400 leading-relaxed">{item.text}</p>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="backdrop-blur-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-2xl p-8 mt-12 text-center"
          >
            <h2 className="text-2xl font-bold mb-4">Des questions ?</h2>
            <p className="text-slate-300 mb-6">
              Si vous avez des préoccupations concernant vos données, contactez-nous :
            </p>
            <p className="text-slate-400">
              <strong className="text-white">Email :</strong> privacy@itroad.consulting
            </p>
            <Link
              href="/contact"
              className="inline-block mt-6 px-8 py-3 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors"
            >
              Contactez-nous
            </Link>
          </motion.div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
