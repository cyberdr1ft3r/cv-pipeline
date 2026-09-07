"use client";
import { motion } from "motion/react";
import { Check, Zap, Building2, Rocket } from "lucide-react";
import { Navigation } from "../components/Navigation";
import { Footer } from "../components/Footer";
import Link from "next/link";

export default function PricingPage() {
  const plans = [
    {
      name: "Starter",
      icon: Zap,
      price: "499",
      period: "par mois",
      description: "Parfait pour les petites équipes de recrutement qui débutent avec le matching propulsé par l'IA.",
      features: [
        "Jusqu'à 5 utilisateurs",
        "500 téléchargements de CV / mois",
        "100 correspondances de postes / mois",
        "Analyses de base",
        "Support par email",
        "Intégrations standards",
        "1 Go de stockage",
      ],
      cta: "Essai Gratuit",
      popular: false,
    },
    {
      name: "Professionnel",
      icon: Building2,
      price: "1 499",
      period: "par mois",
      description: "Pour les entreprises en croissance nécessitant des fonctionnalités avancées et des volumes plus élevés.",
      features: [
        "Jusqu'à 25 utilisateurs",
        "5 000 téléchargements de CV / mois",
        "Matching de postes illimité",
        "Analyses et rapports avancés",
        "Support prioritaire",
        "Toutes les intégrations",
        "50 Go de stockage",
        "Workflows personnalisés",
        "Outils de collaboration d'équipe",
      ],
      cta: "Essai Gratuit",
      popular: true,
    },
    {
      name: "Entreprise",
      icon: Rocket,
      price: "Sur Mesure",
      period: "Contacter la vente",
      description: "Solutions adaptées aux grandes organisations avec des exigences spécifiques.",
      features: [
        "Utilisateurs illimités",
        "Téléchargements de CV illimités",
        "Matching de postes illimité",
        "Suite d'analyses d'entreprise",
        "Gestionnaire de succès dédié",
        "Intégrations personnalisées",
        "Stockage illimité",
        "SSO et sécurité avancée",
        "Accès API",
        "SLA personnalisé",
        "Option de déploiement sur site",
      ],
      cta: "Contacter la Vente",
      popular: false,
    },
  ];

  const faqs = [
    {
      question: "Puis-je changer de forfait plus tard ?",
      answer: "Absolument ! Vous pouvez mettre à niveau ou rétrograder votre forfait à tout moment. Les changements prennent effet immédiatement et nous ajusterons votre facturation au prorata.",
    },
    {
      question: "Y a-t-il un essai gratuit ?",
      answer: "Oui ! Nous offrons un essai gratuit de 14 jours sur nos forfaits Starter et Professionnel. Aucune carte de crédit requise.",
    },
    {
      question: "Que se passe-t-il si je dépasse mes limites ?",
      answer: "Nous vous informerons avant que vous n'atteigniez vos limites. Vous pourrez alors soit mettre à niveau votre forfait, soit acheter des packs supplémentaires.",
    },
    {
      question: "Proposez-vous des tarifs personnalisés ?",
      answer: "Oui ! Pour les clients Entreprise, nous créons des forfaits sur mesure basés sur vos besoins spécifiques, vos volumes et vos exigences d'intégration.",
    },
    {
      question: "Quelles intégrations supportez-vous ?",
      answer: "Nous nous intégrons aux principales plateformes ATS (Greenhouse, Lever, Workday), aux outils de communication (Slack, Teams), et plus encore. Les forfaits Entreprise incluent des intégrations personnalisées.",
    },
    {
      question: "Mes données sont-elles sécurisées ?",
      answer: "Absolument. Nous utilisons un chiffrement de niveau bancaire, sommes certifiés SOC 2 Type II et conformes au RGPD et à d'autres réglementations sur la protection des données.",
    },
  ];

  return (
    <main className="min-h-screen bg-[#0a0e27] text-white">
      <Navigation />
      
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center max-w-3xl mx-auto mb-20"
          >
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-indigo-100 to-purple-300 bg-clip-text text-transparent">
              Tarification Transparente
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed">
              Choisissez le forfait qui convient à votre équipe. Évoluez à votre rythme. Pas de frais cachés.
            </p>
          </motion.div>

          {/* Pricing Cards */}
          <div className="grid md:grid-cols-3 gap-8 max-w-7xl mx-auto">
            {plans.map((plan, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className={`relative backdrop-blur-xl border rounded-3xl p-8 transition-transform hover:scale-[1.02] ${
                  plan.popular
                    ? "bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border-indigo-500/50"
                    : "bg-white/5 border-white/10"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-indigo-600 rounded-full text-sm font-semibold shadow-lg">
                    Le plus populaire
                  </div>
                )}

                <div className="mb-6">
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4">
                    <plan.icon className="w-6 h-6 text-indigo-400" />
                  </div>
                  <h3 className="text-2xl font-bold mb-2">{plan.name}</h3>
                  <p className="text-slate-400 text-sm mb-6 min-h-[40px]">{plan.description}</p>
                  <div className="flex items-baseline gap-2 mb-2">
                    {plan.price !== "Sur Mesure" && <span className="text-slate-400">€</span>}
                    <span className="text-5xl font-bold">{plan.price}</span>
                  </div>
                  <p className="text-slate-400 text-sm">{plan.period}</p>
                </div>

                <button
                  className={`w-full py-4 rounded-xl font-semibold mb-8 transition-all ${
                    plan.popular
                      ? "bg-indigo-600 hover:bg-indigo-700 shadow-lg shadow-indigo-500/20"
                      : "backdrop-blur-xl bg-white/10 hover:bg-white/20 border border-white/20"
                  }`}
                >
                  {plan.cta}
                </button>

                <div className="space-y-4">
                  {plan.features.map((feature, fIndex) => (
                    <div key={fIndex} className="flex items-start gap-3">
                      <Check className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
                      <span className="text-slate-300 text-sm">{feature}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Questions Fréquemment Posées
            </h2>
            <p className="text-xl text-slate-400">
              Tout ce que vous devez savoir sur nos tarifs et forfaits.
            </p>
          </motion.div>

          <div className="grid gap-6">
            {faqs.map((faq, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 hover:bg-white/10 transition-colors"
              >
                <h3 className="text-xl font-bold mb-3">{faq.question}</h3>
                <p className="text-slate-400 leading-relaxed">{faq.answer}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer CTA */}
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
              Encore des questions ?
            </h2>
            <p className="text-xl text-slate-300 mb-8 max-w-2xl mx-auto">
              Notre équipe est là pour vous aider à trouver le forfait idéal pour votre organisation.
            </p>
            <Link
              href="/contact"
              className="inline-block px-8 py-4 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-colors shadow-lg shadow-indigo-500/30"
            >
              Parler à un Expert
            </Link>
          </motion.div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
