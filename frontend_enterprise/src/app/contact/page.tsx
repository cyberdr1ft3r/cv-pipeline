"use client";
import { motion } from "motion/react";
import { Mail, Phone, MapPin, Send } from "lucide-react";
import { useState } from "react";
import { Navigation } from "../components/Navigation";
import { Footer } from "../components/Footer";
import Link from "next/link";
import { DarkSelect } from "@/components/DarkSelect";

const INTEREST_OPTIONS = [
  { value: "demo", label: "Programmer une démo" },
  { value: "pricing", label: "Informations sur les tarifs" },
  { value: "enterprise", label: "Solutions Entreprise" },
  { value: "partnership", label: "Opportunités de partenariat" },
  { value: "support", label: "Support technique" },
  { value: "other", label: "Autre" },
];

export default function ContactPage() {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    company: "",
    phone: "",
    interest: "demo",
    message: "",
  });

  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Simulation d'envoi
    setSubmitted(true);
    setTimeout(() => setSubmitted(false), 5000);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const contactInfo = [
    {
      icon: Mail,
      title: "Email",
      value: "contact@itroad.consulting",
      href: "mailto:contact@itroad.consulting",
    },
    {
      icon: Phone,
      title: "Téléphone",
      value: "+33 (0) 1 23 45 67 89",
      href: "tel:+33123456789",
    },
    {
      icon: MapPin,
      title: "Siège Social",
      value: "Paris, France",
      href: null,
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
              Discutons Ensemble
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed">
              Que vous soyez prêt pour une démo, ayez des questions ou souhaitiez discuter de solutions personnalisées, nous sommes là pour vous aider.
            </p>
          </motion.div>

          {/* Contact Info Cards */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="grid md:grid-cols-3 gap-6 mb-20"
          >
            {contactInfo.map((info, index) => (
              <div
                key={index}
                className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 text-center hover:bg-white/10 transition-colors"
              >
                <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-4">
                  <info.icon className="w-6 h-6 text-indigo-400" />
                </div>
                <h3 className="font-semibold mb-2 text-white">{info.title}</h3>
                {info.href ? (
                  <a
                    href={info.href}
                    className="text-slate-300 hover:text-indigo-400 transition-colors"
                  >
                    {info.value}
                  </a>
                ) : (
                  <p className="text-slate-300">{info.value}</p>
                )}
              </div>
            ))}
          </motion.div>

          {/* Contact Form & Side Info */}
          <div className="grid md:grid-cols-2 gap-12 items-start max-w-7xl mx-auto">
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8, delay: 0.4 }}
            >
              <h2 className="text-3xl font-bold mb-6 text-white">Envoyez-nous un message</h2>
              <p className="text-slate-400 mb-8 leading-relaxed">
                Remplissez le formulaire et notre équipe vous répondra sous 24 heures pendant les jours ouvrables.
              </p>

              <div className="space-y-6 text-sm text-slate-400">
                <div>
                  <h3 className="font-semibold text-white mb-2 underline decoration-indigo-500/50">Demandes Commerciales</h3>
                  <p>Pour les tarifs, démos et solutions d'entreprise.</p>
                </div>
                <div>
                  <h3 className="font-semibold text-white mb-2 underline decoration-indigo-500/50">Support Technique</h3>
                  <p>Clients actuels : support@itroad.consulting</p>
                </div>
                <div>
                  <h3 className="font-semibold text-white mb-2 underline decoration-indigo-500/50">Partenariats</h3>
                  <p>Intéressé par un partenariat ? partnerships@itroad.consulting</p>
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8, delay: 0.4 }}
              className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8 shadow-2xl"
            >
              {submitted ? (
                <div className="text-center py-12">
                  <div className="w-16 h-16 rounded-full bg-green-500/20 border border-green-500/40 flex items-center justify-center mx-auto mb-4">
                    <Send className="w-8 h-8 text-green-400" />
                  </div>
                  <h3 className="text-2xl font-bold mb-2">Message Envoyé !</h3>
                  <p className="text-slate-400">
                    Merci de nous avoir contactés. Nous reviendrons vers vous très prochainement.
                  </p>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-6">
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="name" className="block text-sm font-medium mb-2 opacity-80">
                        Nom Complet *
                      </label>
                      <input
                        type="text"
                        id="name"
                        name="name"
                        required
                        value={formData.name}
                        onChange={handleChange}
                        className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-indigo-500/50 focus:outline-none transition-colors"
                        placeholder="Jean Dupont"
                      />
                    </div>
                    <div>
                      <label htmlFor="email" className="block text-sm font-medium mb-2 opacity-80">
                        Email Professionnel *
                      </label>
                      <input
                        type="email"
                        id="email"
                        name="email"
                        required
                        value={formData.email}
                        onChange={handleChange}
                        className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-indigo-500/50 focus:outline-none transition-colors"
                        placeholder="jean@entreprise.com"
                      />
                    </div>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="company" className="block text-sm font-medium mb-2 opacity-80">
                        Entreprise *
                      </label>
                      <input
                        type="text"
                        id="company"
                        name="company"
                        required
                        value={formData.company}
                        onChange={handleChange}
                        className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-indigo-500/50 focus:outline-none transition-colors"
                        placeholder="Acme Inc."
                      />
                    </div>
                    <div>
                      <label htmlFor="phone" className="block text-sm font-medium mb-2 opacity-80">
                        Téléphone
                      </label>
                      <input
                        type="tel"
                        id="phone"
                        name="phone"
                        value={formData.phone}
                        onChange={handleChange}
                        className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-indigo-500/50 focus:outline-none transition-colors"
                        placeholder="+33 6 00 00 00 00"
                      />
                    </div>
                  </div>

                  <div>
                    <label htmlFor="interest" className="block text-sm font-medium mb-2 opacity-80">
                      Je suis intéressé par *
                    </label>
                    <DarkSelect
                      value={formData.interest}
                      onChange={v => setFormData(prev => ({ ...prev, interest: v }))}
                      options={INTEREST_OPTIONS}
                      className="w-full"
                    />
                  </div>

                  <div>
                    <label htmlFor="message" className="block text-sm font-medium mb-2 opacity-80">
                      Message *
                    </label>
                    <textarea
                      id="message"
                      name="message"
                      required
                      rows={4}
                      value={formData.message}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-indigo-500/50 focus:outline-none transition-colors resize-none"
                      placeholder="Parlez-nous de vos besoins..."
                    />
                  </div>

                  <button
                    type="submit"
                    className="w-full px-8 py-4 bg-indigo-600 hover:bg-indigo-700 rounded-xl font-semibold transition-all flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/20 active:scale-[0.98]"
                  >
                    <Send className="w-5 h-5" />
                    Envoyer le Message
                  </button>

                  <p className="text-xs text-slate-500 text-center">
                    En soumettant ce formulaire, vous acceptez notre{" "}
                    <Link href="/legal/privacy" className="text-indigo-400 hover:underline">
                      Politique de Confidentialité
                    </Link>
                  </p>
                </form>
              )}
            </motion.div>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
