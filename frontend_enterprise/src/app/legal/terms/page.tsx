"use client";
import { motion } from "motion/react";
import { FileText, AlertCircle, Scale, Users } from "lucide-react";
import { Navigation } from "../../components/Navigation";
import { Footer } from "../../components/Footer";
import Link from "next/link";

export default function TermsPage() {
  const sections = [
    {
      icon: Users,
      title: "1. Acceptation des Conditions",
      content: `En accédant ou en utilisant la plateforme et les services d'IT Road Consulting (les "Services"), vous acceptez d'être lié par ces Conditions d'Utilisation. Si vous n'acceptez pas ces conditions, vous ne pouvez pas utiliser nos Services.`,
    },
    {
      icon: FileText,
      title: "2. Description du Service",
      content: `IT Road Consulting fournit une plateforme de recrutement propulsée par l'IA incluant l'analyse de CV, le matching automatisé, et des outils d'analyse de données. Nos services sont conçus pour un usage professionnel de recrutement et de sourcing.`,
    },
    {
      icon: Scale,
      title: "3. Comptes et Responsabilités",
      content: `Vous êtes responsable du maintien de la confidentialité de vos identifiants de compte et de toutes les activités effectuées sous votre compte. Vous acceptez de fournir des informations exactes et à jour.`,
    },
  ];

  const additionalTerms = [
    {
      title: "4. Utilisation Acceptable",
      items: [
        "Utiliser les Services uniquement à des fins légales de recrutement",
        "Ne pas télécharger de code malveillant ou de virus",
        "Ne pas tenter d'accéder sans autorisation aux données d'autres utilisateurs",
        "Ne pas tenter d'extraire ou de rétro-concevoir nos modèles d'IA",
        "Respecter toutes les lois sur l'emploi et la non-discrimination",
      ],
    },
    {
      title: "5. Données et Propriété",
      items: [
        "Vous conservez la propriété de toutes les données de candidats et CV téléchargés",
        "Vous nous accordez une licence pour traiter ces données afin de fournir les Services",
        "Vous êtes responsable de la conformité aux lois sur la protection des données (RGPD, etc.)",
        "Nous pouvons utiliser des données anonymisées pour améliorer nos modèles d'IA",
      ],
    },
    {
      icon: AlertCircle,
      title: "Avis Important",
      content: "IT Road Consulting est un outil d'aide à la décision. Nous ne prenons pas de décisions d'embauche à votre place. Vous restez seul responsable de vos décisions d'emploi et du respect des lois en vigueur.",
    }
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
              <Scale className="w-8 h-8 text-indigo-400" />
            </div>
            <h1 className="text-4xl md:text-6xl font-bold mb-6">Conditions d'Utilisation</h1>
            <p className="text-lg text-slate-400">Dernière mise à jour : 17 Avril 2026</p>
          </motion.div>

          <div className="space-y-8 text-left">
            {sections.map((section, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8"
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0">
                    <section.icon className="w-6 h-6 text-indigo-400" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold mb-3">{section.title}</h2>
                    <p className="text-slate-400 leading-relaxed">{section.content}</p>
                  </div>
                </div>
              </motion.div>
            ))}

            {additionalTerms.map((term, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className={`backdrop-blur-xl border border-white/10 rounded-2xl p-8 ${term.icon ? 'bg-yellow-500/10 border-yellow-500/30' : 'bg-white/5'}`}
              >
                <div className="flex items-start gap-4">
                  {term.icon && <term.icon className="w-6 h-6 text-yellow-400 mt-1" />}
                  <div className="w-full">
                    <h2 className={`text-2xl font-bold mb-4 ${term.icon ? 'text-yellow-400' : 'text-white'}`}>{term.title}</h2>
                    {term.content ? (
                      <p className="text-slate-400 leading-relaxed">{term.content}</p>
                    ) : (
                      <ul className="space-y-3">
                        {term.items?.map((item, idx) => (
                          <li key={idx} className="flex items-start gap-3">
                            <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-2 flex-shrink-0" />
                            <span className="text-slate-400 leading-relaxed">{item}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
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
            <h2 className="text-2xl font-bold mb-4">Question sur ces conditions ?</h2>
            <p className="text-slate-300 mb-6 font-medium">
              Notre équipe juridique est à votre disposition pour toute précision.
            </p>
            <p className="text-slate-400">
              <strong className="text-white">Email :</strong> legal@itroad.consulting
            </p>
            <Link
              href="/contact"
              className="inline-block mt-6 px-8 py-3 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors"
            >
              Nous Contacter
            </Link>
          </motion.div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
